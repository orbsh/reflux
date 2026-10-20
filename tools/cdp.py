"""Shared harness for the reflux gates: serve the page, drive headless chromium over CDP.

stdlib only, on purpose — the gate must run anywhere the library runs. The CDP client is
minimal (CDP needs text frames and nothing more); the launcher gives every gate the same
hermetic setup: a dedicated profile, a free debug port, a same-origin server, and an error
hook installed before any page script runs.

The page is served through `reflux.app.App` (the page tree plus the `/ws` channel), so the
renderer connects even when the gate drives the planes by hand; a gate with a producer of its
own passes `app=`.

The gates keep only their assertions; everything reusable lives here.
"""

from __future__ import annotations

import base64
import json
import os
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from reflux.app import App  # noqa: E402

CHROMIUM = "chromium"
IDLE = "data:text/html,<title>reflux-gate</title>"

# Injected before any page script runs. CDP's console stream is not always delivered on
# headless setups, so the page keeps its own record too.
ERROR_HOOK = """
window.__errs = [];
window.addEventListener("error", (e) => window.__errs.push("error: " + (e.message || e.type)));
window.addEventListener("unhandledrejection", (e) => window.__errs.push("rejection: " + e.reason));
const _ce = console.error.bind(console);
console.error = (...a) => { window.__errs.push("console.error: " + a.join(" ")); _ce(...a); };
"""


class Ws:
    """Text-frame WebSocket client. No fragmentation reassembly: CDP frames fit one frame."""

    def __init__(self, url: str, timeout: float = 30.0) -> None:
        hostport, path = url[5:].split("/", 1)
        host, port = hostport.split(":")
        self.sock = socket.create_connection((host, int(port)), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode())
        head = b""
        while b"\r\n\r\n" not in head:
            head += self.sock.recv(1)
        if b" 101 " not in head.split(b"\r\n")[0]:
            raise RuntimeError(f"ws handshake failed: {head.split(b'\r\n')[0]!r}")
        self.buf = head.split(b"\r\n\r\n", 1)[1]

    def _take(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise EOFError("socket closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        mask = os.urandom(4)
        n = len(payload)
        hdr = bytearray([0x80 | opcode])
        if n < 126:
            hdr.append(0x80 | n)
        elif n < 65536:
            hdr.append(0x80 | 126)
            hdr += struct.pack(">H", n)
        else:
            hdr.append(0x80 | 127)
            hdr += struct.pack(">Q", n)
        hdr += mask
        self.sock.sendall(bytes(hdr) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def _recv_frame(self) -> bytes:
        while True:
            b0, b1 = self._take(2)
            opcode, masked, ln = b0 & 0x0F, b1 & 0x80, b1 & 0x7F
            if ln == 126:
                ln = struct.unpack(">H", self._take(2))[0]
            elif ln == 127:
                ln = struct.unpack(">Q", self._take(8))[0]
            mask = self._take(4) if masked else None
            payload = self._take(ln)
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if opcode == 0x8:
                raise EOFError("ws closed by peer")
            if opcode == 0x9:
                self._send_frame(0xA, payload)
                continue
            if opcode == 0xA:
                continue
            return payload

    def send(self, obj: dict) -> None:
        self._send_frame(0x1, json.dumps(obj).encode())

    def recv(self) -> dict:
        return json.loads(self._recv_frame())

    def close(self) -> None:
        try:
            self._send_frame(0x8, b"")
        finally:
            self.sock.close()


class Cdp:
    """CDP session on a page target; every non-reply message is kept as an event."""

    def __init__(self, ws_url: str) -> None:
        self.ws = Ws(ws_url)
        self.next_id = 0
        self.events: list[dict] = []

    def call(self, method: str, **params) -> dict:
        self.next_id += 1
        mid = self.next_id
        self.ws.send({"id": mid, "method": method, "params": params})
        while True:
            msg = self.ws.recv()
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})
            self.events.append(msg)

    def drain(self) -> None:
        """Pull whatever the browser has queued, by issuing a trivial call."""
        self.call("Runtime.evaluate", expression="1")

    def eval(self, expression: str):
        res = self.call(
            "Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True
        )
        if res.get("exceptionDetails"):
            raise RuntimeError(f"eval failed: {res['exceptionDetails']}")
        return res.get("result", {}).get("value")

    def of(self, method: str) -> list[dict]:
        return [e["params"] for e in self.events if e.get("method") == method]

    # --- real input (the browser's own event pipeline, not synthetic dispatches) -----------

    def box(self, selector: str) -> dict:
        """The centre of an element — the coordinate a real mouse event needs."""
        return self.box_js(f"document.querySelector({json.dumps(selector)})")

    def box_js(self, expression: str) -> dict:
        """The centre of whatever `expression` resolves to (a JS expression, or null).

        The element is scrolled into view first: a real mouse event lands at viewport
        coordinates, and an element below the fold would swallow nothing.
        """
        rect = self.eval(
            "(() => {"
            f" const el = ({expression});"
            " if (!el) return null;"
            " el.scrollIntoView({ block: 'center', inline: 'center' });"
            " const r = el.getBoundingClientRect();"
            " return { x: r.left + r.width / 2, y: r.top + r.height / 2 };"
            "})()"
        )
        if not rect:
            raise RuntimeError(f"no element for {expression!r}")
        return rect

    def click(self, selector: str, modifiers: int = 0) -> None:
        """A real mouse click at the element's centre; it also blurs whatever was focused."""
        self._press(self.box(selector), modifiers)

    def click_js(self, expression: str, modifiers: int = 0) -> None:
        """A real mouse click on whatever a JS expression resolves to (modifiers: 1 alt, 2 ctrl,
        4 meta, 8 shift)."""
        self._press(self.box_js(expression), modifiers)

    def _press(self, at: dict, modifiers: int = 0) -> None:
        for kind, buttons in (("mousePressed", 1), ("mouseReleased", 0)):
            self.call(
                "Input.dispatchMouseEvent",
                type=kind,
                x=at["x"],
                y=at["y"],
                button="left",
                buttons=buttons,
                clickCount=1,
                modifiers=modifiers,
            )

    def type_text(self, text: str) -> None:
        """Real keystrokes into whatever is focused, one key event per character."""
        for char in text:
            self.call("Input.dispatchKeyEvent", type="keyDown", text=char,
                      unmodifiedText=char, key=char)
            self.call("Input.dispatchKeyEvent", type="keyUp", key=char)

    def close(self) -> None:
        self.ws.close()


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_devtools(port: int, timeout: float = 25.0) -> dict:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2) as r:
                return json.load(r)
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as exc:
            last = str(exc)
            time.sleep(0.25)
    raise RuntimeError(f"devtools endpoint never came up on :{port} ({last})")


