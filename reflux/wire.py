"""The outbound frame layer: accrete's eight actions, verbatim.

Fields are the wire's, taken from the renderer's `content` crate: `create` / `set` carry
`Influx{event, data}`, `append` `AppendOp{event, position, data}`, `remove` `RemoveOp{event, id}`,
`patch` `PatchOp{event, id?, path, op, value}`, `inject` `InjectOp{slot, event?, id?, data}`, `tmpl`
`InfluxTmpl{name, data}`, and `empty` carries nothing.

**A frame is the action list** — a bare JSON array, one element per operation. The envelope
(`Message{ev, sender, created?}`) belongs to the host and this layer has none: the renderer decodes
`[Content<Accrete>]` and nothing else (fluxen ADR 0021 decision 6). There is one verb here (`draw`),
so an `ev` field would only restate it, and a `sender` would be a field no reader has.

Shape is what this layer can check — not list length. `position`'s domain depends on how many rows the
slot holds, so an out-of-range position is the renderer's refusal (`warn`, no counter); the gate asserts
that the row did not land. `create`'s `event` is required on the wire but unread, so we write `""`.
"""

from __future__ import annotations

from typing import Any

from .protocol import MAX_OPS_PER_FRAME
from .sdk import closed
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

    A dict goes through the same two checks the server's boundary runs — closure (`closed.problem`,
    one vocabulary shared with the ingest side) and domains (`parse`) — so a producer's typo fails
    where it is built instead of being dropped silently inside the renderer. A tree also owes one
    id per node: keyed rendering needs it, and a repeat is a half-drawn list, not a list.
    """
    if isinstance(node, dict):
        bad = closed.problem(node, what)
        if bad is not None:
            raise ValueError(bad)
        out = dump(parse(node))
    else:
        try:
            out = dump(node)
        except AttributeError:
            raise ValueError(f"{what}: expected an accrete node, got {type(node).__name__}") from None
        if not isinstance(out, dict) or not isinstance(out.get("type"), str):
            raise ValueError(f"{what}: expected an accrete node, got {node!r}")
    _unique_ids(out, what, {})
    return out


def _unique_ids(node: Any, where: str, seen: dict[str, str]) -> None:
    """One id per node in one tree — the producer-side half of the rule in DESIGN's failure table.

    A list renders by key, so two nodes sharing an id make the renderer drop or reuse a row; a
    frame is cheaper to refuse here than to debug in a page. Ids ride `children` (every container)
    and `item` (a rack's or fold's row template) and nowhere else: `attrs` and `bind` hold values,
    not nodes.
    """
    if not isinstance(node, dict):
        return
    ident = node.get("id")
    if isinstance(ident, str) and ident:
        if ident in seen:
            raise ValueError(
                f"{where}: id {ident!r} appears twice in one tree (also at {seen[ident]})"
            )
        seen[ident] = where
    for key in ("children", "item"):
        kids = node.get(key)
        if isinstance(kids, list):
            for i, kid in enumerate(kids):
                _unique_ids(kid, f"{where}.{key}[{i}]", seen)


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


def draw(*operations: dict) -> list[dict]:
    """One turn = one frame: the operations, in order. Nothing wraps them."""
    if not operations:
        raise ValueError("draw: a turn carries at least one operation")
    if len(operations) > MAX_OPS_PER_FRAME:
        raise ValueError(
            f"draw: {len(operations)} operations in one frame — the cap is {MAX_OPS_PER_FRAME}"
        )
    for op in operations:
        if not isinstance(op, dict) or op.get("action") not in ACTIONS:
            raise ValueError(f"draw: {op!r} is not one of accrete's actions")
    return list(operations)


def _slot_or_root(slot: Any, what: str) -> str:
    """`""` is the layout root — the one address that is not a slot name."""
    if slot == "":
        return ""
    return _slot(slot, what)