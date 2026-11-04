"""Static file server for reflux's page, plus the ``/ws`` channel when an app is attached.

A server is one or more **mounts** — a URL prefix mapped to a directory. The page is the root mount
and its assets are a second one (``/static/``), which is what keeps a deep link from resolving an
asset reference against the deep-link directory. Prefixes are matched longest first.

Each mount serves its own modules and pinned assets, same-origin, with caching off (a rebuilt page
must never need a hard refresh), upgrades ``GET /ws`` to the channel, and hands any *page path*
(no file extension, no such file) to that mount's ``index.html`` — which is what makes a deep link
or a reload work: the client boots and asks the producer what lives at that path. Without an app
it is a plain static server and holds no device.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs

from .channel import is_upgrade, upgrade

# A mount entry that is the websocket channel rather than a callable: the socket is one route in the
# same table as the app's own paths, and nothing in the table knows it is special until it is served.
CHANNEL = object()


@dataclass(frozen=True)
class Request:
    """One HTTP request, as a mounted route sees it — the facts, and nothing of `http.server`."""

    method: str
    path: str
    query: dict[str, list[str]] = field(default_factory=dict)
    headers: Mapping[str, str] = field(default_factory=dict)
    peer: str | None = None
    body: bytes = b""


@dataclass(frozen=True)
class Response:
    """What a mounted route answers with. Bytes or text; the type is the route's to state."""

    status: int = 200
    body: bytes | str = b""
    content_type: str = "text/plain; charset=utf-8"


def _body(value: Any) -> bytes | str:
    """A route may hand back text or bytes; anything else is its repr, which is at least visible."""
    return value if isinstance(value, (bytes, str)) else str(value)


def as_response(answered: Any) -> Response:
    """A route may return a `Response`, a `(status, body)` pair, or the body itself (200)."""
    if isinstance(answered, Response):
        return answered
    if isinstance(answered, tuple) and len(answered) == 2:
        status, body = answered
        return Response(int(status), _body(body))
    if answered is None:
        return Response(404, "not found")
    return Response(200, _body(answered))

# Deterministic content types: don't leave module MIME to the host's /etc/mime.types,
# because a wrong type makes the browser refuse the module.
_TYPES = {
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".json": "application/json",
    ".css": "text/css",
    ".html": "text/html",
    ".svg": "image/svg+xml",
    ".txt": "text/plain",
}


