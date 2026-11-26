"""Slots: the names a node carries — the one it reads (`source=`) and the one it speaks to (`sink=`).

Both are names on the wire (a slot is a place in the page, an event is a handler on the host — ADR 0023)
and both are handled the same way: as a handle from one table, never as a string at the point of use.
`source="status"` next to a `slot.set(...)` is the same name written twice, kept in step by eye; the
particular kind of address is the `Bind`'s business — slot, scope, default, path, type (ADR 0031) —
not the caller's. So there is one table (`ctx.slot`), one type (`Slot`), and both `source=` and
`sink=` refuse strings.

A `Slot` carries its verbs (`set`/`append`/`patch`/`remove`, each one frame) — the writing side of a
data plane. Using one as a `sink=` is the same name used as an address, which is all an uplink is.

    slots = ctx.slot                     # this delivery's table
    (slots / "status").set(b.text("就绪"))    # one frame
    b.text(source=slots / "status")           # a node reads a slot
    b.loom(b.button("发送", sink=slots / "chat" / "send"),
           sink=slots / "chat" / "send", submit="button")
                                          # and speaks to an event — one name, two directions

`ctx.slot("chat/status")` and `ctx.slot / "status"` are one slot. Paths go out as
written: hierarchical names are allowed and nothing parses the `/` yet. Declared slots land in
`App.slots`, which `/status` lists: where a page reads and where it speaks are one namespace.

**A slot that owns a value.** `slots / "counter" / "count"` names one; `.signal(0)` gives it a cell —
the same `signals.Signal` the adapters used to build, but reached from the handle the page holds:

    count = (slots / "counter" / "count").signal(0)   # from here on: count.value
    hint = (slots / "counter" / "hint").computed(fn)  # read-only, mirrored to the slot
    rows = (slots / "counter" / "history").keyed(row) # a list the slot is kept equal to, by id

One cell per name per connection (`ctx.data`), so drawing a page again does not seed it back. A slot
with no cell has no `.value` (`RuntimeError`) and is what it always was: an address with verbs.
`signal`/`computed`/`keyed`/`value` and the verbs are therefore members, not names: a slot called
`value` is still reached as `slots / "value"`, because `/` never asks the handle's attributes.
"""

from __future__ import annotations

from typing import Any

from . import wire
from .signals import Computed, Signal, _cells, keep, mirror, own


def is_node(value: Any) -> bool:
    """Is this already a node? A built accrete model, or the wire dict it dumps to."""
    if hasattr(value, "model_dump"):
        return True
    return isinstance(value, dict) and isinstance(value.get("type"), str)


__all__ = ["Slot", "Slots"]


