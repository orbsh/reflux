"""Static file server for the reflux shell, plus the ``/ws`` channel when an app is attached.

One process serves the shell's own modules and the vendored assets, same-origin, with caching
off (a rebuilt shell must never need a hard refresh), upgrades ``GET /ws`` to the channel the
shell speaks on, and hands any *page path* (no file extension, no such file) to the shell itself
— which is what makes a deep link or a reload work: the client boots and asks the producer what
lives at that path. Without an app it is a plain static server: the shell loads and shows its
probe, and holds no session.
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


class ShellHandler(SimpleHTTPRequestHandler):
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
        # A page path is served the shell: the client boots and asks the producer what lives
        # there (that is what makes a deep link and a reload work at all). Anything that looks
        # like a file is served — or 404s — as a file: a missing module must never come back as
        # HTML, or the browser would fail on it in a way nobody can read.
        if not Path(page).suffix and not Path(self.translate_path(self.path)).is_file():
            self.path = "/index.html"
        super().do_GET()

    def log_message(self, format: str, *args) -> None:
        print(f"[http] {self.address_string()} {format % args}", flush=True)


def make_server(
    root: str | Path,
    port: int = 8000,
    host: str = "127.0.0.1",
    app=None,
) -> ThreadingHTTPServer:
    """Return a bound (not yet serving) HTTP server for `root`.

    `port=0` picks a free port; read it back from ``server.server_address[1]``. Passing `app`
    attaches the channel at `/ws` (it needs only ``handle(channel)``).
    """
    root = Path(root)
    if not (root / "index.html").is_file():
        raise FileNotFoundError(f"no index.html under {root} — wrong assets root?")
    handler = functools.partial(ShellHandler, directory=str(root))
    server = ThreadingHTTPServer((host, port), handler)
    server.app = app  # type: ignore[attr-defined]
    return server