def _page_target(port: int, timeout: float = 15.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=3) as r:
            for t in json.load(r):
                if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                    return t
        time.sleep(0.2)
    raise RuntimeError("no page target with a debugger url")


@contextmanager
def open_page(
    root: Path | None = None,
    *,
    app: App | None = None,
    path: str = "/",
    boot: str = "!!(window.fluxen && typeof window.fluxen.send === 'function')",
    settle: float = 0.5,
    timeout: float = 20.0,
) -> Iterator[tuple[Cdp, str]]:
    """Serve the page (through `app`, else a fresh App over `root`), load `path`, yield (cdp, base).

    Waits for `boot` to become truthy (the renderer is mounted and its uplink handle is published)
    and drains late asset requests, so an external-request check is honest. A gate with a producer
    of its own passes `app=` and reads that app's `log` for the frames that crossed the channel;
    `path` is how a gate opens a deep link (the page's hello carries it).
    """
    app = app or App(root)
    srv = app.make_server(0)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    profile = tempfile.mkdtemp(prefix="reflux-gate-")
    port = free_port()
    proc = subprocess.Popen(
        [
            CHROMIUM,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--no-first-run",
            "--no-default-browser-check",
            # A viewport tall enough that the whole demo page is on screen; real mouse events
            # land at viewport coordinates, so a short window would make clicks miss.
            "--window-size=1280,1600",
            f"--user-data-dir={profile}",
            f"--remote-debugging-port={port}",
            IDLE,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    cdp: Cdp | None = None
    try:
        _wait_for_devtools(port)
        cdp = Cdp(_page_target(port)["webSocketDebuggerUrl"])
        for domain in ("Page", "Runtime", "Log", "Network"):
            cdp.call(f"{domain}.enable")
        cdp.call("Page.addScriptToEvaluateOnNewDocument", source=ERROR_HOOK)
        cdp.call("Page.navigate", url=base + path)

        deadline = time.time() + timeout
        while time.time() < deadline:
            cdp.drain()
            if cdp.eval("document.readyState") == "complete" and cdp.eval(f"!!({boot})"):
                break
            time.sleep(0.2)
        else:
            raise TimeoutError(f"the shell never booted ({boot} stayed falsy)")
        time.sleep(settle)
        cdp.drain()
        yield cdp, base
    finally:
        if cdp:
            cdp.close()
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=10)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            proc.kill()
        srv.shutdown()
        srv.server_close()


def external_requests(cdp: Cdp, base: str) -> tuple[int, list[str]]:
    """(total requests, the ones that left this origin).

    The shell's channel handshake is the same origin wearing the ws scheme, so it is compared
    as one (the design's "no network beyond this origin" is about origins, not schemes).
    """
    urls = [p["request"]["url"] for p in cdp.of("Network.requestWillBeSent")]
    foreign = [
        u
        for u in urls
        if not _same_origin(u, base) and not u.startswith(("data:", "blob:", "about:"))
    ]
    return len(urls), foreign


def _same_origin(url: str, base: str) -> bool:
    normalized = url.replace("wss://", "https://").replace("ws://", "http://")
    return normalized.startswith(base)


def console_errors(cdp: Cdp) -> list[str]:
    out: list[str] = []
    for params in cdp.of("Runtime.exceptionThrown"):
        out.append(str(params.get("exceptionDetails", {}).get("text")))
    for params in cdp.of("Log.entryAdded"):
        if params.get("entry", {}).get("level") == "error":
            out.append(str(params["entry"].get("text")))
    out += [str(e) for e in (cdp.eval("window.__errs || []") or [])]
    return out


def report(checks: list[tuple[str, bool, str]], *, gate: str) -> int:
    ok = True
    for i, (name, passed, evidence) in enumerate(checks, 1):
        ok &= passed
        print(f"[{i}/{len(checks)}] {'PASS' if passed else 'FAIL'}  {name:<38} {evidence}")
    print(f"\n{gate} {'PASSED' if ok else 'FAILED'}")
    return 0 if ok else 1