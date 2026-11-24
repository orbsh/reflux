"""The reference application: what a reflux app looks like, written with the SDK and `wire`.

    python3 -m examples.zh.demo_app --port 8000

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
import json

from reflux.app import App, Context
from reflux.auth import Auth
from reflux.protocol import AUTH_SLOT, LOGIN, LOGOUT, ROUTES_SLOT
from reflux.routes import Routes
from reflux.server import Request, Response
from reflux.sdk import builders as b
from reflux.sdk.types import Accrete, Bind, JsType
from reflux.slots import Slot

from . import demo_slots
from .demo_slots import GO, GO_ABOUT, GO_CHAT, GO_DEMO, GO_HOME, DemoSlots, slots_of


# 一张卡片：带 profile `card` 变体的 frame，子节点竖排，高度由自己撑。
CARD = {"grid-auto-rows": "auto", "gap": "10px", "align-content": "start"}


def nav_bundle(label: str, dest: Slot) -> Accrete:
    """一个按钮的 bundle —— 词表里唯一的可点击物，也是演示里页与页之间的走法。

    按下就是 bundle 自己的提交：`submit=["button"]` 把这次点击命名为时机，出口也归 bundle 持有，
    所以按钮只说"发这一组"（ADR 0032 §3）。
    """
    return b.bundle(b.button(label, sink=dest), sink=dest, submit=["button"], id=f"nav-{dest.name}")


def row_node(row: dict) -> Accrete:
    """一行：一个 bundle（删掉它的那个 ✕）套着一个可拖的 frame（货物）。

    一行有两条出路，用两种机制是故意的：按钮是按 bundle 的 id 上行，拖拽则一声不响，直到落点说出
    它去了哪（ADR 0034：货物就是被拖的子树，落点报告被拖节点自己的 id）。所以这一行的 bundle 保留
    `<行 id>` —— `remove` 寻址的就是它 —— 而货物 frame 给自己取名 `<行 id>-cargo`，因为"一棵树里
    一个 id"是 wire 的规矩，落点也没有别的字段能携带身份。

    两个 frame 说明这一行怎么分：bundle 是一行 flex，条目都长，于是货物拿走宽度（`flex: 1 1 auto`），
    而 ✕ 保持自己的尺寸，并在它没占满的高度里居中。
    """
    # `remove` 在槽上是动词，所以这个名字要用下标写。
    return b.bundle(
        b.frame(b.text(row["text"]), draggable={"tag": "row"}, style={"flex": "1 1 auto"},
                id=f"{row['id']}-cargo"),
        b.frame(b.button("删", sink=slots.row["remove"]),
                style={"flex": "0 0 auto", "align-self": "center"}),
        sink=slots.row["remove"],
        submit=["button"],
        id=row["id"],
    )


class State:
    """一次访问留下的东西 —— 演示的全部业务状态。

    放在模块级，因为处理器也是模块级的声明（`@app.on(...)`），而一条连接一页意味着一个对象就够了：
    真正多用户的写法会把它挂在设备上（`ctx.data`），下面的 `rows_seeded` 就是这么做的。
    """

    def __init__(self) -> None:
        self.echo = ""
        self.rows = [{"id": "row-1", "text": "第一行"}, {"id": "row-2", "text": "第二行"}]
        self.next_row = 3


state = State()


def shell(ctx: Context) -> Accrete:
    """每一页都画在里面的那个 frame：一个页头，和 `routes` 这个读槽。

    页头说明你在哪里，并带着三个导航 bundle；翻页只替换那个槽，所以导航在每次翻页后都还在。读槽是
    `min-height: 0`，因为 grid 条目的自动最小尺寸就是它的内容 —— 不写这一条，这一行会随页面一起长高，
    外壳的 `1fr` 就只是个愿望。读槽会滚动，所以一页可以比窗口更高。
    """
    return b.frame(
        b.frame(
            b.text("reflux 参考应用", variant="heading-3"),
            nav_bundle("演示", GO_HOME),
            nav_bundle("关于", GO_ABOUT),
            nav_bundle("走查", GO_DEMO),
            nav_bundle("对话", GO_CHAT),
            grid={"grid-template-columns": "1fr auto auto auto auto", "gap": "8px", "align-items": "center"},
            id="nav",
        ),
        b.frame(
            source=slots(ROUTES_SLOT),
            id=ROUTES_SLOT,
            style={"min-height": "0", "overflow": "auto"},
        ),
        grid={"grid-template-rows": "auto 1fr", "gap": "16px", "height": "100vh",
              "padding": "18px 24px", "box-sizing": "border-box"},
        # `width: 100%` 会对着 `#main` 解析，而它是按内容定尺寸的 flex 条目 ——
        # 于是窄页面会把一个窄宽度交给外壳，页头跟着一起缩。
        # 出路是用窗口自己的单位（`main.css` 里印的就是这个失败）。
        style={"width": "min(1240px, 100vw)", "margin": "0 auto"},
        id="shell",
    )


def demo_view(ctx, state):
    """演示自己的登录面 —— `view` 这个接缝，字段名与它的页面用的是同一套。
    """
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
    """演示的验证器：一个账号，在内存里，其余都交给框架。

    这就是一次部署要写的全部认证 —— `mode` 是 `login` 或 `signup`，所以创建账号的应用在这里决定这件事。
    密码被核对完就丢掉；这个模块里没有任何地方存它、记它、画它。
    """
    del ctx, mode  # 这个演示没有角色，也没有第二种账号
    if credentials.get("user") == "ada" and credentials.get("pass") == "pw":
        return "user-ada"
    return None


# 应用本体。写成模块级声明，是为了处理器可以写在它所在的地方（上面的
# `@app.on(...)`）—— 与 `@route` 用在页面上方是同一套糖。
app = App(routes=Routes(), auth=Auth(verify=demo_verify, view=demo_view), shell=shell)

# 应用自己的表，带类型：`@app.on(slots.name.change)` 有补全，而不在
# `DemoSlots` 里的名字是错误，不是一个永远没人发的处理器。`ctx.slot` 是
# 这张表挂上设备；写入来自 `slots_of(ctx)`。
slots: DemoSlots = demo_slots.table(app)


@app.route("/", title="演示")
def home_page(ctx, match):
    """词表，摆成卡片：一个值在上行的路上做了什么，以及挡在它前面的一道门。

    页面根是一列 flex，自己没有间隙，所以分法由页面自己说：横跨两列的标题，左边一列（回声、列表、
    拖拽），右边一列（框架的凭据动词），再加一条同样横跨的脚注。每张卡片是带 `card` 变体的 `frame`，
    间隙写在它自己身上 —— bundle 是一行 flex，会把字段贴边排开，那是表单的样子，不是页面的样子。

    翻页就是 `ctx.page(...)`，别的什么都不做：运行时读的两个标记（`reflux:path`、`reflux:title`）
    由它替你写好，放在它画的那个节点前面。
    """
    ctx.page(
        b.frame(
            b.frame(
                b.text("演示", variant="heading-1"),
                b.text("这个应用只用 SDK 写出来：回声、列表、表单、拖拽，加三条路由。", variant="muted"),
                grid={"grid-template-rows": "auto auto"},
                # 标题也是个 grid 条目：它横跨两列，所以两列卡片从它下面开始，而不是在它旁边。
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
                    # 落点说出它的事件和它收什么；`accept` 是一个 tag（或 any），所以别的 tag 的
                    # 货物不发一帧就被拒 —— 而一个没有 `sink` 的落点是加载错误，所以这两样
                    # 总是成对出现。
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
                # 两个字段竖着排在按钮旁边：bundle 是一行 flex，所以这一列是它里面的一个
                # frame，而那次按下仍是它所属 bundle 的子节点。
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
                # 在一句声明后面：访客在这里的点击永远到不了处理器。
                b.bundle(b.button("私密", sink=slots("vault.secret")),
                         sink=slots("vault.secret"), submit=["button"], id="vault"),
                b.text(source=slots.secret, id="secret"),
                b.bundle(b.button("退出", sink=slots(LOGOUT)), sink=slots(LOGOUT),
                         submit=["button"], id="logout"),
                grid=CARD,
                variant="card",
                id="card-login",
            ),
            # 脚注也是 grid 条目，而且横跨：文本节点没有样式，所以承载位置的是套着它的
            # 一个 frame。
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
    )

    # 槽活得比一次 `create` 长（树被替换，数据面不会），所以这些行每条连接只种一次 ——
    # 第二次进来再追加一遍就会翻倍。它和别的写入一样是一次发送，所以是
    # `ctx.slot.rows.append(...)`，而不是树的一部分。
    if not ctx.data.get("rows_seeded"):
        ctx.data["rows_seeded"] = True
        for row in state.rows:
            slots_of(ctx).rows.append(row_node(row))
    # The same rule cuts the other way for the secret: the slot would outlive a `退出`, so the draw
    # 同一条规矩对私密那格反过来用：槽会活得比一次 `退出` 长，所以画面把它清掉 ——
    if not ctx.data.get("user") and ctx.data.pop("may_see_secret", False):
        slots_of(ctx).secret.set(b.text(""))


@app.route("/about", title="关于")
def about_page(ctx, match):
    """第二条路由：同一个形状，地址栏、深链或导航都能到。
    """
    ctx.page(
        b.text("关于", variant="heading-1"),
        b.text("这个示例应用只用 SDK 写出来：回声、列表、表单，加三条路由 —— /、/about 和走查。"),
        nav_bundle("回到演示", GO_HOME),
    )


# --- 处理器：改应用的数据，只推那一处改动 ------------------------------------------

@app.on(slots.name.change)
def on_name(ctx, frame) -> None:
    # 一个 `input` 上行时只带值（没有包装）：帧的 `data` 就是那个字符串。
    state.echo = frame["data"] if isinstance(frame["data"], str) else ""
    slots_of(ctx).echo.set(b.text(state.echo))


@app.on(slots.row.add)
def on_add(ctx, frame) -> None:
    row = {"id": f"row-{state.next_row}", "text": f"第 {state.next_row} 行"}
    state.next_row += 1
    state.rows.append(row)
    slots_of(ctx).rows.append(row_node(row))


@app.on(slots.row["remove"])  # `remove` 是动词：这个名字要用下标访问
def on_remove(ctx, frame) -> None:
    row_id = frame.get("id")  # 这一行的表单把它的身份带了上来
    state.rows = [row for row in state.rows if row["id"] != row_id]
    slots_of(ctx).rows.remove(row_id)


@app.on(slots("row.archive"))
def on_archive(ctx, frame) -> None:
    """一次落点：落点发来 `{id, tag}` —— 被拖的 frame 自己的 id，和它的 tag。
    """
    cargo = (frame.get("data") or {}).get("id") or ""
    row_id = cargo.removesuffix("-cargo")
    row = next((r for r in state.rows if r["id"] == row_id), None)
    if row is None:
        return
    state.rows = [r for r in state.rows if r["id"] != row_id]
    slots_of(ctx).rows.remove(row_id)
    slots_of(ctx).archived.set(b.text(f"已归档：{row['text']}"))


@app.on(slots("vault.secret"), auth=True)
def on_secret(ctx, frame) -> None:
    """只有已登录的点击能到这里：其余的在处理器跑之前就被门答掉了。
    """
    ctx.data["may_see_secret"] = True
    slots_of(ctx).secret.set(b.text("机密内容"))


@app.on(slots(GO_HOME.name))
@app.on(slots(GO_ABOUT.name))
@app.on(slots(GO_DEMO.name))
@app.on(slots(GO_CHAT.name))
def on_go(ctx, frame) -> None:
    """一次把客户端送走的提交：新结构，加上新的路径标记。
    """
    ctx.go(GO[frame["dest"]])


@app.mount("/status")
def status(request: Request) -> Response:
    """同一张表里的一个普通 HTTP 路由 —— 给运营它的人看，不关乎页面。

    帧是页面被画出来的方式；而这是监控、脚本或负载均衡器提问的方式。它不是页面，没有设备，答的是
    JSON：这个应用声明了哪些路由、旁边挂了什么、有几条连接活着、它用过的每一个名字（slots、dests、
    宿主事件 —— 一个名字空间），以及那些计数器。
    """
    return Response(
        200,
        json.dumps(
            {
                "ok": True,
                "routes": [declared.path for declared in app.routes],
                "mounts": sorted(app.mounts),
                "devices": len(app.live()),
                "slots": sorted(app.declared),
                "stats": dict(app.stats),
            },
            ensure_ascii=False,
        ),
        "application/json",
    )


# 住在各自模块里的两页：导入它们就是在这个应用上声明它们的路由（它们需要
# `app` 已存在，所以这两行 import 放在这里而不是文件顶部）。
from . import demo_chat  # noqa: E402
from .demo import page as walkthrough  # noqa: E402

# 走查页自带四条上行和它画图用的模块宿主；对话页在它声明页面的地方声明它那两条。
walkthrough.register(app)
walkthrough.install(app)
demo_chat.register(app, slots)


def make_app() -> App:
    """演示的应用 —— 本模块被导入时建好，在这里交出去。

    名字是工厂式的，因为部署就是这么给应用命名的（`reflux.cli`、`App.serve_forever`、各个门）。
    只有一个应用：它的路由与处理器都是模块级声明，所以导入两次得到一张表，不是两张。
    """
    return app


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="examples.zh.demo_app", description="Serve the reference app.")
    ap.add_argument("--port", type=int, default=8000, help="0 picks a free port (default: 8000)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--pace", type=float, default=walkthrough.settings.pace,
                    help="seconds per typewriter chunk on the walkthrough (default: 0.03)")
    ap.add_argument("--hold", type=float, default=walkthrough.settings.hold,
                    help="seconds between the walkthrough's beats (default: 0.35)")
    ap.add_argument("--model", choices=("scripted", "openai"), default="scripted",
                    help="what answers on /chat (default: scripted, offline)")
    ap.add_argument("--delay", type=float, default=demo_chat.settings.delay,
                    help="seconds between the chat's chunks (default: 0.02)")
    ap.add_argument("--window", type=int, default=demo_chat.settings.window,
                    help="turns of chat context the model sees (default: 12)")
    args = ap.parse_args(argv)
    walkthrough.settings.pace = args.pace
    walkthrough.settings.hold = args.hold
    demo_chat.settings.delay = args.delay
    demo_chat.settings.window = args.window
    demo_chat.settings.model = demo_chat.OpenAI() if args.model == "openai" else demo_chat.Scripted(window=args.window)
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