"""The reference app's slot names: one Protocol, one accessor, and the nav's addresses.

A slot name is a string on the wire (`reflux/slots.py`), and the framework's table hands out a `Slot`
for anything it is asked — `Slots.__getattr__ -> Slot`, no vocabulary. So the checking a page needs
comes from a Protocol that names them, which is what this module is: every name the app speaks, in one
place, and the two ways a page reaches them.

    slots_of(ctx)        the page's table, with the delivery — writes go through it (`set`, `append`)
    table(app)           the app's table, no delivery — addresses go through it (`sink=`, `source=`,
                         `@app.on(...)`)

The second one is why `@app.on` gets completion: `App.slot` is typed `Slots`, whose `__getattr__`
accepts any name, so a typo there would register a handler nothing ever sends to, silently. Taking the
table once, annotated, moves that check to the line where the name is written.

This is the English tree; `examples/zh/demo_slots.py` is the same file in Chinese.
"""

from __future__ import annotations

from typing import Any, Protocol

from reflux.app import Context
from reflux.slots import Slot

__all__ = ["DemoSlots", "GO", "GO_ABOUT", "GO_CHAT", "GO_DEMO", "GO_HOME", "slots_of", "table"]


class _Change(Protocol):
    """The `name` family: an input's uplink is `name.change`."""

    change: Slot


class _Row(Protocol):
    """The `row` family. `remove` is a verb on `Slot`, so that name goes by subscript."""

    add: Slot

    def __getitem__(self, name: str) -> Slot: ...


class _Vault(Protocol):
    vault: Slot
    secret: Slot


class _Chat(Protocol):
    """The chat page's two uplinks: the composer's send, and the stop that ends a reply."""

    send: Slot
    stop: Slot


class _Go(Protocol):
    """The nav's four targets — the frame's `dest` is the name."""

    home: Slot
    about: Slot
    demo: Slot
    chat: Slot


class DemoSlots(Protocol):
    """The reference app's slots, for the editor — the runtime only ever sees the names.

    Two halves: the ones the page *writes* (`echo`, `rows`, … — reached through `slots_of(ctx)`, which
    carries the delivery) and the ones the page *addresses* (`name.change`, `row.add`, `go.home`, … —
    reached through `table(app)`, which carries none). One protocol, because they are one namespace:
    the sink of an uplink and the handler that answers it are the same name.
    """

    echo: Slot  # what the input last carried
    rows: Slot  # the list the tiles node reads
    archived: Slot  # what the last drop archived — a text slot, written by the dock's handler
    secret: Slot  # only a signed-in click writes it; every anonymous draw clears it
    routes: Slot  # the shell's reader — where the page is written
    messages: Slot  # the chat page's transcript — a list slot, appended to per bubble
    status: Slot  # the chat page's status line

    name: _Change
    row: _Row
    vault: _Vault
    go: _Go
    chat: _Chat

    def __call__(self, path: str) -> Slot: ...  # `reflux:login`, `reflux:logout`, `reflux:auth`

    # (the login form's answer is the framework's: it lands in the reserved `auth` region)


def slots_of(ctx: Context) -> DemoSlots:
    """The reference app's slots for this delivery — the names the page writes through."""
    return ctx.slot  # type: ignore[return-value]


def table(app: Any) -> DemoSlots:
    """The app's own table, typed — the names it addresses: `@app.on(slots.name.change)`.

    `Any` for the app is the price of not importing the framework's `App` here: this module is the
    names, and an import of `App` would tie the names to one application's shape for nothing.
    """
    return app.slot  # type: ignore[return-value]


# Where a navigation form sends the client. The frame's `dest` is the target's name.
GO_HOME, GO_ABOUT, GO_DEMO, GO_CHAT = (
    Slot("go.home"), Slot("go.about"), Slot("go.demo"), Slot("go.chat"),
)
GO = {GO_HOME.name: "/", GO_ABOUT.name: "/about", GO_DEMO.name: "/demo", GO_CHAT.name: "/chat"}