#!/usr/bin/env python3
"""M1.5 gate — the server's ingest boundary, end to end over a real socket.

The SDK refuses a bad node where it is built; this gate proves the *other* fence: a producer that
hand-writes the JSON (an app's handler, a script, a second language's SDK with a bug) is refused at
the server's door instead of being dropped silently inside the renderer.

Both directions, one session, one socket:

- outbound — `Session.send` checks every frame: the envelope's shape, each of the eight actions'
  field sets, the operation cap, the node closure (types / attributes / bind kinds / domains), and
  one row id per list slot per frame. A refused frame never reaches the client, is counted, and the
  session keeps going.
- inbound — `App.handle` checks an uplink frame before the registry can dispatch it: the key set,
  the event name's shape, the row `id`'s shape. A refused frame never reaches a handler.

The retiring shell's dialect (`{"ev": "draw", "ops": [...]}`) is *not* this layer's business and
must still pass — M1.7 retires it, and a gate that broke it now would break the seven old gates.

    python3 tools/gate_m1_5.py
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cdp import Ws, free_port, report  # noqa: E402
from reflux import wire  # noqa: E402
from reflux.app import App  # noqa: E402
from reflux.sdk import builders as b  # noqa: E402
from reflux.tables_generated import MAX_OPS_PER_FRAME  # noqa: E402

APP = App()
SEEN: list[dict] = []          # what reached a handler (a refused uplink must not show up here)
SESSION: list[str] = []        # the one session id, read from the table


def legacy_op() -> dict:
    """One op of the retiring shell's dialect — the seam this layer must not police."""
    return {"op": "patch", "path": "/slots/x", "value": 1}


def hand(node: dict, *, action: str = "create", **rest) -> dict:
    """A frame the SDK would never build: its op is written out by hand, nodes included."""
    return wire.draw(SESSION[0], {"action": action, "event": "", "data": node, **rest})


def send_all_events() -> None:
    """Every outbound check, as one batch of frames from one handler (order is the queue's)."""

    @APP.events.register("gate.legal")
    def legal(session, frame):
        session.send(wire.draw(session.id, wire.create(b.case(b.text("landed", id="ok")))))

    @APP.events.register("gate.unknown-type")
    def unknown_type(session, frame):
        session.send(hand({"type": "widget"}))

    @APP.events.register("gate.unknown-attr")
    def unknown_attr(session, frame):
        # `selector` is hidden for every type (unlike `class`, which is the token lane now).
        session.send(hand({"type": "text", "attrs": {"selector": "leak"}}))

    @APP.events.register("gate.duplicate-row")
    def duplicate_row(session, frame):
        session.send(
            wire.draw(
                session.id,
                wire.append("rows", b.text("a", id="r")),
                wire.append("rows", b.text("b", id="r")),
            )
        )

    @APP.events.register("gate.over-cap")
    def over_cap(session, frame):
        session.send(wire.draw(session.id, *[wire.empty()] * (MAX_OPS_PER_FRAME + 1)))

    @APP.events.register("gate.unknown-key")
    def unknown_key(session, frame):
        # An op with a field its action does not have — serde would ignore it silently.
        bad = hand({"type": "text", "bind": {"value": {"kind": "default", "default": "x"}}})
        bad["content"][0]["root"] = {}
        session.send(bad)

    @APP.events.register("gate.legacy")
    def legacy(session, frame):
        # The retiring shell's shape: no `content`, so this boundary leaves it alone.
        session.send({"ev": "draw", "ops": [legacy_op()]})

    @APP.events.register("gate.alive")
    def alive(session, frame):
        session.send(wire.draw(session.id, wire.set("echo", b.text("alive"))))


def uplink_handlers() -> list[dict]:
    """One handler that answers, so a refused uplink is visible as a *missing* answer."""

    @APP.events.register("gate.uplink")
    def uplink(session, frame):
        SEEN.append(frame)
        session.send(wire.draw(session.id, wire.set("echo", b.text(repr(frame["data"])))))

    return SEEN


def recv(ws: Ws, timeout: float = 3.0) -> dict | None:
    """The next frame, or None if the client waited `timeout` and the server sent nothing."""
    ws.sock.settimeout(timeout)
    try:
        return ws.recv()
    except (socket.timeout, TimeoutError):
        return None


def ask(ws: Ws, event: str, data: dict | None = None, **extra) -> None:
    ws.send({"event": event, "data": {} if data is None else data, **extra})


