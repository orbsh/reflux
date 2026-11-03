#!/usr/bin/env python3
"""Site walkthrough: routing over one socket, one Enter at a time.

Modelled on fluxen's `examples/walkthrough.py` — a numbered step, an Enter, and the frames printed as
they land. The subject here is the five things a routed reflux app does, in the order they happen:

  1  connect with a query       the shell and the page arrive in ONE frame; the app hears `connect`
                                with the address bar's path and query
  2  click 关于 (a normal event) the frame carries the `routes` slot only — the shell is not redrawn
  3  browser back               `reflux:nav` arrives, that path is drawn again, the app hears `location`
  4  a pasted deep link         a second client opens /about?from=link directly, first frame and all
  5  a path nobody registered   the framework's own 404, drawn inside the same shell
  6  the client goes away       the app hears `disconnect`

The demo starts its own app on a free port unless `--attach` is given, so `--auto` is one command with
no setup. `--attach` can only print frames: the app's own event log lives in the other process.

Usage:
  python3 -m examples.site.walkthrough [--auto] [--path /] [--query "?from=paste"]
  python3 -m examples.site.walkthrough --attach --port 8200

Ctrl-C quits.
"""

from __future__ import annotations

import sys
from pathlib import Path

# `python3 examples/site/{name}.py` as well as `-m examples.site.{name}`: a script's own directory is
# what goes on sys.path by default, and this example needs the repo root (it imports reflux).
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
import time

from examples.chat.client import Socket
from examples.pacing import Step, read_for
from examples.site.app import PAGES, SHELL_ID, make_app


def texts(node: object) -> list[str]:
    """The literal text nodes inside a structure — enough to say which page landed."""
    if not isinstance(node, dict):
        return []
    out: list[str] = []
    value = ((node.get("bind") or {}).get("value") or {})
    if node.get("type") == "text" and isinstance(value.get("default"), str) and value["default"]:
        out.append(value["default"])
    for child in node.get("children") or []:
        out.extend(texts(child))
    return out


def describe(frame: dict) -> str:
    """One frame as a line: its operations, and the first words of what it drew."""
    parts: list[str] = []
    for op in frame:
        action = op.get("action")
        data = op.get("data") if isinstance(op.get("data"), dict) else {}
        head = texts(data)
        said = f"「{head[0][:18]}」" if head else ""
        if action == "create":
            parts.append(f"create({data.get('type')}{said})")
        elif action in ("set", "append", "remove"):
            parts.append(f"{action}({op.get('slot')}{said})")
        else:
            parts.append(f"{action}({op.get('slot')})")
    return f"{len(frame)} op · " + " · ".join(parts)


def show(frames: list[dict]) -> None:
    for frame in frames:
        print(f"    ← {describe(frame)}")


def heard(app: object) -> str:
    """The host events the app recorded, one line each — or a note when we attached to a stranger."""
    log = getattr(app, "heard", None)
    if log is None:
        return "    （--attach：app 自己的事件日志在另一个进程里，这里读不到）"
    if not log:
        return "    （app 还没听到任何宿主事件）"
    return "\n".join(f"    · {name} {where} {detail}" for name, where, detail in log)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8200)
    ap.add_argument("--attach", action="store_true", help="talk to an app that is already running")
    ap.add_argument("--auto", action="store_true", help="no Enter waits")
    ap.add_argument("--path", default="/", help="the address the first client opens (a pasted link)")
    ap.add_argument("--query", default="?from=paste&tag=a&tag=b", help="its query string, as the browser has it")
    args = ap.parse_args()

    server = None
    app: object | None = None
    port = args.port
    if not args.attach:
        app = make_app()
        server = app.serve(port=port)  # port 0 is fine: we read the bound one back
        port = int(server.server_address[1])
        print(f"[walkthrough] 自己起的 app 在 127.0.0.1:{port}（routes={sorted(PAGES)}，shell={SHELL_ID!r}）")

    step = Step(args.auto)
    try:
        with Socket(port, host=args.host) as ws:
            step.wait(f"connect {args.path}{args.query} —— 外框和页面一帧到（connect 事件带上地址）")
            ws.send({"dest": "reflux:hello", "data": {"path": args.path, "query": args.query}})
            show(read_for(ws, 1.2))
            print(heard(app))

            step.wait("点「关于」——一个普通事件：只写 routes 槽，外框不重画")
            ws.send({"dest": "go.about", "id": "go-about", "data": {}})
            show(read_for(ws, 0.8))
            print(heard(app))

            step.wait("浏览器后退——reflux:nav 上来，这个地址重画，app 听到 location")
            ws.send({"dest": "reflux:nav", "data": {"path": args.path, "query": args.query}})
            show(read_for(ws, 0.8))
            print(heard(app))

            step.wait("深链：另一个客户端直接打开 /about?from=link——第一帧就是那一页")
            with Socket(port, host=args.host) as deep:
                deep.send({"dest": "reflux:hello", "data": {"path": "/about", "query": "?from=link"}})
                show(read_for(deep, 1.2))
                print(heard(app))

                step.wait("没人注册过的地址——框架自己的 404，画在同一个外框里")
                with Socket(port, host=args.host) as lost:
                    lost.send({"dest": "reflux:hello", "data": {"path": "/nowhere", "query": ""}})
                    show(read_for(lost, 1.2))
                    print(heard(app))

            step.wait("客户端走开——app 听到 disconnect")
            with Socket(port, host=args.host) as gone:
                gone.send({"dest": "reflux:hello", "data": {"path": "/", "query": ""}})
                read_for(gone, 0.4)
            time.sleep(0.3)
            print(heard(app))
    finally:
        if server is not None:
            if app is not None:
                app.stop()
            server.shutdown()
            server.server_close()
    print("\n[walkthrough] 完")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())