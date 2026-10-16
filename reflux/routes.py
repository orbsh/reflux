"""Routing: a table keyed by path, declared where the handler is written.

    from reflux import route

    @route("/blog/{slug}", title="文章")
    def post(session, match): ...

    @route("/")                # an alias: the same handler on a second path
    @route("/posts")
    def post_index(session, match): ...

Two conventions, no more: `{name}` takes one segment (never an empty one) and `{name:path}` is the
closing catch-all, taking the rest — empty included. The matcher knows only this table, so there is
no second list to keep in step, and no file name ever becomes a URL: discovery is an import.

Every mistake dies at registration, while the app is still starting — a path declared twice, two
patterns that can both match the same concrete path and are equally specific, a converter other
than `path`, a handler or a layout that is not callable. Registration order never decides anything.
"""

from __future__ import annotations

import importlib
import pkgutil
import re
from typing import Any, Callable, Iterator, overload
from urllib.parse import unquote

__all__ = ["Match", "Route", "Routes", "RoutesError", "DEFAULT", "route", "discover"]

NAME = re.compile(r"^\{([A-Za-z_][A-Za-z0-9_]*)\}$")
CONVERTED = re.compile(r"^\{([A-Za-z_][A-Za-z0-9_]*):([A-Za-z_][A-Za-z0-9_]*)\}$")
CONVERTERS = ("path",)

# (kind, value): a static segment's text, or a placeholder's name
Spec = tuple[str, str]


class RoutesError(Exception):
    """A registration that can never be right — raised while the app is still starting."""


def segments_of(path: str) -> list[str]:
    """A request path as decoded segments.

    Empty segments — a trailing or a doubled slash — are not segments; that is what lets
    `{name:path}` stand for "nothing left" as well as for a whole remainder.
    """
    clean = path.split("#", 1)[0].split("?", 1)[0]
    return [unquote(part) for part in clean.split("/") if part != ""]


def compile_path(path: str) -> tuple[Spec, ...]:
    """A pattern as segment specs."""
    if not isinstance(path, str) or not path.startswith("/"):
        raise RoutesError(f"{path!r} is not a path: it must be a string starting with /")
    if path != "/" and path.endswith("/"):
        raise RoutesError(f"{path!r} ends with a slash — {{name:path}} is how a path covers the rest")
    specs: list[Spec] = []
    for part in path.split("/")[1:]:
        if part == "":
            continue  # the root path "/", and any doubled slash in a declaration
        if specs and specs[-1][0] == "tail":
            raise RoutesError(f"{path!r}: nothing may follow a {{name:path}} tail")
        converted = CONVERTED.match(part)
        if converted:
            name, kind = converted.groups()
            if kind not in CONVERTERS:
                raise RoutesError(f"{path!r}: {kind!r} is not a converter ({', '.join(CONVERTERS)})")
            specs.append(("tail", name))
            continue
        named = NAME.match(part)
        if named:
            specs.append(("param", named.group(1)))
            continue
        if "{" in part or "}" in part:
            raise RoutesError(f"{path!r}: {part!r} is neither a static segment nor a {{name}} placeholder")
        specs.append(("static", part))
    names = [value for kind, value in specs if kind != "static"]
    repeated = sorted({name for name in names if names.count(name) > 1})
    if repeated:
        raise RoutesError(f"{path!r}: the same parameter name twice: {repeated}")
    return tuple(specs)


def rank(specs: tuple[Spec, ...]) -> tuple[int, int, int, int]:
    """How specific a pattern is; larger is more specific.

    More static segments beats more captures; a pattern with no tail beats one with a tail (the
    tail is the fallback of last resort); deeper beats shallower; fewer captures beats more.
    """
    static = sum(1 for kind, _ in specs if kind == "static")
    has_tail = any(kind == "tail" for kind, _ in specs)
    captures = sum(1 for kind, _ in specs if kind in ("param", "tail"))
    return (static, 0 if has_tail else 1, len(specs), -captures)


def _pair_ok(left: Spec, right: Spec) -> bool:
    if left[0] == "static" and right[0] == "static":
        return left[1] == right[1]
    return True  # a placeholder accepts whatever the other side asks for


def can_both_match(a: tuple[Spec, ...], b: tuple[Spec, ...]) -> bool:
    """Whether one concrete path could satisfy both patterns.

    Specificity is a separate question — this is only about whether a shared path exists, so
    registration can refuse the pair that is *both* shared and equally specific.
    """
    tail_a = any(kind == "tail" for kind, _ in a)
    tail_b = any(kind == "tail" for kind, _ in b)
    if not tail_a and not tail_b:
        return len(a) == len(b) and all(_pair_ok(x, y) for x, y in zip(a, b))
    if tail_a and not tail_b:
        return len(b) >= len(a) - 1 and all(_pair_ok(x, y) for x, y in zip(a[: len(a) - 1], b))
    if tail_b and not tail_a:
        return len(a) >= len(b) - 1 and all(_pair_ok(x, y) for x, y in zip(a, b[: len(b) - 1]))
    prefix = min(len(a), len(b)) - 1
    return all(_pair_ok(x, y) for x, y in zip(a[:prefix], b[:prefix]))


def match_segments(specs: tuple[Spec, ...], segments: list[str]) -> dict[str, str] | None:
    """The parameters this pattern reads off these segments, or None when it does not match."""
    has_tail = bool(specs) and specs[-1][0] == "tail"
    fixed = specs[:-1] if has_tail else specs
    if len(segments) < len(fixed):
        return None
    if not has_tail and len(segments) != len(fixed):
        return None
    params: dict[str, str] = {}
    for (kind, value), part in zip(fixed, segments):
        if kind == "static":
            if part != value:
                return None
        else:
            params[value] = part
    if has_tail:
        params[specs[-1][1]] = "/".join(segments[len(fixed):])
    return params


