"""Frame builders: the four operations, and the one frame a turn is.

    from reflux import ops, ui

    session.draw(ops.patch("/slots/echo", "你好"))
    frame = ops.draw(ops.insert("/slots/rows", ui.text("新行", id="row-3"), anchor="end"))

A handler that changes two things sends them as *one* frame — that is what makes a turn look
atomic on the client — so the frame gets a builder too. Each builder returns the wire shape and
checks its own shape here, at the boundary: a path that is not a JSON Pointer, an anchor that is
neither ``"end"`` nor an index nor an id, a node that is not a node. The client would drop or
refuse those and count them, which is the wrong side to find out (静默降级不是选项).
"""

from __future__ import annotations

from typing import Any

from .node import Node
from .tables_generated import MAX_OPS_PER_FRAME, OPS

__all__ = ["create", "patch", "insert", "remove", "draw"]


def _pointer(path: Any, what: str) -> str:
    """A path is a JSON Pointer into the client state: "" or a string starting with "/"."""
    if not isinstance(path, str) or (path != "" and not path.startswith("/")):
        raise ValueError(
            f"{what}: {path!r} is not a JSON Pointer ('' or a string starting with '/')"
        )
    return path


def _node(node: Any, what: str) -> dict:
    if not isinstance(node, dict) or not isinstance(node.get("type"), str):
        raise ValueError(f"{what}: expected a node, got {node!r}")
    return node


def create(root: Node, title: str | None = None) -> dict:
    """Replace the whole structure (first paint, a page turn, a resync after trouble)."""
    op: dict[str, Any] = {"op": "create", "root": _node(root, "create")}
    if title is not None:
        if not isinstance(title, str):
            raise ValueError(f"create: title must be a string, got {type(title).__name__}")
        op["title"] = title
    return op


def patch(path: str, value: Any) -> dict:
    """Replace the value at a path — a slot's data, or a field inside the structure."""
    return {"op": "patch", "path": _pointer(path, "patch"), "value": value}


def insert(path: str, node: Node, anchor: Any = "end") -> dict:
    """Insert a node into the array at a path.

    The anchor is ``"end"``, ``{"index": n}`` or ``{"id": s}`` — the id form is what makes a
    row's identity survive concurrent inserts.
    """
    _node(node, "insert")
    if anchor != "end":
        if not isinstance(anchor, dict) or len(set(anchor) & {"index", "id"}) != 1:
            raise ValueError(
                f'insert: anchor must be "end", {{"index": n}} or {{"id": s}}, got {anchor!r}'
            )
        if "index" in anchor and (not isinstance(anchor["index"], int) or anchor["index"] < 0):
            raise ValueError(f"insert: anchor index must be a non-negative int, got {anchor!r}")
        if "id" in anchor and (not isinstance(anchor["id"], str) or not anchor["id"]):
            raise ValueError(f"insert: anchor id must be a non-empty string, got {anchor!r}")
    return {"op": "insert", "path": _pointer(path, "insert"), "anchor": anchor, "node": node}


def remove(path: str, id: str | None = None) -> dict:
    """Remove the value at a path, or the row carrying ``id`` inside that array."""
    op: dict[str, Any] = {"op": "remove", "path": _pointer(path, "remove")}
    if id is not None:
        if not isinstance(id, str) or not id:
            raise ValueError(f"remove: id must be a non-empty string, got {id!r}")
        op["id"] = id
    return op


def _check_row_ids(value: Any, where: str) -> None:
    """Refuse a duplicate row id inside any array of nodes this value carries.

    Keyed rendering — and the client's own check — stands on "one id per array", so a duplicate is
    a producer defect and the frame boundary is where it has to be loud. `value` may be a node, a
    list of nodes (a slot's rows), or plain data a patch carries: free data is left alone, only
    arrays of nodes are walked.
    """
    items = value if isinstance(value, list) else [value]
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("type"), str):
            continue
        row_id = item.get("id")
        if isinstance(row_id, str):
            if row_id in seen:
                raise ValueError(f"{where}: duplicate row id {row_id!r} — one id per array")
            seen.add(row_id)
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("type"), str):
            _check_row_ids(item.get("children") or [], f"{where}.children")


def draw(*ops: dict) -> dict:
    """One turn, one frame: every op a handler made travels together.

    Two rules live here rather than in each builder, because they are about the frame as a whole:
    the op cap from the spec (a runaway producer is a defect, not something to apply halfway), and
    one row id per array wherever the frame carries nodes.
    """
    if len(ops) > MAX_OPS_PER_FRAME:
        raise ValueError(f"draw: {len(ops)} ops in one frame — the cap is {MAX_OPS_PER_FRAME}")
    for op in ops:
        if not isinstance(op, dict) or op.get("op") not in OPS:
            raise ValueError(f"draw: {op!r} is not an op ({', '.join(OPS)})")
        if op["op"] == "create":
            _check_row_ids(op["root"], "create")
        elif op["op"] == "patch":
            _check_row_ids(op["value"], op["path"])
        elif op["op"] == "insert":
            _check_row_ids(op["node"], op["path"])
    return {"ev": "draw", "ops": list(ops)}