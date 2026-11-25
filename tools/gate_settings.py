#!/usr/bin/env python3
"""Settings gate — core.css's whole token surface over a real browser, and the server remembering it.

The unit tests (`tests/test_settings.py`) own the server's half: unpacking the group, the whitelist, the
ranges, the throttled write, and the three tables agreeing. What only a browser can answer is the half
ADR 0001 decided: that `scope: both` writes locally, that fluxen mirrors the members onto the document
root as `data-*`, that `TOKENS` in `www/static/reflux.js` turns those into `:root` custom properties
(colours composed as `oklch` from `L C H`), that the palette's tiles set and show the choice, and that
the renderer's `sketch` member draws borders.

Controls are addressed by position within their kind (the renderer does not put a field node's `id` on
the DOM), and the orders are derived from `TOKENS` so a table that grows cannot silently move this gate
onto the wrong control.

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

# What the page draws, in order: the sketch switch, then one row per token in table order.
COLOURS = [name for name, kind in demo_settings.TOKENS.items() if kind == "color"]
LENGTHS = [name for name, kind in demo_settings.TOKENS.items() if kind == "length"]
SELECTS = [*COLOURS, *[name for name, kind in demo_settings.TOKENS.items() if kind == "keyword"]]
INPUTS = ["sketch", *LENGTHS]
CONTROLS = len(INPUTS) + len(SELECTS)

START = {"sketch": False, "accent": "0.7 0.12 200"}  # what the server already remembers (a palette tile)
PICKED = demo_settings.HUES[4]  # the tile this gate clicks for accent


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


def controls(cdp) -> int:
    """How many controls the page drew: inputs plus selects (a `select` is a list of tiles, not an input)."""
    return cdp.eval("document.querySelectorAll('#settings-page input, #settings-page .select').length") or 0


def set_field(cdp, name: str, value: str) -> bool:
    """Type into a text field and leave it, the way a person would.

    Not `el.value = x` + a synthetic `change`: the renderer listens for the events a person makes, and a
    dispatched `Event("change")` is not one of them. Focus, select, insert text, blur — the blur is what
    makes the browser fire a real `change`, which is the loom's timing here.
    """
    index = INPUTS.index(name)
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


def click_tile(cdp, name: str, index: int):
    """Click one tile of a token's palette — the option rows carry `as-stretch`; the last child is a layer."""
    select = SELECTS.index(name)
    return cdp.eval(
        "(() => {"
        f"const box = document.querySelectorAll('#settings-page .select')[{select}];"
        "if (!box) return null;"
        f"const tile = box.children[{index}];"  # the option rows are the box's children; a layer follows them
        "if (!tile) return null; tile.click(); return true;"
        "})()"
    )


def click_field(cdp, name: str):
    index = INPUTS.index(name)
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
            shown = controls(cdp)
            checks.append(
                (
                    "the page draws one control per token, plus the sketch switch",
                    drawn and shown == CONTROLS,
                    f"controls={shown} expected={CONTROLS}",
                )
            )

            # 1. the first frame carried the stored options, and the table turned them into a colour
            seeded = wait_for(lambda: root_attr(cdp, "accent") == START["accent"])
            checks.append(
                (
                    "the stored token reaches the first frame and becomes an oklch property",
                    bool(seeded) and custom(cdp, "accent") == f"oklch({START['accent']})",
                    f"data-accent={root_attr(cdp, 'accent')!r} --accent={custom(cdp, 'accent')!r}",
                )
            )

            # 2. the palette: one click, no round trip, and nothing else moves
            bg_before = custom(cdp, "bg")
            wrote = click_tile(cdp, "accent", demo_settings.HUES.index(PICKED))
            local = wait_for(lambda: custom(cdp, "accent") == f"oklch({PICKED})")
            checks.append(
                (
                    "a palette tile paints locally and moves nothing else",
                    bool(wrote and local) and custom(cdp, "bg") == bg_before,
                    f"data-accent={root_attr(cdp, 'accent')!r} --accent={custom(cdp, 'accent')!r}",
                )
            )

            # 3. a length: a number in, pixels out
            wrote_round = set_field(cdp, "round", "18")
            rounded = wait_for(lambda: custom(cdp, "round") == "18px")
            checks.append(
                (
                    "round moves (10 → 18) and becomes a length",
                    bool(wrote_round and rounded),
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

            # 4. the border style is picked from its own list of words
            click_tile(cdp, "border-style", demo_settings.KEYWORDS.index("dashed"))
            dashed = wait_for(lambda: custom(cdp, "border-style") == "dashed")
            checks.append(
                (
                    "the border style is a click, and it reaches :root",
                    bool(dashed) and root_attr(cdp, "border-style") == "dashed",
                    f"data-border-style={root_attr(cdp, 'border-style')!r} --border-style={custom(cdp, 'border-style')!r}",
                )
            )

            # 5. the derived tokens follow their members: --border is width, style and colour
            border, colour = custom(cdp, "border"), custom(cdp, "border-color")
            checks.append(
                (
                    "the composed --border follows the tokens it is built from",
                    "dashed" in border and colour == custom(cdp, "secondary"),
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
            waited = wait_for(lambda: demo_settings.settings.state.get("accent") == PICKED, timeout=4.0)
            state = dict(demo_settings.settings.state)
            checks.append(
                (
                    "the uplink reached the server and was merged",
                    bool(
                        waited
                        and state.get("round") == "18"
                        and state.get("border-style") == "dashed"
                        and state.get("sketch") is True
                    ),
                    f"state={state}",
                )
            )

            # A reload is a new document: the flag written before it is gone, so the wait below is waiting
            # on the *new* page, not on the old DOM that happened not to have changed yet.
            cdp.eval("window.__before_reload = true; location.reload(); true")
            fresh = wait_for(lambda: cdp.eval("window.__before_reload") is None, timeout=10.0)
            stayed = wait_for(lambda: custom(cdp, "accent") == f"oklch({PICKED})", timeout=8.0)
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