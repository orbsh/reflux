"""Signals: a value that tells its readers when it changed.

Three kinds, one rule — read to depend, write to notify:

- `Signal` — a value. `s.value` reads it (inside an effect, that read is a subscription) and
  `s.value = x` writes it.
- `Computed` — a value derived from others: recomputed when something it read goes stale, and **not
  passed on** when it comes out equal, so a filter that changes nothing does not redraw a list.
- `Effect` — code that read something. `effect(fn)` runs it now and again whenever what it read changes.

`batch()` holds one propagation round open: a handler that touches three signals writes the page once.

What this layer does *not* do is write the page. An effect writes a slot — the same
`ctx.slot(name).set(...)` a handler would have written by hand — so the layer only decides **who**
writes, never what a write is. That keeps the write path exactly as it was (one write is one frame) and
makes this layer optional: a page can use it for one number and keep writing the rest by hand.

`bound` and `into` are the two lines where the two worlds meet: `bound(ctx, name, value)` is a signal
that owns a slot, `into(ctx, name, computed)` is a computed mirrored onto one. Both write through
`ctx.slot`, so the app's `view` still decides what a value looks like.

Scope: a signal made inside a page belongs to that connection (it holds that connection's `Slot`), and
dies with it; a signal made at module level is shared by every connection, and every reader is told.
"""

from __future__ import annotations

import operator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Generic, Iterator, TypeVar

__all__ = ["Computed", "Effect", "Signal", "batch", "bound", "effect", "into", "keyed"]

T = TypeVar("T")
_UNSET = object()

# Who is reading right now (an effect or a computed), how deep the current propagation round is, and
# what still has to run when it ends. Three ContextVars: a connection is a task, so two connections never
# see each other's dependencies.
_tracking: ContextVar[Any] = ContextVar("reflux_signals_tracking", default=None)
_depth: ContextVar[int] = ContextVar("reflux_signals_depth", default=0)
_queue: ContextVar[list["Effect"] | None] = ContextVar("reflux_signals_queue", default=None)


@contextmanager
def _round() -> Iterator[None]:
    """One propagation round: the outermost writer opens it, writers inside it ride along."""
    depth = _depth.get()
    outer = depth == 0
    token_depth = _depth.set(depth + 1)
    token_queue = _queue.set([]) if outer else None
    try:
        yield
    finally:
        if outer:
            queued = _queue.get() or []
            _depth.reset(token_depth)
            if token_queue is not None:
                _queue.reset(token_queue)
            for running in queued:  # every node is marked first, then the effects run
                running.invalidate()
        else:
            _depth.reset(token_depth)


batch = _round


def _depend(node: Any) -> None:
    """Record that whoever is reading now depends on `node`."""
    reader = _tracking.get()
    if reader is None or reader is node:
        return
    node._observers.add(reader)
    reader._sources.append(node)


class Signal(Generic[T]):
    """A value. Reads subscribe, writes notify — and an equal write is not a change."""

    __slots__ = ("_value", "_observers", "_equal", "_write", "_version")

    def __init__(
        self,
        value: T,
        *,
        equal: Callable[[T, T], bool] = operator.eq,
        write: Callable[[T], None] | None = None,
    ) -> None:
        self._value = value
        self._observers: set[Any] = set()
        self._equal = equal
        self._write = write
        self._version = 0  # bumped only when the value really changes; readers compare it

    @property
    def value(self) -> T:
        _depend(self)
        return self._value

    @value.setter
    def value(self, new: T) -> None:
        if self._equal(self._value, new):
            return
        self._value = new
        self._version += 1
        if self._write is not None:
            self._write(new)  # the slot hears it first, then the readers
        self._notify()

    def _notify(self) -> None:
        if not self._observers:
            return
        with _round():
            for observer in list(self._observers):
                observer.stale()

    def __repr__(self) -> str:
        return f"<Signal {self._value!r}>"


class Computed(Generic[T]):
    """A value computed from others: cached while clean, recomputed when stale, quiet when unchanged."""

    __slots__ = ("_fn", "_value", "_dirty", "_sources", "_observers", "_equal", "_version")

    def __init__(self, fn: Callable[[], T], *, equal: Callable[[T, T], bool] = operator.eq) -> None:
        self._fn = fn
        self._value: Any = _UNSET
        self._dirty = True
        self._sources: list[Any] = []
        self._observers: set[Any] = set()
        self._equal = equal
        self._version = 0

    @property
    def value(self) -> T:
        _depend(self)
        if self._dirty:
            self._recompute()
        return self._value

    def _recompute(self) -> None:
        self._forget()
        reader = _tracking.get()  # whoever pulled this read already gets the new value
        token = _tracking.set(self)
        try:
            value = self._fn()
        finally:
            _tracking.reset(token)
        previous, self._value, self._dirty = self._value, value, False
        if previous is _UNSET or self._equal(previous, value):
            return  # Truncation: an equal answer stops here — nobody downstream has to look again.
        self._version += 1
        for observer in list(self._observers):
            if observer is not reader:  # ...and the reader that pulled it is already holding it
                observer.stale(maybe=True)

    def stale(self) -> None:
        if self._dirty:
            return
        self._dirty = True
        for observer in list(self._observers):
            observer.stale(maybe=True)  # stale is not the same as changed: the pull decides

    def _forget(self) -> None:
        for source in self._sources:
            source._observers.discard(self)
        self._sources.clear()

    def __repr__(self) -> str:
        return f"<Computed {'stale' if self._dirty else 'clean'}>"


