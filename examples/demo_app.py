"""The reference application: what a reflux app looks like, written with the SDK and `wire`.

    python3 -m examples.demo_app --port 8000

Three pages, a shell around them, and one page per shape an application is made of:

- `/` — **the vocabulary**, as cards. An `input` uplinks its buffer on Enter and a `text` reads the
  slot the handler writes (an echo); rows live in a slot and a `tiles` shows them, each row's remove
  button carrying its own identity up, and a row also carries cargo — its frame is `draggable`, so
  dragging it onto the landing frame uplinks `{id, tag}`, the dragged frame's own id, so the archive
  handler resolves what the gesture never could (the drag itself reports nothing: only the landing
  point does); and one `bundle` carries every field it packs (`{tag: value, …}`, ADR 0032) — the
  LOGIN bundle, because credentials are the framework's business: the exit is `reflux:login`, the
  app writes only `verify` and `view`, and no password is ever read here. Behind it, `vault.secret`
  is declared `auth=True`, so an anonymous click opens the login surface instead of reaching the
  handler and the same click lands once signed in (`退出` is the way back out).
- `/about` — the second route, reached by the address bar, a deep link, back/forward, or the nav.
- `/demo` — the walkthrough page, which is `examples/demo/`'s: fluxen's own story, played by a
  floating button, in four regions that each read one slot. The page is content and lives with the
  examples; this module is what an app looks like, and it imports the page the way an app imports a
  page.

**The shell** is this app's, not the framework's default: a header that says where you are and the
`routes` reader the pages are written into. It is drawn once per connection, so a page turn replaces
one slot and leaves the header alone. Its reader is `min-height: 0` on purpose — a grid item's
automatic minimum is its content, and without the zero that row would grow with the page instead of
scrolling it.

Two facts about this vocabulary shape the code, and both are measured by the gates:

- **A `button` lives inside a `bundle`** (`gate_t3_next`): that is where the renderer mounts it, and
  a bundle's `submit` is what a press sends (`submit=["button"]`). So "add a row", "remove a row" and
  "go to another page" are one-button bundles, and the frame's `id` is the bundle's own id — which is
  how a row's identity rides up and back.
- **accrete has no URL-bearing type**, so there is no anchor to click and nothing to intercept: a
  page change is the producer answering with a new structure plus the new path marker (`go.home` /
  `go.about` / `go.demo` below). The runtime mirrors that marker into the address bar.

The two markers are ordinary nodes read straight out of the DOM (`reflux:path`, `reflux:title`) by
`www/static/reflux.js`; the convention lives in `reflux.sdk.markers` (one `page()` call per page),
because the page's own shape is the runtime's contract, not an application's private habit.
"""

from __future__ import annotations

import argparse
from typing import Protocol

try:  # the page is the repository's example tree, not the framework package
    from .demo import page as walkthrough
except ModuleNotFoundError as missing:  # a wheel carries `reflux`, so this app runs from a checkout
    raise ModuleNotFoundError(
        "examples.demo_app serves the walkthrough page, which lives in the repository's examples/demo/ "
        "tree; run it from a checkout of reflux"
    ) from missing
from reflux.app import App, Context
from reflux.auth import Auth
from reflux.protocol import AUTH_SLOT, LOGIN, LOGOUT, ROUTES_SLOT
from reflux.routes import route
from reflux.sdk import builders as b
from reflux.sdk.types import Accrete, Bind, JsType
from reflux.slots import Slot


def slots_of(ctx: Context) -> "DemoSlots":
    """The reference app's slots for this delivery. The names are the Protocol's; the wire sees names."""
    return ctx.slot  # type: ignore[return-value]


class _Change(Protocol):
    """The `name` family: an input's uplink is `name.change`."""

    change: Slot


class _Row(Protocol):
    """The `row` family. `remove` is a verb on `Slot`, so that name goes by subscript."""

    add: Slot

    def __getitem__(self, name: str) -> Slot: ...


class _Vault(Protocol):
    vault: Slot
    secret: Slot


