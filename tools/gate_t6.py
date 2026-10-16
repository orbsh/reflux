#!/usr/bin/env python3
"""T6 gate — navigation: the shell's interception, history, and the producer's page turn.

Real browser, real clicks, real history. A same-origin link must not reload the page (the marker
the gate puts on `window` is the proof: a load would wipe it), back and forward must be the same
request as a click, an unknown path must answer with the built-in 404 (or with the app's own
`{rest:path}` route, which wins like any other match), and the address bar, the page and the
producer's route must all say the same thing.

    python3 tools/gate_t6.py

Exit code 0 = gate passed.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cdp import console_errors, report, shell_page  # noqa: E402

import reflux.demo_app as demo  # noqa: E402
from reflux import ops, ui  # noqa: E402

HELLO = "reflux:hello"
NAV = "reflux:nav"
CTRL = 2  # the CDP modifier bit for ctrl


def link(label: str) -> str:
    """A JS expression resolving to the link with this label."""
    return f"[...document.querySelectorAll('a.rx-link')].find((e) => e.textContent.trim() === {json.dumps(label)})"


def received(app, event: str | None = None) -> list[dict]:
    return [
        frame
        for direction, frame in app.log
        if direction == "recv" and (event is None or frame.get("event") == event)
    ]


def wait(predicate, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def headings(cdp) -> list[str]:
    return cdp.eval("[...document.querySelectorAll('.rx-heading')].map((e) => e.textContent)") or []


def fallback_page(session, match):
    """A tail route the gate registers at runtime: the app's own answer for any path."""
    return ui.stack(
        ui.heading("兜底", level=1),
        ui.text(f"兜底:{match.params['rest']}"),
        gap="md",
    )


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, evidence: str) -> None:
        checks.append((name, ok, evidence))

    app = demo.make_app()

    # the deep link first: the shell's hello is what carries it
    with shell_page(app=app, path="/about") as (cdp, base):
        errors = console_errors(cdp)
        check("zero console errors", not errors, "none" if not errors else str(errors))

        # 1. cold start: the path in the URL is the page the producer drew
        wait(lambda: received(app, HELLO) and app.sessions)
        hello = received(app, HELLO)
        session = app.sessions[0] if app.sessions else None
        match = app.routes.match("/about")
        check(
            "cold start: hello carries the deep link, that page is drawn",
            bool(hello)
            and hello[0]["data"] == {"path": "/about", "token": None}
            and session is not None
            and session.path == "/about"
            and cdp.eval("location.pathname") == "/about"
            and headings(cdp) == ["关于"]
            and match is not None
            and match.route.path == "/about",
            f"hello={hello[0]['data'] if hello else None} session.path={session.path if session else None!r} "
            f"location={cdp.eval('location.pathname')!r} headings={headings(cdp)}",
        )

        # 2. a same-origin link click: intercepted, no page load, one request, one new page
        cdp.eval("window.__gateMark = 'alive'")  # a page load would take this with it
        navs_before = len(received(app, NAV))
        cdp.click_js(link("演示"))
        wait(lambda: len(received(app, NAV)) > navs_before)
        wait(lambda: cdp.eval("location.pathname") == "/")
        wait(lambda: headings(cdp) == ["演示"])
        session_id = session.id if session else None
        check(
            "a link click is a request, not a page load",
            len(received(app, NAV)) == navs_before + 1
            and len(received(app, HELLO)) == 1
            and len(app.sessions) == 1
            and cdp.eval("window.__gateMark") == "alive"
            and cdp.eval("location.pathname") == "/",
            f"nav frames={len(received(app, NAV))} hellos={len(received(app, HELLO))} "
            f"sessions={len(app.sessions)} mark={cdp.eval('window.__gateMark')!r} "
            f"location={cdp.eval('location.pathname')!r}",
        )

        # 3. the three-way agreement: address bar, page, producer's route
        here = app.routes.match(session.path) if session else None
        rows = cdp.eval("document.querySelectorAll('.rx-rack .rx-row').length")
        check(
            "address bar, page and server-side route agree",
            session is not None
            and session.path == "/"
            and cdp.eval("location.pathname") == "/"
            and headings(cdp) == ["演示"]
            and here is not None
            and here.route.path == "/"
            and bool(received(app, NAV))
            and received(app, NAV)[-1]["data"] == {"path": "/"},
            f"session.path={session.path if session else None!r} location={cdp.eval('location.pathname')!r} "
            f"route={here.route.path if here else None!r} last nav={received(app, NAV)[-1]['data'] if received(app, NAV) else None}",
        )
        check(
            "a page turn carries its slot seed in the same frame",
            rows == 2,
            f"rack rows={rows}",
        )

        # 4. back and forward are the same request
        navs_before = len(received(app, NAV))
        cdp.eval("history.back()")
        wait(lambda: len(received(app, NAV)) > navs_before and cdp.eval("location.pathname") == "/about")
        wait(lambda: headings(cdp) == ["关于"])
        back_ok = (
            len(received(app, NAV)) == navs_before + 1
            and cdp.eval("location.pathname") == "/about"
            and headings(cdp) == ["关于"]
            and session is not None
            and session.path == "/about"
        )
        back_line = f"location={cdp.eval('location.pathname')!r} headings={headings(cdp)} nav frames={len(received(app, NAV))}"

        navs_before = len(received(app, NAV))
        cdp.eval("history.forward()")
        wait(lambda: len(received(app, NAV)) > navs_before and cdp.eval("location.pathname") == "/")
        wait(lambda: headings(cdp) == ["演示"])
        forward_ok = (
            len(received(app, NAV)) == navs_before + 1
            and cdp.eval("location.pathname") == "/"
            and headings(cdp) == ["演示"]
            and session is not None
            and session.path == "/"
        )
        forward_line = f"location={cdp.eval('location.pathname')!r} headings={headings(cdp)} nav frames={len(received(app, NAV))}"
        check("back: the previous page, the same request", back_ok, back_line)
        check("forward: the page again, one more request", forward_ok, forward_line)

        # 5. a click with a modifier belongs to the browser
        navs_before = len(received(app, NAV))
        here = cdp.eval("location.pathname + location.search")
        cdp.click_js(link("关于"), modifiers=CTRL)
        time.sleep(0.3)
        check(
            "a ctrl-click is not intercepted",
            len(received(app, NAV)) == navs_before and cdp.eval("location.pathname + location.search") == here,
            f"nav frames+{len(received(app, NAV)) - navs_before} location={cdp.eval('location.pathname + location.search')!r}",
        )

        # 6. the route contract is the path; the query stays in the address bar
        app.sessions[0].draw(
            ops.insert(
                "/tree/children",
                ui.row(ui.link("/about?x=1", label="带查询串"), gap="sm", id="query-row"),
                anchor="end",
            )
        )
        wait(lambda: cdp.eval("!!" + link("带查询串")))
        navs_before = len(received(app, NAV))
        cdp.click_js(link("带查询串"))
        wait(lambda: len(received(app, NAV)) > navs_before)
        wait(lambda: cdp.eval("location.search") == "?x=1")
        wait(lambda: headings(cdp) == ["关于"])  # the address changes first; the page follows the frame
        check(
            "a querystring link: the address keeps it, the frame does not",
            cdp.eval("location.pathname + location.search") == "/about?x=1"
            and received(app, NAV)[-1]["data"] == {"path": "/about"}
            and headings(cdp) == ["关于"],
            f"location={cdp.eval('location.pathname + location.search')!r} nav={received(app, NAV)[-1]['data']}",
        )

        # 7. an unknown path: the built-in 404, the address left alone, the session intact
        app.sessions[0].draw(
            ops.insert(
                "/tree/children",
                ui.row(ui.link("/nope", label="幽灵页", id="ghost-link"), gap="sm", id="ghost-row"),
                anchor="end",
            )
        )
        wait(lambda: cdp.eval("!!" + link("幽灵页")))
        sessions_before = len(app.sessions)  # a ctrl-click's new tab is a session of its own; this
        navs_before = len(received(app, NAV))  # click must not add one
        cdp.click_js(link("幽灵页"))
        wait(lambda: len(received(app, NAV)) > navs_before)
        wait(lambda: "404" in headings(cdp))
        still_here = session is not None and any(s.id == session_id for s in app.sessions)
        check(
            "unknown path: the built-in 404 structure, nothing else moved",
            cdp.eval("location.pathname") == "/nope"
            and headings(cdp) == ["404"]
            and still_here
            and len(app.sessions) == sessions_before
            and session is not None
            and session.path == "/nope",
            f"location={cdp.eval('location.pathname')!r} headings={headings(cdp)} "
            f"sessions={len(app.sessions)} (was {sessions_before}) session.path={session.path if session else None!r}",
        )

        # 8. an app that registers a tail route answers unknown paths itself
        app.routes.add("/{rest:path}", fallback_page)
        app.sessions[0].draw(
            ops.insert(
                "/tree/children",
                ui.row(ui.link("/nope", label="幽灵页", id="ghost-link-2"), gap="sm", id="ghost-row-2"),
                anchor="end",
            )
        )
        wait(lambda: cdp.eval("!!" + link("幽灵页")))
        navs_before = len(received(app, NAV))
        cdp.click_js(link("幽灵页"))
        wait(lambda: len(received(app, NAV)) > navs_before)
        wait(lambda: "兜底" in headings(cdp))
        check(
            "a registered {rest:path} answers instead of the 404",
            headings(cdp) == ["兜底"]
            and cdp.eval("location.pathname") == "/nope",
            f"headings={headings(cdp)} location={cdp.eval('location.pathname')!r}",
        )

        # 9. the frame the shell sends for a page turn
        nav_frames = received(app, NAV)
        shapes = {
            (set(frame) == {"event", "data"}, set(frame.get("data") or {}) == {"path"}, isinstance(frame["data"]["path"], str))
            for frame in nav_frames
        }
        check(
            "every nav frame is exactly {event, data:{path}}",
            bool(nav_frames) and shapes == {(True, True, True)},
            f"{len(nav_frames)} frames, shapes={sorted(shapes)}",
        )

    return report(checks, gate="T6 GATE")


if __name__ == "__main__":
    sys.exit(main())