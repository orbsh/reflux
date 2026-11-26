"""计数器：最常见的那种页面，摆在这里是为了把 API 本身看清楚。

前面几页各讲一件事（词表、走查、对话）；这一页没有内容上的野心 —— 一个数、三个按钮、一个输入框、
一小段历史 —— 所以它写出来的每一行都只是 API 的用法。要读的只有这几样：

- `@app.page(...)`：装饰器写在这个文件里。它写在 `register(app)` 内部，因为页面模块不能 import
  应用（`python3 -m examples.zh.demo_app` 时应用模块以 `__main__` 跑），所以拿到的 `app` 从参数来，
  装饰器照用。
- `h.*`：页面的词表。节点名就是 wire 的 `type`，关键字就是那个节点的字段。
- **名字用 `/` 拼，动词用 `.`**：`ctx.slot / "counter" / "count"` 是一条槽的名字，`slot.set(...)`
  是它的动词 —— 名字是构造、动词是成员，两件事不再共用一个点。
- **闭包 sink**：三个按钮的处理器写在按钮旁边，拿到的是事件的值，句柄是它闭住的。一次请求一次回应
  本来就该这样写。
- **状态跟着连接**：`ctx.data` 是这条连接的，所以两个标签页各数各的，刷新即归零 —— 这个页面没有
  数据库，也不需要。
- **槽自己带值**（`reflux.signals`）：`.signal(0)` 给一条槽一个细胞，之后读写都走 `.value`；
  `.computed(fn)` 是只读的派生；`.keyed(row)` 是列表槽按 id 对齐。细胞每个连接一份、每个名字一个，
  所以页面重画不会把值推回起点。`step` 与 `refusal` 没有细胞 —— 它们不上线，只是本地的中间量。
"""

from __future__ import annotations

from typing import Any, cast

from reflux import Context, signals
from reflux.sdk import h

__all__ = ["HISTORY", "PAGE", "State", "register", "state", "step_line"]

PAGE = "/counter"
HISTORY = 6  # 历史最多留几条，超了删最早的


def step_line(step: int) -> str:
    """`counter.hint` 的正常内容。只有这一句格式，所以它只写一次。"""
    return f"步长 {step} · 每按一次改这么多"


def _row(label: str, row_id: str) -> Any:
    """一行历史：id 从数据来（`keyed` 交回来的那个），位置不参与。"""
    return h.text(label, variant="muted", id=row_id)


class State:
    """一条连接自己的计数。两个标签页 = 两个 State。

    三条槽各带一个细胞（`count` 的、`hint` 的、`history` 的），细胞按名字登记在连接上，所以这里
    重画多少次都拿回同一个。`step` 与 `refusal` 是不上线的两个信号 —— 它们没有这层登记，整个 State
    因此仍要挂在 `ctx.data` 上（见 `state()`）。
    """

    def __init__(self, ctx: Context) -> None:
        counter = ctx.slot / "counter"
        self.step = signals.Signal(1)
        self.refusal = signals.Signal("")
        self.count = (counter / "count").signal(0)
        self.hint = (counter / "hint").computed(self._hint)
        self.history = (counter / "history").keyed(_row)
        self.seq = 0  # 行的身份由数据给：`log-1`、`log-2`……

    def _hint(self) -> str:
        return self.refusal.value or step_line(self.step.value)

    def record(self, label: str) -> None:
        """记一条历史；超出上限的那条随整表一起退场（`keyed` 按 id 删，不按位置）。"""
        self.seq += 1
        row = (f"log-{self.seq}", f"{label} → {self.count.value}")
        self.history.value = (self.history.value + [row])[-HISTORY:]


def state(ctx: Context) -> State:
    """这条连接的计数；第一次进来时建一个（`ctx.data` 随连接生，随连接死）。

    槽的细胞是幂等的，可是 `step` 与 `refusal` 不是 —— 每次绘制造一个 State 再扔掉，这两个会回到
    初值，所以整个 State 照旧缓存。
    """
    # 不能写 `setdefault(..., State(ctx))`：那个写法每次绘制都会造一个 State 再扔掉。
    current = ctx.data.get("counter")
    if current is None:
        current = ctx.data["counter"] = State(ctx)
    return cast(State, current)


def register(app: Any) -> None:
    """把这一页挂到应用上：路由（装饰器就写在这里）、两个视图、三个名字。

    落点全是闭包，所以它们不在应用的表里 —— 画这一页的时候才存在，页面一换就没了。这也是为什么
    这里只需要 `register`：没有名字要提前登记，除了路由本身。
    """

    # 槽在 wire 上放的是节点；可这两条槽放的就是一个值 —— 数字、一行说明。所以"这个值长什么样"
    # 在这里说一次，之后有人写值：`current.count.value = 3`。id 与 variant 只写这一个地方。
    # 写成节点也照样可以（`slot.set(h.text("3"))`）—— 已经是节点的值不再经过视图。
    counter = app.slot / "counter"
    (counter / "count").view(
        lambda value: h.text(str(value), variant="heading-1", id="counter-value")
    )
    (counter / "hint").view(lambda value: h.text(value, variant="muted", id="counter-hint"))

    # 名字在这里先声明一次：`/status` 与 `inspect` 列的是"用过的名字"，不该等人打开这一页才有。
    for name in ("count", "hint", "history"):
        app.declare(f"counter.{name}")

    @app.page(PAGE, title="计数器")
    def counter_page(ctx: Context, match) -> None:
        """一次计数页的绘制：值从连接的 State 来，按钮的处理器写在按钮下面。"""
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
                # 读槽拿的就是上面那几个句柄：名字写过一次，这里不再写第二遍。
                h.text(source=current.count, id="counter-slot"),
                h.text(source=current.hint, id="counter-hint-slot"),
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
                    h.tiles(source=current.history, id="counter-history"),
                    grid={"grid-auto-rows": "auto", "gap": "6px", "align-content": "start"},
                    variant="card",
                    id="counter-log",
                ),
                grid={"grid-auto-rows": "auto", "gap": "16px", "align-content": "start"},
                id="counter-page",
            )
        )