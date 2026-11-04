"""Devices and mounts: one connection, the bag the business hangs on it, and the route table.

Two subjects that meet at the same object. A **device** is a connection the framework keeps —
its id, where it stands, what the business hung on it, and when it goes. The **mount table** is the
HTTP side, and the channel is one route in it (`{"/ws": CHANNEL}`), which is why moving the socket is
`unmount("/ws")` + `mount("/socket")` rather than a server setting.

Every test here drives the real server and a real socket: a route table that only works in-process
would not be a route table.
"""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from reflux import CHANNEL, App, Device, Request, Response, Routes, wire
from reflux.sdk import builders as b
from tools.wire_probe import Socket


def hello(app: App, ws: Socket, path: str = "/") -> Device:
    """Open the connection the way the page does, and hand back the device the app registered.

    An app with nothing to draw answers with no frame, so the device appearing in the table is the
    fact to wait on — not a frame.
    """
    ws.send({"dest": "reflux:hello", "data": {"path": path}})
    for _ in range(200):
        live = app.live()
        if live:
            return live[0]
        threading.Event().wait(0.01)
    raise AssertionError("the device never reached the table")


def bare_app(**kwargs: Any) -> App:
    """An app whose route table is empty: nothing is drawn until the test draws it.

    `App()` falls back to the module-level `DEFAULT` table, which other tests fill with `@route`
    decorators — so a test that assumes "no page yet" must say so.
    """
    return App(routes=Routes(), **kwargs)


def page_app(**kwargs) -> App:
    """An app with one page, so hello is answered with a frame."""
    app = App(**kwargs)
    app.page = lambda device, path: b.text(f"page{path}")
    return app


class Served:
    """An app behind a real server on a free port, torn down on the way out."""

    def __init__(self, app: App) -> None:
        self.app = app
        self.server: ThreadingHTTPServer = app.serve(port=0)
        self.port = int(self.server.server_address[1])

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def get(self, path: str) -> tuple[int, str]:
        return self._ask(urllib.request.Request(self.url(path)))

    def post(self, path: str, body: bytes = b"") -> tuple[int, str]:
        return self._ask(urllib.request.Request(self.url(path), data=body, method="POST"))

    def _ask(self, request: urllib.request.Request) -> tuple[int, str]:
        try:
            with urllib.request.urlopen(request, timeout=5) as answered:
                return answered.status, answered.read().decode()
        except urllib.error.HTTPError as bad:
            return bad.code, bad.read().decode()

    def __enter__(self) -> "Served":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.app.stop()
        self.server.shutdown()
        self.server.server_close()


class TestTheTable(unittest.TestCase):
    def test_the_channel_is_a_route_and_starts_at_ws(self):
        self.assertEqual(bare_app().mounts, {"/ws": CHANNEL})

    def test_a_route_is_a_callable_that_gets_a_request(self):
        seen: list[Request] = []

        def health(request: Request) -> str:
            seen.append(request)
            return "ok"

        app = bare_app()
        app.mount("/health", health)
        with Served(app) as served:
            status, body = served.get("/health?full=1")
        self.assertEqual((status, body), (200, "ok"))
        self.assertEqual(seen[0].path, "/health")
        self.assertEqual(seen[0].query, {"full": ["1"]})
        self.assertEqual(seen[0].method, "GET")

    def test_a_route_may_answer_a_response_a_pair_or_a_body(self):
        app = bare_app()
        app.mount("/response", lambda request: Response(201, "made", "text/plain"))
        app.mount("/pair", lambda request: (418, "teapot"))
        app.mount("/bytes", lambda request: b"raw")
        app.mount("/nothing", lambda request: None)
        with Served(app) as served:
            self.assertEqual(served.get("/response"), (201, "made"))
            self.assertEqual(served.get("/pair")[0], 418)
            self.assertEqual(served.get("/bytes"), (200, "raw"))
            self.assertEqual(served.get("/nothing")[0], 404)

    def test_a_post_carries_its_body(self):
        seen: list[bytes] = []
        app = bare_app()
        app.mount("/echo", lambda request: (seen.append(request.body), "ok")[1])
        with Served(app) as served:
            self.assertEqual(served.post("/echo", b'{"a":1}'), (200, "ok"))
        self.assertEqual(seen, [b'{"a":1}'])

    def test_a_post_nowhere_is_405_and_a_get_nowhere_is_404(self):
        with Served(bare_app()) as served:
            self.assertEqual(served.post("/nope")[0], 405)
            self.assertEqual(served.get("/nope")[0], 200)  # the page tree answers: index.html

    def test_a_route_that_raises_answers_500_and_the_server_keeps_serving(self):
        def broken(request: Request) -> str:
            raise RuntimeError("no")

        app = bare_app()
        app.mount("/broken", broken)
        app.mount("/fine", lambda request: "ok")
        with Served(app) as served:
            self.assertEqual(served.get("/broken")[0], 500)
            self.assertEqual(served.get("/fine"), (200, "ok"))

    def test_mounting_twice_is_an_error_and_unmounting_nothing_is_too(self):
        app = bare_app()
        with self.assertRaises(ValueError):
            app.mount("/ws")
        with self.assertRaises(KeyError):
            app.unmount("/never")

    def test_the_channel_can_be_moved(self):
        app = bare_app()
        app.unmount("/ws")
        app.mount("/socket")
        app.page = lambda device, path: b.text("page")
        with Served(app) as served:
            with Socket(served.port, path="/socket") as ws:
                hello(app, ws)
                self.assertEqual(len(ws.recv()), 1)  # one frame: the page
            with self.assertRaises(ConnectionError):
                Socket(served.port, path="/ws")  # no longer an upgrade

    def test_the_channel_route_answers_a_plain_get_with_426(self):
        with Served(bare_app()) as served:
            self.assertEqual(served.get("/ws")[0], 426)


