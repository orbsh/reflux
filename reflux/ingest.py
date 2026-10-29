"""The server's ingest boundary — the second fence, at the one door each direction passes.

- `check_frame(frame)` — a frame the server is about to put on a socket. Called from
  `Session.send`, the single door every outbound frame passes, so a producer that hand-writes the
  JSON (bypassing the SDK) is checked here just the same.
- `check_uplink(frame)` — a frame a client sent up, checked before the registry dispatches it.

Refusal is **whole-frame** and the first defect wins: nothing is applied half way, and neither door
raises into a handler — a producer's defect is not the session's, so the session survives and the
counter records the loss. Callers do the counting and the log line (they know the session).

Where the closure comes from: `reflux/sdk/closed.py` (the generated models, themselves generated
from `schema/accrete.schema.json`) plus value domains through `parse`. This file owns only the
*frame's* own shape — the eight actions' field sets, which are the renderer's `content` crate, not
accrete's node vocabulary (`test_wire` pins the same shapes from the other side).

Two boundaries stated rather than hidden:

- **A slot name cannot be checked here.** "Was this slot declared?" needs the tree the session sent
  — shadow state — so it stays where it can be judged: the SDK's construction time.
- **There is one dialect.** An outbound frame *is* accrete's action list — a bare array — so an
  object arriving here is an envelope, and the envelope is the host's (fluxen ADR 0021 decision 6).
  The shell's four-op `ops` dialect retired in M1.7 and this boundary stopped tolerating dicts in the
  same change: a frame the renderer would refuse is not a frame this server should put on a socket.
"""

from __future__ import annotations

import json
from typing import Any, NoReturn

from .sdk import closed
from .sdk._parse import parse
from .protocol import MAX_OPS_PER_FRAME

__all__ = ["Refused", "check_frame", "check_uplink", "DEST_KEYS", "OP_KEYS"]

# An uplink frame (`Outflow`): the destination it targets, the row it claims, and its payload.
DEST_KEYS = frozenset({"dest", "id", "data"})

# Each action's field set, verbatim from `content`: `Influx` (create/set — its address is `slot`,
# `""` meaning the layout root), `AppendOp`, `RemoveOp`, `PatchOp`, `InjectOp`, `InfluxTmpl`, and the
# unit `Empty`. An address is a `slot`; `event` is a name, and only `inject` carries one (fluxen
# ADR 0022).
OP_KEYS: dict[str, frozenset[str]] = {
    "create": frozenset({"action", "slot", "data"}),
    "set": frozenset({"action", "slot", "data"}),
    "append": frozenset({"action", "slot", "position", "data"}),
    "remove": frozenset({"action", "slot", "id"}),
    "patch": frozenset({"action", "slot", "id", "path", "op", "value"}),
    "inject": frozenset({"action", "slot", "name", "id", "data"}),
    "tmpl": frozenset({"action", "name", "data"}),
    "empty": frozenset({"action"}),
}
OP_REQUIRED: dict[str, frozenset[str]] = {
    "create": frozenset({"action", "slot", "data"}),
    "set": frozenset({"action", "slot", "data"}),
    "append": frozenset({"action", "slot", "data"}),
    "remove": frozenset({"action", "slot", "id"}),
    "patch": frozenset({"action", "slot", "path", "op", "value"}),
    "inject": frozenset({"action", "slot", "data"}),
    "tmpl": frozenset({"action", "name", "data"}),
    "empty": frozenset({"action"}),
}
# Where the op carries a node — the three planes whose payload is display form.
NODE_FIELD = {"create": "data", "set": "data", "append": "data"}


class Refused(Exception):
    """A frame refused whole. The message is the reason that goes into the log."""


def _refuse(reason: str, *args: Any) -> NoReturn:
    raise Refused(reason % args if args else reason)


def _names(keys: Any) -> str:
    return ", ".join(sorted(repr(k) for k in keys))


# --- the frame ---------------------------------------------------------------------------


def check_frame(frame: Any) -> None:
    """Refuse a frame the server is about to send, or return None.

    A frame is the action list itself. A dict is the retired envelope (or the shell's `ops`
    dialect): named as such, because "expected a list" alone sends the reader looking for the
    wrong bug — the renderer refuses the same shape with the same words.
    """
    if isinstance(frame, dict):
        if "content" in frame or "ev" in frame:
            _refuse(
                "frame is an envelope (%s) — the envelope is the host's; a frame is the action list",
                _names(set(frame)),
            )
        _refuse("frame is an object — a frame is the action list, not a dict of %s", _names(set(frame)))
    if not isinstance(frame, list):
        _refuse("frame is %s, not a list of operations", type(frame).__name__)
    if not frame:
        _refuse("frame is empty — a turn carries at least one operation")
    if len(frame) > MAX_OPS_PER_FRAME:
        _refuse(
            "frame: %d operations in one frame — the cap is %d",
            len(frame),
            MAX_OPS_PER_FRAME,
        )

    appended: dict[str, set[str]] = {}
    for i, op in enumerate(frame):
        _op(op, f"frame[{i}]", appended)


