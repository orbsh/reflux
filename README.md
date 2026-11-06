# reflux

A UI stack where the producer sends **operations**, not HTML.

The browser runs a pinned WebAssembly renderer that knows one vocabulary (accrete: the node and
action set the renderer itself implements) and nothing about your application. Your process builds
nodes from that vocabulary and sends small frames: *create this structure*, *set this slot*, *append
this row*. The page draws it, and sends back what the user did.

Nothing is templated, nothing is compiled per app, and the renderer bundle never changes when your
interface does.

## The three parts

| part | lives in | does |
|---|---|---|
| producer | your code, Python or Rust | builds nodes + frames with a generated SDK |
| host | `reflux/app.py` | serves the page, owns devices, routes, the uplink registry |
| page | `www/` | static shell + `reflux.js` runtime + the pinned renderer bundle |

The wire between them is one dialect: accrete's eight actions, and a frame **is** the array of them —
no envelope (the renderer decodes nothing else). `reflux/wire.py` is that layer, and it is the only
place a frame is built.

## Install

    pip install reflux            # or: uv add reflux

The wheel is self-contained: it carries the page (`reflux/www/`) with the pinned renderer bundle
inside it, so a server started from an installed reflux serves pages without a network request and
without any build step on your side.

    python3 -c "from reflux.demo_app import make_app; make_app().serve_forever(8000)"

The bundle is put in **while the wheel is built** (`hatch_build.py`): it downloads the release
`vendor/pin.json` names, verifies that the manifest on disk is that revision, and copies `www/` in as
`reflux/www/`. Building a wheel therefore needs network the first time; running one never does.

From a checkout, the same thing is one command and no build: `python3 tools/vendor.py fetch` puts the
bundle at `www/static/vendor/fluxen/`, and the server serves the repository's `www/` directly.

## Requirements

- Python ≥ 3.11 and `pydantic` 2 — the generated type layer is pydantic models
- `cargo` only if you want to build the Rust SDK

Everything except the SDK's type layer is standard library.

## The renderer bundle

The page runs a WebAssembly renderer that belongs to another repository (fluxen), so it is **not
committed here** — a 3 MB wasm with a content-hashed name is not something a diff can review. What is
committed is the pin and the means to install it:

```
vendor/pin.json          the release to install: fluxen rev, tag, asset, URL
tools/vendor.py          fetch | build | install — one output layout
www/static/vendor/fluxen/versions.json   written on install; every gate reads it
```

```bash
python3 tools/vendor.py fetch                          # from the pinned release (no Rust needed)
python3 tools/vendor.py build --fluxen ../fluxen       # trunk build a fluxen checkout, then install
python3 tools/vendor.py install --dist ../fluxen/examples/renderer/dist   # adopt an existing build
```

`fetch` installs four files — the JS glue, its wasm, `assets/main.css`, `assets/custom.css` — and
writes `versions.json` with the rev plus a sha256 and size per file. The gates compare against that
file over HTTP (`gate_t0`), so a stale or hand-edited bundle fails as a red gate rather than a page
that half-loads.

Publishing is automatic (`.github/workflows/renderer.yml`), because the tag is the revision and so
the two cannot disagree: every push to main publishes the pin's revision *if that tag does not
exist yet*, by building it with `trunk build --release` and attaching
`dist-release/fluxen-renderer-<rev>.tar.gz` plus `SHA256SUMS` to a release of this repository. A push
whose tag is already published builds nothing — it installs the release and runs the tests against
it. So bumping the renderer is: `build --fluxen ../fluxen` locally to run the browser gates against
the new bundle, then commit `rev`/`tag`/`asset` in `vendor/pin.json`. CI publishes on that push;
`fetch` works everywhere afterwards. The module media (monaco, mermaid, 3d-force-graph, …) is not in
the bundle — frames that name those fetch them, so it stays ~3 MB.

## Try the reference app

```
python3 -m reflux.demo_app --port 8000
```

Open <http://127.0.0.1:8000/>. It has one of each shape an application needs: an input that echoes,
a list you can add to and remove from, a form that submits several fields at once, and two routes
that change both the structure and the address bar.

Two tools tell you what a running app declared:

```
python3 -m reflux.cli routes reflux.demo_app                  # path → source module → metadata
python3 -m reflux.cli dests reflux.demo_app:make_app         # dest → kind → handler source
```

## Your first app

Roughly twenty lines, and every one of them is used:

