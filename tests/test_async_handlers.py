"""Handlers may await (ADR 0002 P2).

The three shapes that matter: `async def` is awaited on the loop, a plain function runs on a worker
thread (so a blocking call stalls only that thread), and a delivery has a budget — a handler that
never returns is cancelled and the device survives. One device's two deliveries are still ordered.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
import unittest

from reflux.app import App
from reflux.auth import Auth
from reflux.sdk import h
from tests.fakes import FakeDevice, run_sync


class Scripted:
    """One connection with a script, close enough to a channel for `App.handle`."""

    def __init__(self, *frames: dict) -> None:
        self.script = [json.dumps(frame) for frame in frames]
        self.last_seen = time.monotonic()
        self.frames: list[list[dict]] = []

    def __aiter__(self) -> "Scripted":
        self._script = iter(self.script)
        return self

    async def __anext__(self) -> str:
        try:
            return next(self._script)
        except StopIteration:
            raise StopAsyncIteration from None

    async def send(self, text: str) -> None:
        self.frames.append(json.loads(text))

    async def ping(self, payload: bytes = b"") -> None:
        pass

    async def close(self, code: int = 1000) -> None:
        pass

    def abort(self) -> None:
        pass


def texts(node) -> list[str]:
    """Every text a node carries — enough to see which page came back."""
    if isinstance(node, list):
        return [found for item in node for found in texts(item)]
    if not isinstance(node, dict):
        return []
    here = []
    if node.get("type") == "text":
        here.append(str(node.get("source", {}).get("default", "")))
    return here + texts(node.get("children")) + texts(node.get("data"))


class TestAwaitableHandlers(unittest.TestCase):
    def test_an_async_handler_is_awaited(self) -> None:
        app = App()
        seen: list[dict] = []

        @app.on("note")
        async def handler(ctx, frame: dict) -> None:
            await asyncio.sleep(0)
            seen.append(frame["data"])

        run_sync(app.dests.dispatch(FakeDevice(), {"dest": "note", "data": {"n": 1}}))
        self.assertEqual(seen, [{"n": 1}])

    def test_a_plain_handler_runs_off_the_loop(self) -> None:
        app = App()
        where: list[str] = []

        @app.on("note")
        def handler(ctx, frame: dict) -> None:
            where.append(threading.current_thread().name)

        run_sync(app.dests.dispatch(FakeDevice(), {"dest": "note", "data": {}}))
        self.assertEqual(len(where), 1)
        self.assertNotEqual(where[0], threading.main_thread().name)

    def test_an_async_closure_landing_is_awaited(self) -> None:
        app = App()
        seen: list = []

        async def land(value):
            await asyncio.sleep(0)
            seen.append(value)

        device = FakeDevice()
        device.landings["add"] = (land, False)
        run_sync(app.dests.dispatch(device, {"dest": "add", "data": {"row": 1}}))
        self.assertEqual(seen, [{"row": 1}])

    def test_an_async_page_is_awaited(self) -> None:
        app = App()

        @app.page
        async def page(ctx, path: str):
            await asyncio.sleep(0)
            return h.text(f"page:{path}")

        device = FakeDevice(path="/here", app=app)
        run_sync(app._draw(device))
        self.assertIn("page:/here", texts([frame for sent in device.frames for frame in sent]))

    def test_an_async_shell_is_awaited(self) -> None:
        async def shell(ctx):
            await asyncio.sleep(0)
            return h.text("shell")

        app = App(shell=shell)

        @app.page
        def page(ctx, path: str):
            return h.text("page")

        device = FakeDevice(app=app)
        run_sync(app._draw(device))
        self.assertIn("shell", texts([frame for sent in device.frames for frame in sent]))

    def test_an_async_verifier_is_awaited(self) -> None:
        async def verify(ctx, credentials, mode):
            await asyncio.sleep(0)
            return "user-ada" if credentials.get("password") == "pw" else None

        app = App(auth=Auth(verify=verify))
        channel = Scripted(
            {"dest": "reflux:login", "data": {"username": "ada", "password": "pw"}}
        )
        run_sync(app.handle(channel))
        self.assertEqual(len(app.tokens), 1)


class TestTheBudget(unittest.TestCase):
    def test_a_handler_past_its_budget_is_cancelled_and_the_device_survives(self) -> None:
        app = App(handler_timeout=0.05)
        stopped = threading.Event()

        @app.on("slow")
        async def slow(ctx, frame: dict) -> None:
            try:
                await asyncio.sleep(5)
            finally:
                stopped.set()

        channel = Scripted({"dest": "slow", "data": {}})
        started = time.monotonic()
        run_sync(app.handle(channel))
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 2.0, "the budget ends the delivery, not the test")
        self.assertTrue(stopped.is_set(), "the coroutine was cancelled, not abandoned")
        self.assertEqual(app.stats["refused"], 1)
        self.assertTrue(any("ran past" in line for line in app.dests.log), app.dests.log)
        # The device outlived its handler's defect: it was removed as a closed connection only.
        self.assertEqual(app.stats["reclaimed"], 1)


class TestOrdering(unittest.TestCase):
    def test_two_deliveries_on_one_device_do_not_interleave(self) -> None:
        app = App()
        order: list[str] = []

        @app.on("step")
        async def step(ctx, frame: dict) -> None:
            name = frame["data"]["n"]
            order.append(f"{name}:in")
            await asyncio.sleep(0.01)
            order.append(f"{name}:out")

        channel = Scripted({"dest": "step", "data": {"n": 1}}, {"dest": "step", "data": {"n": 2}})
        run_sync(app.handle(channel))
        self.assertEqual(order, ["1:in", "1:out", "2:in", "2:out"])

    def test_one_device_waiting_does_not_hold_another(self) -> None:
        app = App()
        done: dict[str, float] = {}
        gate = threading.Event()

        @app.on("slow")
        def slow(ctx, frame: dict) -> None:
            gate.wait(2.0)
            done["slow"] = time.monotonic()

        @app.on("fast")
        def fast(ctx, frame: dict) -> None:
            done["fast"] = time.monotonic()

        slow_side = threading.Thread(
            target=run_sync, args=(app.handle(Scripted({"dest": "slow", "data": {}})),), daemon=True
        )
        slow_side.start()
        time.sleep(0.05)
        run_sync(app.handle(Scripted({"dest": "fast", "data": {}})))
        gate.set()
        slow_side.join(timeout=5)
        self.assertIn("fast", done)
        self.assertIn("slow", done)
        self.assertLess(done["fast"], done["slow"], "the fast delivery did not wait for the slow one")


if __name__ == "__main__":
    unittest.main()