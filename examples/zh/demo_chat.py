"""对话页：一条连接一段对话，流式、可停、对失败诚实。

这是参考应用里唯一一页讲**后端**而不是讲词表的，它有六件行为，一件一节 —— 每一件都在
`tests/test_chat_example.py`（离线、不开 socket）与 `tools/gate_chat.py`（真服务器、真 WebSocket）里断言：

1. **状态随连接** —— 对话挂在 `Device`（`ctx.data`）上，不挂在应用上：socket 本身就是状态，所以刷新
   就是一段新对话，客户端走了也什么都不会漏。对话内容同时就是页面树里那些行，所以后端只留模型需要的：
   轮次，以及窗口装得下几条。
2. **流式** —— 每次回答一个 **task**（`asyncio`），用 `reply.patch("/source/default", chunk, op="append")` 追加分块 ——
   是 `Slot`，不是字符串里的名字。帧队列是设备自己的，所以一个客户端写得慢既挡不住模型调用，也挡不住另一个设备；
   等模型字节挂起的是这条协程，不是线程。
3. **单飞** —— 一段还在流时来的第二条消息会被**带着理由拒掉、写在状态行上**，不是悄悄丢掉：输入框没有被禁用，
   所以第二次发送是真实事件，就该得到真实答复。
4. **停止** —— `chat.stop` 置一个 `asyncio.Event`，回答的 task 在块边界检查它。停掉的回答**不**进上下文，即使它的一部分已经在
   屏幕上：半句话对下一轮比没有话更糟，状态行会这么说。
5. **模型失败是一条气泡** —— 异常变成回答槽里的文字加一行状态；它从不沿帧路径往上抛（抛出去的处理器只会被记
   日志，用户看到的是一段说到一半无声停住的回答）。
6. **应用自己的限制** —— 空消息与超长消息在这里拒，不在 ingest 边界拒：那道边界检查帧的**形状**，而一条提示
   能有多长是这个应用的事。

旋钮（`model`、`delay`、`window`）在 `settings` 里，由参考应用的 `main()` 从命令行填 —— 整个应用只有一处，
因为只有一个应用。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from reflux import Context
from reflux.sdk import h
from reflux.sdk.types import Accrete
from reflux.slots import Slot

from .chat_model import Model, OpenAI, Scripted, Turn
from .demo_slots import DemoSlots, slots_of

__all__ = ["Chat", "MAX_CHARS", "OpenAI", "Scripted", "Turn", "WINDOW", "on_disconnect", "page", "prompt_of", "register", "send", "share_http", "settings", "stream"]

TEXT_VALUE = "/source/default"  # 指向槽里那个文本节点的指针
MAX_CHARS = 4096  # 应用的限制，不是 wire 的限制
WINDOW = 12  # 模型看得到的上下文轮数；更旧的丢掉


@dataclass
class Settings:
    """一次部署只决定一次的东西：用哪个模型、流多快、记得多少。
    """

    model: Model = field(default_factory=lambda: Scripted(window=WINDOW))
    window: int = WINDOW
    delay: float = 0.02


settings = Settings()


@dataclass
class Chat:
    """一段对话：模型被告知什么、用户被告知什么、谁在流。
    """

    model: Model
    window: int = WINDOW
    delay: float = 0.0
    turns: list[Turn] = field(default_factory=list)
    trimmed: int = 0  # 掉出窗口的轮数，供状态行计数
    total: int = 0  # 一共记录过多少轮，读者才看得出差别
    seq: int = 0  # 回答计数器：槽名与行名
    busy: bool = False
    stop: asyncio.Event = field(default_factory=asyncio.Event)
    # 正在流的那条 task：一段对话一次只有一条（`busy` 管着），留着它是为了让停止、崩溃和测试都看得见它。
    task: Any = None

    def record(self, role: str, text: str) -> Turn:
        """加一条并保住窗口：模型看到最近 `window` 条，更旧的不看。
        """
        turn = Turn(role, text)
        self.turns.append(turn)
        self.total += 1
        while len(self.turns) > self.window:
            self.turns.pop(0)
            self.trimmed += 1
        return turn

    def status(self) -> str:
        return f"就绪 · {self.model.name} · {self.total} 轮（窗口 {len(self.turns)}/{self.window}，裁掉 {self.trimmed}）"


def state(ctx: Context) -> Chat:
    """这条连接自己的对话：挂在 `ctx.data` 上，所以它随连接一起结束。
    """
    chat = ctx.data.get("chat")
    if chat is None:
        chat = Chat(model=settings.model, window=settings.window, delay=settings.delay)
        ctx.data["chat"] = chat
    return chat


def row(*children: Accrete, id: str) -> Accrete:
    return h.frame(*children, id=id)


def page(ctx: Context, match) -> None:
    """页面 —— 以及这条连接第一次要它时、它读的那行状态。
    
        种子是一次**发送**，所以它被写成一次发送（`(slots / "status").set(...)`），而不是折进页面里：在
        socket 的这一侧没有"响应"这回事，而一页日后若要同时对不止一个设备说话（广播、定时器的提醒），
        说的方式也是这个。
    
        地址与标题来自上面那条声明 —— 标记由框架按声明造 —— 所以处理器只交内容，别的什么都不交。
    """
    slots = slots_of(ctx)
    if not ctx.data.get("status_seeded"):
        ctx.data["status_seeded"] = True  # 槽比一次 create 活得久：再种一遍就重复了
        (slots / "status").set(h.text("就绪"))
    return (
        h.frame(
            h.text("对话", variant="heading-1"),
            h.text(source=slots / "status", variant="muted", id="status"),
            h.tiles(source=slots / "messages", id="messages"),
            h.frame(
                h.loom(
                    h.input(tag="text", id="composer"),
                    h.button("发送"),
                    sink=slots / "chat" / "send",
                    submit=["enter", "button"],
                    reset="clear",
                    id="send",
                ),
                h.loom(
                    h.button("停止"),
                    sink=slots / "chat" / "stop",
                    submit="button",
                    id="stop",
                ),
                grid={"grid-template-columns": "1fr auto", "gap": "8px"},
                id="composer-row",
            ),
            h.text("回答逐块流出，可停止，可拒绝；模型出错变一条气泡，不是一段堆栈。", variant="muted"),
            id="chat-page",
            grid={"grid-template-rows": "auto auto 1fr auto auto", "height": "100%", "gap": "8px"},
        ),
    )


def prompt_of(frame: dict) -> str | None:
    """从 `chat.send` 帧里取出输入框的文本；帧里没有可用内容时是 None。
    
        表单提交带的是 `{字段: {"data": 值, ...}}` —— 这个形状来自渲染器而不是我们，所以拆包放在这里，
        并且是全的：畸形的帧给出 None，绝不抛异常。
    """
    data = frame.get("data")
    entry = data.get("text") if isinstance(data, dict) else None
    value = entry.get("data") if isinstance(entry, dict) else entry
    return value if isinstance(value, str) else None


def launch(coro: Any) -> Any:
    """把一次回答排成 task。模块级的一个接缝，好让测试改成同步跑完（或干脆不跑）。

    处理器本身就活在 loop 上（ADR 0002 P2），所以这里不需要线程：`create_task` 就是在说
    "这段回答与这条连接并行，但它不属于任何一次投递的预算"。
    """
    return asyncio.ensure_future(coro)


async def send(ctx: Context, chat: Chat, text: str) -> None:
    """收一条消息：要么给出理由拒掉，要么放上屏幕并开始回答。
    """
    slots = slots_of(ctx)
    if not text.strip():
        (slots / "status").set(h.text("空消息没有发出去"))
        return
    if len(text) > MAX_CHARS:
        (slots / "status").set(h.text(f"太长：{len(text)} 字 > {MAX_CHARS} 字上限，没有发出去"))
        return
    # 一个 loop 上只有一个投递在跑，所以这段没有 await，也就没有竞态：`busy` 的翻转是原子的。
    if chat.busy:
        (slots / "status").set(h.text("上一条还在流：按「停止」或等它结束"))
        return
    chat.busy = True
    chat.stop.clear()
    chat.seq += 1
    seq = chat.seq

    chat.record("user", text)
    context = list(chat.turns)  # 一份快照：模型作答时窗口可能已经动了
    reply = ctx.slot(f"reply.{seq}")  # 一个路径，因为每次回答有自己的平面
    with ctx.turn():  # 客户端同时看到这两行、空气泡和状态
        (slots / "messages").append(row(h.text(text), id=f"row-user-{seq}"))
        (slots / "messages").append(row(h.text(source=reply), id=f"row-bot-{seq}"))
        reply.set(h.text(""))
        (slots / "status").set(h.text(f"正在回答…（{chat.model.name}）"))
    chat.task = launch(stream(ctx, chat, reply, context))


async def stream(ctx: Context, chat: Chat, reply: Slot, context: list[Turn]) -> None:
    """一次回答，一块一块。是协程：等模型就是 `await`，所以测试可以直接把它跑完一整段。
    """
    pieces: list[str] = []
    failure: Exception | None = None
    try:
        async for chunk in chat.model.reply(context):
            if chat.stop.is_set():
                break
            pieces.append(chunk)
            reply.patch(TEXT_VALUE, chunk, op="append")
            if chat.delay:
                await asyncio.sleep(chat.delay)
    except asyncio.CancelledError:  # 关机或设备消失：不是模型的失败，也不是一条气泡
        raise
    except Exception as exc:  # 模型是远端系统：它的失败是数据，不是控制流
        failure = exc
    finally:
        chat.busy = False

    slots = slots_of(ctx)
    if failure is not None:
        with ctx.turn():
            reply.patch(TEXT_VALUE, f"\n\n⚠️ 模型出错：{failure}", op="append")
            (slots / "status").set(h.text(f"出错：{type(failure).__name__} · 可以再发一条"))
        return
    if chat.stop.is_set():
        with ctx.turn():
            reply.patch(TEXT_VALUE, " ⏹", op="append")
            (slots / "status").set(h.text(f"已停止（半句没有进上下文）· {chat.total} 轮"))
        return
    chat.record("assistant", "".join(pieces))
    (slots / "status").set(h.text(chat.status()))


async def on_send(ctx: Context, frame: dict) -> None:
    text = prompt_of(frame)
    if text is None:
        (slots_of(ctx) / "status").set(h.text("这一帧里没有文本字段，什么都没发"))
        return
    await send(ctx, state(ctx), text)


async def on_stop(ctx: Context, frame: dict) -> None:
    chat = state(ctx)
    slots = slots_of(ctx)
    if not chat.busy:
        (slots / "status").set(h.text("没有正在进行的回答"))
        return
    chat.stop.set()
    (slots / "status").set(h.text("正在停止…"))


def share_http(app, model) -> None:
    """把框架共享的会话交给模型（ADR 0002 §7）：`demo_app` 在服务启动时调它。

    一个应用一个连接池，模型不拥有它：钩子在 `_boot` 里跑，那时 `app.http` 已经建好，`_halt` 会关它。
    """
    if not hasattr(model, "http"):
        return

    @app.startup
    def hook() -> None:
        model.http = app.http

    @app.shutdown
    def unhook() -> None:
        # 会话是应用的，应用停时它也关；模型不该留着一条已关的会话去发下一个请求。
        model.http = None


async def on_disconnect(ctx: Context, frame: dict) -> None:
    """连接走了，回答也该走：往一个不存在的设备里继续写分块是白做功，`task` 是它唯一的把手。
    """
    chat = ctx.data.get("chat")
    task = getattr(chat, "task", None) if chat is not None else None
    if task is not None and not task.done():
        task.cancel()


def register(app, slots: DemoSlots) -> None:
    """把这一页挂到应用上：它的路由，和它的两条上行。
    
        路由在这里是调用式声明而不是装饰器（`app.page(...)(page)`），因为这个模块不能 import 应用：
        `python3 -m examples.X.demo_app` 时应用模块是以 `__main__` 跑的，`from .demo_app import app`
        会造出第二份。
    """
    app.page("/chat", title="对话")(page)
    app.on(slots / "chat" / "send", on_send)
    app.on(slots / "chat" / "stop", on_stop)
    app.on("disconnect", on_disconnect)

