"""Static file server for the reflux shell.

One process serves the shell's own modules and the vendored assets, same-origin, with
caching off (a rebuilt shell must never need a hard refresh). The WebSocket channel
carrying ops and events lands in T2/T4 and will join this process.
"""

from __future__ import annotations

import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

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

    def log_message(self, format: str, *args) -> None:
        print(f"[http] {self.address_string()} {format % args}", flush=True)


def make_server(root: str | Path, port: int = 8000, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    """Return a bound (not yet serving) HTTP server for `root`.

    `port=0` picks a free port; read it back from ``server.server_address[1]``.
    """
    root = Path(root)
    if not (root / "index.html").is_file():
        raise FileNotFoundError(f"no index.html under {root} — wrong assets root?")
    handler = functools.partial(ShellHandler, directory=str(root))
    return ThreadingHTTPServer((host, port), handler)