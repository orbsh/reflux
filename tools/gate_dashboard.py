"""The example application's gate: the dashboard, its modules, and the chat page.

Phase A drives the app over a real socket — what a page is, and what a page turn is. Phase B opens
the same app in Chromium and looks at the pixels: two charts with a size, a 3D viewport with a size,
and a nav click that swaps the page without rebuilding the shell.

Run it with `python3 tools/gate_dashboard.py` (needs Chromium for phase B).
"""

from __future__ import annotations

import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # the cdp fixture
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # the example package

from cdp import console_errors, open_page, report  # noqa: E402


def wait_for(probe, timeout: float = 20.0, step: float = 0.15):
    """Poll a browser probe until it is truthy (or the deadline passes, and it answers once more)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = probe()
        if value:
            return value
        time.sleep(step)
    return probe()

import examples.app as example  # noqa: E402
from examples.app import chat, dashboard  # noqa: E402
from examples.app.model import Scripted  # noqa: E402
from tools.wire_probe import Socket  # noqa: E402

example.heard.clear()
chat.settings.model = Scripted(window=12)
chat.settings.delay = 0.0


def get(path: str) -> tuple[int, bytes]:
    url = f"http://127.0.0.1:{PORT}{path}"
    try:
        with urllib.request.urlopen(url, timeout=10) as answered:
            return answered.status, answered.read()
    except urllib.error.HTTPError as bad:
        return bad.code, bad.read()


def nodes(frame: list[dict] | None) -> list[dict]:
    """Every node in a frame's ops, flattened — charts and canvases can be anywhere in the tree."""
    if not frame:
        return []
    out: list[dict] = []

    def walk(node):
        if isinstance(node, dict):
            out.append(node)
            for key in ("children", "item"):
                for kid in node.get(key) or []:
                    walk(kid)

    for op in frame:
        walk(op.get("data"))
    return out


def kinds(frame: list[dict] | None, kind: str) -> list[dict]:
    return [node for node in nodes(frame) if node.get("type") == kind]


def body_of(frame: list[dict] | None, slot: str) -> dict | None:
    for op in frame or []:
        if op.get("action") == "set" and op.get("slot") == slot:
            return op.get("data")
    return None


# --- phase A: the wire -----------------------------------------------------------------------


def socket_phase() -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []
    srv = example.app.make_server(0)
    global PORT
    PORT = int(srv.server_address[1])
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with Socket(PORT) as ws:
            ws.send({"dest": "reflux:hello", "data": {"path": "/"}})
            first = ws.recv()

            # 1 — the dashboard: the shell once, the page into the slot, both in one frame.
            ops = [op.get("action") for op in first or []]
            checks.append(
                (
                    "connect draws the shell and the dashboard in one frame",
                    ops[:2] == ["create", "set"] and (first or [{}])[1].get("slot") == "routes",
                    f"ops={ops}",
                )
            )

            # 2 — the page really carries the charts and the viewport, not text that says so.
            specs = kinds(first, "chart")
            canvases = len(kinds(first, "canvas"))
            want_charts = 2 if dashboard.CHARTS else 0
            want_canvas = 1 if dashboard.VIEWER else 0
            checks.append(
                (
                    "the page carries the charts and the module host it has files for",
                    len(specs) == want_charts and canvases == want_canvas,
                    f"charts={len(specs)}/{want_charts} canvases={canvases}/{want_canvas}",
                )
            )
            grammar = [
                ((node.get("bind") or {}).get("value") or {}).get("default", {}).get("type")
                for node in specs
            ]
            # The radar is a polar `view` inside a chart: find the coordinate anywhere in its spec.
            radar = json.dumps(
                [((node.get("bind") or {}).get("value") or {}).get("default") for node in specs], ensure_ascii=False
            )
            polar = '"polar"' in radar and '"area"' in radar
            checks.append(
                (
                    "the charts are G2 specs, polar for the radar",
                    (grammar[:1] == ["line"] and polar) if dashboard.CHARTS else True,
                    f"grammar={grammar} polar={polar} module={'present' if dashboard.CHARTS else 'absent'}",
                )
            )

            # 3 — the modules behind those nodes are served, from directories this app mounted.
            if dashboard.CHARTS:
                chart_js, _ = get("/assets/g2chart/index.js")
                chart_lib, _ = get("/assets/g2chart/g2.min.js")
            else:
                chart_js = chart_lib = 0
            checks.append(
                (
                    "the chart module is mounted and served when it is on disk",
                    (chart_js == 200 and chart_lib == 200) if dashboard.CHARTS else True,
                    f"index.js={chart_js} g2.min.js={chart_lib} from {dashboard.CHART_DIR}",
                )
            )
            viewer = dashboard.VIEWER
            viewer_js, _ = get("/assets/3dbrowser/index.js") if viewer else (0, b"")
            checks.append(
                (
                    "the 3D module is served when a fluxen checkout supplies it",
                    (viewer_js == 200) if viewer else True,
                    "mounted" if viewer else f"not mounted (looked in {dashboard.ASSETS})",
                )
            )

            # 4 — a page turn replaces the slot, never the shell. The chat page seeds its status line
            # as a send of its own (the page hook emits), so the turn may arrive as two frames: keep
            # reading until the frame that writes the slot shows up.
            ws.send({"dest": "go.chat", "id": "nav-chat", "data": {}})
            turn: list[dict] = []
            for _ in range(4):
                frame = ws.recv()
                if not frame:
                    continue
                if any(op.get("slot") == "routes" for op in frame):
                    turn = frame
                    break
            actions = [op.get("action") for op in turn or []]
            checks.append(
                (
                    "the chat is a page turn: the routes slot is written, the shell is not resent",
                    bool(actions)
                    and actions[0] == "set"
                    and (turn or [{}])[0].get("slot") == "routes"
                    and "create" not in actions,
                    f"actions={actions}",
                )
            )
            chat_page = json.dumps(turn, ensure_ascii=False)
            checks.append(
                (
                    "the chat page has its composer and its rack",
                    "chat.send" in chat_page and '"rack"' in chat_page,
                    f"bytes={len(chat_page)}",
                )
            )

            # 5 — chat still works from that page: one message, two rows, a streamed reply.
            ws.send({"dest": "chat.send", "id": "send", "data": {"text": {"data": "你好"}}})
            frames = [ws.recv()] + [ws.recv() for _ in range(6)]
            later = json.dumps([op for frame in frames for op in frame or []], ensure_ascii=False)
            checks.append(
                (
                    "sending a message puts rows on screen and patches the reply",
                    "row-user-1" in later and "row-bot-1" in later and '"patch"' in later,
                    f"frames={len(frames)}",
                )
            )

            # 6 — an address nobody registered is the framework's own 404, in the same shell.
            # The reply's tail may still be draining, so read until the frame that writes the slot.
            ws.send({"dest": "reflux:nav", "data": {"path": "/nope"}})
            missing = ""
            for _ in range(120):  # a stream in flight: drain its patches, then the page turn
                frame = ws.recv()
                written = json.dumps(frame, ensure_ascii=False)
                if any(op.get("slot") == "routes" for op in frame or []):
                    missing = written
                    break
            checks.append(
                (
                    "an unregistered address draws the built-in 404 in the slot",
                    "404" in missing and "没有注册" in missing,
                    f"bytes={len(missing)}",
                )
            )

            # 7 — host events reached the application, in order.
            time.sleep(0.2)
            names = [row[0] for row in example.heard]
            checks.append(
                (
                    "connect and location reached the app",
                    names[:2] == ["connect", "location"],
                    f"heard={example.heard[:2]}",
                )
            )

            # 8 — nothing the app produced was refused or raised.
            checks.append(
                (
                    "nothing was refused",
                    example.app.stats["refused"] == 0,
                    f"refused={example.app.stats['refused']}",
                )
            )
            # 9 — the same table carries a plain HTTP route: JSON for an operator, no device involved.
            code, payload = get("/status")
            try:
                answered = json.loads(payload.decode())
            except ValueError:
                answered = {}
            checks.append(
                (
                    "the app's own /status answers JSON, next to the socket",
                    code == 200
                    and sorted(answered.get("routes") or []) == ["/", "/chat"]
                    and "/status" in (answered.get("mounts") or [])
                    and "modules" in answered
                    and {"status", "messages"} <= set(answered.get("slots") or []),
                    f"{code} keys={sorted(answered)}",
                )
            )
        time.sleep(0.3)
        checks.append(
            (
                "a client that leaves is announced once",
                [row[0] for row in example.heard].count("disconnect") == 1,
                f"heard={[row[0] for row in example.heard]}",
            )
        )
    finally:
        example.app.stop()
        srv.shutdown()
        srv.server_close()
    return checks


