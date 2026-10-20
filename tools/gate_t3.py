#!/usr/bin/env python3
"""T3 gate — the profile's whole vocabulary draws, in one tree, and the DOM proves each type.

The renderer implements all 30 accrete types, so what reflux owes is the closed set — every exposed
type is a legal node and reaches the page. The set itself is proven offline
(`tests/test_types_drawable.py`, one legal node per type, exactly the profile's list); this gate
draws them all at once.

How "each type drew" is measured: every component puts a **role class** on its element (`case`,
`rack`, `pages`, `txt`, `select`, …), read off the renderer. Four types have no class of their own
and are asserted by behaviour instead — a `fold`'s header is its `item[0]` while its body stays
collapsed, a `form` is the only place a `button` renders, and a `portal` mounts its children into
the element its `attrs.to` names.

Asset-backed types stay out on purpose (`canvas` / `chart` / `editor` mount an ES module, `diagram`
fetches mermaid): their capability is a deployment artifact, not vocabulary. A stub module would
prove the stub.

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
from reflux.app import App  # noqa: E402
from reflux.sdk import builders as b  # noqa: E402
from reflux.sdk._parse import dump  # noqa: E402
from tests.types_fixture import ASSET_BACKED, NODES, text  # noqa: E402

PAGE = "/"

# The renderer's own role classes, one per type that has one. `fold`/`form`/`portal`/`button` are
# asserted by behaviour (see the docstring), so they are not here.
ROLE: dict[str, str] = {
    "case": ".case",
    "placeholder": ".placeholder",
    "float": ".float",
    "layer": ".layer",
    "popup": ".popup",
    "svg": ".svg",
    "group": ".group",
    "path": ".path",
    "rack": ".rack",
    "pages": ".pages",
    "image": "img",
    "input": "input",
    "select": ".select",
    "table": "table",
    "thead": "thead",
    "tbody": "tbody",
    "tr": "tr",
    "th": "th",
    "td": "td",
    "text": ".txt",
    "textarea": "textarea",
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
    textarea: q('textarea') && q('textarea').value,
    options: all('.select > div').map((d) => d.innerText.trim()),
    selected: all('.select .selected').map((d) => d.innerText.trim()),
    cells: all('table th, table td').map((c) => c.innerText.trim()),
    rack: all('.rack *').map((r) => r.innerText.trim()).filter(Boolean),
    pages: q('.pages') ? q('.pages').innerText.trim() : null,
    buttons: all('.button').length,
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
    """Every drawable type as one case's children; the button rides inside the form (see fixture)."""
    kids = [
        node
        for tag, node in NODES.items()
        if tag not in ASSET_BACKED and tag != "button"  # `button` is the form's child
    ]
    return {"type": "case", "children": [*kids, {"type": "case", "children": [tokens()]}]}


def tokens() -> dict:
    """A subtree that carries one node per declared variant — the token lane end to end.

    The producer writes the variant *name*; the SDK lowers it to the class; the stylesheet behind
    that class is what these checks read back as computed style.
    """
    return dump(
        b.case(
            b.text("Heading one", variant="heading-1"),
            b.text("Heading two", variant="heading-2"),
            b.text("Heading three", variant="heading-3"),
            b.text("muted", variant="muted"),
            b.text("danger", variant="danger"),
            b.text("inline code", variant="code"),
            b.text("plain", id="t3-plain"),
            b.case(b.text("card body"), variant="card"),
        )
    )


def seed_slots() -> list[dict]:
    """The three list slots the fixture binds to: rack rows, select options, pages rows."""
    return [
        wire.append("rows", text("row-from-slot", id="row-1")),
        wire.append("rows", text("row-from-slot", id="row-2")),  # two rows: the count is the point
        wire.append("opts", text("option-a", id="a")),
        wire.append("opts", text("option-b", id="b")),
        wire.append("sel", text("page-one", id="a")),
        wire.inject("pages-key", "a"),  # the pages key: vals plane, read through `path: "/data"`
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
        session = next(iter(app.live()), None)
        if session is None:
            print("no session: the page never connected")
            return 1

        session.send(wire.draw(session.id, *seed_slots(), wire.create(tree())))
        wait_for(cdp, "!!document.querySelector('.rack')")
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

        checks.append(
            (
                "a fold shows its item as the header and keeps its body collapsed",
                "fold" in body and "fold-body" not in body,
                f"header={'fold' in body} body_hidden={'fold-body' not in body}",
            )
        )
        checks.append(
            (
                "a form registers itself — its submit button renders",
                seen.get("buttons") == 1,
                f"buttons={seen.get('buttons')}",
            )
        )
        checks.append(("a portal mounts its children into the named target", "portal" in body, "portal" if "portal" in body else "missing"))
        checks.append(("a leaf paints its bound value", "text" in body, f"text={'text' in body}"))

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
            ("the table family renders its cells", seen.get("cells") == ["head", "cell"], f"cells={seen.get('cells')}")
        )
        checks.append(
            (
                # A rack renders its `item` template once per row of the bound list slot.
                "rack renders its item once per row of the list slot",
                (seen.get("rack") or []) == ["row", "row"],
                f"rack={seen.get('rack')}",
            )
        )
        checks.append(
            ("pages renders the selected page", "page-one" in (seen.get("pages") or ""), f"pages={seen.get('pages')!r}")
        )
        checks.append(
            (
                "textarea carries its bound default",
                seen.get("textarea") == "textarea",
                f"value={seen.get('textarea')!r}",
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