#!/usr/bin/env python3
"""Settings gate — core.css's whole token surface over a real browser, and the server remembering it.

The unit tests (`tests/test_settings.py`) own the server's half: unpacking the group, the whitelist, the
ranges, the throttled write, and the three tables agreeing. What only a browser can answer is the half
ADR 0001 decided: that `scope: both` writes locally, that fluxen mirrors the members onto the document
root as `data-*`, that `TOKENS` in `www/static/reflux.js` turns those into `:root` custom properties
(colours composed as `oklch` from `L C H`), that clearing a field hands the token back to the stylesheet,
and that the renderer's `sketch` member draws borders.

The fields are addressed by the order `TOKENS` declares, not by an index typed in here: the renderer does
not put a field node's `id` on the DOM, and a table that grows must not silently move the gate onto the
wrong control.

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

# The page draws the sketch switch first, then one row per token in table order.
ORDER = ["sketch", *demo_settings.TOKENS]
START = {"sketch": False, "accent": "0.7 0.12 182.49"}  # what the server already remembers
CORE_ACCENT = "oklch(0.7 0.12 182.49)"  # core.css's own --accent, for "clearing restores it"


def index_of(name: str) -> int:
    return ORDER.index(name)


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
    """The settings group's fields, in the order the page declares them."""
    return cdp.eval(
        "[...document.querySelectorAll('#settings-page input')].map(e => [e.type, e.value])"
    ) or []


def set_field(cdp, name: str, value: str) -> bool:
    """Type into a field and leave it, the way a person would.

    Not `el.value = x` + a synthetic `change`: the renderer listens for the events a person makes, and a
    dispatched `Event("change")` is not one of them. Focus, select, insert text, blur — the blur is what
    makes the browser fire a real `change`, which is the loom's timing here.
    """
    index = index_of(name)
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


def clear_field(cdp, name: str) -> bool:
    """Empty a field (select-all, delete, leave) — "not set", not "zero"."""
    index = index_of(name)
    cdp.eval(
        "(() => {"
        f"const el = document.querySelectorAll('#settings-page input')[{index}];"
        "if (!el) return false; el.focus(); el.select(); return true;"
        "})()"
    )
    cdp.call(
        "Input.dispatchKeyEvent", type="keyDown", key="Backspace", windowsVirtualKeyCode=8, nativeVirtualKeyCode=8
    )
    cdp.call(
        "Input.dispatchKeyEvent", type="keyUp", key="Backspace", windowsVirtualKeyCode=8, nativeVirtualKeyCode=8
    )
    cdp.eval("document.activeElement && document.activeElement.blur()")
    return True


def press(cdp, name: str, code: int) -> None:
    cdp.call("Input.dispatchKeyEvent", type="keyDown", key=name, windowsVirtualKeyCode=code, nativeVirtualKeyCode=code)
    cdp.call("Input.dispatchKeyEvent", type="keyUp", key=name, windowsVirtualKeyCode=code, nativeVirtualKeyCode=code)


def step_field(cdp, name: str, target: int) -> bool:
    """Nudge a number field with ArrowUp until it reads `target`.

    Typing into it is not usable from here: a number input has no selectable caret (`select()` is a no-op,
    the caret sits at 0), so keystrokes prepend. The arrow keys are the field's own increment, and a person's
    hand on the same control does the same thing.
    """
    index = index_of(name)
    cdp.eval(f"document.querySelectorAll('#settings-page input')[{index}].focus()")
    for _ in range(40):
        try:
            current = float(cdp.eval(f"document.querySelectorAll('#settings-page input')[{index}].value"))
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


