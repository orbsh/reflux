"""The reference application: what a reflux app looks like, written with the SDK and `wire`.

    python3 -m examples.en.demo_app --port 8000

Four pages, a shell around them, and one page per shape an application is made of:

- `/` — **the vocabulary**, as cards. An `input` uplinks its buffer on Enter and a `text` reads the
  slot the handler writes (an echo); rows live in a slot and a `tiles` shows them, each row's remove
  button carrying its own identity up, and a row also carries cargo — its frame is `draggable`, so
  dragging it onto the landing frame uplinks `{id, tag}`, the dragged frame's own id, so the archive
  handler resolves what the gesture never could (the drag itself reports nothing: only the landing
  point does); and one `loom` carries every field it packs (`{tag: value, …}`, ADR 0032) — the
  LOGIN loom, because credentials are the framework's business: the exit is `reflux:login`, the
  app writes only `verify` and `view`, and no password is ever read here. Behind it, `vault.secret`
  is declared `auth=True`, so an anonymous click opens the login surface instead of reaching the
  handler and the same click lands once signed in (`Log out` is the way back out).
- `/about` — the second route, reached by the address bar, a deep link, back/forward, or the nav.
- `/chat` — a conversation per connection, streamed and stoppable: the backend's half (`demo_chat.py`).
- `/demo` — the walkthrough page, which is `examples/en/demo/`'s: fluxen's own story, played by a
  floating button, in four regions that each read one slot. The page is content and lives with the
  examples; this module is what an app looks like, and it imports the page the way an app imports a
  page.

**The shell** is this app's, not the framework's default: a header that says where you are and the
`routes` reader the pages are written into. It is drawn once per connection, so a page turn replaces
one slot and leaves the header alone. Its reader is `min-height: 0` on purpose — a grid item's
automatic minimum is its content, and without the zero that row would grow with the page instead of
scrolling it.

Two facts about this vocabulary shape the code, and both are measured by the gates:

- **A `button` lives inside a `loom`** (`gate_t3_next`): that is where the renderer mounts it, and
  a loom's `submit` is what a press sends (`submit=["button"]`). So "add a row", "remove a row" and
  "go to another page" are one-button looms, and the frame's `id` is the loom's own id — which is
  how a row's identity rides up and back.
- **accrete has no URL-bearing type**, so there is no anchor to click and nothing to intercept: a
  page change is the producer answering with a new structure plus the new path marker (`go.home` /
  `go.about` / `go.demo` below). The runtime mirrors that marker into the address bar.

The two markers are ordinary nodes read straight out of the DOM (`reflux:path`, `reflux:title`) by
`www/static/reflux.js`; the convention lives in `reflux.sdk.markers` (one `page()` call per page),
because the page's own shape is the runtime's contract, not an application's private habit.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from reflux import signals
from reflux.application import Context, gated
from reflux.protocol import AUTH_SLOT, LOGIN, LOGOUT, ROUTES_SLOT
from reflux.server import Request, Response
from reflux.sdk import h
from reflux.sdk.types import Accrete, JsType, Source
from reflux.site import app  # this process's site: declarations hang on it, the demo builds nothing
from reflux.slots import Slot

from . import demo_slots
from .demo_slots import GO, GO_ABOUT, GO_CHAT, GO_COUNTER, GO_DEMO, GO_HOME, GO_SETTINGS, DemoSlots, slots_of


# A card: a frame with the profile's `card` variant, its children stacked and its own height.
CARD = {"grid-auto-rows": "auto", "gap": "10px", "align-content": "start"}


def nav_loom(label: str, dest: Slot) -> Accrete:
    """A one-button loom — the vocabulary's only clickable, and the demo's way between pages.

    The press is the loom's own submit: `submit=["button"]` names the click as the timing, and the
    loom holds the exit, so the button only says "send this group" (ADR 0032 §3).
    """
    return h.loom(h.button(label), sink=dest, submit=["button"], id=f"nav-{dest.name}")


def row_node(text: str, row_id: str) -> Accrete:
    """One row: a loom (the ✕ that removes it) around a draggable frame — its cargo and its landing.

    The two ways out of a row are different mechanisms on purpose: the button is an uplink on the
    loom's id, a drag is silent until a landing point says where it went (ADR 0034: the cargo is
    the dragged subtree, and a drop reports the dragged node's own id). So the row's loom keeps
    `<row id>` — that is what `remove` addresses — and the cargo frame names itself `<row id>-cargo`,
    because one id per tree is the wire's rule and the drop has no other field to carry identity in.

    The same frame grows both ends: `draggable` makes it cargo, `accept` + `sink` make it a landing —
    so "which row was landed on" comes from the landing's own id and "which row was dragged" from the
    cargo's id, both in one drop, and a swap needs no second question to the page.

    The two frames say how the row is divided: a loom is a flex row whose items all grow, so the
    cargo takes the width (`flex: 1 1 auto`) and the ✕ keeps its own size and centres itself in the
    height it does not fill.
    """
    # `remove` is a verb on a slot, so this name is written with the subscript.
    return h.loom(
        h.frame(h.text(text), draggable={"tag": "row"}, accept={"tag": "row"},
                sink=slots("row.move"), style={"flex": "1 1 auto"}, id=f"{row_id}-cargo"),
        h.frame(h.button("Remove"),
                style={"flex": "0 0 auto", "align-self": "center"}),
        sink=slots.row["remove"],
        submit=["button"],
        id=row_id,
    )


class State:
    """What a turn leaves behind — the demo's whole business state.

    Module-level, because the handlers are module-level declarations too (`@app.on(...)`), and one
    page per connection means one object is enough: a real multi-user app would hang this on the
    device (`ctx.data`) instead, which is what the `keyed` subscription below does.
    """

    def __init__(self) -> None:
        self.echo = ""
        # Each row is `(id, text)`: identity lives in the data, and both `keyed` and the render
        # function use that one copy — never the position.
        self.rows = signals.Signal([("row-1", "First row"), ("row-2", "Second row")])
        self.next_row = 3


state = State()


@app.hooks.shell()
def shell(ctx: Context) -> Accrete:
    """The frame every page is drawn into: a header, and the `routes` reader.

    The header says where you are and carries the three nav looms; a page turn replaces only the
    slot, so the nav survives every turn. The reader is `min-height: 0` because a grid item's
    automatic minimum is its content — without it this row grows with the page and the shell's `1fr`
    is only a wish. The reader scrolls, so a page may be taller than the window.
    """
    # The page options land first: a slot write is a send, and the page's frame leaves at the end of
    # `_draw`, so a new connection's first frame already carries the user's choices (ADR 0001 §5).
    demo_settings.seed(ctx)
    return h.frame(
        h.frame(
            h.text("reflux reference app", variant="heading-3"),
            nav_loom("Demo", GO_HOME),
            nav_loom("About", GO_ABOUT),
            nav_loom("Walkthrough", GO_DEMO),
            nav_loom("Chat", GO_CHAT),
            nav_loom("Counter", GO_COUNTER),
            nav_loom("Settings", GO_SETTINGS),
            grid={"grid-template-columns": "1fr auto auto auto auto auto auto", "gap": "8px", "align-items": "center"},
            id="nav",
        ),
        h.frame(
            source=slots(ROUTES_SLOT),
            id=ROUTES_SLOT,
            style={"min-height": "0", "overflow": "auto"},
        ),
        grid={"grid-template-rows": "auto 1fr", "gap": "16px", "height": "100vh",
              "padding": "18px 24px", "box-sizing": "border-box"},
        # `width: 100%` would resolve against `#main`, which is a flex item sized by its content —
        # so a narrow page would hand the shell a narrow width and the header would shrink with it.
        # The window's own units are the way out (`main.css` prints exactly this failure).
        style={"width": "min(1240px, 100vw)", "margin": "0 auto"},
        id="shell",
    )


@app.hooks.login_request()
def demo_view(ctx, state):
    """The demo's own login surface — the `login.request` seam, with the field names its page also uses."""
    lines = [h.text("Demo sign-in", variant="heading-1")]
    if state == "refused":
        lines.append(h.text("Wrong username or password", variant="muted"))
    return h.frame(
        *lines,
        h.loom(
            h.input(tag="user", id="auth-user"),
            h.input(tag="pass", kind=JsType.password, id="auth-pass"),
            h.button("Sign in"),
            sink=slots(LOGIN),
            submit=["enter", "button"],
            id="auth-form",
        ),
    )


