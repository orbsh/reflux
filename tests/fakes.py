"""Small stand-ins the unit tests share — the wire, without a browser or a socket."""

from __future__ import annotations

from reflux import wire


class FakeSession:
    """The part of a Session a handler sees, and a record of what it was told to send."""

    def __init__(self, id: str = "test0001", path: str = "/") -> None:
        self.id = id
        self.path = path
        self.frames: list[dict] = []
        self.seen: list[dict] = []

    def send(self, frame: dict) -> None:
        self.frames.append(frame)

    def draw(self, *operations: dict) -> None:
        self.send(wire.draw(*operations))