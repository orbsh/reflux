"""The producer: an app is the shell, the channel, and the registry of event names.

    app = App()

    @app.events.register("name.change")
    def name_changed(session, frame):
        session.draw(ops.patch("/slots/echo", frame["data"]["value"]))

    app.view = page            # a node, or the ops of the session's first frame
    app.serve(port=8000)

The shell speaks first. Its ``reflux:hello`` carries the path it stands on (and, from T7, the
previous session's token); the app answers with the session's first frame, so the client never
sees a wrong tree first and a correction second. Every later uplink goes to the handler
registered for its name.

Sessions hold their path and where their frames go — not the interface's state, which lives in
the shell. A session is a small record; a hundred sessions are a hundred small records.
"""

from __future__ import annotations

import json
import secrets
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Iterator

from . import ops
from .channel import Channel, ChannelClosed
from .events import Registry
from .server import make_server
from .tables_generated import RESERVED_PREFIX

SHELL_ROOT = Path(__file__).resolve().parent.parent / "shell"


class Session:
    """One connection: the path it stands on, and where its frames go."""

    def __init__(self, id: str, channel: Channel, record: Callable[[str, Any], None]) -> None:
        self.id = id
        self.channel = channel
        self.path = "/"
        self.token = None
        self.sent = 0
        self.draws = 0
        self._record = record

    def send(self, frame: dict) -> None:
        """One frame out. Ordering is the caller's, and the channel is the caller's too."""
        self.channel.send(json.dumps(frame, ensure_ascii=False))
        self.sent += 1
        self._record("send", frame)

    def draw(self, *operations: dict) -> None:
        """Send a batch of operations as one turn (one `draw` frame)."""
        self.draws += 1
        self.send(ops.draw(*operations))


class App:
    """A reflux producer: the static shell, the ``/ws`` channel, and the event registry."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else SHELL_ROOT
        self.events = Registry()
        # view(session) -> a node, or the ops of the session's first frame (a node is shorthand
        # for one `create`; ops are how a view also seeds the slots it reads).
        self.view: Callable[[Session], Any] | None = None
        self.sessions: list[Session] = []
        self.log: list[tuple[str, Any]] = []  # every frame in and out, in order
        self.events.builtin(f"{RESERVED_PREFIX}hello", self._on_hello)

    # --- the framework's own protocol -----------------------------------------------------

    def _on_hello(self, session: Session, frame: dict) -> None:
        data = frame.get("data")
        if isinstance(data, dict):
            session.path = data.get("path") or "/"
            session.token = data.get("token")
        if self.view is not None:
            session.draw(*self._first_frame(session))

    def _first_frame(self, session: Session) -> list[dict]:
        view = self.view
        assert view is not None
        frame = view(session)
        return frame if isinstance(frame, list) else [ops.create(frame)]

    # --- serving --------------------------------------------------------------------------

    def make_server(self, port: int = 0, host: str = "127.0.0.1") -> ThreadingHTTPServer:
        return make_server(self.root, port, host, app=self)

    def serve(self, port: int = 8000, host: str = "127.0.0.1") -> ThreadingHTTPServer:
        """Start serving and return the bound server (call ``serve_forever`` to block)."""
        server = self.make_server(port, host)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server

    def serve_forever(self, port: int = 8000, host: str = "127.0.0.1") -> None:
        server = self.make_server(port, host)
        address, bound = server.server_address[0], server.server_address[1]
        print(f"[reflux] serving {self.root} on http://{address}:{bound}/  (ws {address}:{bound}/ws)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()

    # --- one connection -------------------------------------------------------------------

    def handle(self, channel: Channel) -> None:
        """Read this connection's frames until it goes away."""
        session = Session(secrets.token_hex(4), channel, self._record)
        self.sessions.append(session)
        try:
            for raw in channel:
                try:
                    frame = json.loads(raw)
                except ValueError:
                    self.events.refused += 1
                    self.events.log.append(f"not JSON from {session.id}: {raw[:200]!r}")
                    continue
                self._record("recv", frame)
                self.events.dispatch(session, frame)
        except ChannelClosed as exc:
            self.events.log.append(f"session {session.id} closed: {exc}")
        finally:
            if session in self.sessions:
                self.sessions.remove(session)

    def _record(self, direction: str, frame: Any) -> None:
        self.log.append((direction, frame))