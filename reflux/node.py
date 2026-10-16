"""The producer's node — the wire shape, one to one.

A Node is a plain dict with five keys (`type` / `id` / `attrs` / `bind` / `children`): the
shell reads exactly this, so there is no builder tree to lower and no second shape to keep
in step. `make` is the boundary: it validates against the generated component table
(closed vocabulary, value domains, bind acceptance, children cardinality) and fills attr
defaults — so a malformed node raises here, before anything reaches a socket.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

from .tables_generated import (
    BIND_KEYS,
    COMPONENTS,
    FIRE_EVENTS,
    OPS,
    RESERVED_PREFIX,
    SPEC_VERSION,
)

__all__ = [
    "Node",
    "make",
    "COMPONENTS",
    "OPS",
    "BIND_KEYS",
    "FIRE_EVENTS",
    "RESERVED_PREFIX",
    "SPEC_VERSION",
]


class Node(dict):
    """One wire node. A dict, because the wire shape *is* the API shape."""

    def dump(self) -> str:
        return json.dumps(self, ensure_ascii=False)


def _check_domain(component: str, attr: str, domain: Mapping[str, Any], value: Any) -> None:
    where = f"{component}.{attr}"
    if "enum" in domain:
        if value not in domain["enum"]:
            raise ValueError(f"{where}: {value!r} is outside {domain['enum']}")
        return
    kind = domain.get("type")
    if kind == "bool":
        if not isinstance(value, bool):
            raise ValueError(f"{where}: expected bool, got {type(value).__name__}")
    elif kind == "int":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{where}: expected int, got {type(value).__name__}")
        if "min" in domain and value < domain["min"]:
            raise ValueError(f"{where}: {value} below min {domain['min']}")
        if "max" in domain and value > domain["max"]:
            raise ValueError(f"{where}: {value} above max {domain['max']}")
    elif kind in ("string", "url"):
        if not isinstance(value, str):
            raise ValueError(f"{where}: expected str, got {type(value).__name__}")
        if kind == "url" and not (
            value.startswith("http://") or value.startswith("https://") or value.startswith("/")
        ):
            raise ValueError(f"{where}: {value!r} must be http(s) or an internal path")
    else:  # pragma: no cover - the spec validator rejects unknown kinds first
        raise ValueError(f"{where}: unknown domain kind {kind!r}")


def _require_bind(component: str, spec: Mapping[str, Any], key: str, value: Any) -> None:
    if key not in spec["bind"]:
        raise ValueError(
            f"{component} does not accept a {key!r} binding; it accepts {spec['bind']}"
        )
    if key == "event":
        if not isinstance(value, str) or not value:
            raise ValueError(f"{component}.event: event name must be a non-empty string")
        if value.startswith(RESERVED_PREFIX):
            raise ValueError(
                f"{component}.event: {value!r} uses the reserved prefix "
                f"{RESERVED_PREFIX!r} (the shell owns that namespace)"
            )
    if key == "payload":
        unknown = [p for p in value if p not in spec["local"]]
        if unknown:
            raise ValueError(
                f"{component}.payload: {unknown} is not local state of this component; "
                f"it carries {spec['local']}"
            )


def make(
    component: str,
    attrs: Mapping[str, Any] | None = None,
    children: Iterable[Node] = (),
    *,
    id: str | None = None,
    source: str | None = None,
    event: str | None = None,
    payload: list[str] | None = None,
) -> Node:
    """Build one node, or raise describing exactly what is wrong."""
    spec = COMPONENTS.get(component)
    if spec is None:
        raise ValueError(
            f"unknown component {component!r}; the vocabulary is closed: {sorted(COMPONENTS)}"
        )

    given = {k: v for k, v in (attrs or {}).items() if v is not None}
    for attr, value in given.items():
        domain = spec["attrs"].get(attr)
        if domain is None:
            raise ValueError(
                f"{component}: unknown attr {attr!r}; it accepts {sorted(spec['attrs'])}"
            )
        _check_domain(component, attr, domain, value)

    resolved: dict[str, Any] = {}
    for attr, domain in spec["attrs"].items():
        if attr in given:
            resolved[attr] = given[attr]
        elif "default" in domain:
            resolved[attr] = domain["default"]
        else:
            raise ValueError(f"{component}: missing required attr {attr!r}")

    bind: dict[str, Any] = {}
    if source is not None:
        _require_bind(component, spec, "source", source)
        bind["source"] = source
    if event is not None:
        _require_bind(component, spec, "event", event)
        bind["event"] = event
    if payload is not None:
        _require_bind(component, spec, "payload", payload)
        bind["payload"] = list(payload)

    kids = list(children)
    cardinality = spec["children"]
    if cardinality == "none" and kids:
        raise ValueError(f"{component} takes no children, got {len(kids)}")
    if cardinality == "one" and len(kids) != 1:
        raise ValueError(f"{component} takes exactly one child, got {len(kids)}")
    if id is not None and not isinstance(id, str):
        raise ValueError(f"{component}.id: expected str or None, got {type(id).__name__}")

    return Node(
        {"type": component, "id": id, "attrs": resolved, "bind": bind, "children": kids}
    )