class Route:
    """One declaration: the pattern, the handler, its layout, its metadata, where it came from."""

    def __init__(
        self,
        path: str,
        handler: Callable,
        layout: Callable | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        self.path = path
        self.specs = compile_path(path)
        self.handler = handler
        self.layout = layout
        self.meta = dict(meta or {})
        self.source = getattr(handler, "__module__", None)

    @property
    def names(self) -> list[str]:
        return [value for kind, value in self.specs if kind != "static"]

    def __repr__(self) -> str:  # what `reflux routes` prints is the table, this is for the debugger
        return f"<Route {self.path!r} -> {self.handler!r}>"


class Match:
    """One match: which route, on which concrete path, with which parameters.

    This is what a handler receives, and `resolve(session)` is how a page is built — the layout,
    when there is one, wraps the handler's structure around the page it is handed.
    """

    def __init__(self, route: Route, path: str, params: dict[str, str]) -> None:
        self.route = route
        self.path = path
        self.params = dict(params)

    @property
    def meta(self) -> dict[str, Any]:
        return self.route.meta

    def resolve(self, session) -> Any:
        """The structure of this page: the handler's, wrapped by the layout when it declared one."""
        page = self.route.handler(session, self)
        if self.route.layout is None:
            return page
        return self.route.layout(session, self, page)

    def __repr__(self) -> str:
        return f"<Match {self.route.path!r} {self.params!r}>"


class Routes:
    """The table. Registration is where every mistake is loud; matching only reads the table."""

    def __init__(self) -> None:
        self._by_path: dict[str, Route] = {}

    @overload
    def add(
        self, path: str, handler: None = None, *, layout: Callable | None = None, **meta: Any
    ) -> Callable[[Callable], Callable]: ...

    @overload
    def add(
        self, path: str, handler: Callable, *, layout: Callable | None = None, **meta: Any
    ) -> Route: ...

    def add(
        self,
        path: str,
        handler: Callable | None = None,
        *,
        layout: Callable | None = None,
        **meta: Any,
    ) -> Callable[[Callable], Callable] | Route:
        """Declare a route: `@routes.add("/x")` or `routes.add("/x", handler=fn)`, with a layout
        and any metadata fields. The decorator form hands the handler back (that is what makes
        stacking two decorators an alias); the explicit form hands the Route back.
        """
        if handler is None:

            def decorate(function: Callable) -> Callable:
                self.register(path, function, layout=layout, **meta)
                return function

            return decorate
        return self.register(path, handler, layout=layout, **meta)

    def register(
        self,
        path: str,
        handler: Callable,
        *,
        layout: Callable | None = None,
        **meta: Any,
    ) -> Route:
        if not callable(handler):
            raise RoutesError(f"{path!r}: handler must be callable, got {type(handler).__name__}")
        if layout is not None and not callable(layout):
            raise RoutesError(f"{path!r}: layout must be callable, got {type(layout).__name__}")
        route = Route(path, handler, layout, meta)
        if path in self._by_path:
            other = self._by_path[path]
            raise RoutesError(
                f"{path!r} is already registered (by {other.source}) — a path is declared once"
            )
        for other in self._by_path.values():
            if can_both_match(route.specs, other.specs) and rank(route.specs) == rank(other.specs):
                raise RoutesError(
                    f"{path!r} and {other.path!r} can both match the same path and are equally "
                    "specific — the table must not depend on registration order"
                )
        self._by_path[path] = route
        return route

    def __len__(self) -> int:
        return len(self._by_path)

    def __iter__(self) -> Iterator[Route]:
        return iter(self.routes())

    def routes(self) -> list[Route]:
        """Every route, in a fixed order (the table must not depend on how it was filled)."""
        return [self._by_path[path] for path in sorted(self._by_path)]

    def match(self, path: str) -> Match | None:
        """The most specific route for a request path, or None."""
        segments = segments_of(path)
        best: tuple[tuple[int, int, int, int], Route, dict[str, str]] | None = None
        for route in self.routes():
            params = match_segments(route.specs, segments)
            if params is None:
                continue
            score = rank(route.specs)
            if best is None or score > best[0]:
                best = (score, route, params)
        if best is None:
            return None
        return Match(best[1], path, best[2])

    def resolve(self, session, path: str) -> Any:
        """Match a path and build its page, or None when nothing matches."""
        match = self.match(path)
        return None if match is None else match.resolve(session)

    def table(self) -> list[tuple[str, str, dict[str, Any]]]:
        """Rows for `reflux routes`: path, source module, metadata fields."""
        return [(route.path, route.source or "-", route.meta) for route in self.routes()]


def discover(*packages: str) -> list[str]:
    """Import every module under the given packages — discovery is import.

    An import that fails is a startup error: skipping it is not on the menu, because a skipped
    module is a set of routes that silently do not exist.
    """

    def fatal(name: str) -> None:
        raise RoutesError(f"cannot walk {name!r} — a module that cannot be imported is not skipped")

    imported: list[str] = []
    for name in packages:
        module = importlib.import_module(name)
        imported.append(name)
        if hasattr(module, "__path__"):
            for info in pkgutil.walk_packages(module.__path__, prefix=f"{name}.", onerror=fatal):
                importlib.import_module(info.name)
                imported.append(info.name)
    return imported


DEFAULT = Routes()
route = DEFAULT.add