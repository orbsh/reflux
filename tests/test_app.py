"""The app's page resolution: the route table, the built-in 404, and one road for hello and nav.

What a path turns into is the producer's half of navigation, and it is testable without a browser:
a frame in, one frame out, with the session's path updated on the way. The browser's half (the
path marker mirroring the address bar, popstate) is asserted in tools/gate_t6.py against a real
browser.
"""

from __future__ import annotations

import unittest

import reflux.demo_app as demo
from reflux.app import App, not_found
from reflux.routes import Routes
from reflux.sdk import builders as b
from reflux.sdk._parse import dump

from tests.fakes import FakeSession


def page_for(session, match):
    """A handler that says which path it was given — enough to see which page came back."""
    return b.text(f"page:{match.path}")


def drawn(session: FakeSession) -> list[dict]:
    """The operations of the last frame the app sent."""
    return session.frames[-1]["content"]


def shown(node: dict) -> str:
    """The text a `text` node carries by default — what a plain text page renders."""
    return node["bind"]["value"]["default"]


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
        root = drawn(session)[0]["data"]
        self.assertEqual(root["type"], "text")
        self.assertEqual(shown(root), "page:/a")

    def test_a_nav_frame_takes_the_same_road(self) -> None:
        app = self.app("/a", "/b")
        session = FakeSession(path="/a")
        app.events.dispatch(session, {"event": "reflux:hello", "data": {"path": "/a"}})
        app.events.dispatch(session, {"event": "reflux:nav", "data": {"path": "/b"}})
        self.assertEqual(session.path, "/b")
        self.assertEqual(len(session.frames), 2)
        self.assertEqual(shown(drawn(session)[0]["data"]), "page:/b")

    def test_an_unknown_path_without_a_fallback_draws_the_builtin_404(self) -> None:
        app = self.app("/a")
        session = FakeSession()
        app.events.dispatch(session, {"event": "reflux:nav", "data": {"path": "/nope"}})
        children = drawn(session)[0]["data"]["children"]
        self.assertEqual(shown(children[0]), "404")
        self.assertIn("/nope", shown(children[1]))
        self.assertEqual(session.path, "/nope")  # where the client stands, not a redirect

    def test_a_registered_tail_route_wins_over_the_404(self) -> None:
        app = self.app("/a", "/{rest:path}")
        session = FakeSession()
        app.events.dispatch(session, {"event": "reflux:nav", "data": {"path": "/nope/deep"}})
        self.assertEqual(shown(drawn(session)[0]["data"]), "page:/nope/deep")

    def test_the_builtin_404_is_a_valid_structure(self) -> None:
        node = dump(not_found("/x"))
        self.assertEqual(node["type"], "case")
        self.assertEqual([child["type"] for child in node["children"]], ["text", "text"])
        # the profile's token lane is how the framework's own page gets its look
        self.assertEqual(node["children"][0]["attrs"]["class"], ["rx-heading-1"])
        self.assertEqual(node["children"][1]["attrs"]["class"], ["rx-muted"])

    def test_an_app_that_sets_page_overrides_the_table(self) -> None:
        from reflux import wire

        app = self.app("/a")  # a table is there; the hook still wins
        app.page = lambda session, path: [wire.patch("here", "/bind/value/default", path)]
        session = FakeSession()
        app.events.dispatch(session, {"event": "reflux:nav", "data": {"path": "/whatever"}})
        op = drawn(session)[0]
        self.assertEqual(op["action"], "patch")
        self.assertEqual(op["value"], "/whatever")

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
            [
                "go.about",
                "go.home",
                "login.submit",
                "name.change",
                "reflux:hello",
                "reflux:nav",
                "row.add",
                "row.remove",
            ],
        )

    def test_the_demo_page_carries_its_slot_seed_in_the_same_frame(self) -> None:
        app = demo.make_app()
        session = FakeSession()
        app.events.dispatch(session, {"event": "reflux:hello", "data": {"path": "/"}})
        ops = drawn(session)
        self.assertEqual([op["action"] for op in ops], ["create", "append", "append"])
        self.assertEqual({op["event"] for op in ops[1:]}, {demo.ROWS})

    def test_a_second_visit_does_not_seed_the_rows_again(self) -> None:
        """A slot outlives a `create`, so the seed is once per session — not once per page turn."""
        app = demo.make_app()
        session = FakeSession()
        app.events.dispatch(session, {"event": "reflux:hello", "data": {"path": "/"}})
        app.events.dispatch(session, {"event": "reflux:nav", "data": {"path": "/"}})
        self.assertEqual([op["action"] for op in drawn(session)], ["create"])

    def test_the_demo_page_carries_the_two_markers(self) -> None:
        app = demo.make_app()
        session = FakeSession()
        app.events.dispatch(session, {"event": "reflux:hello", "data": {"path": "/about"}})
        root = drawn(session)[0]["data"]
        markers = {
            child["id"]: child["children"][0]["bind"]["value"]["default"]
            for child in root["children"]
            if child["type"] == "placeholder"
        }
        self.assertEqual(markers, {"reflux:path": "/about", "reflux:title": "关于"})

    def test_the_about_page_is_structure_only(self) -> None:
        app = demo.make_app()
        session = FakeSession()
        app.events.dispatch(session, {"event": "reflux:nav", "data": {"path": "/about"}})
        self.assertEqual([op["action"] for op in drawn(session)], ["create"])

    def test_a_navigation_submit_answers_with_the_new_page_and_path(self) -> None:
        app = demo.make_app()
        session = FakeSession()
        app.events.dispatch(session, {"event": "reflux:hello", "data": {"path": "/"}})
        app.events.dispatch(
            session, {"event": "go.about", "id": "nav-go.about", "data": {}}
        )
        self.assertEqual(session.path, "/about")
        root = drawn(session)[0]["data"]
        path_marker = next(child for child in root["children"] if child.get("id") == "reflux:path")
        self.assertEqual(path_marker["children"][0]["bind"]["value"]["default"], "/about")


if __name__ == "__main__":
    unittest.main()