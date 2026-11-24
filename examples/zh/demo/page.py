"""走查页：fluxen 自己的故事，作为 `/demo` 贡献给参考应用。

    python3 -m examples.zh.demo_app --port 8000      # 然后 /demo，或导航里的「走查」

`fluxen/examples/walkthrough.py` 是一个消息框，把两张图、三个雷达、一张复核表、两个 3D 模型、一个代码编辑器
和一张不断生长的关系图流进它自己。那边剧本按键盘的节奏向 `stage` 的控制台 POST 帧（一步一个 `Enter`），终端
就是控制器；这里这个故事是参考应用的一条路由，剧本在服务器上为要它的那台设备跑，窗口角落的一个浮动按钮负责
播放、暂停、继续、重播。

这一页是四个区，每个区读一个槽 —— 渲染器自己那份笔记要的岛形（`fluxen/docs/ideas/islands.md`：一页分几个区，
每区一个槽，部件是声明的而不是加载的）：

    graph    左列：一个原生 forcegraph，喂给它累积快照
    stream   右列：一行，每个子节点绑在自己的槽上
    pins     拖到窗口边缘那条轨道上的碎片
    control  浮动按钮，和说明正走到哪一拍的那行字

有两件事值得点出来，因为它们就是这一页写成这样的原因：

- **一拍只写槽，绝不重画页面。** 一次槽写入只唤醒它的读者，所以一张图出现只重绘它那一条，不会重建消息，也
  不会重挂已经起来的 3D 查看器。这就是为什么那一行的每个子节点各有一个槽，也是为什么页面每轮只画一次。
- **按钮的标签是一个节点，不是绑在槽上的字符串。** `button_` 从 `source.default` 读它的标签
  （`fluxen/crates/ui_core/src/widgets/button.rs`），所以标签不可能来自槽；控制区里挂的是
  `frame(source=control)`，播放器写的是"当前状态长什么样"的那个**节点**。一个 frame 的 `source` 挂一个节点
  （ADR 0027），所以一个区、一个槽、四种状态，不翻页（翻页会把那一行里的每个模块重挂一遍）。

播放状态挂在 `device.data` 上：一个 socket 就是一台设备，所以两个观看者各跑各的剧本，关掉标签页就结束。
不共享，不持久。

内容是 `scene.py` 的（文案、图表 spec、一张图）—— 本模块是播放器，它不知道故事说了什么。
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from reflux import Context, Match
from reflux.sdk import h
from reflux.sdk.types import Accrete, Bind
from reflux.slots import Slot

from . import scene

__all__ = [
    "BEATS",
    "PAGE",
    "PRESENT",
    "ROW_ID",
    "Run",
    "Settings",
    "Walkthrough",
    "install",
    "page",
    "register",
    "settings",
    "slots_of",
    "start",
    "state",
]

# ---- 这一页画图用的模块宿主 -------------------------------------------

HERE = Path(__file__).resolve().parents[2]  # 仓库根：examples/zh/demo/ 在下面两级
VENDOR = HERE / "www" / "static" / "vendor"
ASSETS = Path(
    os.environ.get("REFLUX_ASSETS", HERE.parent / "fluxen" / "examples" / "renderer" / "assets")
)

CHART_URL = "/assets/g2chart/index.js"
VIEWER_URL = "/assets/3dbrowser/index.js"
SPLAT_URL = "/assets/splatviewer/index.js"
EDITOR_URL = "/assets/editor/index.js"
SHOE_URL = "/assets/3dbrowser/MaterialsVariantsShoe.glb"
TRUCK_URL = "/assets/splatviewer/truck.ksplat"


def _find(name: str, probe: str) -> Path | None:
    """一个模块的目录：先找本地 vendor 副本，再找 fluxen 检出。
    """
    for where in (VENDOR / name, ASSETS / name):
        if (where / probe).exists():
            return where
    return None


CHART = _find("g2chart", "index.js")
VIEWER = _find("3dbrowser", "index.js")
SPLAT = _find("splatviewer", "index.js")
EDITOR = _find("editor", "index.js")
# 编辑器模块自己加载 `../monaco/vs/…`，那棵树里没有 `index.js` —— 加载器的
# 入口是 `vs/loader.js`，探针命名的就是它。
MONACO = _find("monaco", "vs")

MOUNTS: dict[str, Any] = {
    "/assets/g2chart": CHART,
    "/assets/3dbrowser": VIEWER,
    "/assets/splatviewer": SPLAT,
    "/assets/editor": EDITOR,
    "/assets/monaco": MONACO,
}

# 这一页能画什么，只问一次：不在磁盘上的目录什么都不挂，它的 URL 答 404，
# 所以 `/status` 报这一项，读者能分辨"文件缺了"和"页面是空的"。
PRESENT: dict[str, bool] = {
    "chart": CHART is not None,
    "viewer": VIEWER is not None,
    "splat": SPLAT is not None,
    "editor": EDITOR is not None,
    "monaco": MONACO is not None,
}


def install(app: Any) -> None:
    """把磁盘上存在的每个模块目录都挂出去 —— 这是应用的表，不是页面的。

    这些都不进 git（`www/static/vendor/` 被忽略，3D 查看器带一个模型有 30 MB），所以每个都从它实际
    在的地方提供服务。背后什么都没有的宿主会在屏幕上显示成一个 bug，所以这一页说出它找过哪里，
    而不是画一个空盒子。
    """
    for path, where in MOUNTS.items():
        if where is not None:
            app.mount(path, where)


# ---- 名字 -----------------------------------------------------------------

# 这一页的四条上行。一个名字既是槽又是上行（ADR 0023）：轨道的 `sink` 就是
# `PIN`，而回答它的处理器也注册在同一个名字下。
TOGGLE = Slot("demo.toggle")
PIN = Slot("demo.pin")
SAVE = Slot("demo.save")
REVIEW = Slot("demo.review")


class Walkthrough(Protocol):
    """这一页的槽 —— 给编辑器看的视图；wire 只看得见名字。

    这里每个名字都是 `demo.<字段>`，所以一个句柄（`ctx.slot("demo")`）就能拿到全部，页面写
    `s.stream`，而不是写字符串。
    """

    graph: Slot  # 左列的关系图
    stream: Slot  # 右列的那一行
    pins: Slot  # 拖到轨道上落地的东西
    control: Slot  # 浮动按钮那个节点
    beat: Slot  # 正走到哪一拍
    echo: Slot  # 应用对最近一次上行的答复
    analytics: Slot  # 引言那一段
    trend: Slot  # 30 天那张图的 spec
    radar_rd: Slot
    radar_mkt: Slot
    radar_ops: Slot
    summary: Slot
    review_form: Slot  # 表与表单：一个节点，所以它们一次到场
    review_rows: Slot  # 表里的行
    say_car: Slot
    intro_car: Slot
    say_shoe: Slot
    intro_shoe: Slot
    say_patch: Slot
    patch_code: Slot
    say_graph: Slot
    toggle: Slot  # == TOGGLE：轨道的和按钮的 sink
    pin: Slot
    save: Slot
    review: Slot


def slots_of(ctx: Context) -> "Walkthrough":
    """一次投递里这一页的名字 —— `ctx.slot("demo")` 套着一层，于是 `s.stream` 就是 `demo.stream`。
    """
    return ctx.slot("demo")  # type: ignore[return-value]


PAGE = "/demo"
ROW_ID = "demo-row"
TEXT_VALUE = "/source/default"  # 指向槽里那个文本节点的指针
TREND_DATA = "/source/default/data"  # 指向折线 spec 各数据行的指针
PIN_TAG = "snippet"  # 轨道只收这样打 tag 的货物（ADR 0034）


@dataclass
class Settings:
    """故事说得多快 —— 部署的选择，从命令行填。
    """

    pace: float = 0.03  # 每个打字机块几秒（每块 3 个字符）
    hold: float = 0.35  # 拍与拍之间几秒
    day: float = 0.12  # 折线每追加一天几秒


settings = Settings()


@dataclass
class Run:
    """一台设备的播放：它能说什么、停在哪、图上显示什么。

    `phase` 是显式写的，不从线程推断 —— 一个还没起的线程和一个正走到一拍中间的线程对同一个问题
    回答不同，而按钮必须知道自己处在哪一种。
    """

    phase: str = "idle"  # 阶段：idle | playing | paused | done
    beat: int = 0  # 屏幕上那一拍的序号（从 1 起）；0 = 还没画
    label: str = ""
    revealed: set[str] = field(default_factory=lambda: set(scene.GRAPH_SEED))
    resume: threading.Event = field(default_factory=threading.Event)  # 置位 = 剧本可以说话


def state(ctx: Context) -> Run:
    """这条连接的播放状态，挂在 `ctx.data` 上 —— 随连接一起结束。
    """
    run = ctx.data.get("demo")
    if run is None:
        run = Run()
        ctx.data["demo"] = run
    return run


# ---- 页面 ---------------------------------------------------------------

# 浮动控件的盒子。`style` 由 frame 自己内联写出，所以位置由页面说；
# `border: var(--border)` 是简写词元，不能摊开拼。
FLOAT = {
    "position": "fixed",
    "right": "24px",
    "bottom": "24px",
    "z-index": "50",
    "padding": "10px 14px",
    "background": "var(--bg)",
    "border": "var(--border)",
    "border-radius": "var(--round)",
    "box-shadow": "0 0.5rem 1.5rem rgba(0, 0, 0, 0.18)",
}

# 这一页正好一个窗口高，而且用窗口自己的单位这么说。`height: 100%` 在这里
# 没有可解析的对象：页面被挂进一个由内容定尺寸的节点（`#page-root`，
# `flex: 1 0 auto`），所以它的百分比就是页面自己的百分比。83 px 是这一页外面
# 那个外壳的实测值 —— 两个 16 px 内边距、12 px 间隙、39 px 的导航行。
WINDOW = "calc(100vh - 97px)"

# 落区：消息列右边缘里的一条带，压在页面上而不在页面里 ——
# 拖拽不能移动指针下面的东西。
RAIL = {
    "position": "absolute",
    "top": "0",
    "right": "0",
    "bottom": "0",
    "width": "12px",
    "z-index": "5",
    "border-radius": "var(--round)",
}


def control(label: str) -> Accrete:
    """浮动按钮，四种状态之一：播放 → 暂停 → 继续 → 重播。

    这个按钮是 bundle 的确认键（它有 sink，时机由 bundle 命名），标签由状态给 —— 所以整个节点
    走一个槽，而不是画进页面里。
    """
    return h.bundle(
        h.button(label, sink=TOGGLE),
        sink=TOGGLE,
        submit="button",
        id="demo-toggle",
    )


def page(ctx: Context, match: Match) -> None:
    """页面，以及每条连接一次的、控制区一开始装的东西。

    浮动控件的第一个节点是一次**发送**，和所有种子一样：页面提供结构，一个区的内容写进它的槽。
    种在这里按设备守卫，因为槽活得比一次 `create` 长 —— 画两次不能把同一个碎片追加两遍。
    """
    s: Walkthrough = slots_of(ctx)
    if not ctx.data.get("demo_seeded"):
        ctx.data["demo_seeded"] = True
        s.control.set(control("▶ 播放"))
        s.beat.set(h.text("未开始 · 右下角开始"))
        s.echo.set(h.text(""))
    ctx.page(
        h.frame(
            h.frame(  # 左列：一个区，一个槽
                h.forcegraph(
                    source=s.graph,
                    width="100%",
                    height="100%",
                    style={"fit_padding_px": 56},
                    id="graph",
                ),
                grid={"grid-template-rows": "1fr"},
                style={"min-height": "0", "min-width": "0"},
                id="demo-graph",
            ),
            h.frame(  # 右列：落下的东西、消息流、应用的答复
                h.tiles(source=s.pins, dir="row", wrap="wrap", id="pins"),
                # 消息流在自己的盒子里滚动：它装的那一行比任何窗口都高，
                # 而跟着它一起长的页面会把关系图的画布拖走（实测：3.9k 高的
                # forcegraph 挨着 600 宽的消息流）。
                h.frame(
                    h.tiles(source=s.stream, id="stream"),
                    grid={"grid-template-rows": "1fr"},
                    style={"overflow": "auto", "min-height": "0"},
                    id="stream-box",
                ),
                h.text(source=s.echo, variant="muted", id="echo"),
                h.frame(accept={"tag": PIN_TAG}, sink=s.pin, style=RAIL, id="rail"),
                grid={"grid-template-rows": "auto 1fr auto"},
                style={"min-height": "0", "min-width": "0", "position": "relative", "padding-right": "18px"},
                id="demo-stream-column",
            ),
            h.frame(  # 控制区：固定在窗口上，只画一次
                h.frame(source=s.control, id="demo-control"),
                h.text(source=s.beat, variant="muted", id="demo-beat"),
                grid={"grid-template-columns": "auto auto", "gap": "10px", "align-items": "center"},
                style=FLOAT,
                id="demo-playback",
            ),
            grid={"grid-template-columns": "minmax(0, 1fr) minmax(360px, 620px)", "gap": "12px"},
            style={"height": WINDOW, "min-height": "0", "box-sizing": "border-box"},
            id="demo-page",
        )
    )


# ---- 这一行 -------------------------------------------------------------

def band(*children: Accrete, rows: str, columns: str | None = None, id: str) -> Accrete:
    """一个无边框容器，给它的图表一个确定的尺寸（ADR 0009）。

    画布自己没有尺寸：它挂上去的是 100×100 的面，页面看着一片空白、控制台一个错都不报，所以尺寸
    只能来自它坐的那个盒子。
    """
    grid: dict[str, str] = {"grid-template-rows": rows}
    if columns is not None:
        grid["grid-template-columns"] = columns
    return h.frame(*children, grid=grid, id=id)


def pin_tile(name: str, title: str) -> Accrete:
    """这一行里唯一可拖的单位：货物就是这棵子树，在 dragstart 时读出（ADR 0034）。

    `attrs.draggable` 把这个盒子标成 `snippet`，右侧轨道只 `accept` 这个 tag，落地的是 `{id, kind}`
    —— 源自己不加任何尺寸或样式，所以读者看见的是它里面那个碎片。
    """
    return h.frame(
        h.text(f"≡ 把「{title}」拖到右边", variant="muted"),
        draggable={"tag": PIN_TAG},
        variant="card",
        id=f"pin-{name}",
    )


def row(s: Demo) -> Accrete:
    """一行，每个子节点绑在自己的槽上 —— 这就是一段流只重绘一截的原因。

    空的数据区不占位置（ADR 0012），所以盒子一开始什么都不装，一段一段长出来：图表、模型或编辑器
    在各自的载荷到达那一刻出现，屏幕上已有的东西不会被重建。
    """
    return h.frame(
        h.text(source=s.analytics, format="md", id="say-analytics"),
        pin_tile("analytics", "分析引言"),
        band(h.canvas(source=s.trend, url=CHART_URL, id="chart-trend"), rows="260px", id="band-trend"),
        band(
            h.canvas(source=s.radar_rd, url=CHART_URL, id="chart-rd"),
            h.canvas(source=s.radar_mkt, url=CHART_URL, id="chart-mkt"),
            h.canvas(source=s.radar_ops, url=CHART_URL, id="chart-ops"),
            rows="340px",
            columns="repeat(3, minmax(0, 1fr))",
            id="band-radar",
        ),
        h.text(source=s.summary, format="md", id="say-summary"),
        h.frame(source=s.review_form, id="review-here"),
        h.text(source=s.say_car, format="md", id="say-car"),
        h.canvas(source=s.intro_car, url=SPLAT_URL, width="100%", height="460px", id="car"),
        h.text(source=s.say_shoe, format="md", id="say-shoe"),
        h.canvas(source=s.intro_shoe, url=VIEWER_URL, width="100%", height="420px", id="shoe"),
        h.text(source=s.say_patch, format="md", id="say-patch"),
        h.canvas(source=s.patch_code, url=EDITOR_URL, width="100%", height="280px", id="editor"),
        h.text(source=s.say_graph, format="md", id="say-graph"),
        grid={"gap": "10px"},
        id=ROW_ID,
    )


REVIEW_FIELDS = [
    {"key": "score", "title": "复核项", "width": "7rem"},
    {"key": "name", "title": "姓名"},
    {"key": "dept", "title": "部门"},
    {"key": "avg", "title": "日均分", "width": "5rem", "align": "end"},
    {"key": "note", "title": "备注"},
]

# 每种字段在屏幕上叫什么 —— wire 的 `number` / `bool` / `text` 是渲染器的词，
# 读者的词是下面这些。
KINDS = {"number": "数字", "bool": "勾选", "text": "文本"}


def review_row(key: str, initial: Any, name: str, dept: str, avg: str, note: str) -> Accrete:
    """表格的一行：一个 `entry`，每格的 `selector` 就是那个字段的键。

    没有 table/thead/tr/td 这一族（ADR 0031 §4）：带 `fields` 的 `tiles` 按键放格子，表头由字段的
    标题推出来。
    """
    return h.entry(
        h.text(str(initial), selector="score"),
        h.text(name, selector="name"),
        h.text(dept, selector="dept"),
        h.text(avg, selector="avg"),
        h.text(note, selector="note"),
        id=f"review-{key}",
    )


def review_form(s: Demo) -> Accrete:
    """表（行从槽里来）与表单（bundle 能打包的那些字段）。

    两半都在这里，因为它们合不成一个：`bundle` 靠遍历自己的静态子节点认领字段（`hooks.rs`、`collect`），
    而一行从槽里来，就不在它的字段里。所以表是读数，它下面那三个输入是表单 —— 一次提交带
    `{zw, cj, sy}`，每行一个值，不管那一行那格是什么类型。
    """
    return h.bundle(
        # 一个竖盒子：bundle 是一行 flex，子节点并排会把散文挤成一列单词（实测）——
        # 里面的排法是页面的事。
        h.frame(
            h.text(
                "复核：上表是本轮的数据（行从槽里来），下面三格各自改一个值再提交 —— "
                "三种字段各一（数字 / 勾选 / 文本），提交沿 `demo.review` 上行。",
                format="md",
            ),
            h.tiles(
                fields=REVIEW_FIELDS,
                header={"selector": "review-head"},
                source=s.review_rows,
                id="review-table",
            ),
            h.frame(
                *(
                    h.input(
                        tag=key,
                        selector="score",
                        source=Bind(default=initial, type=kind),
                        placeholder=f"{name} · {KINDS.get(kind, kind)}",
                        id=f"field-{key}",
                    )
                    for key, kind, initial, name, *_ in scene.REVIEW
                ),
                h.button("提交复核", sink=s.review),
                grid={"grid-template-columns": "repeat(3, minmax(0, 1fr)) auto", "gap": "8px", "align-items": "center"},
                id="review-fields",
            ),
            grid={"grid-template-rows": "auto auto auto", "gap": "8px"},
            id="review-body",
        ),
        sink=s.review,
        submit=["enter", "button"],
        id="review-form",
    )


# ---- 各拍 ---------------------------------------------------------------

def payload(value: Any) -> Accrete:
    """一个槽的值，不带任何结构：一个 `frame`，它的 `source.default` **就是**载荷。

    `frame` 是唯一持有值的节点（ADR 0027），模块宿主从它槽里那个节点的 `source.default` 读载荷 ——
    图表 spec、图快照或一个场景就是这样到达宿主的。
    """
    return h.frame(source=Bind(default=value))


def hold(run: Run, seconds: float) -> None:
    """一个随剧本一起停的睡眠：暂停的时间不算在剧本里。

    `Event.wait` 不是睡眠 —— 事件已置位时它立刻返回，在这里恰好是错的形状。所以暂停是一个阻塞
    （无超时的 `wait()`），时钟是切片里的真睡眠，于是暂停能在 50 ms 内生效，又不牺牲节奏。
    """
    left = seconds
    while left > 0:
        if not run.resume.is_set():
            run.resume.wait()  # 暂停：阻塞到按钮改口
        span = min(left, 0.05)
        time.sleep(span)
        left -= span


def type_out(run: Run, slot: Slot, text: str) -> None:
    """一帧三个字，像模型吐词元那样 —— 而暂停就是等。

    暂停在每一块**之前**读，所以停下的剧本不再写新东西；已经在路上的那一块仍然会落地，这也是为什么
    门读的是一段安静窗口，而不是一帧。
    """
    for at in range(0, len(text), 3):
        run.resume.wait()
        slot.patch(TEXT_VALUE, text[at : at + 3], op="append")
        hold(run, settings.pace)


def grow(run: Run, s: Demo, label: str) -> None:
    """把到场到现在为止的快照推出去 —— 图随流一起长大。
    """
    ids = next((ids for name, ids in scene.GRAPH_REVEAL if name == label), ())
    if not ids:
        return
    run.revealed.update(ids)
    s.graph.set(payload(scene.graph_payload(run.revealed)))


def beat_row(ctx: Context, run: Run, s: Demo) -> None:
    """那一行、它将被写进去的六个文本槽，和图的第一个快照。
    """
    with ctx.turn():  # 盒子与它空着的几段一起到场，读者看得见
        s.stream.append(row(s))
        for slot in (s.analytics, s.summary, s.say_car, s.say_shoe, s.say_patch, s.say_graph):
            slot.set(h.text(""))  # 追加需要一个能装东西的节点
        s.graph.set(payload(scene.graph_payload(run.revealed)))


def beat_analytics(ctx: Context, run: Run, s: Demo) -> None:
    type_out(run, s.analytics, scene.ANALYTICS)


def beat_charts(ctx: Context, run: Run, s: Demo) -> None:
    """一帧里四份 spec：折线与三个雷达填满各自那一条。
    """
    with ctx.turn():
        for name, spec in (("trend", scene.TREND), *scene.RADARS.items()):
            getattr(s, name).set(payload(spec))


def beat_days(ctx: Context, run: Run, s: Demo) -> None:
    """一天一帧，每帧三次追加 —— 折线长到三十天，读者一路看着。
    """
    for day, *scores in scene.TAIL_DAYS:
        hold(run, settings.day)
        with ctx.turn():
            for dept, avg in zip(scene.DEPTS, scores):
                s.trend.patch(TREND_DATA, {"day": day, "avg": avg, "dept": dept}, op="append")


def beat_summary(ctx: Context, run: Run, s: Demo) -> None:
    type_out(run, s.summary, scene.SUMMARY)


def beat_review(ctx: Context, run: Run, s: Demo) -> None:
    with ctx.turn():  # 表一次到齐：它的 frame 和三行一起
        s.review_form.set(review_form(s))
        for key, _kind, initial, *cells in scene.REVIEW:
            s.review_rows.append(review_row(key, initial, *cells))


def beat_car(ctx: Context, run: Run, s: Demo) -> None:
    type_out(run, s.say_car, scene.SAY_CAR)
    s.intro_car.set(payload({"assets": {"scene": TRUCK_URL}, "camera": scene.TRUCK_CAMERA}))


def beat_shoe(ctx: Context, run: Run, s: Demo) -> None:
    type_out(run, s.say_shoe, scene.SAY_SHOE)
    s.intro_shoe.set(payload({"assets": {"shoe": SHOE_URL}}))


def beat_editor(ctx: Context, run: Run, s: Demo) -> None:
    """代码和两个模型一样是参数：Monaco 在载荷到达时才取。
    """
    type_out(run, s.say_patch, scene.PATCH)
    s.patch_code.set(payload({"code": scene.PATCH_CODE, "lang": "rust", "event": str(SAVE)}))


def beat_graph(ctx: Context, run: Run, s: Demo) -> None:
    type_out(run, s.say_graph, scene.SAY_GRAPH)


def beat_focus(ctx: Context, run: Run, s: Demo) -> None:
    """相当于一次搜索落点：相机飞向一簇，别的东西不离开。
    """
    snapshot = scene.graph_payload(run.revealed)
    snapshot["focus"] = {"ids": ["accrete", "content", "transport"], "seq": 1}
    s.graph.set(payload(snapshot))


BEATS: tuple[tuple[str, Callable[[Context, Run, Demo], None]], ...] = (
    ("消息入场", beat_row),
    ("分析引言", beat_analytics),
    ("图表落位", beat_charts),
    ("三十天", beat_days),
    ("摘要", beat_summary),
    ("复核表与表单", beat_review),
    ("泼溅车", beat_car),
    ("鞋的网格模型", beat_shoe),
    ("代码编辑器", beat_editor),
    ("关系图段落", beat_graph),
    ("距焦", beat_focus),
)


# ---- 播放器 -------------------------------------------------------------

def spawn(target: Callable[..., None], args: tuple) -> None:
    """把剧本放上线程。模块级的一个接缝，好让测试改成同步执行。
    """
    threading.Thread(target=target, args=args, daemon=True).start()


def play(ctx: Context) -> None:
    """剧本，一拍一拍地走。故意是同步的：线程是调用方的选择。
    """
    run = state(ctx)
    s: Walkthrough = slots_of(ctx)
    try:
        for index, (label, step) in enumerate(BEATS, start=1):
            run.resume.wait()  # 暂停的剧本不会开始下一拍
            run.beat, run.label = index, label
            s.beat.set(h.text(f"{index}/{len(BEATS)} · {label}"))
            step(ctx, run, s)
            grow(run, s, label)
            hold(run, settings.hold)
    except Exception as failure:  # 演示里的缺陷是屏幕上的一行字，不是一条死掉的线程
        run.phase = "done"
        s.control.set(control("↻ 重播"))
        s.beat.set(h.text(f"出错：{type(failure).__name__} · {failure}"))
        return
    run.phase = "done"
    s.control.set(control("↻ 重播"))
    s.beat.set(h.text("完 · 折线 30 天，复核可提交，编辑器可回传"))


def start(ctx: Context, run: Run) -> None:
    """清掉跑完一遍留下的东西，再把剧本放上线程。

    只清播放器自己写的：那一行（它的子节点由第一拍重新种，载荷由各自的拍重新设）和表的三行。
    **读者**拖到轨道上的东西留着 —— 重播这个故事不是撤销别人钉下的东西。
    """
    s: Walkthrough = slots_of(ctx)
    if run.beat:
        s.stream.remove(ROW_ID)
        for key, *_ in scene.REVIEW:
            s.review_rows.remove(f"review-{key}")
    run.phase = "playing"
    run.beat, run.label = 0, ""
    run.revealed = set(scene.GRAPH_SEED)
    run.resume.set()
    s.control.set(control("⏸ 暂停"))
    s.beat.set(h.text(f"0/{len(BEATS)} · 开始"))
    spawn(play, (ctx,))


def on_toggle(ctx: Context, frame: dict) -> None:
    """一个按钮，四种状态：播放 → 暂停 → 继续 → 重播。
    """
    run = state(ctx)
    s: Walkthrough = slots_of(ctx)
    if run.phase in ("idle", "done"):
        start(ctx, run)
        return
    if run.phase == "playing":
        run.phase = "paused"
        run.resume.clear()
        s.control.set(control("▶ 继续"))
        s.beat.set(h.text(f"已暂停 · {run.beat}/{len(BEATS)} · {run.label}"))
        return
    run.phase = "playing"
    run.resume.set()
    s.control.set(control("⏸ 暂停"))
    s.beat.set(h.text(f"{run.beat}/{len(BEATS)} · {run.label}"))


def fields(frame: dict) -> dict:
    """处理器的载荷：帧的 `data` 当一个袋子看，帧里没有时就是空的。

    这一页的每条上行都防御式地读 —— 来自模块或过期客户端的畸形帧是屏幕上的一行字，不是抛出去的
    处理器（抛出去也只会进日志）。
    """
    data = frame.get("data")
    return data if isinstance(data, dict) else {}


def on_pin(ctx: Context, frame: dict) -> None:
    """一次落点落在轨道上：货物自己的 id 与 kind，写在屏幕上（ADR 0034）。
    """
    s: Walkthrough = slots_of(ctx)
    data = fields(frame)
    ident = data.get("id")
    if not ident:
        s.echo.set(h.text("落点上收到一份没有 id 的货物，什么都没记"))
        return
    kind = data.get("kind") or data.get("tag") or "—"
    # 这一块是数据描述出来的（载荷只有 id 与 kind），所以按数据构造：`h.node` 与 `h.frame` 是同一条
    # 构造器，只是前者读起来像"一颗 pin 是什么"，而不是"我在这里造一个 frame"。
    s.pins.append(
        h.node(
            (
                "frame",
                {"variant": "card", "id": f"pin-{ident}"},
                [("text", {"variant": "muted"}, f"≡ {ident} · {kind}")],
            )
        )
    )
    s.echo.set(h.text(f"落点收到 {ident}（{kind}）"))


def on_save(ctx: Context, frame: dict) -> None:
    """编辑器里按 Ctrl/Cmd+S：代码连同语言，走表单用的同一条腿。
    """
    s: Walkthrough = slots_of(ctx)
    data = fields(frame)
    code = data.get("code")
    if not isinstance(code, str):
        s.echo.set(h.text("编辑器回传里没有 code，什么都没记"))
        return
    s.echo.set(h.text(f"编辑器回传 {len(code)} 字 · {data.get('lang') or '—'}"))


def on_review(ctx: Context, frame: dict) -> None:
    """表单的字段，按渲染器打包的样子 —— 一行一个键。
    """
    s: Walkthrough = slots_of(ctx)
    data = frame.get("data") if isinstance(frame.get("data"), dict) else {}
    if not data:
        s.echo.set(h.text("提交到了，但没有字段：这一帧只打包表单自己的具名字段"))
        return
    packed = ", ".join(f"{key}={value!r}" for key, value in data.items())
    s.echo.set(h.text(f"复核已提交：{packed}"))


# ---- 一个应用拿这一页做什么 ---------------------------------------------

def register(app: Any) -> None:
    """把这一页挂到应用上：它的路由，和页面所说的那些名字下的四个处理器。

    路由是调用式而不是装饰器，因为这个模块不能 import 应用：`python3 -m examples.zh.demo_app` 时
    应用模块是以 `__main__` 跑的。
    """
    app.route(PAGE, title="走查")(page)
    app.on(TOGGLE, on_toggle)
    app.on(PIN, on_pin)
    app.on(SAVE, on_save)
    app.on(REVIEW, on_review)
