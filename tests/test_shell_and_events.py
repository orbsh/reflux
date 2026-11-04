"""The shell, the `routes` slot, and the host's own events — offline, no browser, no socket.

Three things live here because they are the same subject: what a page turn becomes when the app
supplies a frame around its pages, what the address bar hands the backend (`path` + `query`), and
which names the host raises rather than the wire — `connect`, `location`, `disconnect`.

An app with no shell is the single-page shape and is asserted in `test_app.py` (a page replaces the
layout root); nothing here changes that.
"""

from __future__ import annotations

import unittest

from reflux import HOST_EVENTS, ROUTES_SLOT, wire
from reflux.app import App, Device, into_routes, location_of, query_of
from reflux.ingest import Refused, check_uplink
from reflux.protocol import HOST_EVENTS as PROTOCOL_HOST_EVENTS
from reflux.routes import Routes
from reflux.sdk import builders as b

from tests.fakes import FakeDevice


def page_for(ctx, match):
    """A page that draws which path it is — enough to tell which one landed in the slot."""
    ctx.page(b.text(f"page:{match.path}"))


def shell(ctx) -> object:
    """A frame with one nav line and the routes reader — the shape the slot is written into."""
    return b.case(b.text("shell"), b.placeholder(source=ROUTES_SLOT, id="routes"), id="shell")


def app_with_shell(*paths: str, page=None) -> App:
    table = Routes()
    for path in paths:
        table.add(path, page or page_for)
    return App(routes=table, shell=shell)


def ops(device: FakeDevice, index: int = -1) -> list[dict]:
    return device.frames[index]


class TestLocation(unittest.TestCase):
    def test_a_query_string_becomes_repeated_values(self):
        self.assertEqual(
            query_of("?from=paste&tag=a&tag=b&empty="),
            {"from": ["paste"], "tag": ["a", "b"], "empty": [""]},
        )

    def test_the_leading_question_mark_is_optional(self):
        self.assertEqual(query_of("q=1"), {"q": ["1"]})

    def test_nothing_to_read_is_an_empty_mapping(self):
        for raw in (None, "", {}, 3):
            with self.subTest(raw=raw):
                self.assertEqual(query_of(raw), {})

    def test_a_frame_carries_both_halves_and_both_are_total(self):
        self.assertEqual(location_of({"data": {"path": "/a", "query": "?q=1"}}), ("/a", {"q": ["1"]}))
        self.assertEqual(location_of({"data": {"path": "/a"}}), ("/a", {}))
        self.assertEqual(location_of({"data": {}}), ("/", {}))
        self.assertEqual(location_of({}), ("/", {}))
        self.assertEqual(location_of({"data": {"path": "", "query": "?q=1"}}), ("/", {"q": ["1"]}))


class TestShell(unittest.TestCase):
    def test_the_first_frame_is_the_shell_and_the_page_in_its_slot(self):
        app = app_with_shell("/")
        device = FakeDevice()
        app.dests.dispatch(device, {"dest": "reflux:hello", "data": {"path": "/"}})
        first = ops(device)
        self.assertEqual([op["action"] for op in first], ["create", "set"])
        self.assertEqual(first[0]["data"]["id"], "shell")
        self.assertEqual(first[1]["slot"], ROUTES_SLOT)
        self.assertEqual(first[1]["data"]["children"][2]["bind"]["value"]["default"], "page:/")

    def test_a_page_turn_after_that_writes_the_slot_and_nothing_else(self):
        app = app_with_shell("/", "/about")
        device = FakeDevice()
        app.dests.dispatch(device, {"dest": "reflux:hello", "data": {"path": "/"}})
        app.dests.dispatch(device, {"dest": "reflux:nav", "data": {"path": "/about"}})
        second = ops(device)
        self.assertEqual([op["action"] for op in second], ["set"])
        self.assertEqual(second[0]["slot"], ROUTES_SLOT)
        self.assertEqual(second[0]["data"]["children"][2]["bind"]["value"]["default"], "page:/about")

    def test_a_missing_path_lands_as_the_builtin_404_inside_the_shell(self):
        app = app_with_shell("/")
        device = FakeDevice()
        app.dests.dispatch(device, {"dest": "reflux:hello", "data": {"path": "/nope"}})
        first = ops(device)
        self.assertEqual([op["action"] for op in first], ["create", "set"])
        self.assertIn("404", str(first[1]["data"]))
        self.assertEqual(first[1]["slot"], ROUTES_SLOT)

    def test_a_page_draws_and_a_seed_is_a_send_of_its_own(self):
        def seeding(ctx, match):
            ctx.emit(wire.set("status", b.text("就绪")))  # a send, not part of the page
            ctx.page(b.text("page"))  # the page itself

        app = app_with_shell("/", page=seeding)
        device = FakeDevice()
        app.dests.dispatch(device, {"dest": "reflux:hello", "data": {"path": "/"}})
        seed, first = device.frames[0], device.frames[1]
        self.assertEqual([op["action"] for op in seed], ["set"])  # what the handler said
        self.assertEqual(seed[0]["slot"], "status")
        self.assertEqual([op["action"] for op in first], ["create", "set"])  # what the app drew
        self.assertEqual(first[1]["slot"], ROUTES_SLOT)

    def test_a_page_that_produces_no_structure_is_a_loud_producer_defect(self):
        with self.assertRaises(ValueError):
            into_routes([wire.set("status", b.text("就绪"))])

    def test_without_a_shell_the_page_still_replaces_the_root(self):
        table = Routes()
        table.add("/", page_for)
        app = App(routes=table)
        device = FakeDevice()
        app.dests.dispatch(device, {"dest": "reflux:hello", "data": {"path": "/"}})
        self.assertEqual([op["action"] for op in ops(device)], ["create"])
        app.dests.dispatch(device, {"dest": "reflux:nav", "data": {"path": "/"}})
        self.assertEqual([op["action"] for op in ops(device)], ["create"])  # a whole page, every turn

    def test_a_resync_re_creates_the_shell_the_stale_client_may_have_missed(self):
        app = app_with_shell("/")
        device = FakeDevice(app=app)
        app.dests.dispatch(device, {"dest": "reflux:hello", "data": {"path": "/"}})
        app.dests.dispatch(device, {"dest": "reflux:nav", "data": {"path": "/"}})
        self.assertEqual([op["action"] for op in ops(device)], ["set"])
        # What `flush_device` does when frames were shed: forget the shell, draw again.
        device.stale = True
        device.shell_drawn = False
        device.draw()
        self.assertEqual([op["action"] for op in ops(device)], ["create", "set"])


