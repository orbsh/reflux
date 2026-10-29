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
from . import profile

__all__ = ["parse", "dump", "drop_none", "token_attrs", "bind_value", "bind_options", "bind_select"]


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


def bind_entry(
    key: str,
    *,
    default: Any = None,
    source: str | None = None,
    dest: str | None = None,
    field: str | None = None,
    local: str | None = None,
    submit: Any = None,
    payload: Any = None,
    path: str | None = None,
    js_kind: Any = None,
) -> dict[str, Any] | None:
    """One entry of accrete's `bind` map — the display source, the uplink落点, or a form field, one
    at a time. `key` is the entry's name on the wire (`value` for most types; `options` for a
    select's rows, `select` for a pages container's key, `placeholder` for a textarea's).

    `dest` is the uplink's target (ADR 0023 — kind and field are both `dest`; the uplink is *not*
    a `slot`: a slot is a place in the page, a dest is a handler on the host).
    `js_kind` is the entry's own `type` (accrete's `JsType`: bool → a checkbox, number, text,
    password, …), a sibling of the variant, not part of it. `payload` rides a `field` entry only.
    `path` rides a `local`落点: a client-side slot holds the wrapper an in-page emit wrote, so a
    reader that wants the payload itself points at it (`path="/data"`).
    """
    picks = [
        ("default", default),
        ("source", source),
        ("dest", dest),
        ("field", field),
        ("local", local),
        ("submit", submit),
    ]
    chosen = [(kind, value) for kind, value in picks if value is not None]
    if len(chosen) > 1:
        names = [kind for kind, _ in chosen]
        raise ValueError(f'bind[{key!r}] takes one target at a time, got {names}')
    if not chosen:
        if payload is not None or js_kind is not None or path is not None:
            raise ValueError(f"bind[{key!r}]: payload / type / path need an entry to ride on")
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
        if path is not None:
            entry["path"] = path
    elif kind == "dest":
        entry["dest"] = value  # 上行目标
    else:  # source carries its own field, named after the kind
        entry[kind] = value
    if path is not None and kind != "local":
        raise ValueError(f"bind[{key!r}]: `path` rides a `local` entry, got {kind!r}")
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