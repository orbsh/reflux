"""`@app.route` — a page declared on the app it belongs to, right above its handler.

The point of the decorator is where the declaration hangs, so the tests check that: the app's own
table, the module-level one left alone, and the two ways of declaring a path staying in step.
"""

from __future__ import annotations

import unittest

from reflux import DEFAULT, App, Routes, RoutesError, route
from reflux.sdk import builders as b


class TestDeclaringOnTheApp(unittest.TestCase):
    def test_the_page_lands_in_that_apps_table(self):
        app = App(routes=Routes())

        @app.route("/hello", title="问候")
        def hello(device, match):
            return b.text("hi")

        self.assertEqual([found.path for found in app.routes], ["/hello"])
        match = app.routes.match("/hello")
        assert match is not None
        self.assertEqual(match.meta["title"], "问候")
        self.assertIs(match.route.handler, hello)

    def test_the_default_table_is_not_touched(self):
        before = len(DEFAULT)
        app = App(routes=Routes())

        @app.route("/only-here")
        def only_here(device, match):
            return b.text("x")

        self.assertEqual(len(DEFAULT), before)
        self.assertIsNone(DEFAULT.match("/only-here"))

    def test_a_second_decorator_is_an_alias(self):
        app = App(routes=Routes())

        @app.route("/")
        @app.route("/home")
        def home(device, match):
            return b.text("home")

        self.assertEqual(sorted(found.path for found in app.routes), ["/", "/home"])
        alias = app.routes.match("/home")
        assert alias is not None
        self.assertIs(alias.route.handler, home)

    def test_the_same_path_twice_is_loud(self):
        app = App(routes=Routes())
        app.route("/taken")(lambda device, match: b.text("a"))
        with self.assertRaises(RoutesError):
            app.route("/taken")(lambda device, match: b.text("b"))

    def test_a_bare_app_reads_the_module_table_and_app_route_does_not(self):
        @route("/module-level")
        def module_level(device, match):
            return b.text("m")

        self.assertIs(App().routes, DEFAULT)
        self.assertIsNotNone(App().routes.match("/module-level"))

    def test_layout_rides_along(self):
        app = App(routes=Routes())

        def frame(device, match, page):
            return b.case(page)

        @app.route("/framed", layout=frame)
        def framed(device, match):
            return b.text("in")

        match = app.routes.match("/framed")
        assert match is not None
        self.assertIs(match.route.layout, frame)


if __name__ == "__main__":
    unittest.main()