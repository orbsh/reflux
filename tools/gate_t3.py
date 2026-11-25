#!/usr/bin/env python3
"""T3 gate — the profile's whole vocabulary draws, in one tree, and the DOM proves each type.

The renderer implements every accrete type, so what reflux owes is the closed set — every exposed
type is a legal node and reaches the page. The set itself is proven offline
(`tests/test_types_drawable.py`, one legal node per type, exactly the profile's list); this gate
draws them all at once.

How "each type drew" is measured: most components put a **role class** on their element (`frame`,
`tiles`, `entry`, `case`, `text`, `select`, …), read off the renderer. `panel` is asserted by
behaviour instead — an `inline` panel is a fold: it starts collapsed and its body appears on a
click — and `button` is asserted where it renders, inside its `loom`.

The asset-backed type stays out on purpose (`canvas` mounts an ES module): its capability is a
deployment artifact, not vocabulary. A stub module would prove the stub.

    python3 tools/gate_t3.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cdp import Cdp, console_errors, report, open_page  # noqa: E402
from reflux import wire  # noqa: E402
from reflux.application import App  # noqa: E402
from reflux.sdk import h  # noqa: E402
from reflux.sdk._parse import dump  # noqa: E402
from tests.types_fixture import ASSET_BACKED, NODES, text  # noqa: E402

PAGE = "/"
PANEL = "t3-panel"  # the fixture's id: an inline panel is only observable by clicking it open

# The renderer's own role classes, one per type that has one. `panel` and `button` are asserted by
# behaviour (see the docstring), so they are not here. A draggable or accepting `frame` is still a
# `frame`: cargo is an attribute of the box, not a type of its own.
ROLE: dict[str, str] = {
    "frame": ".frame",
    "forcegraph": ".fg-host",
    "loom": ".case",
    "svg": "svg",
    "path": "path",
    "tiles": ".tiles",
    "entry": ".entry",
    "image": "img",
    "input": "input",
    "select": ".select",
    "text": ".text",
}

PROBE = """(() => {
  const all = (sel) => Array.from(document.querySelectorAll(sel));
  const q = (sel) => document.querySelector(sel);
  const counts = {};
  %COUNTS%
  return {
    counts,
    text: (document.getElementById('main') || {}).innerText || '',
    src: q('img') && q('img').getAttribute('src'),
    d: q('.path') && q('.path').getAttribute('d'),
    input: q('input') && q('input').value,
    in_loom: all('.case input, .case textarea').length,
    options: all('.select > div').map((d) => d.innerText.trim()),
    selected: all('.select .selected').map((d) => d.innerText.trim()),
    head: all('.tiles-hcell').map((c) => c.innerText.trim()),
    rows: all('.tiles-row').length,
    buttons: all('.button').length,
    graph: (() => {
      const c = q('canvas');
      return c ? {w: c.width, h: c.height} : null;
    })(),
    style: (() => {
      const cs = (sel, prop) => { const el = q(sel); return el ? getComputedStyle(el)[prop] : null; };
      return {
        h1: cs('.rx-heading-1', 'fontSize'),
        h2: cs('.rx-heading-2', 'fontSize'),
        h3: cs('.rx-heading-3', 'fontSize'),
        plain: cs('.t3-plain', 'fontSize'),
        muted: cs('.rx-muted', 'color'),
        danger: cs('.rx-danger', 'color'),
        plainColor: cs('.t3-plain', 'color'),
        codeFont: cs('.rx-code', 'fontFamily'),
        cardBorder: cs('.rx-card', 'borderTopWidth'),
      };
    })(),
  };
})()"""


def tree() -> dict:
    """Every drawable type as one case's children; the button rides inside its loom (see fixture)."""
    kids = [
        node
        for tag, node in NODES.items()
        if tag not in ASSET_BACKED and tag != "button"  # `button` is the loom's child
    ]
    return {"type": "frame", "children": [*kids, {"type": "frame", "children": [tokens()]}]}


def tokens() -> dict:
    """A subtree that carries one node per declared variant — the token lane end to end.

    The producer writes the variant *name*; the SDK lowers it to the class; the stylesheet behind
    that class is what these checks read back as computed style.
    """
    return dump(
        h.frame(
            h.text("Heading one", variant="heading-1"),
            h.text("Heading two", variant="heading-2"),
            h.text("Heading three", variant="heading-3"),
            h.text("muted", variant="muted"),
            h.text("danger", variant="danger"),
            h.text("inline code", variant="code"),
            h.text("plain", id="t3-plain"),
            h.frame(h.text("card body"), variant="card"),
        )
    )


def seed_slots() -> list[dict]:
    """The two list slots the fixture binds to: the tiles' rows and the select's options."""
    return [
        wire.append("rows", text("row-from-slot", id="row-1")),
        wire.append("rows", text("row-from-slot", id="row-2")),  # two rows: the count is the point
        wire.append("opts", text("option-a", id="a")),
        wire.append("opts", text("option-b", id="b")),
    ]


