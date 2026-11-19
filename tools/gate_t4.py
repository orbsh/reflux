#!/usr/bin/env python3
"""T4 gate — the page's uplinks: which component fires, when, and what the frame carries.

The timing and the payload belong to the renderer, so the gate asserts the renderer's real
contract — read out of `ui_leptos`, not assumed:

- an `input` emits on **Enter** (there is no blur handler anywhere in that crate), and an empty
  value does not fire at all;
- a tagged `input` inside a `bundle` only commits into the bundle's pack — the uplink is the
  bundle's, one frame carrying `{tag: value}` for every field it packs;
- a `bundle` sends when `attrs.submit` names the timing and that timing happens: here only
  `button`, so a press inside it is the one submit (`enter` would make the field's Enter send);
- the frame's `id` is the **emitting node's** own id, and an empty id is no id at all (the key is
  absent, it is not null);
- there is no `payload` lane of ours: what a producer sends is what the component sends, and a
  packed field is a plain value — the old `{data, payload}` entry retired with the envelope.

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
from reflux import Slot, wire  # noqa: E402
from reflux.app import App  # noqa: E402
from reflux.sdk import builders as b  # noqa: E402

PAGE = "/"

SEEN: list[dict] = []


def field(name: str, *, id: str) -> dict:
    """An input whose typed value lands in the enclosing bundle under `name` (`tag` names it)."""
    return {"type": "input", "id": id, "tag": name}


def tree() -> Any:
    return b.frame(
        # 0: an event-emitting input with its own identity
        {"type": "input", "id": "name-in", "sink": {"slot": "gate.name"}},
        # 1: the same, with no id — an empty id is not an id
        {"type": "input", "sink": {"slot": "gate.anon"}},
        # 2: a bundle: two tagged fields and the press that packs them. `submit: [button]` says a
        # press is the only timing — Enter in a field commits, it does not uplink.
        b.bundle(
            field("who", id="who-in"),
            field("n", id="n-in"),
            b.button("送", sink=Slot("gate.form")),
            sink=Slot("gate.form"),
            submit=["button"],
            id="the-form",
        ),
        # 3: the cargo pair (ADR 0034) — a draggable frame is its own cargo, and the landing frame
        # owns the handler and what it accepts (its `sink` names the handler). A second source
        # carries a tag the landing refuses.
        b.frame(b.text("cargo", id="cargo-text"), draggable={"tag": "note"}, id="cargo-1"),
        b.frame(b.text("drop here"), accept={"tag": "note"}, sink=Slot("gate.dock"), id="dock-1"),
        b.frame(b.text("refused cargo", id="other-text"), draggable={"tag": "other"}, id="cargo-2"),
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


# A drag is the browser's gesture: `dragstart` on the source writes the cargo into the renderer's
# page-level session, and the drop on the landing frame is what emits. Synthetic DragEvents carry a
# real DataTransfer, which is what `dragstart` writes a label into; the cargo itself never travels
# through it (the session does). Cargo and landing are addressed by their own DOM ids — a draggable
# frame is a `frame`, there is no class of its own to select.
DRAG = """((sourceIndex) => {
  const source = ['cargo-1', 'cargo-2'][sourceIndex];
  const grab = document.getElementById(source);
  const dock = document.getElementById('dock-1');
  if (!grab || !dock) return 'missing';
  const dt = new DataTransfer();
  const fire = (el, type) => el.dispatchEvent(new DragEvent(type, {bubbles: true, cancelable: true, dataTransfer: dt}));
  fire(grab, 'dragstart');
  fire(dock, 'dragenter');
  fire(dock, 'dragover');
  fire(dock, 'drop');
  fire(grab, 'dragend');
  return 'ok';
})"""


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

    for event in ("gate.name", "gate.anon", "gate.form", "gate.dock"):
        app.on(event, lambda ctx, frame: SEEN.append(frame))

    with open_page(path=PAGE, app=app, settle=0.5) as (cdp, base):
        device = next(iter(app.live()), None)
        if device is None:
            print("no device: the page never connected")
            return 1

        device.send(wire.draw(wire.create(tree())))
        drawn = wait_for(lambda: cdp.eval("document.querySelectorAll('input').length === 4"))
        cdp.drain()
        if not drawn:
            print("the fixture never drew: expected four inputs")
            return 1

        # 1 — Enter on an input is the uplink, and the frame is exactly {dest, id, data}.
        focus(cdp, 0)
        cdp.type_text("hello")
        press_enter(cdp)
        wait_for(lambda: len(SEEN) == 1)
        first = SEEN[0] if SEEN else {}
        checks.append(
            (
                "an input's Enter uplinks {dest, id, data}",
                first == {"dest": "gate.name", "id": "name-in", "data": "hello"},
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
                second == {"dest": "gate.anon", "data": "anon"},
                json.dumps(second, ensure_ascii=False),
            )
        )

        # 4 — a packed field commits, it does not uplink; the bundle owns the frame.
        before = len(SEEN)
        focus(cdp, 2)
        cdp.type_text("ada")
        press_enter(cdp)
        focus(cdp, 3)
        cdp.type_text("7")
        press_enter(cdp)
        time.sleep(0.4)
        silent = len(SEEN) == before
        checks.append(("a bundle field's Enter commits without uplinking", silent, f"frames +{len(SEEN) - before}"))

        # 5 — the button's press is the one frame, carrying every field it packs.
        cdp.click(".button")  # a bundle draws as a div; the button carries the role class
        wait_for(lambda: len(SEEN) == before + 1)
        submit = SEEN[-1] if len(SEEN) > before else {}
        checks.append(
            (
                "a bundle sends once, with every tagged field and its own id",
                submit
                == {
                    "dest": "gate.form",
                    "id": "the-form",
                    "data": {"who": "ada", "n": "7"},
                },
                json.dumps(submit, ensure_ascii=False),
            )
        )

        # 6 — no wrapper: the pack is `tag → value`, not the retired `{data, payload}` entry.
        data = submit.get("data")
        packed = data if isinstance(data, dict) else {}
        checks.append(
            (
                "a packed field is a plain value, with no wrapper",
                set(packed) == {"who", "n"} and not any(isinstance(v, dict) for v in packed.values()),
                f"packed={packed}",
            )
        )

        # 7 — a second press is a second submit, not a stuck state.
        before = len(SEEN)
        cdp.click(".button")  # a bundle draws as a div; the button carries the role class
        wait_for(lambda: len(SEEN) == before + 1)
        checks.append(
            (
                "the bundle sends again on the next press",
                len(SEEN) == before + 1,
                f"frames +{len(SEEN) - before}",
            )
        )

        # 8 — a drop uplinks on the landing frame: that frame's event name, its own id, and the
        # cargo's {id, tag} as data — the cargo does not travel, only its identity and its tag do
        # (ADR 0034).
        before = len(SEEN)
        cdp.eval(f"{DRAG}(0)")
        wait_for(lambda: len(SEEN) == before + 1)
        drop = SEEN[-1] if len(SEEN) > before else {}
        checks.append(
            (
                "a drop uplinks {dest, id, data} from the landing frame",
                drop
                == {
                    "dest": "gate.dock",
                    "id": "dock-1",
                    "data": {"id": "cargo-1", "tag": "note"},
                },
                json.dumps(drop, ensure_ascii=False),
            )
        )

        # 9 — a landing frame that names what it accepts refuses the rest: the wrong tag is silent.
        before = len(SEEN)
        cdp.eval(f"{DRAG}(1)")
        time.sleep(0.4)
        checks.append(
            (
                "a landing frame refuses cargo whose tag it does not name",
                len(SEEN) == before,
                f"frames +{len(SEEN) - before}",
            )
        )

        errors = console_errors(cdp)
        checks.append(("zero console errors", not errors, "none" if not errors else str(errors)))

    return report(checks, gate="T4 GATE")


if __name__ == "__main__":
    sys.exit(main())