@app.hooks.inspect("/v1/inspect")  # this app's own declaration, over HTTP: routes, dests, slots, seams
def inspect(data):
    """The demo does not filter: `data` is the answer. A real deployment decides here who may see it."""
    return data


@app.hooks.login()
def demo_verify(ctx, credentials, mode):
    """The demo's verifier: one account, in memory, and the framework does the rest.

    This is the entire authentication a deployment writes — `mode` is `login` or `signup`, so an
    app that creates accounts decides that here. The password is checked and dropped; nothing in
    this module stores it, logs it, or draws it.

    The return is the verdict: `(True, user_id, info)` lets them in, `(False, reason)` refuses.
    `info` is the app's own (none here); the framework only hands it back as `ctx.session`.
    """
    del ctx, mode  # the demo has no roles and no second kind of account
    if credentials.get("user") == "ada" and credentials.get("pass") == "pw":
        return (True, "user-ada", None)
    return (False, "Wrong username or password")

# The app's own table, typed: `@app.on(slots.name.change)` completes, and a name that is not in
# `DemoSlots` is an error rather than a handler nothing ever sends to. `ctx.slot` is this table with
# a device attached; `slots_of(ctx)` is where a write comes from.
slots: DemoSlots = demo_slots.table(app)


@app.page("/", title="Demo")
def home_page(ctx, match):
    """The vocabulary, as cards: what a value does on its way up, and the gate in front of one.

    The page root is a flex column with no gap of its own, so the page says how it is divided: a
    title that spans both columns, the left column (an echo, a list, a drag) and the right one (the
    framework's credential verb), and a footnote that spans as well. Each card is a `frame` with the
    `card` variant, and its own gap — a loom is a flex row and would line its fields up edge to
    edge, which is a form, not a page.

    A page turn is that `return` and nothing else: the two markers the runtime reads
    (`reflux:path`, `reflux:title`) are written for you, in front of the node.

    This page is also the contrast between the two kinds of landing point. **Echo**, **add a row** and
    **secret** are closures: one request, one answer, the handler written beside the button that sends
    to it, the closure taking the event's value and holding its slots. **✕**, the **drop zone** and the
    **nav** stay names on `@app.on` — their identity is not in the page (one id per row, and the name
    belongs to the row), and a name has to exist before any page is drawn. The walkthrough's `echo` is
    the other end of it: that slot is written by two sources, the drag landing and the editor's save,
    and only a name can say "one slot, several sources".
    """
    slots = slots_of(ctx)

    def echo(value: object) -> None:
        # A loom submits the object it packed: {field: value}. A frame comes from outside, so
        # anything unrecognised becomes the empty string instead of an exception.
        text = value.get("name") if isinstance(value, dict) else None
        state.echo = text if isinstance(text, str) else ""
        slots.echo.set(h.text(state.echo))

    def add_row(value: object) -> None:
        row = (f"row-{state.next_row}", f"Row {state.next_row}")
        state.next_row += 1
        state.rows.value = state.rows.value + [row]  # no slot write here: `keyed` adds the append

    def reveal(value: object) -> None:
        # Only a signed-in click gets here: the gate answered the rest before the closure ran.
        ctx.data["may_see_secret"] = True
        slots.secret.set(h.text("Classified content"))

    # The rows are kept equal to `state.rows` by `signals.keyed`: on this connection's first draw it
    # appends every row there is, and after that it follows the signal through adds, removes and moves.
    # A slot outlives a `create` (the tree is replaced, the data planes are not), so this subscription
    # is made once — making it again on the next visit would append the same rows twice.
    if ctx.data.get("rows_keyed") is None:
        ctx.data["rows_keyed"] = signals.keyed(ctx, "rows", state.rows, row_node)
    # The same rule cuts the other way for the secret: the slot would outlive a `Log out`, so the draw
    # clears it — only when this app wrote something (`may_see_secret` is its own memory of doing so).
    if not ctx.data.get("user") and ctx.data.pop("may_see_secret", False):
        slots_of(ctx).secret.set(h.text(""))
    return (
        h.frame(
            h.frame(
                h.text("Demo", variant="heading-1"),
                h.text("This app is written with the SDK alone: an echo, a list, a form, a drag, and four routes.", variant="muted"),
                grid={"grid-template-rows": "auto auto"},
                # The title is a grid item too: it spans both columns, so the two columns of
                # cards start under it instead of beside it.
                style={"grid-column": "1 / -1"},
                id="home-title",
            ),
            h.frame(
                h.frame(
                    h.text("Echo", variant="heading-3"),
                    h.text(
                        "A field's exit is the group it sits in: Enter makes the loom send {field: value} to the "
                        "loom's sink, and the field's `tag` is the key.",
                        variant="muted",
                    ),
                    h.loom(h.input(tag="name", id="name-input"), sink=echo, submit=["enter"], id="echo-form"),
                    h.text(source=slots.echo, id="echo"),
                    grid=CARD,
                    variant="card",
                    id="card-echo",
                ),
                h.frame(
                    h.text("List · drag", variant="heading-3"),
                    h.text(
                        "A row's identity is its id: ✕ removes by id, the archive box archives by id, and "
                        "a drop on another row swaps them — the gesture itself says nothing; only the "
                        "landing point speaks.",
                        variant="muted",
                    ),
                    h.loom(h.button("Add a row"), sink=add_row,
                             submit=["button"], id="add-row"),
                    h.tiles(source=slots.rows, id="rows"),
                    # The landing point names its event and what it accepts; `accept` is one tag
                    # (or any), so cargo of another tag is refused without a frame — and a
                    # landing without a `sink` is a load error, which is why the two come
                    # together.
                    h.frame(
                        h.text("Drag a row here to archive it"),
                        accept={"tag": "row"},
                        sink=slots("row.archive"),
                        grid={"place-items": "center"},
                        style={"border": "var(--border)", "border-style": "dashed",
                               "min-height": "72px"},
                        id="archive",
                    ),
                    h.text(source=slots.archived, id="archived"),
                    grid=CARD,
                    variant="card",
                    id="card-rows",
                ),
                grid={"grid-template-rows": "auto auto", "gap": "16px", "align-content": "start"},
                id="home-left",
            ),
            h.frame(
                h.text("Sign in · the gate", variant="heading-3"),
                h.text(
                    "This form speaks the framework's verb `reflux:login`: the app writes only verify and view, and never reads the password.",
                    variant="muted",
                ),
                # Two fields stacked beside the button: a loom is a flex row, so the column is
                # a frame inside it and the press stays a child of the loom it belongs to.
                h.loom(
                    h.frame(
                        h.input(tag="user", id="f-user"),
                        h.input(tag="pass", kind=JsType.password, id="f-pass"),
                        grid={"grid-template-rows": "auto auto", "gap": "8px"},
                        id="login-fields",
                    ),
                    h.frame(
                        h.button("Sign in"),
                        style={"flex": "0 0 auto", "align-self": "end"},
                        id="login-press",
                    ),
                    sink=slots(LOGIN),
                    submit=["enter", "button"],
                    id="login",
                ),
                h.frame(source=slots(AUTH_SLOT), id="auth-region"),
                # Behind a declaration: a click here from a visitor never reaches the handler.
                h.loom(h.button("Secret"),
                         sink=gated(reveal), submit=["button"], id="vault"),
                h.text(source=slots.secret, id="secret"),
                h.loom(h.button("Log out"), sink=slots(LOGOUT),
                         submit=["button"], id="logout"),
                grid=CARD,
                variant="card",
                id="card-login",
            ),
            # The footnote is a grid item too, and it spans: a text node has no style, so the
            # node that carries the placement is a frame around it.
            h.frame(
                h.text(
                    "accrete has no URL-bearing type: a page turns by submitting that form above, the producer"
                    "answers with a new structure plus the new path marker, and the runtime mirrors the marker into the address bar.",
                    variant="muted",
                ),
                style={"grid-column": "1 / -1"},
                id="home-note",
            ),
            grid={"grid-template-columns": "minmax(0, 1fr) minmax(280px, 360px)", "gap": "16px",
                  "align-items": "start"},
            id="home-grid",
        ),
    )



