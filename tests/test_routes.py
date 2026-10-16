"""T5's gate: the route table, the matcher, discovery and the CLI — table-driven, no browser.

Routing mistakes are startup mistakes: a path declared twice, two patterns that can both match the
same concrete path and are equally specific, a converter that does not exist, a handler or layout
that is not callable. And the matcher's answer must never depend on the order routes were declared
in. Both halves are asserted here; most shapes are tables of cases, so a new case is one line.
"""

from __future__ import annotations

import contextlib
import io
import unittest

from reflux import cli
from reflux.routes import (
    DEFAULT,
    Routes,
    RoutesError,
    compile_path,
    discover,
    rank,
    segments_of,
)

SESSION = object()


def handler(name: str = "h"):
    def run(session, match):
        return f"{name}:{match.path}"

    return run


class TestCompilePath(unittest.TestCase):
    def test_segments_are_static_param_or_tail(self) -> None:
        self.assertEqual(
            compile_path("/a/{b}/{c:path}"),
            (("static", "a"), ("param", "b"), ("tail", "c")),
        )
        self.assertEqual(compile_path("/"), ())
        self.assertEqual(compile_path("/blog/{slug}"), (("static", "blog"), ("param", "slug")))

    def test_bad_shapes_die_at_registration(self) -> None:
        cases = {
            "a/b": "must be a string starting with /",
            "/a/": "ends with a slash",
            "/{a:slug}": "not a converter",
            "/{a:path}/b": "nothing may follow",
            "/a/{b}/{b}": "same parameter name twice",
            "/a/{b": "neither a static segment nor",
        }
        for path, reason in cases.items():
            with self.subTest(path=path):
                with self.assertRaises(RoutesError) as caught:
                    compile_path(path)
                self.assertIn(reason, str(caught.exception))

    def test_a_request_path_is_decoded_segments(self) -> None:
        self.assertEqual(segments_of("/blog/caf%C3%A9/"), ["blog", "café"])
        self.assertEqual(segments_of("/a//b"), ["a", "b"])
        self.assertEqual(segments_of("/blog/x?y=1#z"), ["blog", "x"])
        self.assertEqual(segments_of("/"), [])


class TestRegistration(unittest.TestCase):
    def test_a_path_is_declared_once(self) -> None:
        table = Routes()
        table.add("/x", handler())
        with self.assertRaises(RoutesError) as caught:
            table.add("/x", handler())
        self.assertIn("already registered", str(caught.exception))

    def test_parallel_patterns_are_refused(self) -> None:
        """/x/{a} and /{b}/y both match /x/y and are equally specific — order must not decide."""
        table = Routes()
        table.add("/x/{a}", handler())
        with self.assertRaises(RoutesError) as caught:
            table.add("/{b}/y", handler())
        self.assertIn("registration order", str(caught.exception))

    def test_patterns_that_share_a_path_but_differ_in_specificity_are_allowed(self) -> None:
        table = Routes()
        table.add("/x/{a}", handler())
        table.add("/x/y", handler())  # more static: it wins by rule, not by order
        self.assertEqual(len(table), 2)

    def test_equally_specific_patterns_that_cannot_share_a_path_are_allowed(self) -> None:
        table = Routes()
        table.add("/x/{a}", handler())
        table.add("/y/{b}", handler())
        self.assertEqual(len(table), 2)

    def test_handler_and_layout_must_be_callable(self) -> None:
        table = Routes()
        with self.assertRaises(RoutesError) as caught:
            table.add("/x", "not callable")  # type: ignore[arg-type]
        self.assertIn("handler must be callable", str(caught.exception))
        with self.assertRaises(RoutesError) as caught:
            table.add("/y", handler(), layout="not callable")  # type: ignore[arg-type]
        self.assertIn("layout must be callable", str(caught.exception))

    def test_decorator_form_returns_the_handler_so_aliases_stack(self) -> None:
        table = Routes()

        @table.add("/a")
        @table.add("/b")
        def page(session, match):
            return "page"

        self.assertEqual([route.path for route in table.routes()], ["/a", "/b"])
        for route in table.routes():
            self.assertIs(route.handler, page)

    def test_explicit_form_returns_the_route(self) -> None:
        table = Routes()
        registered = table.add("/c", handler())
        self.assertEqual(registered.path, "/c")
        self.assertEqual(registered.source, __name__)


