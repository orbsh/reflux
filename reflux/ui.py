"""The writing layer: the spec's whole vocabulary addressed as one module.

    from reflux import ops, ui

    page = ui.stack(
        ui.heading("看板", level=1),
        ui.input(placeholder="名字", source="name", event="name.change", payload=["value"]),
        gap="lg",
    )

``ui.<component>`` IS the generated builder for that component — real signature, real defaults,
validated at the boundary (``node.make``). So the DSL adds no vocabulary: one import, no
shadowing of ``input``, and an unknown name fails with the closed vocabulary listed. What it
does add is the shape a tree wants: children are positional (a list or tuple is spliced in,
because a view built from a loop is the normal case), and everything else is a keyword named
exactly as the wire names it.

The namespace is the module itself (PEP 562), so `from reflux import ui` and
`from reflux.ui import stack` both land on the same builders — one name per component, no
second table to keep in step.

Rejected shapes, for the record: a ``with``-block stack machine (it makes the enclosing
container implicit — a shadow parent — and a helper that appends cannot return its own
subtree), a text notation (a second syntax to keep in step with the spec), and a uniform
``ui("stack", ...)`` (it throws away the spec-derived signatures that catch a typo before the
boundary).
"""

from __future__ import annotations

import functools
from typing import Any

from . import components_generated as _builders
from .tables_generated import COMPONENTS

__all__ = sorted(COMPONENTS)


def _spliced(args: tuple) -> list:
    """Children may arrive as a list or tuple — a loop's rows — or one by one."""
    out: list = []
    for arg in args:
        if isinstance(arg, (list, tuple)):
            out.extend(arg)
        else:
            out.append(arg)
    return out


def __getattr__(name: str) -> Any:
    if name.startswith("_"):
        raise AttributeError(name)
    builder = getattr(_builders, name, None)
    if builder is None or name not in COMPONENTS:
        raise AttributeError(
            f"{name!r} is not a component; the vocabulary is closed: {sorted(COMPONENTS)}"
        )

    @functools.wraps(builder)
    def build(*args: Any, **kwargs: Any) -> Any:
        return builder(*_spliced(args), **kwargs)

    return build


def __dir__() -> list[str]:
    return sorted(COMPONENTS)