@app.page("/about", title="About")
def about_page(ctx, match):
    """The second route: the same shape, reached by the address bar, a deep link, or the nav."""
    return (
        h.text("About", variant="heading-1"),
        h.text("This example app is written with the SDK alone: an echo, a list, a form, and four routes — /, /about, /chat and the walkthrough."),
        nav_loom("Back to the demo", GO_HOME),
    )


# --- handlers: the named landing points (identity in the page, or across it) --------------------

@app.on(slots.row["remove"])  # `remove` is a verb: the name goes by subscript
def on_remove(ctx, frame) -> None:
    row_id = frame.get("id")  # the row's form carried its identity up
    state.rows.value = [row for row in state.rows.value if row[0] != row_id]


@app.on(slots("row.archive"))
def on_archive(ctx, frame) -> None:
    """A drop: the landing point sends `{id, tag}` — the dragged frame's own id, and its tag."""
    cargo = (frame.get("data") or {}).get("id") or ""
    row_id = cargo.removesuffix("-cargo")
    row = next((r for r in state.rows.value if r[0] == row_id), None)
    if row is None:
        return
    slots_of(ctx).archived.set(h.text(f"Archived: {row[1]}"))
    state.rows.value = [r for r in state.rows.value if r[0] != row_id]


@app.on(slots("row.move"))
def on_move(ctx, frame) -> None:
    """One row landed on another: put it where the landing row was.

    Both identities are in this one frame (`id` is the landing, `data.id` the cargo), so a swap is
    just a list reordering — on the wire it is one `move`, the row's node is reused and focus stays
    (fluxen ADR 0005).
    """
    target = (frame.get("id") or "").removesuffix("-cargo")
    dragged = ((frame.get("data") or {}).get("id") or "").removesuffix("-cargo")
    rows = state.rows.value
    ids = [row[0] for row in rows]
    if not dragged or dragged == target or dragged not in ids or target not in ids:
        return  # landed on itself, or one end is already gone: nothing happened
    moving = rows[ids.index(dragged)]
    rest = [row for row in rows if row[0] != dragged]
    rest.insert([row[0] for row in rest].index(target), moving)  # land on a row, sit before it
    state.rows.value = rest


