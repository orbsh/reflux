"""参考应用：一个 reflux 应用长什么样，只用 SDK 和 `wire` 写出来。

    python3 -m examples.zh.demo_app --port 8000

四页、一个把它们包起来的外壳，一页对应应用由之构成的一种形状：

- `/` —— **词表**，摆成卡片。一个 `input` 在回车时把缓冲上行，一个 `text` 读处理器写进去的那个槽（回声）；
  行住在槽里、由 `tiles` 显示，每行的删除按钮把自己的身份抬上去；一行还可以当货物 —— 它的 frame 是
  `draggable`，把它拖到落点 frame 上就上行 `{id, tag}`，即被拖 frame 自己的 id，于是归档处理器能解析出手势
  永远给不出的东西（拖拽本身什么都不报告：只有落点报告）；一个 `loom` 携带它打包的每个字段
  （`{tag: value, …}`，ADR 0032）—— 那是 LOGIN 这个 loom，因为凭据是框架的事：出口是 `reflux:login`，
  应用只写 `verify` 与 `view`，密码在这里从来没被读过。它后面，`vault.secret` 声明为 `auth=True`，所以匿名
  点击打开登录面而到不了处理器，而同一个点击登录之后就落地（`退出` 是出去的走法）。
- `/about` —— 第二条路由，地址栏、深链、前进后退或导航都能到。
- `/chat` —— 对话页：每条连接一段对话，流式、可停、可拒；模型接缝在 `chat_model.py`。
- `/demo` —— 走查页，属于 `examples/zh/demo/`：fluxen 自己的故事，由一个浮动按钮播放，四个区各读一个槽。
  这一页是内容，住在示例里；本模块是"一个应用长什么样"，它像应用导入页面那样导入这一页。

**外壳**是这个应用自己的，不是框架的缺省：一个说你在哪里的页头，和一个页面被写进去的 `routes` 读槽。它每条
连接只画一次，所以翻页只替换一个槽，页头不动。它的读槽故意是 `min-height: 0` —— grid 条目的自动最小值就是它
的内容，不写这个零，那一行会跟着页面一起长高，而不是滚动它。

两条关于这套词表的事实决定了代码的形状，两样都由门量着：

- **一个 `button` 住在 `loom` 里**（`gate_t3_next`）：渲染器就把它挂在那里，而一次按下发送的是 loom 的
  `submit`（`submit=["button"]`）。所以"加一行""删一行""去另一页"都是一个按钮的 loom，而 frame 的 `id`
  就是 loom 自己的 id —— 一行的身份就是靠它上去又回来的。
- **accrete 没有带 URL 的类型**，所以没有可点的锚、也没有可拦截的东西：一次换页是生产者答回一帧新结构加一个
  新的路径标记（下面的 `go.home` / `go.about` / `go.demo`）。runtime 把这个标记镜像进地址栏。

这两个标记是普通节点，由 `www/static/reflux.js` 直接从 DOM 里读（`reflux:path`、`reflux:title`）；约定住在
`reflux.sdk.markers`（每页一次 `page()` 调用），因为页面自己的形状是 runtime 的契约，不是某个应用的私习。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from reflux.application import Context, create_app, gated
from reflux.protocol import AUTH_SLOT, LOGIN, LOGOUT, ROUTES_SLOT
from reflux.server import Request, Response
from reflux.sdk import h
from reflux.sdk.types import Accrete, JsType, Source
from reflux.slots import Slot

from . import demo_slots
from .demo_slots import GO, GO_ABOUT, GO_CHAT, GO_COUNTER, GO_DEMO, GO_HOME, GO_SETTINGS, DemoSlots, slots_of


# 一张卡片：带 profile `card` 变体的 frame，子节点竖排，高度由自己撑。
CARD = {"grid-auto-rows": "auto", "gap": "10px", "align-content": "start"}


def nav_loom(label: str, dest: Slot) -> Accrete:
    """一个按钮的 loom —— 词表里唯一的可点击物，也是演示里页与页之间的走法。

    按下就是 loom 自己的提交：`submit=["button"]` 把这次点击命名为时机，出口也归 loom 持有，
    所以按钮只说"发这一组"（ADR 0032 §3）。
    """
    return h.loom(h.button(label), sink=dest, submit=["button"], id=f"nav-{dest.name}")


def row_node(row: dict) -> Accrete:
    """一行：一个 loom（删掉它的那个 ✕）套着一个可拖的 frame（货物）。

    一行有两条出路，用两种机制是故意的：按钮是按 loom 的 id 上行，拖拽则一声不响，直到落点说出
    它去了哪（ADR 0034：货物就是被拖的子树，落点报告被拖节点自己的 id）。所以这一行的 loom 保留
    `<行 id>` —— `remove` 寻址的就是它 —— 而货物 frame 给自己取名 `<行 id>-cargo`，因为"一棵树里
    一个 id"是 wire 的规矩，落点也没有别的字段能携带身份。

    两个 frame 说明这一行怎么分：loom 是一行 flex，条目都长，于是货物拿走宽度（`flex: 1 1 auto`），
    而 ✕ 保持自己的尺寸，并在它没占满的高度里居中。
    """
    # `remove` 在槽上是动词，所以这个名字要用下标写。
    return h.loom(
        h.frame(h.text(row["text"]), draggable={"tag": "row"}, style={"flex": "1 1 auto"},
                id=f"{row['id']}-cargo"),
        h.frame(h.button("删"),
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

# 一个部署一个 app。演示用 `create_app()` 而不是框架那个单例，因为 zh 与 en 两棵树要在同一个进程里
# 并存（`test_two_trees`）：单例只有一个，两个演示会写进同一张表、同一个 dest 注册表。
app = create_app()


@app.hooks.shell()
def shell(ctx: Context) -> Accrete:
    """每一页都画在里面的那个 frame：一个页头，和 `routes` 这个读槽。

    页头说明你在哪里，并带着五个导航 loom；翻页只替换那个槽，所以导航在每次翻页后都还在。读槽是
    `min-height: 0`，因为 grid 条目的自动最小尺寸就是它的内容 —— 不写这一条，这一行会随页面一起长高，
    外壳的 `1fr` 就只是个愿望。读槽会滚动，所以一页可以比窗口更高。
    """
    # 页面选项先落地：槽的写是一次 send，而页面那一帧在 `_draw` 末尾才发，所以新连接的第一帧
    # 就带着用户的选择（ADR 0001 §5）。
    demo_settings.seed(ctx)
    return h.frame(
        h.frame(
            h.text("reflux 参考应用", variant="heading-3"),
            nav_loom("演示", GO_HOME),
            nav_loom("关于", GO_ABOUT),
            nav_loom("走查", GO_DEMO),
            nav_loom("对话", GO_CHAT),
            nav_loom("计数器", GO_COUNTER),
            nav_loom("设置", GO_SETTINGS),
            grid={"grid-template-columns": "1fr auto auto auto auto auto auto", "gap": "8px", "align-items": "center"},
            id="nav",
        ),
        h.frame(
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


@app.hooks.login_request()
def demo_view(ctx, state):
    """演示自己的登录面 —— `login.request` 这个接缝，字段名与它的页面用的是同一套。
    """
    lines = [h.text("演示登录", variant="heading-1")]
    if state == "refused":
        lines.append(h.text("用户或密码不对", variant="muted"))
    return h.frame(
        *lines,
        h.loom(
            h.input(tag="user", id="auth-user"),
            h.input(tag="pass", kind=JsType.password, id="auth-pass"),
            h.button("确认登录"),
            sink=slots(LOGIN),
            submit=["enter", "button"],
            id="auth-form",
        ),
    )


@app.hooks.inspect("/v1/inspect")  # 这张应用自己的声明，走 HTTP：路由、上行落点、槽名、口子
def inspect(data):
    """演示不裁剪：`data` 就是答案。真实部署在这里决定给谁看（`return 403, {"error": "..."}`）。"""
    return data


@app.hooks.login()
def demo_verify(ctx, credentials, mode):
    """演示的验证器：一个账号，在内存里，其余都交给框架。

    这就是一次部署要写的全部认证 —— `mode` 是 `login` 或 `signup`，所以创建账号的应用在这里决定这件事。
    密码被核对完就丢掉；这个模块里没有任何地方存它、记它、画它。

    返回值是判决：`(True, user_id, info)` 放行，`(False, 说明)` 拒绝。`info` 是应用自己的东西（这里没有），
    框架只把它在你需要的地方递回来（`ctx.session`）。
    """
    del ctx, mode  # 这个演示没有角色，也没有第二种账号
    if credentials.get("user") == "ada" and credentials.get("pass") == "pw":
        return (True, "user-ada", None)
    return (False, "用户或密码不对")

# 应用自己的表，带类型：`@app.on(slots.name.change)` 有补全，而不在
# `DemoSlots` 里的名字是错误，不是一个永远没人发的处理器。`ctx.slot` 是
# 这张表挂上设备；写入来自 `slots_of(ctx)`。
slots: DemoSlots = demo_slots.table(app)


@app.page("/", title="演示")
def home_page(ctx, match):
    """词表，摆成卡片：一个值在上行的路上做了什么，以及挡在它前面的一道门。

    页面根是一列 flex，自己没有间隙，所以分法由页面自己说：横跨两列的标题，左边一列（回声、列表、
    拖拽），右边一列（框架的凭据动词），再加一条同样横跨的脚注。每张卡片是带 `card` 变体的 `frame`，
    间隙写在它自己身上 —— loom 是一行 flex，会把字段贴边排开，那是表单的样子，不是页面的样子。

    翻页就是 `return` 那个节点，别的什么都不做：运行时读的两个标记（`reflux:path`、`reflux:title`）
    由框架按声明写好，放在它前面。

    这页也是两种落点的对照。**回声**、**加一行**、**私密**是闭包：一次请求一次回应，处理器写在发出
    它的那个按钮旁边，闭包拿到的就是事件的值，槽是它闭住的。**✕**、**落点**、**导航**仍是
    `@app.on` 的名字 —— 它们的身份不在页面里（一行一个 id，名字由行持有），而且名字必须先于任何
    一次绘制存在。走查页的 `echo` 是另一头：那个槽被拖拽落点和编辑器回传两个来源写，只有名字能表达
    「一个槽，多个来源」。
    """
    slots = slots_of(ctx)

    def echo(value: object) -> None:
        # 一个组提交的是它打包出来的对象：{字段: 值}。帧从外面来，所以不认识的东西给空串，不炸。
        text = value.get("name") if isinstance(value, dict) else None
        state.echo = text if isinstance(text, str) else ""
        slots.echo.set(h.text(state.echo))

    def add_row(value: object) -> None:
        row = {"id": f"row-{state.next_row}", "text": f"第 {state.next_row} 行"}
        state.next_row += 1
        state.rows.append(row)
        slots.rows.append(row_node(row))

    def reveal(value: object) -> None:
        # 只有已登录的点击能到这里：其余的在闭包之前就被门答掉了（`gated`）。
        ctx.data["may_see_secret"] = True
        slots.secret.set(h.text("机密内容"))

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
        slots_of(ctx).secret.set(h.text(""))
    return (
        h.frame(
            h.frame(
                h.text("演示", variant="heading-1"),
                h.text("这个应用只用 SDK 写出来：回声、列表、表单、拖拽，加三条路由。", variant="muted"),
                grid={"grid-template-rows": "auto auto"},
                # 标题也是个 grid 条目：它横跨两列，所以两列卡片从它下面开始，而不是在它旁边。
                style={"grid-column": "1 / -1"},
                id="home-title",
            ),
            h.frame(
                h.frame(
                    h.text("回声", variant="heading-3"),
                    h.text(
                        "一个输入框的出口是它所在的那个组：回车让组把 {字段: 值} 发给组的 sink，"
                        "字段自己的 `tag` 就是键。",
                        variant="muted",
                    ),
                    h.loom(h.input(tag="name", id="name-input"), sink=echo, submit=["enter"], id="echo-form"),
                    h.text(source=slots.echo, id="echo"),
                    grid=CARD,
                    variant="card",
                    id="card-echo",
                ),
                h.frame(
                    h.text("列表 · 拖拽", variant="heading-3"),
                    h.text(
                        "行的身份在 id 上：✕ 按 id 删，拖过落点也按 id 归档 —— 手势本身什么都不说，只有落点说话。",
                        variant="muted",
                    ),
                    h.loom(h.button("加一行"), sink=add_row,
                             submit=["button"], id="add-row"),
                    h.tiles(source=slots.rows, id="rows"),
                    # 落点说出它的事件和它收什么；`accept` 是一个 tag（或 any），所以别的 tag 的
                    # 货物不发一帧就被拒 —— 而一个没有 `sink` 的落点是加载错误，所以这两样
                    # 总是成对出现。
                    h.frame(
                        h.text("拖一行到这里归档"),
                        accept={"tag": "row"},
                        sink=slots("row.archive"),
                        grid={"place-items": "center"},
                        style={"border": "var(--border)", "border-style": "dashed",
                               "min-height": "72px"},
                        id="archive",
                    ),
                    h.text(source=slots.archived, id="archived"),
                    grid=CARD,
                    variant="card",
                    id="card-rows",
                ),
                grid={"grid-template-rows": "auto auto", "gap": "16px", "align-content": "start"},
                id="home-left",
            ),
            h.frame(
                h.text("登录 · 门", variant="heading-3"),
                h.text(
                    "这张表单说的是框架的动词 `reflux:login`：应用只写 verify 和 view，密码它从来读不到。",
                    variant="muted",
                ),
                # 两个字段竖着排在按钮旁边：loom 是一行 flex，所以这一列是它里面的一个
                # frame，而那次按下仍是它所属 loom 的子节点。
                h.loom(
                    h.frame(
                        h.input(tag="user", id="f-user"),
                        h.input(tag="pass", kind=JsType.password, id="f-pass"),
                        grid={"grid-template-rows": "auto auto", "gap": "8px"},
                        id="login-fields",
                    ),
                    h.frame(
                        h.button("登录"),
                        style={"flex": "0 0 auto", "align-self": "end"},
                        id="login-press",
                    ),
                    sink=slots(LOGIN),
                    submit=["enter", "button"],
                    id="login",
                ),
                h.frame(source=slots(AUTH_SLOT), id="auth-region"),
                # 在一句声明后面：访客在这里的点击永远到不了处理器。
                h.loom(h.button("私密"),
                         sink=gated(reveal), submit=["button"], id="vault"),
                h.text(source=slots.secret, id="secret"),
                h.loom(h.button("退出"), sink=slots(LOGOUT),
                         submit=["button"], id="logout"),
                grid=CARD,
                variant="card",
                id="card-login",
            ),
            # 脚注也是 grid 条目，而且横跨：文本节点没有样式，所以承载位置的是套着它的
            # 一个 frame。
            h.frame(
                h.text(
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



@app.page("/about", title="关于")
def about_page(ctx, match):
    """第二条路由：同一个形状，地址栏、深链或导航都能到。
    """
    return (
        h.text("关于", variant="heading-1"),
        h.text("这个示例应用只用 SDK 写出来：回声、列表、表单，加三条路由 —— /、/about 和走查。"),
        nav_loom("回到演示", GO_HOME),
    )


# --- 处理器：名字的落点（身份在页面里或跨页的那些） ---------------------------------

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
    slots_of(ctx).archived.set(h.text(f"已归档：{row['text']}"))


@app.on(slots(GO_HOME.name))
@app.on(slots(GO_ABOUT.name))
@app.on(slots(GO_DEMO.name))
@app.on(slots(GO_CHAT.name))
@app.on(slots(GO_COUNTER.name))
@app.on(slots(GO_SETTINGS.name))
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
from . import demo_chat, demo_counter, demo_settings  # noqa: E402
from .demo import page as walkthrough  # noqa: E402

# 走查页自带四条上行和它画图用的模块宿主；对话页在它声明页面的地方声明它那两条。
walkthrough.register(app)
walkthrough.install(app)
demo_chat.register(app, slots)
demo_counter.register(app)
demo_settings.register(app)


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
    ap.add_argument("--settings", default=".demo-settings.json",
                    help="where the settings page keeps its choices (default: ./.demo-settings.json)")
    args = ap.parse_args(argv)
    walkthrough.settings.pace = args.pace
    walkthrough.settings.hold = args.hold
    demo_chat.settings.delay = args.delay
    demo_chat.settings.window = args.window
    demo_chat.settings.model = demo_chat.OpenAI() if args.model == "openai" else demo_chat.Scripted(window=args.window)
    demo_settings.settings.path = Path(args.settings)
    demo_settings.settings.load()  # 已存的选择就是这个应用的开场白（ADR 0001 §5）
    app = make_app()
    demo_chat.share_http(app, demo_chat.settings.model)

    server = app.start(0 if args.port == 0 else args.port, args.host)
    print(f"[reflux] serving the reference app on http://{args.host}:{server.server_address[1]}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.stop()  # 钩子 → 共享会话 → 看门狗 → server，一处收尾
    return 0


if __name__ == "__main__":
    raise SystemExit(main())