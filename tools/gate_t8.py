#!/usr/bin/env python3
"""T8 gate — every failure mode the design lists, each one refusable without losing the session.

Two phases again. The offline phase drives a real socket with a stdlib client: bad JSON, an
unregistered name, a frame with no `event`, a handler that raises — four refusals counted, and
after each one the session still answers. It also proves the two producer-side refusals (the op cap
and one row id per array) and the isolation claim that matters most here: a client that stopped
reading must not hold anybody else's frames.

The browser phase proves the shell's half: a hand-built frame over the cap is refused *whole* (the
store does not move), and an uplink whose declared payload the shell cannot read is not sent at all.

    python3 tools/gate_t8.py

Exit code 0 = gate passed.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cdp import Ws, report, shell_page  # noqa: E402

import reflux.demo_app as demo  # noqa: E402
from reflux import ops, ui  # noqa: E402
from reflux.app import App  # noqa: E402
from reflux.routes import Routes  # noqa: E402
from reflux.tables_generated import MAX_OPS_PER_FRAME  # noqa: E402


def wait_for(condition, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return condition()


def offline_phase() -> list[tuple[str, bool, str]]:
    app = App(routes=Routes(), heartbeat=10.0, dead_after=30.0, outbox=4)
    app.events.register("ok.ping")(
        lambda session, frame: session.draw(ops.patch("/slots/x", "pong"))
    )

    def boom(session, frame):
        raise RuntimeError("handler defect")

    app.events.register("boom")(boom)
    srv = app.make_server(0)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    client = Ws(f"ws://127.0.0.1:{port}/ws")
    check: list[tuple[str, bool, str]] = []

    def round_trip() -> bool:
        """One good turn: the session answers, so it survived whatever came before."""
        client.send({"event": "ok.ping", "data": {}})
        try:
            frame = client.recv()
        except (EOFError, TimeoutError):
            return False
        return bool(frame.get("ops")) and frame["ops"][0]["op"] == "patch"

    try:
        client.send({"event": "reflux:hello", "data": {"path": "/"}})
        check.append(
            ("a connection registers a session", wait_for(lambda: len(app.live()) == 1), f"live={len(app.live())}")
        )

        refused_before = app.events.refused
        client._send_frame(0x1, b"this is not json")  # a frame that never parses
        client.send({"event": "no.such.handler", "data": {}})  # unregistered: never dispatched
        client.send({"data": {}})  # no event key at all
        client.send({"event": "boom", "data": {}})  # a handler that raises
        counted = wait_for(lambda: app.events.refused == refused_before + 4)
        traceback_logged = any("handler for 'boom' raised" in line for line in app.events.log)
        check.append(
            (
                "bad JSON / unknown name / no event / raising handler: four refusals, one per frame",
                counted and traceback_logged and round_trip(),
                f"refused +{app.events.refused - refused_before} traceback={traceback_logged} session answered",
            )
        )

        cap_refused = dup_refused = False
        try:
            ops.draw(*[ops.patch("/slots/x", 1)] * (MAX_OPS_PER_FRAME + 1))
        except ValueError:
            cap_refused = True
        try:
            ops.draw(ops.patch("/slots/rows", [ui.text("a", id="r"), ui.text("b", id="r")]))
        except ValueError:
            dup_refused = True
        check.append(
            (
                "the producer refuses before the wire sees it: over the cap, duplicate row id",
                cap_refused and dup_refused,
                f"cap={cap_refused} duplicate_id={dup_refused}",
            )
        )

        # A client that reads nothing: big frames fill its socket, the (tiny) outbox starts shedding,
        # and the point of the check is that the *other* session keeps flowing meanwhile.
        deaf = Ws(f"ws://127.0.0.1:{port}/ws")
        deaf.send({"event": "reflux:hello", "data": {"path": "/deaf"}})
        wait_for(lambda: any(s.path == "/deaf" for s in app.live()))
        deaf_session = next((s for s in app.live() if s.path == "/deaf"), None)
        assert deaf_session is not None, "the deaf client's session should be registered"
        reader_before = app.events.calls
        big = "x" * 200_000
        for _ in range(12):
            deaf_session.draw(ops.patch("/slots/big", big))
        shed = wait_for(lambda: app.stats["shed"] >= 1, timeout=3.0)
        isolated = round_trip()
        check.append(
            (
                "a client that stopped reading sheds frames and holds nobody else",
                shed and isolated and app.stats["shed"] >= 1,
                f"shed={app.stats['shed']} resync={app.stats['resync']} "
                f"other session answered={isolated}",
            )
        )
        deaf.sock.close()
    finally:
        client.sock.close()
        app.stop()
        srv.shutdown()
        srv.server_close()
    return check


def shell_phase() -> list[tuple[str, bool, str]]:
    app = demo.make_app()
    check: list[tuple[str, bool, str]] = []
    with shell_page(app=app) as (cdp, base):
        wait_for(lambda: len(app.live()) == 1)
        session = next(iter(app.live()), None)

        # 1. a hand-built frame over the cap (the SDK would never produce one) is refused whole
        rejected_before = cdp.eval("window.reflux.counters.rejected") or 0
        tree_before = cdp.eval("JSON.stringify(window.reflux.state.tree ?? null).length")
        app._write(
            session.channel,
            {"ev": "draw", "ops": [{"op": "patch", "path": "/slots/x", "value": 1}] * (MAX_OPS_PER_FRAME + 1)},
        )
        counted = wait_for(
            lambda: (cdp.eval("window.reflux.counters.rejected") or 0) > rejected_before
        )
        tree_after = cdp.eval("JSON.stringify(window.reflux.state.tree ?? null).length")
        errors = cdp.eval("JSON.stringify(window.reflux.errors ?? [])") or ""
        check.append(
            (
                "an oversized frame is refused whole",
                counted and tree_after == tree_before and "ops in one frame" in errors,
                f"rejected={rejected_before}->{cdp.eval('window.reflux.counters.rejected')} "
                f"tree {tree_before}->{tree_after}",
            )
        )

        # 2. a declared payload the shell cannot read refuses the uplink (and says why)
        #    The defect has to be the same lie on both sides: the frame is built against the Python
        #    tables, the uplink is refused against the shell's — so a bogus local goes into both.
        from reflux.tables_generated import COMPONENTS

        COMPONENTS["input"]["local"].append("nonsense")
        cdp.eval(
            "(async () => { const m = await import('/js/components.generated.js');"
            " m.COMPONENTS.input.local.push('nonsense'); return true; })()"
        )
        uplink_before = cdp.eval("window.reflux.uplink.refused") or 0
        app.live()[0].draw(
            ops.insert(
                "/tree/children",
                ui.field(
                    ui.input(
                        placeholder="probe",
                        source="name",
                        event="probe.change",
                        payload=["nonsense"],
                        id="probe-input",
                    ),
                    label="probe",
                ),
                anchor="end",
            )
        )
        probe = ".rx-input[placeholder=\"probe\"]"
        rendered = wait_for(lambda: cdp.eval(f"!!document.querySelector('{probe}')"))
        if rendered:
            cdp.eval(
                f"document.querySelector('{probe}').dispatchEvent(new Event('change', {{ bubbles: true }}))"
            )
        refused = wait_for(
            lambda: (cdp.eval("window.reflux.uplink.refused") or 0) > uplink_before
        )
        notes = cdp.eval("JSON.stringify(window.reflux.notes ?? [])") or ""
        errors = cdp.eval("JSON.stringify(window.reflux.errors ?? [])") or ""
        sent = [f for f in (f for d, f in app.log if d == "recv") if f.get("event") == "probe.change"]
        check.append(
            (
                "an unreadable declared payload refuses the uplink instead of sending a hole",
                rendered and refused and not sent and "cannot be read" in notes,
                f"rendered={rendered} uplink.refused={cdp.eval('window.reflux.uplink.refused')} "
                f"sent={len(sent)} note={'cannot be read' in notes} errors={errors[:120]}",
            )
        )
    app.stop()
    return check


def main() -> int:
    checks = offline_phase() + shell_phase()
    return report(checks, gate="T8 gate")


if __name__ == "__main__":
    raise SystemExit(main())