"""A minimal WebSocket client, so the demo can be a client instead of a browser.

The producer side of this repo only ever *accepts* upgrades (`reflux.channel`), and the CDP client in
`tools/cdp.py` speaks that framing to a DevTools port. This is the missing half: masked text frames
out, text frames in, stdlib only.

    with Socket(port) as ws:
        ws.send({"dest": "reflux:hello", "data": {"path": "/"}})
        print(ws.recv())

`recv` takes a deadline (`None` waits forever). Closing is our own: the server answers a close frame
and drops the session, which is what the walkthrough wants at the end of a run.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import struct
import time

__all__ = ["Socket"]

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
TEXT, CLOSE, PING, PONG = 0x1, 0x8, 0x9, 0xA


class Socket:
    """One connection to a reflux app's `/ws`."""

    def __init__(self, port: int, host: str = "127.0.0.1", path: str = "/ws", timeout: float = 10.0) -> None:
        self.sock = socket.create_connection((host, port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode())
        head = b""
        while b"\r\n\r\n" not in head:
            piece = self.sock.recv(4096)
            if not piece:
                raise ConnectionError("the server closed during the handshake")
            head += piece
        status = head.split(b"\r\n", 1)[0]
        if b"101" not in status:
            raise ConnectionError(f"not an upgrade: {status.decode(errors='replace')}")
        self._buf = head.split(b"\r\n\r\n", 1)[1]  # frames may already follow the headers

    # --- framing ---------------------------------------------------------------------------

    def _take(self, count: int, deadline: float | None) -> bytes:
        while len(self._buf) < count:
            if deadline is not None:
                left = deadline - time.monotonic()
                if left <= 0:
                    raise TimeoutError("no frame before the deadline")
                self.sock.settimeout(left)
            piece = self.sock.recv(65536)
            if not piece:
                raise ConnectionError("the peer closed")
            self._buf += piece
        data, self._buf = self._buf[:count], self._buf[count:]
        return data

    def _frame(self, opcode: int, payload: bytes) -> bytes:
        """A client frame: always masked (RFC 6455 §5.3 — a server must refuse an unmasked one)."""
        head = bytearray([0x80 | opcode])
        size = len(payload)
        if size < 126:
            head.append(0x80 | size)
        elif size < 65536:
            head.append(0x80 | 126)
            head += struct.pack(">H", size)
        else:
            head.append(0x80 | 127)
            head += struct.pack(">Q", size)
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
        return bytes(head) + mask + masked

    # --- the two verbs ---------------------------------------------------------------------

    def send(self, frame: dict) -> None:
        """One text frame; `ensure_ascii=False` so CJK stays readable on the wire."""
        self.sock.sendall(self._frame(TEXT, json.dumps(frame, ensure_ascii=False).encode("utf-8")))

    def recv(self, timeout: float | None = 10.0) -> dict | None:
        """The next JSON frame, or None when the server closed. `timeout=None` waits forever."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            first, second = self._take(2, deadline)
            final, kind = bool(first & 0x80), first & 0x0F
            length = second & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._take(2, deadline))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._take(8, deadline))[0]
            mask = self._take(4, deadline) if second & 0x80 else b""
            payload = self._take(length, deadline) if length else b""
            if mask:
                payload = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
            if kind == CLOSE:
                return None
            if kind == PING:
                self.sock.sendall(self._frame(PONG, payload))
                continue
            if kind == PONG:
                continue
            if kind != TEXT or not final:
                continue  # this protocol carries unfragmented JSON text, nothing else
            return json.loads(payload.decode("utf-8"))

    def close(self) -> None:
        try:
            self.sock.sendall(self._frame(CLOSE, struct.pack(">H", 1000)))
        except OSError:
            pass
        finally:
            self.sock.close()

    def __enter__(self) -> "Socket":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()