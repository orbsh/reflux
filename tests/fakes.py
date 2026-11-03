"""Small stand-ins the unit tests share — the wire, without a browser or a socket."""

from __future__ import annotations

from reflux import wire


class FakeSession:
    """The part of a Session a handler sees, and a record of what it was told to send.

    The three flags are the framework's, not a handler's: `connected` (the first hello already
    raised `connect`), `shell_drawn` (the shell is on this client) and `query` (what the address bar
    carried). They live here so a test can drive the same code a socket would.
    """

    def __init__(self, id: str = "test0001", path: str = "/") -> None:
        self.id = id
        self.path = path
        self.query: dict[str, list[str]] = {}
        self.connected = False
        self.shell_drawn = False
        self.stale = False
        self.frames: list[dict] = []
        self.seen: list[dict] = []

    def send(self, frame: dict) -> None:
        self.frames.append(frame)

    def draw(self, *operations: dict) -> None:
        self.send(wire.draw(*operations))