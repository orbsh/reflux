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
- **信号是主语，槽是它的去处**（`reflux.signals`）：`Signal(0).bind(slot)` 说这个值往哪条槽写，
  `.view(fn)` 说值怎么变成节点，`.keyed(row)` 说列表按 id 对齐，`.store(key)` 说这个值要活过连接。
  声明全写在页函数头部，一次绘制一行；重画拿回同一个信号，所以槽不会被推回起点。
- **`step`／`refusal`／`seq` 不上线**：它们没有槽，只有 `.store(key)` —— 匿名连接存在这条连接自己
  的数据里，登录用户存在应用的 store 里、按 user id 取回。
"""

from __future__ import annotations

from typing import Any

from reflux import Context, signals
from reflux.sdk import h

__all__ = ["HISTORY", "PAGE", "register", "step_line"]

PAGE = "/counter"
HISTORY = 6  # 历史最多留几条，超了删最早的


def step_line(step: int) -> str:
    """`counter.hint` 的正常内容。只有这一句格式，所以它只写一次。"""
    return f"步长 {step} · 每按一次改这么多"


def _row(label: str, row_id: str) -> Any:
    """一行历史：id 从数据来（`keyed` 交回来的那个），位置不参与。"""
    return h.text(label, variant="muted", id=row_id)


def register(app: Any) -> None:
    """把这一页挂到应用上：路由，以及那三个名字。

    落点全是闭包，所以它们不在应用的表里 —— 画这一页的时候才存在，页面一换就没了。这也是为什么
    这里只需要 `register`：没有名字要提前登记，除了路由本身。
    """

    # 名字在这里先声明一次：`/status` 与 `inspect` 列的是"用过的名字"，不该等人打开这一页才有。
    for name in ("count", "hint", "history"):
        app.declare(f"counter.{name}")

    @app.page(PAGE, title="计数器")
    def counter_page(ctx: Context, match) -> None:
        """一次计数页的绘制：状态声明在头部，处理器是它下面的闭包。"""
        slots = ctx.slot
        # 不上线的三条：只有 `.store(key)`，没有槽。匿名连接存在这条连接的数据里（session），
        # 登录用户存在应用的 store 里、按 user id 取回 —— 换个标签页也接着数。
        step = signals.Signal(1).store("counter.step")
        refusal = signals.Signal("").store("counter.refusal")
        seq = signals.Signal(0).store("counter.seq")
        # 上线的三条：值写进槽；`.view` 说这个值长什么样，`.keyed` 说列表按 id 对齐。
        count = signals.Signal(0).bind(slots / "counter" / "count").view(
            lambda value: h.text(str(value), variant="heading-1", id="counter-value")
        )
        hint = signals.Computed(lambda: refusal.value or step_line(step.value)).bind(
            slots / "counter" / "hint"
        ).view(lambda value: h.text(value, variant="muted", id="counter-hint"))
        history = signals.Signal([]).keyed(_row).bind(slots / "counter" / "history")

        def record(label: str) -> None:
            """记一条历史；超出上限的那条随整表一起退场（`keyed` 按 id 删，不按位置）。"""
            seq.value += 1
            row = (f"log-{seq.value}", f"{label} → {count.value}")
            history.value = (history.value + [row])[-HISTORY:]

        def change(by: int) -> None:
            with signals.batch():  # 一次按下：值改一次、历史记一条，页面只写一轮
                count.value += by * step.value
                record(f"{by * step.value:+d}")

        def up(value: object) -> None:
            change(+1)

        def down(value: object) -> None:
            change(-1)

        def reset(value: object) -> None:
            with signals.batch():
                count.value = 0
                record("归零")

        def set_step(value: dict) -> None:
            # 交上来的是解析好的数（`kind="number"` 由渲染器解析）—— 这里只剩页面自己的规矩：1–10 的整数。
            wanted = value.get("step")
            if wanted is None:  # 空着回车：没有一个数
                refusal.value = f"没有输入，步长还是 {step.value}"
                return
            with signals.batch():
                step.value = min(max(round(wanted), 1), 10)
                refusal.value = ""  # 收下了，那句拒绝就退场

        return (
            h.frame(
                h.text("计数器", variant="heading-1", id="counter-title"),
                h.text(
                    "状态挂在连接上（`ctx.data`）：开两个标签页，两个各数各的；刷新即归零。",
                    variant="muted",
                    id="counter-blurb",
                ),
                # 读的是信号绑的那条槽：名字写过一次，这里不再写第二遍。
                h.text(source=count, id="counter-slot"),
                h.text(source=hint, id="counter-hint-slot"),
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
                        h.input(tag="step", kind="number", placeholder="1–10，回车生效", id="counter-step"),
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
                    h.tiles(source=history, id="counter-history"),
                    grid={"grid-auto-rows": "auto", "gap": "6px", "align-content": "start"},
                    variant="card",
                    id="counter-log",
                ),
                grid={"grid-auto-rows": "auto", "gap": "16px", "align-content": "start"},
                id="counter-page",
            )
        )