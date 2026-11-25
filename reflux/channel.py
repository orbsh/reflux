"""The channel: one per device, ops down and uplinks up, JSON text frames.

One class, and it is a wrapper rather than a codec. `WsChannel` is what the aiohttp server hands to
`App.handle`: a `WebSocketResponse` seen as a channel — framing, masking, fragmentation, ping/pong and
the close handshake are aiohttp's, which is why this file is short. The hand-written codec that
predates it (with `accept_key` / `is_upgrade` / `upgrade`, and the byte-level tests that exercised
it) is gone with the transport that needed it (ADR 0002).

Two things this layer owns because it is the layer that knows them:

- ``last_seen`` — every byte read from the peer counts as activity, and the watchdog judges a device
  by it, so a peer that vanished without a FIN is caught.
- ``closed`` — the flag every other method checks, because a write to a socket that already closed is
  the one failure that has no useful answer.

A channel is what `App` and `Device` ask five things of: `recv`, `send`, `ping`, `close`, `abort`.
"""

from __future__ import annotations

import time
from typing import Any

from aiohttp import WSMsgType

WS_PATH = "/ws"

# Application close codes (RFC 6455 §7.4.2 reserves 4000-4999 for these).
JUDGED_DEAD = 4001
EVICTED = 4002


class ChannelClosed(Exception):
    """The peer went away, or the write could not be carried — the caller treats it as a lost client."""


class WsChannel:
    """A `WebSocketResponse` seen as a channel — the five things `App` and `Device` ask of one.

    Reading is a read loop: text frames in, and `None` (as `StopAsyncIteration`) once the peer is
    gone. Ping/pong and fragmentation never reach this layer: aiohttp answers control frames and
    reassembles messages, which is the whole reason this class is a wrapper.
    """

    def __init__(self, ws: Any) -> None:
        self.ws = ws
        self.closed = False
        self.last_seen = time.monotonic()

    async def recv(self) -> str | None:
        message = await self.ws.receive()
        if message.type is WSMsgType.TEXT:
            self.last_seen = time.monotonic()
            return message.data
        if message.type is WSMsgType.BINARY:
            # The wire here is JSON text; a binary frame is still bytes we can read, and refusing it
            # would only turn a producer's mistake into a silent hang.
            self.last_seen = time.monotonic()
            return message.data.decode("utf-8", "replace")
        if message.type in (WSMsgType.PING, WSMsgType.PONG):
            self.last_seen = time.monotonic()
            return ""
        self.closed = True
        return None

    def __aiter__(self) -> "WsChannel":
        return self

    async def __anext__(self) -> str:
        message = await self.recv()
        if message is None:
            raise StopAsyncIteration
        return message

    async def send(self, text: str) -> None:
        try:
            await self.ws.send_str(text)
        except (ConnectionError, RuntimeError) as exc:
            # aiohttp says this several ways depending on where the socket died (a reset, a closed
            # transport, a response already written). The framework only ever needs one answer.
            self.closed = True
            raise ChannelClosed(str(exc)) from exc

    async def ping(self) -> None:
        if not self.closed:
            await self.ws.ping()

    async def close(self, code: int = 1000) -> None:
        self.closed = True
        await self.ws.close(code=code)

    def abort(self) -> None:
        """Drop the transport without a close handshake — the peer is not going to read it."""
        self.closed = True
        writer = getattr(self.ws, "_writer", None)
        if writer is not None:
            writer.transport.abort()