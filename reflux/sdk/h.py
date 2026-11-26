"""The page vocabulary under the name front-end code gives it: `h`.

    from reflux.sdk import h

    h.frame(h.text("hi", variant="muted"), grid={"gap": "8px"}, id="root")

Two entry points, and the difference between them is where the page comes from:

- `h.<type>(...)` — a page a person writes. Every node type keeps its generated signature, so keywords
  complete, a typo in a keyword is a `TypeError` at the line that made it, and the type checker sees
  the whole call. This is the one to write by hand.
- `h.node(tree)` — a page that *is* data: `('frame', props, children)`. Unknown keys are still refused
  (the builder gets them), but nothing completes, because a structure has no signature to complete
  from. Read `reflux/sdk/node.py` for the shape.

The `h` name is the convention this borrows from (`hyperscript`): one letter for "make a node". What it
does not borrow is the JavaScript reason for `h('div', …)`: there is no JSX here compiling into it, so
writing pages through strings would buy a string and cost a signature — hence `h.<type>` for code and
`h.node` for data, and no third spelling.
"""

from __future__ import annotations

from .builders import (
    loom,
    button,
    canvas,
    entry,
    forcegraph,
    color,
    frame,
    image,
    input,
    panel,
    path,
    select,
    svg,
    text,
    tiles,
)
from .node import node

__all__ = [
    "loom",
    "button",
    "canvas",
    "color",
    "entry",
    "forcegraph",
    "frame",
    "image",
    "input",
    "node",
    "panel",
    "path",
    "select",
    "svg",
    "text",
    "tiles",
]