class TestScoring(unittest.TestCase):
    def test_rank_orders_the_way_the_design_says(self) -> None:
        self.assertGreater(rank(compile_path("/a/b")), rank(compile_path("/a/{x}")))
        self.assertGreater(rank(compile_path("/a/{x}")), rank(compile_path("/a/{rest:path}")))
        self.assertGreater(
            rank(compile_path("/a/b/{rest:path}")), rank(compile_path("/a/{rest:path}"))
        )

    def test_static_beats_param_beats_tail(self) -> None:
        table = Routes()
        table.add("/a/{x}", handler("param"))
        table.add("/a/b", handler("static"))
        table.add("/a/{rest:path}", handler("tail"))
        cases = {
            "/a/b": "static",  # the static route outranks the capture that also matches it
            "/a/c": "param",
            "/a/b/c": "tail",
            "/a": "tail",
        }
        for path, who in cases.items():
            with self.subTest(path=path):
                match = table.match(path)
                self.assertIsNotNone(match)
                assert match is not None
                self.assertTrue(match.resolve(SESSION).startswith(who), match.resolve(SESSION))


class TestMatching(unittest.TestCase):
    def setUp(self) -> None:
        self.table = Routes()
        self.post = self.table.add("/blog/{slug}", handler("post")).handler
        self.rest = self.table.add("/blog/{rest:path}", handler("rest")).handler
        self.index = self.table.add("/", handler("index")).handler
        self.table.add("/posts", self.index)  # an alias: the same handler, a second path
        self.cafe = self.table.add("/café", handler("cafe")).handler
        self.docs = self.table.add("/docs/{part}/{rest:path}", handler("docs")).handler

    def test_matches_are_table_driven(self) -> None:
        cases = [
            ("/blog/hello", "post", {"slug": "hello"}),
            ("/blog/", "rest", {"rest": ""}),
            ("/blog/hello/world", "rest", {"rest": "hello/world"}),
            ("/", "index", {}),
            ("/posts", "index", {}),
            ("/caf%C3%A9", "cafe", {}),
            ("/docs/guide/part two/three", "docs", {"part": "guide", "rest": "part two/three"}),
            ("/docs/guide", "docs", {"part": "guide", "rest": ""}),
        ]
        for path, who, params in cases:
            with self.subTest(path=path):
                match = self.table.match(path)
                self.assertIsNotNone(match, f"{path} matched nothing")
                assert match is not None
                self.assertIs(match.route.handler, getattr(self, who))
                self.assertEqual(match.params, params)
                self.assertEqual(match.path, path)

    def test_a_param_never_takes_an_empty_segment(self) -> None:
        table = Routes()
        table.add("/x/{a}", handler())
        self.assertIsNone(table.match("/x"))
        self.assertIsNone(table.match("/x/"))

    def test_a_tail_takes_the_empty_remainder(self) -> None:
        table = Routes()
        table.add("/docs/{rest:path}", handler())
        for path in ("/docs", "/docs/"):
            with self.subTest(path=path):
                match = table.match(path)
                self.assertIsNotNone(match)
                assert match is not None
                self.assertEqual(match.params, {"rest": ""})

    def test_percent_escapes_are_decoded_per_segment(self) -> None:
        match = self.table.match("/blog/a%2Fb")
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.params["slug"], "a/b")  # %2F stays inside one segment

    def test_nothing_matching_is_none(self) -> None:
        self.assertIsNone(self.table.match("/nope/x/y/z"))
        self.assertIsNone(Routes().match("/x"))