class _Go(Protocol):
    """The nav's three targets — the frame's `dest` is the name."""

    home: Slot
    about: Slot
    demo: Slot


class DemoSlots(Protocol):
    """The reference app's slots, for the editor — the runtime only ever sees the names.

    Two halves: the ones the page *writes* (`echo`, `rows`, … — reached through `slots_of(ctx)`,
    which carries the delivery) and the ones the page *addresses* (`name.change`, `row.add`,
    `go.home`, … — reached through the module-level `slots`, which carries none). One protocol,
    because they are one namespace: the sink of an uplink and the handler that answers it are the
    same name (`slots.py`).
    """

    echo: Slot  # what the input last carried
    rows: Slot  # the list the tiles node reads
    archived: Slot  # what the last drop archived — a text slot, written by the dock's handler
    secret: Slot  # only a signed-in click writes it; every anonymous draw clears it
    routes: Slot  # the shell's reader — where the page is written

    name: _Change
    row: _Row
    vault: _Vault
    go: _Go

    def __call__(self, path: str) -> Slot: ...  # `reflux:login`, `reflux:logout`, `reflux:auth`

    # (the login form's answer is the framework's: it lands in the reserved `auth` region)

# Where a navigation form sends the client. The frame's `event` is the target's name.
GO_HOME, GO_ABOUT, GO_DEMO = Slot("go.home"), Slot("go.about"), Slot("go.demo")
GO = {GO_HOME.name: "/", GO_ABOUT.name: "/about", GO_DEMO.name: "/demo"}

# A card: a frame with the profile's `card` variant, its children stacked and its own height.
CARD = {"grid-auto-rows": "auto", "gap": "10px", "align-content": "start"}


def nav_bundle(label: str, dest: Slot) -> Accrete:
    """A one-button bundle — the vocabulary's only clickable, and the demo's way between pages.

    The press is the bundle's own submit: `submit=["button"]` names the click as the timing, and the
    bundle holds the exit, so the button only says "send this group" (ADR 0032 §3).
    """
    return b.bundle(b.button(label, sink=dest), sink=dest, submit=["button"], id=f"nav-{dest.name}")


