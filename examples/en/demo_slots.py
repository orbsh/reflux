"""The reference app's slot names: one type alias, two accessors, and the nav's six addresses.

Names only: the `@app.on` landing points — identity in the page, a name that outlives a page, or one
slot with several sources. A page's own request-response does not belong here: that is a closure,
`sink=add_row`, written beside the button that sends to it, named by the framework when the page is
drawn.

A slot name is a string on the wire (`reflux/slots.py`), and a name is built with `/`:
`ctx.slot / "echo"`. A dot on a handle is a verb or a cell (`set`, `append`, `value`, …), never a name —
`Slot.__getattr__` refuses anything else. So this namespace has no second list: `ctx.slot / "echo"` and
`app.slot / "echo"` are one slot, and a typo shows up at runtime. The module keeps two things:

    slots_of(ctx)        the page's table, with the delivery — writes go through it (`set`, `append`)
    table(app)           the app's table, no delivery — addresses go through it (`sink=`, `source=`,
                         `@app.on(...)`)

Both return the framework's `Slots`; `DemoSlots` is this app's alias for it, so a signature still reads
"this app's slots".

This is the English tree; `examples/zh/demo_slots.py` is the same file in Chinese.
"""

from __future__ import annotations

from typing import Any

from reflux.application import Context
from reflux.slots import Slot, Slots

__all__ = ["DemoSlots", "GO", "GO_ABOUT", "GO_CHAT", "GO_COUNTER", "GO_DEMO", "GO_SETTINGS", "GO_HOME", "slots_of", "table"]

DemoSlots = Slots


def slots_of(ctx: Context) -> DemoSlots:
    """The reference app's slots for this delivery — the names the page writes through."""
    return ctx.slot


def table(app: Any) -> DemoSlots:
    """The app's own table — the names it addresses: `@app.on(app.slot / "row" / "remove")`.

    `Any` for the app is the price of not importing the framework's `App` here: this module is the
    names, and an import of `App` would tie the names to one application's shape for nothing.
    """
    return app.slot


# Where a navigation form sends the client. The frame's `dest` is the target's name.
GO_HOME, GO_ABOUT, GO_DEMO, GO_CHAT, GO_COUNTER, GO_SETTINGS = (
    Slot("go.home"), Slot("go.about"), Slot("go.demo"), Slot("go.chat"), Slot("go.counter"),
    Slot("go.settings"),
)
GO = {
    GO_HOME.name: "/",
    GO_ABOUT.name: "/about",
    GO_DEMO.name: "/demo",
    GO_CHAT.name: "/chat",
    GO_COUNTER.name: "/counter",
    GO_SETTINGS.name: "/settings",
}