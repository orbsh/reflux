#!/usr/bin/env python3
"""Settings gate — core.css's whole token surface over a real browser, and the server remembering it.

The unit tests (`tests/test_settings.py`) own the server's half: unpacking the group, the whitelist, the
ranges, the throttled write, and the three tables agreeing. What only a browser can answer is the half
ADR 0001 decided: that `scope: both` writes locally, that fluxen mirrors the members onto the document
root as `data-*`, that `TOKENS` in `www/static/reflux.js` turns those into `:root` custom properties
(colours composed as `oklch` from `L C H`), that the disc's face sets and shows the choice — its angle and
radius are two of oklch's three terms, and the shape of the click is what the renderer owns — and that the
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

# What the page draws, in order: the sketch switch, then one row per token in table order. Every colour is a
# disc in the oklch plane, and the border style is a row of words.
COLOURS = [name for name, kind in demo_settings.TOKENS.items() if kind == "color"]
LENGTHS = [name for name, kind in demo_settings.TOKENS.items() if kind == "length"]
SELECTS = [name for name, kind in demo_settings.TOKENS.items() if kind == "keyword"]
INPUTS = ["sketch", *LENGTHS]
CONTROLS = len(INPUTS) + len(SELECTS) + len(COLOURS)

START = {"sketch": False, "accent": "0.7 0.12 200"}  # what the server already remembers
PICKED_HUE = 250.0  # the angle this gate clicks on the accent disc
PICKED_CHROMA = 0.2  # half way to the rim, so the value is exactly representable
LIGHT = demo_settings.LIGHT["accent"]
PICKED = f"{LIGHT} {PICKED_CHROMA:.2f} {int(PICKED_HUE)}"  # what the disc should pack
GREY = f"{demo_settings.LIGHT['bg']} 0.00"  # a click on bg's centre: the grey axis


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
    """How many controls the page drew: inputs plus selects (a `select` is a list of tiles, not an input)."""
    return (
        cdp.eval("document.querySelectorAll('#settings-page input, #settings-page .select, #settings-page .disc').length")
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
    """Open a folded select: its face is a `.select-trigger` and the rows only exist while it is open."""
    select = SELECTS.index(name)
    return cdp.eval(
        "(() => {"
        f"const box = document.querySelectorAll('#settings-page .select')[{select}];"
        "if (!box) return null;"
        "const trigger = box.querySelector('.select-trigger');"
        "if (!trigger) return null; trigger.click(); return true;"
        "})()"
    )


def click_tile(cdp, name: str, index: int):
    """Click one row of an open menu — the rows are the `.select-menu`'s children."""
    select = SELECTS.index(name)
    return cdp.eval(
        "(() => {"
        f"const box = document.querySelectorAll('#settings-page .select')[{select}];"
        "if (!box) return null;"
        "const menu = box.querySelector('.select-menu');"
        "if (!menu) return null;"
        f"const tile = menu.querySelectorAll('.as-stretch')[{index}];"
        "if (!tile) return null; tile.click(); return true;"
        "})()"
    )


