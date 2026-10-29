#!/usr/bin/env python3
"""T8 gate — the page's side of the failure table (what `gate_ingest` does not already pin).

The *frame*-level half of this subject lives in `tools/gate_ingest.py` (two doors, one count each):
the server refuses a bad frame and counts it. What this gate asserts on the real page is what a
user's screen does when the producer or the page misbehaves:

- an event name nobody registered is refused and counted, and the page keeps working;
- a handler that raises leaves a traceback, the session alive, and the page answering;
- a frame with one bad operation is refused **whole** — the page never shows half a turn — and the
  next frame still lands.

    python3 tools/gate_t8.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cdp import Cdp, console_errors, report, open_page  # noqa: E402
from reflux import wire  # noqa: E402
from reflux.app import App  # noqa: E402
from reflux.sdk import builders as b  # noqa: E402

PAGE = "/"


def tree() -> Any:
    return b.case(
        {"type": "input", "bind": {"value": {"kind": "event", "event": "gate.nowhere", "type": "text"}}},
        {"type": "input", "bind": {"value": {"kind": "event", "event": "gate.boom", "type": "text"}}},
        # an emitter for the refused-frame case: bound to the `echo` data slot
        {"type": "text", "id": "echo", "bind": {"value": {"kind": "source", "source": "echo"}}},
    )


def press_enter(cdp: Cdp) -> None:
    for kind in ("keyDown", "keyUp"):
        cdp.call(
            "Input.dispatchKeyEvent",
            type=kind,
            key="Enter",
            code="Enter",
            windowsVirtualKeyCode=13,
            nativeVirtualKeyCode=13,
            text="\r" if kind == "keyDown" else "",
        )


def uplink(cdp: Cdp, index: int, text: str) -> None:
    """Type into the index-th input and press Enter — the page's own way of sending a frame."""
    cdp.eval(f"document.querySelectorAll('input')[{index}].focus()")
    cdp.type_text(text)
    press_enter(cdp)


def wait_for(predicate, timeout: float = 3.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def main() -> int:
    app = App()
    checks: list[tuple[str, bool, str]] = []

    @app.events.register("gate.boom")
    def boom(session, frame):
        raise RuntimeError("the producer's own defect")

    @app.events.register("gate.half")
    def half(session, frame):
        # One legal operation and one that is not a wire type: the whole frame must be refused, so
        # "half-way" can never reach the page — and the frame after it still must.
        session.send(
            wire.draw(
wire.set("echo", b.text("half-way")),
                {"action": "create", "event": "", "data": {"type": "widget"}})
        )
        session.send(wire.draw(wire.set("echo", b.text("whole"))))

    with open_page(path=PAGE, app=app, settle=0.5) as (cdp, base):
        session = next(iter(app.live()), None)
        if session is None:
            print("no session: the page never connected")
            return 1

        session.send(wire.draw(wire.create(tree())))
        drawn = wait_for(lambda: cdp.eval("document.querySelectorAll('input').length === 2"))
        cdp.drain()
        if not drawn:
            print("the fixture never drew: expected two inputs")
            return 1

        # 1 — an unregistered name: counted by the registry, never dispatched, page untouched.
        before = app.events.refused
        uplink(cdp, 0, "hello")
        wait_for(lambda: app.events.refused == before + 1)
        counted = app.events.refused == before + 1
        alive = bool(app.live()) and bool(cdp.eval("document.querySelectorAll('#main *').length > 0"))
        checks.append(
            (
                "an unregistered event name is refused and counted",
                counted and alive,
                f"registry +{app.events.refused - before} live={len(app.live())}",
            )
        )

        # 2 — a handler that raises: a traceback in the log, the session alive, the page answering.
        before = app.events.refused
        uplink(cdp, 1, "boom")
        # The counter moves before the traceback is formatted, so wait for the line, not the number.
        traceback_logged = wait_for(
            lambda: any("handler for 'gate.boom' raised" in line for line in app.events.log)
        )
        checks.append(
            (
                "a raising handler is logged and the session survives",
                app.events.refused == before + 1 and traceback_logged and bool(app.live()),
                f"registry +{app.events.refused - before} traceback={traceback_logged} live={len(app.live())}",
            )
        )

        # 3 — one bad operation refuses the frame whole: no half turn, and the next frame lands.
        before = app.stats["refused"]
        half(session, {})  # the handler directly: a `local` inject would not call it
        wait_for(lambda: "whole" in (cdp.eval("document.body.innerText") or ""))
        time.sleep(0.2)
        body = cdp.eval("document.body.innerText") or ""
        checks.append(
            (
                "a frame with one bad operation is refused whole",
                "half-way" not in body and app.stats["refused"] == before + 1,
                f"half_way={'half-way' in body} refused +{app.stats['refused'] - before}",
            )
        )
        checks.append(
            (
                "the frame after the refused one still lands",
                "whole" in body,
                "whole" if "whole" in body else "missing",
            )
        )

        errors = console_errors(cdp)
        checks.append(("zero console errors", not errors, "none" if not errors else str(errors)))

    return report(checks, gate="T8 GATE")


if __name__ == "__main__":
    sys.exit(main())