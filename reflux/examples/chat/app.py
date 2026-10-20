"""An AI chat application: the backend is the subject, the page is the skin.

    python3 -m reflux.examples.chat.app --port 8100            # page + backend
    python3 -m reflux.examples.chat.walkthrough --auto         # the demo, no browser

Six pieces of backend behaviour, one per section below — each is asserted in
`tests/test_chat_example.py` (offline, no socket) and `tools/gate_chat.py` (real server, real
WebSocket):

1. **state per connection** — the conversation hangs off the `Session`, not off the app: reflux's
   model is that the socket *is* the state, so a refresh is a new conversation and nothing leaks when
   a client goes away. The transcript is also the page tree's (the rows), so the backend only keeps
   what the model needs: turns, and how many of them the window holds.
2. **streaming** — a worker thread per reply appends chunks with `wire.patch(slot, "/bind/value/default",
   chunk, op="append")`. The frame queue is the session's, so one client's slow write never holds a
   model call or another session.
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
   boundary: that boundary checks the *shape* of a frame, which is the protocol's business; how long a
   prompt may be is this app's.

The page is one route, built with `markers.page` so the runtime owns the URL and the title.
"""

from __future__ import annotations

import argparse
import threading
import time
from dataclasses import dataclass, field

from reflux import wire
from reflux.app import App, Session
from reflux.sdk import builders as b
from reflux.sdk import markers
from reflux.sdk.types import Accrete

from .model import Model, OpenAI, Scripted, Turn

__all__ = ["Chat", "MAX_CHARS", "WINDOW", "make_app", "page"]

MESSAGES = "messages"  # the list slot the rack reads
STATUS = "status"  # the one-line state of the backend
TEXT_VALUE = "/bind/value/default"  # pointer into a text node stored in a slot
MAX_CHARS = 4096  # an application limit, not a wire limit
WINDOW = 12  # turns of context the model sees; older ones are dropped


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


def state(session: Session) -> Chat:
    """The session's conversation, created on first use and collected with the session."""
    chat = getattr(session, "chat", None)
    if chat is None:
        chat = Chat(model=Scripted(window=WINDOW), window=WINDOW)
        setattr(session, "chat", chat)  # the session is the state: it dies with the connection
    return chat


def row(*children: Accrete, id: str) -> Accrete:
    return b.case(*children, id=id)


def page(session: Session, path: str = "/") -> list[dict]:
    """The one page, plus the slot seeds it reads. Borrowed from `demo_app`: a slot outlives a
    `create`, so the seed happens once per session or a second visit doubles it.

    `App` calls this as `page(session, path)`; a second path gets the framework's own shape of an
    answer (a page that says so) rather than the chat page wearing the wrong address.
    """
    if path not in ("", "/"):
        return [
            wire.create(
                b.case(
                    b.text("404", variant="heading-1"),
                    b.text(f"这个示例只有一个页面，没有注册 {path}", variant="muted"),
                )
            )
        ]
    ops = [
        wire.create(
            markers.page(
                "/",
                "对话",
                b.text("对话", variant="heading-1"),
                b.text(source=STATUS, variant="muted", id="status"),
                b.rack(source=MESSAGES, scroll=True, id="messages"),
                b.form(b.input(field="text", id="composer"), b.button("发送"), event="chat.send", id="send"),
                b.form(b.button("停止"), event="chat.stop", id="stop"),
                b.text(
                    "一个最小可用的后端：会话挂在连接上，回答逐块流出，可停止，可拒绝，模型出错变一条气泡。",
                    variant="muted",
                ),
            )
        )
    ]
    if not getattr(session, "chat_seeded", False):
        setattr(session, "chat_seeded", True)
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


