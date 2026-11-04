"""The chat page: a conversation per connection, streamed, stoppable, and honest about failures.

Six pieces of backend behaviour, one per section — each asserted in `tests/test_chat_example.py`
(offline, no socket) and in `tools/gate_app.py` (real server, real WebSocket):

1. **state per connection** — the conversation hangs off the `Device`, not off the app: the socket
   *is* the state, so a refresh is a new conversation and nothing leaks when a client goes away. The
   transcript is also the page tree's (the rows), so the backend only keeps what the model needs:
   turns, and how many of them the window holds.
2. **streaming** — a worker thread per reply appends chunks with
   `wire.patch(slot, "/bind/value/default", chunk, op="append")`. The frame queue is the device's, so
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

from reflux import Match, wire
from reflux.app import Device
from reflux.sdk import builders as b
from reflux.sdk import markers
from reflux.sdk.types import Accrete

from .app import app
from .model import Model, Scripted, Turn

__all__ = ["Chat", "MAX_CHARS", "WINDOW", "page", "send", "settings", "spawn", "stream"]

MESSAGES = "messages"  # the list slot the rack reads
STATUS = "status"  # the one-line state of the backend
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


def state(device: Device) -> Chat:
    """The device's conversation: hung on `device.data`, so it dies with the connection."""
    chat = device.data.get("chat")
    if chat is None:
        chat = Chat(model=settings.model, window=settings.window, delay=settings.delay)
        device.data["chat"] = chat
    return chat


def row(*children: Accrete, id: str) -> Accrete:
    return b.case(*children, id=id)


@app.route("/chat", title="对话")
def page(device: Device, match: Match) -> list[dict]:
    """The page, plus the slot seeds it reads — a slot outlives a `create`, so seeding is once per
    device or a second visit doubles the transcript."""
    ops = [
        wire.create(
            markers.page(
                "/chat",
                "对话",
                b.case(
                    b.text("对话", variant="heading-1"),
                    b.text(source=STATUS, variant="muted", id="status"),
                    b.rack(source=MESSAGES, scroll=True, id="messages"),
                    b.case(
                        b.form(b.input(field="text", id="composer"), b.button("发送"), dest="chat.send", id="send"),
                        b.form(b.button("停止"), dest="chat.stop", id="stop"),
                        grid={"grid-template-columns": "1fr auto", "gap": "8px"},
                        id="composer-row",
                    ),
                    b.text("回答逐块流出，可停止，可拒绝；模型出错变一条气泡，不是一段堆栈。", variant="muted"),
                    id="chat-page",
                    grid={"grid-template-rows": "auto auto 1fr auto auto", "height": "100%", "gap": "8px"},
                ),
            )
        )
    ]
    if not device.data.get("status_seeded"):
        device.data["status_seeded"] = True  # the status line is seeded once per connection
        ops.append(wire.set(STATUS, b.text("就绪")))
    return ops


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


def send(device: Device, chat: Chat, text: str) -> None:
    """Take one message: refuse it with a reason, or put it on screen and start the reply."""
    if not text.strip():
        device.emit(wire.set(STATUS, b.text("空消息没有发出去")))
        return
    if len(text) > MAX_CHARS:
        device.emit(wire.set(STATUS, b.text(f"太长：{len(text)} 字 > {MAX_CHARS} 字上限，没有发出去")))
        return
    with chat.lock:
        if chat.busy:
            device.emit(wire.set(STATUS, b.text("上一条还在流：按「停止」或等它结束")))
            return
        chat.busy = True
        chat.stop.clear()
        chat.seq += 1
        seq = chat.seq

    chat.record("user", text)
    context = list(chat.turns)  # a snapshot: the window may move while the model is answering
    slot = f"reply.{seq}"
    device.emit(
        wire.append(MESSAGES, row(b.text(text), id=f"row-user-{seq}")),
        wire.append(MESSAGES, row(b.text(source=slot), id=f"row-bot-{seq}")),
        wire.set(slot, b.text("")),
        wire.set(STATUS, b.text(f"正在回答…（{chat.model.name}）")),
    )
    spawn(stream, (device, chat, slot, context))


def stream(device: Device, chat: Chat, slot: str, context: list[Turn]) -> None:
    """One reply, chunk by chunk. Synchronous on purpose: the thread is the caller's choice, so a test
    can run a whole reply without one."""
    pieces: list[str] = []
    failure: Exception | None = None
    try:
        for chunk in chat.model.reply(context):
            if chat.stop.is_set():
                break
            pieces.append(chunk)
            device.emit(wire.patch(slot, TEXT_VALUE, chunk, op="append"))
            if chat.delay:
                time.sleep(chat.delay)
    except Exception as exc:  # a model is a remote system: its failure is data, not control flow
        failure = exc
    finally:
        with chat.lock:
            chat.busy = False

    if failure is not None:
        device.emit(
            wire.patch(slot, TEXT_VALUE, f"\n\n⚠️ 模型出错：{failure}", op="append"),
            wire.set(STATUS, b.text(f"出错：{type(failure).__name__} · 可以再发一条")),
        )
        return
    if chat.stop.is_set():
        device.emit(
            wire.patch(slot, TEXT_VALUE, " ⏹", op="append"),
            wire.set(STATUS, b.text(f"已停止（半句没有进上下文）· {chat.total} 轮")),
        )
        return
    chat.record("assistant", "".join(pieces))
    device.emit(wire.set(STATUS, b.text(chat.status())))


@app.dests.register("chat.send")
def on_send(device: Device, frame: dict) -> None:
    text = prompt_of(frame)
    if text is None:
        device.emit(wire.set(STATUS, b.text("这一帧里没有文本字段，什么都没发")))
        return
    send(device, state(device), text)


@app.dests.register("chat.stop")
def on_stop(device: Device, frame: dict) -> None:
    chat = state(device)
    if not chat.busy:
        device.emit(wire.set(STATUS, b.text("没有正在进行的回答")))
        return
    chat.stop.set()
    device.emit(wire.set(STATUS, b.text("正在停止…")))