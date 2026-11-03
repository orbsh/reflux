"""A routed site: one shell that stays, and the page inside the `routes` slot.

    python3 -m examples.site.app --port 8200        # page + backend (also: python3 examples/site/app.py)
    python3 -m examples.site.walkthrough --auto     # the demo, no browser

Three things this example exists to show, in the order they happen:

1. **connect carries the address bar.** The runtime hands `reflux:hello` its location — `path` and
   `query` — so a pasted deep link (or `?from=paste`) opens that page on the first frame. No
   redirect, no correction turn.
2. **routes, not root.** The app supplies a shell (`App(shell=…)`) whose `placeholder` reads the
   `routes` slot. The first frame is `create(shell)` plus the page written into that slot; a later
   page turn writes only the slot, so the header and the nav are never drawn twice. Without a shell
   the same handlers would replace the layout root — that is `examples/chat`, the single-page case.
3. **navigating is an ordinary event, both ways.** The app navigates by writing the next page into
   the slot; that page carries its own path marker, so the address bar follows without a reload. The
   browser's back/forward arrives as `reflux:nav`, the framework re-draws that path and raises
   `location` for the app.

`connect` / `location` / `disconnect` are the **host's** events: register them like any other name
(`@app.dests.register("connect")`), and note that no client can send them — the frame boundary
refuses those three names, so an app cannot be told a connect that never happened.

The query string is read, not written: it comes up with `hello` and `nav` and lives on
`session.query` (`{"tag": ["a", "b"]}` — repeated keys keep every value). The address bar's query
belongs to the browser, so the downlink never touches it.
"""

from __future__ import annotations

import sys
from pathlib import Path

# `python3 examples/site/{name}.py` as well as `-m examples.site.{name}`: a script's own directory
# is what goes on sys.path by default, and this example needs the repo root (it imports reflux).
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
from typing import Any

from reflux import ROUTES_SLOT, Routes, wire
from reflux.app import App, Session
from reflux.sdk import builders as b
from reflux.sdk import markers
from reflux.sdk.types import Accrete

__all__ = ["PAGES", "SHELL_ID", "app", "go", "make_app", "shell", "site"]

PAGES = {"/": "首页", "/about": "关于"}
SHELL_ID = "shell"


def where(session: Session) -> str:
    """The address as the backend sees it — which is the whole point of carrying `query` up."""
    pairs = [f"{key}={value}" for key, values in session.query.items() for value in values]
    return f"地址 {session.path}" + (f" · 查询 {' & '.join(pairs)}" if pairs else " · 没有查询")


def home(session: Session, match: Any = None) -> Accrete:
    return markers.page(
        "/",
        "首页",
        b.text("首页", variant="heading-1"),
        b.text(where(session), variant="muted"),
        b.text("点「关于」，或者按一次浏览器后退：地址栏跟着走，外面那层不重画。", variant="muted"),
        id="page-home",
    )


def about(session: Session, match: Any = None) -> Accrete:
    return markers.page(
        "/about",
        "关于",
        b.text("关于", variant="heading-1"),
        b.text(where(session), variant="muted"),
        b.text("这一页住在一个槽里：标题和导航是连接时建的那一层，之后没再画过。", variant="muted"),
        id="page-about",
    )


# One table of its own, not the module-level default: two modules declaring "/" collide at import.
site = Routes()
site.add("/", home)
site.add("/about", about)


def shell(session: Session) -> Accrete:
    """The frame around every page: created once per connection, then left alone.

    Its last child reads the `routes` slot — that is the whole contract between the framework and
    this view. The shell is the app's own structure, so the slot reader is written here, not by the
    framework; the framework only knows the name it writes to (`ROUTES_SLOT`).
    """
    return b.case(
        b.text("示例站点", variant="heading-1"),
        b.form(b.button("首页", id="go-home"), dest="go.home", id="nav-home"),
        b.form(b.button("关于", id="go-about"), dest="go.about", id="nav-about"),
        b.placeholder(source=ROUTES_SLOT, id="routes"),
        id=SHELL_ID,
    )


def go(session: Session, path: str) -> None:
    """Navigate: one frame, the page into the slot. The page's own marker moves the address bar.

    `session.path` moves first: the page is built from it (the address line inside the page reads
    it), and a resync later must draw the same page the client is standing on.
    """
    match = site.match(path)
    if match is None:
        return
    session.path = path
    session.draw(wire.set(ROUTES_SLOT, match.resolve(session)))


def make_app() -> App:
    """The app: one shell, two routes, and the three host events in a small log."""
    app = App(routes=site, shell=shell)
    # What the app heard from the host, in order — the walkthrough and the gate read it. Keeping it
    # on the app is the example's own choice; the framework hands the event over and forgets it.
    heard: list[tuple[str, str, Any]] = []
    setattr(app, "heard", heard)

    @app.dests.register("connect")
    def on_connect(session: Session, frame: dict) -> None:
        heard.append(("connect", session.path, dict(session.query)))

    @app.dests.register("location")
    def on_location(session: Session, frame: dict) -> None:
        heard.append(("location", session.path, dict(session.query)))

    @app.dests.register("disconnect")
    def on_disconnect(session: Session, frame: dict) -> None:
        heard.append(("disconnect", session.id, dict(session.query)))

    @app.dests.register("go.home")
    def on_home(session: Session, frame: dict) -> None:
        go(session, "/")

    @app.dests.register("go.about")
    def on_about(session: Session, frame: dict) -> None:
        go(session, "/about")

    return app


app = make_app()


def main() -> None:
    ap = argparse.ArgumentParser(description="A routed site: a shell, a routes slot, two pages.")
    ap.add_argument("--port", type=int, default=8200)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    print(f"[site] routes={sorted(PAGES)} shell={SHELL_ID!r} slot={ROUTES_SLOT!r}", flush=True)
    make_app().serve_forever(args.port, args.host)


if __name__ == "__main__":
    main()