"""Small stand-ins the unit tests share — the wire, without a browser or a socket."""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any, Callable

from reflux import wire


def run_sync(coro: Any) -> Any:
    """A coroutine on a fresh loop — how a synchronous test drives the async app (ADR 0002)."""
    return asyncio.run(coro)


def background_loop() -> asyncio.AbstractEventLoop:
    """A loop in a daemon thread: what an app needs when a test wants its tasks to tick."""
    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_forever, name="test-loop", daemon=True).start()
    return loop


async def until(predicate: Callable[[], bool], timeout: float = 2.0) -> bool:
    """Poll a predicate without blocking the loop — the async twin of a wait loop in a test."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.005)
    return predicate()


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
        self.landings: dict = {}  # this page's closure landing points, named at draw time

    def draw(self) -> None:
        """Draw the page this device stands on — the real `Device.draw`, through the app."""
        if self.app is None:
            raise RuntimeError("FakeDevice.draw: pass `app=` when the test needs a page drawn")
        self.app._draw(self)

    def go(self, url: str) -> None:
        """The real move, through the app's own splitter: the address changes, then the page is drawn."""
        from reflux.app import split_location

        self.path, self.query = split_location(url)
        self.draw()

    def send(self, frame: dict) -> None:
        self.frames.append(frame)

    def emit(self, *operations: dict) -> None:
        self.send(wire.draw(*operations))


def page_nodes(app: Any, path: str = "/") -> list[dict]:
    """The nodes of the page an app sends for `path` — the `create`'s payload, markers and all.

    A page is a send (`ctx.page(...)`), not a value a route hands back, so a fixture that wants the
    tree takes the one the app actually draws: one fake device, one draw, the frame it got.
    """
    device = FakeDevice(path=path, app=app)
    app._draw(device)
    for sent in device.frames:
        for operation in sent:
            # The page arrives as `set routes <page-root>`: the markers are that root's first two
            # children (`ctx.page` puts them there), so one node carries the whole page.
            if operation.get("action") == "set" and operation.get("slot") == "routes":
                return [operation["data"]]
    raise AssertionError(f"no page was drawn for {path!r}")
