#!/usr/bin/env python3
"""Settings gate — core.css's settable token surface over a real browser, and the server remembering it.

The unit tests (`tests/test_settings.py`) own the server's half: unpacking the group, the whitelist, the
ranges, the throttled write, and the three tables agreeing. What only a browser can answer is the half
ADR 0001 decided: that `scope: both` writes locally, that fluxen mirrors the members onto the document
root as `data-*`, that `TOKENS` in `www/static/reflux.js` turns those into `:root` custom properties
(colours composed as `oklch` from `L C H`), that the colour field's panel sets and shows the choice — the three
sliders are oklch's three terms, and the shape of that control is what the renderer owns — and that the
renderer's `sketch` member draws borders.

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

# What the page draws, in order: the sketch switch, then one row per token in table order. The palette is six
# colour fields (a swatch with a panel behind it), form is three number boxes and a folded picker, and type is a
# number box plus a text box (the font stack) — the thirteen leaves `@layer options` names.
COLOURS = [name for name, kind in demo_settings.TOKENS.items() if kind == "color"]
LENGTHS = [name for name, kind in demo_settings.TOKENS.items() if kind == "length"]
FONTS = [name for name, kind in demo_settings.TOKENS.items() if kind == "font"]
SELECTS = [name for name, kind in demo_settings.TOKENS.items() if kind == "keyword"]
INPUTS = ["sketch", *LENGTHS, *FONTS]
CONTROLS = len(INPUTS) + len(SELECTS) + len(COLOURS)

START = {"sketch": False, "accent": "0.7 0.12 200"}  # what the server already remembers
# The three terms this gate types into the accent field's panel. Lightness moves too — the whole point of the
# panel is that the third axis is reachable from the page, which the disc could not do.
PICKED_LIGHT = 0.55
PICKED_CHROMA = 0.2
PICKED_HUE = 250.0
PICKED = f"{PICKED_LIGHT:.2f} {PICKED_CHROMA:.2f} {int(PICKED_HUE)}"  # what the field should pack


def wait_for(predicate, timeout: float = 6.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.03)
    return predicate()


def norm(triple: str) -> str:
    """A triple the way the server writes it back (`:g` on each term), so a comparison survives normalisation."""
    return " ".join(f"{float(term):g}" for term in triple.split())


def root_attr(cdp, name: str):
    return cdp.eval(f"document.documentElement.getAttribute('data-{name}')")


def custom(cdp, name: str) -> str:
    return cdp.eval(
        f"(getComputedStyle(document.documentElement).getPropertyValue('--{name}') || '').trim()"
    ) or ""


def controls(cdp) -> int:
    """How many controls the page drew: inputs plus selects (a `picker` is a list of tiles, not an input)."""
    return (
        cdp.eval("document.querySelectorAll('#settings-page input, #settings-page .picker, #settings-page .color').length")
        or 0
    )


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


def open_menu(cdp, name: str):
    """Open a folded picker: its face is a `.picker-trigger` and the rows only exist while it is open."""
    select = SELECTS.index(name)
    return cdp.eval(
        "(() => {"
        f"const box = document.querySelectorAll('#settings-page .picker')[{select}];"
        "if (!box) return null;"
        "const trigger = box.querySelector('.picker-trigger');"
        "if (!trigger) return null; trigger.click(); return true;"
        "})()"
    )


def click_tile(cdp, name: str, index: int):
    """Click one row of an open menu — the rows are the `.picker-menu`'s children."""
    select = SELECTS.index(name)
    return cdp.eval(
        "(() => {"
        f"const box = document.querySelectorAll('#settings-page .picker')[{select}];"
        "if (!box) return null;"
        "const menu = box.querySelector('.picker-menu');"
        "if (!menu) return null;"
        f"const tile = menu.querySelectorAll('.as-stretch')[{index}];"
        "if (!tile) return null; tile.click(); return true;"
        "})()"
    )