def _op(op: Any, where: str, appended: dict[str, set[str]]) -> None:
    if not isinstance(op, dict):
        _refuse("%s: an operation is an object, got %s", where, type(op).__name__)
    action = op.get("action")
    if not isinstance(action, str) or action not in OP_KEYS:
        _refuse("%s: %r is not one of the eight actions", where, action)
    where = f"{where} ({action})"

    extra = set(op) - OP_KEYS[action]
    if extra:
        _refuse("%s: %s is not a field of this action", where, _names(extra))
    missing = OP_REQUIRED[action] - set(op)
    if missing:
        _refuse("%s: %s is required", where, _names(missing))

    if action in NODE_FIELD:
        _node(op["data"], f"{where}.data")
        if action == "append":
            _row_id(op, where, appended)

    if action in ("create", "set", "append"):
        _text(op["slot"], f"{where}.slot", allow_empty=action == "create")
    elif action == "remove":
        _text(op["slot"], f"{where}.slot")
        _text(op["id"], f"{where}.id")
    elif action == "patch":
        _text(op["slot"], f"{where}.slot", allow_empty=True)
        if "id" in op:
            _text(op["id"], f"{where}.id")
        path = op["path"]
        if not isinstance(path, str) or (path and not path.startswith("/")):
            _refuse("%s: path %r is not a JSON Pointer", where, path)
        if op["op"] not in ("replace", "append"):
            _refuse('%s: op is %r — "replace" or "append"', where, op["op"])
    elif action == "inject":
        _text(op["slot"], f"{where}.slot")
        if "name" in op:
            _text(op["name"], f"{where}.name")
        if "id" in op:
            _text(op["id"], f"{where}.id")
    elif action == "tmpl":
        _text(op["name"], f"{where}.name")
        body = op["data"]
        if not isinstance(body, str):
            _refuse("%s: data is %s, not the template's JSON as text", where, type(body).__name__)
        try:
            # A body is a node with `{{key}}` holes in its strings, so it parses as JSON but is not
            # a node yet: closure and domains are judged after expansion, inside the renderer.
            json.loads(body)
        except ValueError as exc:
            _refuse("%s: data is not JSON (%s)", where, exc)

    if action == "append" and "position" in op:
        position = op["position"]
        if not isinstance(position, int) or isinstance(position, bool):
            _refuse("%s: position is %r, not an integer", where, position)


def _node(node: Any, where: str) -> None:
    """Closure through the shared walk, then the domains the schema declares."""
    bad = closed.problem(node, where)
    if bad is not None:
        _refuse("%s", bad)
    try:
        parse(node)
    except Exception as exc:  # pydantic's ValidationError — a domain, not a shape
        _refuse("%s: %s", where, _one_line(exc))


def _text(value: Any, where: str, *, allow_empty: bool = False) -> None:
    if not isinstance(value, str) or (not allow_empty and not value):
        _refuse("%s: %r is not a %sstring", where, value, "" if allow_empty else "non-empty ")


def _row_id(op: dict, where: str, appended: dict[str, set[str]]) -> None:
    """One row id per list slot per frame.

    The renderer refuses a duplicate append against the list it holds (a `warn`, one row short);
    within one frame we refuse the frame instead, so a producer never gets half a turn. An empty or
    absent id is a positional row (ADR 0005) and may repeat.
    """
    data = op["data"]
    row = data.get("id") if isinstance(data, dict) else None
    if not isinstance(row, str) or not row:
        return
    seen = appended.setdefault(op["slot"], set())
    if row in seen:
        _refuse("%s: row id %r appears twice in one frame", where, row)
    seen.add(row)


def _one_line(exc: Exception) -> str:
    text = " ".join(str(exc).split())
    return text[:300] + ("…" if len(text) > 300 else "")


# --- the uplink ---------------------------------------------------------------------------


def check_uplink(frame: Any) -> None:
    """Refuse a frame a client sent up, or return None. The event *name* is the registry's call."""
    if not isinstance(frame, dict):
        _refuse("frame is %s, not an object", type(frame).__name__)
    extra = set(frame) - DEST_KEYS
    if extra:
        _refuse("uplink: %s is not a field of an uplink frame", _names(extra))
    landed = frame.get("dest")
    if not isinstance(landed, str) or not landed:
        _refuse("uplink: dest is %r, not a non-empty string", landed)
    if "id" in frame:
        row = frame["id"]
        if not isinstance(row, str) or not row:
            _refuse("uplink: id is %r, not a non-empty string", row)
    if "data" not in frame:
        _refuse("uplink: data is missing — a frame carries its payload")