```python
from reflux import App, wire
from reflux.sdk import builders as b
from reflux.sdk import markers

app = App()                       # one object; every declaration below hangs on it


@app.route("/", title="Hello")
def home(ctx, match):
    return markers.page(
        "/",
        "Hello",
        b.text("Hello", variant="heading-1"),
        b.input(dest=ctx.slot.name.change, id="name"),   # a dest: the handler's name
        b.text(source=ctx.slot.echo, id="echo"),          # a slot: the data plane's name
    )


@app.on(app.slot.name.change)
def on_name(ctx, frame):
    ctx.slot["echo"].set(b.text(str(frame["data"])))   # one frame: set the `echo` slot


if __name__ == "__main__":
    app.serve_forever(8000)
```

What the pieces are:

- **`@app.route("/")`** declares a page on that app's table, right above its handler. (`@route(…)`
  is the same declaration against the module-level table `App()` reads by default — use it when the
  table is shared across modules, e.g. with `discover`.) The handler draws with `ctx.page(*content)` — the
  framework wraps it in the markers and `create` for you, and a page never returns. Data the page
  reads is a slot, seeded with a send: `ctx.slot["rows"].append(row)` (what `demo_app` does, so its
  rows arrive before the structure that reads them).
- **`markers.page(path, title, *children)`** is what `ctx.page` builds: the two markers the page runtime
  mirrors into the address bar and the tab title, then your content. It is a convention, not a wire type
  — reach for it directly only when you are assembling a page by hand.
- **`b.*`** are the generated constructors: one per accrete type, named after the wire's own `type`
  values. `b.text(source=…)` reads a slot and `b.input(dest=…)` speaks to a dest — both take a handle
  from `ctx.slot`, never a string. A handle nests: `ctx.slot.chat.send` is the name `chat.send`, so a
  page's slots and its uplinks read off the same view.
- **`@app.on(app.slot.name.change)`** is the only way an uplink frame reaches your code — the handle
  is the app's own table, so the page that sends to the dest and the handler that answers it are one
  name (`@app.dests.register(name)` is the same declaration spelled at the registry). An
  unregistered name is refused and counted — never dispatched dynamically.
"- **`ctx.emit(*ops)`** is exactly one frame, flushed in order — a handler's only way to speak.
- **A slot is an object.** `ctx.slot["status"]` / `ctx.slot.chat.send` hand out a `Slot`; its verbs
  are the wire's: `.set(node)`, `.append(node)`, `.patch(path, value, op=)`, `.remove(id)`. The name is
  written once, and a `Protocol` with the names is what the editor completes — no `STATUS = "status"`
  constants kept in step by eye. `with ctx.turn():` collects several writes into one frame.
- **Nothing returns.** An uplink handler says `ctx.emit(...)`; a page handler says `ctx.page(*content)`
  and the app composes the frame (shell once, then the `routes` slot) — including the two markers, so
  the address and the title are written once, on the route where they were declared. Only an HTTP route
  returns, because only HTTP is a request waiting for an answer.".strip('"')
- **`device.data`** is yours. The framework hands you a device per connection and never reads that
  bag: put the user on it after a login, and it dies with the socket.

Run it with `python3 myapp.py` and open <http://127.0.0.1:8000/>.

## Connections, and the HTTP side

A **device** is one connection, not one user: a browser tab is a device, a phone is another, and
whether two of them share anything is your bookkeeping. The framework keeps the table and nothing
else — `app.live()` (a snapshot), `app.device(id)` (one, by the id a handler was handed),
`app.evict(id=… | where=…, reason=…)` (close them, through the door a disconnect already uses),
plus the heartbeat that judges a peer dead after `dead_after` seconds of silence.

Signing in is therefore not a framework event. Connect anonymously, draw a login form when you need
one (it is a downlink message like any other), register the destination it posts to, and after your
own verification (`user = check_credentials(...)`, an external service, whatever) hang the result on
the connection and redraw:

```python
@app.on(app.slot.login)
def on_login(ctx, frame):
    user = check_credentials(frame["data"])     # yours; may call an external service
    if user is None:
        ctx.emit(wire.set("form.error", b.text("wrong password")))
        return
    device.data["user"] = user
    device.draw()                               # one frame, now with an identity
```

The socket itself is a **route in a table**, next to whatever else you mount:

```python
app = App()                                  # mounts == {"/ws": CHANNEL}
app.mount("/health", lambda request: "ok")   # Request in; Response, (status, body) or a body out
app.unmount("/ws"); app.mount("/socket", CHANNEL)   # move the channel
```

`Request` carries `method`, `path`, `query`, `headers` (lower-cased), `peer` and `body`; a route that
raises answers 500 and the server keeps serving. This layer is deliberately thin — reflux is not an
HTTP framework, and anything bigger belongs behind a real server.

