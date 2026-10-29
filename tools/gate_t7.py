#!/usr/bin/env python3
"""T7 gate — a session is one connection: created on open, reclaimed on close or when it goes quiet.

Two phases, because they want different clocks.

The browser phase drives the real page through a reload with the *default* heartbeat, so nothing
races: the check is that the old connection's session is gone and exactly one remains. A refresh
must not leave a string of sessions behind, and that is a claim about reclamation, not about
resuming anything — nothing crosses connections.

The offline phase uses tiny intervals: a stdlib client upgrades, says hello, and then stops
answering without closing (the half-open case — present in the socket, deaf to its pings, which no
close event ever reports). The watchdog must judge it dead and empty the table, and that must count
as *dead*, not as reclaimed: the two ends of a session are different facts.

    python3 tools/gate_t7.py

Exit code 0 = gate passed.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cdp import Ws, report, open_page  # noqa: E402

import reflux.demo_app as demo  # noqa: E402
from reflux.app import App  # noqa: E402
from reflux.routes import Routes  # noqa: E402


def wait_for(condition, timeout: float = 5.0) -> bool:
    """Poll a condition: the browser drops its old socket asynchronously, so a bare read races."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return condition()


def browser_phase() -> list[tuple[str, bool, str]]:
    app = demo.make_app()
    checks: list[tuple[str, bool, str]] = []
    with open_page(app=app) as (cdp, base):
        opened = wait_for(lambda: app.stats["issued"] == 1 and len(app.live()) == 1)
        session = next(iter(app.live()), None)
        checks.append(
            (
                "a connection is one session, standing where its hello said",
                opened and session is not None and session.path == "/",
                f"issued={app.stats['issued']} live={len(app.live())} path={getattr(session, 'path', None)!r}",
            )
        )

        cdp.call("Page.reload")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            cdp.drain()
            if cdp.eval("document.readyState") == "complete" and cdp.eval(
                "!!(window.__reflux && window.__reflux.booted)"
            ):
                break
            time.sleep(0.1)
        settled = wait_for(
            lambda: app.stats["issued"] >= 2 and app.stats["reclaimed"] >= 1 and len(app.live()) == 1
        )
        checks.append(
            (
                "a reload leaves exactly one session",
                settled,
                f"issued={app.stats['issued']} reclaimed={app.stats['reclaimed']} live={len(app.live())}",
            )
        )
    app.stop()
    return checks


def half_open_phase() -> list[tuple[str, bool, str]]:
    # No routes and no page: this phase is about the session table, and an app that draws nothing
    # keeps it that way (an empty table of its own, so the demo's routes cannot leak in).
    app = App(routes=Routes(), heartbeat=0.1, dead_after=0.3)
    srv = app.make_server(0)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    client = Ws(f"ws://127.0.0.1:{port}/ws")
    client.send({"dest": "reflux:hello", "data": {"path": "/"}})
    registered = wait_for(lambda: len(app.live()) == 1, timeout=3.0)
    live_after_connect = len(app.live())  # read it now: later it is legitimately gone

    # From here the client reads nothing and closes nothing: it is deaf, not gone. The server's
    # pings go out and nothing ever comes back — the only thing that can notice is a deadline.
    judged = wait_for(
        lambda: not app.live() and app.stats["dead"] >= 1 and app.stats["reclaimed"] == 0,
        timeout=6.0,
    )
    checks = [
        (
            "a connection registers a session",
            registered,
            f"live={live_after_connect}",
        ),
        (
            "a deaf client is judged dead and the table empties",
            judged,
            f"live={len(app.live())} dead={app.stats['dead']} reclaimed={app.stats['reclaimed']}",
        ),
    ]
    client.sock.close()  # cleanup only: nothing was ever read from it
    app.stop()
    srv.shutdown()
    srv.server_close()
    return checks


def main() -> int:
    checks = browser_phase() + half_open_phase()
    return report(checks, gate="T7 gate")


if __name__ == "__main__":
    raise SystemExit(main())