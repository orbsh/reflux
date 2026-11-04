"""The producer: an app is the pages it serves, the channel, the registry of event names, and the
routing.

    app = App()

    @route("/blog/{slug}", title="文章")
    def post(device, match): ...

    @app.dests.register("name.change")
    def name_changed(device, frame):
        device.emit(wire.set("echo", b.text(frame["data"])))

    app.serve(port=8000)

The page speaks first. Its ``reflux:hello`` carries the location it stands on — path and query
string — and every later page request is ``reflux:nav`` (back and forward, the only navigation this
wire has), carrying the same two. Both land on the device, one frame comes back, so the client
never sees a wrong tree first and a correction second. Every other uplink goes to the handler
registered for its name.

Three names are the *host's* rather than the wire's, and an application registers them like any
other: ``connect`` (the hello landed), ``location`` (the client navigated) and ``disconnect`` (the
device ended). They have no uplink address — a client cannot fake its own connect — so the frame
boundary refuses them and `dests.announce` is how they are raised.

A page is a node, or the ops of that turn (which is how a view also seeds the slots it reads). By
default the route table answers; an app with a single page sets `app.page` instead of declaring
routes. An app with a **shell** — a frame around every page, its navigation and its header — sets
`App(shell=…)` and puts a reader of the `routes` slot where pages belong: the first frame then
carries `create(shell)` plus the page in that slot, and a later page turn replaces only the slot.
No shell, no routes slot: the page replaces the layout root (the single-page-app case).

Frames are built by `wire` — accrete's eight actions, the renderer's own vocabulary. There is no
second dialect and no translation layer: everything that leaves here is checked at `Device.send`
and reaches one renderer.

A device is one connection — created when it opens, reclaimed when it closes or when it stops
answering. Nothing crosses connections: the socket is the state, and a refresh is a new device
holding nothing but the location its hello carried. One user may hold several devices, and whether
they share anything is the business's logic: the framework gives each connection a `data` bag and
never reads it. Identity, when a deployment needs it, arrives as an ordinary event on the live
socket (`login`), not as a credential checked before it. Devices hold their location, that bag, and
where their frames go — not the interface's state, which lives in the page tree; a hundred devices
are a hundred small records.

The HTTP side is a mount table with the channel in it: `App.mounts` starts as `{"/ws": CHANNEL}`, so
the socket is a route like any other. `@app.mount("/health")` (or `app.mount("/health", handler)`) adds the
app's own paths — a `Request` in, a `Response` out — and `app.mount("/socket", CHANNEL)` moves the
channel.

Frames queue per device and one writer thread drains each queue, so a client that stopped reading
blocks its own writer and nobody else's.
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from dataclasses import dataclass, field
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs

from . import ingest, wire
from .channel import EVICTED, JUDGED_DEAD, WS_PATH, Channel, ChannelClosed
from .dests import Registry
from .protocol import RESERVED_PREFIX, ROUTES_SLOT
from .routes import DEFAULT, Match, Routes
from .sdk import builders as b
from .sdk import markers
from .sdk.markers import PAGE_ID
from .sdk.types import Accrete
from .slots import Slot, Slots
from .server import CHANNEL, make_server

# "no handler was passed" — apart from `None`, which means the channel (a route that answers an
# upgrade instead of a request). The difference is what lets `mount("/x")` be a decorator.
_UNSET = object()

# The page tree: `reflux/www` when reflux came from a wheel (the build copies it in, renderer bundle
# and all), `www/` at the repository root in a checkout or an editable install. Same files either way.
PAGE_ROOT = Path(__file__).resolve().parent / "www"
if not PAGE_ROOT.is_dir():
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


def query_of(raw: Any) -> dict[str, list[str]]:
    """A query string as a mapping of its repeated values, or {} when there is nothing to read.

    The client sends `location.search` as it stands (`?a=1&b=2`, or `a=1` without the `?`), so the
    leading `?` is optional here. Blank values are kept: `?q=` and no `q` at all are different
    questions, and only the app can say which one it meant.
    """
    if isinstance(raw, str):
        return parse_qs(raw[1:] if raw.startswith("?") else raw, keep_blank_values=True)
    return {}


def split_location(url: str) -> tuple[str, dict[str, list[str]]]:
    """`"/chat?tag=a"` as a path and a query — what `hello`/`nav` carry, arriving as one string."""
    path, _, search = url.partition("?")
    return (path or "/"), query_of(search)


def location_of(frame: Any) -> tuple[str, dict[str, list[str]]]:
    """The location a `hello` or a `nav` carried: its path and its query, both total."""
    data = frame.get("data") if isinstance(frame, dict) else None
    if not isinstance(data, dict):
        return "/", {}
    path = data.get("path")
    return (path if isinstance(path, str) and path else "/"), query_of(data.get("query"))


def into_routes(operations: list[dict]) -> list[dict]:
    """A page's own operations, with its structure written into the `routes` slot instead of the root.

    A page in shell mode owes a structure — a node (which `Device.draw` wrapped in `create`) or a
    `create` of its own. That single operation becomes `set(routes, …)`; everything else (the slot
    seeds a view sends along) passes through in order, so "structure first, data after" still reads
    the same way in the frame. No structure at all is a producer defect and says so here: the slot
    would keep the previous page and nothing would look wrong until someone clicked.
    """
    out: list[dict] = []
    landed = False
    for op in operations:
        if not landed and op.get("action") == "create":
            out.append(wire.set(ROUTES_SLOT, op.get("data")))
            landed = True
            continue
        out.append(op)
    if not landed:
        raise ValueError(
            "a page in shell mode must produce its structure (a node, or a create operation): "
            f"nothing would reach the {ROUTES_SLOT!r} slot"
        )
    return out


class Device:
    """One connection: the location it stands on, what the business hung on it, and where its frames go.

    A device is a connection, not a user: one user may hold several, and whether two of them share
    anything is the business's logic, not the framework's. What the framework keeps here is only what
    the connection itself needs — where it stands (`path`, `query`), how far the view got
    (`shell_drawn`), and the outbox.

    Frames *queue* here instead of being written inline: a client that stopped reading must not be
    able to hold the thread that produced a frame (that may be the app's own handler, another
    device's, or a gate). The queue is bounded at enqueue — the only point that sees every frame a
    slow client misses — and the writer thread (one per device, in `App._pump`) is what blocks.
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
        # Its app, for the move that has to draw a page (`go`). Set by `App.handle`, which is the
        # only place devices are made.
        self.app: App | None = None
        self.path = "/"
        # What the address bar carried after the path: `?q=1&tag=a&tag=b` is {"q": ["1"], "tag": ["a","b"]}.
        self.query: dict[str, list[str]] = {}
        # What the business hangs on this connection: an identity, a name, a permission, anything.
        # The framework never reads it, never validates it and never clears it — when the connection
        # goes, it goes with it. Two devices sharing a user's state is the app's own bookkeeping.
        self.data: dict[str, Any] = {}
        self.connected = False  # the hello landed: `connect` is raised once, not per hello frame
        self.shell_drawn = False  # the shell is on the client; a page turn now only writes `routes`
        self.sent = 0
        self.emits = 0
        self.capacity = outbox
        self.outbox: list[list[dict]] = []  # waiting for the writer thread, oldest first
        self.stale = False  # frames were shed: the client has a hole (a resync repairs it)
        self._record = record
        self._stats = stats
        self._note = note or (lambda line: None)
        self._wake = threading.Event()

    def go(self, url: str) -> None:
        """Stand somewhere else and draw it — the server's own page turn.

        `device.go("/chat")` is the move a client's `reflux:nav` makes, with one difference: the
        client did not ask. The address moves first (the page is built from it), then the page is
        drawn into the slot; the browser's own address bar follows because the page carries the path
        marker. `location` is *not* raised — that event says the client navigated, and a handler
        listening for it would otherwise turn one move into two.

        A query may ride the same string: `device.go("/?filter=done")` stands on the filtered list.
        """
        self.path, self.query = split_location(url)
        self.draw()

    def draw(self) -> None:
        """Draw the page this device stands on — one frame, the app's route for its own path.

        With a shell the frame is `create(shell)` (once per connection) followed by the page written
        into the `routes` slot, so a page turn after that replaces one slot and leaves the frame
        around it alone. Without one the page replaces the layout root: the single-page-app shape.

        An app that declares neither a page hook nor any route draws nothing at all — that is the
        gates that drive the plane themselves; the page keeps whatever it has. A device with no app
        (one a test made by hand) says so instead of drawing nothing and looking healthy.
        """
        if self.app is None:
            raise RuntimeError("device.draw: this device is not attached to an app")
        self.app._draw(self)

    def send(self, frame: list[dict]) -> None:
        """Queue one frame out. The writer writes it; nobody blocks on the socket here.

        Every outbound frame passes this one door, so this is where the ingest boundary stands:
        a frame that contradicts the wire is refused **whole**, counted, logged with this device
        and its path — and the device keeps going. A producer's defect is not the device's, and
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
        """Block until a frame is queued — or the timeout, so a live device stays checked."""
        self._wake.wait(timeout)
        self._wake.clear()

    def emit(self, *operations: dict) -> None:
        """Send a batch of operations as one turn — the frame is the list itself.

        `operations` are accrete's DSL (the same `wire.set` / `wire.patch` / … the page is built
        from); `draw` is the name of the builder, `emit` is what a connection does with the result.
        """
        self.emits += 1
        self.send(wire.draw(*operations))


class _Turn:
    """The `with ctx.turn():` block: collect what is said, send it as one frame on the way out."""

    __slots__ = ("_ctx",)

    def __init__(self, ctx: Context) -> None:
        self._ctx = ctx

    def __enter__(self) -> Context:
        self._ctx._buffer = []
        return self._ctx

    def __exit__(self, *exc: object) -> None:
        buffered, self._ctx._buffer = self._ctx._buffer or [], None
        if buffered:
            self._ctx.device.emit(*buffered)


@dataclass
class Context:
    """One delivery — and the room around it: this app, the device it was addressed to, its frame.

    Handlers get `(ctx, …)`. Everything that *says* something goes through `ctx.emit(*operations)`:
    on this side of the socket there is no response to return, and a reply that is not a return is what
    makes a second device (or a thousand) addressable at all — `ctx.devices` is the snapshot of the
    room, `ctx.device_of(id)` is one of them. Nothing here returns: a page handler draws with
    `ctx.page(node)` and the app composes the frame around it; an event handler says nothing.
    """

    app: "App"
    device: "Device"
    frame: dict | None = None
    match: "Match | None" = None
    _page: Any = field(default=None, repr=False)
    _buffer: list[dict] | None = field(default=None, repr=False)

    # --- the connection this delivery came from ---
    @property
    def id(self) -> str:
        return self.device.id

    @property
    def path(self) -> str:
        return self.device.path

    @property
    def query(self) -> dict[str, list[str]]:
        return self.device.query

    @property
    def data(self) -> dict:
        """The bag the business hangs on this connection. The framework still never reads it."""
        return self.device.data

    # --- what it can say, and where ---
    @property
    def slot(self) -> Slots:
        """The slots of this delivery: `ctx.slot("chat/status")`, `ctx.slot["status"]`, `ctx.slot.status`.

        A slot is a name plus its verbs (`set`/`append`/`patch`/`remove`), each of them one frame —
        so a handler never writes `wire.set("status", …)` and never keeps the name in a constant of
        its own. Declaring a `Protocol` with the names gives the editor completion; see `slots.py`.
        """
        return Slots(app=self.app, ctx=self)


    def turn(self) -> Any:
        """One frame out of several writes: every send inside the block lands in the same frame.

        A turn is what the client sees at once — rows, a bubble, a status line — and it is cheaper to
        compose than to send. Not nestable: a block inside a block would have to decide which frame it
        belongs to, and no page has needed two.
        """
        return _Turn(self)

    def emit(self, *operations: dict) -> None:
        """Say something to the device this delivery came from: these accrete operations, one frame.

        A later frame (a broadcast, a timer's nudge) says it to `ctx.devices()` instead — same verb,
        on those devices, because saying is a device's act and not a handler's return.
        """
        if self._buffer is not None:
            self._buffer.extend(operations)
        else:
            self.device.emit(*operations)

    def devices(self) -> list["Device"]:
        """Every live device, this one included — the room a broadcast picks from."""
        return self.app.live()

    def device_of(self, id: str) -> "Device | None":
        """One device by id, for when the answer belongs to somebody else."""
        return self.app.device(id)

    # --- what it can ask of the page ---
    def page(self, *children: Any, title: str | None = None, path: str | None = None, id: str = PAGE_ID) -> None:
        """This is the page for the address this delivery is about.

        A page handler **draws**; it does not return. The framework composes the frame around the
        page (the shell once per connection, the `routes` slot after that) and sends it — which is why
        a page handler and an uplink handler have the same shape, and why neither of them can
        accidentally answer a device that is not the one in front of it.

        The page is `markers.page(...)`, built here: the address and the title are what the route
        already declared (`@app.route("/chat", title="对话")`), so a handler passes neither — only
        its content. `path=` / `title=` override them for the case where the declaration is not the
        whole story (the single-page hook, which has no route).
        """
        self._page = markers.page(
            self.match.path if path is None and self.match else (path if path is not None else self.device.path),
            title if title is not None else self._declared_title(),
            *children,
            id=id,
        )

    def _declared_title(self) -> str:
        """The title the route declared, or "" when there is no route to ask."""
        return str(self.match.route.meta.get("title", "")) if self.match else ""

    def take_page(self) -> Any:
        """The node this delivery drew, once: the framework composes frames out of it."""
        node, self._page = self._page, None
        return node

    def draw(self) -> None:
        """Redraw the page this device stands on. The app draws it; the device is where it lands."""
        self.app._draw(self.device)

    def go(self, url: str) -> None:
        """Move this device's address, then draw — the server's own page turn (`Device.go`)."""
        self.device.path, self.device.query = split_location(url)
        self.app._draw(self.device)


class App:
    """A reflux producer: the page tree, the channel route, the registry, and the pages."""

    def __init__(
        self,
        root: str | Path | None = None,
        routes: Routes | None = None,
        *,
        heartbeat: float = 10.0,
        dead_after: float = 30.0,
        outbox: int = 256,
        shell: Callable[[Device], Any] | None = None,
    ) -> None:
        # One page tree, served at the origin root; its assets come from `root/static` under
        # `/static/` when that directory exists (a produced site may have none).
        self.root = Path(root) if root is not None else PAGE_ROOT
        self.dests = Registry(self.context)
        self.declared: set[str] = set()  # every name the app has used: slots, dests, host events
        self.routes: Routes = routes if routes is not None else DEFAULT
        # page(device, path) -> a node, or the ops of that turn; left None the route table answers
        # (which is the shape of a routed app; one page and no routes sets this instead).
        self.page: Callable[[Device, str], Any] | None = None
        # shell(device) -> the frame around every page (nav, header, and a reader of ROUTES_SLOT).
        # Set it and a page turn replaces that one slot; leave it None and the page replaces the
        # layout root — the single-page-app shape.
        self.shell: Callable[[Device], Any] | None = shell
        # Live devices, keyed by the channel itself: reclaiming one is a matter of identity, so
        # nothing can remove a device that is not its own.
        self.devices: dict[Any, Device] = {}
        # The HTTP side: a path -> route table, where the channel is one route among others. The
        # default is the channel at `/ws`; `mount` moves it and adds the app's own paths.
        self.mounts: dict[str, Any] = {WS_PATH: CHANNEL}
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
        self.outbox = outbox  # frames a device may queue before the middle is shed
        self.log: list[tuple[str, Any]] = []  # every frame in and out, in order
        self._stop = threading.Event()
        self._watchdog: threading.Thread | None = None
        self.dests.builtin(f"{RESERVED_PREFIX}hello", self._on_hello)
        self.dests.builtin(f"{RESERVED_PREFIX}nav", self._on_nav)

    # --- the framework's own protocol -----------------------------------------------------

    def _on_hello(self, ctx: Context, frame: dict) -> None:
        """The client says where it stands; the first frame answers, then `connect` is raised."""
        device = ctx.device
        device.path, device.query = location_of(frame)
        self._draw(device)
        if not device.connected:
            device.connected = True
            # After the frame is queued: a handler that draws more lands on top of a page the
            # client already has, never under one it is about to lose.
            self.dests.announce("connect", device, frame)

    def _on_nav(self, ctx: Context, frame: dict) -> None:
        """The page asked for another path — back or forward: the only navigation this wire has.

        The browser already moved its address bar before this arrived, so the framework only
        re-draws and tells the app: `location` is the host's event, not a wire address.
        """
        device = ctx.device
        device.path, device.query = location_of(frame)
        self._draw(device)
        self.dests.announce(
            "location",
            device,
            {"dest": "location", "data": {"path": device.path, "query": device.query}},
        )

    def route(
        self, path: str, *, layout: Callable | None = None, **meta: Any
    ) -> Callable[[Callable], Callable]:
        """Declare a page on this app: `@app.route("/", title="首页")` above its handler.

        Sugar over `self.routes.add`. The point is where the declaration hangs: on the object the
        pages belong to, so a file reads as one app and a list of decorators, instead of a table
        built somewhere else and handed to a constructor.
        """
        declared: Callable[[Callable], Callable] = self.routes.add(path, layout=layout, **meta)
        return declared

    def on(self, name: "str | Slot", handler: Callable | None = None) -> Callable:
        """Declare a handler for one upstream dest: `@app.on(app.slot.go.chat)` above it.

        The dest is a handle from the app's table, so a page saying `dest=ctx.slot.go.chat` and the
        handler answering it are one name. A plain string is still accepted for the framework's own
        host events (`connect`, `location`, `disconnect`) — those names are the framework's, not the
        app's.

        Sugar over `self.dests.register`, the way `route` is sugar over `self.routes.add` — the verb
        you write at a handler with no page to its name. Both of the registry's shapes come through:
        `@app.on("x")` as a decorator, `app.on("x", handler)` when the table is built at runtime. The
        registry is still the table — `dests` stays public for the built-ins and for lookups.
        """
        if isinstance(name, Slot):
            name.declare()
            name = name.name
        return self.dests.register(name, handler)

    @property
    def slot(self) -> Slots:
        """The app's own table: `@app.on(app.slot.go.chat)`, `app.slot.routes`.

        The names belong to the app — a page and its handler answering the same dest are the same
        name — and a handle taken here has no delivery, so it names and declares but cannot send.
        `ctx.slot` is this same table with a device attached.
        """
        return Slots(app=self)

    def declare(self, name: str) -> None:
        """Record a name. Idempotent; `declared` is what `/status` lists."""
        self.declared.add(name)

    def context(self, device: Device, frame: dict | None = None, match: Any = None) -> Context:
        """One delivery, ready to hand a handler: this app, this device, and what came in."""
        return Context(self, device, frame, match)

    def _draw(self, device: Device) -> None:
        """One frame for the device's current location: a create, or the ops the page gave for it.

        Private on purpose: the page is the app's, the act is the device's. `device.draw()` is how
        anything else asks for this, and `Device.go` is a move plus a draw.
        """
        if self.page is None and len(self.routes) == 0:
            return
        ctx = self.context(device)
        if self.page is not None:
            self.page(ctx, device.path)
            drawn = ctx.take_page()
        else:
            match = self.routes.match(device.path)
            drawn = None
            if match is not None:
                ctx = self.context(device, match=match)
                drawn = match.resolve(ctx)
        if drawn is None:  # nothing drew for this address: the app's own 404, not a blank page
            drawn = not_found(device.path)
        operations = drawn if isinstance(drawn, list) else [wire.create(drawn)]
        if self.shell is None:
            device.emit(*operations)
            return
        frame: list[dict] = []
        if not device.shell_drawn:
            device.shell_drawn = True
            frame.append(wire.create(self.shell(ctx)))
        frame.extend(into_routes(operations))
        device.emit(*frame)

    # --- the device table -----------------------------------------------------------------

    def live(self) -> list[Device]:
        """The devices in the table right now, as a snapshot list.

        The table itself is identity-keyed — a device leaves it by identity, never by name — so
        anything that only wants to *look* asks for this instead of reaching into the container's
        shape (a gate, a health endpoint, a shutdown that closes what is open).
        """
        return list(self.devices.values())

    def device(self, id: str) -> Device | None:
        """The device with that id — the direction a handler does not have.

        A handler is *given* its device; this looks one up by id (a `connect` handler that kept the
        id, a timer, another device's handler writing to a specific peer). None when it is gone.
        """
        for device in self.devices.values():
            if device.id == id:
                return device
        return None

    def evict(
        self,
        id: str | None = None,
        *,
        where: Callable[[Device], bool] | None = None,
        reason: str = "evicted",
    ) -> int:
        """Close the devices that match, through the door a disconnect already uses.

        `id` names one, `where` takes a predicate (by whatever the app hung in `device.data`). The
        socket is closed and shut down so its reader thread ends, the device leaves the table once,
        and `disconnect` is announced with `reason` — there is no second way to remove one.
        """
        if id is None and where is None:
            raise TypeError("evict needs id= or where=: naming nothing would close every device")
        hit = [
            device
            for device in list(self.devices.values())
            if (id is None or device.id == id) and (where is None or where(device))
        ]
        for device in hit:
            if not self._gone(device, reason):
                continue
            device.channel.close(EVICTED)
            device.channel.abort()
            self.stats["reclaimed"] += 1
        return len(hit)

    def watch(self) -> None:
        """One pass over the table: ping the live devices, reclaim the ones gone quiet.

        A device is judged by its channel's ``last_seen`` — every byte read from the peer counts,
        so a client that vanished without a FIN (still connected, still deaf) falls to the same rule
        as one that closed: tell it, shut its socket down so its reader thread can end, drop it.
        Without that shutdown the connection thread would sit in ``read`` forever.
        """
        now = time.monotonic()
        for channel, device in list(self.devices.items()):
            if now - channel.last_seen < self.dead_after:
                channel.ping()
                continue
            # Take it out before closing it: one removal, one accounting. Otherwise the reader
            # thread (woken by the shutdown below) could get there first and the same device
            # would be accounted twice — as reclaimed *and* as dead.
            if not self._gone(device, "dead"):
                continue
            channel.close(JUDGED_DEAD)
            channel.abort()
            self.stats["dead"] += 1
            self.dests.log.append(f"device {device.id} judged dead ({self.dead_after}s quiet)")

    def start_watchdog(self) -> None:
        """Start the thread that ticks ``watch()`` — one per server, so every server reclaims.

        The stop flag is re-armed here: `stop()` ends a run, and serving the same app again (a gate
        that runs two phases against one app) starts a fresh one — otherwise the new watchdog would
        see the old stop flag already set and exit at its first tick.
        """
        if self._watchdog is not None:
            return
        self._stop = threading.Event()

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

    def mount(self, path: str, handler: Any = _UNSET) -> Any:
        """Put a route in the HTTP table — as a decorator, or with its handler in hand.

        The table starts as `{"/ws": CHANNEL}`, so the socket is a route like any other rather than a
        special case of the server. One method covers the four things the table holds:

            @app.mount("/status")                       # a decorator over the handler it names
            def status(request: Request) -> Response: ...

            app.mount("/health", lambda request: "ok")  # the same declaration, written flat
            app.mount("/assets/chart", path)            # a directory, served file by file
            app.mount("/socket", CHANNEL)               # the channel, put somewhere else

        A handler is a `Request` in and a `Response` / `(status, body)` / body out. A path may be
        declared once: declaring it twice raises rather than giving the second one the first one's
        address.
        """
        if handler is _UNSET:
            def declare(fn: Callable) -> Callable:
                self._put(path, fn)
                return fn

            return declare
        self._put(path, CHANNEL if handler is None else handler)
        return handler

    def _put(self, path: str, route: Any) -> None:
        """One entry, once: the table has no notion of a later declaration overriding an earlier one."""
        if path in self.mounts:
            raise ValueError(f"{path!r} is already mounted; unmount it first")
        self.mounts[path] = route

    def unmount(self, path: str) -> None:
        """Take a route out of the table — moving the channel is unmount, then mount."""
        if self.mounts.pop(path, None) is None:
            raise KeyError(f"nothing mounted at {path!r}")

    def make_server(self, port: int = 0, host: str = "127.0.0.1") -> ThreadingHTTPServer:
        mounts: dict[str, str | Path] = {"/": self.root}
        static = self.root / "static"
        if static.is_dir():
            mounts[STATIC_PREFIX] = static
        # A route may also be a directory (`app.mount("/assets/chart", path)`): those are the server's
        # mounts, served file by file, not the app's callables.
        for path, route in self.mounts.items():
            if isinstance(route, (str, Path)):
                mounts[path.rstrip("/") + "/"] = route  # a directory mount is a prefix, with the slash
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
        """Read this connection's frames until it goes away: the device lives and dies with it."""
        device = Device(
            secrets.token_hex(4), channel, self._record, self.stats, self.outbox, self.dests.log.append
        )
        device.app = self
        self.devices[channel] = device
        self.stats["issued"] += 1
        # Writing is a thread of its own, so nothing that produces a frame can be held by a client
        # that stopped reading (this reader thread included: a slow client must not be able to stall
        # the very thread that would drain it).
        threading.Thread(target=self._pump, args=(device,), name="reflux-writer", daemon=True).start()
        try:
            for raw in channel:
                try:
                    frame = json.loads(raw)
                except ValueError:
                    self.dests.refused += 1
                    self.dests.log.append(f"not JSON from {device.id}: {raw[:200]!r}")
                    continue
                self._record("recv", frame)
                try:
                    ingest.check_uplink(frame)
                except ingest.Refused as bad:
                    # The registry never sees it: a frame that is not shaped like an uplink frame
                    # is refused before anything can dispatch on it. The device survives.
                    self.stats["refused"] += 1
                    self.dests.log.append(
                        f"refused uplink from {device.id} on {device.path}: {bad}"
                    )
                    continue
                self.dests.dispatch(device, frame)
        except ChannelClosed as exc:
            self.dests.log.append(f"device {device.id} closed: {exc}")
        finally:
            # Identity, not id: a device the watchdog already reclaimed is not this thread's to
            # count, and no thread can remove a device that is not its own.
            if self._gone(device, "closed"):
                self.stats["reclaimed"] += 1
                self.dests.log.append(f"device {device.id} reclaimed")

    def _gone(self, device: Device, reason: str) -> bool:
        """Take a device out of the table once — and let the app hear that it is gone.

        The one place that removes: `disconnect` cannot fire twice (both the reader thread and the
        watchdog come here, and only the first wins) and cannot fail to fire (a device leaving the
        table is exactly the fact the event names).
        """
        if self.devices.pop(device.channel, None) is None:
            return False
        self.dests.announce(
            "disconnect", device, {"dest": "disconnect", "data": {"reason": reason}}
        )
        return True

    def _pump(self, device: Device) -> None:
        """Write one device's frames until it is no longer live.

        One thread per device, on purpose: writing is the only step that can block on a client, so
        a slow client blocks *its own* writer and nobody else's. The loop ends when the device
        leaves the table — the reader thread removes it on close, the watchdog on a dead peer.
        """
        while self.devices.get(device.channel) is device:
            device.await_frames()
            self.flush_device(device)

    def flush_device(self, device: Device) -> None:
        """Write what this device has waiting, then repair it if frames were shed.

        The repair only happens when the queue is *empty*: the client is reading again by then, so a
        single fresh frame for its current location goes out inline — a resync is one frame, not a
        replay of everything the client missed. With a shell the resync re-creates it (the stale
        client may have missed the frame that built it), so the flag is cleared first.
        """
        while device.outbox:
            if not self._write(device.channel, device.outbox.pop(0)):
                return
        if device.stale:
            device.stale = False
            device.shell_drawn = False
            self._draw(device)
            frames, device.outbox = device.outbox, []
            if all(self._write(device.channel, frame) for frame in frames):
                self.stats["resync"] += 1

    def _record(self, direction: str, frame: Any) -> None:
        self.log.append((direction, frame))

    def _write(self, channel: Channel, frame: list[dict]) -> bool:
        """One frame onto the socket. False when the client cannot take it — then it is its own."""
        try:
            channel.send(json.dumps(frame, ensure_ascii=False))
            return True
        except (ChannelClosed, OSError, ValueError) as exc:
            self.dests.log.append(f"write failed: {exc}")
            return False