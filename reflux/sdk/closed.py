"""The closed sets, read off the generated models — one vocabulary, two fences.

`schema/accrete.schema.json` → `parse`/`dump`/`tools/gen_sdk.py` → `reflux/sdk/types.py` →
the tables below. Nothing here retypes a type, a field or a domain; the allowlists are computed
from the models at import time, and value domains stay pydantic's job (`parse`).

Two callers, one rule:

- `reflux/wire.py` — a hand-written node must fail **where it is built** (`ValueError`, loud).
- `reflux/ingest.py` — a frame handed straight to a device must fail at the server's boundary.

Why a shared module rather than two walks: a node's closure is a fact about the vocabulary, and a
second copy of it is exactly the drift this stack keeps paying for. The two callers differ only in
what they do with the reason.

The profile's `hidden_attrs` (`class`) are subtracted here on purpose: they exist in accrete but
not in a producer's reach, so the builders never emit them and a hand-written frame that does is
refused. `selector` is *not* hidden: an `entry` names each of its fields with its child's
`attrs.selector` (ADR 0031 §4), so it is data a frame must be able to carry. The profile's `expose`
is *not* consulted — that is the builder surface, not the wire's closure (a `stamp` node is legal
on the wire and has no builder).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, get_args

from .profile import hidden_attrs, tokens
from .types import Accrete, Bind

__all__ = ["problem", "node_keys", "attrs_keys", "bind_keys", "value_fields", "token_values", "arms"]


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
    """Per node type: the attributes it may carry, minus the profile's hidden ones.

    `class` is the one exception, and only where the profile declares variants for the type: there
    it is the token lane's carrier (`variant=` → one of these strings), so the key is allowed and
    `problem` then checks every member against `token_values`.
    """
    hidden = hidden_attrs()
    out: dict[str, frozenset[str]] = {}
    for tag, cls in arms().items():
        field = cls.model_fields.get("attrs")
        model = _attrs_model(field.annotation) if field is not None else None
        keys = _wire_keys(model) if model is not None else frozenset()
        allowed = keys - hidden
        if token_values(tag):
            allowed |= keys & {"class"}
        out[tag] = frozenset(allowed)
    return out


@lru_cache(maxsize=None)
def token_values(tag: str) -> frozenset[str]:
    """The class strings the profile declares for `tag` — the closed set behind `variant=`."""
    return frozenset((tokens().get(tag) or {}).values())


@lru_cache(maxsize=1)
def bind_keys() -> frozenset[str]:
    """The keys a `Bind` may carry — one value, one address, one closed scope (ADR 0031)."""
    return _wire_keys(Bind)


@lru_cache(maxsize=1)
def value_fields() -> dict[str, frozenset[str]]:
    """Per node type: the fields that carry a `Bind` (`source`, `sink`, and named second values).

    Read off the generated models, not listed by hand: a node that grows a fourth value makes this
    table grow with it, and `problem` then closes that field for free.
    """
    out: dict[str, frozenset[str]] = {}
    for tag, cls in arms().items():
        out[tag] = frozenset(
            field.alias or name
            for name, field in cls.model_fields.items()
            if any(part is Bind for part in get_args(field.annotation))
        )
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
        classy = attrs.get("class")
        if classy is not None:
            if not isinstance(classy, list) or not all(isinstance(c, str) for c in classy):
                return f"{where}: class must be a list of token names"
            stray = [c for c in classy if c not in token_values(tag)]
            if stray:
                return f"{where}: {_names(stray)} is not a token of {tag!r}"

    # Every value a node carries is one `Bind` (ADR 0031): the two channels and the node's own
    # named second values are the same shape, so one key set closes all of them.
    for field in value_fields()[tag]:
        entry = node.get(field)
        if entry is None:
            continue
        if not isinstance(entry, dict):
            return f"{where}: {field} is {type(entry).__name__}, not an object"
        extra = set(entry) - bind_keys()
        if extra:
            return f"{where}.{field}: {_names(extra)} is not a field of a value (slot/scope/default/path/type)"

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