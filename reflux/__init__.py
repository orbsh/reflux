"""Reflux — a producer for fluxen's renderer: write frontend UI in any language.

This package is the Python SDK (the vocabulary, the frame layer, the boundary) and the
producer-side server that serves the page tree. Other languages get their own SDK generated from
the same schema (`schema/accrete.schema.json`), because the vocabulary is the renderer's, not ours.

Layering, so imports never cycle:
  protocol            the protocol's own constants — the operation cap, the reserved prefix, the
                      routes slot, and the names of the events the host raises
  sdk.types|builders  the vocabulary: accrete's types as models, and one builder per type (generated)
  sdk._parse          the boundary: `parse` / `dump`, and the assembly of a `bind` entry
  sdk.closed          the closure walk — the one vocabulary list the boundary reads
  wire                accrete's eight actions, and the `draw` frame that carries them
  channel / dests / app / server  the producer: the page tree, the channel route, the registry
  routes / cli        the route table (a path declared where its handler is) and the printing of it

The words that matter here: a **device** is one connection (not a user — one user may hold several),
`device.emit(...)` sends accrete's operations as one frame, `device.data` is the bag the business
hangs its own facts on (an identity, a name), and the **channel is a route** in `app.mounts` next to
whatever else the app mounts.

    from reflux import Request, Response, route, wire
    from reflux.sdk import builders as b

    @route("/blog/{slug}", title="文章")
    def post(device, match):
        return b.case(b.text(match.params["slug"]))

    app.mount("/health", lambda request: "ok")
    device.data["user"] = {"name": "Ada"}          # the business's, never the framework's
    device.emit(wire.set("greeting", b.text("你好")))
"""

from . import sdk, wire
from .app import App, Device
from .dests import Registry, RegistryError
from .protocol import HOST_EVENTS, MAX_OPS_PER_FRAME, RESERVED_PREFIX, ROUTES_SLOT
from .routes import DEFAULT, Match, Route, Routes, RoutesError, discover, route
from .sdk import builders
from .sdk._parse import dump, parse
from .sdk.builders import *  # noqa: F401,F403  (one constructor per type, generated)
from .server import CHANNEL, Request, Response

__version__ = "0.0.0"

__all__ = [
    "App",
    "Device",
    "CHANNEL",
    "Request",
    "Response",
    "Registry",
    "RegistryError",
    "route",
    "Routes",
    "Route",
    "Match",
    "RoutesError",
    "discover",
    "DEFAULT",
    "wire",
    "sdk",
    "parse",
    "dump",
    "MAX_OPS_PER_FRAME",
    "RESERVED_PREFIX",
    "ROUTES_SLOT",
    "HOST_EVENTS",
    *builders.__all__,
]