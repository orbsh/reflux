"""Slots: the names a node carries — the one it reads (`source=`) and the one it speaks to (`dest=`).

Both are names on the wire (a slot is a place in the page, a dest is a handler on the host — ADR 0023)
and both are handled the same way: as a handle from one table, never as a string at the point of use.
`source="status"` next to a `slot.set(...)` is the same name written twice, kept in step by eye; the
particular kind of address is the bind entry's business, not the caller's. So there is one table
(`ctx.slot`), one type (`Slot`), and both `source=` and `dest=` refuse strings.

A `Slot` carries its verbs (`set`/`append`/`patch`/`remove`, each one frame) — the writing side of a
data plane. Using one as a `dest=` is the same name used as an address, which is all a dest is.

    class Chat(Protocol):
        send: Slot
        stop: Slot

    class ChatSlots(Protocol):           # annotations only — this is what the editor completes
        status: Slot
        messages: Slot
        chat: Chat                       # `slots.chat.send` is the dest "chat.send"

    slots: ChatSlots = ctx.slot          # type: ignore[assignment]
    slots.status.set(b.text("就绪"))      # one frame
    b.text(source=slots.status)          # a node reads a slot
    b.form(b.button("发送"), dest=slots.chat.send)        # and speaks to a dest — same view, nested

`ctx.slot("chat/status")`, `ctx.slot["status"]` and `ctx.slot.status` are one slot. Paths go out as
written: hierarchical names are allowed and nothing parses the `/` yet. Declared slots land in
`App.slots`, which `/status` lists: where a page reads and where it speaks are one namespace.
"""

from __future__ import annotations

from typing import Any

from . import wire

__all__ = ["Slot", "Slots"]


class Slot:
    """One name, and the operations of the data plane it names.

    A slot belongs to a delivery (`ctx`), because saying something is a device's act: two devices
    reading the same slot hold two `Slot`s with the same name. A handle with no delivery is still a
    name — enough to read a slot (`source=`) or address a dest (`dest=`), and a mistake to write
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
    def set(self, node: Any) -> None:
        """Replace the node in this slot."""
        self._emit(wire.set(self.name, node))

    def append(self, node: Any, *, position: int = 0) -> None:
        """Add a row to this list slot."""
        self._emit(wire.append(self.name, node, position=position))

    def patch(self, path: str, value: Any, *, op: str = "replace") -> None:
        """Write one value inside the node that is already here."""
        self._emit(wire.patch(self.name, path, value, op=op))

    def remove(self, id: str) -> None:
        """Drop the row carrying `id`."""
        self._emit(wire.remove(self.name, id))

    def declare(self) -> "Slot":
        """Record this name on the app — what makes `/status` a list of names in use, not of guesses.

        Called where the name is actually used: a write (`set`/`append`/`patch`/`remove`) or an
        entry in a node (`source=`, `dest=`). Taking a handle is not a use, so `ctx.slot.go` inside
        `ctx.slot.go.dashboard` records `go.dashboard` and not the `go` on the way.
        """
        if self._app is not None:
            self._app.declare(self.name)
        return self

    def _emit(self, operation: dict) -> None:
        self.declare()
        if self._ctx is None:
            raise RuntimeError(
                f"slot {self.name!r} has no delivery: a handle built without one can name an address "
                f"(source=, dest=) but not write through it"
            )
        self._ctx.emit(operation)

    # --- nesting: `slots.chat.send` is the name "chat.send" ---
    def __getattr__(self, name: str) -> "Slot":
        """A name below this one: `slots.chat.send` is the slot `chat.send`.

        Nesting is how a hierarchy is *read*; the wire still sees one dotted name. Verbs win over
        children (`set`, `append`, `patch`, `remove` are always verbs), and a child carries this
        slot's delivery, so `slots.chat.status.set(...)` writes a frame like any other.
        """
        if name.startswith("__"):
            raise AttributeError(name)
        return self._child(name)

    def __getitem__(self, name: str) -> "Slot":
        """`slots.chat["send"]` — the same child as `slots.chat.send`, and the way past the verbs.

        `set`/`append`/`patch`/`remove` are always verbs, so a name that ends in one of them is
        reached with the subscript: `slots.row["remove"]` is the dest `row.remove`, while
        `slots.row.remove` is the verb that drops a row.
        """
        return self._child(name)

    def _child(self, name: str) -> "Slot":
        return Slot(f"{self.name}.{name}", self._ctx, self._app)

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

    Every form — `ctx.slot("chat/status")`, `ctx.slot["status"]`, `ctx.slot.status` — resolves to the
    same handle type, and a name is recorded on the app when it is used.
    """

    def __init__(self, app: Any = None, ctx: Any = None) -> None:
        self._app = app
        self._ctx = ctx

    def __call__(self, path: str) -> Slot:
        """Declare a name: `ctx.slot("chat/status")` — or the dest a form speaks to."""
        return self._make(path)

    def __getitem__(self, name: str) -> Slot:
        """A slot by name: `ctx.slot["status"]`."""
        return self._make(name)

    def __getattr__(self, name: str) -> Slot:
        """The same slot, in the form a Protocol's completion reads: `ctx.slot.status`."""
        if name.startswith("__"):
            raise AttributeError(name)
        return self._make(name)

    def _make(self, name: str) -> Slot:
        # Taking a handle is not using it: `app.slot.go.chat` declares `go.chat` when the decorator
        # answers it, and not the `go` on the way.
        return Slot(name, self._ctx, self._app)
