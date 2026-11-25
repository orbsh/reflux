"""Static file server for reflux's page, plus the ``/ws`` channel when an app is attached.

A server is one or more **mounts** — a URL prefix mapped to a directory. The page is the root mount
and its assets are a second one (``/static/``), which is what keeps a deep link from resolving an
asset reference against the deep-link directory. Prefixes are matched longest first.

Each mount serves its own modules and pinned assets, same-origin, with caching off (a rebuilt page
must never need a hard refresh), upgrades the channel route to a WebSocket, and hands any *page path*
(no file extension, no such file) to that mount's ``index.html`` — which is what makes a deep link
or a reload work: the client boots and asks the producer what lives at that path. Without an app it
is a plain static server and holds no device.

The transport is asyncio (ADR 0002): aiohttp owns HTTP and the WebSocket handshake, one task per
connection, and the loop runs in a thread of its own so `make_server` keeps the blocking shape its
callers — the gates, `tools/serve.py`, `tools/cdp.py` — already speak.
"""

from __future__ import annotations

import asyncio
import traceback

import aiohttp
import mimetypes
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs

from aiohttp import web

from .settle import maybe

# A mount entry that is the websocket channel rather than a callable: the socket is one route in the
# same table as the app's own paths, and nothing in the table knows it is special until it is served.
CHANNEL = object()

# aiohttp's typed keys for what a request needs to reach: strings would warn on every run, and a
# typo in one would be a KeyError at request time rather than at import.
APP_KEY: web.AppKey = web.AppKey("reflux", object)
MOUNTS_KEY: web.AppKey = web.AppKey("mounts", dict)


@dataclass(frozen=True)
class Request:
    """One HTTP request, as a mounted route sees it — the facts, and nothing of aiohttp."""

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

NO_CACHE = "no-cache"


def _content_type(path: Path) -> str:
    known = _TYPES.get(path.suffix.lower())
    if known:
        return known
    guessed = mimetypes.guess_type(path.name)[0]
    return guessed or "application/octet-stream"


def _inside(remainder: str) -> str | None:
    """A mount-relative path with every escape removed — or None when the request tried one.

    The mount's directory is the ceiling: `..` is dropped rather than followed, so no spelling of a
    path can reach outside the tree the operator named.
    """
    parts: list[str] = []
    for piece in remainder.split("/"):
        if piece in ("", "."):
            continue
        if piece == "..":
            return None
        parts.append(piece)
    return "/".join(parts)


async def _serve_file(path: Path, status: int = 200) -> web.Response:
    payload = await asyncio.to_thread(path.read_bytes)
    return web.Response(
        status=status,
        body=payload,
        content_type=_content_type(path),
    )


def _split_type(content_type: str) -> tuple[str, str | None]:
    """`"text/plain; charset=utf-8"` → `("text/plain", "utf-8")`.

    aiohttp refuses a charset inside the type argument — one header, two parameters, and it owns
    the spelling. The `Response` dataclass keeps the old single-string shape so a route can still
    say `text/html; charset=utf-8`.
    """
    kind, _, rest = content_type.partition(";")
    charset = None
    for part in rest.split(";"):
        key, _, value = part.strip().partition("=")
        if key.lower() == "charset" and value:
            charset = value.strip().strip('"')
    return kind.strip(), charset


def _response(answered: Response) -> web.Response:
    payload = answered.body.encode("utf-8") if isinstance(answered.body, str) else answered.body
    kind, charset = _split_type(answered.content_type)
    return web.Response(status=answered.status, body=payload, content_type=kind, charset=charset)


def build_application(
    app: Any,
    mounts: dict[str, Path],
) -> web.Application:
    """One aiohttp application for a mount table, with the app's own routes in front of it."""

    application = web.Application()
    application[MOUNTS_KEY] = mounts
    application[APP_KEY] = app

    async def prepare(request: web.Request, response: web.StreamResponse) -> None:
        # A rebuilt page must never need a hard refresh: every response revalidates.
        response.headers["Cache-Control"] = NO_CACHE

    application.on_response_prepare.append(prepare)

    async def serve(request: web.Request) -> web.StreamResponse:
        page = request.path
        route = (app.mounts.get(page) if app is not None else None)

        if route is CHANNEL:
            if request.headers.get("Upgrade", "").lower() != "websocket":
                return web.Response(status=426, text="this route is the websocket channel")
            return await _upgrade(app, request)

        if route is not None and not isinstance(route, (str, Path)):
            return await _route(app, route, page, request)

        if request.method not in ("GET", "HEAD"):
            # Only the app's own routes take a body; a static path answers GET/HEAD and nothing else.
            return web.Response(status=405, text="no route here takes a POST")

        if page + "/" in mounts:
            # "/static" without its slash: send the browser to the mounted root, or every relative
            # reference on that page would resolve against "/" instead.
            raise web.HTTPMovedPermanently(page + "/")

        prefix, root = _mount(mounts, page)
        if prefix is None:
            return web.Response(status=404, text="nothing mounted here")

        remainder = page[len(prefix) :] if prefix != "/" else page[1:]
        safe = _inside(remainder)
        if safe is None:
            return web.Response(status=404, text="nothing mounted here")

        target = root / safe if safe else root
        looks_like_page = not Path(safe).suffix
        if target.is_dir() or (looks_like_page and not target.is_file()):
            index = root / "index.html"
            if not index.is_file():
                return web.Response(status=404, text="nothing mounted here")
            return await _serve_file(index)
        if not target.is_file():
            # A missing module must never come back as HTML, or the browser fails unreadably.
            return web.Response(status=404, text="not found")
        return await _serve_file(target)

    application.router.add_route("*", "/{tail:.*}", serve)
    return application