def row_node(row: dict, ctx: Context) -> Accrete:
    """One row: a bundle (the ✕ that removes it) around a draggable frame (the cargo).

    The two ways out of a row are different mechanisms on purpose: the button is an uplink on the
    bundle's id, a drag is silent until a landing point says where it went (ADR 0034: the cargo is
    the dragged subtree, and a drop reports the dragged node's own id). So the row's bundle keeps
    `<row id>` — that is what `remove` addresses — and the cargo frame names itself `<row id>-cargo`,
    because one id per tree is the wire's rule and the drop has no other field to carry identity in.

    The two frames say how the row is divided: a bundle is a flex row whose items all grow, so the
    cargo takes the width (`flex: 1 1 auto`) and the ✕ keeps its own size and centres itself in the
    height it does not fill.
    """
    # `remove` is a verb on a slot, so this name is written with the subscript.
    return b.bundle(
        b.frame(b.text(row["text"]), draggable={"tag": "row"}, style={"flex": "1 1 auto"},
                id=f"{row['id']}-cargo"),
        b.frame(b.button("删", sink=slots.row["remove"]),
                style={"flex": "0 0 auto", "align-self": "center"}),
        sink=slots.row["remove"],
        submit=["button"],
        id=row["id"],
    )


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
        # A slot outlives a `create`, so the secret would outlive a LOGOUT too — the page is redrawn
        # when the connection unbinds. Clearing is therefore part of the draw, and only when there
        # is something to clear (`may_see_secret` is the app's own memory of having written it), so
        # an ordinary first draw sends nothing extra.
        if not ctx.data.get("user") and ctx.data.pop("may_see_secret", False):
            slots_of(ctx).secret.set(b.text(""))
        if not ctx.data.get("rows_seeded"):
            ctx.data["rows_seeded"] = True
            for row in self.rows:
                slots_of(ctx).rows.append(row_node(row, ctx))

    def home(self, ctx: Context) -> list[Accrete]:
        """The home page's content — the markers are `ctx.page`'s business, not the app's.

        It takes the delivery because its nodes name things: the slots they read (`source=`) and the
        dests they speak to (`sink=`) are handles, and a handle comes from the context that owns them.

        A title, two columns and a footnote, inside one frame that says so: the page root is a flex
        column with no gap of its own. The left column is what a value does on its way up (an echo, a
        list, a drag); the right one is the framework's credential verb and the gate in front of a
        landing point. Each card is a `frame` with the `card` variant, and its own gap — a bundle is
        a flex row and would line its fields up edge to edge, which is a form, not a page.
        """
        return [
            b.frame(
                b.frame(
                    b.text("演示", variant="heading-1"),
                    b.text("这个应用只用 SDK 写出来：回声、列表、表单、拖拽，加三条路由。", variant="muted"),
                    grid={"grid-template-rows": "auto auto"},
                    # The title is a grid item too: it spans both columns, so the two columns of
                    # cards start under it instead of beside it.
                    style={"grid-column": "1 / -1"},
                    id="home-title",
                ),
                b.frame(
                    b.frame(
                        b.text("回声", variant="heading-3"),
                        b.text(
                            "一个 input 在回车时把缓冲上行；上行不带包装，处理器拿到的 `data` 就是那个字符串。",
                            variant="muted",
                        ),
                        b.input(sink=slots.name.change, id="name-input"),
                        b.text(source=slots.echo, id="echo"),
                        grid=CARD,
                        variant="card",
                        id="card-echo",
                    ),
                    b.frame(
                        b.text("列表 · 拖拽", variant="heading-3"),
                        b.text(
                            "行的身份在 id 上：✕ 按 id 删，拖过落点也按 id 归档 —— 手势本身什么都不说，只有落点说话。",
                            variant="muted",
                        ),
                        b.bundle(b.button("加一行", sink=slots.row.add), sink=slots.row.add,
                                 submit=["button"], id="add-row"),
                        b.tiles(source=slots.rows, id="rows"),
                        # The landing point names its event and what it accepts; `accept` is one tag
                        # (or any), so cargo of another tag is refused without a frame — and a
                        # landing without a `sink` is a load error, which is why the two come
                        # together.
                        b.frame(
                            b.text("拖一行到这里归档"),
                            accept={"tag": "row"},
                            sink=slots("row.archive"),
                            grid={"place-items": "center"},
                            style={"border": "var(--border)", "border-style": "dashed",
                                   "min-height": "72px"},
                            id="archive",
                        ),
                        b.text(source=slots.archived, id="archived"),
                        grid=CARD,
                        variant="card",
                        id="card-rows",
                    ),
                    grid={"grid-template-rows": "auto auto", "gap": "16px", "align-content": "start"},
                    id="home-left",
                ),
                b.frame(
                    b.text("登录 · 门", variant="heading-3"),
                    b.text(
                        "这张表单说的是框架的动词 `reflux:login`：应用只写 verify 和 view，密码它从来读不到。",
                        variant="muted",
                    ),
                    # Two fields stacked beside the button: a bundle is a flex row, so the column is
                    # a frame inside it and the press stays a child of the bundle it belongs to.
                    b.bundle(
                        b.frame(
                            b.input(tag="user", id="f-user"),
                            b.input(tag="pass", sink=Bind(type=JsType.password), id="f-pass"),
                            grid={"grid-template-rows": "auto auto", "gap": "8px"},
                            id="login-fields",
                        ),
                        b.frame(
                            b.button("登录", sink=slots(LOGIN)),
                            style={"flex": "0 0 auto", "align-self": "end"},
                            id="login-press",
                        ),
                        sink=slots(LOGIN),
                        submit=["enter", "button"],
                        id="login",
                    ),
                    b.frame(source=slots(AUTH_SLOT), id="auth-region"),
                    # Behind a declaration: a click here from a visitor never reaches the handler.
                    b.bundle(b.button("私密", sink=slots("vault.secret")),
                             sink=slots("vault.secret"), submit=["button"], id="vault"),
                    b.text(source=slots.secret, id="secret"),
                    b.bundle(b.button("退出", sink=slots(LOGOUT)), sink=slots(LOGOUT),
                             submit=["button"], id="logout"),
                    grid=CARD,
                    variant="card",
                    id="card-login",
                ),
                # The footnote is a grid item too, and it spans: a text node has no style, so the
                # node that carries the placement is a frame around it.
                b.frame(
                    b.text(
                        "accrete 没有带 URL 的类型：页面之间靠上面那个表单提交，生产者回一帧新结构"
                        "加上新的路径标记，runtime 把标记镜像进地址栏。",
                        variant="muted",
                    ),
                    style={"grid-column": "1 / -1"},
                    id="home-note",
                ),
                grid={"grid-template-columns": "minmax(0, 1fr) minmax(280px, 360px)", "gap": "16px",
                      "align-items": "start"},
                id="home-grid",
            ),
        ]

    def about(self) -> list[Accrete]:
        return [
            b.text("关于", variant="heading-1"),
            b.text("这个示例应用只用 SDK 写出来：回声、列表、表单，加三条路由 —— /、/about 和走查。"),
            nav_bundle("回到演示", GO_HOME),
        ]

