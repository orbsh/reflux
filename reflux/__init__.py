"""Reflux — a producer for fluxen's renderer: write frontend UI in any language.

This package is the Python SDK (the vocabulary, the frame layer, the boundary) and the
producer-side server that serves the page tree. Other languages get their own SDK generated from
the same schema (`schema/accrete.schema.json`), because the vocabulary is the renderer's, not ours.

Layering, so imports never cycle:
  protocol            the protocol's own numbers — the operation cap, the reserved prefix
  sdk.types|builders  the vocabulary: accrete's types as models, and one builder per type (generated)
  sdk._parse          the boundary: `parse` / `dump`, and the assembly of a `bind` entry
  sdk.closed          the closure walk — the one vocabulary list the boundary reads
  wire                accrete's eight actions, and the `draw` frame that carries them
  channel / dests / app / server  the producer: the page tree, the /ws channel, the registry
  routes / cli        the route table (a path declared where its handler is) and the printing of it

    from reflux import route, wire
    from reflux.sdk import builders as b

    page = b.case(b.text("hello", source="greeting"), b.input(dest="name.change"))

    @route("/blog/{slug}", title="文章")
    def post(session, match):
        return b.case(b.text(match.params["slug"]))

    session.draw(wire.set("greeting", b.text("你好")))
"""

from . import sdk, wire
from .app import App, Session
from .dests import Registry, RegistryError
from .protocol import MAX_OPS_PER_FRAME, RESERVED_PREFIX
from .routes import DEFAULT, Match, Route, Routes, RoutesError, discover, route
from .sdk import builders
from .sdk._parse import dump, parse
from .sdk.builders import *  # noqa: F401,F403  (one constructor per type, generated)

__version__ = "0.0.0"

__all__ = [
    "App",
    "Session",
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
    *builders.__all__,
]