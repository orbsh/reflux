#!/usr/bin/env python3
"""Chat walkthrough: the backend's behaviour, one Enter at a time.

Modelled on fluxen's `examples/walkthrough.py` — the same skeleton (a numbered step, an Enter, the
frames it produced printed as they land) with a different subject: there, a renderer being fed a
page; here, a *backend* answering a client.

Steps:
  1  connect + hello          the page comes back (one `create`), then the status seed
  2  send one message         two rows land, and the reply falls into its slot chunk by chunk
  3  send, then stop          it stops at a chunk boundary; the half sentence stays out of context
  4  send while streaming     refused with a reason on the status line (single flight)
  5  empty / oversized        refused at the app's own boundary, not at the wire's
  6  fill the window          send until turns get trimmed; the status line counts what was cut

The demo starts its own app on a free port unless `--attach` is given, so `--auto` is one command
with no setup. `--model openai` needs `OPENAI_BASE_URL`/`OPENAI_API_KEY`; the default is the offline
scripted model.

Usage:
  python3 -m examples.chat.walkthrough [--auto] [--delay 0.01] [--window 6] [--port 8100]
  python3 -m examples.chat.walkthrough --attach --port 8100

Ctrl-C quits.
"""

from __future__ import annotations

import sys
from pathlib import Path

# `python3 examples/chat/{name}.py` as well as `-m examples.chat.{name}`: a script's own directory is
# what goes on sys.path by default, and this example needs the repo root (it imports reflux).
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
import sys
import time

from examples.chat.app import MAX_CHARS, WINDOW, make_app
from examples.chat.client import Socket
from examples.chat.model import Model, OpenAI, Scripted


def nodes(node: object) -> int:
    """How many nodes a `create` carries — enough to say 'a page arrived' without printing it."""
    if not isinstance(node, dict):
        return 0
    return 1 + sum(nodes(child) for child in node.get("children") or [])


def describe(frame: dict) -> str:
    """One frame as a line: the ops it carries, with just enough shape to recognise them."""
    content = frame
    parts: list[str] = []
    for op in content:
        action = op.get("action")
        if action == "create":
            parts.append(f"create({nodes(op.get('data'))} nodes)")
        elif action == "append":
            parts.append(f"append→{op.get('event')}")
        elif action == "set":
            parts.append(f"set({op.get('event')})")
        elif action == "patch":
            value = op.get("value")
            shown = repr(value if len(str(value)) <= 12 else str(value)[:9] + "…")
            parts.append(f"patch({op.get('event')} += {shown})")
        elif action == "remove":
            parts.append(f"remove({op.get('event')})")
        else:
            parts.append(str(action))
    return f"{len(content)} op · " + " · ".join(parts)


def read_for(ws: Socket, seconds: float) -> list[dict]:
    """Every frame that lands within `seconds` (reading stops early once the wire goes quiet)."""
    frames: list[dict] = []
    deadline = time.monotonic() + seconds
    while True:
        left = deadline - time.monotonic()
        if left <= 0:
            return frames
        try:
            frame = ws.recv(timeout=left)
        except TimeoutError:
            return frames
        if frame is None:
            return frames
        frames.append(frame)


def read_until(ws: Socket, marker: str, *, limit: float = 30.0) -> list[dict]:
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
        if marker in describe(frame) or marker in status_of([frame]):
            break
    return frames


class Step:
    """The Enter gate, borrowed whole from fluxen's walkthrough: it is the pacing, not the subject."""

    def __init__(self, auto: bool, pause: float = 0.4) -> None:
        self.auto = auto
        self.pause = pause
        self.n = 0

    def wait(self, title: str) -> None:
        self.n += 1
        print(f"\n[{self.n}] {title}")
        if self.auto:
            time.sleep(self.pause)
        else:
            try:
                input("    ↵ 回车继续 … ")
            except EOFError:
                print("    (stdin closed — switching to --auto)")
                self.auto = True


def show(frames: list[dict], *, limit: int = 6) -> None:
    """Print a frame list, collapsing a long tail (a stream is dozens of patches)."""
    for frame in frames[:limit]:
        print(f"    ← {describe(frame)}")
    if len(frames) > limit:
        print(f"    ← …还有 {len(frames) - limit} 帧（流式块）")


def patches(frames: list[dict]) -> str:
    """The text a run of patch frames appended, in order — the reply as the page assembled it."""
    out = []
    for frame in frames:
        for op in frame:
            if op.get("action") == "patch" and isinstance(op.get("value"), str):
                out.append(op["value"])
    return "".join(out)


