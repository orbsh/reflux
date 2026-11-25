"""设置页：三样东西写进页面选项槽，本机立刻生效，服务端记住（ADR 0001）。

页面选项是 fluxen 的机制，不是这一页的发明：`#main` 没写 `data-config`，所以在它上面挂着的槽就叫缺省
名 `__CONFIG__`（fluxen ADR 0038 §2），槽里放一个对象，成员**逐个**决定——页面自己那一半先、远侧
（生产端）在后；渲染器再把标量成员镜像成文档根上的 `data-<member>`，浏览器侧的表（`www/static/reflux.js`
的 `STYLE`）把它们落到 `:root` 的自定义属性。所以这一页没有新帧、没有新动作，只有三件普通的事：

1. **写**：一个组的出口 `Sink(dest="__CONFIG__", scope="both", path="/")`——`both` 是"本地先改、同时
   上行"（fluxen ADR 0031 §1），一个组只有一个出口，所以这条需求没有别的合法形状。
2. **记**：`demo_app` 把上行交给 `on_config`，这里做白名单 + 值域校验 + 合并，随后节流落盘。落盘是
   应用的，不是框架的：`App` 不碰磁盘。
3. **起始值**：每台设备第一次被画时，外框把已存对象先 `set` 进这个槽，所以新连接、刷新、换设备的第一帧
   就带着用户的选择，不会出现"默认 → 你的选择"那一闪。

值能改的三样：`sketch`（线框模式，布尔）、`accent`（强调色，`#rrggbb`）、`round`（圆角，0–24 的整数）。
白名单之外的成员一律丢，值域之外的也丢——两处都丢，是因为浏览器不是可信的一侧，而这个文件会被下一个
进程读回来。
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

__all__ = ["CONFIG", "DEFAULTS", "MEMBERS", "Store", "flatten", "merge", "on_config", "page", "register", "seed", "state"]

CONFIG = "__CONFIG__"  # fluxen 的页面选项槽：`#main` 上没有 `data-config`，就是缺省名

DEFAULTS: dict[str, Any] = {"sketch": False, "accent": "#4fb3a5", "round": 10}

# 一个成员一个校验：通过就给出规整之后的值，不通过返回 None（这一条丢，其余照收）。
ACCENT = re.compile(r"^#[0-9a-fA-F]{6}$")


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in ("true", "false"):
        return value.lower() == "true"
    return None


def _accent(value: Any) -> str | None:
    cleaned = value.strip() if isinstance(value, str) else ""
    return cleaned.lower() if ACCENT.match(cleaned) else None


def _round(value: Any) -> int | None:
    if isinstance(value, bool):  # bool 是 int 的子类，这里不能让它过
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if 0 <= number <= 24 else None


MEMBERS: dict[str, Any] = {"sketch": _bool, "accent": _accent, "round": _round}


def flatten(payload: Any) -> dict:
    """把渲染器打包的一组字段摊成 `{成员: 值}`。

    组的出口把每个字段送出时带着它自己的那份记录（`{字段: {"data": 值, ...}}`，聊天页的 `prompt_of`
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

    只有**通过校验且真的不同**的成员才换，所以一次"没改变什么"的上行不会让落盘动一下。
    """
    merged = dict(state)
    rejected: list[str] = []
    for name, value in patch.items():
        check = MEMBERS.get(name)
        if check is None:
            rejected.append(name)
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


def field(label: str, name: str, kind: str, value: Any) -> Accrete:
    """一个设置项：一行说明加一个字段。字段的 `tag` 就是成员名——组的出口按它打包。"""
    return h.frame(
        h.text(label, variant="muted"),
        h.input(tag=name, kind=kind, selector="cfg", source=Source(default=value), id=f"cfg-{name}"),
        grid={"grid-template-columns": "1fr 2fr", "gap": "8px", "align-items": "center"},
        id=f"setting-{name}",
    )


def page(ctx: Context, match) -> Accrete:
    """设置页 —— 一个组，三个字段，一个出口。

    出口只写一次（组是唯一的），`submit=["change"]` 说"值一变就发"，`reset="keep"` 说"发完别清空"——
    清空是给表单用的，设置项不是提交一次就作废的东西。
    """
    now = state().state
    return h.frame(
        h.text("设置", variant="heading-1"),
        h.text(
            "这三样进页面选项槽 `__CONFIG__`：本机立刻生效，同时上行到服务端记住（ADR 0001）。"
            "线框模式归渲染器（它按 `data-sketch` 画边框），强调色与圆角归 `:root` 的自定义属性。",
            variant="muted",
        ),
        h.loom(
            # loom 是一行 flex：把三行装进一个 frame，排法是页面的事（与复核表同一形状）。
            h.frame(
                field("线框模式", "sketch", "bool", now["sketch"]),
                field("强调色", "accent", "text", now["accent"]),
                field("圆角（0–24）", "round", "number", now["round"]),
                grid={"grid-template-rows": "auto auto auto", "gap": "10px"},
                id="config-rows",
            ),
            sink=Sink(dest=CONFIG, scope="both", path="/"),
            submit=["change"],
            reset="keep",
            id="config-form",
        ),
        h.text("白名单之外或值域之外的成员会被丢掉，两处都查：浏览器不是可信的一侧。", variant="muted"),
        id="settings-page",
        grid={"grid-template-rows": "auto auto auto auto", "gap": "12px", "align-content": "start"},
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