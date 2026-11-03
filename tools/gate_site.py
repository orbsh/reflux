#!/usr/bin/env python3
"""Site gate — the routed example: the shell, the `routes` slot, and the address bar.

Two phases, because they answer different questions.

**A. The socket phase** drives `examples.site` as a client: the first frame carries the shell and the
page in one turn; a page turn after that carries the slot and nothing else; a deep link opens its own
page on the first frame; a path nobody registered lands the framework's 404 inside the same shell; and
the app hears `connect` / `location` / `disconnect` with the address bar's path and query.

**B. The browser phase** puts the same app in real Chromium, which is the only place the address bar
can be judged: clicking 关于 must change the URL without redrawing the shell (the same DOM node
before and after), back must come home the same way, and a pasted `/about?from=link` must arrive with
its query — that is the whole point of carrying it up.

    python3 tools/gate_site.py

Exit code 0 = gate passed.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # the cdp fixture
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # the example (examples/site)

from cdp import Cdp, console_errors, open_page, report  # noqa: E402

from examples.chat.client import Socket  # noqa: E402
from examples.site.app import make_app  # noqa: E402

PAGE = "/"


def wait_for(predicate, timeout: float = 8.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


# --- reading frames --------------------------------------------------------------------


def actions(frames: list[dict]) -> list[str]:
    return [op.get("action") for frame in frames for op in frame]


def slots(frames: list[dict]) -> list[str]:
    return [op.get("slot") for frame in frames for op in frame]


def text_of(node: object) -> str:
    """Every literal a structure carries, joined — enough to say which page landed."""
    if not isinstance(node, dict):
        return ""
    out: list[str] = []
    value = (node.get("bind") or {}).get("value") or {}
    if node.get("type") == "text" and isinstance(value.get("default"), str):
        out.append(value["default"])
    for child in node.get("children") or []:
        out.append(text_of(child))
    return " ".join(part for part in out if part)


def read(ws: Socket, want: int = 1, timeout: float = 5.0) -> list[dict]:
    """`want` frames, or as many as arrive before the timeout."""
    frames: list[dict] = []
    deadline = time.monotonic() + timeout
    while len(frames) < want and time.monotonic() < deadline:
        try:
            frame = ws.recv(timeout=max(0.05, deadline - time.monotonic()))
        except TimeoutError:
            break
        if frame is None:
            break
        frames.append(frame)
    return frames


def quiet(ws: Socket, seconds: float = 0.25) -> list[dict]:
    """Whatever else arrives in the next `seconds` — should be nothing after a single frame."""
    return read(ws, want=99, timeout=seconds)


# --- phase A ---------------------------------------------------------------------------


def socket_phase() -> list[tuple[str, bool, str]]:
    app = make_app()
    srv = app.make_server(0)
    port = int(srv.server_address[1])
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    checks: list[tuple[str, bool, str]] = []
    try:
        with Socket(port) as ws:
            # 1 — connect: shell + page in one frame, and the query reached the backend.
            ws.send({"dest": "reflux:hello", "data": {"path": "/", "query": "?from=paste&tag=a&tag=b"}})
            first = read(ws, 1)
            page_op = next((op for op in first[0] if op.get("slot") == "routes"), None) if first else None
            body = text_of(page_op["data"]) if page_op else ""
            checks.append(
                (
                    "connect draws the shell and the home page in one frame",
                    actions(first) == ["create", "set"] and slots(first) == ["", "routes"],
                    f"actions={actions(first)} slots={slots(first)}",
                )
            )
            checks.append(
                (
                    "the address bar's query reaches the backend",
                    "from=paste" in body and "tag=a" in body and "tag=b" in body,
                    f"page={body[:60]!r}",
                )
            )
            checks.append(
                (
                    "the app heard connect with that location",
                    any(name == "connect" and where == "/" and detail.get("from") == ["paste"]
                        for name, where, detail in getattr(app, "heard", [])),
                    f"heard={getattr(app, 'heard', [])[:2]}",
                )
            )
            checks.append(("no second frame follows the first", quiet(ws) == [], "extra frames"))
            checks.append(("nothing was refused", app.stats["refused"] == 0, f"refused={app.stats['refused']}"))

            # 2 — a nav button is an ordinary event: the slot moves, the shell does not.
            ws.send({"dest": "go.about", "id": "go-about", "data": {}})
            turn = read(ws, 1)
            body = text_of(turn[0][0]["data"]) if turn else ""
            checks.append(
                (
                    "a page turn writes only the routes slot",
                    actions(turn) == ["set"] and slots(turn) == ["routes"] and "关于" in body,
                    f"actions={actions(turn)} page={body[:40]!r}",
                )
            )

            # 3 — back/forward: the browser drove it, so the app hears `location`.
            ws.send({"dest": "reflux:nav", "data": {"path": "/", "query": "?from=paste"}})
            turn = read(ws, 1)
            body = text_of(turn[0][0]["data"]) if turn else ""
            heard = getattr(app, "heard", [])
            checks.append(
                (
                    "a nav re-draws that path and raises location",
                    actions(turn) == ["set"] and "首页" in body and ("location", "/", {"from": ["paste"]}) in heard,
                    f"actions={actions(turn)} heard={heard[-1:]!r}",
                )
            )

            # 4 — a pasted deep link: its own first frame, its own query.
            with Socket(port) as deep:
                deep.send({"dest": "reflux:hello", "data": {"path": "/about", "query": "?from=link"}})
                first = read(deep, 1)
                body = text_of(first[0][1]["data"]) if first else ""
                checks.append(
                    (
                        "a pasted /about?from=link opens that page directly",
                        actions(first) == ["create", "set"] and "关于" in body and "from=link" in body,
                        f"actions={actions(first)} page={body[:50]!r}",
                    )
                )

            # 5 — nothing registered: the framework's own 404, inside the same shell.
            with Socket(port) as lost:
                lost.send({"dest": "reflux:hello", "data": {"path": "/nowhere", "query": ""}})
                first = read(lost, 1)
                body = text_of(first[0][1]["data"]) if first else ""
                checks.append(
                    (
                        "an unregistered address draws the built-in 404 in the routes slot",
                        actions(first) == ["create", "set"] and slots(first)[1] == "routes" and "404" in body,
                        f"actions={actions(first)} page={body[:40]!r}",
                    )
                )

            # 6 — the clients came and went: the app heard it, once each.
            time.sleep(0.4)
            heard = getattr(app, "heard", [])
            gone = [row for row in heard if row[0] == "disconnect"]
            checks.append(
                (
                    "every closed session is announced once",
                    len(gone) >= 2 and app.stats["refused"] == 0,
                    f"disconnects={len(gone)} refused={app.stats['refused']}",
                )
            )
    finally:
        app.stop()
        srv.shutdown()
        srv.server_close()
    return checks


# --- phase B ---------------------------------------------------------------------------


def browser_phase() -> list[tuple[str, bool, str]]:
    app = make_app()
    checks: list[tuple[str, bool, str]] = []
    with open_page(app=app, path=PAGE, settle=0.6) as (cdp, base):
        drawn = wait_for(lambda: "示例站点" in (cdp.eval("document.body.innerText") or ""))
        checks.append(
            (
                "the shell draws and the home page lands in it",
                bool(drawn) and "首页" in (cdp.eval("document.body.innerText") or ""),
                f"body={((cdp.eval('document.body.innerText') or ''))[:60]!r}",
            )
        )
        if not drawn:
            return checks

        # Remember the shell node itself: a page turn must not replace it.
        cdp.eval("window.__shell = document.getElementById('shell')")
        click = (
            "[...document.querySelectorAll('.button')]"
            ".filter(el => (el.innerText || '').trim() === '关于')[0]"
        )
        cdp.click_js(click)
        moved = wait_for(
            lambda: "关于" in (cdp.eval("document.body.innerText") or "")
            and cdp.eval("location.pathname") == "/about"
        )
        checks.append(
            (
                "clicking 关于 draws the page and the address bar follows",
                bool(moved) and cdp.eval("location.pathname") == "/about",
                f"url={cdp.eval('location.pathname')!r}",
            )
        )
        checks.append(
            (
                "the shell is the same node after the page turn",
                bool(cdp.eval("window.__shell === document.getElementById('shell')")),
                "identity of #shell",
            )
        )

        cdp.eval("history.back()")
        home = wait_for(
            lambda: "首页" in (cdp.eval("document.body.innerText") or "")
            and cdp.eval("location.pathname") == "/"
        )
        checks.append(
            (
                "back returns home without redrawing the shell",
                bool(home) and bool(cdp.eval("window.__shell === document.getElementById('shell')")),
                f"url={cdp.eval('location.pathname')!r}",
            )
        )

        cdp.eval("window.__title = document.title")
        checks.append(
            ("the page's title marker reaches the document", cdp.eval("document.title") == "首页",
             f"title={cdp.eval('document.title')!r}"),
        )
        errors = console_errors(cdp)
        checks.append(("the page logged no console errors", not errors, f"errors={errors[:2]}"))
        if not (drawn and moved and home):
            print(f"    base={base}")

    # A pasted deep link with a query, through the real runtime.
    app = make_app()
    with open_page(app=app, path="/about?from=link", settle=0.6) as (cdp, base):
        arrived = wait_for(
            lambda: "from=link" in (cdp.eval("document.body.innerText") or "")
        )
        checks.append(
            (
                "a deep link with a query opens that page and the backend sees the query",
                bool(arrived) and cdp.eval("location.pathname") == "/about",
                f"url={cdp.eval('location.search')!r}",
            )
        )
        errors = console_errors(cdp)
        checks.append(("the deep-linked page logged no console errors", not errors, f"errors={errors[:2]}"))
        if not arrived:
            print(f"    base={base}")
    app.stop()
    return checks


def main() -> int:
    checks = socket_phase() + browser_phase()
    return report(checks, gate="SITE GATE")


if __name__ == "__main__":
    raise SystemExit(main())