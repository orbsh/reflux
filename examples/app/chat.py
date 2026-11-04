"""The chat page: a conversation per connection, streamed, stoppable, and honest about failures.

Six pieces of backend behaviour, one per section — each asserted in `tests/test_chat_example.py`
(offline, no socket) and in `tools/gate_chat.py` (real server, real WebSocket):

1. **state per connection** — the conversation hangs off the `Device`, not off the app: the socket
   *is* the state, so a refresh is a new conversation and nothing leaks when a client goes away. The
   transcript is also the page tree's (the rows), so the backend only keeps what the model needs:
   turns, and how many of them the window holds.
2. **streaming** — a worker thread per reply appends chunks with
   `reply.patch("/bind/value/default", chunk, op="append")` — a `Slot`, not a name in a string. The frame queue is the device's, so
   one client's slow write never holds a model call or another device.
3. **single flight** — a second message while one is streaming is refused *with a reason on the
   status line*, not silently dropped: the composer is not disabled, so the second send is a real
   event and deserves a real answer.
4. **stop** — `chat.stop` sets an event the worker checks at chunk boundaries. A stopped reply is
   **not** added to the context even though part of it is on screen: half a sentence is worse for the
   next turn than no sentence, and the status line says so.
5. **a failing model is a bubble** — the exception becomes text in the reply slot plus a status line;
   it never travels up the frame path (a raised handler would only be logged, and the user would see a
   reply that silently stopped mid-sentence).
6. **application limits** — empty and oversized messages are refused here, not at the ingest
   boundary: that boundary checks the *shape* of a frame; how long a prompt may be is this app's.

The knobs (`model`, `delay`, `window`) live in `settings`, which `main()` fills from the command line.
Nothing is threaded through a factory: a page module is a declaration, and its settings are settings.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from reflux import Context, Match
from reflux.sdk import builders as b
from reflux.sdk.types import Accrete
from reflux.slots import Slot

from .app import app, names
from .model import Model, Scripted, Turn
from .names import Names

__all__ = ["Chat", "MAX_CHARS", "WINDOW", "page", "send", "settings", "spawn", "stream"]

TEXT_VALUE = "/bind/value/default"  # pointer into a text node stored in a slot
MAX_CHARS = 4096  # an application limit, not a wire limit
WINDOW = 12  # turns of context the model sees; older ones are dropped


@dataclass
class Settings:
    """What a deployment decides once: which model, how fast it streams, how much it remembers."""

    model: Model = field(default_factory=lambda: Scripted(window=WINDOW))
    window: int = WINDOW
    delay: float = 0.02


settings = Settings()


@dataclass
class Chat:
    """One conversation: what the model is told, what the user is told, and who is streaming."""

    model: Model
    window: int = WINDOW
    delay: float = 0.0
    turns: list[Turn] = field(default_factory=list)
    trimmed: int = 0  # turns dropped out of the window, counted for the status line
    total: int = 0  # turns ever recorded, so the reader can see the difference
    seq: int = 0  # reply counter: slot and row names
    busy: bool = False
    stop: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def record(self, role: str, text: str) -> Turn:
        """Add a turn and keep the window: the model sees the last `window` turns, nothing older."""
        turn = Turn(role, text)
        self.turns.append(turn)
        self.total += 1
        while len(self.turns) > self.window:
            self.turns.pop(0)
            self.trimmed += 1
        return turn

    def status(self) -> str:
        return (
            f"就绪 · {self.model.name} · {self.total} 轮（窗口 {len(self.turns)}/{self.window}，裁掉 {self.trimmed}）"
        )


def state(ctx: Context) -> Chat:
    """This connection's conversation: hung on `ctx.data`, so it dies with the connection."""
    chat = ctx.data.get("chat")
    if chat is None:
        chat = Chat(model=settings.model, window=settings.window, delay=settings.delay)
        ctx.data["chat"] = chat
    return chat


def row(*children: Accrete, id: str) -> Accrete:
    return b.case(*children, id=id)


@app.route("/chat", title="对话")
def page(ctx: Context, match: Match) -> None:
    """The page — and, the first time this connection asks for it, the status line it reads.

    The seed is a **send**, so it is written as one (`ctx.emit`), not folded into the page: on this
    side of the socket nothing is a response, and a page that later has to say something to more than
    the one device that asked (a broadcast, a nudge from a timer) says it the same way.

    The address and the title come from the declaration above — `ctx.page` builds the markers — so the
    handler passes its content and nothing else.
    """
    slots: Names = ctx.slot  # type: ignore[assignment]  # the names are `names.py`'s
    if not ctx.data.get("status_seeded"):
        ctx.data["status_seeded"] = True  # a slot outlives a create: seeding again would duplicate
        slots.status.set(b.text("就绪"))
    ctx.page(
        b.case(
            b.text("对话", variant="heading-1"),
            b.text(source=slots.status, variant="muted", id="status"),
            b.rack(source=slots.messages, scroll=True, id="messages"),
            b.case(
                b.form(b.input(field="text", id="composer"), b.button("发送"), dest=slots.chat.send, id="send"),
                b.form(b.button("停止"), dest=slots.chat.stop, id="stop"),
                grid={"grid-template-columns": "1fr auto", "gap": "8px"},
                id="composer-row",
            ),
            b.text("回答逐块流出，可停止，可拒绝；模型出错变一条气泡，不是一段堆栈。", variant="muted"),
            id="chat-page",
            grid={"grid-template-rows": "auto auto 1fr auto auto", "height": "100%", "gap": "8px"},
        ),
    )


