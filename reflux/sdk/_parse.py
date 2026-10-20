"""The SDK's boundary and `bind` assembly — hand-written, never generated.

The generated builders call into this module. Two jobs:

- `parse` / `dump`: validate a built node against the wire's types and turn it back into the wire's
  dict. Refusal is loud (a pydantic `ValidationError`) and "no value" is `None`, never a sentinel.
- `bind_value` / `bind_options` / `bind_select`: assemble one entry of accrete's `bind` map, one
  落点 at a time.

Why `drop_none` rather than emitting `null`s: accrete's serde skips absent fields and a `null` value
is meaningless on this wire, so the SDK's shape is "absent means None". An empty dict collapses to
None for the same reason — an empty container is noise, not information.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import TypeAdapter

from .types import Accrete

__all__ = ["parse", "dump", "drop_none", "bind_value", "bind_options", "bind_select"]


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


def bind_entry(
    key: str,
    *,
    default: Any = None,
    source: str | None = None,
    event: str | None = None,
    field: str | None = None,
    local: str | None = None,
    submit: Any = None,
    payload: Any = None,
    js_kind: Any = None,
) -> dict[str, Any] | None:
    """One entry of accrete's `bind` map — the display source, the uplink落点, or a form field, one
    at a time. `key` is the entry's name on the wire (`value` for most types; `options` for a
    select's rows, `select` for a pages container's key, `placeholder` for a textarea's).

    `js_kind` is the entry's own `type` (accrete's `JsType`: bool → a checkbox, number, text,
    password, …), a sibling of the variant, not part of it. `payload` rides a `field`落点 only.
    """
    picks = [
        ("default", default),
        ("source", source),
        ("event", event),
        ("field", field),
        ("local", local),
        ("submit", submit),
    ]
    chosen = [(kind, value) for kind, value in picks if value is not None]
    if len(chosen) > 1:
        names = [kind for kind, _ in chosen]
        raise ValueError(f'bind[{key!r}] takes one落点 at a time, got {names}')
    if not chosen:
        if payload is not None or js_kind is not None:
            raise ValueError(f"bind[{key!r}]: payload / kind need a落点 to ride on")
        return None
    kind, value = chosen[0]
    entry: dict[str, Any] = {"kind": kind}
    if kind in ("default", "submit"):
        entry["default"] = value  # the variant is unit; its value is the entry's own `default`
    elif kind == "field":
        entry["field"] = value
        if payload is not None:
            entry["payload"] = payload
    elif kind == "local":
        entry["slot"] = value
    else:  # source / event carry their own field, named after the kind
        entry[kind] = value
    if js_kind is not None:
        entry["type"] = getattr(js_kind, "value", js_kind)
    return entry


def bind_value(**kw: Any) -> dict[str, Any] | None:
    """`bind["value"]` — the entry almost every type carries."""
    return bind_entry("value", **kw)


def bind_options(*, source: str | None = None) -> dict[str, Any] | None:
    """`bind["options"]` — a select's rows: a list slot's name."""
    return bind_entry("options", source=source)


def bind_select(*, source: str | None = None, local: str | None = None) -> dict[str, Any] | None:
    """`bind["select"]` — a pages container's selection key: a source slot or a local value slot."""
    return bind_entry("select", source=source, local=local)