class Slot:
    """One name, and the operations of the data plane it names.

    A slot belongs to a delivery (`ctx`), because saying something is a device's act: two devices
    reading the same slot hold two `Slot`s with the same name. A handle with no delivery is still a
    name — enough to read a slot (`source=`) or address an event (`sink=`), and a mistake to write
    through.
    """

    __slots__ = ("name", "_app", "_ctx")

    def __init__(self, name: str, ctx: Any = None, app: Any = None) -> None:
        if not isinstance(name, str) or not name:
            # `""` is the layout root's address, and the layout root is not a slot: it is the page,
            # whose writer is `ctx.page(...)`. Naming it here would be a second way to say that.
            raise ValueError(f"a slot needs a name, got {name!r}")
        self.name = name
        self._ctx = ctx
        self._app = app if app is not None else getattr(ctx, "app", None)

    # --- writing: each is one frame ---
    def set(self, value: Any) -> None:
        """Replace this slot's node — or its value, when the slot has a view (`Slot.view`)."""
        self._emit(wire.set(self.name, self.frame(value)))

    def append(self, value: Any, *, position: int = 0) -> None:
        """Add a row to this list slot — a node, or a value when the slot has a view."""
        self._emit(wire.append(self.name, self.frame(value), position=position))

    def frame(self, value: Any) -> Any:
        """The node this write means: a node passes through, anything else goes through the view.

        A view is declared once (`app.view("counter.count", lambda v: h.text(v))`), so a page writes
        values and the id/variant live in one place — and a page that wants a node of its own shape
        still writes one: `slot.set(h.text(...))` is not converted, because it already is the node.
        That is the rule, and it is read off the value, not off the slot: a slot without a view takes
        nodes exactly as before.
        """
        if is_node(value):
            return value
        view = self._app.view_for(self.name) if self._app is not None else None
        return view(value) if view is not None else value

    def view(self, render: Any) -> "Slot":
        """Declare how this slot's values become nodes: `Slot("x").view(lambda v: h.text(v))`."""
        if self._app is None:
            raise RuntimeError(
                f"slot {self.name!r} has no app to record a view on: declare it where the app exists "
                f"(`app.view(name, render)` in the page's `register`)"
            )
        self._app.view(self.name, render)
        return self

    # --- the cell: a value this slot owns ---
    @property
    def value(self) -> Any:
        """The cell's value. A slot with no cell is an address, not a value — that read raises."""
        return self._cell().value

    @value.setter
    def value(self, new: Any) -> None:
        cell = self._cell()
        if isinstance(cell, Computed):
            raise RuntimeError(
                f"slot {self.name!r} is computed — write what it is computed from, not the answer"
            )
        cell.value = new

    def signal(self, value: Any, **kwargs: Any) -> "Slot":
        """Give this slot a cell: `(slots / "counter").signal(0)`, then `handle.value` reads and writes.

        The cell is made once per connection — drawing the page again hands back the same one, so the
        first value is not written twice. Its first value is a write like any other, so a value needs
        the slot's view already: `.view(fn).signal(0)`.
        """
        self._seeded(value)
        own(self._ctx, self, value, **kwargs)
        return self

    def _seeded(self, value: Any) -> None:
        """Say it plainly when a value slot has no view yet — the first value is a write like any other."""
        if is_node(value):
            return
        if self._app is not None and self._app.view_for(self.name) is not None:
            return
        raise ValueError(
            f"slot {self.name!r} holds nodes and has no view: declare one first — `.view(fn).signal(...)`"
        )

    def computed(self, fn: Any) -> "Slot":
        """Declare this slot's cell as computed: mirrored onto the slot, read-only from here."""
        mirror(self._ctx, self, Computed(fn))
        return self

    def keyed(self, render: Any, initial: Any = ()) -> "Slot":
        """Declare this slot a list kept equal to `handle.value` by id: `render(item, row_id)` builds a row."""
        keep(self._ctx, self, Signal(list(initial)), render)
        return self

    def _cell(self) -> Any:
        """The cell this name holds on this connection, or a sentence saying how to declare one."""
        cell = _cells(self._ctx).get(self.name)
        if cell is None:
            raise RuntimeError(
                f"slot {self.name!r} has no signal — declare one with `.signal(default)`"
            )
        return cell

    def patch(self, path: str, value: Any, *, op: str = "replace") -> None:
        """Write one value inside the node that is already here."""
        self._emit(wire.patch(self.name, path, value, op=op))

    def move(self, id: str, position: int) -> None:
        """Move the row carrying `id` to `position` — the row's node is reused, so its focus stays.

        `position` counts like `append`'s (`0` = the end, `+n` from the tail, `-n` from the head),
        but on the list with the row lifted out (fluxen ADR 0005).
        """
        self._emit(wire.move(self.name, id, position))

    def remove(self, id: str) -> None:
        """Drop the row carrying `id`."""
        self._emit(wire.remove(self.name, id))

    def declare(self) -> "Slot":
        """Record this name on the app — what makes `/status` a list of names in use, not of guesses.

        Called where the name is actually used: a write (`set`/`append`/`move`/`patch`/`remove`) or an
        entry in a node (`source=`, `sink=`). Taking a handle is not a use, so `ctx.slot / "go"` inside
        `ctx.slot / "go" / "dashboard"` records `go.dashboard` and not the `go` on the way.
        """
        if self._app is not None:
            self._app.declare(self.name)
        return self

    def _emit(self, operation: dict) -> None:
        self.declare()
        if self._ctx is None:
            raise RuntimeError(
                f"slot {self.name!r} has no delivery: a handle built without one can name an address "
                f"(source=, sink=) but not write through it"
            )
        self._ctx.emit(operation)

    # --- names are built, not looked up ---
    def __getattr__(self, name: str) -> "Slot":
        """A dot on a slot is a mistake — say which spelling was meant, and hand back nothing.

        `set`/`append`/`patch`/`remove`/`move`/`declare`, the cell (`value`/`signal`/`computed`/
        `keyed`/`view`) and `name`/`frame` are the handle's own. Every other name is *built* with
        `/`, and `/` never consults the attributes — so a slot called `value` is `slot / "value"`.
        """
        raise AttributeError(
            f"slot {self.name!r} has no member {name!r}: names are built with `/` — "
            f"slot / {name!r}"
        )

    def _child(self, name: str) -> "Slot":
        return Slot(f"{self.name}.{name}", self._ctx, self._app)

    def __truediv__(self, name: str) -> "Slot":
        """`slots / "chat" / "send"` — a name joined the way a path is (`Path / "a"`), not a member.

        The `/` is how a name is *built*; a dot stays the verbs and the handle's own attributes. So
        `slot.set` is the verb and `slots / "row" / "remove"` is a slot that happens to be called
        `remove` — the same escape `slots.row["remove"]` gives, spelled as construction.
        """
        if not isinstance(name, str) or not name:
            raise ValueError(f"a slot name segment must be a non-empty string, got {name!r}")
        return self._child(name)

    # --- identity ---
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Slot) and other.name == self.name

    def __hash__(self) -> int:
        return hash(("slot", self.name))

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"Slot({self.name!r})"


class Slots:
    """One table, seen from two places: `app.slot` (the names a declaration comes from) and `ctx.slot`
    (the same names, bound to a delivery so the verbs can send).

    Every form — `ctx.slot("chat/status")` and `ctx.slot / "status"` — resolves to the
    same handle type, and a name is registered on the app when it is used. There is no attribute form
    and no subscript: a dot on the table is a mistake, not a name.
    """

    def __init__(self, app: Any = None, ctx: Any = None) -> None:
        self._app = app
        self._ctx = ctx

    def __call__(self, path: str) -> Slot:
        """Declare a name: `ctx.slot("chat/status")` — or the sink a loom exits through."""
        return self._make(path)

    def __truediv__(self, name: str) -> Slot:
        """`ctx.slot / "counter" / "count"` — the table, joined segment by segment."""
        if not isinstance(name, str) or not name:
            raise ValueError(f"a slot name segment must be a non-empty string, got {name!r}")
        return self._make(name)

    def __getattr__(self, name: str) -> Slot:
        """A dot on the table is not a name — say which spelling was meant, and hand back nothing."""
        raise AttributeError(
            f"the slot table has no member {name!r}: a name is built with `/` "
            f"(ctx.slot / {name!r})"
        )

    def _make(self, name: str) -> Slot:
        # Taking a handle is not using it: `app.slot / "go" / "chat"` declares `go.chat` when the
        # decorator answers it, and not the `go` on the way.
        return Slot(name, self._ctx, self._app)
