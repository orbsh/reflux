"""Reflux — a spec plus a static shell: write frontend UI in any language.

This package is the Python SDK (and the producer-side server that serves the shell).
Other languages get their own SDK generated from `spec/components.json`.

Layering, so imports never cycle:
  tables_generated   pure data — the vocabulary (generated)
  node               the wire shape + the validating boundary (`make`)
  components_generated  the builders (generated)
  server / demo      serve the shell; the ops channel lands in T2

    from reflux import stack, text, button
    stack(text("hello", source="greeting"), button("+", event="counter.inc"))
"""

from .components_generated import *  # noqa: F403  (the builders, generated from the spec)
from .node import Node, make
from .tables_generated import BIND_KEYS, COMPONENTS, OPS, RESERVED_PREFIX, SPEC_VERSION

__version__ = "0.0.0"

__all__ = [
    "Node",
    "make",
    "COMPONENTS",
    "OPS",
    "BIND_KEYS",
    "RESERVED_PREFIX",
    "SPEC_VERSION",
]