def click_field(cdp, name: str):
    index = index_of(name)
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
        demo_settings.settings.state = dict(START)
        app = example.app

        with open_page(app=app, path=PAGE, settle=0.7) as (cdp, base):
            drawn = wait_for(lambda: "设置" in (cdp.eval("document.body.innerText") or ""))
            fields = len(inputs(cdp))
            checks.append(
                (
                    "the page draws one field per token, plus the sketch switch",
                    drawn and fields == len(ORDER),
                    f"fields={fields} expected={len(ORDER)}",
                )
            )

            # 1. the first frame carried the stored options, and the table turned them into a colour
            seeded = wait_for(lambda: root_attr(cdp, "accent") == START["accent"])
            checks.append(
                (
                    "the stored token reaches the first frame and becomes an oklch property",
                    bool(seeded) and custom(cdp, "accent") == CORE_ACCENT,
                    f"data-accent={root_attr(cdp, 'accent')!r} --accent={custom(cdp, 'accent')!r}",
                )
            )

            # 2. local write, no round trip: a new triple paints at once
            wrote = set_field(cdp, "accent", "0.62 0.15 40")
            local = wait_for(lambda: custom(cdp, "accent") == "oklch(0.62 0.15 40)")
            checks.append(
                (
                    "a colour typed as L C H is composed to oklch locally",
                    bool(wrote and local),
                    f"data-accent={root_attr(cdp, 'accent')!r} --accent={custom(cdp, 'accent')!r}",
                )
            )

            # 3. a length: a number in, pixels out
            stepped = set_field(cdp, "round", "18")
            rounded = wait_for(lambda: custom(cdp, "round") == "18px")
            checks.append(
                (
                    "round moves (10 → 18) and becomes a length",
                    bool(stepped and rounded),
                    f"--round={custom(cdp, 'round')!r} data-round={root_attr(cdp, 'round')!r}",
                )
            )

            # 3b. the table has its own checks: a value it does not understand **drops the property**,
            # which hands the look back to the stylesheet's `:root` default — it does not guess.
            cdp.eval("document.documentElement.setAttribute('data-round', '99.5')")
            time.sleep(0.25)
            dropped = custom(cdp, "round")
            cdp.eval("document.documentElement.setAttribute('data-round', '18')")
            checks.append(
                (
                    "a length out of range is refused and the stylesheet shows through",
                    dropped == "10px",
                    f"--round={dropped!r} for 99.5 (core.css default 10px)",
                )
            )

            # 4. clearing a field is "not set": the member goes away and core's own value returns
            set_field(cdp, "warn", "0.8 0.1 90")
            wait_for(lambda: custom(cdp, "warn") == "oklch(0.8 0.1 90)")
            clear_field(cdp, "warn")
            cleared = wait_for(lambda: not (root_attr(cdp, "warn") or "").strip())
            checks.append(
                (
                    "clearing a field hands the token back to core.css",
                    bool(cleared) and custom(cdp, "warn") == "oklch(0.84 0.12 92.82)",
                    f"data-warn={root_attr(cdp, 'warn')!r} --warn={custom(cdp, 'warn')!r}",
                )
            )

            # 5. the derived tokens follow their members: --border is width, style and colour
            border, colour = custom(cdp, "border"), custom(cdp, "border-color")
            checks.append(
                (
                    "the composed --border follows the tokens it is built from",
                    "solid" in border and colour == custom(cdp, "secondary"),
                    f"--border={border!r} --border-color={colour!r} secondary={custom(cdp, 'secondary')!r}",
                )
            )

            # 6. sketch is the renderer's member: the mirror moves, the browser draws borders
            toggled = click_field(cdp, "sketch")
            mirrored = wait_for(lambda: root_attr(cdp, "sketch") == "true")
            checks.append(
                (
                    "sketch is mirrored for the renderer",
                    bool(toggled and mirrored),
                    f"data-sketch={root_attr(cdp, 'sketch')!r}",
                )
            )

            # 7. the server took the same changes (the throttle window has closed by now)
            waited = wait_for(lambda: demo_settings.settings.state.get("accent") == "0.62 0.15 40", timeout=4.0)
            state = dict(demo_settings.settings.state)
            checks.append(
                (
                    "the uplink reached the server and was merged",
                    bool(waited and state.get("round") == "18" and state.get("sketch") is True and "warn" not in state),
                    f"state={state}",
                )
            )

            # A reload is a new document: the flag written before it is gone, so the wait below is waiting
            # on the *new* page, not on the old DOM that happened not to have changed yet.
            cdp.eval("window.__before_reload = true; location.reload(); true")
            fresh = wait_for(lambda: cdp.eval("window.__before_reload") is None, timeout=10.0)
            stayed = wait_for(lambda: custom(cdp, "accent") == "oklch(0.62 0.15 40)", timeout=8.0)
            checks.append(
                (
                    "a reload shows the stored tokens again",
                    bool(fresh and stayed),
                    f"fresh={fresh} --accent={custom(cdp, 'accent')!r} data-round={root_attr(cdp, 'round')!r}",
                )
            )

            # The renderer's check icon for a bool field is an `<svg>` with an empty `viewBox`, and Chromium
            # logs one error per render. That is fluxen's, not this page's (nothing here touches SVG); the
            # filter names the exact message so any *other* error still fails.
            renderer_noise = "<svg> attribute viewBox: Unexpected end of attribute"
            errors = [e for e in console_errors(cdp) if renderer_noise not in e]
            checks.append(
                ("the page logged no console errors (besides the renderer's svg warning)", not errors, f"errors={errors[:2]}")
            )

    return report(checks, gate="SETTINGS GATE")


if __name__ == "__main__":
    sys.exit(main())