def set_color(cdp, name: str, light: float, chroma: float, hue: float):
    """Open the field's panel and type the three terms into it (ADR 0052).

    The panel is what the field is now: a swatch and a literal in the row, three sliders behind it. Typing the
    number boxes is the same write a drag makes (both go through one path), and it is exact — no pixel-rounding
    to allow for. The panel is closed again on the way out, so its click-outside layer does not sit over the
    controls the rest of this gate drives.
    """
    index = COLOURS.index(name)
    opened = cdp.eval(
        "(() => {"
        f"const el = document.querySelectorAll('#settings-page .color')[{index}];"
        "if (!el) return null;"
        "el.click();"
        "return true;"
        "})()"
    )
    if not opened:
        return None
    # The panel is a reactive node: it lands a beat after the click, not inside it.
    ready = wait_for(
        lambda: bool(
            cdp.eval(
                "(() => {"
                f"const el = document.querySelectorAll('#settings-page .color')[{index}];"
                "return !!(el && el.querySelector('.color-panel'));"
                "})()"
            )
        )
    )
    if not ready:
        return None
    return cdp.eval(
        "(() => {"
        f"const el = document.querySelectorAll('#settings-page .color')[{index}];"
        "const panel = el && el.querySelector('.color-panel');"
        "if (!panel) return null;"
        "const boxes = panel.querySelectorAll('input[type=number]');"
        f"const want = [{light}, {chroma}, {hue}];"
        "for (let k = 0; k < 3 && k < boxes.length; k++) {"
        "boxes[k].value = String(want[k]);"
        "boxes[k].dispatchEvent(new Event('input', {bubbles: true}));"
        "}"
        # Close it again: an open panel adds six inputs to the page, and the checks below address the
        # remaining controls by position within their kind.
        "panel.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));"
        "return true;"
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

            # 2. the colour field: three terms in, the whole triple out, and nothing else moves. Lightness is
            #    one of the three — reaching it is the reason the panel replaced the disc.
            bg_before = custom(cdp, "bg")
            wrote = set_color(cdp, "accent", PICKED_LIGHT, PICKED_CHROMA, PICKED_HUE)
            local = wait_for(lambda: root_attr(cdp, "accent") == PICKED)
            picked = root_attr(cdp, "accent") or ""
            checks.append(
                (
                    "the panel packs the exact triple it was given, lightness included",
                    bool(wrote and local)
                    and custom(cdp, "accent") == f"oklch({norm(picked)})"  # Chromium writes the property back normalised
                    and custom(cdp, "bg") == bg_before,
                    f"data-accent={picked!r} --accent={custom(cdp, 'accent')!r} asked={PICKED!r}",
                )
            )

            # 2b. every colour uses the same field, and a chroma of zero is the grey axis
            greyed = set_color(cdp, "secondary", 1.0, 0.0, 0.0)
            neutral = wait_for(lambda: (root_attr(cdp, "secondary") or "").split()[1:2] in (["0"], ["0.00"]))
            grey = root_attr(cdp, "secondary") or ""
            checks.append(
                (
                    "a chroma of zero is grey — a neutral token is reached through the same panel",
                    bool(greyed and neutral) and float(grey.split()[1]) == 0.0 and custom(cdp, "secondary") == f"oklch({norm(grey)})",
                    f"data-secondary={grey!r} --secondary={custom(cdp, 'secondary')!r}",
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

            # 4. the border style is a folded picker: the page holds the word in force, a click opens the five,
            #    and choosing one closes it again (ADR 0049)
            opened = open_menu(cdp, "border-style")
            shown = cdp.eval("document.querySelectorAll('#settings-page .picker-menu').length") or 0
            click_tile(cdp, "border-style", demo_settings.KEYWORDS.index("dashed"))
            dashed = wait_for(lambda: custom(cdp, "border-style") == "dashed")
            closed = wait_for(lambda: (cdp.eval("document.querySelectorAll('#settings-page .picker-menu').length") or 0) == 0)
            checks.append(
                (
                    "a folded picker opens, takes a word, closes, and the word reaches :root",
                    bool(opened) and shown == 1 and bool(dashed) and bool(closed)
                    and root_attr(cdp, "border-style") == "dashed",
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

            # 5b. type reaches :root: the size is a length, the stack is one text value
            typed = set_field(cdp, "font-size", "24")
            sized = wait_for(lambda: custom(cdp, "font-size") == "24px")
            stacked = set_field(cdp, "font-family", '"Courier New", monospace')
            faced = wait_for(lambda: '"Courier New"' in custom(cdp, "font-family"))
            reads = cdp.eval("getComputedStyle(document.documentElement).fontSize") or ""
            checks.append(
                (
                    "the type knobs reach :root — size as a length, the stack as one value",
                    bool(typed and sized and stacked and faced) and reads == "24px",
                    f"--font-size={custom(cdp, 'font-size')!r} --font-family={custom(cdp, 'font-family')!r} root={reads!r}",
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

            # 6b. the skin answers the same box with the pen: the fold is a box in both modes — drawn edge
            #     and drawn shadow under the skin, painted edge and soft shadow without it
            opened_skin = open_menu(cdp, "border-style")
            drawn = wait_for(
                lambda: cdp.eval(
                    "(() => {const m = document.querySelector('#settings-page .picker-menu');"
                    "if (!m) return ''; return (m.getAttribute('data-rough') || '-') + '|' + m.querySelectorAll('svg.rough').length;})()"
                )
                == "ready|1"
            )
            edge = cdp.eval(
                "(() => {const m = document.querySelector('#settings-page .picker-menu');"
                "if (!m) return null; const cs = getComputedStyle(m);"
                "return cs.borderTopColor + '|' + cs.backgroundColor + '|' + getComputedStyle(document.body).backgroundColor;})()"
            ) or ""
            from_skin = "rgba(0, 0, 0, 0)" in edge or "transparent" in edge
            same_panel = edge.split("|")[1:2] == edge.split("|")[2:3]  # the skin paints no panel: the page shows through
            dismissed = cdp.eval(
                "(() => {const s = document.querySelector('#settings-page .picker-scrim'); if (!s) return false;"
                " s.click(); return true;})()"
            )
            shut = wait_for(lambda: (cdp.eval("document.querySelectorAll('#settings-page .picker-menu').length") or 0) == 0)
            checks.append(
                (
                    "under the skin the fold is drawn, not painted",
                    bool(opened_skin) and bool(drawn) and from_skin and same_panel and bool(dismissed) and bool(shut),
                    f"drawn={bool(drawn)} edge={edge!r}",
                )
            )

            # 7. the server took the same changes (the throttle window has closed by now)
            waited = wait_for(lambda: demo_settings.settings.state.get("accent") == norm(picked), timeout=4.0)
            state = dict(demo_settings.settings.state)
            checks.append(
                (
                    "the uplink reached the server and was merged",
                    bool(
                        waited
                        and state.get("secondary") == norm(grey)
                        and state.get("round") == "18"
                        and state.get("border-style") == "dashed"
                        and state.get("font-size") == "24"
                        and state.get("font-family") == '"Courier New", monospace'
                        and state.get("sketch") is True
                    ),
                    f"state={state}",
                )
            )

            # A reload is a new document: the flag written before it is gone, so the wait below is waiting
            # on the *new* page, not on the old DOM that happened not to have changed yet.
            cdp.eval("window.__before_reload = true; location.reload(); true")
            fresh = wait_for(lambda: cdp.eval("window.__before_reload") is None, timeout=10.0)
            stayed = wait_for(lambda: custom(cdp, "accent") == f"oklch({norm(picked)})", timeout=8.0)
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