def send(session: Session, chat: Chat, text: str) -> None:
    """Take one message: refuse it with a reason, or put it on screen and start the reply."""
    if not text.strip():
        session.draw(wire.set(STATUS, b.text("空消息没有发出去")))
        return
    if len(text) > MAX_CHARS:
        session.draw(wire.set(STATUS, b.text(f"太长：{len(text)} 字 > {MAX_CHARS} 字上限，没有发出去")))
        return
    with chat.lock:
        if chat.busy:
            session.draw(wire.set(STATUS, b.text("上一条还在流：按「停止」或等它结束")))
            return
        chat.busy = True
        chat.stop.clear()
        chat.seq += 1
        seq = chat.seq

    chat.record("user", text)
    context = list(chat.turns)  # a snapshot: the window may move while the model is answering
    slot = f"reply.{seq}"
    session.draw(
        wire.append(MESSAGES, row(b.text(text), id=f"row-user-{seq}")),
        wire.append(MESSAGES, row(b.text(source=slot), id=f"row-bot-{seq}")),
        wire.set(slot, b.text("")),
        wire.set(STATUS, b.text(f"正在回答…（{chat.model.name}）")),
    )
    spawn(stream, (session, chat, slot, context))


def stream(session: Session, chat: Chat, slot: str, context: list[Turn]) -> None:
    """One reply, chunk by chunk. Synchronous on purpose: the thread is the caller's choice, so a
    test can run a whole reply without one."""
    pieces: list[str] = []
    failure: Exception | None = None
    try:
        for chunk in chat.model.reply(context):
            if chat.stop.is_set():
                break
            pieces.append(chunk)
            session.draw(wire.patch(slot, TEXT_VALUE, chunk, op="append"))
            if chat.delay:
                time.sleep(chat.delay)
    except Exception as exc:  # a model is a remote system: its failure is data, not control flow
        failure = exc
    finally:
        with chat.lock:
            chat.busy = False

    if failure is not None:
        session.draw(
            wire.patch(slot, TEXT_VALUE, f"\n\n⚠️ 模型出错：{failure}", op="append"),
            wire.set(STATUS, b.text(f"出错：{type(failure).__name__} · 可以再发一条")),
        )
        return
    if chat.stop.is_set():
        session.draw(
            wire.patch(slot, TEXT_VALUE, " ⏹", op="append"),
            wire.set(STATUS, b.text(f"已停止（半句没有进上下文）· {chat.total} 轮")),
        )
        return
    chat.record("assistant", "".join(pieces))
    session.draw(wire.set(STATUS, b.text(chat.status())))


def make_app(model: Model | None = None, *, delay: float = 0.02, window: int = WINDOW) -> App:
    """The app: one page, two events. `model`/`delay` are knobs for the demo and the gates."""
    app = App()
    app.page = page  # type: ignore[assignment]  # one page, no route table
    chosen: Model = model if model is not None else Scripted(window=window)

    def chat_of(session: Session) -> Chat:
        chat = state(session)
        chat.model = chosen
        chat.window = window
        chat.delay = delay
        return chat

    @app.events.register("chat.send")
    def on_send(session: Session, frame: dict) -> None:
        text = prompt_of(frame)
        if text is None:
            session.draw(wire.set(STATUS, b.text("这一帧里没有文本字段，什么都没发")))
            return
        send(session, chat_of(session), text)

    @app.events.register("chat.stop")
    def on_stop(session: Session, frame: dict) -> None:
        chat = chat_of(session)
        if not chat.busy:
            session.draw(wire.set(STATUS, b.text("没有正在进行的回答")))
            return
        chat.stop.set()
        session.draw(wire.set(STATUS, b.text("正在停止…")))

    return app


def main() -> None:
    ap = argparse.ArgumentParser(description="An AI chat app: the page, served with its backend.")
    ap.add_argument("--port", type=int, default=8100)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--model", choices=("scripted", "openai"), default="scripted")
    ap.add_argument("--delay", type=float, default=0.02, help="seconds between chunks (0 = as fast as possible)")
    ap.add_argument("--window", type=int, default=WINDOW)
    args = ap.parse_args()
    model: Model = OpenAI() if args.model == "openai" else Scripted(window=args.window)
    app = make_app(model, delay=args.delay, window=args.window)
    print(f"[chat] model={model.name} window={args.window} chunk_delay={args.delay}s", flush=True)
    app.serve_forever(args.port, args.host)


if __name__ == "__main__":
    main()