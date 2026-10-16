"""The producer: an app is the shell, the channel, the registry of event names, and the pages.

    app = App()

    @route("/blog/{slug}", title="文章")
    def post(session, match): ...

    @app.events.register("name.change")
    def name_changed(session, frame):
        session.draw(ops.patch("/slots/echo", frame["data"]["value"]))

    app.serve(port=8000)

The shell speaks first. Its ``reflux:hello`` carries the path it stands on (and, from T7, the
previous session's token), and every later page request is ``reflux:nav`` — a link click or the
back button. Both go down the same road: the path lands on the session, one frame comes back, so
the client never sees a wrong tree first and a correction second. Every other uplink goes to the
handler registered for its name.

A page is a node, or the ops of that turn (which is how a view also seeds the slots it reads). By
default the route table answers; an app with a single page sets `app.page` instead of declaring
routes. Sessions hold their path and where their frames go — not the interface's state, which
lives in the shell. A session is a small record; a hundred sessions are a hundred small records.
"""

from __future__ import annotations

import json
import secrets
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Iterator

from . import ops, ui
from .channel import Channel, ChannelClosed
from .events import Registry
from .node import Node
from .routes import DEFAULT, Routes
from .server import make_server
from .tables_generated import RESERVED_PREFIX

SHELL_ROOT = Path(__file__).resolve().parent.parent / "shell"


def not_found(path: str) -> Node:
    """What the framework answers with when nothing matched and nothing catches all.

    A missing path is not the app's fault, and a blank page is not an answer. An app that wants its
    own 404 registers a `{rest:path}` route: that is an ordinary match, and it wins like any other.
    """
    return ui.stack(
        ui.heading("404", level=1),
        ui.text(f"没有注册 {path} 这个地址", tone="muted"),
        gap="md",
    )


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
    """A reflux producer: the static shell, the ``/ws`` channel, the registry, and the pages."""

    def __init__(self, root: str | Path | None = None, routes: Routes | None = None) -> None:
        self.root = Path(root) if root is not None else SHELL_ROOT
        self.events = Registry()
        self.routes: Routes = routes if routes is not None else DEFAULT
        # page(session, path) -> a node, or the ops of this turn; left None the route table answers
        # (which is the shape of a routed app; one page and no routes sets this instead).
        self.page: Callable[[Session, str], Any] | None = None
        self.sessions: list[Session] = []
        self.log: list[tuple[str, Any]] = []  # every frame in and out, in order
        self.events.builtin(f"{RESERVED_PREFIX}hello", self._on_hello)
        self.events.builtin(f"{RESERVED_PREFIX}nav", self._on_nav)

    # --- the framework's own protocol -----------------------------------------------------

    def _on_hello(self, session: Session, frame: dict) -> None:
        data = frame.get("data")
        if isinstance(data, dict):
            session.path = data.get("path") or "/"
            session.token = data.get("token")
        self.draw_page(session)

    def _on_nav(self, session: Session, frame: dict) -> None:
        """The shell asked for another path: a link click, or back/forward."""
        data = frame.get("data")
        session.path = (data.get("path") if isinstance(data, dict) else None) or "/"
        self.draw_page(session)

    def draw_page(self, session: Session) -> None:
        """One frame for the session's current path: a create, or the ops the app gave for it.

        An app that declares neither a page nor any route draws nothing at all — that is the shell
        served by hand (`reflux.demo`) and the gates that drive the store themselves; the shell
        keeps whatever it has.
        """
        page = self.page
        if page is None and len(self.routes) == 0:
            return
        if page is not None:
            drawn = page(session, session.path)
        else:
            match = self.routes.match(session.path)
            drawn = not_found(session.path) if match is None else match.resolve(session)
        session.draw(*(drawn if isinstance(drawn, list) else [ops.create(drawn)]))

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