def status_of(frames: list[dict]) -> str:
    """The last status line those frames wrote — the backend's own words about what just happened."""
    text = ""
    for frame in frames:
        for op in frame:
            if op.get("action") == "set" and op.get("event") == "status":
                value = ((op.get("data") or {}).get("bind") or {}).get("value") or {}
                if isinstance(value.get("default"), str):
                    text = value["default"]
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8100)
    ap.add_argument("--attach", action="store_true", help="talk to an app that is already running")
    ap.add_argument("--auto", action="store_true", help="no Enter waits")
    ap.add_argument("--delay", type=float, default=0.01, help="seconds between chunks (the pacing you watch)")
    ap.add_argument("--window", type=int, default=6, help="context window for the demo's app")
    ap.add_argument("--model", choices=("scripted", "openai"), default="scripted")
    args = ap.parse_args()

    model: Model = OpenAI() if args.model == "openai" else Scripted(window=args.window)
    server = None
    port = args.port
    if not args.attach:
        app = make_app(model, delay=args.delay, window=args.window)
        server = app.serve(port=port)  # port 0 is fine: we read the bound one back
        port = int(server.server_address[1])
        print(f"[walkthrough] 自己起的 app 在 127.0.0.1:{port}（model={model.name}，window={args.window}）")
    else:
        print(f"[walkthrough] 连已运行的应用 127.0.0.1:{port}")

    step = Step(args.auto)
    try:
        try:
            ws = Socket(port, args.host)
        except OSError as exc:
            print(f"连不上 127.0.0.1:{port}（{exc}）——先起 app，或去掉 --attach 让它自己起。")
            return 1
        with ws:
            step.wait("握手：hello 带路径上去，服务端回一帧页面")
            ws.send({"dest": "reflux:hello", "data": {"path": "/"}})
            show(read_for(ws, 0.6))

            step.wait("发一条消息：两行入场，回话逐块落进它自己的槽")
            ws.send({"dest": "chat.send", "id": "send", "data": {"text": {"data": "你好，先介绍一下你自己"}}})
            early = read_for(ws, max(0.4, args.delay * 12))
            show(early, limit=4)
            rest = read_until(ws, "就绪", limit=20)
            reply = patches(early + rest)
            print(f"    ← 回话拼起来 {len(reply)} 字；首句：{reply.splitlines()[0][:48] if reply else '（空）'}")
            show(rest[-2:], limit=2)

            step.wait("发第二条，紧接着按「停止」：块边界停住，半句不进上下文")
            # Both frames go out before anything is read: at a small --delay the whole reply would
            # otherwise finish in the time it takes us to read one frame, and the step would show a
            # stop that had nothing left to stop.
            ws.send({"dest": "chat.send", "id": "send", "data": {"text": {"data": "这一条我要中途停掉"}}})
            ws.send({"dest": "chat.stop", "id": "stop", "data": {}})
            frames = read_until(ws, "已停止", limit=20)
            partial = patches(frames).replace(" ⏹", "")  # the ⏹ is the bubble's own mark, not reply text
            print(f"    ← 停之前流出 {len(partial)} 字：{partial[:24]!r}")
            print(f"    ← 状态行：{status_of(frames) or '（没等到「已停止」）'}")

            step.wait("流还没结束时再发一条：被拒，并说明原因（单飞）")
            # Send #2 goes out before we read anything: the refusal is decided in the handler, so
            # the only pacing that matters is that the first reply has not finished — sending two
            # frames back to back guarantees that (the reader thread handles them in order).
            ws.send({"dest": "chat.send", "id": "send", "data": {"text": {"data": "流未结束时的第一条"}}})
            ws.send({"dest": "chat.send", "id": "send", "data": {"text": {"data": "这一条应该被拒（单飞）"}}})
            frames = read_until(ws, "上一条还在流", limit=10)
            print(f"    ← 状态行：{status_of(frames) or '（没有拒绝——流已经结束，说明延迟太小）'}")
            ws.send({"dest": "chat.stop", "id": "stop", "data": {}})
            read_until(ws, "已停止", limit=20)

            step.wait("空消息与超长：应用层的两道门（协议层只查形状，不查长度）")
            for text, why in (("   ", "空"), ("字" * (MAX_CHARS + 1), f"超 {MAX_CHARS} 字")):
                ws.send({"dest": "chat.send", "id": "send", "data": {"text": {"data": text}}})
                frames = read_until(ws, "没有发出去", limit=5)
                print(f"    {why} → 状态行：{status_of(frames) or '（没收到）'}")

            step.wait(f"填满窗口：连发到超过 {args.window} 轮，状态行开始报裁剪")
            for i in range(1, args.window + 2):
                ws.send({"dest": "chat.send", "id": "send", "data": {"text": {"data": f"第 {i} 条填充消息"}}})
                frames = read_until(ws, "就绪", limit=20)
                print(f"    第 {i} 条 → {status_of(frames) or '（状态行未变）'}")
    except KeyboardInterrupt:
        pass
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()

    print("\n完成。六件事都在这条连接上发生过：出页、流式、停止、单飞、应用层拒绝、窗口裁剪。")
    print("页面版：python3 -m examples.chat.app --port 8100，然后开 http://127.0.0.1:8100/")
    return 0


if __name__ == "__main__":
    sys.exit(main())