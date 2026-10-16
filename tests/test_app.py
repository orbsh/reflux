"""The app's page resolution: the route table, the built-in 404, and one road for hello and nav.

What a path turns into is the producer's half of navigation, and it is testable without a browser:
a frame in, one frame out, with the session's path updated on the way. The shell's half (the click
interception, history, popstate) is asserted in tools/gate_t6.py against a real browser.
"""

from __future__ import annotations

import unittest

import reflux.demo_app as demo
from reflux import ops, ui
from reflux.app import App, not_found
from reflux.routes import Routes

from tests.fakes import FakeSession


def page_for(session, match):
    """A handler that says which path it was given — enough to see which page came back."""
    return ui.text(f"page:{match.path}")


def drawn(session: FakeSession) -> list[dict]:
    """The ops of the last frame the app sent."""
    frame = session.frames[-1]
    return frame["ops"]


class TestPageResolution(unittest.TestCase):
    def app(self, *paths: str) -> App:
        table = Routes()
        for path in paths:
            table.add(path, page_for)
        return App(routes=table)

    def test_hello_resolves_the_path_it_carries(self) -> None:
        app = self.app("/a")
        session = FakeSession(path="/")
        app.events.dispatch(session, {"event": "reflux:hello", "data": {"path": "/a"}})
        self.assertEqual(session.path, "/a")
        self.assertEqual(len(session.frames), 1)
        self.assertEqual(session.frames[0]["ev"], "draw")
        root = drawn(session)[0]["root"]
        self.assertEqual(root["type"], "text")
        self.assertEqual(root["attrs"]["value"], "page:/a")

    def test_a_nav_frame_takes_the_same_road(self) -> None:
        app = self.app("/a", "/b")
        session = FakeSession(path="/a")
        app.events.dispatch(session, {"event": "reflux:hello", "data": {"path": "/a"}})
        app.events.dispatch(session, {"event": "reflux:nav", "data": {"path": "/b"}})
        self.assertEqual(session.path, "/b")
        self.assertEqual(len(session.frames), 2)
        self.assertEqual(drawn(session)[0]["root"]["attrs"]["value"], "page:/b")

    def test_an_unknown_path_without_a_fallback_draws_the_builtin_404(self) -> None:
        app = self.app("/a")
        session = FakeSession()
        app.events.dispatch(session, {"event": "reflux:nav", "data": {"path": "/nope"}})
        root = drawn(session)[0]["root"]
        self.assertEqual(root["children"][0]["attrs"]["value"], "404")
        self.assertIn("/nope", root["children"][1]["attrs"]["value"])
        self.assertEqual(session.path, "/nope")  # where the client stands, not a redirect

    def test_a_registered_tail_route_wins_over_the_404(self) -> None:
        app = self.app("/a", "/{rest:path}")
        session = FakeSession()
        app.events.dispatch(session, {"event": "reflux:nav", "data": {"path": "/nope/deep"}})
        self.assertEqual(drawn(session)[0]["root"]["attrs"]["value"], "page:/nope/deep")

    def test_the_builtin_404_is_a_valid_structure(self) -> None:
        node = not_found("/x")
        self.assertEqual(node["type"], "stack")
        self.assertEqual([child["type"] for child in node["children"]], ["heading", "text"])

    def test_an_app_that_sets_page_overrides_the_table(self) -> None:
        app = self.app("/a")  # a table is there; the hook still wins
        app.page = lambda session, path: [ops.patch("/slots/here", path)]
        session = FakeSession()
        app.events.dispatch(session, {"event": "reflux:nav", "data": {"path": "/whatever"}})
        frame = session.frames[-1]
        self.assertEqual(frame["ops"][0]["op"], "patch")
        self.assertEqual(frame["ops"][0]["value"], "/whatever")

    def test_an_app_with_neither_page_nor_routes_draws_nothing(self) -> None:
        app = App(routes=Routes())
        session = FakeSession()
        app.events.dispatch(session, {"event": "reflux:hello", "data": {"path": "/"}})
        self.assertEqual(session.frames, [])


class TestTheDemoApp(unittest.TestCase):
    def test_the_demo_declares_routes_and_handlers(self) -> None:
        app = demo.make_app()
        for path in ("/", "/about"):
            with self.subTest(path=path):
                self.assertIsNotNone(app.routes.match(path))
        self.assertEqual(
            sorted(app.events.names()),
            ["login.submit", "name.change", "reflux:hello", "reflux:nav", "row.add", "row.remove"],
        )

    def test_the_demo_page_carries_its_slot_seed_in_the_same_frame(self) -> None:
        app = demo.make_app()
        session = FakeSession()
        app.events.dispatch(session, {"event": "reflux:hello", "data": {"path": "/"}})
        frame = session.frames[-1]
        self.assertEqual([op["op"] for op in frame["ops"]], ["create", "patch"])
        self.assertEqual(frame["ops"][1]["path"], "/slots/rows")
        self.assertEqual(len(frame["ops"][1]["value"]), 2)  # the two seed rows

    def test_the_about_page_is_structure_only(self) -> None:
        app = demo.make_app()
        session = FakeSession()
        app.events.dispatch(session, {"event": "reflux:nav", "data": {"path": "/about"}})
        frame = session.frames[-1]
        self.assertEqual(len(frame["ops"]), 1)
        self.assertEqual(frame["ops"][0]["root"]["children"][1]["attrs"]["value"], "关于")


if __name__ == "__main__":
    unittest.main()