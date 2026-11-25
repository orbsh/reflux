"""计数器：最常见的那种页面，摆在这里是为了把 API 本身看清楚。

前面几页各讲一件事（词表、走查、对话）；这一页没有内容上的野心 —— 一个数、三个按钮、一个输入框、
一小段历史 —— 所以它写出来的每一行都只是 API 的用法。要读的只有五样：

- `@app.page(...)`：装饰器写在这个文件里。它写在 `register(app)` 内部，因为页面模块不能 import
  应用（`python3 -m examples.zh.demo_app` 时应用模块以 `__main__` 跑），所以拿到的 `app` 从参数来，
  装饰器照用。
- `h.*`：页面的词表。节点名就是 wire 的 `type`，关键字就是那个节点的字段。
- **闭包 sink**：三个按钮的处理器写在按钮旁边，拿到的是事件的值，槽是它闭住的。一次请求一次回应
  本来就该这样写。
- **状态跟着连接**：`ctx.data` 是这条连接的，所以两个标签页各数各的，刷新即归零 —— 这个页面没有
  数据库，也不需要。
- **信号**（`reflux.signals`）：值声明一次，槽跟着它走；处理器改值，不再自己写槽。这一页是那层的
  最短用法 —— `bound` 让一个信号拥有一个槽，`Computed` 把说明从步长算出来，`keyed` 把历史按 id
  对齐，`batch()` 让一次按下只写一轮。原来散在三处的 `slots.hint.set(...)`、那段"只种一次"的
  守卫，以及那本 `State.ids` 账，都不在了。
"""

from __future__ import annotations

from typing import Any, Protocol, cast

from reflux import Context, signals
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


def step_line(step: int) -> str:
    """`counter.hint` 的正常内容。只有这一句格式，所以它只写一次。"""
    return f"步长 {step} · 每按一次改这么多"


def _row(label: str, row_id: str) -> Any:
    """一行历史：id 从数据来（`keyed` 交回来的那个），位置不参与。"""
    return h.text(label, variant="muted", id=row_id)


class State:
    """一条连接自己的计数。两个标签页 = 两个 State。

    三个信号是存储：`count`（带槽）、`step`、`refusal`（"上一次输入不合法"这一阵子的事实）；
    `hint` 由后两者算出，`history` 是 `[(id, 文案)]` 的一张表，槽由 `keyed` 对齐。
    """

    def __init__(self, ctx: Context) -> None:
        self.count = signals.bound(ctx, "counter.count", 0)
        self.step = signals.Signal(1)
        self.refusal = signals.Signal("")
        self.hint = signals.into(ctx, "counter.hint", signals.Computed(self._hint))
        self.history = signals.Signal([])
        signals.keyed(ctx, "counter.history", self.history, _row)
        self.seq = 0  # 行的身份由数据给：`log-1`、`log-2`……

    def _hint(self) -> str:
        return self.refusal.value or step_line(self.step.value)

    def record(self, label: str) -> None:
        """记一条历史；超出上限的那条随整表一起退场（`keyed` 按 id 删，不按位置）。"""
        self.seq += 1
        row = (f"log-{self.seq}", f"{label} → {self.count.value}")
        self.history.value = (self.history.value + [row])[-HISTORY:]


def state(ctx: Context) -> State:
    """这条连接的计数；第一次进来时建一个（`ctx.data` 随连接生，随连接死）。"""
    # 不能写 `setdefault(..., State(ctx))`：那个写法每次绘制都会造一个 State 再扔掉，而 State 里的
    # `bound` 信号在构造时就写第一个值 —— 被扔掉的那一个会把读者刚改好的数推回 0。
    current = ctx.data.get("counter")
    if current is None:
        current = ctx.data["counter"] = State(ctx)
    return cast(State, current)


def register(app: Any) -> None:
    """把这一页挂到应用上：路由（装饰器就写在这里），外加三个按钮与一个输入框的落点。

    落点全是闭包，所以它们不在应用的表里 —— 画这一页的时候才存在，页面一换就没了。这也是为什么
    这里只需要 `register`：没有名字要提前登记，除了路由本身。
    """

    # 槽在 wire 上放的是节点；可这两个槽放的就是一个值 —— 数字、一行说明。所以"这个值长什么样"
    # 在这里说一次，之后有人写值：`slots.count.set(3)`。id 与 variant 只写这一个地方。
    # 写成节点也照样可以（`slots.count.set(h.text("3"))`）—— 已经是节点的值不再经过视图。
    app.view("counter.count", lambda value: h.text(str(value), variant="heading-1", id="counter-value"))
    app.view("counter.hint", lambda value: h.text(value, variant="muted", id="counter-hint"))

    # 名字在这里先声明一次：`/status` 与 `inspect` 列的是"用过的名字"，不该等人打开这一页才有。
    for name in ("count", "hint", "history"):
        app.declare(f"counter.{name}")

    @app.page(PAGE, title="计数器")
    def counter_page(ctx: Context, match) -> None:
        """一次计数页的绘制：值从连接的 State 来，按钮的处理器写在按钮下面。"""
        slots = counter_of(ctx)
        current = state(ctx)

        def change(by: int) -> None:
            with signals.batch():  # 一次按下：值改一次、历史记一条，页面只写一轮
                current.count.value += by * current.step.value
                current.record(f"{by * current.step.value:+d}")

        def up(value: object) -> None:
            change(+1)

        def down(value: object) -> None:
            change(-1)

        def reset(value: object) -> None:
            with signals.batch():
                current.count.value = 0
                current.record("归零")

        def set_step(value: object) -> None:
            # 组提交的是它打包出来的对象（{字段: 值}），值是字符串 —— 所以这里既解析也拒绝。
            raw = value.get("step") if isinstance(value, dict) else None
            text = raw.strip() if isinstance(raw, str) else ""
            try:
                step = int(text)
            except ValueError:
                current.refusal.value = f"「{text}」不是整数，步长还是 {current.step.value}"
                return
            with signals.batch():
                current.step.value = min(max(step, 1), 10)
                current.refusal.value = ""  # 合法输入了，那句拒绝就退场

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
                    # 一个 `button` 住在 `loom` 里，按下的时机由 loom 的 `submit` 命名 —— 所以每次
                    # 按下都是一个 loom 的提交，而不是按钮自己会说话（ADR 0032 §3）。
                    h.loom(h.button("−"), sink=down, submit=["button"], id="counter-down"),
                    h.loom(h.button("＋"), sink=up, submit=["button"], id="counter-up"),
                    h.loom(h.button("归零"), sink=reset, submit=["button"], id="counter-reset"),
                    horizontal=True,
                    grid={"grid-template-columns": "max-content max-content max-content", "gap": "8px",
                          "justify-content": "start"},
                    id="counter-buttons",
                ),
                h.frame(
                    h.text("步长", variant="muted"),
                    # 输入框的出口是它所在的组：`tag` 是它打包时的键，`submit` 决定何时发。
                    h.loom(
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