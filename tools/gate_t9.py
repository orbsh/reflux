#!/usr/bin/env python3
"""T9 gate — the reference app in a real browser: is the SDK enough to write an application?

`reflux/demo_app.py` is the only application in this repo written the way an application is written
(SDK builders + `wire` + the route table), and until this gate nothing drove it: it was `gate_t7`'s
session fixture and nothing more. So the question T9 asks is not about a mechanism — every mechanism
has its own gate — but about the whole: four advertised interactions, two declared routes, and the
framework's built-in 404 on the same page.

Navigation is asserted as the **mirror**, not as an anchor: accrete has no URL-bearing type, so the
demo moves between pages with a one-button form, and the producer answers with a new structure that
carries a new `reflux:path` marker; the address bar follows because the runtime mirrors that marker
(`gate_t6` pins the runtime, this gate uses it).

The 404 check is new ground: it could not exist before M1.7, when the built-in 404 was still the
retired shell's shape and drew nothing on this page. It is an accrete node now (two token variants),
so a deep link to an unregistered path must land on it and the bar must stay where the client is.

    python3 tools/gate_t9.py

Exit code 0 = gate passed.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cdp import Cdp, console_errors, report, open_page  # noqa: E402

import reflux.demo_app as demo  # noqa: E402

PAGE = "/"


def wait_for(predicate, timeout: float = 5.0):
    """Poll until the predicate is truthy — the DOM lands asynchronously, the bar after it."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        got = predicate()
        if got:
            return got
        time.sleep(0.03)
    return predicate()


def body(cdp: Cdp) -> str:
    return cdp.eval("document.body.innerText") or ""


def seen(cdp: Cdp, text: str) -> bool:
    return text in body(cdp)


def rows(cdp: Cdp) -> int:
    """The buttons inside the list slot — one per row (each row is a one-button form)."""
    return cdp.eval("document.querySelectorAll('#rows .button').length") or 0


def frames(app, event: str) -> list[dict]:
    return [
        frame
        for direction, frame in list(app.log)
        if direction == "recv" and isinstance(frame, dict) and frame.get("dest") == event
    ]


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


def type_into(cdp: Cdp, index: int, text: str, *, enter: bool = True) -> None:
    """Type into the index-th input of the page (the tree's order is the demo app's own)."""
    cdp.eval(f"document.querySelectorAll('input')[{index}].focus()")
    cdp.type_text(text)
    if enter:
        press_enter(cdp)


def click_label(cdp: Cdp, label: str, *, nth: int = 0) -> None:
    """Click the button that says `label` (a button's label is its own value) — no index guessing."""
    cdp.click_js(
        f"[...document.querySelectorAll('.button')]"
        f".filter(el => (el.innerText || '').trim() === {json.dumps(label)})[{nth}]"
    )


def main() -> int:
    app = demo.make_app()
    checks: list[tuple[str, bool, str]] = []
    base_url = ""

    with open_page(path=PAGE, app=app, settle=0.5) as (cdp, base):
        base_url = base
        drawn = wait_for(lambda: seen(cdp, "演示") and rows(cdp) == 2)
        checks.append(
            (
                "the reference app draws its page and seeds the list",
                bool(drawn),
                f"heading={'演示' in body(cdp)} rows={rows(cdp)}",
            )
        )
        if not drawn:
            return report(checks, gate="T9 GATE")

        # 1 — an input's Enter uplinks, and the text that reads the slot follows.
        type_into(cdp, 0, "hello")
        echoed = wait_for(lambda: seen(cdp, "hello"))
        checks.append(("an input's Enter reaches the slot it wrote", bool(echoed), f"echo={'hello' in body(cdp)}"))

        # 2 — one form submit adds a row (the add form's button is the page's own).
        click_label(cdp, "加一行")
        added = wait_for(lambda: rows(cdp) == 3)
        checks.append(("a one-button form adds a row", bool(added), f"rows={rows(cdp)}"))

        # 3 — a row's own form removes that row, by the identity it carried up.
        click_label(cdp, "删", nth=0)
        removed = wait_for(lambda: rows(cdp) == 2 and "第一行" not in body(cdp))
        checks.append(
            (
                "a row's form removes it by identity",
                bool(removed),
                f"rows={rows(cdp)} first_row={'第一行' in body(cdp)}",
            )
        )

        # 4 — one submit carries every field of the form, in the renderer's own shape.
        type_into(cdp, 1, "ada")
        type_into(cdp, 2, "secret")
        click_label(cdp, "保存")
        submitted = wait_for(lambda: "已提交" in body(cdp) and "ada" in body(cdp))
        checks.append(
            (
                "one submit carries every field",
                bool(submitted) and "secret" in body(cdp),
                f"submitted={'已提交' in body(cdp)} fields={'ada' in body(cdp) and 'secret' in body(cdp)}",
            )
        )

        # 5 — navigation is a submit, and the address bar follows the marker (the mirror).
        before_nav = len(frames(app, "reflux:nav"))
        click_label(cdp, "关于")
        moved = wait_for(lambda: seen(cdp, "关于") and cdp.eval("location.pathname") == "/about")
        checks.append(
            (
                "a submit moves the page and the marker moves the address bar",
                bool(moved),
                f"location={cdp.eval('location.pathname')} about={'关于' in body(cdp)}",
            )
        )

        # 6 — and back the other way, the same mechanism.
        click_label(cdp, "回到演示")
        back_home = wait_for(lambda: seen(cdp, "演示") and cdp.eval("location.pathname") == "/")
        checks.append(
            (
                "the other direction is the same mechanism",
                bool(back_home),
                f"location={cdp.eval('location.pathname')}",
            )
        )

        # 7 — the browser's own back is one `reflux:nav`, and the producer answers it.
        before_back = len(frames(app, "reflux:nav"))
        cdp.eval("history.back()")
        navs = wait_for(lambda: frames(app, "reflux:nav")[before_nav:] or None)
        nav = (navs or [{}])[0]
        landed = wait_for(
            lambda: seen(cdp, "关于") and cdp.eval("location.pathname") == "/about"
        )
        checks.append(
            (
                "back is one reflux:nav carrying the app path",
                len(navs or []) == 1 and nav.get("data") == {"path": "/about"} and bool(landed),
                f"frames={len(navs or [])} data={nav.get('data')!r} location={cdp.eval('location.pathname')}",
            )
        )

        # 8 — nothing matched is the framework's own page, and the bar stays where the client is.
        cdp.call("Page.navigate", url=base_url + "/nope")
        not_found = wait_for(lambda: seen(cdp, "404") and seen(cdp, "/nope"))
        checks.append(
            (
                "an unregistered path draws the built-in 404",
                bool(not_found) and cdp.eval("location.pathname") == "/nope",
                f"location={cdp.eval('location.pathname')} text={body(cdp)[:40]!r}",
            )
        )

        errors = console_errors(cdp)
        checks.append(("zero console errors", not errors, "none" if not errors else str(errors)))

    return report(checks, gate="T9 GATE")


if __name__ == "__main__":
    sys.exit(main())