async def _route(app: Any, route: Any, page: str, request: web.Request) -> web.Response:
    """The app's own callable route: a `Request` in, a `Response` / pair / body out."""
    length = request.content_length or 0
    facts = Request(
        method=request.method,
        path=page,
        query={key: list(values) for key, values in request.query.items()},
        headers={key.lower(): value for key, value in request.headers.items()},
        peer=request.remote,
        body=await request.read() if length else b"",
    )
    try:
        answered = route(facts)
        if asyncio.iscoroutine(answered):
            answered = await answered
    except Exception as bad:  # a route's defect is the route's: answer it, keep serving
        print(f"[http] route {page!r} raised: {bad!r}", flush=True)
        return web.Response(status=500, text="the route raised")
    return _response(as_response(answered))


async def _upgrade(app: Any, request: web.Request) -> web.StreamResponse:
    """The connection stops being HTTP here: the app reads frames until it closes."""
    from .channel import WsChannel


    ws = web.WebSocketResponse()
    await ws.prepare(request)
    await app.handle(WsChannel(ws))
    return ws


def _mount(mounts: dict[str, Path], page: str) -> tuple[str | None, Path | None]:
    """(prefix, directory) with the longest matching prefix winning — or (None, None)."""
    for prefix in sorted(mounts, key=len, reverse=True):
        if page.startswith(prefix):
            return prefix, mounts[prefix]
    return None, None


class Server:
    """A bound server with the blocking shape its callers already speak.

    `http.server`'s interface is what the gates, `tools/cdp.py`, `tools/serve.py` and the packaging
    tests hold: `server_address`, `serve_forever()`, `shutdown()`. The transport underneath is
    aiohttp on a loop of its own thread, so those callers do not learn that anything moved.
    """

    def __init__(self, application: web.Application, host: str, port: int) -> None:
        self._web = application
        self.app = application[APP_KEY]
        self.mounts = application[MOUNTS_KEY]
        self._stopped = threading.Event()
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, name="reflux-loop", daemon=True)
        self._thread.start()
        self._runner: web.AppRunner | None = None
        self.server_address = self._call(self._start(host, port))

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """The loop this server runs on — what a watchdog task needs to exist on."""
        return self._loop

    # --- the blocking interface ---------------------------------------------------------

    def serve_forever(self) -> None:
        """Block until `shutdown()` — the loop itself has been running since construction."""
        self._stopped.wait()

    def shutdown(self) -> None:
        """Stop the site, close the loop and let the thread go. Safe to call twice."""
        if self._stopped.is_set():
            return
        try:
            if self.app is not None:
                # Hooks and the shared client first (the loop is still running), then the app's own
                # work — the watchdog is a task on this loop, and ending it keeps the loop from
                # being closed under a sleeping task.
                try:
                    self._call(self._halt(), timeout=30.0)
                except Exception:
                    pass
                self.app.stop()
            if self._runner is not None:
                self._call(self._runner.cleanup())
        finally:
            self._stopped.set()
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=5)
            if not self._thread.is_alive():
                try:
                    self._loop.close()  # the loop was ours; leaving it open leaks a file descriptor
                except RuntimeError:  # already closed, or closed from under us
                    pass

    def server_close(self) -> None:
        self.shutdown()

    def close(self) -> None:
        self.shutdown()

    # --- inside the loop ---------------------------------------------------------------

    def _call(self, coro: Any, timeout: float = 10.0) -> Any:
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    async def _boot(self) -> None:
        """What a deployment builds once, on the loop, before the first connection (ADR 0002 §7)."""
        app = self.app
        if app is None:
            return
        app.http = aiohttp.ClientSession()
        for hook in list(app._startup):
            await maybe(hook)

    async def _halt(self) -> None:
        """...and what it closes, in reverse: hooks first (they may still use the session)."""
        app = self.app
        if app is None:
            return
        for hook in reversed(list(app._shutdown)):
            try:
                await maybe(hook)
            except Exception:  # a deployment's defect stays a log line; the shutdown goes on
                app.dests.log.append(f"a shutdown hook raised:\n{traceback.format_exc()}")
        session, app.http = app.http, None
        if session is not None:
            await session.close()

    async def _start(self, host: str, port: int) -> tuple[str, int]:
        await self._boot()
        self._runner = web.AppRunner(self._web, access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, host, port)
        await site.start()
        assert self._runner.addresses, "aiohttp did not report a bound address"
        bound_host, bound_port = self._runner.addresses[0][:2]
        return str(bound_host), int(bound_port)


def make_server(
    root: str | Path | None = None,
    port: int = 8000,
    host: str = "127.0.0.1",
    app=None,
    *,
    mounts: dict[str, str | Path] | None = None,
) -> Server:
    """Return a bound (not yet serving) server for `root`, or for a table of mounts.

    `port=0` picks a free port; read it back from ``server.server_address[1]``. Passing `app`
    attaches the channel at its route (it needs only ``await handle(channel)``).

    `mounts` maps a URL prefix to a directory — ``{"/": page, "/static/": assets}`` serves the page
    and its assets from one origin. Prefixes are matched longest first; every mount needs its own
    `index.html`.
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
    application = build_application(app, table)
    return Server(application, host, port)