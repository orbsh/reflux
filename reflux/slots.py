"""Slots: the named data planes a page reads and the handlers write.

A slot is a name on the wire — `set`, `patch`, `append` and `remove` each address exactly one — and
nothing else. An app used to keep that name twice, as a constant where it wrote and the same name in
a string where it read; the constant was the seam between two halves that had to agree. Here the name
lives once, on the `Slot`, and the verbs hang off it:

    slots: ChatSlots = ctx.slot          # type: ignore[assignment]  — the Protocol completes
    slots.status.set(b.text("就绪"))      # one frame: set `status`
    slots.messages.append(row)            # one frame: append to `messages`
    b.text(source=slots.status)           # a node reads the slot; builders take a Slot

`ctx.slot("chat/status")` declares (or looks up) a slot by path; `ctx.slot["status"]` and
`ctx.slot.status` are the same slot by name. Paths may be hierarchical — the `/` is carried through
and nothing here reads it yet, which is the whole of "we may want namespaces later".

Static completion is the Protocol's job, not ours: the group answers any name at runtime, and the app
declares a Protocol with the names it expects, so the editor knows them and a typo is an `AttributeError`
at the first call instead of a silent empty slot.
"""

from __future__ import annotations

from typing import Any

from . import wire

__all__ = ["Slot", "Slots"]


class Slot:
    """One data plane, and the only place its operations are written.

    A slot belongs to a delivery (`ctx`), because saying something is a device's act: two devices
    reading the same slot hold two `Slot`s with the same name.
    """

    __slots__ = ("name", "_ctx")

    def __init__(self, ctx: Any, name: str) -> None:
        if not isinstance(name, str) or not name:
            # `""` is the layout root's address, and the layout root is not a slot: it is the page,
            # whose writer is `ctx.page(...)`. Naming it here would be a second way to say that.
            raise ValueError(f"a slot needs a name, got {name!r}")
        self._ctx = ctx
        self.name = name

    # --- writing: each is one frame ---
    def set(self, node: Any) -> None:
        """Replace the node in this slot."""
        self._ctx.emit(wire.set(self.name, node))

    def append(self, node: Any, *, position: int = 0) -> None:
        """Add a row to this list slot."""
        self._ctx.emit(wire.append(self.name, node, position=position))

    def patch(self, path: str, value: Any, *, op: str = "replace") -> None:
        """Write one value inside the node that is already here."""
        self._ctx.emit(wire.patch(self.name, path, value, op=op))

    def remove(self, id: str) -> None:
        """Drop the row carrying `id`."""
        self._ctx.emit(wire.remove(self.name, id))

    # --- identity ---
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Slot) and other.name == self.name

    def __hash__(self) -> int:
        return hash(("slot", self.name))

    def __repr__(self) -> str:
        return f"<Slot {self.name!r}>"


class Slots:
    """The slot table of one delivery: `ctx.slot("a/b")`, `ctx.slot["a"]`, `ctx.slot.a`.

    Every form declares the name on the app the first time it is seen — a declaration costs one dict
    entry and buys the `/status` listing and a single place to see what a page writes.
    """

    def __init__(self, ctx: Any) -> None:
        self._ctx = ctx

    def __call__(self, path: str) -> Slot:
        """Declare a slot by path: `ctx.slot("chat/status")`.

        There is no "no name" case: a slot without a name is the layout root, and the layout root is
        not a data plane — it is the page, drawn with `ctx.page(...)`. `ctx.slot("")` says so by
        refusing.
        """
        return self._declare(path)

    def __getitem__(self, name: str) -> Slot:
        """A slot by name: `ctx.slot["status"]`."""
        return self._declare(name)

    def __getattr__(self, name: str) -> Slot:
        """The same slot, in the form a Protocol's completion reads: `ctx.slot.status`."""
        if name.startswith("__"):
            raise AttributeError(name)
        return self._declare(name)

    def _declare(self, name: str) -> Slot:
        slot = Slot(self._ctx, name)
        app = getattr(self._ctx, "app", None)
        if app is not None:
            app.slot(slot.name)  # record it; the app is where the names are visible
        return slot

    def __repr__(self) -> str:
        return "<Slots>"