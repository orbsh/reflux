"""Reflux — a spec plus a static shell: write frontend UI in any language.

This package is the Python SDK (and the producer-side server that serves the shell).
Other languages get their own SDK generated from `spec/components.json`.

Layering, so imports never cycle:
  tables_generated   pure data — the vocabulary (generated)
  node               the wire shape + the validating boundary (`make`)
  components_generated  the builders (generated)
  ui / ops           the writing layer: components addressed as one object, and frame builders
  channel / events / app / server   the producer: the shell, the /ws channel, the registry
  routes / cli       the route table (a path declared where its handler is) and the printing of it

    from reflux import ops, route, ui

    page = ui.stack(ui.text("hello", source="greeting"), ui.button("+", event="counter.inc"))
    session.draw(ops.patch("/slots/greeting", "你好"))

    @route("/blog/{slug}", title="文章")
    def post(session, match): ...
"""

from . import ops, ui
from .app import App, Session
from .components_generated import *  # noqa: F403  (the builders, generated from the spec)
from .events import Registry, RegistryError
from .node import Node, make
from .routes import DEFAULT, Match, Route, Routes, RoutesError, discover, route
from .tables_generated import (
    BIND_KEYS,
    COMPONENTS,
    FIRE_EVENTS,
    OPS,
    RESERVED_PREFIX,
    SPEC_VERSION,
)

__version__ = "0.0.0"

__all__ = [
    "Node",
    "make",
    "App",
    "Session",
    "Registry",
    "RegistryError",
    "ops",
    "ui",
    "route",
    "Routes",
    "Route",
    "Match",
    "RoutesError",
    "discover",
    "DEFAULT",
    "COMPONENTS",
    "OPS",
    "BIND_KEYS",
    "FIRE_EVENTS",
    "RESERVED_PREFIX",
    "SPEC_VERSION",
]