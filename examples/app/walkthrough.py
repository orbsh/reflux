"""The example, walked through without a browser.

    python3 -m examples.app.walkthrough --auto

Seven steps, in the order a person meets them: the dashboard arriving, the page turn into the chat, a
reply streaming, a stop that keeps the half sentence out, an address nobody registered, the `/status`
route answering JSON over plain HTTP, and the disconnect the app hears on the way out. Each step
prints the frames that crossed the wire.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
import json
import time
import urllib.request

from examples.pacing import Step, read_for
from tools.wire_probe import Socket

PAGE = "/"


def show(label: str, frames: list[list[dict]]) -> None:
    """One line per frame: the actions, and the slot or dest they touched."""
    if not frames:
        print(f"    {label}: （没有帧）")
        return
    for frame in frames:
        print(f"    {label}:", [(op.get("action"), op.get("slot") or op.get("dest") or "") for op in frame])


def node_kinds(frame: list[dict]) -> dict[str, int]:
    """What the frame's tree is made of: chart nodes, canvas nodes, racks, forms."""
    counts: dict[str, int] = {}

    def walk(node):
        if isinstance(node, dict):
            kind = node.get("type")
            if isinstance(kind, str):
                counts[kind] = counts.get(kind, 0) + 1
            for key in ("children", "item"):
                for kid in node.get(key) or []:
                    walk(kid)

    for op in frame:
        walk(op.get("data"))
    return counts


def main() -> int:
    ap = argparse.ArgumentParser(description="Walk through the example application.")
    ap.add_argument("--port", type=int, default=0, help="0 starts the app on a free port")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--auto", action="store_true", help="no Enter waits")
    args = ap.parse_args()

    import examples.app as example  # the app is built at import; this starts it

    server = example.app.serve(port=args.port, host=args.host)
    port = int(server.server_address[1])
    print(f"[walkthrough] 应用在 http://{args.host}:{port}/（路由 {[r.path for r in example.app.routes]}）")

    step = Step(args.auto)
    try:
        with Socket(port, host=args.host) as ws:
            step.wait("打开 / —— 外框一次，页面进 routes 槽，图表和 3D 视口都在这一帧里")
            ws.send({"dest": "reflux:hello", "data": {"path": PAGE}})
            first = read_for(ws, 1.2)
            show("hello", first)
            if first:
                print("    这一页的节点：", node_kinds(first[0]))

            step.wait("点「对话」——一次页面切换：只写 routes 槽，外框不重画")
            ws.send({"dest": "go.chat", "id": "nav-chat", "data": {}})
            show("go.chat", read_for(ws, 0.8))

            step.wait("发一句话——两条行先到，回答逐块 patch 进来")
            ws.send({"dest": "chat.send", "id": "send", "data": {"text": {"data": "用三句话解释一下 reflux"}}})
            frames = read_for(ws, 1.0)
            show("chat.send", frames)

            step.wait("按「停止」——半句留在屏幕上，但不进上下文")
            ws.send({"dest": "chat.stop", "id": "stop", "data": {}})
            show("chat.stop", read_for(ws, 0.6))

            step.wait("跳到一个没注册的地址——框架自己的 404，画在同一个外框里")
            ws.send({"dest": "reflux:nav", "data": {"path": "/nowhere"}})
            missing = read_for(ws, 0.8)
            show("nav /nowhere", missing)
            if missing:
                print("    404 页：", json.dumps(missing[0][0].get("data"), ensure_ascii=False)[:120])

            # A plain HTTP route in the same table: the socket is one entry, `/status` is another.
            step.wait("/status——同一张表里的普通 HTTP 接口：页面用帧，运维要 JSON")
            with urllib.request.urlopen(f"http://{args.host}:{port}/status", timeout=5) as answered:
                print("    /status:", answered.status, answered.headers.get("content-type"))
                print("   ", json.dumps(json.loads(answered.read().decode()), ensure_ascii=False))

        step.wait("客户端走开——app 听到 disconnect")
        time.sleep(0.4)
        print("    heard:", example.heard)
    finally:
        example.app.stop()
        server.shutdown()
        server.server_close()
    print("[walkthrough] 完")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())