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

`Signal` is the value, and what it is attached to is read off the signal:

    value = Signal(0).store("counter.step")        # survives the connection (see `stores.py`)
    count = Signal(0).bind(slots / "counter" / "count").view(lambda v: h.text(str(v)))
    hint  = Computed(fn).bind(slots / "counter" / "hint")
    rows  = Signal([]).bind(slots / "counter" / "history").keyed(row_node)

Scope: a signal made inside a page belongs to that connection (it holds that connection's `Slot` or its
`ctx.data`), and dies with it; a signal made at module level is shared by every connection, and every
reader is told.
"""

from __future__ import annotations

import operator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Generic, Iterator, TypeVar

__all__ = ["Computed", "Effect", "Signal", "batch", "drawing", "effect", "keyed"]

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

    __slots__ = (
        "_value", "_observers", "_equal", "_write", "_version", "_slot", "_keyed", "_stored",
        "_pending_keyed", "_keyed_done", "_keyed_effect",
    )

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
        self._slot: Any = None  # set by `bind`
        self._keyed = False  # set by `keyed`, so a second draw does not stack effects
        self._stored = False  # set by `store`, so a second draw returns the held one
        self._pending_keyed: Callable[[Any, str], Any] | None = None
        self._keyed_done = False
        self._keyed_effect: Any = None

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

    def bind(self, slot: Any) -> "Signal":
        """Write through to `slot`: seeded once, then every change goes there. Identity = the slot's name.

        A page is drawn again on every delivery, so the same declaration runs again — the table hands
        back the first signal instead of seeding the slot a second time.
        """
        cells = _cells(slot.ctx)
        held = cells.get(slot.name)
        if held is not None:
            if not isinstance(held, Signal):
                raise RuntimeError(
                    f"slot {slot.name!r} already has a {type(held).__name__}: one value per name"
                )
            return held
        cells[slot.name] = self
        self._slot = slot
        inner = self._write

        def write(new: T) -> None:
            if inner is not None:
                inner(new)
            if not self._keyed:  # a keyed list reaches the slot by the effect, one row at a time
                slot.set(new)

        self._write = write
        if self._keyed:
            self._install_keyed()  # a keyed list's first write is its rows, not the list
        else:
            # The first value is a write like any other — the view still decides the node — but it waits
            # for the end of the draw, because the page declares `.view(...)` after this line.
            _defer(lambda: None if self._keyed else slot.set(self.value))
        return self

    def view(self, render: Callable[[Any], Any]) -> "Signal":
        """Say how this value becomes a node, once: `Signal(0).bind(slot).view(lambda v: h.text(v))`."""
        self._need_slot("view").view(render)
        return self

    def keyed(self, render: Callable[[Any, str], Any]) -> "Signal":
        """A list slot kept equal to this one, by id: `render(item, row_id)` builds a row.

        Declared before `.bind(...)` — a keyed list's first write is the rows it appends, never the list
        as a value, so the seed a bind would make is not made at all.
        """
        self._keyed = True
        self._pending_keyed = render
        if self._slot is not None:
            self._install_keyed()
        return self

    def _install_keyed(self) -> None:
        if self._pending_keyed is None or self._keyed_done:
            return
        self._keyed_done = True
        self._keyed_effect = _keyed_effect(self._slot, self, self._pending_keyed)

    def store(self, key: str) -> "Signal":
        """Keep this value beyond the connection, under `key`.

        An anonymous device keeps it in this delivery's data (the session), and an authenticated user
        keeps it in the app's store under their user id — so it follows them to another tab or device.
        Declare it before `.bind(...)`: the stored value is what the slot's first write carries.
        """
        if self._stored:
            return self
        if self._slot is not None:
            raise RuntimeError(
                f"store({key!r}) must come before bind(slot): the stored value decides the first write"
            )
        ctx = _delivery.get()
        if ctx is None:
            raise RuntimeError(
                f"store({key!r}) needs a delivery: declare it inside a page's draw (or bind a slot first)"
            )
        user = getattr(ctx, "user", None)
        held = ctx.data.setdefault(STORED, {})
        at = f"{user}/{'/'.join((key,))}" if user is not None else f"-/{key}"
        held_cell = held.get(at)
        if held_cell is not None:
            return held_cell
        if user is not None:
            loaded = ctx.app.store.load(user, key)
            if loaded is not None:
                self._value = loaded  # type: ignore[assignment]
        self._stored = True
        held[at] = self
        inner = self._write

        def write(new: T) -> None:
            if inner is not None:
                inner(new)
            if user is not None:
                ctx.app.store.save(user, key, new)

        self._write = write
        return self

    @property
    def slot(self) -> Any:
        """The slot this value writes through — what a node's `source=` takes: `h.text(source=count)`."""
        if self._slot is None:
            raise RuntimeError("this signal has no slot: bind one first — Signal(v).bind(ctx.slot / …)")
        return self._slot

    def _need_slot(self, verb: str) -> Any:
        if self._slot is None:
            raise RuntimeError(f"{verb}(…) needs a slot: Signal(value).bind(slot).{verb}(…)")
        return self._slot

    def __repr__(self) -> str:
        return f"<Signal {self._value!r}>"


