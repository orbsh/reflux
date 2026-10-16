"""The WebSocket channel: one per session, ops down and events up, JSON text frames.

stdlib only, like everything else on the producer side. The handshake is the HTTP upgrade the
browser asks for on ``GET /ws``; after that it is frames, and the codec is deliberately the
smallest one that is still correct: text frames, fragmentation reassembled, ping answered,
close answered. A binary frame closes the connection — the protocol is JSON text, and a second
encoding would mean a second schema to keep in step.

    from reflux.channel import ChannelClosed, upgrade

    channel = upgrade(handler)     # inside an http.server handler's do_GET
    for message in channel: ...    # text in
    channel.send(frame_text)       # text out
"""

from __future__ import annotations

import base64
import hashlib
import struct
from typing import IO, Iterator

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
WS_PATH = "/ws"

TEXT, BINARY, CLOSE, PING, PONG, CONTINUATION = 0x1, 0x2, 0x8, 0x9, 0xA, 0x0


class ChannelClosed(Exception):
    """The peer went away, or the frame was not something this protocol can carry."""


def accept_key(client_key: str) -> str:
    """The handshake's answer: sha1(key + GUID), base64 (RFC 6455 §4.2.2)."""
    digest = hashlib.sha1(f"{client_key}{GUID}".encode()).digest()
    return base64.b64encode(digest).decode()


def is_upgrade(headers) -> bool:
    """Whether these request headers are asking for a WebSocket upgrade."""
    return (
        headers.get("Upgrade", "").lower() == "websocket"
        and "upgrade" in headers.get("Connection", "").lower()
    )


class Channel:
    """One upgraded connection. Text in, text out; everything else is protocol plumbing."""

    def __init__(self, rfile: IO[bytes], wfile: IO[bytes]) -> None:
        self.rfile = rfile
        self.wfile = wfile
        self.closed = False

    # --- reading -------------------------------------------------------------------------

    def _take(self, count: int) -> bytes:
        data = self.rfile.read(count)
        if data is None or len(data) < count:
            raise ChannelClosed("the peer closed mid-frame")
        return data

    def recv(self) -> str | None:
        """The next text message, or None when the peer closed cleanly."""
        opcode = None
        parts: list[bytes] = []
        while True:
            first, second = self._take(2)
            final = bool(first & 0x80)
            kind = first & 0x0F
            masked = bool(second & 0x80)
            length = second & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._take(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._take(8))[0]
            mask = self._take(4) if masked else b""
            payload = self._take(length) if length else b""
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))

            if kind == CLOSE:
                self._send(CLOSE, payload[:125])
                self.closed = True
                return None
            if kind == PING:
                self._send(PONG, payload)
                continue
            if kind == PONG:
                continue
            if kind == BINARY:
                raise ChannelClosed("binary frame: this protocol carries JSON text")
            if kind == TEXT:
                opcode = TEXT
                parts.append(payload)
            elif kind == CONTINUATION and opcode == TEXT:
                parts.append(payload)
            else:
                raise ChannelClosed(f"unexpected frame opcode {kind:#x}")
            if final:
                return b"".join(parts).decode("utf-8")

    # --- writing -------------------------------------------------------------------------

    def _send(self, opcode: int, payload: bytes) -> None:
        head = bytearray([0x80 | opcode])
        size = len(payload)
        if size < 126:
            head.append(size)
        elif size < 65536:
            head.append(126)
            head += struct.pack(">H", size)
        else:
            head.append(127)
            head += struct.pack(">Q", size)
        self.wfile.write(bytes(head) + payload)
        self.wfile.flush()

    def send(self, text: str) -> None:
        self._send(TEXT, text.encode("utf-8"))

    def close(self, code: int = 1000) -> None:
        if self.closed:
            return
        self._send(CLOSE, struct.pack(">H", code))
        self.closed = True

    def __iter__(self) -> Iterator[str]:
        while True:
            message = self.recv()
            if message is None:
                return
            yield message


def upgrade(handler) -> Channel:
    """Answer the upgrade on an ``http.server`` handler and hand back the channel.

    The handler's connection is now the channel's; the caller owns the read loop and must
    not let the HTTP machinery write a response for this request.
    """
    key = handler.headers.get("Sec-WebSocket-Key")
    if not key:
        raise ValueError("no Sec-WebSocket-Key: not a WebSocket request")
    handler.send_response_only(101, "Switching Protocols")
    handler.send_header("Upgrade", "websocket")
    handler.send_header("Connection", "Upgrade")
    handler.send_header("Sec-WebSocket-Accept", accept_key(key))
    handler.end_headers()
    handler.close_connection = True
    return Channel(handler.rfile, handler.wfile)