demo = Demo()  # the routes are module-level declarations, so they attach to one application


def shell(ctx: Context) -> Accrete:
    """The frame every page is drawn into: a header, and the `routes` reader.

    The header says where you are and carries the three nav bundles; a page turn replaces only the
    slot, so the nav survives every turn. The reader is `min-height: 0` because a grid item's
    automatic minimum is its content — without it this row grows with the page and the shell's `1fr`
    is only a wish. The reader scrolls, so a page may be taller than the window.
    """
    return b.frame(
        b.frame(
            b.text("reflux 参考应用", variant="heading-3"),
            nav_bundle("演示", GO_HOME),
            nav_bundle("关于", GO_ABOUT),
            nav_bundle("走查", GO_DEMO),
            grid={"grid-template-columns": "1fr auto auto auto", "gap": "8px", "align-items": "center"},
            id="nav",
        ),
        b.frame(
            source=slots(ROUTES_SLOT),
            id=ROUTES_SLOT,
            style={"min-height": "0", "overflow": "auto"},
        ),
        grid={"grid-template-rows": "auto 1fr", "gap": "16px", "height": "100vh",
              "padding": "18px 24px", "box-sizing": "border-box"},
        # `width: 100%` would resolve against `#main`, which is a flex item sized by its content —
        # so a narrow page would hand the shell a narrow width and the header would shrink with it.
        # The window's own units are the way out (`main.css` prints exactly this failure).
        style={"width": "min(1240px, 100vw)", "margin": "0 auto"},
        id="shell",
    )


def demo_view(ctx, state):
    """The demo's own login surface — the `view` seam, with the field names its page also uses."""
    lines = [b.text("演示登录", variant="heading-1")]
    if state == "refused":
        lines.append(b.text("用户或密码不对", variant="muted"))
    return b.frame(
        *lines,
        b.bundle(
            b.input(tag="user", id="auth-user"),
            b.input(tag="pass", sink=Bind(type=JsType.password), id="auth-pass"),
            b.button("确认登录", sink=slots(LOGIN)),
            sink=slots(LOGIN),
            submit=["enter", "button"],
            id="auth-form",
        ),
    )


def demo_verify(ctx, credentials, mode):
    """The demo's verifier: one account, in memory, and the framework does the rest.

    This is the entire authentication a deployment writes — `mode` is `login` or `signup`, so an
    app that creates accounts decides that here. The password is checked and dropped; nothing in
    this module stores it, logs it, or draws it.
    """
    del ctx, mode  # the demo has no roles and no second kind of account
    if credentials.get("user") == "ada" and credentials.get("pass") == "pw":
        return "user-ada"
    return None


@route("/", title="演示")
def home_page(ctx, match):
    demo.draw_home(ctx)


@route("/about", title="关于")
def about_page(ctx, match):
    ctx.page(*demo.about())


