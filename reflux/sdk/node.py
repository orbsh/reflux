"""A page as data: `('frame', props, children)` in, a node out.

`h.frame(...)` is how a person writes a page; this is how a page that *is* data gets built — a chip
list read from a slot, a table's rows, a scene's beats, anything a producer assembles from a
structure rather than from code. It is the same builders underneath, so the frame it produces is the
same frame (byte for byte — `tests/test_h.py` says so).

The shape, and there is only one:

    ("frame", {"id": "root", "grid": {...}}, [("text", {"variant": "muted"}, "hi")])

- a **tuple** is one node: `tag`, a props dict (the builder's own keywords — an unknown key is a
  `TypeError` from the builder, the same refusal `h.frame(...)` gives), and children, which may be
  omitted, a list, or one bare value (`("text", {}, "hi")` is `h.text("hi")`).
- a **list** is several nodes, in order.
- anything else is already a node (or a value) and goes through untouched, so a tree may mix.

No type is invented here: `tag` is the wire's own `type` value, exactly as in `h.<name>(...)`.
"""

from __future__ import annotations

from typing import Any

from . import builders as _builders

__all__ = ["node"]


def node(tree: Any) -> Any:
    """Build the node (or nodes) that this structure describes."""
    if isinstance(tree, tuple):
        return _one(tree)
    if isinstance(tree, list):
        return [node(item) for item in tree]
    return tree  # already a node, or a bare value a parent asked for


def _one(tree: tuple) -> Any:
    if not tree:
        raise ValueError("a node needs at least a type: ('frame', {...}, [...])")
    tag = tree[0]
    if not isinstance(tag, str):
        raise ValueError(f"a node's first element is its type, a string — got {tag!r}")
    props = dict(tree[1]) if len(tree) > 1 and tree[1] is not None else {}
    children = tree[2] if len(tree) > 2 else None
    build = getattr(_builders, tag, None)
    if tag not in _builders.__all__ or build is None:
        raise ValueError(f"no node type {tag!r}; the vocabulary is {', '.join(_builders.__all__)}")
    return build(*(_children(children)), **props)


def _children(children: Any) -> list[Any]:
    if children is None:
        return []
    if isinstance(children, list):
        return [node(item) for item in children]
    if isinstance(children, tuple):
        return [node(children)]  # one child, written without its list
    return [children]  # a positional value: `("text", {}, "hi")`