def main() -> int:
    port = free_port()
    server = APP.make_server(port)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    ws = Ws(f"ws://127.0.0.1:{port}/ws")

    deadline = time.monotonic() + 5.0
    while not APP.live() and time.monotonic() < deadline:
        time.sleep(0.01)
    if not APP.live():
        print("no session: the socket never reached the app")
        return 1
    SESSION.append(APP.live()[0].id)

    send_all_events()
    uplink_handlers()
    checks: list[tuple[str, bool, str]] = []

    # 1 — the legal frame is the control: this boundary refuses, it does not block.
    ask(ws, "gate.legal")
    first = recv(ws)
    checks.append(
        (
            "a legal frame lands unchanged",
            first is not None
            and first.get("ev") == "draw"
            and first.get("content") == [wire.create(b.case(b.text("landed", id="ok")))],
            json.dumps(first, ensure_ascii=False)[:70] if first else "nothing arrived",
        )
    )

    # 2-6 — each refusal: nothing on the wire, counted, logged with the session and the defect.
    refusals = [
        ("an unknown node type", "gate.unknown-type", "not one of the wire's types"),
        ("an attribute outside the profile", "gate.unknown-attr", "is not an attribute"),
        ("one row id twice in a frame", "gate.duplicate-row", "appears twice in one frame"),
        ("more operations than the cap", "gate.over-cap", f"the cap is {MAX_OPS_PER_FRAME}"),
        ("a field the action does not have", "gate.unknown-key", "is not a field of this action"),
    ]
    for label, event, reason in refusals:
        before = APP.stats["refused"]
        ask(ws, event)
        got = recv(ws, 0.4)
        counted = APP.stats["refused"] == before + 1
        logged = any(
            "refused frame" in line and SESSION[0] in line and reason in line for line in APP.events.log
        )
        checks.append(
            (
                label,
                got is None and counted and logged,
                f"wire={'silent' if got is None else 'FRAME'} refused+{APP.stats['refused'] - before} "
                f"logged={logged}",
            )
        )

    # 7 — the client's own dialect: the session survives, and a legal frame still lands.
    ask(ws, "gate.alive")
    alive = recv(ws)
    checks.append(
        (
            "the session survives every refusal",
            alive is not None and alive.get("content") == [wire.set("echo", b.text("alive"))],
            json.dumps(alive, ensure_ascii=False)[:70] if alive else "the session stopped answering",
        )
    )

    # 8 — the retiring shell's dialect is out of scope, deliberately.
    ask(ws, "gate.legacy")
    legacy = recv(ws)
    checks.append(
        (
            "the retiring shell's dialect still passes",
            legacy is not None and legacy.get("ops") == [legacy_op()],
            json.dumps(legacy, ensure_ascii=False)[:70] if legacy else "nothing arrived",
        )
    )

    # 9-11 — the inbound door: refused before dispatch, counted, and the session keeps working.
    before = APP.stats["refused"]
    ask(ws, "gate.uplink", {"n": 1}, extra="hand written")
    silent = recv(ws, 0.4)
    checks.append(
        (
            "a bad uplink never reaches a handler",
            silent is None and not SEEN and APP.stats["refused"] == before + 1,
            f"wire={'silent' if silent is None else 'FRAME'} handler_calls={len(SEEN)} "
            f"refused+{APP.stats['refused'] - before}",
        )
    )

    before = APP.stats["refused"]
    ask(ws, "gate.uplink", {"n": 2}, id=17)
    silent = recv(ws, 0.4)
    checks.append(
        (
            "an uplink id that is not a string",
            silent is None and not SEEN and APP.stats["refused"] == before + 1,
            f"wire={'silent' if silent is None else 'FRAME'} handler_calls={len(SEEN)} "
            f"refused+{APP.stats['refused'] - before}",
        )
    )

    ask(ws, "gate.uplink", {"n": 3})
    answered = recv(ws)
    checks.append(
        (
            "a legal uplink is dispatched and answered",
            answered is not None and len(SEEN) == 1 and SEEN[0]["data"] == {"n": 3},
            f"handled={SEEN[0]['data'] if SEEN else None}",
        )
    )

    # 12 — the counters are the record: what was refused is exactly what the gate asked for.
    checks.append(
        (
            "every refusal is counted once",
            APP.stats["refused"] == len(refusals) + 2,
            f"refused={APP.stats['refused']} expected={len(refusals) + 2}",
        )
    )

    ws.close()
    server.shutdown()
    server.server_close()
    APP.stop()
    return report(checks, gate="M1.5 ingest boundary")


if __name__ == "__main__":
    sys.exit(main())