## The wire

Eight actions. A frame **is** the list of them — a bare JSON array, with nothing wrapped around it. An
address inside the tree is a `slot` (`""` = the layout root); an uplink's landing point is a `dest`
(`Outflow.dest`, `bind: {kind: "dest", dest: …}`) — two words, because the directions are not
symmetric: one writes into a place in the page, the other names a target on the host. `event` stays
with the DOM and with the host's own events; it never appears on this wire:

| action | payload | meaning |
|---|---|---|
| `create` | `slot: ""`, `data` (a node) | replace the layout root |
| `set` | `slot`, `data` | replace the node in a data slot |
| `append` | `slot`, `data`, `position?` | add a row to a list slot |
| `remove` | `slot`, `id` | drop a row by identity |
| `patch` | `slot`, `path` (JSON Pointer), `op`, `value`, `id?` | change one value inside the addressed plane |
| `inject` | `slot`, `data`, `name?`, `id?` | write the values plane, as if a local emit fired (`name` defaults to the slot) |
| `tmpl` | `name`, `data` (JSON text) | register a substitution table |
| `empty` | — | a no-op, for keeping a frame's shape |

Rules the framework enforces rather than documents and forgets:

- one turn is one frame; **1024 operations** per frame (`reflux/protocol.py`)
- every node id is unique **within one tree** — a list renders by key, so a repeat is a half-drawn list
- `position = 0` means "the tail" and is left off the wire
- a frame is an array; an object is refused at both ends (the envelope belongs to the host, not the wire)
- uplinks are `{dest, id?, data}`; the reserved `reflux:` prefix belongs to the framework
- `connect` / `location` / `disconnect` are the host's events, not addresses: a client that sends
  one is refused whole (it cannot claim a connect that never happened)

## Two SDKs, one specification

`profile/profile.json` says which types are exposed and what each one's keywords are;
`schema/accrete.schema.json` is the wire's snapshot. Both SDKs are generated from those two files,
which is what makes the second language a translation of the same thing rather than a second dialect.

```
python3 tools/gen_sdk.py            # regenerate Python + Rust builders
python3 tools/gen_sdk.py --check    # drift gate: exits 1 when disk disagrees with schema + profile
cd sdks/rust && cargo run --bin frames   # the reference app's frames, as JSON lines
```

Generated: the node builders (`reflux/sdk/types.py`, `reflux/sdk/builders.py`,
`sdks/rust/src/types.rs`). Hand-written in both languages: the frame layer (`reflux/wire.py`,
`sdks/rust/src/wire.rs`) and the page markers. The spec owns *what you may build*; it does not own
the shape of a frame.

`python3 tools/gate_t10.py` builds seven frames with each SDK and compares them **byte for byte**.

## The example app: one page per file

`examples/app/` is a whole application, not a toy: a dashboard with two charts and a 3D viewport, and
a chat page with a backend behind it. The shape is the one a framework's docs should teach —

```
examples/app/
  app.py         the app and its shell; the host events; main()
  dashboard.py   "/"     — charts, a module host, a refresh
  chat.py        "/chat" — a conversation per connection, streamed, stoppable
  walkthrough.py seven steps, no browser
```

— one page per file, each declaring its route on the shared app with `@app.route`, each keeping the
handlers for its own events. Importing a page module is what puts it in the table:

```python
# app.py
app = App(routes=Routes(), shell=shell)      # the shell stays; pages are written into `routes`

# dashboard.py
from .app import app

@app.route("/", title="概览")
def dashboard(ctx, match):
    ctx.page(b.text("概览", variant="heading-1"), ...)      # "/" 与 "概览" 来自 @app.route
```

- **The shell is drawn once.** The first frame is `create(shell)` plus the page in the `routes` slot;
  every page turn after that writes only that slot, so the header is never sent twice. Declare no shell
  and the framework supplies one — a single full-screen `routes` — so a page lands in that slot either
  way and `demo_app` is only a smaller frame, not a second shape.
- **A chart is a node with a spec.** `b.chart(value=<G2 grammar>, url="/assets/g2chart/index.js")`;
  the module that draws it is a file, and `app.mount("/assets/g2chart", path)` is how a page gets the
  files its modules need. A 3D viewport is the same idea with `b.canvas(url=…, value=…)`.
- **The address carries what the backend needs.** `hello` brings `path` and `query`, so `/chat` and
  `/?filter=…` open the right thing on the first frame; the URL belongs to the browser.
