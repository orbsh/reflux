"""The app's page resolution: the route table, the built-in 404, and one road for hello and nav.

What a path turns into is the producer's half of navigation, and it is testable without a browser:
a frame in, one frame out, with the device's path updated on the way. The browser's half (the
path marker mirroring the address bar, popstate) is asserted in tools/gate_t6.py against a real
browser.
"""

from __future__ import annotations

import unittest

import reflux.demo_app as demo
from reflux import ROUTES_SLOT
from reflux.app import App, not_found
from reflux.routes import Routes
from reflux.sdk import builders as b
from reflux.sdk._parse import dump

from tests.fakes import FakeDevice


def page_for(ctx, match):
    """A handler that draws which path it was given — enough to see which page came back."""
    ctx.page(b.text(f"page:{match.path}"))


def drawn(device: FakeDevice) -> list[dict]:
    """The operations of the last frame the app sent."""
    return device.frames[-1]


def page_op(device: FakeDevice) -> dict:
    """The page in the last frame: the `set` on `routes` (the frame around it is not resent)."""
    return next(op for op in drawn(device) if op["action"] == "set" and op["slot"] == ROUTES_SLOT)


def page_of(device: FakeDevice) -> dict:
    """The page's node as the client got it — the slot the shell declared, not the root."""
    return page_op(device)["data"]


def shown(node: dict) -> str:
    """The text the page's content carries — `ctx.page` writes the two markers ahead of it."""
    if node.get("type") == "case" and (node.get("children") or [{}])[0].get("id") == "reflux:path":
        node = node["children"][2]
    return node["bind"]["value"]["default"]


class TestPageResolution(unittest.TestCase):
    def app(self, *paths: str) -> App:
        table = Routes()
        for path in paths:
            table.add(path, page_for)
        return App(routes=table)

    def test_hello_resolves_the_path_it_carries(self) -> None:
        app = self.app("/a")
        device = FakeDevice(path="/")
        app.dests.dispatch(device, {"dest": "reflux:hello", "data": {"path": "/a"}})
        self.assertEqual(device.path, "/a")
        self.assertEqual(len(device.frames), 1)
        self.assertTrue(isinstance(device.frames[0], list), "一帧就是动作列表")
        # The default frame and the page in it, one frame: no shell declared is not a second road.
        self.assertEqual([op["action"] for op in drawn(device)], ["create", "set"])
        root = page_of(device)
        self.assertEqual(root["type"], "case")  # a page: the two markers, then the content
        self.assertEqual([kid.get("id") for kid in root["children"][:2]], ["reflux:path", "reflux:title"])
        self.assertEqual(shown(root), "page:/a")

    def test_a_nav_frame_takes_the_same_road(self) -> None:
        app = self.app("/a", "/b")
        device = FakeDevice(path="/a")
        app.dests.dispatch(device, {"dest": "reflux:hello", "data": {"path": "/a"}})
        app.dests.dispatch(device, {"dest": "reflux:nav", "data": {"path": "/b"}})
        self.assertEqual(device.path, "/b")
        self.assertEqual(len(device.frames), 2)
        self.assertEqual(shown(page_of(device)), "page:/b")

    def test_an_unknown_path_without_a_fallback_draws_the_builtin_404(self) -> None:
        app = self.app("/a")
        device = FakeDevice()
        app.dests.dispatch(device, {"dest": "reflux:nav", "data": {"path": "/nope"}})
        children = page_of(device)["children"]
        self.assertEqual(shown(children[0]), "404")
        self.assertIn("/nope", shown(children[1]))
        self.assertEqual(device.path, "/nope")  # where the client stands, not a redirect

    def test_a_registered_tail_route_wins_over_the_404(self) -> None:
        app = self.app("/a", "/{rest:path}")
        device = FakeDevice()
        app.dests.dispatch(device, {"dest": "reflux:nav", "data": {"path": "/nope/deep"}})
        self.assertEqual(shown(page_of(device)), "page:/nope/deep")

    def test_the_builtin_404_is_a_valid_structure(self) -> None:
        node = dump(not_found("/x"))
        self.assertEqual(node["type"], "case")
        self.assertEqual([child["type"] for child in node["children"]], ["text", "text"])
        # the profile's token lane is how the framework's own page gets its look
        self.assertEqual(node["children"][0]["attrs"]["class"], ["rx-heading-1"])
        self.assertEqual(node["children"][1]["attrs"]["class"], ["rx-muted"])

    def test_an_app_that_sets_page_overrides_the_table(self) -> None:
        app = self.app("/a")  # a table is there; the hook still wins

        def single(ctx, path):
            ctx.page(b.text(f"single:{path}"))  # a page is a node; ops are `ctx.emit`

        app.page = single
        device = FakeDevice()
        app.dests.dispatch(device, {"dest": "reflux:nav", "data": {"path": "/whatever"}})
        op = page_op(device)
        self.assertEqual(op["slot"], ROUTES_SLOT)
        self.assertEqual(shown(op["data"]), "single:/whatever")

    def test_an_app_with_neither_page_nor_routes_draws_nothing(self) -> None:
        app = App(routes=Routes())
        device = FakeDevice()
        app.dests.dispatch(device, {"dest": "reflux:hello", "data": {"path": "/"}})
        self.assertEqual(device.frames, [])


