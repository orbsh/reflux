#!/usr/bin/env python3
"""Chat gate — the example's backend, over a real socket, and then the same app in a browser.

Two phases, because they answer different questions.

**A. The socket phase** drives `reflux.examples.chat` as a client: no browser, no DOM, just the
frames. That is where the backend's promises live — one conversation per connection, a reply that
arrives in chunks, a stop that stops at a boundary, a second message refused with a reason, the app's
own size limit (the protocol has none), and a window that trims while the status line keeps counting.
A refusal that only exists in a unit test is a claim; here it crosses the wire.

**B. The browser phase** puts the same page in real Chromium and types into the composer. It exists
because a backend that streams correctly into a page that never renders it is still a broken app:
the rack has to show the bubble, and the bubble has to grow while the frames land.

    python3 tools/gate_chat.py

Exit code 0 = gate passed.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cdp import Cdp, console_errors, open_page, report  # noqa: E402

from reflux.examples.chat.app import MAX_CHARS, make_app  # noqa: E402
from reflux.examples.chat.client import Socket  # noqa: E402
from reflux.examples.chat.model import Scripted  # noqa: E402

PAGE = "/"
WINDOW = 4  # small on purpose: the trimming check must not need 30 messages


def wait_for(predicate, timeout: float = 5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


# --- reading frames --------------------------------------------------------------------


def status_of(frames: list[dict]) -> str:
    """The last status line those frames wrote."""
    text = ""
    for frame in frames:
        for op in frame.get("content") or []:
            if op.get("action") == "set" and op.get("event") == "status":
                value = ((op.get("data") or {}).get("bind") or {}).get("value") or {}
                if isinstance(value.get("default"), str):
                    text = value["default"]
    return text


def patched(frames: list[dict]) -> str:
    out = []
    for frame in frames:
        for op in frame.get("content") or []:
            if op.get("action") == "patch" and isinstance(op.get("value"), str):
                out.append(op["value"])
    return "".join(out)


def appends(frames: list[dict]) -> list[str]:
    return [
        op.get("data", {}).get("id", "")
        for frame in frames
        for op in frame.get("content") or []
        if op.get("action") == "append"
    ]


def read_until(ws: Socket, marker: str, *, limit: float = 25.0) -> list[dict]:
    """Frames until one's status text contains `marker` (or the limit runs out)."""
    frames: list[dict] = []
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        try:
            frame = ws.recv(timeout=max(0.05, deadline - time.monotonic()))
        except TimeoutError:
            break
        if frame is None:
            break
        frames.append(frame)
        if marker in status_of([frame]):
            break
    return frames


def send(ws: Socket, text: str) -> None:
    ws.send({"event": "chat.send", "id": "send", "data": {"text": {"data": text}}})


def stop(ws: Socket) -> None:
    ws.send({"event": "chat.stop", "id": "stop", "data": {}})


# --- phase A ---------------------------------------------------------------------------


