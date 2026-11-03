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
from reflux.app import App, Session, into_routes, location_of, query_of
from reflux.ingest import Refused, check_uplink
from reflux.protocol import HOST_EVENTS as PROTOCOL_HOST_EVENTS
from reflux.routes import Routes
from reflux.sdk import builders as b

from tests.fakes import FakeSession


def page_for(session, match):
    """A page that says which path it is — enough to tell which one landed in the slot."""
    return b.text(f"page:{match.path}")


def shell(session) -> object:
    """A frame with one nav line and the routes reader — the shape the slot is written into."""
    return b.case(b.text("shell"), b.placeholder(source=ROUTES_SLOT, id="routes"), id="shell")


def app_with_shell(*paths: str, page=None) -> App:
    table = Routes()
    for path in paths:
        table.add(path, page or page_for)
    return App(routes=table, shell=shell)


def ops(session: FakeSession, index: int = -1) -> list[dict]:
    return session.frames[index]


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
        session = FakeSession()
        app.dests.dispatch(session, {"dest": "reflux:hello", "data": {"path": "/"}})
        first = ops(session)
        self.assertEqual([op["action"] for op in first], ["create", "set"])
        self.assertEqual(first[0]["data"]["id"], "shell")
        self.assertEqual(first[1]["slot"], ROUTES_SLOT)
        self.assertEqual(first[1]["data"]["bind"]["value"]["default"], "page:/")

    def test_a_page_turn_after_that_writes_the_slot_and_nothing_else(self):
        app = app_with_shell("/", "/about")
        session = FakeSession()
        app.dests.dispatch(session, {"dest": "reflux:hello", "data": {"path": "/"}})
        app.dests.dispatch(session, {"dest": "reflux:nav", "data": {"path": "/about"}})
        second = ops(session)
        self.assertEqual([op["action"] for op in second], ["set"])
        self.assertEqual(second[0]["slot"], ROUTES_SLOT)
        self.assertEqual(second[0]["data"]["bind"]["value"]["default"], "page:/about")

    def test_a_missing_path_lands_as_the_builtin_404_inside_the_shell(self):
        app = app_with_shell("/")
        session = FakeSession()
        app.dests.dispatch(session, {"dest": "reflux:hello", "data": {"path": "/nope"}})
        first = ops(session)
        self.assertEqual([op["action"] for op in first], ["create", "set"])
        self.assertIn("404", str(first[1]["data"]))
        self.assertEqual(first[1]["slot"], ROUTES_SLOT)

    def test_slot_seeds_a_page_sends_ride_along_after_its_structure(self):
        def seeding(session, match):
            return [wire.create(b.text("page")), wire.set("status", b.text("就绪"))]

        app = app_with_shell("/", page=seeding)
        session = FakeSession()
        app.dests.dispatch(session, {"dest": "reflux:hello", "data": {"path": "/"}})
        first = ops(session)
        self.assertEqual([op["action"] for op in first], ["create", "set", "set"])
        self.assertEqual(first[1]["slot"], ROUTES_SLOT)  # the page, rewritten into the slot
        self.assertEqual(first[2]["slot"], "status")  # the seed, untouched and after it

    def test_a_page_that_produces_no_structure_is_a_loud_producer_defect(self):
        with self.assertRaises(ValueError):
            into_routes([wire.set("status", b.text("就绪"))])

    def test_without_a_shell_the_page_still_replaces_the_root(self):
        table = Routes()
        table.add("/", page_for)
        app = App(routes=table)
        session = FakeSession()
        app.dests.dispatch(session, {"dest": "reflux:hello", "data": {"path": "/"}})
        self.assertEqual([op["action"] for op in ops(session)], ["create"])
        app.dests.dispatch(session, {"dest": "reflux:nav", "data": {"path": "/"}})
        self.assertEqual([op["action"] for op in ops(session)], ["create"])  # a whole page, every turn

    def test_a_resync_re_creates_the_shell_the_stale_client_may_have_missed(self):
        app = app_with_shell("/")
        session = FakeSession()
        app.dests.dispatch(session, {"dest": "reflux:hello", "data": {"path": "/"}})
        app.dests.dispatch(session, {"dest": "reflux:nav", "data": {"path": "/"}})
        self.assertEqual([op["action"] for op in ops(session)], ["set"])
        # What `flush_session` does when frames were shed: forget the shell, draw again.
        session.stale = True
        session.shell_drawn = False
        app.draw_page(session)
        self.assertEqual([op["action"] for op in ops(session)], ["create", "set"])


class TestHostEvents(unittest.TestCase):
    def setUp(self):
        self.app = App()
        self.session = FakeSession()
        self.heard: list[tuple[str, str]] = []
        for name in HOST_EVENTS:
            self.app.dests.register(name, self.recorder(name))

    def recorder(self, name: str):
        def record(session, frame):
            self.heard.append((name, session.path))

        return record

    def test_connect_is_raised_once_per_session_on_the_first_hello(self):
        self.app.dests.dispatch(self.session, {"dest": "reflux:hello", "data": {"path": "/a"}})
        self.app.dests.dispatch(self.session, {"dest": "reflux:hello", "data": {"path": "/b"}})
        self.assertEqual(self.heard, [("connect", "/a")])  # the second hello only re-draws
        self.assertEqual(self.session.path, "/b")

    def test_a_nav_raises_location(self):
        self.app.dests.dispatch(self.session, {"dest": "reflux:hello", "data": {"path": "/"}})
        self.heard.clear()
        self.app.dests.dispatch(self.session, {"dest": "reflux:nav", "data": {"path": "/b"}})
        self.assertEqual(self.heard, [("location", "/b")])

    def test_connect_is_raised_after_the_first_frame_is_queued(self):
        app, session = App(), FakeSession()
        app.page = lambda session, path: b.text("page")  # something to draw, so there is a frame
        seen: list[int] = []

        def record(session, frame):
            seen.append(len(session.frames))  # frames on the wire when the handler runs

        app.dests.register("connect", record)
        app.dests.dispatch(session, {"dest": "reflux:hello", "data": {"path": "/"}})
        self.assertEqual(seen, [1])  # the page is already out, so a handler's frames land on top

    def test_disconnect_fires_once_and_only_for_a_session_in_the_table(self):
        channel = object()
        session = Session("test0002", channel, lambda *a: None, {})
        self.app.sessions[channel] = session
        self.assertTrue(self.app._gone(session, "closed"))
        self.assertFalse(self.app._gone(session, "dead"))  # the second caller is not its own
        self.assertEqual(self.heard, [("disconnect", "/")])

    def test_nobody_listening_is_not_a_refusal(self):
        app = App()
        session = FakeSession()
        self.assertFalse(app.dests.announce("connect", session, {"dest": "connect", "data": {}}))
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