class Effect:
    """Code that read something: runs now, and again when a dependency changes.

    "A dependency changed" has two strengths. A `Signal` *knows* it changed, so the effect runs. A
    `Computed` only knows it went stale — its new value may come out equal — so the effect is queued as a
    *maybe*: at flush time the computed is pulled, and the effect runs only if some source's version really
    moved. Without that, a filter that returns the same list would still redraw it.
    """

    __slots__ = ("_fn", "_sources", "_queued", "_maybe", "_seen")

    def __init__(self, fn: Callable[[], None]) -> None:
        self._fn = fn
        self._sources: list[Any] = []
        self._queued = False
        self._maybe = False
        self._seen: list[tuple[Any, int]] = []

    def run(self) -> None:
        for source in self._sources:
            source._observers.discard(self)
        self._sources.clear()
        self._queued = self._maybe = False
        token = _tracking.set(self)
        try:
            self._fn()
        finally:
            _tracking.reset(token)
        self._seen = [(source, source._version) for source in self._sources]

    def stale(self, maybe: bool = False) -> None:
        """A dependency changed (`maybe`: a computed went stale — it may come out the same)."""
        if not self._queued:
            self._queued = True
            queue = _queue.get()
            if queue is not None:
                queue.append(self)
            else:
                with _round():  # a write outside any round still runs its effects, once marking is done
                    queue = _queue.get()
                    if queue is not None:
                        queue.append(self)
        self._maybe = self._maybe or maybe

    def invalidate(self) -> None:
        self.settle()

    def settle(self) -> None:
        """Pull the stale computeds, then run — unless nothing this effect read actually changed."""
        if self._maybe:
            self._maybe = False
            for source in list(self._sources):
                if isinstance(source, Computed) and source._dirty:
                    source.value  # a pull: recomputes, and truncates when the answer is the same
            if all(source._version == version for source, version in self._seen):
                self._queued = False
                return
        self.run()

    def __repr__(self) -> str:
        return "<Effect>"


def effect(fn: Callable[[], None]) -> Effect:
    """Run `fn` now, and again whenever something it read changes."""
    node = Effect(fn)
    node.run()
    return node


def bound(ctx: Any, name: str, value: T, **kwargs: Any) -> Signal[T]:
    """A signal that owns the slot `name`: every change is written there, and the first value seeds it.

    The write is `ctx.slot(name).set(value)` — the app's `view` still decides what a value looks like,
    so a page keeps rendering `h.text(source=slots.<same name>)` exactly as before.
    """
    slot = ctx.slot(name)
    signal: Signal[T] = Signal(value, write=slot.set, **kwargs)
    slot.set(value)
    return signal


def into(ctx: Any, name: str, computed: Computed[Any]) -> Computed[Any]:
    """Mirror `computed` onto the slot `name`, once now and once per change."""
    slot = ctx.slot(name)
    effect(lambda: slot.set(computed.value))
    return computed


def keyed(
    ctx: Any,
    name: str,
    rows: Signal[list[tuple[str, Any]]],
    render: Callable[[Any, str], Any],
) -> Effect:
    """Keep the list slot `name` equal to `rows`, by id: append what is new, remove what is gone.

    `rows` is `[(id, item), ...]` in the order to show, and `render(item, row_id)` must build the row
    with that id — a row's identity comes from the data, never from its position. The rendered ids are
    tracked here, so a page does not have to remember them (that bookkeeping was the counter's
    `State.ids`).

    Reordering moves the fewest rows that can express it: the rows already in relative order (a longest
    increasing run, by where they sit on screen) are left alone, and each of the rest is moved to its
    own place — one `move` per row, and none at all when the order did not change. A `move`'s position
    is counted with the row lifted out (fluxen ADR 0005), so placing row `i` is `-(i + 1)`: `-1` is the
    head, and by then everything wanted before it is already there in order.
    """
    slot = ctx.slot(name)
    shown: list[str] = []

    def sync() -> None:
        want = [row_id for row_id, _ in rows.value]
        wanted = set(want)
        for old in list(shown):
            if old not in wanted:
                slot.remove(old)
                shown.remove(old)
        for row_id, item in rows.value:
            if row_id not in shown:
                slot.append(render(item, row_id))
                shown.append(row_id)
        # Appended rows land at the tail, and a list that is only appended to keeps its order; a fresh
        # draw rebuilds nothing because `shown` is empty on the first pass.
        _reorder(slot, shown, want)

    return effect(sync)


def _reorder(slot: Any, shown: list[str], want: list[str]) -> None:
    """Bring `shown` into `want`'s order with as few moves as the order allows, and keep `shown` true."""
    if shown == want:
        return
    places = {row_id: index for index, row_id in enumerate(shown)}
    order = [places[row_id] for row_id in want]
    stay = {want[index] for index in _longest_run(order)}
    for index, row_id in enumerate(want):
        if row_id in stay:
            continue
        # `-(index + 1)` is "before the (index+1)-th row from the head" counted with this row lifted,
        # so the last place is the end, which only `0` names (`-n` stops one short of it).
        slot.move(row_id, 0 if index == len(want) - 1 else -(index + 1))
        shown.remove(row_id)
        shown.insert(index, row_id)


def _longest_run(order: list[int]) -> list[int]:
    """Indices of one longest strictly increasing run: the rows that are already in relative order."""
    tails: list[int] = []  # tails[k] = index in `order` ending the best run of length k + 1
    previous = [-1] * len(order)
    for index, spot in enumerate(order):
        low, high = 0, len(tails)
        while low < high:
            middle = (low + high) // 2
            if order[tails[middle]] < spot:
                low = middle + 1
            else:
                high = middle
        previous[index] = tails[low - 1] if low else -1
        if low == len(tails):
            tails.append(index)
        else:
            tails[low] = index
    run: list[int] = []
    at = tails[-1] if tails else -1
    while at != -1:
        run.append(at)
        at = previous[at]
    run.reverse()
    return run