"""The SDK's boundary and value-channel assembly — hand-written, never generated.

The generated builders call into this module. Two jobs:

- `parse` / `dump`: validate a built node against the wire's types and turn it back into the wire's
  dict. Refusal is loud (a pydantic `ValidationError`) and "no value" is `None`, never a sentinel.
- `as_source` / `as_sink`: turn what a caller passed to a channel into the wire's `Source` / `Sink`
  shape — ADR 0031's one value, one address, one closed scope (ADR 0039 split the one `Bind`).

Why `drop_none` rather than emitting `null`s: accrete's serde skips absent fields and a `null` value
is meaningless on this wire, so the SDK's shape is "absent means None". An empty dict collapses to
None for the same reason — an empty container is noise, not information.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import TypeAdapter

from .types import Accrete, Sink, Source
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
    if _carries_landing(obj):
        # A callable sink is not a name yet, so this tree is not wire-shaped yet: it validates when
        # the app draws it, which is the first moment a name can exist (`App._name_landings`).
        return obj
    adapter = _adapter(cls or Accrete)
    if isinstance(obj, (list, tuple)):
        return [adapter.validate_python(item) for item in obj]
    return adapter.validate_python(obj)


def _carries_landing(node: Any) -> bool:
    """Does this tree hold a closure landing point? The one shape the wire types do not accept yet."""
    if isinstance(node, dict):
        sink = node.get("sink")
        if isinstance(sink, dict) and "__landing__" in sink:
            return True
        return any(_carries_landing(kid) for kid in node.values())
    if isinstance(node, (list, tuple)):
        return any(_carries_landing(kid) for kid in node)
    return False


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

    **Where the key goes matters**, because a frame is compared as bytes by `gate_t10`: the class
    sits where the schema's attrs class declares it, which is first everywhere except `FrameAttr`
    (`accept` comes before it). That is also the order `sdks/rust/src/types.rs` writes, and the two
    SDKs must not disagree about a node's keys.
    """
    if variant is None:
        return attrs
    tokens = profile.tokens().get(tag) or {}
    if variant not in tokens:
        known = ", ".join(sorted(tokens)) or "none declared"
        raise ValueError(f"{tag}: {variant!r} is not a variant of this type ({known})")
    out = dict(attrs or {})
    classes = [tokens[variant], *out.pop("class", [])]
    # `accept` is the one attrs property declared before `class`.
    if "accept" in out:
        return {"accept": out.pop("accept"), "class": classes, **out}
    return {"class": classes, **out}


def _address(
    value: Any, name: str, model: type, key: str, *, constant: bool = False
) -> dict[str, Any]:
    """One channel's entry: the direction's address as it is, a `Slot` as its name, else a constant.

    The address is the whole thing for its direction — a `Source` carries slot, scope, path and
    default; a `Sink` carries dest, scope and path (ADR 0039) — so a caller that needs a scope writes
    `Source(slot="draft", scope="local")` rather than a second keyword beside the slot.
    """
    if value is None:
        return {}
    if isinstance(value, model):
        return value.model_dump(exclude_none=True)
    from ..slots import Slot  # local: reflux.slots -> reflux.wire -> reflux.sdk is a cycle here

    if isinstance(value, Slot):
        value.declare()  # the name is used here; `/status` lists names in use
        return {key: value.name}
    if constant:
        return {"default": value}
    raise TypeError(
        f"{name}= takes a {model.__name__}, a Slot or a constant, got {value!r} — pass "
        f"{model.__name__}({key}={value!r}) or take the name from the table first "
        f"(ctx.slot({value!r}))"
    )


def as_source(value: Any = None, *, default: Any = None, constants: bool = True) -> dict[str, Any] | None:
    """A read channel — `source=`, or one of a node's named second values.

    `default` is the type's positional `value` folded in: a slot with a fallback is exactly what the
    wire means by `{slot, default}`, so giving both is one value, not a contradiction. An explicit
    `default` on a `Source` wins over the positional one.
    """
    entry = _address(_source_of(value), "source", Source, "slot", constant=constants)
    if default is not None and "default" not in entry:
        entry["default"] = default
    return entry or None


def _source_of(value: Any) -> Any:
    """A bound signal reads as the slot it writes through: `h.text(source=count)` names `counter.count`."""
    from ..signals import Computed, Signal  # local: reflux.sdk -> reflux.signals is a cycle here

    if isinstance(value, (Signal, Computed)):
        return value.slot
    return value


def as_sink(value: Any = None) -> dict[str, Any] | None:
    """A write channel — `sink=`, or a callable as one.

    A bare string is a slot name: a write has nothing to default to. A **callable** (or `gated(fn)`)
    is the other kind of landing point — a handler written where the frame that sends to it is
    written — and it goes into the tree as itself; `App._draw` turns it into a name once it knows
    which device the frame is for, because a name for a closure can only be a per-connection name.
    """
    if isinstance(value, str):
        return {"dest": value} if value else None
    landing = getattr(value, "__landing__", None)
    if landing is True:  # `gated(fn)`
        return {"__landing__": value.fn, "__auth__": bool(value.auth)}
    if callable(value) and not isinstance(value, type):
        return {"__landing__": value, "__auth__": False}
    return _address(value, "sink", Sink, "dest") or None


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