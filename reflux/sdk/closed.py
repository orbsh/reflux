"""The closed sets, read off the generated models — one vocabulary, two fences.

`schema/accrete.schema.json` → `parse`/`dump`/`tools/gen_sdk.py` → `reflux/sdk/types.py` →
the tables below. Nothing here retypes a type, a field or a domain; the allowlists are computed
from the models at import time, and value domains stay pydantic's job (`parse`).

Two callers, one rule:

- `reflux/wire.py` — a hand-written node must fail **where it is built** (`ValueError`, loud).
- `reflux/ingest.py` — a frame handed straight to a session must fail at the server's boundary.

Why a shared module rather than two walks: a node's closure is a fact about the vocabulary, and a
second copy of it is exactly the drift this stack keeps paying for. The two callers differ only in
what they do with the reason.

The profile's `hidden_attrs` (`class`/`selector`) are subtracted here on purpose: they exist in
accrete but not in a producer's reach, so the builders never emit them and a hand-written frame
that does is refused. The profile's `expose` is *not* consulted — that is the builder surface, not
the wire's closure (a `template` node is legal on the wire and has no builder).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, get_args

from .profile import hidden_attrs
from .types import Accrete, Bind

__all__ = ["problem", "node_keys", "attrs_keys", "bind_keys", "arms"]


def _names(keys: Any) -> str:
    return ", ".join(sorted(repr(k) for k in keys))


@lru_cache(maxsize=1)
def arms() -> dict[str, Any]:
    """`type` value → the model class that carries it (the generated discriminated union)."""
    out: dict[str, Any] = {}
    for cls in get_args(get_args(Accrete)[0]):
        tag = get_args(cls.model_fields["type"].annotation)[0]
        out[tag] = cls
    return out


def _wire_keys(model: Any) -> frozenset[str]:
    """The keys a model accepts *on the wire*: the alias when it has one, else the field name.

    `class_` is the model's name for the wire's `class`; only the wire's name is allowed, so a
    producer leaking the Python spelling is refused instead of silently dropped by serde.
    """
    return frozenset(field.alias or name for name, field in model.model_fields.items())


def _attrs_model(annotation: Any) -> Any:
    """The model class inside `X | None` (an `attrs` annotation), or None."""
    for part in get_args(annotation):
        if hasattr(part, "model_fields"):
            return part
    return None


@lru_cache(maxsize=1)
def node_keys() -> dict[str, frozenset[str]]:
    return {tag: _wire_keys(cls) for tag, cls in arms().items()}


@lru_cache(maxsize=1)
def attrs_keys() -> dict[str, frozenset[str]]:
    """Per node type: the attributes it may carry, minus the profile's hidden ones."""
    hidden = hidden_attrs()
    out: dict[str, frozenset[str]] = {}
    for tag, cls in arms().items():
        field = cls.model_fields.get("attrs")
        model = _attrs_model(field.annotation) if field is not None else None
        out[tag] = frozenset(_wire_keys(model) - hidden) if model is not None else frozenset()
    return out


@lru_cache(maxsize=1)
def bind_keys() -> dict[str, frozenset[str]]:
    """`bind` entry `kind` → the keys that entry may carry (the `Bind` union's own members)."""
    out: dict[str, frozenset[str]] = {}
    for cls in get_args(get_args(Bind)[0]):
        kind = get_args(cls.model_fields["kind"].annotation)[0]
        out[kind] = _wire_keys(cls)
    return out


def problem(node: Any, where: str = "node") -> str | None:
    """The first thing outside the vocabulary, or None. Structure only — domains are `parse`."""
    if not isinstance(node, dict):
        return f"{where}: a node is an object, got {type(node).__name__}"
    tag = node.get("type")
    if not isinstance(tag, str):
        return f"{where}: no `type` tag ({tag!r})"
    allowed = node_keys().get(tag)
    if allowed is None:
        return f"{where}: {tag!r} is not one of the wire's types"
    extra = set(node) - allowed
    if extra:
        return f"{where}: {_names(extra)} is not a field of {tag!r}"

    attrs = node.get("attrs")
    if attrs is not None:
        if not isinstance(attrs, dict):
            return f"{where}: attrs is {type(attrs).__name__}, not an object"
        extra = set(attrs) - attrs_keys()[tag]
        if extra:
            return f"{where}: {_names(extra)} is not an attribute of {tag!r}"

    bind = node.get("bind")
    if bind is not None:
        if not isinstance(bind, dict):
            return f"{where}: bind is {type(bind).__name__}, not an object"
        for key, entry in bind.items():
            bad = _bind_entry(entry, f"{where}.bind[{key!r}]")
            if bad:
                return bad

    for field in ("children", "item"):
        kids = node.get(field)
        if kids is None:
            continue
        if not isinstance(kids, list):
            return f"{where}: {field} is {type(kids).__name__}, not a list"
        for i, kid in enumerate(kids):
            bad = problem(kid, f"{where}.{field}[{i}]")
            if bad:
                return bad
    return None


def _bind_entry(entry: Any, where: str) -> str | None:
    if not isinstance(entry, dict):
        return f"{where}: a binding is an object, got {type(entry).__name__}"
    kind = entry.get("kind")
    allowed = bind_keys().get(kind) if isinstance(kind, str) else None
    if allowed is None:
        return f"{where}: {kind!r} is not one of the wire's binding kinds"
    extra = set(entry) - allowed
    if extra:
        return f"{where}: {_names(extra)} is not a field of a {kind!r} binding"
    return None