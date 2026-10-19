"""The outbound frame layer for the new page: accrete's eight actions, verbatim.

This is the dialect of the fluxen-backed page. The retiring shell's dialect (`{"op": "create", "root": …}`)
still lives in `reflux/ops.py`; the two never meet on one socket — each page gets frames in the shape it
can read, and the app picks the builder. When the shell retires (M1.7), `ops` goes with it.

Field names are the wire's, taken from the renderer's `content` crate: `create` / `set` carry
`Influx{event, data}`, `append` `AppendOp{event, position, data}`, `remove` `RemoveOp{event, id}`,
`patch` `PatchOp{event, id?, path, op, value}`, `inject` `InjectOp{slot, event?, id?, data}`, `tmpl`
`InfluxTmpl{name, data}`, and `empty` carries nothing. The frame is `Message{ev, sender, created?,
content}`: we write `ev = "draw"` and leave `created` out (it is optional).

Shape is what this layer can check — not list length. `position`'s domain depends on how many rows the
slot holds, so an out-of-range position is the renderer's refusal (`warn`, no counter); the gate asserts
that the row did not land. `create`'s `event` is required on the wire but unread, so we write `""`.
"""

from __future__ import annotations

from typing import Any

from .sdk._parse import dump, parse

__all__ = [
    "ACTIONS",
    "append",
    "create",
    "draw",
    "empty",
    "inject",
    "patch",
    "remove",
    "set",
    "tmpl",
]

ACTIONS = frozenset({"create", "set", "append", "remove", "patch", "inject", "tmpl", "empty"})


def _node(node: Any, what: str) -> dict:
    """A built SDK node (or a hand-written one) as the wire's dict.

    A dict goes through the same boundary the SDK builds on, so a hand-written node is validated rather
    than trusted — a producer's typo has to fail here, not as a silent drop inside the renderer.
    """
    if isinstance(node, dict):
        return dump(parse(node))
    try:
        out = dump(node)
    except AttributeError:
        raise ValueError(f"{what}: expected an accrete node, got {type(node).__name__}") from None
    if not isinstance(out, dict) or not isinstance(out.get("type"), str):
        raise ValueError(f"{what}: expected an accrete node, got {node!r}")
    return out


def _slot(name: Any, what: str) -> str:
    if not isinstance(name, str) or not name:
        raise ValueError(f"{what}: the slot name must be a non-empty string, got {name!r}")
    return name


def _pointer(path: Any, what: str) -> str:
    if not isinstance(path, str) or (path != "" and not path.startswith("/")):
        raise ValueError(
            f"{what}: {path!r} is not a JSON Pointer ('' or a string starting with '/')"
        )
    return path


def _position(position: Any, what: str) -> int:
    if not isinstance(position, int) or isinstance(position, bool):
        raise ValueError(f"{what}: position must be an int, got {position!r}")
    return position


def create(data: Any) -> dict:
    """Replace the whole layout root. `Influx.event` is required and unread — we write `""`."""
    return {"action": "create", "event": "", "data": _node(data, "create")}


def set(slot: str, data: Any) -> dict:
    """Replace the node in the named data slot."""
    return {"action": "set", "event": _slot(slot, "set"), "data": _node(data, "set")}


def append(slot: str, data: Any, *, position: int = 0) -> dict:
    """Add a row to the list slot `slot`.

    `position`: `0` (the tail, and left off the wire) · `+n` counts in from the tail (`+1` = before the
    last) · `-n` counts in from the head (`-1` = the head).
    """
    op: dict[str, Any] = {
        "action": "append",
        "event": _slot(slot, "append"),
        "data": _node(data, "append"),
    }
    position = _position(position, "append")
    if position != 0:  # 缺省即 0：位置没有信息时帧里不写这个字段
        op["position"] = position
    return op


def remove(slot: str, id: str) -> dict:
    """Drop the row carrying `id` from the list slot."""
    if not isinstance(id, str) or not id:
        raise ValueError(f"remove: the row id must be a non-empty string, got {id!r}")
    return {"action": "remove", "event": _slot(slot, "remove"), "id": id}


def patch(
    slot: str,
    path: str,
    value: Any,
    *,
    op: str = "replace",
    id: str | None = None,
) -> dict:
    """Change one value by JSON Pointer (RFC 6901) inside the addressed plane.

    Plane: `slot == ""` → the layout root; `id` set → that row of the list slot **by identity**;
    otherwise the named data slot. `op`: `replace` swaps the pointed value, `append` extends a string
    or pushes into an array.
    """
    if op not in ("replace", "append"):
        raise ValueError(f'patch: op must be "replace" or "append", got {op!r}')
    out: dict[str, Any] = {
        "action": "patch",
        "event": _slot_or_root(slot, "patch"),
        "path": _pointer(path, "patch"),
        "op": op,
        "value": value,
    }
    if id is not None:
        if not isinstance(id, str) or not id:
            raise ValueError(f"patch: the row id must be a non-empty string, got {id!r}")
        out["id"] = id
    return out


def inject(slot: str, data: Any, *, event: str | None = None, id: str | None = None) -> dict:
    """Write the vals plane as if the page had emitted a `local` event on `slot`.

    `data` is a bare JSON value: the vals plane's currency is not display form (no node). The renderer
    short-circuits an equal value, so this is safe to repeat.
    """
    out: dict[str, Any] = {"action": "inject", "slot": _slot(slot, "inject"), "data": data}
    if event is not None:
        out["event"] = _slot(event, "inject")
    if id is not None:
        if not isinstance(id, str) or not id:
            raise ValueError(f"inject: the id must be a non-empty string, got {id!r}")
        out["id"] = id
    return out


def tmpl(name: str, body: str) -> dict:
    """Register a `{{key}}` substitution table. `body` is the template's own Accrete JSON, as text."""
    if not isinstance(name, str) or not name:
        raise ValueError(f"tmpl: the name must be a non-empty string, got {name!r}")
    if not isinstance(body, str):
        raise ValueError(f"tmpl: the body must be a string of JSON, got {type(body).__name__}")
    return {"action": "tmpl", "name": name, "data": body}


def empty() -> dict:
    """An op that does nothing — the wire's own no-op."""
    return {"action": "empty"}


def draw(sender: str, *operations: dict) -> dict:
    """One turn = one frame. `sender` is the session id the envelope requires."""
    if not isinstance(sender, str) or not sender:
        raise ValueError("draw: sender must be a non-empty string (the session id)")
    if not operations:
        raise ValueError("draw: a turn carries at least one operation")
    for op in operations:
        if not isinstance(op, dict) or op.get("action") not in ACTIONS:
            raise ValueError(f"draw: {op!r} is not one of accrete's actions")
    return {"ev": "draw", "sender": sender, "content": list(operations)}


def _slot_or_root(slot: Any, what: str) -> str:
    """`""` is the layout root — the one address that is not a slot name."""
    if slot == "":
        return ""
    return _slot(slot, what)