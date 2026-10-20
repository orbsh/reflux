"""The reference application: what a reflux app looks like, written with the SDK and `wire`.

    python3 -m reflux.demo_app --port 8000

Four things, one per shape a page needs to be an application:

- **an echo** — an `input` uplinks its buffer on Enter, a `text` reads the slot the handler writes;
- **a list** — rows live in the `rows` slot and a `rack` shows it; each row's remove button carries
  the row's own identity up, and `remove` takes it back by identity;
- **a form** — one submit carries every field it holds, in the shape the renderer itself produces;
- **two routes** — `/` and `/about`, reached by the address bar, a deep link, back/forward, or the
  page's own navigation forms.

Two facts about this vocabulary shape the code, and both are measured by the gates:

- **A `button` lives inside a `form`** (`gate_t3_next`): that is where the renderer mounts it, and a
  form's submit is the only click that produces a frame. So "add a row", "remove a row" and "go to
  another page" are forms, and the frame's `id` is the form's own id — which is how a row's identity
  rides up and back.
- **accrete has no URL-bearing type**, so there is no anchor to click and nothing to intercept: a
  page change is the producer answering with a new structure plus the new path marker (`go.home` /
  `go.about` below). The runtime mirrors that marker into the address bar.

The two markers are ordinary nodes read straight out of the DOM (`reflux:path`, `reflux:title`) by
`www/static/reflux.js`; `page()` is the one place in this app that writes that convention.
"""

from __future__ import annotations

import argparse
import json

from . import wire
from .app import App
from .protocol import RESERVED_PREFIX
from .routes import route
from .sdk import builders as b
from .sdk.types import Accrete, JsType

ECHO, ROWS, SUBMITTED = "echo", "rows", "submitted"
PATH_MARKER, TITLE_MARKER = f"{RESERVED_PREFIX}path", f"{RESERVED_PREFIX}title"

# Where a navigation form sends the client. The frame's `event` is the target's name.
GO = {"go.home": "/", "go.about": "/about"}


def marker(node_id: str, text: str) -> Accrete:
    """One reserved-id node: a `placeholder` puts its id on the DOM, where the runtime reads it."""
    return b.placeholder(b.text(text), id=node_id)


def page(path: str, title: str, *children: Accrete) -> Accrete:
    """A page: the two markers the client runtime mirrors, then the content."""
    return b.case(marker(PATH_MARKER, path), marker(TITLE_MARKER, title), *children, id="page-root")


def nav_form(label: str, event: str) -> Accrete:
    """A one-button form — the vocabulary's only clickable, and the demo's way between pages."""
    return b.form(b.button(label), event=event, id=f"nav-{event}")


def row_node(row: dict) -> Accrete:
    """One row: its text, and the form whose submit carries the row's own id up."""
    return b.form(b.text(row["text"]), b.button("删"), event="row.remove", id=row["id"])


class Demo:
    """Business state only — what the interface is doing is the page tree's business."""

    def __init__(self) -> None:
        self.echo = ""
        self.submitted: dict = {}
        self.rows = [{"id": "row-1", "text": "第一行"}, {"id": "row-2", "text": "第二行"}]
        self.next_row = 3

    # --- the pages the routes below hand back ---------------------------------------------

    def frame_for(self, session, path: str) -> list[dict]:
        """The ops of one page turn: the structure, plus the rows seeded into the slot it reads.

        The seed happens **once per session**: a slot outlives a `create` (the tree is replaced, the
        data planes are not), so appending the seed rows on a second visit would double them. That
        is the price of a client that keeps the state — the producer counts, per DESIGN's「操作」.
        """
        if path == "/about":
            return [wire.create(self.about())]
        ops = [wire.create(self.home())]
        if not getattr(session, "rows_seeded", False):
            session.rows_seeded = True
            ops.extend(wire.append(ROWS, row_node(row)) for row in self.rows)
        return ops

    def home(self) -> Accrete:
        return page(
            "/",
            "演示",
            b.text("演示", variant="heading-1"),
            b.input(event="name.change", id="name-input"),
            b.text(source=ECHO, id="echo"),
            b.form(b.button("加一行"), event="row.add", id="add-row"),
            b.rack(source=ROWS, id="rows"),
            b.form(
                b.input(field="user", id="f-user"),
                b.input(field="pass", kind=JsType.password, id="f-pass"),
                b.button("保存"),
                event="login.submit",
                id="login",
            ),
            b.text(source=SUBMITTED, id="submitted"),
            nav_form("关于", "go.about"),
            b.text(
                "accrete 没有带 URL 的类型：页面之间靠上面那个表单提交，生产者回一帧新结构"
                "加上新的路径标记，runtime 把标记镜像进地址栏。",
                variant="muted",
            ),
        )

    def about(self) -> Accrete:
        return page(
            "/about",
            "关于",
            b.text("关于", variant="heading-1"),
            b.text("这个示例应用只用 SDK 写出来：回声、列表、表单，加两条路由。"),
            nav_form("回到演示", "go.home"),
        )

    # --- handlers: change the app's data, push exactly that change -------------------------

    def on_name(self, session, frame) -> None:
        # An `input` uplinks its value alone (no wrapper): the frame's `data` is the string.
        self.echo = frame["data"] if isinstance(frame["data"], str) else ""
        session.draw(wire.set(ECHO, b.text(self.echo)))

    def on_add(self, session, frame) -> None:
        row = {"id": f"row-{self.next_row}", "text": f"第 {self.next_row} 行"}
        self.next_row += 1
        self.rows.append(row)
        session.draw(wire.append(ROWS, row_node(row)))

    def on_remove(self, session, frame) -> None:
        row_id = frame.get("id")  # the row's form carried its identity up
        self.rows = [row for row in self.rows if row["id"] != row_id]
        session.draw(wire.remove(ROWS, row_id))

    def on_submit(self, session, frame) -> None:
        fields = frame["data"] if isinstance(frame["data"], dict) else {}
        self.submitted = {
            name: entry.get("data") for name, entry in fields.items() if isinstance(entry, dict)
        }
        summary = json.dumps(self.submitted, ensure_ascii=False, sort_keys=True)
        session.draw(wire.set(SUBMITTED, b.text(f"已提交 {summary}")))

    def on_go(self, session, frame) -> None:
        """A submit that moves the client: new structure and the new path marker, one frame."""
        session.path = GO[frame["event"]]
        session.draw(*self.frame_for(session, session.path))


demo = Demo()  # the routes are module-level declarations, so they attach to one application


@route("/", title="演示")
def home_page(session, match):
    return demo.frame_for(session, "/")


@route("/about", title="关于")
def about_page(session, match):
    return demo.frame_for(session, "/about")


def make_app() -> App:
    """The demo's app: the routes declared above (a side effect of importing this module) and
    this app's event handlers."""
    app = App()
    app.events.register("name.change", demo.on_name)
    app.events.register("row.add", demo.on_add)
    app.events.register("row.remove", demo.on_remove)
    app.events.register("login.submit", demo.on_submit)
    for name in GO:
        app.events.register(name, demo.on_go)
    return app


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="reflux.demo_app", description="Serve the demo app.")
    ap.add_argument("--port", type=int, default=8000, help="0 picks a free port (default: 8000)")
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args(argv)
    app = make_app()
    if args.port == 0:
        server = app.make_server(0, args.host)
        print(f"[reflux] serving the demo on http://{args.host}:{server.server_address[1]}/", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
        return 0
    app.serve_forever(args.port, args.host)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())