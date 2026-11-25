"""The outbound frame layer: accrete's eight actions, verbatim.

Fields are the wire's, taken from the renderer's `content` crate: `create` / `set` carry
`Influx{slot, data}`, `append` `AppendOp{slot, position, data}`, `move` `MoveOp{slot, id, position}`,
`remove` `RemoveOp{slot, id}`, `patch` `PatchOp{slot, id?, path, op, value}`, `tmpl`
`InfluxTmpl{name, params, data}`, and `empty` carries nothing. (`report` and `inject` are gone:
ADR 0031 §2 and ADR 0038 §1.)

**A frame is the action list** — a bare JSON array, one element per operation. The envelope
(`Message{ev, sender, created?}`) belongs to the host and this layer has none: the renderer decodes
`[Content<Accrete>]` and nothing else (fluxen ADR 0021 decision 6). There is one verb here (`draw`),
so an `ev` field would only restate it, and a `sender` would be a field no reader has.

**An address is a `slot`; an `event` is a name** (fluxen ADR 0022). `create`/`set`/`append`/`remove`/
`patch` carry `slot` (`""` = the layout root); `event` appears only on the way *up* (`Outflow.event`,
and in a node's `sink`), plus `inject`'s optional `event?` — the local event it imitates.

Shape is what this layer can check — not list length. `position`'s domain depends on how many rows the
slot holds, so an out-of-range position is the renderer's refusal (`warn`, no counter); the gate asserts
that the row did not land. `create`'s `event` is required on the wire but unread, so we write `""`.
"""

from __future__ import annotations

import json

from typing import Any, Sequence

from .protocol import MAX_OPS_PER_FRAME
from .sdk import closed
from .sdk._parse import dump, parse

__all__ = [
    "ACTIONS",
    "append",
    "create",
    "draw",
    "empty",
    "move",
    "patch",
    "remove",
    "set",
    "tmpl",
]

ACTIONS = frozenset({"create", "set", "append", "move", "remove", "patch", "tmpl", "empty"})


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
    — and `item`, the template lane, if a type ever declares one — and nowhere else: `attrs` and the
    value channels (`source`, `sink`) hold values, not nodes.
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
    """Replace the whole layout root: `slot: ""` is the root address (the same as `patch`)."""
    return {"action": "create", "slot": "", "data": _node(data, "create")}


def set(slot: str, data: Any) -> dict:
    """Replace the node in the named data slot."""
    return {"action": "set", "slot": _slot(slot, "set"), "data": _node(data, "set")}


def append(slot: str, data: Any, *, position: int = 0) -> dict:
    """Add a row to the list slot `slot`.

    `position`: `0` (the tail, and left off the wire) · `+n` counts in from the tail (`+1` = before the
    last) · `-n` counts in from the head (`-1` = the head).
    """
    op: dict[str, Any] = {
        "action": "append",
        "slot": _slot(slot, "append"),
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
    return {"action": "remove", "slot": _slot(slot, "remove"), "id": id}


def move(slot: str, id: str, position: int) -> dict:
    """Move the row `id`, already in the list slot, to `position`.

    `position` uses `append`'s vocabulary — `0` = the end, `+n` counts in from the tail, `-n` in
    from the head — but counted on the list **with the row lifted out**, and it is always written:
    unlike `append`, the end is one of several places a row can be sent, not the absence of an
    opinion (fluxen ADR 0005). Out of range is refused by the renderer, not clamped here.
    """
    if not isinstance(id, str) or not id:
        raise ValueError(f"move: the row id must be a non-empty string, got {id!r}")
    return {
        "action": "move",
        "slot": _slot(slot, "move"),
        "id": id,
        "position": _position(position, "move"),
    }


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
        "slot": _slot_or_root(slot, "patch"),
        "path": _pointer(path, "patch"),
        "op": op,
        "value": value,
    }
    if id is not None:
        if not isinstance(id, str) or not id:
            raise ValueError(f"patch: the row id must be a non-empty string, got {id!r}")
        out["id"] = id
    return out


def tmpl(name: str, data: Any, *, params: Sequence[str] = ()) -> dict:
    """Register a template: an Accrete tree with `$name` holes, and the names it takes.

    Registration is validation (ADR 0037): every `$name` in `data` must be one of `params` and every
    param must be used, which the renderer checks when the op lands. `data` may be the tree itself or
    its JSON text — the text form is what a hand-written frame carries.
    """
    if not isinstance(name, str) or not name:
        raise ValueError(f"tmpl: the name must be a non-empty string, got {name!r}")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"tmpl {name!r}: the body is not JSON ({e})") from None
    if not isinstance(data, (dict, list)):
        raise ValueError(f"tmpl {name!r}: the body must be a node or a list of them, got {type(data).__name__}")
    names = list(params)
    if any(not isinstance(p, str) or not p for p in names):
        raise ValueError(f"tmpl {name!r}: params are names, got {names!r}")
    return {"action": "tmpl", "name": name, "params": names, "data": data}


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