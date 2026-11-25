"""计数器：最常见的那种页面，摆在这里是为了把 API 本身看清楚。

前面几页各讲一件事（词表、走查、对话）；这一页没有内容上的野心 —— 一个数、三个按钮、一个输入框、
一小段历史 —— 所以它写出来的每一行都只是 API 的用法。要读的只有四样：

- `@app.page(...)`：装饰器写在这个文件里。它写在 `register(app)` 内部，因为页面模块不能 import
  应用（`python3 -m examples.zh.demo_app` 时应用模块以 `__main__` 跑），所以拿到的 `app` 从参数来，
  装饰器照用。
- `h.*`：页面的词表。节点名就是 wire 的 `type`，关键字就是那个节点的字段。
- **闭包 sink**：三个按钮的处理器写在按钮旁边，拿到的是事件的值，槽是它闭住的。一次请求一次回应
  本来就该这样写。
- **状态跟着连接**：`ctx.data` 是这条连接的，所以两个标签页各数各的，刷新即归零 —— 这个页面没有
  数据库，也不需要。
"""

from __future__ import annotations

from typing import Any, Protocol, cast

from reflux import Context
from reflux.sdk import h
from reflux.slots import Slot

__all__ = ["HISTORY", "PAGE", "State", "counter_of", "register", "state", "step_line"]

PAGE = "/counter"
HISTORY = 6  # 历史最多留几条，超了删最早的


class _Counter(Protocol):
    """`counter` 这一族：当前值、步长说明、历史。"""

    count: Slot
    hint: Slot
    history: Slot


def counter_of(ctx: Context) -> _Counter:
    """这一页的槽，带类型 —— `ctx.slot("counter")` 是同一个东西，只是没有静态检查。"""
    return cast(_Counter, ctx.slot("counter"))


class State:
    """一条连接自己的计数。两个标签页 = 两个 State。"""

    def __init__(self) -> None:
        self.value = 0
        self.step = 1
        self.ids: list[str] = []  # 历史里那些节点的 id，删最早那条要用


def state(ctx: Context) -> State:
    """这条连接的计数；第一次进来时建一个（`ctx.data` 随连接生，随连接死）。"""
    return cast(State, ctx.data.setdefault("counter", State()))


def step_line(step: int) -> str:
    """`counter.hint` 的正常内容。只有这一句格式，所以它只写一次。"""
    return f"步长 {step} · 每按一次改这么多"


def record(ctx: Context, label: str) -> None:
    """记一条历史，并把超出上限的最早一条删掉 —— 列表槽的 `append` 与 `remove` 都在这里。"""
    slots = counter_of(ctx)
    current = state(ctx)
    bump = len(current.ids) + 1
    ident = f"log-{bump}"
    current.ids.append(ident)
    slots.history.append(h.text(f"{label} → {current.value}", variant="muted", id=ident))
    while len(current.ids) > HISTORY:
        slots.history.remove(current.ids.pop(0))


def register(app: Any) -> None:
    """把这一页挂到应用上：路由（装饰器就写在这里），外加三个按钮与一个输入框的落点。

    落点全是闭包，所以它们不在应用的表里 —— 画这一页的时候才存在，页面一换就没了。这也是为什么
    这里只需要 `register`：没有名字要提前登记，除了路由本身。
    """

    # 槽在 wire 上放的是节点；可这两个槽放的就是一个值 —— 数字、一行说明。所以"这个值长什么样"
    # 在这里说一次，之后页面写值：`slots.count.set(3)`。id 与 variant 只写这一个地方。
    # 写成节点也照样可以（`slots.count.set(h.text("3"))`）—— 已经是节点的值不再经过视图。
    app.view("counter.count", lambda value: h.text(str(value), variant="heading-1", id="counter-value"))
    app.view("counter.hint", lambda value: h.text(value, variant="muted", id="counter-hint"))

    # 名字在这里先声明一次：`/status` 与 `cli dests` 列的是"用过的名字"，不该等人打开这一页才有。
    for name in ("count", "hint", "history"):
        app.declare(f"counter.{name}")

    @app.page(PAGE, title="计数器")
    def counter_page(ctx: Context, match) -> None:
        """一次计数页的绘制：值从连接的 State 来，按钮的处理器写在按钮下面。"""
        slots = counter_of(ctx)
        current = state(ctx)
        if not ctx.data.get("counter_seeded"):
            # 槽活得比一次 `create` 长，所以值只种一次：第二条进来再种就会把读者刚改的数字压回去。
            ctx.data["counter_seeded"] = True
            slots.count.set(current.value)
            slots.hint.set(step_line(current.step))

        def change(by: int) -> None:
            current.value += by * current.step
            slots.count.set(current.value)
            record(ctx, f"{by * current.step:+d}")

        def up(value: object) -> None:
            change(+1)

        def down(value: object) -> None:
            change(-1)

        def reset(value: object) -> None:
            current.value = 0
            slots.count.set(0)
            record(ctx, "归零")

        def set_step(value: object) -> None:
            # 组提交的是它打包出来的对象（{字段: 值}），值是字符串 —— 所以这里既解析也拒绝。
            raw = value.get("step") if isinstance(value, dict) else None
            text = raw.strip() if isinstance(raw, str) else ""
            try:
                step = int(text)
            except ValueError:
                slots.hint.set(f"「{text}」不是整数，步长还是 {current.step}")
                return
            current.step = min(max(step, 1), 10)
            slots.hint.set(step_line(current.step))

        return (
            h.frame(
                h.text("计数器", variant="heading-1", id="counter-title"),
                h.text(
                    "状态挂在连接上（`ctx.data`）：开两个标签页，两个各数各的；刷新即归零。",
                    variant="muted",
                    id="counter-blurb",
                ),
                h.text(source=slots.count, id="counter-slot"),
                h.text(source=slots.hint, id="counter-hint-slot"),
                h.frame(
                    # 一个 `button` 住在 `bundle` 里，按下的时机由 bundle 的 `submit` 命名 —— 所以每次
                    # 按下都是一个 bundle 的提交，而不是按钮自己会说话（ADR 0032 §3）。
                    h.bundle(h.button("−", sink=down), sink=down, submit=["button"], id="counter-down"),
                    h.bundle(h.button("＋", sink=up), sink=up, submit=["button"], id="counter-up"),
                    h.bundle(h.button("归零", sink=reset), sink=reset, submit=["button"], id="counter-reset"),
                    horizontal=True,
                    grid={"grid-template-columns": "max-content max-content max-content", "gap": "8px",
                          "justify-content": "start"},
                    id="counter-buttons",
                ),
                h.frame(
                    h.text("步长", variant="muted"),
                    # 输入框的出口是它所在的组：`tag` 是它打包时的键，`submit` 决定何时发。
                    h.bundle(
                        h.input(tag="step", placeholder="1–10，回车生效", id="counter-step"),
                        sink=set_step,
                        submit=["enter"],
                        id="counter-step-form",
                    ),
                    horizontal=True,
                    grid={"grid-template-columns": "auto 1fr", "gap": "8px", "align-items": "center"},
                    variant="card",
                    id="counter-step-box",
                ),
                h.frame(
                    h.text("历史", variant="heading-3"),
                    h.tiles(source=slots.history, id="counter-history"),
                    grid={"grid-auto-rows": "auto", "gap": "6px", "align-content": "start"},
                    variant="card",
                    id="counter-log",
                ),
                grid={"grid-auto-rows": "auto", "gap": "16px", "align-content": "start"},
                id="counter-page",
            )
        )