class TestTheDemoApp(unittest.TestCase):
    def test_the_demo_declares_routes_and_handlers(self) -> None:
        app = demo.make_app()
        for path in ("/", "/about"):
            with self.subTest(path=path):
                self.assertIsNotNone(app.routes.match(path))
        self.assertEqual(
            sorted(app.dests.names()),
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

    def test_the_demo_page_sends_its_slot_seed_before_the_page(self) -> None:
        """The rows are a send (`ctx.emit`), so they leave as their own frames, before the page."""
        app = demo.make_app()
        device = FakeDevice()
        app.dests.dispatch(device, {"dest": "reflux:hello", "data": {"path": "/"}})
        frames = device.frames
        self.assertEqual(device.frames[-1][0]["action"], "create")
        seeds = [frame for frame in frames[:-1]]
        self.assertEqual([op["action"] for frame in seeds for op in frame], ["append", "append"])
        self.assertEqual({op["slot"] for frame in seeds for op in frame}, {"rows"})

    def test_a_second_visit_does_not_seed_the_rows_again(self) -> None:
        """A slot outlives a page turn, so the seed is once per device — not once per turn."""
        app = demo.make_app()
        device = FakeDevice()
        app.dests.dispatch(device, {"dest": "reflux:hello", "data": {"path": "/"}})
        app.dests.dispatch(device, {"dest": "reflux:nav", "data": {"path": "/"}})
        self.assertEqual([op["action"] for op in drawn(device)], ["set"])

    def test_the_demo_page_carries_the_two_markers(self) -> None:
        app = demo.make_app()
        device = FakeDevice()
        app.dests.dispatch(device, {"dest": "reflux:hello", "data": {"path": "/about"}})
        root = page_of(device)
        markers = {
            child["id"]: child["children"][0]["bind"]["value"]["default"]
            for child in root["children"]
            if child["type"] == "placeholder"
        }
        self.assertEqual(markers, {"reflux:path": "/about", "reflux:title": "关于"})

    def test_the_about_page_is_structure_only(self) -> None:
        app = demo.make_app()
        device = FakeDevice()
        app.dests.dispatch(device, {"dest": "reflux:nav", "data": {"path": "/about"}})
        # This page seeds no slots, so the turn is the frame (a first visit draws it too) and the page.
        self.assertEqual([op["action"] for op in drawn(device)], ["create", "set"])

    def test_a_navigation_submit_answers_with_the_new_page_and_path(self) -> None:
        app = demo.make_app()
        device = FakeDevice()
        app.dests.dispatch(device, {"dest": "reflux:hello", "data": {"path": "/"}})
        app.dests.dispatch(
            device, {"dest": "go.about", "id": "nav-go.about", "data": {}}
        )
        self.assertEqual(device.path, "/about")
        root = page_of(device)
        path_marker = next(child for child in root["children"] if child.get("id") == "reflux:path")
        self.assertEqual(path_marker["children"][0]["bind"]["value"]["default"], "/about")


if __name__ == "__main__":
    unittest.main()