class PageHandler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, **_TYPES}

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_GET(self) -> None:
        if self._serve_route():
            return
        page = self.path.split("?", 1)[0]

        prefix, root = self._mount(page)
        if prefix is None:
            self.send_error(404, "nothing mounted here")
            return
        if prefix == "/" and page + "/" in self._mounts():
            # "/static" without its slash: send the browser to the mounted root, or every
            # relative reference on that page would resolve against "/" instead.
            self.send_response(301)
            self.send_header("Location", page + "/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if prefix != "/":
            self.directory = str(root)
            self.path = page[len(prefix) - 1 :] + self.path[len(page) :]

        # A page path is served that mount's index: the client boots and asks the producer what
        # lives there (that is what makes a deep link and a reload work at all). Anything that
        # looks like a file is served — or 404s — as a file: a missing module must never come
        # back as HTML, or the browser would fail on it in a way nobody can read.
        if not Path(self.path.split("?", 1)[0]).suffix and not Path(
            self.translate_path(self.path)
        ).is_file():
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        if not self._serve_route():
            self.send_error(405, "no route here takes a POST")

    def _serve_route(self) -> bool:
        """The app's own table answers first — the channel, or a path it mounted. True = answered.

        The channel is one entry in that table (`CHANNEL`), which is what makes the socket a route
        rather than a special case of the server: this method is the only place that knows the
        difference, and it is one `is` test.
        """
        app = getattr(self.server, "app", None)
        if app is None:
            return False
        page = self.path.split("?", 1)[0]
        route = getattr(app, "mounts", {}).get(page)
        if route is None:
            return False
        if route is CHANNEL:
            if not is_upgrade(self.headers):
                self.send_error(426, "this route is the websocket channel")
                return True
            # The connection stops being HTTP here: the app reads frames until it closes.
            app.handle(upgrade(self))
            return True
        if isinstance(route, (str, Path)):
            return False  # a directory mount: the static path below serves it, file by file
        length = int(self.headers.get("Content-Length") or 0)
        request = Request(
            method=getattr(self, "command", "GET") or "GET",
            path=page,
            query=parse_qs(self.path.split("?", 1)[1], keep_blank_values=True) if "?" in self.path else {},
            headers={key.lower(): value for key, value in self.headers.items()},
            peer=self.client_address[0] if self.client_address else None,
            body=self.rfile.read(length) if length else b"",
        )
        try:
            answered = as_response(route(request))
        except Exception as bad:  # a route's defect is the route's: answer it, keep serving
            print(f"[http] route {page!r} raised: {bad!r}", flush=True)
            self.send_error(500, "the route raised")
            return True
        payload = answered.body.encode("utf-8") if isinstance(answered.body, str) else answered.body
        self.send_response(answered.status)
        self.send_header("Content-Type", answered.content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if payload:
            self.wfile.write(payload)
        return True

    def _mounts(self) -> dict:
        return getattr(self.server, "mounts", None) or {}

    def _mount(self, page: str):
        """(prefix, directory) with the longest matching prefix winning — or (None, None)."""
        mounts = self._mounts()
        for prefix in sorted(mounts, key=len, reverse=True):
            if page.startswith(prefix):
                return prefix, Path(mounts[prefix])
        return None, None

    def finish(self) -> None:
        """Close the connection, tolerating a peer that vanished mid-write.

        A websocket client that hangs up leaves `super().finish()` flushing into a dead socket;
        the device accounting has already run by then (`App.handle` caught the close), so the
        stack trace would only be noise about the TCP half of an event we handled.
        """
        try:
            super().finish()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, format: str, *args) -> None:
        print(f"[http] {self.address_string()} {format % args}", flush=True)


def make_server(
    root: str | Path | None = None,
    port: int = 8000,
    host: str = "127.0.0.1",
    app=None,
    *,
    mounts: dict[str, str | Path] | None = None,
) -> ThreadingHTTPServer:
    """Return a bound (not yet serving) HTTP server for `root`, or for a table of mounts.

    `port=0` picks a free port; read it back from ``server.server_address[1]``. Passing `app`
    attaches the channel at `/ws` (it needs only ``handle(channel)``).

    `mounts` maps a URL prefix to a directory — ``{"/": page, "/static/": assets}`` serves the page
    and its assets from one origin. Prefixes
    are matched longest first; every mount needs its own `index.html`.
    """
    if mounts is None:
        if root is None:
            raise TypeError("make_server needs root= or mounts=")
        mounts = {"/": root}
    table = {prefix: Path(directory) for prefix, directory in mounts.items()}
    for prefix, directory in table.items():
        if not directory.is_dir():
            raise FileNotFoundError(f"no such directory for mount {prefix!r}: {directory}")
    # Only the base mount must serve a page; the others may be asset trees (a page path under one
    # of those 404s, which is the honest answer — it is not a page).
    base_prefix = "/" if "/" in table else sorted(table, key=len)[0]
    if not (table[base_prefix] / "index.html").is_file():
        raise FileNotFoundError(
            f"the page mount {base_prefix!r} has no index.html ({table[base_prefix]})"
        )
    base = table[base_prefix]
    handler = functools.partial(PageHandler, directory=str(base))
    server = ThreadingHTTPServer((host, port), handler)
    server.app = app  # type: ignore[attr-defined]
    server.mounts = table  # type: ignore[attr-defined]
    return server