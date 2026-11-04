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
`www/static/reflux.js`; the convention lives in `reflux.sdk.markers` (one `page()` call per page),
because the page's own shape is the runtime's contract, not an application's private habit.
"""

from __future__ import annotations

import argparse
import json
from typing import Protocol

from .app import App, Context
from .routes import route
from .sdk import builders as b
from .sdk.types import Accrete, JsType
from .slots import Slot

def slots_of(ctx: Context) -> "DemoSlots":
    """The reference app's slots for this delivery. The names are the Protocol's; the wire sees names."""
    return ctx.slot  # type: ignore[return-value]


class DemoSlots(Protocol):
    """The reference app's slots, for the editor — the runtime only ever sees the names."""

    echo: Slot  # what the input last carried
    rows: Slot  # the list the rack reads
    submitted: Slot  # the last form's fields, as one line of JSON

# Where a navigation form sends the client. The frame's `event` is the target's name.
GO_HOME, GO_ABOUT = Slot("go.home"), Slot("go.about")
GO = {GO_HOME.name: "/", GO_ABOUT.name: "/about"}


def nav_form(label: str, dest: Slot) -> Accrete:
    """A one-button form — the vocabulary's only clickable, and the demo's way between pages."""
    return b.form(b.button(label), dest=dest, id=f"nav-{dest.name}")


def row_node(row: dict, ctx: Context) -> Accrete:
    """One row: its text, and the form whose submit carries the row's own id up."""
    # `remove` is a verb on a slot, so this name is written with the subscript.
    return b.form(b.text(row["text"]), b.button("删"), dest=ctx.slot.row["remove"], id=row["id"])


class Demo:
    """Business state only — what the interface is doing is the page tree's business."""

    def __init__(self) -> None:
        self.echo = ""
        self.submitted: dict = {}
        self.rows = [{"id": "row-1", "text": "第一行"}, {"id": "row-2", "text": "第二行"}]
        self.next_row = 3

    # --- the pages the routes below hand back ---------------------------------------------

    def draw_home(self, ctx) -> None:
        """The home page, and — the first time this connection asks — the rows it reads.

        The seed happens **once per device**: a slot outlives a `create` (the tree is replaced, the
        data planes are not), so appending the seed rows on a second visit would double them. It is a
        send like any other, so it is written as one: the page is `ctx.page(...)`, the seed is
        `ctx.emit(...)`, and neither of them is a return.
        """
        ctx.page(*self.home(ctx))
        if not ctx.data.get("rows_seeded"):
            ctx.data["rows_seeded"] = True
            for row in self.rows:
                slots_of(ctx).rows.append(row_node(row, ctx))

    def home(self, ctx: Context) -> list[Accrete]:
        """The home page's content — the markers are `ctx.page`'s business, not the app's.

        It takes the delivery because its nodes name things: the slots they read (`source=`) and the
        dests they speak to (`dest=`) are handles, and a handle comes from the context that owns them.
        """
        slots = slots_of(ctx)
        return [
            b.text("演示", variant="heading-1"),
            b.input(dest=ctx.slot.name.change, id="name-input"),
            b.text(source=slots.echo, id="echo"),
            b.form(b.button("加一行"), dest=ctx.slot.row.add, id="add-row"),
            b.rack(source=slots.rows, id="rows"),
            b.form(
                b.input(field="user", id="f-user"),
                b.input(field="pass", kind=JsType.password, id="f-pass"),
                b.button("保存"),
                dest=ctx.slot.login.submit,
                id="login",
            ),
            b.text(source=slots.submitted, id="submitted"),
            nav_form("关于", GO_ABOUT),
            b.text(
                "accrete 没有带 URL 的类型：页面之间靠上面那个表单提交，生产者回一帧新结构"
                "加上新的路径标记，runtime 把标记镜像进地址栏。",
                variant="muted",
            ),
        ]

    def about(self) -> list[Accrete]:
        return [
            b.text("关于", variant="heading-1"),
            b.text("这个示例应用只用 SDK 写出来：回声、列表、表单，加两条路由。"),
            nav_form("回到演示", GO_HOME),
        ]

    # --- handlers: change the app's data, push exactly that change -------------------------

    def on_name(self, ctx, frame) -> None:
        # An `input` uplinks its value alone (no wrapper): the frame's `data` is the string.
        self.echo = frame["data"] if isinstance(frame["data"], str) else ""
        slots_of(ctx).echo.set(b.text(self.echo))

    def on_add(self, ctx, frame) -> None:
        row = {"id": f"row-{self.next_row}", "text": f"第 {self.next_row} 行"}
        self.next_row += 1
        self.rows.append(row)
        slots_of(ctx).rows.append(row_node(row, ctx))

    def on_remove(self, ctx, frame) -> None:
        row_id = frame.get("id")  # the row's form carried its identity up
        self.rows = [row for row in self.rows if row["id"] != row_id]
        slots_of(ctx).rows.remove(row_id)

    def on_submit(self, ctx, frame) -> None:
        fields = frame["data"] if isinstance(frame["data"], dict) else {}
        self.submitted = {
            name: entry.get("data") for name, entry in fields.items() if isinstance(entry, dict)
        }
        summary = json.dumps(self.submitted, ensure_ascii=False, sort_keys=True)
        slots_of(ctx).submitted.set(b.text(f"已提交 {summary}"))

    def on_go(self, ctx, frame) -> None:
        """A submit that moves the client: the new structure and the new path marker."""
        ctx.go(GO[frame["dest"]])


demo = Demo()  # the routes are module-level declarations, so they attach to one application


@route("/", title="演示")
def home_page(ctx, match):
    demo.draw_home(ctx)


@route("/about", title="关于")
def about_page(ctx, match):
    ctx.page(*demo.about())


def make_app() -> App:
    """The demo's app: the routes declared above (a side effect of importing this module) and
    this app's event handlers."""
    app = App()
    app.on(app.slot.name.change, demo.on_name)
    app.on(app.slot.row.add, demo.on_add)
    app.on(app.slot.row["remove"], demo.on_remove)  # `remove` is a verb: the name goes by subscript
    app.on(app.slot.login.submit, demo.on_submit)
    for name in GO:
        app.on(app.slot(name), demo.on_go)
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