class TestHostEvents(unittest.TestCase):
    def setUp(self):
        self.app = App()
        self.device = FakeDevice()
        self.heard: list[tuple[str, str]] = []
        for name in HOST_EVENTS:
            self.app.dests.register(name, self.recorder(name))

    def recorder(self, name: str):
        def record(ctx, frame):
            self.heard.append((name, ctx.path))

        return record

    def test_connect_is_raised_once_per_device_on_the_first_hello(self):
        self.app.dests.dispatch(self.device, {"dest": "reflux:hello", "data": {"path": "/a"}})
        self.app.dests.dispatch(self.device, {"dest": "reflux:hello", "data": {"path": "/b"}})
        self.assertEqual(self.heard, [("connect", "/a")])  # the second hello only re-draws
        self.assertEqual(self.device.path, "/b")

    def test_a_nav_raises_location(self):
        self.app.dests.dispatch(self.device, {"dest": "reflux:hello", "data": {"path": "/"}})
        self.heard.clear()
        self.app.dests.dispatch(self.device, {"dest": "reflux:nav", "data": {"path": "/b"}})
        self.assertEqual(self.heard, [("location", "/b")])

    def test_connect_is_raised_after_the_first_frame_is_queued(self):
        app, device = App(), FakeDevice()
        def single(ctx, path):
            ctx.page(b.text("page"))

        app.page = single  # something to draw, so there is a frame
        seen: list[int] = []

        def record(ctx, frame):
            seen.append(len(ctx.device.frames))  # frames on the wire when the handler runs

        app.dests.register("connect", record)
        app.dests.dispatch(device, {"dest": "reflux:hello", "data": {"path": "/"}})
        self.assertEqual(seen, [1])  # the page is already out, so a handler's frames land on top

    def test_disconnect_fires_once_and_only_for_a_device_in_the_table(self):
        channel = object()
        device = Device("test0002", channel, lambda *a: None, {})
        self.app.devices[channel] = device
        self.assertTrue(self.app._gone(device, "closed"))
        self.assertFalse(self.app._gone(device, "dead"))  # the second caller is not its own
        self.assertEqual(self.heard, [("disconnect", "/")])

    def test_nobody_listening_is_not_a_refusal(self):
        app = App()
        device = FakeDevice()
        self.assertFalse(app.dests.announce("connect", device, {"dest": "connect", "data": {}}))
        self.assertEqual(app.dests.refused, 0)


class TestTheWireRefusesHostEvents(unittest.TestCase):
    def test_a_client_cannot_address_connect_location_or_disconnect(self):
        for name in PROTOCOL_HOST_EVENTS:
            with self.subTest(name=name):
                with self.assertRaises(Refused) as caught:
                    check_uplink({"dest": name, "data": {}})
                self.assertIn("host event", str(caught.exception))

    def test_an_ordinary_name_still_passes(self):
        check_uplink({"dest": "chat.send", "data": {}})  # raises nothing


if __name__ == "__main__":
    unittest.main()