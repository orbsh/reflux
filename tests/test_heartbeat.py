"""The transport's own frame (ADR 0044): a probe is answered on the socket and counted as nothing.

The client's heartbeat asks in the wire's language, because a browser cannot send a WebSocket ping from
wasm. The server's half is one branch, and what matters is that it stays *outside* the app: no handler is
called, no refusal is counted, no log line is written — a probe that showed up in `/status` as a refused
event would send every operator chasing a client that is working perfectly.
"""

from __future__ import annotations

import json
import unittest

from reflux.app import App
from tests.fakes import run_sync
from reflux.protocol import PING_DEST, PONG_DEST

from tests.fakes import FakeDevice


class Socket:
    """The bit of `Channel` the answer uses: one text frame out."""

    def __init__(self) -> None:
        self.sent: list[str] = []

    def send(self, text: str) -> None:
        self.sent.append(text)


class ProbeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.app = App()
        self.device = FakeDevice()
        self.socket = Socket()
        self.device.channel = self.socket  # type: ignore[attr-defined]
        self.calls = self.app.dests.calls
        self.refused = self.app.dests.refused

    def probe(self) -> dict:
        return {"dest": PING_DEST, "id": None, "data": None}

    def test_a_probe_is_answered_on_the_socket(self) -> None:
        self.assertTrue(run_sync(self.app.dests.dispatch(self.device, self.probe())))
        self.assertEqual(len(self.socket.sent), 1)
        answer = json.loads(self.socket.sent[0])
        self.assertEqual(answer["dest"], PONG_DEST)

    def test_a_probe_is_not_an_event(self) -> None:
        run_sync(self.app.dests.dispatch(self.device, self.probe()))
        self.assertEqual(self.app.dests.calls, self.calls, "a handler was called for a probe")
        self.assertEqual(self.app.dests.refused, self.refused, "a probe was counted as a refusal")
        self.assertFalse(
            any(PING_DEST in line for line in self.app.dests.log),
            "a probe was logged as app traffic",
        )

    def test_a_device_without_a_socket_survives_the_probe(self) -> None:
        # The unit-test device has no channel; the branch must not raise on it.
        bare = FakeDevice()
        self.assertTrue(run_sync(self.app.dests.dispatch(bare, self.probe())))
        self.assertEqual(self.app.dests.refused, self.refused)


if __name__ == "__main__":
    unittest.main()