class TestOrderInvariance(unittest.TestCase):
    PATHS = ["/", "/blog/{slug}", "/blog/{rest:path}", "/a/b", "/a/{x}", "/x/{a:path}"]
    REQUESTS = ["/", "/blog/hello", "/blog/hello/world", "/a/b", "/a/c", "/x/1/2", "/a/"]

    def _answers(self, order: list[str]) -> list[tuple[str, dict] | None]:
        table = Routes()
        for path in order:
            table.add(path, handler(path))
        self.assertEqual([route.path for route in table.routes()], sorted(self.PATHS))
        out = []
        for request in self.REQUESTS:
            match = table.match(request)
            out.append(None if match is None else (match.route.path, match.params))
        return out

    def test_the_same_set_in_any_order_matches_the_same_way(self) -> None:
        forwards = self.PATHS
        backwards = list(reversed(self.PATHS))
        shuffled = [self.PATHS[2], self.PATHS[5], self.PATHS[0], self.PATHS[4], self.PATHS[1], self.PATHS[3]]
        first = self._answers(forwards)
        self.assertEqual(first, self._answers(backwards))
        self.assertEqual(first, self._answers(shuffled))


class TestResolve(unittest.TestCase):
    def test_a_route_without_a_layout_resolves_to_the_handler(self) -> None:
        table = Routes()
        table.add("/x/{id}", handler("x"))
        match = table.match("/x/7")
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.resolve(SESSION), "x:/x/7")
        self.assertEqual(match.meta, {})

    def test_a_layout_wraps_the_page_the_handler_built(self) -> None:
        seen: dict = {}

        def layout(session, match, page):
            seen.update(session=session, path=match.path, page=page)
            return f"layout({page})"

        table = Routes()
        table.add("/admin", handler("admin"), layout=layout, title="后台")
        match = table.match("/admin")
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.resolve(SESSION), "layout(admin:/admin)")
        self.assertIs(seen["session"], SESSION)
        self.assertEqual(seen["page"], "admin:/admin")
        self.assertEqual(match.meta, {"title": "后台"})

    def test_routes_resolve_by_path_and_return_none_when_nothing_matches(self) -> None:
        table = Routes()
        table.add("/x", handler("x"))
        self.assertEqual(table.resolve(SESSION, "/x"), "x:/x")
        self.assertIsNone(table.resolve(SESSION, "/nope"))


class TestDiscovery(unittest.TestCase):
    def test_importing_a_package_registers_its_routes(self) -> None:
        imported = discover("tests.route_fixture")
        for expected in ("tests.route_fixture", "tests.route_fixture.blog", "tests.route_fixture.admin"):
            with self.subTest(module=expected):
                self.assertIn(expected, imported)
        paths = [path for path, _, _ in DEFAULT.table()]
        for expected in ("/blog/{slug}", "/posts", "/latest", "/admin"):
            with self.subTest(path=expected):
                self.assertIn(expected, paths)

    def test_the_source_column_is_where_the_route_was_written(self) -> None:
        discover("tests.route_fixture")
        sources = {path: source for path, source, _ in DEFAULT.table()}
        self.assertEqual(sources["/blog/{slug}"], "tests.route_fixture.blog")
        self.assertEqual(sources["/admin"], "tests.route_fixture.admin")

    def test_discovering_twice_is_a_no_op(self) -> None:
        discover("tests.route_fixture")
        before = len(DEFAULT)
        discover("tests.route_fixture")  # a second import does not re-run the decorators
        self.assertEqual(len(DEFAULT), before)

    def test_a_module_that_cannot_be_imported_is_fatal(self) -> None:
        with self.assertRaises(ImportError):
            discover("tests.route_fixture_broken")

    def test_nothing_to_discover_is_an_empty_list(self) -> None:
        self.assertEqual(discover(), [])


class TestCli(unittest.TestCase):
    def test_routes_prints_path_source_and_metadata(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["routes", "tests.route_fixture"])
        self.assertEqual(code, 0)
        text = out.getvalue()
        for expected in (
            "path",
            "source",
            "metadata",
            "/blog/{slug}",
            "/admin",
            "tests.route_fixture.blog",
            "title='文章'",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)
        printed = [line for line in text.splitlines() if line.startswith("/")]
        self.assertEqual(len(printed), len(DEFAULT))

    def test_a_verb_is_required(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            cli.main([])
        self.assertEqual(caught.exception.code, 2)

    def test_an_empty_table_prints_that_it_is_empty(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.print_routes([], table=Routes())
        self.assertEqual(code, 0)
        self.assertIn("nothing registered", out.getvalue())


if __name__ == "__main__":
    unittest.main()