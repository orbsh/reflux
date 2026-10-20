#!/usr/bin/env python3
"""T6 gate — the client runtime mirrors the URL and the title, and only mirrors them.

The runtime (`www/static/reflux.js`) is the only thing on the page that writes `location` and
`document.title`; it reads two reserved-id nodes and nothing else, and the producer is the only
writer of those nodes. This gate runs the real page and plays the producer:

  * it draws accrete pages by hand — a hand-writing producer is exactly the no-closure case the
    design allows, and it keeps this gate about the runtime rather than about `wire`
  * the markers are built with the generated SDK and dumped to the wire, which pins the marker node
    shape an application's page helper has to produce

Checks: the path marker moves the address bar (once per real change), the title marker writes
document.title, back/forward is one `reflux:nav` carrying the app path, a deep link is answered
from the hello path, and a page without markers leaves the bar and the title at their old values.

    python3 tools/gate_t6.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cdp import Cdp, console_errors, report, open_page  # noqa: E402
from reflux.app import App  # noqa: E402
from reflux.sdk import builders as b  # noqa: E402
from reflux.sdk import markers as page_markers  # noqa: E402
from reflux.sdk._parse import dump  # noqa: E402

PAGE = "/"


def page(path: str, title: str, *, label: str | None = None, markers: bool = True):
    """One page; `markers=False` omits the two reserved markers on purpose.

    The convention itself is the SDK's (`markers.page`); this helper only adds the two knobs these
    scenarios need — a label to find the page by, and a page with no markers at all.
    """
    shown = label or f"page {path}"
    children = [b.text(shown, id="page-label")]
    if markers:
        return page_markers.page(path, title, *children)
    return b.case(*children, id="page-root")


def draw(session, node) -> None:
    """One accrete `draw` frame: `create` on the layout root (`event` is required but unread)."""
    session.send(
        {
            "ev": "draw",
            "sender": session.id,
            "content": [{"action": "create", "event": "", "data": dump(node)}],
        }
    )


def wait(predicate, timeout: float = 10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        got = predicate()
        if got:
            return got
        time.sleep(0.05)
    return None


def seen(cdp: Cdp, text: str) -> bool:
    return bool(cdp.eval(f"document.body.innerText.includes({json.dumps(text)})"))


def frames(app: App, event: str) -> list[dict]:
    return [
        frame
        for direction, frame in list(app.log)
        if direction == "recv" and isinstance(frame, dict) and frame.get("event") == event
    ]


def main() -> int:
    app = App()
    checks: list[tuple[str, bool, str]] = []

    with open_page(path=PAGE, app=app, settle=0.4) as (cdp, base):
        session = wait(lambda: next(iter(app.live()), None))
        if session is None:
            print("no session: the page never connected")
            return 1

        # 1: the first page's marker moves the bar exactly once
        before = cdp.eval("history.length")
        draw(session, page("/a", "A"))
        drawn = wait(lambda: seen(cdp, "page /a"))
        bar = cdp.eval("location.pathname")
        title = cdp.eval("document.title")
        after_first = cdp.eval("history.length")
        checks.append(
            (
                "the path marker moves the address bar",
                bool(drawn) and bar == PAGE + "a" and after_first == before + 1,
                f"location={bar} history={before}->{after_first}",
            )
        )
        checks.append(("the title marker writes document.title", title == "A", f"title={title!r}"))

        # 2: the same path again is not a new history entry
        draw(session, page("/a", "A", label="again"))
        wait(lambda: seen(cdp, "again"))
        same = cdp.eval("history.length")
        checks.append(
            (
                "drawing the same path again adds no entry",
                same == after_first,
                f"history={after_first}->{same}",
            )
        )

        # 3: a real page turn pushes exactly one entry
        draw(session, page("/b", "B"))
        wait(lambda: seen(cdp, "page /b"))
        bar_b = cdp.eval("location.pathname")
        after_turn = cdp.eval("history.length")
        checks.append(
            (
                "a page turn pushes exactly one entry",
                bar_b == PAGE + "b" and after_turn == same + 1,
                f"location={bar_b} history={same}->{after_turn}",
            )
        )

        # 4: back is one nav frame carrying the app path; the producer answers with the page
        before_nav = len(frames(app, "reflux:nav"))
        cdp.eval("history.back()")
        navs = wait(lambda: frames(app, "reflux:nav")[before_nav:])
        nav = navs[0] if navs else {}
        if nav:
            draw(session, page("/a", "A"))
            wait(lambda: cdp.eval("document.title") == "A")
        back_bar = cdp.eval("location.pathname")
        checks.append(
            (
                "back is one reflux:nav with the app path",
                bool(nav)
                and nav.get("data") == {"path": "/a"}
                and back_bar == PAGE + "a"
                and cdp.eval("history.length") == after_turn,
                f"frame={nav!r} location={back_bar}",
            )
        )

        # 5: a deep link is answered from the hello path, and the bar does not move
        before_hellos = len(frames(app, "reflux:hello"))
        cdp.call("Page.navigate", url=base + PAGE + "deep/link")
        wait(
            lambda: cdp.eval("!!(window.fluxen && typeof window.fluxen.send === 'function')") is True,
            timeout=20,
        )
        hellos = wait(lambda: frames(app, "reflux:hello")[before_hellos:])
        hello = hellos[0] if hellos else {}
        deep_session = wait(lambda: next((s for s in app.live() if s.path == "/deep/link"), None))
        if deep_session is not None:
            draw(deep_session, page("/deep/link", "Deep"))
            wait(lambda: seen(cdp, "page /deep/link"))
        deep_bar = cdp.eval("location.pathname")
        checks.append(
            (
                "a deep link is one hello with the app path",
                hello.get("data") == {"path": "/deep/link"} and deep_bar == PAGE + "deep/link",
                f"hello={hello.get('data')!r} location={deep_bar}",
            )
        )

        # 6: a page without markers leaves the bar and the title alone (mirror, do not guess)
        title_before = cdp.eval("document.title")
        if deep_session is not None:
            draw(deep_session, page("/ignored", "Ignored", label="no markers", markers=False))
            wait(lambda: seen(cdp, "no markers"))
        checks.append(
            (
                "a page without markers changes nothing",
                cdp.eval("location.pathname") == deep_bar
                and cdp.eval("document.title") == title_before,
                f"location={cdp.eval('location.pathname')} title={cdp.eval('document.title')!r}",
            )
        )

        # 7: nothing on the page complained
        errors = console_errors(cdp)
        checks.append(("zero console errors", not errors, "none" if not errors else str(errors)))

    return report(checks, gate="T6 GATE")


if __name__ == "__main__":
    sys.exit(main())