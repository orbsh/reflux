"""The chat page: a conversation per connection, streamed, stoppable, and honest about failures.

It is the one page of the reference app whose subject is the *backend* rather than the vocabulary,
and it is six pieces of behaviour, one per section — each asserted in `tests/test_chat_example.py`
(offline, no socket) and in `tools/gate_chat.py` (real server, real WebSocket):

1. **state per connection** — the conversation hangs off the `Device` (`ctx.data`), not off the app:
   the socket *is* the state, so a refresh is a new conversation and nothing leaks when a client goes
   away. The transcript is also the page tree's (the rows), so the backend keeps only what the model
   needs: turns, and how many of them the window holds.
2. **streaming** — one task per reply (`asyncio`) appends chunks with
   `reply.patch("/source/default", chunk, op="append")` — a `Slot`, not a name in a string. The frame
   queue is the device's, so one client's slow write never holds a model call or another device, and
   waiting for the model suspends this coroutine rather than a thread.
3. **single flight** — a second message while one is streaming is refused *with a reason on the
   status line*, not silently dropped: the composer is not disabled, so the second send is a real
   event and deserves a real answer.
4. **stop** — `chat.stop` sets an `asyncio.Event` that the reply's task checks at chunk boundaries. A stopped reply is
   **not** added to the context even though part of it is on screen: half a sentence is worse for the
   next turn than no sentence, and the status line says so.
5. **a failing model is a bubble** — the exception becomes text in the reply slot plus a status line;
   it never travels up the frame path (a raised handler would only be logged, and the user would see
   a reply that silently stopped mid-sentence).
6. **application limits** — empty and oversized messages are refused here, not at the ingest
   boundary: that boundary checks the *shape* of a frame; how long a prompt may be is this app's.

The knobs (`model`, `delay`, `window`) live in `settings`, which the reference app's `main()` fills
from the command line — one place for the whole app, because there is one app.
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

TEXT_VALUE = "/source/default"  # pointer into a text node stored in a slot
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
    stop: asyncio.Event = field(default_factory=asyncio.Event)
    # The task doing the streaming: one per conversation (the `busy` flag guarantees it), kept so that
    # a stop, a crash and a test can all see it.
    task: Any = None

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
        return f"ready · {self.model.name} · {self.total} turns (window {len(self.turns)}/{self.window}, trimmed {self.trimmed})"


def state(ctx: Context) -> Chat:
    """This connection's conversation: hung on `ctx.data`, so it dies with the connection."""
    chat = ctx.data.get("chat")
    if chat is None:
        chat = Chat(model=settings.model, window=settings.window, delay=settings.delay)
        ctx.data["chat"] = chat
    return chat


def row(*children: Accrete, id: str) -> Accrete:
    return h.frame(*children, id=id)


def page(ctx: Context, match) -> None:
    """The page — and, the first time this connection asks for it, the status line it reads.

    The seed is a **send**, so it is written as one (`(slots / "status").set(...)`), not folded into the
    page: on this side of the socket nothing is a response, and a page that later has to say
    something to more than the one device that asked (a broadcast, a nudge from a timer) says it the
    same way.

    The address and the title come from the declaration above — the framework builds the markers — so
    the handler passes its content and nothing else.
    """
    slots = slots_of(ctx)
    if not ctx.data.get("status_seeded"):
        ctx.data["status_seeded"] = True  # a slot outlives a create: seeding again would duplicate
        (slots / "status").set(h.text("ready"))
    return (
        h.frame(
            h.text("Chat", variant="heading-1"),
            h.text(source=slots / "status", variant="muted", id="status"),
            h.tiles(source=slots / "messages", id="messages"),
            h.frame(
                h.loom(
                    h.input(tag="text", id="composer"),
                    h.button("Send"),
                    sink=slots / "chat" / "send",
                    submit=["enter", "button"],
                    reset="clear",
                    id="send",
                ),
                h.loom(
                    h.button("Stop"),
                    sink=slots / "chat" / "stop",
                    submit="button",
                    id="stop",
                ),
                grid={"grid-template-columns": "1fr auto", "gap": "8px"},
                id="composer-row",
            ),
            h.text("The reply streams in chunks and can be stopped or refused; a failing model becomes a bubble, not a stack trace.", variant="muted"),
            id="chat-page",
            grid={"grid-template-rows": "auto auto 1fr auto auto", "height": "100%", "gap": "8px"},
        ),
    )


def prompt_of(frame: dict) -> str | None:
    """The composer's text out of a `chat.send` frame, or None when the frame carries nothing usable.

    A group's payload is `{tag: value}` (ADR 0032 §2) — the value is the value, with no wrapper; anything
    that is not a string counts as nothing, and a malformed frame yields None, never a raise.
    """
    data = frame.get("data")
    value = data.get("text") if isinstance(data, dict) else None
    return value if isinstance(value, str) else None


