#!/usr/bin/env python3
"""T4 gate — binding: `source` / `event` / `payload`, the delegate, the uplink, the refusal.

Real browser, real mouse clicks and real keystrokes over CDP, and a real producer on the far
side of the channel: every frame asserted below is one that actually crossed the socket (the
app's `log`), not a page-side mock. The headline interactions are the demo app's — an echo, a
list living in a slot, and a form submitting several fields at once.

    python3 tools/gate_t4.py

Exit code 0 = gate passed.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cdp import console_errors, report, shell_page  # noqa: E402

import reflux.demo_app as demo  # noqa: E402
from reflux import ops, ui  # noqa: E402

HELLO = "reflux:hello"
PROBE = "probe.change"  # the gate's own event name, registered like any application's
GHOST = "ghost.press"  # never registered: the refusal path


def find(selector: str, predicate: str) -> str:
    """A JS expression resolving to one element among `selector`."""
    return f"[...document.querySelectorAll({json.dumps(selector)})].find({predicate})"


def by_placeholder(selector: str, text: str) -> str:
    return find(selector, f"(e) => e.placeholder === {json.dumps(text)}")


def by_text(selector: str, text: str) -> str:
    return find(selector, f"(e) => e.textContent.trim() === {json.dumps(text)}")


def received(app, event: str | None = None) -> list[dict]:
    """The frames that came up the channel, in order (optionally one event name)."""
    return [
        frame
        for direction, frame in app.log
        if direction == "recv" and (event is None or frame.get("event") == event)
    ]


def sent(app) -> list[dict]:
    return [frame for direction, frame in app.log if direction == "send"]


def wait(predicate, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def texts(cdp) -> str:
    """Every text component's content, joined — the page's own view of what it painted."""
    return cdp.eval(
        "[...document.querySelectorAll('.rx-text')].map((e) => e.textContent).join('|')"
    )


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, evidence: str) -> None:
        checks.append((name, ok, evidence))

    app = demo.Demo().app()
    # a registered name of the gate's own: `register(name)` alone only hands back the decorator
    app.events.register(PROBE, lambda session, frame: None)

    with shell_page(app=app) as (cdp, base):
        errors = console_errors(cdp)
        check("zero console errors", not errors, "none" if not errors else str(errors))

        # 1. the shell speaks first; structure only follows a hello
        wait(lambda: received(app, HELLO) and sent(app))
        hellos = received(app, HELLO)
        first_frame = app.log[0][1] if app.log else {}
        sends = sent(app)
        session = app.sessions[0] if app.sessions else None
        check(
            "hello first (with its path); structure after",
            bool(hellos)
            and first_frame.get("event") == HELLO
            and session is not None
            and session.path == "/"
            and bool(sends)
            and sends[0].get("ev") == "draw"
            and sends[0]["ops"][0]["op"] == "create",
            f"first recv={first_frame.get('event')!r} path={session.path if session else None!r} "
            f"first send op={sends[0]['ops'][0]['op'] if sends else None!r}",
        )

        # 2. the view is up, and the rack's rows came from the slot (`source`)
        wait(lambda: cdp.eval("document.querySelectorAll('.rx-rack .rx-row').length") == 2)
        rows_in_dom = cdp.eval("document.querySelectorAll('.rx-rack .rx-row').length")
        slot_rows = cdp.eval("(window.reflux.snapshot().slots.rows || []).map((r) => r.id)")
        check(
            "a rack mounts its rows from the slot",
            rows_in_dom == 2 and slot_rows == ["row-1", "row-2"],
            f"dom rows={rows_in_dom} slot rows={slot_rows}",
        )

        # 3. the echo: type, commit, and the producer answers into the slot
        name_input = by_placeholder(".rx-input", "名字")
        cdp.click_js(name_input)
        before_typing = len(received(app))
        cdp.type_text("alice")
        time.sleep(0.4)
        typing_delta = len(received(app)) - before_typing
        quiet_while_typing = typing_delta == 0
        cdp.click_js("document.querySelector('.rx-heading')")  # blur = the commit
        wait(lambda: received(app, "name.change"))
        echo = received(app, "name.change")
        # the frame arriving is not the paint landing: wait for the DOM the round trip produces
        wait(lambda: "alice" in (texts(cdp) or ""))
        echo_text = texts(cdp)
        check(
            "input echo: type → commit → the producer's slot write comes back",
            bool(echo)
            and echo[-1]["data"] == {"value": "alice"}
            and "alice" in (echo_text or ""),
            f"frame={echo[-1] if echo else None} texts={echo_text!r}",
        )
        check(
            "a keystroke is not a turn (fire says change, not input)",
            quiet_while_typing,
            f"frames while typing: {typing_delta}",
        )
        check(
            "payload is verbatim: keys = the declaration, in order",
            bool(echo)
            and list(echo[-1]["data"]) == ["value"]
            and set(echo[-1]) == {"event", "id", "data"}
            and echo[-1]["id"] == "name-input"
            and echo[-1]["event"] == "name.change",
            f"keys={list(echo[-1]['data']) if echo else None} frame keys={sorted(echo[-1]) if echo else None} "
            f"id={echo[-1]['id'] if echo else None!r}",
        )

        # 4. the list: add and remove, with the row's identity riding the button
        cdp.eval("window.__gate = { row: document.querySelectorAll('.rx-rack .rx-row')[1] }")
        cdp.click_js(by_text("button", "加一行"))
        wait(lambda: received(app, "row.add"))
        added = received(app, "row.add")[-1]
        wait(lambda: cdp.eval("document.querySelectorAll('.rx-rack .rx-row').length") == 3)
        rows_after_add = cdp.eval("document.querySelectorAll('.rx-rack .rx-row').length")
        kept = cdp.eval("window.__gate.row === document.querySelectorAll('.rx-rack .rx-row')[1]")
        check(
            "list add: the producer inserts, the row keeps its DOM node",
            added["data"] == {} and added["id"] == "add-row" and rows_after_add == 3 and kept,
            f"frame={added} rows={rows_after_add} identity kept={kept}",
        )

        second_row_button = (
            "[...document.querySelectorAll('.rx-rack .rx-row')]"
            ".find((r) => r.textContent.includes('第二行')).querySelector('button')"
        )
        cdp.click_js(second_row_button)
        wait(lambda: received(app, "row.remove"))
        removed = received(app, "row.remove")[-1]
        wait(lambda: cdp.eval("document.querySelectorAll('.rx-rack .rx-row').length") == 2)
        rows_after_remove = cdp.eval("document.querySelectorAll('.rx-rack .rx-row').length")
        gone = cdp.eval("!document.contains(window.__gate.row)")
        check(
            "list remove: the frame carries the row's own id",
            removed["id"] == "row-2" and rows_after_remove == 2 and gone,
            f"frame id={removed['id']!r} rows={rows_after_remove} removed in dom={not gone}",
        )

        # 5. the form: one submit, every field at once
        cdp.click_js(by_placeholder(".rx-input", "用户名"))
        cdp.type_text("alice")
        cdp.click_js(by_placeholder(".rx-input", "口令"))
        cdp.type_text("s3cret")
        cdp.click_js("document.querySelector('.rx-form button[type=submit]')")
        wait(lambda: received(app, "login.submit"))
        submits = received(app, "login.submit")
        fields = submits[-1]["data"].get("fields") if submits else None
        wait(lambda: "s3cret" in (texts(cdp) or ""))
        summary = texts(cdp)
        check(
            "form: one submit carries every field it holds",
            len(submits) == 1
            and fields == {"user": "alice", "pass": "s3cret"}
            and list(fields or {}) == ["user", "pass"]
            and submits[-1]["data"].keys() == {"fields"}
            and "s3cret" in (summary or ""),
            f"frames={len(submits)} fields={fields} keys={list(submits[-1]['data']) if submits else None}",
        )

        # 6. the probe row: a two-key payload, and an event name nobody registered
        probe_row = ui.row(
            ui.input(
                placeholder="probe",
                source="probe",
                event=PROBE,
                payload=["value", "focus"],
                id="probe-input",
            ),
            ui.button("幽灵", event=GHOST, id="ghost"),
            gap="sm",
            id="probe-row",
        )
        app.sessions[0].draw(ops.insert("/tree/children", probe_row, anchor="end"))
        wait(lambda: cdp.eval("!!" + by_placeholder(".rx-input", "probe")))

        cdp.click_js(by_placeholder(".rx-input", "probe"))
        cdp.type_text("abc")
        cdp.click_js("document.querySelector('.rx-heading')")
        wait(lambda: received(app, PROBE))
        probes = received(app, PROBE)
        probe_frame = probes[-1] if probes else {}
        check(
            "payload declared as two keys arrives as exactly two",
            probe_frame.get("data") == {"value": "abc", "focus": False}
            and list(probe_frame.get("data") or {}) == ["value", "focus"]
            and probe_frame.get("id") == "probe-input",
            f"data={probe_frame.get('data')} order={list(probe_frame.get('data') or {})}",
        )

        before_ghost = len(received(app))
        calls_before, refused_before = app.events.calls, app.events.refused
        cdp.click_js(by_text("button", "幽灵"))
        time.sleep(0.3)
        ghost_frames = received(app)[before_ghost:]
        refused = app.events.refused - refused_before
        handled = app.events.calls - calls_before
        ghost_log = app.events.log[-1] if app.events.log else ""
        check(
            "unregistered event name: uplinked verbatim, refused, never dispatched",
            refused == 1
            and handled == 0
            and GHOST in ghost_log
            and ghost_frames == [{"event": GHOST, "id": "ghost", "data": {}}],
            f"frame={ghost_frames} refused+{refused} handlers+{handled} log={ghost_log!r}",
        )

        before_add = len(received(app, "row.add"))
        cdp.click_js(by_text("button", "加一行"))
        # wait for the *new* frame: a predicate satisfied by the earlier one is not a wait at all
        wait(lambda: len(received(app, "row.add")) > before_add)
        alive = len(received(app, "row.add")) > before_add and bool(app.sessions)
        check(
            "after a refusal the session still works",
            alive,
            f"row.add frames={len(received(app, 'row.add'))} sessions={len(app.sessions)}",
        )

        # 7. every component frame has exactly the documented shape
        component_frames = [f for f in received(app) if not str(f.get("event", "")).startswith("reflux:")]
        shapes = {
            (set(f) == {"event", "id", "data"}, isinstance(f.get("event"), str), isinstance(f.get("data"), dict))
            for f in component_frames
        }
        check(
            "every uplink frame is exactly {event, id, data}",
            bool(component_frames) and shapes == {(True, True, True)},
            f"{len(component_frames)} frames, shapes={sorted(shapes)}",
        )

    return report(checks, gate="T4 GATE")


if __name__ == "__main__":
    sys.exit(main())