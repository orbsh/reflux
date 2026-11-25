#!/usr/bin/env python3
"""Settings gate — the page's three members over a real browser, and the server remembering them.

The unit tests (`tests/test_settings.py`) own the server's half: unpacking the group, the whitelist, the
ranges, the throttled write. What only a browser can answer is the other half, and it is the half
ADR 0001 actually decided: that `scope: both` writes locally, that fluxen mirrors the members onto the
document root as `data-*`, that `STYLE` in `www/static/reflux.js` turns those into `:root` custom
properties, and that the renderer's `sketch` member draws borders. Four claims:

1. the first frame already carries the stored options (a new connection never sees "default, then
   yours");
2. a change lands **locally** — `data-accent` and `--accent` move without a round trip;
3. the same change reaches the server and is written when the throttle window closes;
4. a reload shows the stored values again, and the page logs no console errors.

    python3 tools/gate_settings.py

Exit code 0 = gate passed.
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # the cdp fixture
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # the example package

from cdp import console_errors, open_page, report  # noqa: E402

import examples.zh.demo_app as example  # noqa: E402
from examples.zh import demo_settings  # noqa: E402

PAGE = "/settings"
DEFAULTS = dict(demo_settings.DEFAULTS)


def wait_for(predicate, timeout: float = 6.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.03)
    return predicate()


def root_attr(cdp, name: str):
    return cdp.eval(f"document.documentElement.getAttribute('data-{name}')")


def custom(cdp, name: str) -> str:
    return cdp.eval(
        f"(getComputedStyle(document.documentElement).getPropertyValue('--{name}') || '').trim()"
    ) or ""


def inputs(cdp) -> list:
    """The settings group's three fields, in the order the page declares them.

    Selected by position, not by id: a field node's `id` addresses patches on the wire, and the
    renderer does not put it on the DOM (only the frame that wraps the page does).
    """
    return cdp.eval(
        "[...document.querySelectorAll('#settings-page input')].map(e => [e.type, e.value])"
    ) or []


def set_field(cdp, index: int, value: str) -> bool:
    """Type into a field and leave it, the way a person would.

    Not `el.value = x` + a synthetic `change`: the renderer listens for the events a person makes, and
    a dispatched `Event("change")` is not one of them. Focus, select, insert text, blur — the blur is
    what makes the browser fire a real `change`, which is the loom's timing here.
    """
    focused = cdp.eval(
        "(() => {"
        f"const el = document.querySelectorAll('#settings-page input')[{index}];"
        "if (!el) return false; el.focus(); el.select(); return true;"
        "})()"
    )
    if not focused:
        return False
    cdp.type_text(value)
    cdp.eval("document.activeElement && document.activeElement.blur()")
    return True


def press(cdp, name: str, code: int, times: int = 1) -> None:
    for _ in range(times):
        cdp.call("Input.dispatchKeyEvent", type="keyDown", key=name, windowsVirtualKeyCode=code, nativeVirtualKeyCode=code)
        cdp.call("Input.dispatchKeyEvent", type="keyUp", key=name, windowsVirtualKeyCode=code, nativeVirtualKeyCode=code)


def step_field(cdp, index: int, target: int) -> bool:
    """Nudge a number field with ArrowUp until it reads `target`.

    Typing into it is not usable from here: a number input has no selectable caret (`select()` is a
    no-op, the caret sits at 0), so keystrokes prepend — "18" on top of "10.0" gave "10.018". The
    arrow keys are the field's own increment, and a person's hand on the same control does the same
    thing.
    """
    cdp.eval(f"document.querySelectorAll('#settings-page input')[{index}].focus()")
    for _ in range(40):
        value = cdp.eval(f"document.querySelectorAll('#settings-page input')[{index}].value")
        try:
            current = float(value)
        except (TypeError, ValueError):
            return False
        if current == target:
            break
        press(cdp, "ArrowUp" if current < target else "ArrowDown", 38 if current < target else 40)
    cdp.eval("document.activeElement && document.activeElement.blur()")
    try:
        return float(cdp.eval(f"document.querySelectorAll('#settings-page input')[{index}].value")) == target
    except (TypeError, ValueError):
        return False


def click_field(cdp, index: int):
    return cdp.eval(
        "(() => {"
        f"const el = document.querySelectorAll('#settings-page input')[{index}];"
        "if (!el) return null; el.click(); return true;"
        "})()"
    )


def main() -> int:
    checks: list[tuple[str, bool, str]] = []
    with tempfile.TemporaryDirectory() as where:
        demo_settings.settings.path = Path(where) / "settings.json"
        demo_settings.settings.state = dict(DEFAULTS)
        app = example.make_app()

        with open_page(app=app, path=PAGE, settle=0.7) as (cdp, base):
            drawn = wait_for(lambda: "设置" in (cdp.eval("document.body.innerText") or ""))
            fields = len(inputs(cdp))
            checks.append(
                ("the page draws its heading and three fields", drawn and fields >= 3, f"fields={fields}")
            )

            # 1. the first frame carried the options
            seeded = wait_for(lambda: root_attr(cdp, "accent") == DEFAULTS["accent"])
            checks.append(
                (
                    "the stored options are mirrored on the first frame",
                    bool(seeded),
                    f"data-accent={root_attr(cdp, 'accent')!r} data-round={root_attr(cdp, 'round')!r}",
                )
            )
            checks.append(
                (
                    "STYLE turns the mirror into :root properties",
                    custom(cdp, "accent").lower() == DEFAULTS["accent"] and custom(cdp, "round") == f"{DEFAULTS['round']}px",
                    f"--accent={custom(cdp, 'accent')!r} --round={custom(cdp, 'round')!r}",
                )
            )

            # 2. local write, no round trip
            wrote = set_field(cdp, 1, "#c08a2e")
            local = wait_for(lambda: (root_attr(cdp, "accent") or "").lower() == "#c08a2e")
            checks.append(
                (
                    "a change lands locally (data-accent, then --accent)",
                    bool(wrote and local) and custom(cdp, "accent").lower() == "#c08a2e",
                    f"data-accent={root_attr(cdp, 'accent')!r} --accent={custom(cdp, 'accent')!r}",
                )
            )

            # 3. round takes a number and the table appends px
            stepped = step_field(cdp, 2, 18)
            rounded = wait_for(lambda: custom(cdp, "round") == "18px")
            checks.append(
                (
                    "round moves (10 → 18) and becomes a length",
                    bool(stepped and rounded),
                    f"--round={custom(cdp, 'round')!r} data-round={root_attr(cdp, 'round')!r}",
                )
            )

            # 3b. the STYLE table has its own checks: a value it does not understand **drops the
            # property**, which hands the look back to the stylesheet's `:root` default (10px) — it
            # does not guess, and it does not keep a value the server would have refused.
            cdp.eval("document.documentElement.setAttribute('data-round', '99.5')")
            time.sleep(0.25)
            dropped = custom(cdp, "round")
            cdp.eval("document.documentElement.setAttribute('data-round', '18')")
            checks.append(
                (
                    "STYLE refuses 99.5 and falls back to the stylesheet",
                    dropped == f"{DEFAULTS['round']}px",
                    f"--round={dropped!r} for 99.5 (stylesheet default)",
                )
            )

            # 4. sketch is the renderer's member: the mirror moves, the browser draws borders
            toggled = click_field(cdp, 0)
            mirrored = wait_for(lambda: root_attr(cdp, "sketch") == "true")
            checks.append(
                ("sketch is mirrored for the renderer", bool(toggled and mirrored), f"data-sketch={root_attr(cdp, 'sketch')!r}")
            )

            # 5. the server took the same changes (the throttle window has closed by now)
            waited = wait_for(lambda: demo_settings.settings.state["accent"] == "#c08a2e", timeout=4.0)
            state = dict(demo_settings.settings.state)
            checks.append(
                (
                    "the uplink reached the server and was merged",
                    bool(waited and state["round"] == 18 and state["sketch"] is True),
                    f"state={state}",
                )
            )

            # A reload is a new document: the flag written before it is gone, so the wait below is
            # waiting on the *new* page, not on the old DOM that happened not to have changed yet.
            cdp.eval("window.__before_reload = true; location.reload(); true")
            fresh = wait_for(lambda: cdp.eval("window.__before_reload") is None, timeout=10.0)
            stayed = wait_for(lambda: (root_attr(cdp, "accent") or "").lower() == "#c08a2e", timeout=8.0)
            checks.append(
                (
                    "a reload shows the stored values again",
                    bool(fresh and stayed),
                    f"fresh={fresh} data-accent={root_attr(cdp, 'accent')!r} data-sketch={root_attr(cdp, 'sketch')!r}",
                )
            )

            # The renderer's check icon for a bool field is an `<svg>` with an empty `viewBox`, and
            # Chromium logs one error per render. That is fluxen's, not this page's (nothing here
            # touches SVG); the filter names the exact message so any *other* error still fails.
            renderer_noise = "<svg> attribute viewBox: Unexpected end of attribute"
            errors = [e for e in console_errors(cdp) if renderer_noise not in e]
            checks.append(("the page logged no console errors (besides the renderer's svg warning)", not errors, f"errors={errors[:2]}"))

    return report(checks, gate="SETTINGS GATE")


if __name__ == "__main__":
    sys.exit(main())