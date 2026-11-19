"""The SDK's boundary and value-channel assembly — hand-written, never generated.

The generated builders call into this module. Two jobs:

- `parse` / `dump`: validate a built node against the wire's types and turn it back into the wire's
  dict. Refusal is loud (a pydantic `ValidationError`) and "no value" is `None`, never a sentinel.
- `as_source` / `as_sink`: turn what a caller passed to a channel into the wire's `Bind` shape —
  ADR 0031's one value, one address, one closed scope.

Why `drop_none` rather than emitting `null`s: accrete's serde skips absent fields and a `null` value
is meaningless on this wire, so the SDK's shape is "absent means None". An empty dict collapses to
None for the same reason — an empty container is noise, not information.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import TypeAdapter

from .types import Accrete, Bind
from . import profile

__all__ = ["parse", "dump", "drop_none", "token_attrs", "as_source", "as_sink", "as_set"]


@lru_cache(maxsize=None)
def _adapter(cls: Any) -> TypeAdapter:
    return TypeAdapter(cls)


def parse(obj: Any, cls: Any = None) -> Any:
    """Validate `obj` (or each item of a list) into the wire's types.

    `cls` defaults to the `Accrete` union, which discriminates on `type`; pass a component class to
    demand that exact one. An unknown `type`, a missing one, or a field of the wrong shape raises —
    the boundary is where a producer's mistake should surface.
    """
    adapter = _adapter(cls or Accrete)
    if isinstance(obj, (list, tuple)):
        return [adapter.validate_python(item) for item in obj]
    return adapter.validate_python(obj)


def dump(node: Any) -> Any:
    """The wire dict for a built node (or a list of them): `None` fields dropped, enums as values.

    `mode="json"` is what makes this the *wire's* dict rather than a Python one: an enum field is
    serialized to its value (accrete's enums are string-valued) instead of an enum member.
    `by_alias` is the other half of the same rule: the wire says `class`, so the model's `class_`
    must leave here as `class` — the Python spelling would be dropped by the renderer's serde.
    """
    if isinstance(node, (list, tuple)):
        return [dump(item) for item in node]
    if node is None:
        return None
    return node.model_dump(exclude_none=True, mode="json", by_alias=True)


def drop_none(**kw: Any) -> dict[str, Any] | None:
    """The keyword arguments minus the `None`s; empty collapses to `None`."""
    out = {k: v for k, v in kw.items() if v is not None}
    return out or None


def token_attrs(attrs: dict[str, Any] | None, variant: str | None, tag: str) -> dict[str, Any] | None:
    """`variant=` → `attrs.class`, the token lane.

    The producer picks a **name** from the profile's closed set for its type; the class string
    behind it is the profile's, and it is the only way a class ever reaches the wire (the builders
    have no `class` keyword otherwise). An unknown variant is refused here, listing the set — the
    alternative is a class the stylesheet does not know and a page that silently looks wrong.
    """
    if variant is None:
        return attrs
    tokens = profile.tokens().get(tag) or {}
    if variant not in tokens:
        known = ", ".join(sorted(tokens)) or "none declared"
        raise ValueError(f"{tag}: {variant!r} is not a variant of this type ({known})")
    out = dict(attrs or {})
    out["class"] = [tokens[variant], *out.get("class", [])]
    return out


def _bind(value: Any, name: str, *, constant: bool = False) -> dict[str, Any]:
    """One channel's entry: a `Bind` as it is, a `Slot` as its name, anything else as a constant.

    A `Bind` is the whole address — slot, scope, default, path, type — so a caller that needs a
    scope writes `Bind(slot="draft", scope="local")` rather than a second keyword beside the slot.
    """
    if value is None:
        return {}
    if isinstance(value, Bind):
        return value.model_dump(exclude_none=True)
    from ..slots import Slot  # local: reflux.slots -> reflux.wire -> reflux.sdk is a cycle here

    if isinstance(value, Slot):
        value.declare()  # the name is used here; `/status` lists names in use
        return {"slot": value.name}
    if constant:
        return {"default": value}
    raise TypeError(
        f"{name}= takes a Bind, a Slot or a constant, got {value!r} — pass Bind(slot={value!r}) "
        f"or take the name from the table first (ctx.slot({value!r}))"
    )


def as_source(value: Any = None, *, default: Any = None, constants: bool = True) -> dict[str, Any] | None:
    """A read channel — `source=`, or one of a node's named second values.

    `default` is the type's positional `value` folded in: a slot with a fallback is exactly what the
    wire means by `{slot, default}`, so giving both is one value, not a contradiction. An explicit
    `default` on a `Bind` wins over the positional one.
    """
    entry = _bind(value, "source", constant=constants)
    if default is not None and "default" not in entry:
        entry["default"] = default
    return entry or None


def as_sink(value: Any = None) -> dict[str, Any] | None:
    """A write channel — `sink=`. A bare string is a slot name: a write has nothing to default to."""
    if isinstance(value, str):
        return {"slot": value} if value else None
    return _bind(value, "sink") or None


def as_set(value: Any = None) -> list[Any] | None:
    """A set-valued attribute — ADR 0032's `submit` (`enter | button | change`).

    The wire takes a bare string or a list and means the same thing either way; the builder
    writes the list, so one frame has one shape whoever built it.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    return list(value)