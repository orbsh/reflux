#!/usr/bin/env python3
"""T4 gate — the page's uplinks: which component fires, when, and what the frame carries.

The timing and the payload belong to the renderer, so the gate asserts the renderer's real
contract — read out of `ui_leptos`, not assumed:

- an `input` emits on **Enter** (there is no blur handler anywhere in that crate), and an empty
  value does not fire at all;
- an `input` bound with `field` only commits into its form's field signal — the uplink is the
  form's, one frame carrying every field as `{field: {data, payload?}}`;
- a `form` submits when a `button` with a `submit` binding flips its confirm signal;
- the frame's `id` is the **emitting node's** own id, and an empty id is no id at all (the key is
  absent, it is not null);
- there is no `payload` lane of ours: what a producer sends is what the component sends. (The
  field entry does carry `"payload": null` — the renderer's own `Option` without a skip — so the
  gate asserts that shape rather than pretending the key is absent.)

    python3 tools/gate_t4.py
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

SEEN: list[dict] = []


def field(name: str, *, id: str) -> dict:
    """An input whose value lands in the enclosing form's field signal on Enter."""
    return {
        "type": "input",
        "id": id,
        "bind": {"value": {"kind": "field", "field": name, "type": "text"}},
    }


def tree() -> Any:
    return b.case(
        # 0: an event-emitting input with its own identity
        {"type": "input", "id": "name-in", "bind": {"value": {"kind": "event", "event": "gate.name", "type": "text"}}},
        # 1: the same, with no id — an empty id is not an id
        {"type": "input", "bind": {"value": {"kind": "event", "event": "gate.anon", "type": "text"}}},
        # 2: a form: two field inputs and its submit button
        {
            "type": "form",
            "id": "the-form",
            "bind": {"value": {"kind": "event", "event": "gate.form"}},
            "children": [
                field("who", id="who-in"),
                field("n", id="n-in"),
                {"type": "button", "bind": {"value": {"kind": "submit"}}},
            ],
        },
    )


def press_enter(cdp: Cdp) -> None:
    """A real Enter keydown/keyup on whatever is focused (the renderer listens on keydown)."""
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


def focus(cdp: Cdp, index: int) -> None:
    """Focus the index-th input of the page (the tree's order is the gate's own)."""
    cdp.eval(f"document.querySelectorAll('input')[{index}].focus()")


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

    for event in ("gate.name", "gate.anon", "gate.form"):
        app.events.register(event, lambda session, frame: SEEN.append(frame))

    with open_page(path=PAGE, app=app, settle=0.5) as (cdp, base):
        session = next(iter(app.live()), None)
        if session is None:
            print("no session: the page never connected")
            return 1

        session.send(wire.draw(session.id, wire.create(tree())))
        drawn = wait_for(lambda: cdp.eval("document.querySelectorAll('input').length === 4"))
        cdp.drain()
        if not drawn:
            print("the fixture never drew: expected four inputs")
            return 1

        # 1 — Enter on an input is the uplink, and the frame is exactly {event, id, data}.
        focus(cdp, 0)
        cdp.type_text("hello")
        press_enter(cdp)
        wait_for(lambda: len(SEEN) == 1)
        first = SEEN[0] if SEEN else {}
        checks.append(
            (
                "an input's Enter uplinks {event, id, data}",
                first == {"event": "gate.name", "id": "name-in", "data": "hello"},
                json.dumps(first, ensure_ascii=False),
            )
        )

        # 2 — an empty value does not fire (the renderer's own rule), and the input cleared itself.
        before = len(SEEN)
        press_enter(cdp)
        time.sleep(0.4)
        checks.append(
            (
                "an empty input does not fire on Enter",
                len(SEEN) == before,
                f"frames +{len(SEEN) - before}",
            )
        )

        # 3 — no id on the node, no `id` key on the frame.
        focus(cdp, 1)
        cdp.type_text("anon")
        press_enter(cdp)
        wait_for(lambda: len(SEEN) == 2)
        second = SEEN[1] if len(SEEN) > 1 else {}
        checks.append(
            (
                "an input without an id sends no id key",
                second == {"event": "gate.anon", "data": "anon"},
                json.dumps(second, ensure_ascii=False),
            )
        )

        # 4 — a `field` input commits, it does not uplink; the form owns the frame.
        before = len(SEEN)
        focus(cdp, 2)
        cdp.type_text("ada")
        press_enter(cdp)
        focus(cdp, 3)
        cdp.type_text("7")
        press_enter(cdp)
        time.sleep(0.4)
        silent = len(SEEN) == before
        checks.append(("a form field's Enter commits without uplinking", silent, f"frames +{len(SEEN) - before}"))

        # 5 — the submit button's click is the one frame, carrying every field.
        cdp.click(".button")  # a form draws as a div; the button carries the role class
        wait_for(lambda: len(SEEN) == before + 1)
        submit = SEEN[-1] if len(SEEN) > before else {}
        checks.append(
            (
                "a form submits once, with every field and the form's own id",
                submit
                == {
                    "event": "gate.form",
                    "id": "the-form",
                    "data": {
                        "who": {"data": "ada", "payload": None},
                        "n": {"data": "7", "payload": None},
                    },
                },
                json.dumps(submit, ensure_ascii=False),
            )
        )

        # 6 — no payload *of ours*: the entry's `payload` is the renderer's `Option` at null, which is
        # what an undeclared field looks like. A producer cannot populate it — there is no lane.
        entries = list((submit.get("data") or {}).values()) if isinstance(submit.get("data"), dict) else []
        checks.append(
            (
                "nothing but the renderer's own null payload rides a field",
                [set(e) for e in entries] == [{"data", "payload"}, {"data", "payload"}]
                and all(e.get("payload") is None for e in entries),
                f"entries={entries}",
            )
        )

        # 7 — the confirm signal is consumed: a second click is a second submit, not a stuck state.
        before = len(SEEN)
        cdp.click(".button")  # a form draws as a div; the button carries the role class
        wait_for(lambda: len(SEEN) == before + 1)
        checks.append(
            (
                "the form's confirm resets after a submit",
                len(SEEN) == before + 1,
                f"frames +{len(SEEN) - before}",
            )
        )

        errors = console_errors(cdp)
        checks.append(("zero console errors", not errors, "none" if not errors else str(errors)))

    return report(checks, gate="T4 GATE")


if __name__ == "__main__":
    sys.exit(main())