def wait_for(cdp: Cdp, expression: str, timeout: float = 3.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cdp.eval(expression):
            return True
        time.sleep(0.05)
    return False


def main() -> int:
    app = App()
    checks: list[tuple[str, bool, str]] = []
    probe = PROBE.replace(
        "%COUNTS%", "\n  ".join(f"counts[{tag!r}] = all({sel!r}).length;" for tag, sel in ROLE.items())
    )

    with open_page(path=PAGE, app=app, settle=0.5) as (cdp, base):
        device = next(iter(app.live()), None)
        if device is None:
            print("no device: the page never connected")
            return 1

        device.send(wire.draw(*seed_slots(), wire.create(tree())))
        wait_for(cdp, "!!document.querySelector('.tiles')")
        cdp.drain()
        seen = json.loads(cdp.eval(f"JSON.stringify({probe})") or "{}")
        counts: dict[str, int] = seen.get("counts") or {}
        body: str = seen.get("text") or ""

        missing = [tag for tag, n in counts.items() if not n]
        checks.append(
            (
                "every class-bearing type draws its own element",
                not missing,
                f"missing={missing}" if missing else f"{len(counts)} role classes",
            )
        )

        # An inline `panel` is a fold: header (its `item`) plus a body that a click reveals. The
        # fixture has no `item`, so the header is blank on purpose — what it proves is the toggle.
        collapsed = "panel-body" not in body
        opened = False
        if collapsed:
            # A collapsed panel is an empty grid, so it has no box for a mouse event to land on:
            # the fold's own handler is what a press would call, so the gate calls it that way.
            cdp.eval(f"document.getElementById({PANEL!r}).click()")
            opened = wait_for(cdp, "'panel-body' && document.body.innerText.includes('panel-body')")
        checks.append(
            (
                "an inline panel starts collapsed and opens on a click",
                collapsed and opened,
                f"collapsed={collapsed} opened={opened}",
            )
        )

        checks.append(
            (
                "a loom registers itself — its submit button renders, with its fields",
                seen.get("buttons") == 1 and seen.get("in_loom") == 2,
                f"buttons={seen.get('buttons')} fields={seen.get('in_loom')}",
            )
        )
        checks.append(("an entry draws its named fields", "entry-field" in body, f"entry={'entry-field' in body}"))
        checks.append(("a leaf paints its bound value", "text" in body, f"text={'text' in body}"))
        # The graph is the one exposed type with no DOM id: its renderer is in the wasm, so the proof
        # is the canvas it mounts — nothing else in this tree can make one — plus a drawing buffer
        # that is not 0x0.
        graph = seen.get("graph") or {}
        checks.append(
            (
                "the native graph mounts a canvas with a real drawing buffer",
                bool(graph) and graph.get("w", 0) > 0 and graph.get("h", 0) > 0,
                f"canvas={graph}",
            )
        )

        checks.append(("image carries its src", seen.get("src") == "/static/logo.svg", f"src={seen.get('src')!r}"))
        checks.append(("path draws its d", seen.get("d") == "M0 0 L1 1", f"d={seen.get('d')!r}"))
        checks.append(
            (
                "select renders its options from a list slot and marks the bound one",
                seen.get("options") == ["option-a", "option-b"] and seen.get("selected") == ["option-a"],
                f"options={seen.get('options')} selected={seen.get('selected')}",
            )
        )
        checks.append(
            (
                "a tiles header names its fields, and its rows come from the list slot",
                seen.get("head") == ["Name", "qty"] and seen.get("rows") == 2,
                f"head={seen.get('head')} rows={seen.get('rows')}",
            )
        )
        # The renderer's truth, and the reason the profile no longer offers `default`/`source` for an
        # input: it starts from its js-kind default and only emits.
        checks.append(
            ("input starts from its js-kind default, not a binding", seen.get("input") == "", f"value={seen.get('input')!r}")
        )

        # The token lane: variant name → class → the stylesheet's rule, read as computed style.
        style = seen.get("style") or {}
        sizes = [style.get(key) for key in ("h1", "h2", "h3", "plain")]
        try:
            sizes = [float(str(px).replace("px", "")) for px in sizes]
        except (TypeError, ValueError):
            sizes = []
        checks.append(
            (
                "a heading variant is a real size step",
                len(sizes) == 4 and sizes[0] > sizes[1] > sizes[2] > sizes[3],
                f"h1/h2/h3/plain={[style.get(k) for k in ('h1', 'h2', 'h3', 'plain')]}",
            )
        )
        checks.append(
            (
                "muted and danger are colours of their own",
                bool(style.get("muted"))
                and style.get("muted") != style.get("plainColor")
                and style.get("danger") not in (None, style.get("plainColor")),
                f"muted={style.get('muted')} danger={style.get('danger')} plain={style.get('plainColor')}",
            )
        )
        checks.append(
            (
                "a code variant is monospace",
                "mono" in str(style.get("codeFont") or "").lower(),
                f"font-family={style.get('codeFont')}",
            )
        )
        checks.append(
            (
                "a card variant draws a frame",
                str(style.get("cardBorder")) not in ("0px", "None", ""),
                f"border-top-width={style.get('cardBorder')}",
            )
        )

        errors = console_errors(cdp)
        checks.append(("zero console errors", not errors, "none" if not errors else str(errors)))

    return report(checks, gate="T3 GATE")


if __name__ == "__main__":
    sys.exit(main())