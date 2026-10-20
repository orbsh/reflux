"""The page markers: the two reserved ids the client runtime reads out of the DOM.

`www/static/reflux.js` mirrors `reflux:path` into the address bar and `reflux:title` into the
document's title. Both are ordinary nodes — a `placeholder` whose id is the reserved name, holding
the value as its only child — so producing them is a **convention**, not a wire type: accrete does
not know the words `path` or `title`, and the vocabulary must not learn them.

Written by hand in every SDK, next to `wire`, for the same reason the frame's shape is hand-written:
what the specification owns is the vocabulary of nodes, not this framework's contract with its own
runtime. The prefix comes from `reflux/protocol.py` (the framework owns it); the ids below are the
whole of the contract — the runtime and the producer meet on nothing else.

This had three hand-written copies before it had a name — the reference app, `gate_t6`, and the Rust
frame dump — and all three agreed on the same shape and the same two arguments, which is what named
it `page(path, title, *children)`. `PAGE_ID` is a default, not a rule: `page-root` is what a producer
calls its layout root, and nothing reads it.
"""

from __future__ import annotations

from ..protocol import RESERVED_PREFIX
from . import builders as b
from .types import Accrete

__all__ = ["PATH_ID", "TITLE_ID", "PAGE_ID", "path_marker", "title_marker", "page"]

PATH_ID = f"{RESERVED_PREFIX}path"
TITLE_ID = f"{RESERVED_PREFIX}title"
PAGE_ID = "page-root"


def path_marker(path: str) -> Accrete:
    """The address the page is showing. The runtime copies it into the address bar."""
    return b.placeholder(b.text(path), id=PATH_ID)


def title_marker(title: str) -> Accrete:
    """The page's title. The runtime copies it into `document.title`."""
    return b.placeholder(b.text(title), id=TITLE_ID)


def page(path: str, title: str, *children: Accrete, id: str = PAGE_ID) -> Accrete:
    """A page: the two markers first (in this order), then the content.

    Order matters only for reading the frame, not for the runtime: both markers are found by id.
    Marshal them first anyway — a page turn's frame then reads like the page it becomes.
    """
    return b.case(path_marker(path), title_marker(title), *children, id=id)