- **A page turn is one call.** `device.go("/chat")` moves that device's address and draws the page the
  way a click on a link would; `device.draw()` redraws where it already stands (a refresh, or after a
  login changed what the page should show). The address bar follows on its own, because the page says
  which address it is.
- **Three names belong to the host** — `connect` / `location` / `disconnect` — registered like any
  other name, and refused if a client tries to send them.
- **The socket is one entry in the HTTP table, and an operator's endpoint is another.** `@app.mount("/status")` puts a plain function next to `/ws` and the two asset directories; it takes a `Request` and answers JSON, because a monitor asks a question that is neither a page nor a frame:

  ```python
  @app.mount("/status")
  def status(request):
      return Response(200, json.dumps({"devices": len(app.live()), ...}), "application/json")
  ```

  `mount` returns the function, so the name stays bound and the declaration sits on the handler. A `str` or `Path` as the second argument means a directory served file by file instead; the channel is `mount("/socket", CHANNEL)`.

```
python3 -m examples.app --port 8100            # 概览 + 对话
python3 -m examples.app.walkthrough --auto     # the same seven steps, no browser
python3 tools/gate_dashboard.py                # 18 assertions: 13 over HTTP, 5 in Chromium
python3 tools/gate_chat.py                     # the chat page's own 12, over a socket and in Chromium
```

The chat's model is one method (`Model.reply`). `Scripted` runs offline and deterministic — the
default, so the demo needs no key; `OpenAI` speaks the OpenAI-compatible SSE form and is configured by
`OPENAI_BASE_URL` / `OPENAI_API_KEY` / `OPENAI_MODEL` (its reader is tested against a stub; it has not
been run against a live provider from this repo). Neither module is in git — `www/static/vendor/` is ignored, and 30 MB of 3D viewer is not an
example's business. Each is mounted from wherever it exists: a fluxen checkout's own assets
(`REFLUX_ASSETS`, default `../fluxen/examples/renderer/assets`), or a local copy under
`www/static/vendor/`:

```
cp -r ../fluxen/examples/renderer/assets/g2chart www/static/vendor/g2chart
cp -r ../fluxen/examples/renderer/assets/3dbrowser www/static/vendor/3dbrowser   # optional, 30 MB
```

A module that is not on disk draws a line saying where the page looked, not an empty box.

## Verify

```
python3 -m unittest discover -s tests -t .     # 229 tests, no browser
python3 tools/gate_ingest.py                   # the two boundaries, over a real socket
python3 tools/gate_t0.py                       # the page's request set and asset hashes
python3 tools/gate_t2.py                       # every action, asserted in a real browser
python3 tools/gate_t3.py                       # the whole vocabulary, drawn and styled
python3 tools/gate_t4.py                       # typing, clicking, form submits
python3 tools/gate_t6.py                       # address bar, history, deep links
python3 tools/gate_t7.py                       # devices: reload and death
python3 tools/gate_t8.py                       # what a bad frame does (and does not) do
python3 tools/gate_t9.py                       # the reference app end to end, auth included
python3 tools/gate_t10.py                      # Rust vs Python frames (needs cargo)
python3 tools/gate_dashboard.py                # the dashboard, its modules, and the chat page
python3 tools/measure.py                       # bytes, DOM changes, first paint, CPU
```

Every gate needs the renderer installed first: `python3 tools/vendor.py fetch`.

The browser gates drive a real headless Chromium over CDP using only the standard library; the first
`cargo build` needs crates.io.

## Layout

```
reflux/            the host: app, devices, wire, ingest, routes, dests, cli
reflux/sdk/        the Python SDK — generated types/builders, hand-written parse/markers
www/               the page: index.html, reflux.js runtime, css (the renderer bundle is
                   installed into www/static/vendor/fluxen/ by tools/vendor.py, not committed)
schema/ profile/   the wire's snapshot and this framework's selection over it
sdks/rust/         the second SDK, generated from the same two files
tools/             generators, gates, the CDP fixture, the measurement script, vendor.py
examples/app/      the example application — one page per file: dashboard (/), chat (/chat)
vendor/pin.json    which renderer release to install
tests/             everything that needs no browser
docs/              design and decision record (in Chinese)
```

## Docs

| file | what it is |
|---|---|
| `docs/DESIGN.md` | the design, including why each rejected shape was rejected |
| `docs/PLAN.md` | the ledger: what actually landed, and how each piece is re-verified |
| `docs/HANDOFF.md` | where things stand, what is deliberately missing, pitfalls already hit |
| `docs/PERF.md` | one measured run: frame bytes, DOM changes, first paint, server CPU |