def click_disc(cdp, name: str, hue: float, chroma: float):
    """Click the disc at (hue, chroma): a real MouseEvent at that point, so the widget's own maths runs.

    The face is polar — the angle is the hue, the radius the chroma — and the rim is the validator's cap
    (0.4), so `chroma / 0.4` of the radius is where that chroma sits.
    """
    disc = COLOURS.index(name)
    return cdp.eval(
        "(() => {"
        f"const el = document.querySelectorAll('#settings-page .disc')[{disc}];"
        "if (!el) return null;"
        "const r = el.getBoundingClientRect();"
        f"const rad = ({hue} - 90) * Math.PI / 180;"
        f"const reach = ({chroma} / 0.4) * (r.width / 2);"
        "const x = r.left + r.width / 2 + Math.cos(rad) * reach;"
        "const y = r.top + r.height / 2 + Math.sin(rad) * reach;"
        "el.dispatchEvent(new MouseEvent('click', {clientX: x, clientY: y, bubbles: true}));"
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

            # 2. the disc: a point in, the whole triple out, and nothing else moves. The angle the widget
            #    computes is the angle of the point the browser reported, so it lands within a degree of the
            #    one asked for — that is the claim, not an exact equality.
            bg_before = custom(cdp, "bg")
            wrote = click_disc(cdp, "accent", PICKED_HUE, PICKED_CHROMA)
            local = wait_for(lambda: len((root_attr(cdp, "accent") or "").split()) == 3)
            picked = root_attr(cdp, "accent") or ""
            parts = picked.split()
            # A pixel is 1/64 of the radius, i.e. ~0.006 of chroma, and the browser reports whole pixels: the
            # point lands within a couple of hundredths, not exactly on the request.
            near = (
                len(parts) == 3
                and abs(int(parts[2]) - int(PICKED_HUE)) <= 1
                and abs(float(parts[1]) - PICKED_CHROMA) <= 0.02
            )
            checks.append(
                (
                    "a disc click packs the triple its light and its point name",
                    bool(wrote and local and near)
                    and custom(cdp, "accent") == f"oklch({norm(picked)})"  # Chromium writes the property back normalised
                    and custom(cdp, "bg") == bg_before,
                    f"data-accent={picked!r} --accent={custom(cdp, 'accent')!r} asked={PICKED_HUE}/{PICKED_CHROMA}",
                )
            )

            # 2b. every token uses the same disc, so a token whose default is grey gets its grey from the centre
            greyed = click_disc(cdp, "bg", PICKED_HUE, 0.0)
            neutral = wait_for(lambda: (root_attr(cdp, "bg") or "").split()[1:2] in (["0"], ["0.00"]))
            grey = root_attr(cdp, "bg") or ""
            checks.append(
                (
                    "the centre of a disc is grey — a neutral token is reached there too",
                    bool(greyed and neutral) and float(grey.split()[1]) == 0.0 and custom(cdp, "bg") == f"oklch({norm(grey)})",
                    f"data-bg={grey!r} --bg={custom(cdp, 'bg')!r}",
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

            # 4. the border style is a folded select: the page holds the word in force, a click opens the five,
            #    and choosing one closes it again (ADR 0049)
            opened = open_menu(cdp, "border-style")
            shown = cdp.eval("document.querySelectorAll('#settings-page .select-menu').length") or 0
            click_tile(cdp, "border-style", demo_settings.KEYWORDS.index("dashed"))
            dashed = wait_for(lambda: custom(cdp, "border-style") == "dashed")
            closed = wait_for(lambda: (cdp.eval("document.querySelectorAll('#settings-page .select-menu').length") or 0) == 0)
            checks.append(
                (
                    "a folded select opens, takes a word, closes, and the word reaches :root",
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
                    "(() => {const m = document.querySelector('#settings-page .select-menu');"
                    "if (!m) return ''; return (m.getAttribute('data-rough') || '-') + '|' + m.querySelectorAll('svg.rough').length;})()"
                )
                == "ready|1"
            )
            edge = cdp.eval(
                "(() => {const m = document.querySelector('#settings-page .select-menu');"
                "if (!m) return null; const cs = getComputedStyle(m);"
                "return cs.borderTopColor + '|' + cs.backgroundColor + '|' + getComputedStyle(document.body).backgroundColor;})()"
            ) or ""
            from_skin = "rgba(0, 0, 0, 0)" in edge or "transparent" in edge
            same_panel = edge.split("|")[1:2] == edge.split("|")[2:3]  # the skin paints no panel: the page shows through
            dismissed = cdp.eval(
                "(() => {const s = document.querySelector('#settings-page .select-scrim'); if (!s) return false;"
                " s.click(); return true;})()"
            )
            shut = wait_for(lambda: (cdp.eval("document.querySelectorAll('#settings-page .select-menu').length") or 0) == 0)
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
                        and state.get("bg") == norm(grey)
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