def prompt_of(frame: dict) -> str | None:
    """The composer's text out of a `chat.send` frame, or None when the frame carries nothing usable.

    A form's submit carries `{field: {"data": value, ...}}` — that shape comes from the renderer, not
    from us, so the unwrapping lives here and is total: a malformed frame yields None, never a raise.
    """
    data = frame.get("data")
    entry = data.get("text") if isinstance(data, dict) else None
    value = entry.get("data") if isinstance(entry, dict) else entry
    return value if isinstance(value, str) else None


def spawn(target, args: tuple) -> None:
    """Start a reply's worker. A module-level seam so a test can run the reply inline instead."""
    threading.Thread(target=target, args=args, daemon=True).start()


def send(ctx: Context, chat: Chat, text: str) -> None:
    """Take one message: refuse it with a reason, or put it on screen and start the reply."""
    slots: Names = ctx.slot  # type: ignore[assignment]
    if not text.strip():
        slots.status.set(b.text("空消息没有发出去"))
        return
    if len(text) > MAX_CHARS:
        slots.status.set(b.text(f"太长：{len(text)} 字 > {MAX_CHARS} 字上限，没有发出去"))
        return
    with chat.lock:
        if chat.busy:
            slots.status.set(b.text("上一条还在流：按「停止」或等它结束"))
            return
        chat.busy = True
        chat.stop.clear()
        chat.seq += 1
        seq = chat.seq

    chat.record("user", text)
    context = list(chat.turns)  # a snapshot: the window may move while the model is answering
    reply = ctx.slot(f"reply.{seq}")  # a path, because each answer gets its own plane
    with ctx.turn():  # the client sees the two rows, the empty bubble and the status at once
        slots.messages.append(row(b.text(text), id=f"row-user-{seq}"))
        slots.messages.append(row(b.text(source=reply), id=f"row-bot-{seq}"))
        reply.set(b.text(""))
        slots.status.set(b.text(f"正在回答…（{chat.model.name}）"))
    spawn(stream, (ctx, chat, reply, context))


def stream(ctx: Context, chat: Chat, reply: Slot, context: list[Turn]) -> None:
    """One reply, chunk by chunk. Synchronous on purpose: the thread is the caller's choice, so a test
    can run a whole reply without one."""
    pieces: list[str] = []
    failure: Exception | None = None
    try:
        for chunk in chat.model.reply(context):
            if chat.stop.is_set():
                break
            pieces.append(chunk)
            reply.patch(TEXT_VALUE, chunk, op="append")
            if chat.delay:
                time.sleep(chat.delay)
    except Exception as exc:  # a model is a remote system: its failure is data, not control flow
        failure = exc
    finally:
        with chat.lock:
            chat.busy = False

    slots: Names = ctx.slot  # type: ignore[assignment]
    if failure is not None:
        with ctx.turn():
            reply.patch(TEXT_VALUE, f"\n\n⚠️ 模型出错：{failure}", op="append")
            slots.status.set(b.text(f"出错：{type(failure).__name__} · 可以再发一条"))
        return
    if chat.stop.is_set():
        with ctx.turn():
            reply.patch(TEXT_VALUE, " ⏹", op="append")
            slots.status.set(b.text(f"已停止（半句没有进上下文）· {chat.total} 轮"))
        return
    chat.record("assistant", "".join(pieces))
    slots.status.set(b.text(chat.status()))


@app.on(names.chat.send)
def on_send(ctx: Context, frame: dict) -> None:
    text = prompt_of(frame)
    if text is None:
        slots: Names = ctx.slot  # type: ignore[assignment]
        slots.status.set(b.text("这一帧里没有文本字段，什么都没发"))
        return
    send(ctx, state(ctx), text)


@app.on(names.chat.stop)
def on_stop(ctx: Context, frame: dict) -> None:
    chat = state(ctx)
    if not chat.busy:
        slots: Names = ctx.slot  # type: ignore[assignment]
        slots.status.set(b.text("没有正在进行的回答"))
        return
    chat.stop.set()
    slots = ctx.slot  # type: ignore[assignment]
    slots.status.set(b.text("正在停止…"))