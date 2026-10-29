#!/usr/bin/env python3
"""T2 gate — accrete's eight actions land on the renderer, one check per action.

Does the wire layer (`reflux/wire.py`) produce frames the renderer accepts, and does each action do
what the four planes say it does? The gate plays the producer: `App` has no page hook, so the gate
sends its own frames through `wire` and reads the DOM.

Checks: create draws · tmpl expands · set replaces a slot · append lands at the tail · append `+1` lands
before the last · remove drops by identity · patch `replace` · patch `append` · inject writes the vals
plane · an out-of-range position is refused (not clamped) · empty is a no-op inside a frame that still
lands · zero console errors.

    python3 tools/gate_t2.py
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

PAGE = "/"

# A body the tmpl op registers: `{{label}}` is the only template language there is (ADR 0006).
TEMPLATE_BODY = (
    '{"type":"text","bind":{"value":{"kind":"default","default":"{{label}}"}}}'
)


def local_text(slot: str, *, id: str):
    """A `text` bound to the vals plane.

    The reader takes `path: "/data"` because the vals slot holds the Outflow-shaped wrapper an
    in-page `local` emit writes, so the payload itself is one level in. This used to be hand-built —
    `local` was exposed on `fold`/`pages` only, so the `text` reader had no keyword for it.
    """
    return b.text(local=slot, path="/data", id=id)


def tree():
    return b.case(
        b.text(source="echo", id="echo"),          # the data-slot reader (set / patch)
        b.rack(source="rows", id="rows"),          # the list slot (append / remove)
        local_text("chan", id="local-echo"),       # the vals plane (inject)
        {"type": "template", "name": "t1", "data": {"label": "expanded"}},
        id="root",
    )


def wait(predicate, timeout: float = 10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        got = predicate()
        if got:
            return got
        time.sleep(0.05)
    return None


def text_of(cdp: Cdp, cls: str) -> str:
    """A `text` node found by its id-as-class (`text`/`case` put the id into the class list)."""
    return (
        cdp.eval(
            f"(document.getElementsByClassName({json.dumps(cls)})[0]||{{}}).innerText"
        )
        or ""
    ).strip()


def rows(cdp: Cdp) -> list[str]:
    text = cdp.eval("(document.getElementById('rows')||{}).innerText") or ""
    return [line.strip() for line in text.splitlines() if line.strip()]


def main() -> int:
    app = App()
    checks: list[tuple[str, bool, str]] = []

    with open_page(path=PAGE, app=app, settle=0.4) as (cdp, base):
        session = wait(lambda: next(iter(app.live()), None))
        if session is None:
            print("no session: the page never connected")
            return 1

        def send(*ops) -> None:
            session.send(wire.draw(*ops))

        # tmpl first: a template node expands when the tree lands, so the body must be registered
        send(wire.tmpl("t1", TEMPLATE_BODY), wire.create(tree()))
        drawn = wait(lambda: cdp.eval("!!document.getElementsByClassName('root').length"))
        checks.append(("create draws the layout root", bool(drawn), "root present" if drawn else "root missing"))

        expanded = wait(lambda: "expanded" in (cdp.eval("document.body.innerText") or ""))
        checks.append(("tmpl expands {{label}} inside create", bool(expanded), "expanded" if expanded else "not expanded"))

        send(wire.set("echo", b.text("set-value")))
        ok = wait(lambda: text_of(cdp, "echo") == "set-value")
        checks.append(("set replaces the node in a data slot", bool(ok), f"echo={text_of(cdp, 'echo')!r}"))

        send(wire.append("rows", b.text("row-1", id="row-1")))
        send(wire.append("rows", b.text("row-3", id="row-3")))
        ok = wait(lambda: rows(cdp) == ["row-1", "row-3"])
        checks.append(("append lands at the tail", bool(ok), f"rows={rows(cdp)}"))

        send(wire.append("rows", b.text("row-2", id="row-2"), position=1))
        ok = wait(lambda: rows(cdp) == ["row-1", "row-2", "row-3"])
        checks.append(("append +1 lands before the last row", bool(ok), f"rows={rows(cdp)}"))

        send(wire.remove("rows", "row-2"))
        ok = wait(lambda: rows(cdp) == ["row-1", "row-3"])
        checks.append(("remove drops the row by identity", bool(ok), f"rows={rows(cdp)}"))

        send(wire.patch("echo", "/bind/value/default", "patched"))
        ok = wait(lambda: text_of(cdp, "echo") == "patched")
        checks.append(("patch replace rewrites the pointed value", bool(ok), f"echo={text_of(cdp, 'echo')!r}"))

        send(wire.patch("echo", "/bind/value/default", "!", op="append"))
        ok = wait(lambda: text_of(cdp, "echo") == "patched!")
        checks.append(("patch append extends a string", bool(ok), f"echo={text_of(cdp, 'echo')!r}"))

        send(wire.inject("chan", "injected"))
        ok = wait(lambda: text_of(cdp, "local-echo") == "injected")
        checks.append(("inject writes the vals plane", bool(ok), f"local-echo={text_of(cdp, 'local-echo')!r}"))

        # Out of range is refused, never clamped. The following op in the same frame proves the refused one
        # was processed: a frame is applied in order and an undecodable op refuses the whole frame.
        send(
            wire.append("rows", b.text("ghost", id="ghost"), position=99),
            wire.append("rows", b.text("row-4", id="row-4")),
        )
        ok = wait(lambda: "row-4" in rows(cdp))
        checks.append(
            (
                "an out-of-range position is refused, not clamped",
                bool(ok) and "ghost" not in rows(cdp),
                f"rows={rows(cdp)}",
            )
        )

        # `empty` is a no-op, and it must still decode: if it did not, the whole frame would be refused and
        # the row after it would never land.
        send(wire.empty(), wire.append("rows", b.text("row-5", id="row-5")))
        ok = wait(lambda: "row-5" in rows(cdp))
        checks.append(("empty decodes and changes nothing", bool(ok), f"rows={rows(cdp)}"))

        errors = console_errors(cdp)
        checks.append(("zero console errors", not errors, "none" if not errors else str(errors)))

    return report(checks, gate="T2 GATE")


if __name__ == "__main__":
    sys.exit(main())