class Computed(Generic[T]):
    """A value computed from others: cached while clean, recomputed when stale, quiet when unchanged."""

    __slots__ = ("_fn", "_value", "_dirty", "_sources", "_observers", "_equal", "_version", "_slot")

    def __init__(self, fn: Callable[[], T], *, equal: Callable[[T, T], bool] = operator.eq) -> None:
        self._fn = fn
        self._value: Any = _UNSET
        self._dirty = True
        self._sources: list[Any] = []
        self._observers: set[Any] = set()
        self._equal = equal
        self._version = 0
        self._slot: Any = None

    def bind(self, slot: Any) -> "Computed[T]":
        """Keep `slot` equal to this answer: once now, and once per change. Identity = the slot's name."""
        cells = _cells(slot.ctx)
        held = cells.get(slot.name)
        if held is not None:
            if not isinstance(held, Computed):
                raise RuntimeError(
                    f"slot {slot.name!r} already has a {type(held).__name__}: one value per name"
                )
            return held
        cells[slot.name] = self
        self._slot = slot
        _defer(lambda: effect(lambda: slot.set(self.value)))
        return self

    def view(self, render: Callable[[Any], Any]) -> "Computed[T]":
        """Say how this answer becomes a node — the same `view` a plain value has."""
        if self._slot is None:
            raise RuntimeError("view(…) needs a slot: Computed(fn).bind(slot).view(…)")
        self._slot.view(render)
        return self

    @property
    def slot(self) -> Any:
        """The slot this answer is mirrored onto — what a node's `source=` takes."""
        if self._slot is None:
            raise RuntimeError("this computed has no slot: bind one first — Computed(fn).bind(slot)")
        return self._slot

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


# --- what a signal is attached to -------------------------------------------
#
# Four attachments, all optional and all read off the signal instead of off the slot:
#
#   `.bind(slot)`   write through to it — once at declaration, then on every change;
#   `.view(fn)`     how a value becomes a node (one per slot name, kept on the app);
#   `.keyed(fn)`    a list slot kept equal to this one, by id;
#   `.store(key)`   survive the connection (see `stores.py`).
#
# The cell table is one per connection (`ctx.data[CELLS]`) and one `STORED` table beside it — so drawing
# a page again hands back the same signal instead of seeding the slot a second time.
CELLS = "__cells__"
STORED = "__stored__"
_delivery: ContextVar[Any] = ContextVar("reflux_signals_delivery", default=None)
_pending: ContextVar[list[Callable[[], None]] | None] = ContextVar(
    "reflux_signals_pending", default=None
)


@contextmanager
def drawing(ctx: Any) -> Iterator[None]:
    """Say which delivery is being drawn, and hold the first writes until the draw is over.

    A page declares its values at the top and says what they look like on the same line, but the write a
    declaration makes is a frame, and `h.text(...)` needs the view — so the first write waits for the end
    of the draw, when every view this page declares has been declared.
    """
    token_delivery = _delivery.set(ctx)
    token_pending = _pending.set([])
    try:
        yield
    finally:
        queued = _pending.get() or []
        _pending.reset(token_pending)
        _delivery.reset(token_delivery)
        for run in queued:
            run()


def _defer(run: Callable[[], None]) -> None:
    """Run it now if nothing is being drawn, and at the end of the draw if something is."""
    queue = _pending.get()
    if queue is None:
        run()
    else:
        queue.append(run)


def _cells(ctx: Any) -> dict[str, Any]:
    """The per-connection cell table. A delivery is what a cell belongs to, so it lives in `ctx.data`."""
    data = getattr(ctx, "data", None)
    if not isinstance(data, dict):
        raise RuntimeError(f"a signal needs a delivery with `ctx.data`, got {type(ctx).__name__}")
    return data.setdefault(CELLS, {})


def keyed(rows: Any, slot: Any, render: Callable[[Any, str], Any]) -> Effect:
    """A list shared by every connection, kept equal on **this** connection's `slot`.

    `Signal.keyed` is the page's own list: one signal per connection, bound to that connection's slot.
    This is the other case — one signal at module level, one subscription per connection — and the
    subscription has to be made per connection because a slot is.
    """
    return _keyed_effect(slot, rows, render)


def _keyed_effect(slot: Any, rows: Any, render: Callable[[Any, str], Any]) -> Effect:
    """The effect behind `keyed`: one pass adds, removes and reorders; `shown` is its own ledger."""
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