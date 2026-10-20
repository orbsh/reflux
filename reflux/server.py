"""Static file server for reflux's page, plus the ``/ws`` channel when an app is attached.

A server is one or more **mounts** — a URL prefix mapped to a directory. The page is the root mount
and its assets are a second one (``/static/``), which is what keeps a deep link from resolving an
asset reference against the deep-link directory. Prefixes are matched longest first.

Each mount serves its own modules and pinned assets, same-origin, with caching off (a rebuilt page
must never need a hard refresh), upgrades ``GET /ws`` to the channel, and hands any *page path*
(no file extension, no such file) to that mount's ``index.html`` — which is what makes a deep link
or a reload work: the client boots and asks the producer what lives at that path. Without an app
it is a plain static server and holds no session.
"""

from __future__ import annotations

import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .channel import WS_PATH, is_upgrade, upgrade

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
        app = getattr(self.server, "app", None)
        page = self.path.split("?", 1)[0]
        if app is not None and page == WS_PATH and is_upgrade(self.headers):
            # The connection stops being HTTP here: the app reads frames until it closes.
            channel = upgrade(self)
            app.handle(channel)
            return

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
        the session accounting has already run by then (`App.handle` caught the close), so the
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