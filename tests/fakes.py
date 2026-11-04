"""Small stand-ins the unit tests share — the wire, without a browser or a socket."""

from __future__ import annotations

from typing import Any

from reflux import wire


class FakeDevice:
    """The part of a Device a handler sees, and a record of what it was told to send.

    The three flags are the framework's, not a handler's: `connected` (the first hello already
    raised `connect`), `shell_drawn` (the shell is on this client) and `query` (what the address bar
    carried). They live here so a test can drive the same code a socket would.
    """

    def __init__(self, id: str = "test0001", path: str = "/", app: Any = None) -> None:
        self.id = id
        self.path = path
        self.app = app  # set it to drive `draw()`: the page is the app's, the act is the device's
        self.query: dict[str, list[str]] = {}
        self.data: dict = {}  # what the business hangs on the connection; the framework never reads it
        self.connected = False
        self.shell_drawn = False
        self.stale = False
        self.emits = 0
        self.frames: list[dict] = []
        self.seen: list[dict] = []

    def draw(self) -> None:
        """Draw the page this device stands on — the real `Device.draw`, through the app."""
        if self.app is None:
            raise RuntimeError("FakeDevice.draw: pass `app=` when the test needs a page drawn")
        self.app._draw(self)

    def send(self, frame: dict) -> None:
        self.frames.append(frame)

    def emit(self, *operations: dict) -> None:
        self.send(wire.draw(*operations))