def socket_phase() -> list[tuple[str, bool, str]]:
    app = make_app(Scripted(window=WINDOW), delay=0.01, window=WINDOW)
    srv = app.serve(port=0)
    port = int(srv.server_address[1])
    checks: list[tuple[str, bool, str]] = []
    try:
        with Socket(port) as ws:
            # 1 — the page, and the one seed it needs.
            ws.send({"event": "reflux:hello", "data": {"path": PAGE}})
            hello = read_until(ws, "", limit=2.0) or [ws.recv(timeout=3)]
            ops = [op.get("action") for frame in hello for op in frame.get("content") or []]
            checks.append(
                (
                    "hello draws the page and seeds the status line",
                    ops[:1] == ["create"] and "set" in ops,
                    f"ops={ops}",
                )
            )

            # 2 — a message: two rows, then chunks.
            send(ws, "你好，先介绍一句")
            first = read_until(ws, "正在回答", limit=5.0)
            stream = read_until(ws, "就绪", limit=25.0)
            landed = patched(first + stream)
            rows = appends(first)
            checks.append(
                (
                    "a message puts two rows on screen",
                    rows == ["row-user-1", "row-bot-1"],
                    f"appends={rows}",
                )
            )
            checks.append(
                (
                    "the reply arrives in chunks, not one write",
                    len([frame for frame in first + stream if patched([frame])]) >= 5 and len(landed) > 40,
                    f"chunks={len([f for f in first + stream if patched([f])])} chars={len(landed)}",
                )
            )
            checks.append(
                (
                    "the status line returns to idle with a turn count",
                    "就绪" in status_of(stream) and "轮" in status_of(stream),
                    f"status={status_of(stream)!r}",
                )
            )

            # 3 — stop mid-stream.
            send(ws, "这一条会被中途停掉")
            early = read_until(ws, "正在回答", limit=5.0) + read_until(ws, "", limit=0.15)
            stop(ws)
            stopped = read_until(ws, "已停止", limit=10.0)
            partial = patched(early + stopped)
            session = app.live()[0] if app.live() else None
            chat = getattr(session, "chat", None)
            checks.append(
                (
                    "stop ends the stream at a boundary and says the half sentence is out",
                    "已停止" in status_of(stopped)
                    and "⏹" in partial
                    and chat is not None
                    and not chat.busy
                    and bool(chat.turns)
                    and chat.turns[-1].role == "user",  # no assistant turn: the half sentence stayed out
                    f"status={status_of(stopped)!r} chunk_chars={len(partial)} busy={getattr(chat, 'busy', None)} last={chat.turns[-1].role if chat and chat.turns else None}",
                )
            )

            # 4 — single flight: two sends back to back, before anything is read. Drain what the
            # stopped reply still had in flight first, so the appends counted here belong to
            # *these* two sends only.
            read_until(ws, "", limit=0.3)
            send(ws, "单飞测试的第一条")
            send(ws, "这一条必须被拒")
            refused = read_until(ws, "上一条还在流", limit=10.0)
            rows_here = [row for row in appends(refused) if row]
            checks.append(
                (
                    "a second message while streaming is refused with a reason",
                    "上一条还在流" in status_of(refused)
                    and len(rows_here) == 2  # one accepted send, one refused: no second pair of rows
                    and rows_here[0].startswith("row-user") != rows_here[1].startswith("row-user"),
                    f"status={status_of(refused)!r} appends={rows_here}",
                )
            )
            stop(ws)
            read_until(ws, "已停止", limit=10.0)

            # 5 — the app's own limits.
            send(ws, "   ")
            blank = read_until(ws, "空消息", limit=5.0)
            send(ws, "字" * (MAX_CHARS + 1))
            huge = read_until(ws, "太长", limit=5.0)
            checks.append(
                (
                    "empty and oversized messages are refused by the app, not the wire",
                    "空消息" in status_of(blank) and "太长" in status_of(huge),
                    f"blank={status_of(blank)!r} huge={status_of(huge)[:40]!r}",
                )
            )

            # 6 — the window trims, and the status line counts what it dropped.
            for i in range(WINDOW + 1):
                send(ws, f"填充第 {i} 条")
                read_until(ws, "就绪", limit=20.0)
            chat = getattr(app.live()[0], "chat", None) if app.live() else None
            trimmed = getattr(chat, "trimmed", 0)
            checks.append(
                (
                    "the context window trims and the counts add up",
                    chat is not None and len(chat.turns) == WINDOW and trimmed > 0 and chat.total > WINDOW,
                    f"turns={len(chat.turns) if chat else None} window={WINDOW} trimmed={trimmed} total={getattr(chat, 'total', None)}",
                )
            )

        # 7 — the framework's own accounting stayed clean while all of that ran.
        raised = [line for line in app.events.log if "raised" in line]
        checks.append(
            (
                "no frame was refused and no handler raised",
                app.stats["refused"] == 0 and not raised,
                f"refused={app.stats['refused']} raised={len(raised)}",
            )
        )
    finally:
        app.stop()
        srv.shutdown()
        srv.server_close()
    return checks


# --- phase B ---------------------------------------------------------------------------


def browser_phase() -> list[tuple[str, bool, str]]:
    app = make_app(Scripted(window=WINDOW), delay=0.01, window=WINDOW)
    checks: list[tuple[str, bool, str]] = []
    with open_page(app=app, path=PAGE, settle=0.6) as (cdp, base):
        body = cdp.eval("document.body.innerText") or ""
        has_input = bool(cdp.eval("!!document.querySelector('input')"))
        drawn = wait_for(lambda: "对话" in (cdp.eval("document.body.innerText") or ""))
        checks.append(
            (
                "the page draws its heading, rack and composer",
                bool(drawn) and has_input,
                f"heading={'对话' in body} input={has_input}",
            )
        )
        if not drawn:
            return checks

        cdp.eval("document.querySelector('input').focus()")
        typed = "浏览器里发的一句话"
        cdp.type_text(typed)
        # Submit with the button, not with Enter: a form's submit is a click in this vocabulary (the
        # composer is a `form` + `button` pair), and a bare Enter in a text input is not a submit.
        cdp.click_js(
            "[...document.querySelectorAll('.button')].filter(el => (el.innerText || '').trim() === '发送')[0]"
        )
        grew = wait_for(
            lambda: typed in (cdp.eval("document.body.innerText") or "")
            and "第 1 轮收到" in (cdp.eval("document.body.innerText") or ""),
            timeout=15.0,
        )
        body = cdp.eval("document.body.innerText") or ""
        checks.append(
            (
                "typing a message and submitting the composer grows a bubble that streams in",
                bool(grew),
                f"asked={'第 1 轮收到' in body} echoed={typed in body} chars={len(body)}",
            )
        )
        errors = console_errors(cdp)
        checks.append(("the page logged no console errors", not errors, f"errors={errors[:2]}"))
        if not grew:
            print(f"    base={base}")
    app.stop()
    return checks


def main() -> int:
    checks = socket_phase() + browser_phase()
    return report(checks, gate="CHAT GATE")


if __name__ == "__main__":
    raise SystemExit(main())