# --- phase B: the pixels ---------------------------------------------------------------------


def browser_phase() -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []
    with open_page(app=example.app, path="/", settle=0.8) as (cdp, base):
        drawn = wait_for(lambda: "概览" in (cdp.eval("document.body.innerText") or ""), timeout=20)
        checks.append(
            (
                "the dashboard draws",
                bool(drawn) and "概览" in (cdp.eval("document.body.innerText") or ""),
                f"body={((cdp.eval('document.body.innerText') or ''))[:50]!r}",
            )
        )
        if not drawn:
            return checks

        wanted = (2 if dashboard.CHARTS else 0) + (1 if dashboard.VIEWER else 0)
        sizes = wait_for(
            lambda: cdp.eval(
                "[...document.querySelectorAll('canvas')].map(c => c.width * c.height).filter(a => a > 20000).length"
            ),
            timeout=20,
        )
        checks.append(
            (
                "every module host on the page has a real size",
                True if not wanted else (bool(sizes) and int(sizes) >= wanted),
                f"big canvases={sizes}/{wanted} charts={'mounted' if dashboard.CHARTS else 'absent'}"
                f" viewer={'mounted' if dashboard.VIEWER else 'absent'}",
            )
        )

        cdp.eval("window.__shell = document.getElementById('shell')")
        cdp.click_js("[...document.querySelectorAll('.button')].filter(el => (el.innerText || '').trim() === '对话')[0]")
        moved = wait_for(lambda: cdp.eval("location.pathname") == "/chat", timeout=20)
        checks.append(
            (
                "clicking 对话 moves the address bar and keeps the shell",
                bool(moved) and bool(cdp.eval("window.__shell === document.getElementById('shell')")),
                f"url={cdp.eval('location.pathname')!r}",
            )
        )
        inputs = cdp.eval("document.querySelectorAll('input').length")
        checks.append(
            (
                "the chat page has its composer",
                bool(wait_for(lambda: cdp.eval("document.querySelectorAll('input').length > 0"), timeout=10)),
                f"inputs={inputs}",
            )
        )
        errors = console_errors(cdp)
        checks.append(("the app logged no console errors", not errors, f"errors={errors[:2]}"))
        if not (drawn and moved):
            print(f"    base={base}")
    return checks


PORT = 0


def main() -> int:
    checks = socket_phase() + browser_phase()
    return report(checks, gate="APP GATE")


if __name__ == "__main__":
    raise SystemExit(main())