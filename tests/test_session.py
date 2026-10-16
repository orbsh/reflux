"""Sessions: one per connection, reclaimed when it closes or when it stops answering.

No clock in these assertions — `App.watch()` is *one pass* and the tests call it directly, so the
judgement is deterministic. The thread that ticks the pass is tested once, with tiny intervals.

The fake below is exactly what the session table reads of a channel: activity (`last_seen`), a
ping, a close, an abort. A connection that never hangs is a connection whose reader returns at
once — that is what the empty `messages` list gives.
"""

from __future__ import annotations

import threading
import time
import unittest

from reflux.app import App
from reflux.channel import JUDGED_DEAD, Channel


class FakeChannel(Channel):
    """A channel as the session table sees it, with a record of what was done to it.

    Subclassed rather than duck-typed so the double stays assignable to what `handle()` takes; it
    skips the base's reader/writer and keeps only what the table touches.
    """

    def __init__(self, *, quiet_for: float = 0.0, hold: bool = False) -> None:
        self.last_seen = time.monotonic() - quiet_for
        self.hold = threading.Event()
        if not hold:
            self.hold.set()
        self.pings = 0
        self.closed_with: int | None = None
        self.aborted = False
        self.frames: list[str] = []

    def __iter__(self):
        # `hold` keeps the connection in the table for the duration of a test; released, the
        # reader ends at once and the session is reclaimed, which is the clean-close path.
        self.hold.wait()
        yield from ()

    def send(self, text: str) -> None:
        self.frames.append(text)

    def ping(self, payload: bytes = b"") -> None:
        self.pings += 1

    def close(self, code: int = 1000) -> None:
        self.closed_with = code

    def abort(self) -> None:
        self.aborted = True


def run_connections(app: App, *channels: FakeChannel) -> list[threading.Thread]:
    """Start one `handle()` thread per channel and wait until they are all registered."""
    threads = [
        threading.Thread(target=app.handle, args=(channel,), daemon=True) for channel in channels
    ]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + 2.0
    while len(app.sessions) < len(channels) and time.monotonic() < deadline:
        time.sleep(0.005)
    return threads


class TestSessionLifecycle(unittest.TestCase):
    def setUp(self) -> None:
        self.app = App(heartbeat=0.01, dead_after=0.05)

    def tearDown(self) -> None:
        self.app.stop()
        for channel in list(self.app.sessions):
            channel.hold.set()

    def test_closing_reclaims_the_session(self) -> None:
        channel = FakeChannel()
        self.app.handle(channel)  # returns as soon as the connection ends
        self.assertEqual(len(self.app.sessions), 0)
        self.assertEqual(self.app.stats, {"issued": 1, "reclaimed": 1, "dead": 0})

    def test_a_live_session_is_pinged_and_kept(self) -> None:
        channel = FakeChannel(hold=True)
        run_connections(self.app, channel)
        self.app.watch()
        self.assertEqual(channel.pings, 1)
        self.assertIn(channel, self.app.sessions)
        self.assertEqual(self.app.stats["dead"], 0)
        self.assertIsNone(channel.closed_with)

    def test_a_session_gone_quiet_is_judged_dead_and_reclaimed(self) -> None:
        channel = FakeChannel(quiet_for=1.0, hold=True)  # long past dead_after
        run_connections(self.app, channel)
        self.app.watch()
        self.assertNotIn(channel, self.app.sessions)
        self.assertEqual(self.app.stats["dead"], 1)
        self.assertEqual(channel.closed_with, JUDGED_DEAD)
        self.assertTrue(channel.aborted, "a dead peer's socket must be shut, or its thread hangs")

    def test_only_the_quiet_one_is_reclaimed(self) -> None:
        live, quiet = FakeChannel(hold=True), FakeChannel(quiet_for=1.0, hold=True)
        threads = run_connections(self.app, live, quiet)
        self.app.watch()
        self.assertIn(live, self.app.sessions)
        self.assertEqual(live.pings, 1)
        self.assertNotIn(quiet, self.app.sessions)
        # Judged dead is not reclaimed: the dead one leaves the table by the deadline, and its
        # reader — still blocked in the fake's hold — must not count it a second time on the way
        # out. The live one is untouched by the pass.
        self.assertEqual(self.app.stats, {"issued": 2, "reclaimed": 0, "dead": 1})
        for channel in (live, quiet):
            channel.hold.set()
        for thread in threads:
            thread.join(timeout=2)
        self.assertEqual(len(self.app.sessions), 0)
        self.assertEqual(self.app.stats, {"issued": 2, "reclaimed": 1, "dead": 1})

    def test_the_watchdog_thread_ticks_the_pass(self) -> None:
        channel = FakeChannel(quiet_for=1.0, hold=True)
        run_connections(self.app, channel)
        self.app.start_watchdog()
        deadline = time.monotonic() + 2.0
        while self.app.sessions and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(len(self.app.sessions), 0)
        self.assertGreaterEqual(self.app.stats["dead"], 1)


if __name__ == "__main__":
    unittest.main()