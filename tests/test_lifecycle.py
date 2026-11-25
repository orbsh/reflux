"""Lifecycle: what a deployment builds around serving (ADR 0002 §7).

Three facts are worth a test each: the hooks run on the loop *before* anything is accepted, the
shared client exists while the app serves and is gone after, and `start()`/`stop()` is a pair that
cannot be called out of order.
"""

from __future__ import annotations

import asyncio
import threading
import unittest

from reflux.app import App


class TestHooks(unittest.TestCase):
    def test_a_startup_hook_runs_on_the_loop_before_serving(self) -> None:
        app = App()
        seen: list[tuple[str, str]] = []

        @app.startup
        async def boot() -> None:
            seen.append(("boot", threading.current_thread().name))

        server = app.start(port=0)
        try:
            self.assertEqual([name for name, _ in seen], ["boot"])
            self.assertEqual(seen[0][1], "reflux-loop", "the hook ran on the server's own loop")
            self.assertEqual(app.loop, server.loop)
        finally:
            app.stop()

    def test_shutdown_hooks_run_last_first(self) -> None:
        app = App()
        seen: list[str] = []

        @app.shutdown
        def one() -> None:
            seen.append("one")

        @app.shutdown
        async def two() -> None:
            await asyncio.sleep(0)
            seen.append("two")

        app.start(port=0)
        app.stop()
        self.assertEqual(seen, ["two", "one"], "the last registered runs first")

    def test_a_failing_shutdown_hook_is_logged_and_the_rest_still_run(self) -> None:
        app = App()
        seen: list[str] = []

        @app.shutdown
        def fine() -> None:
            seen.append("fine")

        @app.shutdown
        def broken() -> None:
            raise RuntimeError("the deployment's own defect")

        app.start(port=0)
        app.stop()
        self.assertEqual(seen, ["fine"])
        self.assertTrue(any("shutdown hook raised" in line for line in app.dests.log), app.dests.log)


class TestTheSharedClient(unittest.TestCase):
    def test_the_app_has_a_session_while_it_serves_and_not_after(self) -> None:
        app = App()
        self.assertIsNone(app.http, "an app nobody is serving has no client")
        app.start(port=0)
        session = app.http
        self.assertIsNotNone(session, "a handler may await app.http.get(...)")
        self.assertFalse(session.closed)
        app.stop()
        self.assertIsNone(app.http)
        self.assertTrue(session.closed)

    def test_a_startup_hook_may_use_the_session(self) -> None:
        app = App()
        seen: list[bool] = []

        @app.startup
        async def boot() -> None:
            seen.append(app.http is not None and not app.http.closed)

        app.start(port=0)
        try:
            self.assertEqual(seen, [True])
        finally:
            app.stop()


class TestStartStop(unittest.TestCase):
    def test_starting_twice_is_an_error(self) -> None:
        app = App()
        app.start(port=0)
        try:
            with self.assertRaises(RuntimeError):
                app.start(port=0)
        finally:
            app.stop()

    def test_stopping_twice_is_safe(self) -> None:
        app = App()
        server = app.start(port=0)
        seen: list[str] = []

        @app.shutdown
        def once() -> None:
            seen.append("hook")

        app.stop()
        app.stop()
        self.assertEqual(seen, ["hook"], "the hooks ran once, not once per stop")
        self.assertTrue(server._stopped.is_set())

    def test_stop_leaves_no_loop_thread_behind(self) -> None:
        app = App()
        before = [t.name for t in threading.enumerate()]
        app.start(port=0)
        self.assertIn("reflux-loop", [t.name for t in threading.enumerate()])
        app.stop()
        leftover = [t for t in threading.enumerate() if t.name == "reflux-loop" and t.is_alive()]
        self.assertEqual(leftover, [], "the serving thread ended")
        self.assertGreaterEqual(len(before), 1)

    def test_stop_ends_a_server_this_app_started(self) -> None:
        app = App()
        server = app.start(port=0)
        self.assertFalse(server._stopped.is_set())
        app.stop()
        self.assertTrue(server._stopped.is_set())

    def test_an_app_can_serve_again_after_stopping(self) -> None:
        app = App()
        app.start(port=0)
        app.stop()
        server = app.start(port=0)
        try:
            self.assertFalse(server._stopped.is_set())
        finally:
            app.stop()


if __name__ == "__main__":
    unittest.main()