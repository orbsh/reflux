"""`@app.page` — a page declared on the app it belongs to, right above its handler.

The point of the decorator is where the declaration hangs, so the tests check that: the app's own
table, the module-level one left alone, and the two ways of declaring a path staying in step.

Two more things belong here because they are the same word: a page **returns** its structure (the
reactive path), and the manual path may still draw it with `ctx.page` — one answer per handler.
"""

from __future__ import annotations

import json
import unittest

from reflux import DEFAULT, App, Routes, RoutesError, page
from reflux.sdk import h

from .fakes import page_nodes


class TestDeclaringOnTheApp(unittest.TestCase):
    def test_the_page_lands_in_that_apps_table(self):
        app = App(routes=Routes())

        @app.page("/hello", title="问候")
        def hello(ctx, match):
            return h.text("hi")

        self.assertEqual([found.path for found in app.routes], ["/hello"])
        match = app.routes.match("/hello")
        assert match is not None
        self.assertEqual(match.meta["title"], "问候")
        self.assertIs(match.route.handler, hello)

    def test_the_default_table_is_not_touched(self):
        before = len(DEFAULT)
        app = App(routes=Routes())

        @app.page("/only-here")
        def only_here(ctx, match):
            return h.text("x")

        self.assertEqual(len(DEFAULT), before)
        self.assertIsNone(DEFAULT.match("/only-here"))

    def test_a_second_decorator_is_an_alias(self):
        app = App(routes=Routes())

        @app.page("/")
        @app.page("/home")
        def home(ctx, match):
            return h.text("home")

        self.assertEqual(sorted(found.path for found in app.routes), ["/", "/home"])
        alias = app.routes.match("/home")
        assert alias is not None
        self.assertIs(alias.route.handler, home)

    def test_the_same_path_twice_is_loud(self):
        app = App(routes=Routes())
        app.page("/taken")(lambda ctx, match: h.text("a"))
        with self.assertRaises(RoutesError):
            app.page("/taken")(lambda ctx, match: h.text("b"))

    def test_a_bare_app_reads_the_module_table_and_app_route_does_not(self):
        @page("/module-level")
        def module_level(ctx, match):
            return h.text("m")

        self.assertIs(App().routes, DEFAULT)
        self.assertIsNotNone(App().routes.match("/module-level"))

    def test_layout_rides_along(self):
        app = App(routes=Routes())

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
        app = App(routes=Routes())

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
        app = App(routes=Routes())

        @app.page("/")
        def confused(ctx, match):
            ctx.page(h.text("drawn"))
            return h.text("returned")

        with self.assertRaises(RoutesError) as raised:
            page_nodes(app, "/")
        self.assertIn("returns its structure or draws it", str(raised.exception))

    def test_the_single_page_may_return_too(self):
        """`@app.page` with no path is the one page; it returns like any other."""
        app = App(routes=Routes())

        @app.page
        def only(ctx, path):
            return h.text(path, id="where")

        root = page_nodes(app, "/walk")[0]
        self.assertIn('"where"', json.dumps(root, ensure_ascii=False))

    def test_a_single_page_with_parentheses_is_the_same_thing(self):
        app = App(routes=Routes())

        @app.page()
        def only(ctx, path):
            return h.text("hi")

        self.assertTrue(page_nodes(app, "/"))