def launch(coro: Any) -> Any:
    """Start a reply as a task. A module-level seam, so a test can run it inline or not at all.

    The handler already lives on the loop (ADR 0002 P2), so no thread is involved: `create_task` is
    saying "this answer runs alongside this connection, but it is not part of any one delivery's
    budget".
    """
    return asyncio.ensure_future(coro)


async def send(ctx: Context, chat: Chat, text: str) -> None:
    """Take one message: refuse it with a reason, or put it on screen and start the reply."""
    slots = slots_of(ctx)
    if not text.strip():
        (slots / "status").set(h.text("empty message — nothing was sent"))
        return
    if len(text) > MAX_CHARS:
        (slots / "status").set(h.text(f"too long: {len(text)} characters > the {MAX_CHARS}-character limit — nothing was sent"))
        return
    # One delivery runs at a time on a loop, so this stretch has no await and no race: flipping
    # `busy` is atomic.
    if chat.busy:
        (slots / "status").set(h.text("the previous reply is still streaming: press Stop, or wait for it"))
        return
    chat.busy = True
    chat.stop.clear()
    chat.seq += 1
    seq = chat.seq

    chat.record("user", text)
    context = list(chat.turns)  # a snapshot: the window may move while the model is answering
    reply = ctx.slot(f"reply.{seq}")  # a path, because each answer gets its own plane
    with ctx.turn():  # the client sees the two rows, the empty bubble and the status at once
        (slots / "messages").append(row(h.text(text), id=f"row-user-{seq}"))
        (slots / "messages").append(row(h.text(source=reply), id=f"row-bot-{seq}"))
        reply.set(h.text(""))
        (slots / "status").set(h.text(f"answering… ({chat.model.name})"))
    chat.task = launch(stream(ctx, chat, reply, context))


async def stream(ctx: Context, chat: Chat, reply: Slot, context: list[Turn]) -> None:
    """One reply, chunk by chunk. A coroutine: waiting for the model is an `await`, so a test can run
    a whole reply inline."""
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
    except asyncio.CancelledError:  # shutdown, or a device that went away: not the model's failure
        raise
    except Exception as exc:  # a model is a remote system: its failure is data, not control flow
        failure = exc
    finally:
        chat.busy = False

    slots = slots_of(ctx)
    if failure is not None:
        with ctx.turn():
            reply.patch(TEXT_VALUE, f"\n\n⚠️ the model failed: {failure}", op="append")
            (slots / "status").set(h.text(f"failed: {type(failure).__name__} · you can send another"))
        return
    if chat.stop.is_set():
        with ctx.turn():
            reply.patch(TEXT_VALUE, " ⏹", op="append")
            (slots / "status").set(h.text(f"stopped (the half sentence stayed out of the context) · {chat.total} turns"))
        return
    chat.record("assistant", "".join(pieces))
    (slots / "status").set(h.text(chat.status()))


async def on_send(ctx: Context, frame: dict) -> None:
    text = prompt_of(frame)
    if text is None:
        (slots_of(ctx) / "status").set(h.text("this frame carried no text field — nothing was sent"))
        return
    await send(ctx, state(ctx), text)


async def on_stop(ctx: Context, frame: dict) -> None:
    chat = state(ctx)
    slots = slots_of(ctx)
    if not chat.busy:
        (slots / "status").set(h.text("nothing is streaming"))
        return
    chat.stop.set()
    (slots / "status").set(h.text("stopping…"))


def share_http(app, model) -> None:
    """Hand the framework's shared session to the model (ADR 0002 §7): `demo_app` calls this when it
    starts serving.

    One app, one pool, and the model does not own it: the hook runs inside `_boot`, where `app.http`
    already exists, and `_halt` closes it.
    """
    if not hasattr(model, "http"):
        return

    @app.startup
    def hook() -> None:
        model.http = app.http

    @app.shutdown
    def unhook() -> None:
        # The session is the app's, and it closes when the app stops; a model must not keep a closed
        # session around to send its next request through.
        model.http = None


async def on_disconnect(ctx: Context, frame: dict) -> None:
    """The connection is gone, so the reply is too: streaming chunks into a device that no longer
    exists is wasted work, and `task` is the only handle on it."""
    chat = ctx.data.get("chat")
    task = getattr(chat, "task", None) if chat is not None else None
    if task is not None and not task.done():
        task.cancel()


def register(app, slots: DemoSlots) -> None:
    """Put this page on the app: its route, and its two uplinks.

    The route is declared here as a call rather than a decorator (`app.page(...)(page)`) because this
    module must not import the app: under `python3 -m examples.X.demo_app` the app module runs as
    `__main__`, and `from .demo_app import app` would build a second copy of it.
    """
    app.page("/chat", title="Chat")(page)
    app.on(slots / "chat" / "send", on_send)
    app.on(slots / "chat" / "stop", on_stop)
    app.on("disconnect", on_disconnect)