# The app itself. It is a module-level declaration so that a handler can be declared where it is
# written (`@app.on(...)` above it) — the same sugar `@route` uses one line up.
app = App(auth=Auth(verify=demo_verify, view=demo_view), shell=shell)

# The app's own table, typed: `@app.on(slots.name.change)` completes, and a name that is not in
# `DemoSlots` is an error rather than a handler nothing ever sends to. `ctx.slot` is this table with
# a device attached; `slots_of(ctx)` is where a write comes from.
slots: DemoSlots = app.slot  # type: ignore[assignment]  # `Slots` hands out `Slot`s; the names are the Protocol's


# --- handlers: change the app's data, push exactly that change ---------------------------------

@app.on(slots.name.change)
def on_name(ctx, frame) -> None:
    # An `input` uplinks its value alone (no wrapper): the frame's `data` is the string.
    demo.echo = frame["data"] if isinstance(frame["data"], str) else ""
    slots_of(ctx).echo.set(b.text(demo.echo))


@app.on(slots.row.add)
def on_add(ctx, frame) -> None:
    row = {"id": f"row-{demo.next_row}", "text": f"第 {demo.next_row} 行"}
    demo.next_row += 1
    demo.rows.append(row)
    slots_of(ctx).rows.append(row_node(row, ctx))


@app.on(slots.row["remove"])  # `remove` is a verb: the name goes by subscript
def on_remove(ctx, frame) -> None:
    row_id = frame.get("id")  # the row's form carried its identity up
    demo.rows = [row for row in demo.rows if row["id"] != row_id]
    slots_of(ctx).rows.remove(row_id)


@app.on(slots("row.archive"))
def on_archive(ctx, frame) -> None:
    """A drop: the landing point sends `{id, tag}` — the dragged frame's own id, and its tag."""
    cargo = (frame.get("data") or {}).get("id") or ""
    row_id = cargo.removesuffix("-cargo")
    row = next((r for r in demo.rows if r["id"] == row_id), None)
    if row is None:
        return
    demo.rows = [r for r in demo.rows if r["id"] != row_id]
    slots_of(ctx).rows.remove(row_id)
    slots_of(ctx).archived.set(b.text(f"已归档：{row['text']}"))


@app.on(slots("vault.secret"), auth=True)
def on_secret(ctx, frame) -> None:
    """Only a signed-in click gets here: the gate answered the rest before this handler ran."""
    ctx.data["may_see_secret"] = True
    slots_of(ctx).secret.set(b.text("机密内容"))


@app.on(slots(GO_HOME.name))
@app.on(slots(GO_ABOUT.name))
@app.on(slots(GO_DEMO.name))
def on_go(ctx, frame) -> None:
    """A submit that moves the client: the new structure and the new path marker."""
    ctx.go(GO[frame["dest"]])


# The walkthrough page brings its own four uplinks and the module hosts it draws with.
walkthrough.register(app)
walkthrough.install(app)


def make_app() -> App:
    """The demo's app — built when this module was imported, returned here.

    The name is a factory's because that is how a deployment names an app (`reflux.cli`,
    `App.serve_forever`, the gates). There is one app: its routes and handlers are module-level
    declarations, so importing twice gives one table, not two.
    """
    return app


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="examples.demo_app", description="Serve the reference app.")
    ap.add_argument("--port", type=int, default=8000, help="0 picks a free port (default: 8000)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--pace", type=float, default=walkthrough.settings.pace,
                    help="seconds per typewriter chunk on the walkthrough (default: 0.03)")
    ap.add_argument("--hold", type=float, default=walkthrough.settings.hold,
                    help="seconds between the walkthrough's beats (default: 0.35)")
    args = ap.parse_args(argv)
    walkthrough.settings.pace = args.pace
    walkthrough.settings.hold = args.hold
    app = make_app()
    if args.port == 0:
        server = app.make_server(0, args.host)
        print(f"[reflux] serving the reference app on http://{args.host}:{server.server_address[1]}/", flush=True)
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