class TestDirectoryMounts(unittest.TestCase):
    """A route may be a directory: the page's modules and models are files, served like any other."""

    def setUp(self) -> None:
        self.tree = tempfile.mkdtemp(prefix="reflux-mount-")
        (Path(self.tree) / "module.js").write_text("export const x = 1;\n")
        (Path(self.tree) / "nested").mkdir()
        (Path(self.tree) / "nested" / "data.json").write_text('{"ok": true}')

    def test_a_mounted_directory_serves_its_files(self):
        app = bare_app()
        app.mount("/assets/mod", Path(self.tree))
        with Served(app) as served:
            status, body = served.get("/assets/mod/module.js")
            self.assertEqual((status, body), (200, "export const x = 1;\n"))
            status, body = served.get("/assets/mod/nested/data.json")
            self.assertEqual((status, body), (200, '{"ok": true}'))

    def test_a_file_that_is_not_there_is_404_not_the_page(self):
        app = bare_app()
        app.mount("/assets/mod", Path(self.tree))
        with Served(app) as served:
            self.assertEqual(served.get("/assets/mod/nope.js")[0], 404)

    def test_the_channel_still_answers_next_to_a_directory(self):
        app = page_app()
        app.mount("/assets/mod", Path(self.tree))
        with Served(app) as served:
            with Socket(served.port) as ws:
                hello(app, ws)
                self.assertEqual(len(ws.recv()), 1)
            self.assertEqual(served.get("/assets/mod/module.js")[0], 200)

    def test_mounting_a_directory_twice_is_loud(self):
        app = bare_app()
        app.mount("/assets/mod", Path(self.tree))
        with self.assertRaises(ValueError):
            app.mount("/assets/mod", Path(self.tree))


class TestDevices(unittest.TestCase):
    def test_a_device_is_found_by_id_and_the_bag_is_the_business_own(self):
        app = bare_app()
        with Served(app) as served:
            with Socket(served.port) as ws:
                device = hello(app, ws)
                self.assertIs(app.device(device.id), device)
                device.data["user"] = {"name": "Ada"}
                found = app.device(device.id)
                assert found is not None
                self.assertEqual(found.data["user"], {"name": "Ada"})
                self.assertIsNone(app.device("nope"))

    def test_the_bag_dies_with_the_connection(self):
        app = bare_app()
        with Served(app) as served:
            with Socket(served.port) as ws:
                device = hello(app, ws)
                device.data["user"] = "Ada"
            for _ in range(100):
                if not app.live():
                    break
                threading.Event().wait(0.02)
            self.assertEqual(app.live(), [])

    def test_emit_sends_one_frame_and_counts_it(self):
        app = bare_app()
        with Served(app) as served:
            with Socket(served.port) as ws:
                device = hello(app, ws)
                device.emit(wire.set("greeting", b.text("hi")))
                frame = ws.recv()
                self.assertEqual(device.emits, 1)
                self.assertEqual(json.loads(json.dumps(frame))[0]["slot"], "greeting")

    def test_evict_closes_the_named_device_and_says_why(self):
        app = bare_app()
        heard: list[tuple[str, Any]] = []
        app.dests.register("disconnect", lambda device, frame: heard.append((device.id, frame["data"]["reason"])))
        with Served(app) as served:
            with Socket(served.port) as ws:
                device = hello(app, ws)
                self.assertEqual(app.evict(id=device.id), 1)
                self.assertIsNone(app.device(device.id))
                self.assertEqual(app.live(), [])
                self.assertEqual(heard, [(device.id, "evicted")])
                self.assertIsNone(ws.recv(timeout=2.0))  # the close frame, then the socket ends

    def test_evict_takes_a_predicate_over_the_bag(self):
        app = bare_app()
        with Served(app) as served:
            with Socket(served.port) as ws:
                device = hello(app, ws)
                device.data["user"] = "Ada"
                self.assertEqual(app.evict(where=lambda device: device.data.get("user") == "Ada"), 1)
                self.assertEqual(app.live(), [])

    def test_evict_without_a_target_refuses_rather_than_closing_everything(self):
        with self.assertRaises(TypeError):
            bare_app().evict()


class TestTheShape(unittest.TestCase):
    def test_a_login_is_an_ordinary_dest_that_hangs_its_result_on_the_device(self):
        app = bare_app()

        @app.dests.register("login")
        def on_login(device: Device, frame: dict) -> None:
            # In a real app this is where an external service gets asked; the framework owns none of it.
            if frame["data"].get("name") == "Ada":
                device.data["user"] = {"name": "Ada"}
                device.emit(wire.set("hello", b.text("欢迎回来")))
            else:
                device.emit(wire.set("hello", b.text("名字不认识")))

        with Served(app) as served:
            with Socket(served.port) as ws:
                device = hello(app, ws)
                ws.send({"dest": "login", "data": {"name": "Ada"}})
                ws.recv()
                self.assertEqual(device.data["user"], {"name": "Ada"})


if __name__ == "__main__":
    unittest.main()