"""The producer: an app is the pages it serves, the channel, the registry of event names, and the
routing.

    app = App()

    @route("/blog/{slug}", title="文章")
    def post(session, match): ...

    @app.events.register("name.change")
    def name_changed(session, frame):
        session.draw(wire.set("echo", b.text(frame["data"])))

    app.serve(port=8000)

The page speaks first. Its ``reflux:hello`` carries the path it stands on, and every later page
request is ``reflux:nav`` — back and forward, the only navigation this wire has. Both go down the
same road: the path lands on the session, one frame comes back, so the client never sees a wrong
tree first and a correction second. Every other uplink goes to the handler registered for its name.

A page is a node, or the ops of that turn (which is how a view also seeds the slots it reads). By
default the route table answers; an app with a single page sets `app.page` instead of declaring
routes. Frames are built by `wire` — accrete's eight actions, the renderer's own vocabulary. There
is no second dialect and no translation layer: everything that leaves here is checked at
`Session.send` and reaches one renderer.

A session is one connection — created when it opens, reclaimed when it closes or when it stops
answering. Nothing crosses connections: the socket is the state, and a refresh is a new session
holding nothing but the path its hello carried. Identity, when a deployment needs it, arrives as
an ordinary event on the live socket (`login`), not as a credential checked before it. Sessions
hold their path and where their frames go — not the interface's state, which lives in the page
tree; a hundred sessions are a hundred small records.

Frames queue per session and one writer thread drains each queue, so a client that stopped reading
blocks its own writer and nobody else's.
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from . import ingest, wire
from .channel import JUDGED_DEAD, Channel, ChannelClosed
from .events import Registry
from .protocol import RESERVED_PREFIX
from .routes import DEFAULT, Routes
from .sdk import builders as b
from .sdk.types import Accrete
from .server import make_server

PAGE_ROOT = Path(__file__).resolve().parent.parent / "www"
# The page's assets are addressed from the origin root, so a deep link cannot drag its own
# references into a subdirectory.
STATIC_PREFIX = "/static/"


def not_found(path: str) -> Accrete:
    """What the framework answers with when nothing matched and nothing catches all.

    A missing path is not the app's fault, and a blank page is not an answer. An app that wants its
    own 404 registers a `{rest:path}` route: that is an ordinary match, and it wins like any other.
    """
    return b.case(
        b.text("404", variant="heading-1"),
        b.text(f"没有注册 {path} 这个地址", variant="muted"),
    )


class Session:
    """One connection: the path it stands on, and where its frames go.

    Frames *queue* here instead of being written inline: a client that stopped reading must not be
    able to hold the thread that produced a frame (that may be the app's own handler, another
    session's, or a gate). The queue is bounded at enqueue — the only point that sees every frame a
    slow client misses — and the writer thread (one per session, in `App._pump`) is what blocks.
    """

    def __init__(
        self,
        id: str,
        channel: Channel,
        record: Callable[[str, Any], None],
        stats: dict[str, int],
        outbox: int = 256,
        note: Callable[[str], None] | None = None,
    ) -> None:
        self.id = id
        self.channel = channel
        self.path = "/"
        self.sent = 0
        self.draws = 0
        self.capacity = outbox
        self.outbox: list[dict] = []  # waiting for the writer thread, oldest first
        self.stale = False  # frames were shed: the client has a hole (a resync repairs it)
        self._record = record
        self._stats = stats
        self._note = note or (lambda line: None)
        self._wake = threading.Event()

    def send(self, frame: dict) -> None:
        """Queue one frame out. The writer writes it; nobody blocks on the socket here.

        Every outbound frame passes this one door, so this is where the ingest boundary stands:
        a frame that contradicts the wire is refused **whole**, counted, logged with this session
        and its path — and the session keeps going. A producer's defect is not the session's, and
        it must not become the client's (the renderer would drop the defect silently).

        Over capacity the *middle* goes: the first frame (whatever established the tree) and the
        newest state are the two ends a stale client can still use, and the resync replaces the rest.
        """
        try:
            ingest.check_frame(frame)
        except ingest.Refused as bad:
            self._refuse(str(bad))
            return
        if len(self.outbox) >= self.capacity:
            del self.outbox[1]
            self.stale = True
            self._stats["shed"] += 1
        self.outbox.append(frame)
        self.sent += 1
        self._record("send", frame)
        self._wake.set()

    def _refuse(self, reason: str) -> None:
        self._stats["refused"] += 1
        self._note(f"refused frame for {self.id} on {self.path}: {reason}")

    def await_frames(self, timeout: float = 0.5) -> None:
        """Block until a frame is queued — or the timeout, so a live session stays checked."""
        self._wake.wait(timeout)
        self._wake.clear()

    def draw(self, *operations: dict) -> None:
        """Send a batch of operations as one turn (one `draw` frame)."""
        self.draws += 1
        self.send(wire.draw(self.id, *operations))


class App:
    """A reflux producer: the page tree, the ``/ws`` channel, the registry, and the pages."""

    def __init__(
        self,
        root: str | Path | None = None,
        routes: Routes | None = None,
        *,
        heartbeat: float = 10.0,
        dead_after: float = 30.0,
        outbox: int = 256,
    ) -> None:
        # One page tree, served at the origin root; its assets come from `root/static` under
        # `/static/` when that directory exists (a produced site may have none).
        self.root = Path(root) if root is not None else PAGE_ROOT
        self.events = Registry()
        self.routes: Routes = routes if routes is not None else DEFAULT
        # page(session, path) -> a node, or the ops of this turn; left None the route table answers
        # (which is the shape of a routed app; one page and no routes sets this instead).
        self.page: Callable[[Session, str], Any] | None = None
        # Live sessions, keyed by the channel itself: reclaiming one is a matter of identity, so
        # nothing can remove a session that is not its own.
        self.sessions: dict[Any, Session] = {}
        self.stats = {
            "issued": 0,
            "reclaimed": 0,
            "dead": 0,
            "shed": 0,
            "resync": 0,
            "refused": 0,  # frames the ingest boundary refused, in either direction
        }
        self.heartbeat = heartbeat
        self.dead_after = dead_after
        self.outbox = outbox  # frames a session may queue before the middle is shed
        self.log: list[tuple[str, Any]] = []  # every frame in and out, in order
        self._stop = threading.Event()
        self._watchdog: threading.Thread | None = None
        self.events.builtin(f"{RESERVED_PREFIX}hello", self._on_hello)
        self.events.builtin(f"{RESERVED_PREFIX}nav", self._on_nav)

    # --- the framework's own protocol -----------------------------------------------------

    def _on_hello(self, session: Session, frame: dict) -> None:
        data = frame.get("data")
        if isinstance(data, dict):
            session.path = data.get("path") or "/"
        self.draw_page(session)

    def _on_nav(self, session: Session, frame: dict) -> None:
        """The page asked for another path — back or forward: the only navigation this wire has."""
        data = frame.get("data")
        session.path = (data.get("path") if isinstance(data, dict) else None) or "/"
        self.draw_page(session)

    def draw_page(self, session: Session) -> None:
        """One frame for the session's current path: a create, or the ops the app gave for it.

        An app that declares neither a page nor any route draws nothing at all — that is the gates
        that drive the plane themselves; the page keeps whatever it has.
        """
        page = self.page
        if page is None and len(self.routes) == 0:
            return
        if page is not None:
            drawn = page(session, session.path)
        else:
            match = self.routes.match(session.path)
            drawn = not_found(session.path) if match is None else match.resolve(session)
        session.draw(*(drawn if isinstance(drawn, list) else [wire.create(drawn)]))

    # --- the session table -----------------------------------------------------------------

    def live(self) -> list[Session]:
        """The sessions in the table right now, as a snapshot list.

        The table itself is identity-keyed — a session leaves it by identity, never by name — so
        anything that only wants to *look* asks for this instead of reaching into the container's
        shape (a gate, a health endpoint, a shutdown that closes what is open).
        """
        return list(self.sessions.values())

    def watch(self) -> None:
        """One pass over the table: ping the live sessions, reclaim the ones gone quiet.

        A session is judged by its channel's ``last_seen`` — every byte read from the peer counts,
        so a client that vanished without a FIN (still connected, still deaf) falls to the same rule
        as one that closed: tell it, shut its socket down so its reader thread can end, drop it.
        Without that shutdown the connection thread would sit in ``read`` forever.
        """
        now = time.monotonic()
        for channel, session in list(self.sessions.items()):
            if now - channel.last_seen < self.dead_after:
                channel.ping()
                continue
            # Take it out before closing it: one removal, one accounting. Otherwise the reader
            # thread (woken by the shutdown below) could get there first and the same session
            # would be counted twice — as reclaimed *and* as dead.
            if self.sessions.pop(channel, None) is None:
                continue
            channel.close(JUDGED_DEAD)
            channel.abort()
            self.stats["dead"] += 1
            self.events.log.append(f"session {session.id} judged dead ({self.dead_after}s quiet)")

    def start_watchdog(self) -> None:
        """Start the thread that ticks ``watch()`` — one per server, so every server reclaims."""
        if self._watchdog is not None:
            return

        def tick() -> None:
            while not self._stop.wait(self.heartbeat):
                self.watch()

        self._watchdog = threading.Thread(target=tick, name="reflux-watchdog", daemon=True)
        self._watchdog.start()

    def stop(self) -> None:
        """End the watchdog (the gates and tests call this on the way out)."""
        self._stop.set()
        self._watchdog = None

    # --- serving --------------------------------------------------------------------------

    def make_server(self, port: int = 0, host: str = "127.0.0.1") -> ThreadingHTTPServer:
        mounts: dict[str, str | Path] = {"/": self.root}
        static = self.root / "static"
        if static.is_dir():
            mounts[STATIC_PREFIX] = static
        server = make_server(self.root, port, host, app=self, mounts=mounts)
        self.start_watchdog()
        return server

    def serve(self, port: int = 8000, host: str = "127.0.0.1") -> ThreadingHTTPServer:
        """Start serving and return the bound server (call ``serve_forever`` to block)."""
        server = self.make_server(port, host)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server

    def serve_forever(self, port: int = 8000, host: str = "127.0.0.1") -> None:
        server = self.make_server(port, host)
        address, bound = server.server_address[0], server.server_address[1]
        print(
            f"[reflux] serving {self.root} on http://{address}:{bound}/  (ws {address}:{bound}/ws)",
            flush=True,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
            server.server_close()

    # --- one connection -------------------------------------------------------------------

    def handle(self, channel: Channel) -> None:
        """Read this connection's frames until it goes away: the session lives and dies with it."""
        session = Session(
            secrets.token_hex(4), channel, self._record, self.stats, self.outbox, self.events.log.append
        )
        self.sessions[channel] = session
        self.stats["issued"] += 1
        # Writing is a thread of its own, so nothing that produces a frame can be held by a client
        # that stopped reading (this reader thread included: a slow client must not be able to stall
        # the very thread that would drain it).
        threading.Thread(target=self._pump, args=(session,), name="reflux-writer", daemon=True).start()
        try:
            for raw in channel:
                try:
                    frame = json.loads(raw)
                except ValueError:
                    self.events.refused += 1
                    self.events.log.append(f"not JSON from {session.id}: {raw[:200]!r}")
                    continue
                self._record("recv", frame)
                try:
                    ingest.check_uplink(frame)
                except ingest.Refused as bad:
                    # The registry never sees it: a frame that is not shaped like an uplink frame
                    # is refused before anything can dispatch on it. The session survives.
                    self.stats["refused"] += 1
                    self.events.log.append(
                        f"refused uplink from {session.id} on {session.path}: {bad}"
                    )
                    continue
                self.events.dispatch(session, frame)
        except ChannelClosed as exc:
            self.events.log.append(f"session {session.id} closed: {exc}")
        finally:
            # Identity, not id: a session the watchdog already reclaimed is not this thread's to
            # count, and no thread can remove a session that is not its own.
            if self.sessions.pop(channel, None) is not None:
                self.stats["reclaimed"] += 1
                self.events.log.append(f"session {session.id} reclaimed")

    def _pump(self, session: Session) -> None:
        """Write one session's frames until it is no longer live.

        One thread per session, on purpose: writing is the only step that can block on a client, so
        a slow client blocks *its own* writer and nobody else's. The loop ends when the session
        leaves the table — the reader thread removes it on close, the watchdog on a dead peer.
        """
        while self.sessions.get(session.channel) is session:
            session.await_frames()
            self.flush_session(session)

    def flush_session(self, session: Session) -> None:
        """Write what this session has waiting, then repair it if frames were shed.

        The repair only happens when the queue is *empty*: the client is reading again by then, so a
        single fresh `create` for its current path goes out inline — a resync is one frame, not a
        replay of everything the client missed.
        """
        while session.outbox:
            if not self._write(session.channel, session.outbox.pop(0)):
                return
        if session.stale:
            session.stale = False
            self.draw_page(session)
            frames, session.outbox = session.outbox, []
            if all(self._write(session.channel, frame) for frame in frames):
                self.stats["resync"] += 1

    def _record(self, direction: str, frame: Any) -> None:
        self.log.append((direction, frame))

    def _write(self, channel: Channel, frame: dict) -> bool:
        """One frame onto the socket. False when the client cannot take it — then it is its own."""
        try:
            channel.send(json.dumps(frame, ensure_ascii=False))
            return True
        except (ChannelClosed, OSError, ValueError) as exc:
            self.events.log.append(f"write failed: {exc}")
            return False