@app.on(slots(GO_HOME.name))
@app.on(slots(GO_ABOUT.name))
@app.on(slots(GO_DEMO.name))
@app.on(slots(GO_CHAT.name))
@app.on(slots(GO_COUNTER.name))
@app.on(slots(GO_SETTINGS.name))
def on_go(ctx, frame) -> None:
    """A submit that moves the client: the new structure and the new path marker."""
    ctx.go(GO[frame["dest"]])


@app.mount("/status")
def status(request: Request) -> Response:
    """A plain HTTP route in the same table as the socket — for whoever runs this, not for the page.

    Frames are how a page is drawn; this is how a monitor, a shell script or a load balancer asks a
    question. It is not a page, it has no device, and it answers JSON: the routes this app declares,
    what is mounted beside them, how many connections are live, every name it has used (slots, dests,
    host events — one namespace), and the counters.
    """
    return Response(
        200,
        json.dumps(
            {
                "ok": True,
                "routes": [declared.path for declared in app.routes],
                "mounts": sorted(app.mounts),
                "devices": len(app.live()),
                "slots": sorted(app.declared),
                "stats": dict(app.stats),
            },
            ensure_ascii=False,
        ),
        "application/json",
    )


# The two pages that live in their own modules: importing them is what declares their routes on this
# app (they need `app` to exist, which is why the imports are here and not at the top).
from . import demo_chat, demo_counter, demo_settings  # noqa: E402
from .demo import page as walkthrough  # noqa: E402

