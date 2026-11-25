"""设置页：core.css 的令牌面写进页面选项槽，本机立刻生效，服务端记住（ADR 0001）。

页面选项是 fluxen 的机制，不是这一页的发明：`#main` 没写 `data-config`，所以在它上面挂着的槽就叫缺省
名 `__CONFIG__`（fluxen ADR 0038 §2），槽里放一个对象，成员**逐个**决定——页面自己那一半先、远侧
（生产端）在后；渲染器再把标量成员镜像成文档根上的 `data-<member>`，浏览器侧的表（`www/static/reflux.js`
的 `TOKENS`）把它们落到 `:root` 的自定义属性。所以这一页没有新帧、没有新动作：

1. **写**：一个组的出口 `Sink(dest="__CONFIG__", scope="both", path="/")`——`both` 是"本地先改、同时
   上行"（fluxen ADR 0031 §1），一个组只有一个出口，所以这条需求没有别的合法形状。
2. **记**：`demo_app` 把上行交给 `on_config`，这里做白名单 + 值域校验 + 合并，随后节流落盘。
3. **起始值**：每台设备第一次被画时，外框把已存对象先 `set` 进这个槽，所以新连接、刷新、换设备的第一帧
   就带着用户的选择。

**导出的是一张表，不是一个一个字段**：`TOKENS` 说"core 的 `:root` 上有哪些可独立设置的令牌、各自是
什么种类"，页面按它生成控件、校验按种类选，浏览器侧那张表也按种类查。三处于是只有一份事实——名字
（去掉 `--` 就是 `:root` 上的变量名）与种类；加一个令牌是往表里加一行，不是改三处。

**颜色是 `oklch` 三元组**：成员值存 `L C H`（三个数），`oklch(...)` 只在 `reflux.js` 里合成为一次——
于是"颜色空间"是一个决定，不是散在十几个值里的字符串。空值 = 不设 = core 的缺省（成对的
`light-dark(a, b)` 也一起回来）。

**一设就两种配色模式都钉住**：`fg`／`bg`／`surface` 在 core 里是 `light-dark(浅, 深)` 成对值，而一个
成员只能带一个值。设置它们就等于替两种模式选同一个颜色；清空即回到成对缺省。这是 2026-11-25 定下的
取舍（另一条路是每种模式一个成员，真有那需求再开）。
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from reflux import Context
from reflux.sdk import h
from reflux.sdk.types import Accrete, Sink, Source

__all__ = [
    "CONFIG",
    "CORE",
    "DEFAULTS",
    "GROUPS",
    "KEYWORDS",
    "LABELS",
    "MEMBERS",
    "Store",
    "TOKENS",
    "flatten",
    "merge",
    "on_config",
    "page",
    "register",
    "seed",
    "state",
]

CONFIG = "__CONFIG__"  # fluxen 的页面选项槽：`#main` 上没有 `data-config`，就是缺省名

# core.css 的 `:root` 令牌面：名字（`--` 之后那一段）→ 种类。派生的两个不在这里：`--border-color` 缺省
# 是 `var(--secondary)`、`--border` 由宽／线型／色拼出来 —— 它们跟着表里的成员走。
TOKENS: dict[str, str] = {
    "fg": "color",
    "bg": "color",
    "surface": "color",
    "accent": "color",
    "primary": "color",
    "secondary": "color",
    "disabled": "color",
    "warn": "color",
    "error": "color",
    "border-color": "color",
    "round": "length",
    "input-round": "length",
    "border-width": "length",
    "border-style": "keyword",
}

# 页面上的分组：只是排版，不参与校验。
GROUPS: list[tuple[str, str, list[str]]] = [
    ("颜色 · oklch 三元组（L C H）", "color", [n for n, k in TOKENS.items() if k == "color"]),
    ("尺寸 · 数字（像素）", "length", [n for n, k in TOKENS.items() if k == "length"]),
    ("边框线型", "keyword", [n for n, k in TOKENS.items() if k == "keyword"]),
]

LABELS: dict[str, str] = {
    "fg": "前景 / 文字",
    "bg": "背景",
    "surface": "表面（卡片）",
    "accent": "强调色",
    "primary": "主色",
    "secondary": "次色",
    "disabled": "禁用",
    "warn": "警告",
    "error": "错误",
    "border-color": "边框色",
    "round": "圆角",
    "input-round": "输入框圆角",
    "border-width": "边框宽",
    "border-style": "边框线型",
}

# core.css 里的缺省，只用来当输入框的占位与页面上的说明：真正的缺省在样式表里，这里从不写它。
CORE: dict[str, str] = {
    "fg": "0.18 0 0 / 深色 0.98 0 0",
    "bg": "1 0 0 / 深色 0.15 0 0",
    "surface": "0.965 0 0 / 深色 0.205 0 0",
    "accent": "0.7 0.12 182.49",
    "primary": "0.98 0.06 107.14",
    "secondary": "0.93 0 0",
    "disabled": "0.6 0 0",
    "warn": "0.84 0.12 92.82",
    "error": "0.63 0.19 23.03",
    "border-color": "var(--secondary)",
    "round": "10",
    "input-round": "5.6（0.35em）",
    "border-width": "1",
    "border-style": "solid",
}

KEYWORDS = ("solid", "dashed", "dotted", "double", "none")

# 十个颜色令牌都用同一个**色盘**：盘面是 oklch 的两个自由度——角度是色相、半径是彩度（圆心是灰），
# 第三个（亮度）盘面放不下，按令牌钉住，取各自缺省的那个数。盘打包的就是 `L C H` 三元组，所以成员值、
# 校验器、浏览器那侧都不必知道有个盘。
LIGHT: dict[str, float] = {
    "fg": 0.18,
    "bg": 1.0,
    "surface": 0.965,
    "accent": 0.7,
    "primary": 0.98,
    "secondary": 0.93,
    "disabled": 0.6,
    "warn": 0.84,
    "error": 0.63,
    "border-color": 0.93,  # 缺省是 `var(--secondary)`，跟它同一个亮度
}

WORDS_SLOT = "palettes.words"


DEFAULTS: dict[str, Any] = {"sketch": False}  # 令牌不进缺省：不设就是 core 的缺省


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in ("true", "false"):
        return value.lower() == "true"
    return None


def _color(value: Any) -> str | None:
    """`L C H` → 规整成同样的三元组。范围：亮度 0–1、彩度 0–0.4、色相 0–360。

    也接受已经写好的 `oklch(L C H)`：这个值是人看着改的，不是只给程序写的。
    """
    text = value.strip() if isinstance(value, str) else ""
    if text.lower().startswith("oklch(") and text.endswith(")"):
        text = text[6:-1]
    parts = [part for part in re.split(r"[\s,]+", text.strip()) if part]
    if len(parts) != 3:
        return None
    try:
        light, chroma, hue = (float(part.rstrip("%")) for part in parts)
    except ValueError:
        return None
    if not (0.0 <= light <= 1.0 and 0.0 <= chroma <= 0.4 and 0.0 <= hue <= 360.0):
        return None
    return f"{light:g} {chroma:g} {hue:g}"


def _length(value: Any) -> str | None:
    """一个 0–64 的数（像素由浏览器侧补上）。`px` 后缀可以写，会被去掉。"""
    if isinstance(value, bool):  # bool 是 int 的子类，这里不能让它过
        return None
    text = value.strip() if isinstance(value, str) else value
    if isinstance(text, str) and text.lower().endswith("px"):
        text = text[:-2]
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    if not 0.0 <= number <= 64.0:
        return None
    return f"{number:g}"


def _keyword(value: Any) -> str | None:
    text = value.strip().lower() if isinstance(value, str) else ""
    return text if text in KEYWORDS else None


_BY_KIND = {"color": _color, "length": _length, "keyword": _keyword}

MEMBERS: dict[str, Any] = {"sketch": _bool, **{name: _BY_KIND[kind] for name, kind in TOKENS.items()}}


def flatten(payload: Any) -> dict:
    """把渲染器打包的一组字段摊成 `{成员: 值}`。

    组的出口把每个字段送出时带着它自己那份记录（`{字段: {"data": 值, ...}}`，聊天页的 `prompt_of`
    拆的是同一个形状），而这一页要的是成员本身——那一层是渲染器的，不是协议的一部分，所以拆包在这里，
    而且拆得全：畸形的帧给出 `{}`，绝不抛异常。
    """
    if not isinstance(payload, dict):
        return {}
    out: dict[str, Any] = {}
    for name, entry in payload.items():
        if isinstance(entry, dict):
            if "data" not in entry:  # 没有值的那份记录是畸形，不是一个对象成员
                continue
            entry = entry["data"]
        if entry is not None:
            out[name] = entry
    return out


def merge(state: dict, patch: dict) -> tuple[dict, list[str]]:
    """白名单 + 值域校验之后的新状态，以及被丢掉的那些成员。

    空值不是坏值：**清空一个字段就是"不设"**，成员从状态里退场，core 的缺省（成对的 `light-dark` 也在
    里面）随之回来。只有"有值但不合法"才进 `rejected`——组的出口把这个组的所有字段一起打包上行，空着的
    那些因此每帧都来一趟，它们不是错误。

    只有**通过校验且真的不同**的成员才换，所以一次"没改变什么"的上行不会让落盘动一下。
    """
    merged = dict(state)
    rejected: list[str] = []
    for name, value in patch.items():
        check = MEMBERS.get(name)
        if check is None:
            rejected.append(name)
            continue
        if isinstance(value, str) and not value.strip():
            merged.pop(name, None)
            continue
        clean = check(value)
        if clean is None:
            rejected.append(name)
            continue
        merged[name] = clean
    return merged, rejected


class Store:
    """这个应用唯一要记住的东西：页面选项。

    落盘是**节流**的：`submit=["change"]` 是每次按键一次上行（滑杆与输入框都是），所以短间隔内的连续
    改动只写最后一次；值没变就不写。写是原子的（先写 `.tmp` 再 `replace`），因为下一个进程会把它读回来。
    """

    def __init__(self, path: str | Path = ".demo-settings.json", delay: float = 0.35) -> None:
        self.path = Path(path)
        self.delay = delay
        self.state: dict[str, Any] = dict(DEFAULTS)
        self.writes = 0  # 落了盘几次：测试与快照读它
        self.rejected: list[str] = []
        self._timer: asyncio.TimerHandle | None = None

    def load(self) -> dict:
        """读回已存的那份（缺文件、坏 JSON、白名单外的成员都只是"没有"）。"""
        try:
            stored = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return self.state
        self.state, _ = merge(self.state, stored if isinstance(stored, dict) else {})
        return self.state

    def apply(self, payload: Any) -> dict:
        """一次上行：合并，变了就排一次落盘。返回合并之后的状态。"""
        before = dict(self.state)
        self.state, self.rejected = merge(self.state, flatten(payload))
        if self.state != before:
            self.save_soon()
        return self.state

    def save_soon(self) -> None:
        """排一次写，节流的窗口是 `delay`：窗口内再来一次就把它往后推。"""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # 没有 loop（测试直接调处理器）：立刻写，别假装排上了
            self.flush()
            return
        self._timer = loop.call_later(self.delay, self.flush)

    def flush(self) -> None:
        """写一次，马上。`self.writes` 记次数，测试靠它分清"排上"与"写了"。"""
        self._timer = None
        temp = self.path.with_name(self.path.name + ".tmp")
        try:
            temp.write_text(json.dumps(self.state, ensure_ascii=False, indent=1), encoding="utf-8")
            temp.replace(self.path)
        except OSError as exc:  # 界面上没有"磁盘满了"这种设置项：记一条，别让一次点击变一次崩溃
            print(f"[settings] could not write {self.path}: {exc!r}", flush=True)
            return
        self.writes += 1


settings = Store()


def state() -> Store:
    """这一份存储：整个应用一个，因为只有一个应用。"""
    return settings


def seed(ctx: Context) -> None:
    """每台设备第一次被画时，先把这个槽写下去（ADR 0001 §5）。

    顺序是重点：槽的写是一次 `send`，而页面的那一帧在 `_draw` 末尾才发出，所以值先到、结构后到，
    渲染器拿到第一棵页面树时成员就已经在了。
    """
    if ctx.data.get("config_seeded"):
        return
    ctx.data["config_seeded"] = True
    # 槽里放的是一个**对象**：fluxen 读的是这个节点的 `source.default`（`config_members`），所以拿一个
    # 不带结构的 `frame` 把它递过去——与走查页 `payload()` 同一个写法。
    ctx.slot(CONFIG).set(h.frame(source=Source(default=dict(state().state))))


def field(name: str, kind: str, value: Any) -> Accrete:
    """一个令牌一行：说明、控件、（颜色的）实时色块。

    色块自己读变量（`background: var(--fg)`），所以它显示的就是这一刻生效的颜色——不需要第二份状态。
    字段的 `tag` 就是成员名，组的出口按它打包。

    颜色都在同一个人色盘上点（角度=色相、半径=彩度、圆心是灰），线型是点出来的词——这一页没有"自己填"
    的控件。盘与词表都是字段，出口在它们所在的组：点一下 = 一次 `change`。
    """
    if kind == "color":
        control: Accrete = h.disc(
            tag=name,
            light=LIGHT[name],
            source=Source(default=value),
            id=f"cfg-{name}",
        )
    elif kind == "keyword":
        # 一个 `select` 的选项行由它的 `source` 那个槽给（这一版渲染器读的是 `source`，不是 `options`；
        # 见 ADR 0001 §9）。值不从这里来：`tag` 让它在组里有自己的一份，组负责打包与上行。
        control = h.select(
            tag=name,
            selector="cfg",
            source=Source(slot=WORDS_SLOT),
            id=f"cfg-{name}",
        )
    else:
        control = h.input(
            tag=name,
            # 一律 text：`number` 输入框在空着的时候打包出 0（"没写" 变成了 "设成 0"），而这里的空值
            # 是"不设"——种类的判断在校验器里，不在控件的类型上。
            kind="text",
            selector="cfg",
            source=Source(default=value),
            placeholder=CORE.get(name, ""),
            id=f"cfg-{name}",
        )
    preview = (
        h.frame(
            style={
                "background": f"var(--{name})",
                "border": "var(--border)",
                "border-radius": "6px",
                "min-height": "22px",
            },
            id=f"here-{name}",
        )
        if kind == "color"
        else h.text("")
    )
    return h.frame(
        h.text(f"{LABELS.get(name, name)} · {name}", variant="muted"),
        control,
        preview,
        grid={"grid-template-columns": "1fr 3fr 26px", "gap": "8px", "align-items": "center"},
        id=f"setting-{name}",
    )


def page(ctx: Context, match) -> Accrete:
    """设置页 —— 一个组，core 的令牌面全部生成成字段，一个出口。

    出口只写一次（组是唯一的），`submit=["change"]` 说"值一变就发"，`reset="keep"` 说"发完别清空"——
    清空是给表单用的，设置项不是提交一次就作废的东西。
    """
    now = state().state
    # 调色板是一次发送，不是页面树的一部分：一个 `select` 的选项只能从**槽**里读（`bind_list` 只认 slot），
    # 所以三张板每条连接写一次——槽活得比一次 `create` 长，第二次进这一页不必重写。
    if not ctx.data.get(f"{WORDS_SLOT}.seeded"):
        ctx.data[f"{WORDS_SLOT}.seeded"] = True
        words = ctx.slot(WORDS_SLOT)
        for word in KEYWORDS:
            words.append(h.text(word, id=word))
    groups: list[Accrete] = []
    for title, kind, names in GROUPS:
        groups.append(
            h.frame(
                h.text(title, variant="heading-3"),
                *[field(name, kind, now.get(name, "")) for name in names],
                grid={"grid-template-rows": f"auto repeat({len(names)}, auto)", "gap": "8px"},
                variant="card",
                id=f"group-{kind}",
            )
        )
    return h.frame(
        h.text("设置", variant="heading-1"),
        h.text(
            "core.css 的令牌面：颜色都在**同一个色盘**上点——盘面是 oklch 的色相（角度）与彩度（半径），"
            "圆心是灰；亮度按令牌钉住（取各自缺省）。尺寸填数字（像素），线型点一下。存的是 oklch 三元组 "
            "`L C H`（亮度 0–1、彩度 0–0.4、色相 0–360）。值一变本机立刻生效，同时上行到服务端记住（ADR 0001）。",
            variant="muted",
        ),
        h.loom(
            h.frame(
                h.frame(
                    h.text("线框模式（渲染器自己画的边框）", variant="muted"),
                    h.input(
                        tag="sketch",
                        kind="bool",
                        selector="cfg",
                        source=Source(default=now["sketch"]),
                        id="cfg-sketch",
                    ),
                    grid={"grid-template-columns": "1fr 2fr", "gap": "8px", "align-items": "center"},
                    id="setting-sketch",
                ),
                *groups,
                grid={"grid-template-rows": f"auto repeat({len(groups)}, auto)", "gap": "14px"},
                id="config-rows",
            ),
            sink=Sink(dest=CONFIG, scope="both", path="/"),
            submit=["change"],
            reset="keep",
            id="config-form",
        ),
        h.text("白名单之外或值域之外的成员会被丢掉，两处都查：浏览器不是可信的一侧。", variant="muted"),
        h.text(source=Source(slot="settings.note"), id="settings-note"),
        id="settings-page",
        grid={"grid-template-rows": "auto auto auto auto auto", "gap": "12px", "align-content": "start"},
    )


async def on_config(ctx: Context, frame: dict) -> None:
    """一次设置上行：合并、校验、节流落盘。状态行告诉用户哪一条被丢了。"""
    store = state()
    before = dict(store.state)
    store.apply(frame.get("data"))
    lost = [name for name in store.rejected if name]
    if lost:
        ctx.slot("settings.note").set(h.text(f"没有接受：{', '.join(sorted(lost))}（白名单或值域）"))
    elif store.state != before:
        ctx.slot("settings.note").set(h.text(f"已保存：{', '.join(sorted(store.state))}"))


def register(app, slots: Any = None) -> None:
    """把这一页挂到应用上：它的路由，和它那一条上行。"""
    app.page("/settings", title="设置")(page)
    app.on(CONFIG, on_config)