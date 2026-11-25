"""`@app.page` — a page declared on the app it belongs to, right above its handler.

The point of the decorator is where the declaration hangs, so the tests check that: the app's own
table, the module-level one left alone, and the two ways of declaring a path staying in step.

Two more things belong here because they are the same word: a page **returns** its structure (the
reactive path), and the manual path may still draw it with `ctx.page` — one answer per handler.
"""

from __future__ import annotations

import json
import unittest

from reflux import App, Routes, RoutesError
from reflux.sdk import h
from reflux.application import create_app

from .fakes import page_nodes


class TestDeclaringOnTheApp(unittest.TestCase):
    def test_the_page_lands_in_that_apps_table(self):
        app = create_app()

        @app.page("/hello", title="问候")
        def hello(ctx, match):
            return h.text("hi")

        self.assertEqual([found.path for found in app.routes], ["/hello"])
        match = app.routes.match("/hello")
        assert match is not None
        self.assertEqual(match.meta["title"], "问候")
        self.assertIs(match.route.handler, hello)

    def test_two_apps_share_nothing(self):
        first = create_app()
        second = create_app()

        @first.page("/only-here")
        def only_here(ctx, match):
            return h.text("x")

        self.assertIsNot(first.routes, second.routes)
        self.assertIsNotNone(first.routes.match("/only-here"))
        self.assertIsNone(second.routes.match("/only-here"))

    def test_a_second_decorator_is_an_alias(self):
        app = create_app()

        @app.page("/")
        @app.page("/home")
        def home(ctx, match):
            return h.text("home")

        self.assertEqual(sorted(found.path for found in app.routes), ["/", "/home"])
        alias = app.routes.match("/home")
        assert alias is not None
        self.assertIs(alias.route.handler, home)

    def test_the_same_path_twice_is_loud(self):
        app = create_app()
        app.page("/taken")(lambda ctx, match: h.text("a"))
        with self.assertRaises(RoutesError):
            app.page("/taken")(lambda ctx, match: h.text("b"))

    def test_a_fresh_app_starts_empty(self):
        # There is no module-level table to inherit and nothing to opt out of: an app's table is its own
        # from the first line, and `create_app()` is how a second, independent one is asked for.
        self.assertEqual(create_app().routes.table(), [])

    def test_layout_rides_along(self):
        app = create_app()

        def frame(ctx, match, page):
            return h.frame(page)

        @app.page("/framed", layout=frame)
        def framed(ctx, match):
            return h.text("in")

        match = app.routes.match("/framed")
        assert match is not None
        self.assertIs(match.route.layout, frame)


if __name__ == "__main__":
    unittest.main()

class TestWhatAPageGives(unittest.TestCase):
    """The structure leaves a page one way: returned, or drawn. Never both, never neither by accident."""

    def test_a_returned_node_is_the_page(self):
        app = create_app()

        @app.page("/", title="回声")
        def home(ctx, match):
            return h.text("hi", id="greeting")

        root = page_nodes(app, "/")[0]
        self.assertEqual(root["id"], "page-root")
        dumped = json.dumps(root, ensure_ascii=False)
        self.assertIn('"greeting"', dumped)  # the returned node is in the frame
        self.assertIn("回声", dumped)  # and the title the declaration named, not one the handler repeated

    def test_drawing_and_returning_is_loud(self):
        """Both is a defect with no right answer: refuse it instead of picking one."""
        app = create_app()

        @app.page("/")
        def confused(ctx, match):
            ctx.page(h.text("drawn"))
            return h.text("returned")

        with self.assertRaises(RoutesError) as raised:
            page_nodes(app, "/")
        self.assertIn("returns its structure or draws it", str(raised.exception))

    def test_the_single_page_may_return_too(self):
        """`@app.page` with no path is the one page; it returns like any other."""
        app = create_app()

        @app.page
        def only(ctx, path):
            return h.text(path, id="where")

        root = page_nodes(app, "/walk")[0]
        self.assertIn('"where"', json.dumps(root, ensure_ascii=False))

    def test_a_single_page_with_parentheses_is_the_same_thing(self):
        app = create_app()

        @app.page()
        def only(ctx, path):
            return h.text("hi")

        self.assertTrue(page_nodes(app, "/"))