# Each page declares its own route and uplinks in its own `register`: the module is the page, and the
# app only says where on it to hang them. (`app.page(...)(page)` rather than a decorator, because a
# page module must not import the app — under `python3 -m examples.en.demo_app` the app module runs as
# `__main__`, and `from .demo_app import app` would build a second copy of it.)
demo_chat.register(app, slots)
demo_counter.register(app)
demo_settings.register(app)
walkthrough.register(app)
walkthrough.install(app)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="examples.zh.demo_app", description="Serve the reference app.")
    ap.add_argument("--port", type=int, default=8000, help="0 picks a free port (default: 8000)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--pace", type=float, default=walkthrough.settings.pace,
                    help="seconds per typewriter chunk on the walkthrough (default: 0.03)")
    ap.add_argument("--hold", type=float, default=walkthrough.settings.hold,
                    help="seconds between the walkthrough's beats (default: 0.35)")
    ap.add_argument("--model", choices=("scripted", "openai"), default="scripted",
                    help="what answers on /chat (default: scripted, offline)")
    ap.add_argument("--delay", type=float, default=demo_chat.settings.delay,
                    help="seconds between the chat's chunks (default: 0.02)")
    ap.add_argument("--window", type=int, default=demo_chat.settings.window,
                    help="turns of chat context the model sees (default: 12)")
    ap.add_argument("--settings", default=".demo-settings.json",
                    help="where the settings page keeps its choices (default: ./.demo-settings.json)")
    args = ap.parse_args(argv)
    walkthrough.settings.pace = args.pace
    walkthrough.settings.hold = args.hold
    demo_chat.settings.delay = args.delay
    demo_chat.settings.window = args.window
    demo_chat.settings.model = demo_chat.OpenAI() if args.model == "openai" else demo_chat.Scripted(window=args.window)
    demo_settings.settings.path = Path(args.settings)
    demo_settings.settings.load()  # what was stored is this app's opening line (ADR 0001 §5)
    demo_chat.share_http(app, demo_chat.settings.model)

    server = app.start(0 if args.port == 0 else args.port, args.host)
    print(f"[reflux] serving the reference app on http://{args.host}:{server.server_address[1]}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.stop()  # hooks -> the shared session -> the watchdog -> the server, in one place
    return 0


if __name__ == "__main__":
    raise SystemExit(main())