# reflux

A UI stack where the producer sends **operations**, not HTML.

The browser runs a pinned WebAssembly renderer that knows one vocabulary (accrete: the node and
action set the renderer itself implements) and nothing about your application. Your process builds
nodes from that vocabulary and sends small frames: *create this structure*, *set this slot*, *append
this row*. The page draws it, and sends back what the user did.

Nothing is templated, nothing is compiled per app, and the renderer loom never changes when your
interface does.

## The three parts

| part | lives in | does |
|---|---|---|
| producer | your code, Python or Rust | builds nodes + frames with a generated SDK |
| host | `reflux/app.py` | serves the page, owns devices, routes, the uplink registry |
| page | `www/` | static shell + `reflux.js` runtime + the pinned renderer loom |

The wire between them is one dialect: accrete's eight actions, and a frame **is** the array of them —
no envelope (the renderer decodes nothing else). `reflux/wire.py` is that layer, and it is the only
place a frame is built.

## Install

    pip install reflux            # or: uv add reflux

The wheel is self-contained: it carries the page (`reflux/www/`) with the pinned renderer loom
inside it, so a server started from an installed reflux serves pages without a network request and
without any build step on your side.

    python3 -c "from examples.zh.demo_app import make_app; make_app().serve_forever(8000)"

The loom is put in **while the wheel is built** (`hatch_build.py`): it downloads the release
`vendor/pin.json` names, verifies that the manifest on disk is that revision, and copies `www/` in as
`reflux/www/`. Building a wheel therefore needs network the first time; running one never does.

From a checkout, the same thing is one command and no build: `python3 tools/vendor.py fetch` puts the
loom at `www/static/vendor/fluxen/`, and the server serves the repository's `www/` directly.

## Requirements

- Python ≥ 3.11 and `pydantic` 2 — the generated type layer is pydantic models
- `cargo` only if you want to build the Rust SDK

Everything except the SDK's type layer is standard library.

## The renderer loom

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

`fetch` installs four files — the JS glue, its wasm, `assets/core.css`, `assets/custom.css` — and
writes `versions.json` with the rev plus a sha256 and size per file. The gates compare against that
file over HTTP (`gate_t0`), so a stale or hand-edited loom fails as a red gate rather than a page
that half-loads.

Publishing is automatic (`.github/workflows/renderer.yml`), because the tag is the revision and so
the two cannot disagree: every push to main publishes the pin's revision *if that tag does not
exist yet*, by building it with `trunk build --release` and attaching
`dist-release/fluxen-renderer-<rev>.tar.gz` plus `SHA256SUMS` to a release of this repository. A push
whose tag is already published builds nothing — it installs the release and runs the tests against
it. So bumping the renderer is: `build --fluxen ../fluxen` locally to run the browser gates against
the new loom, then commit `rev`/`tag`/`asset` in `vendor/pin.json`. CI publishes on that push;
`fetch` works everywhere afterwards. The module media (monaco, mermaid, 3d-force-graph, …) is not in
the loom — frames that name those fetch them, so it stays ~3 MB.

## Try the reference app

```
python3 -m examples.zh.demo_app --port 8000
```

Open <http://127.0.0.1:8000/>. It has one of each shape an application needs: an input that echoes,
a list you can add to, remove from, and drag onto an archive frame, a loom that submits several
fields at once, and a shell with a nav over three routes — `/` (that vocabulary, laid out as cards),
`/about`, and `/demo`.

`/demo` is the walkthrough (`examples/zh/demo/page.py`): fluxen's own demo story — two charts, three
radars, a review table, two 3D models, a code editor and a relationship graph that grows as the story
goes — played inside this framework. It is four regions that each read one slot, and a floating
button in the window's corner plays, pauses, resumes and replays it. The story's text, chart specs
and graph are `examples/zh/demo/scene.py`; the module hosts it draws with (g2chart, the two viewers, the
editor) are mounted by the page itself, from `www/static/vendor/` or a fluxen checkout
(`REFLUX_ASSETS` overrides the path), and a page missing one says where it looked instead of drawing
an empty box.

Two tools tell you what a running app declared:

```
@app.hooks.inspect("/v1/inspect")                                 # the app's declaration, as JSON
def inspect(data):
    return data                                                   # or a subset, or (403, {...})
```

## Your first app

Roughly twenty lines, and every one of them is used:

```python
from reflux.site import app
from reflux import wire
from reflux.sdk import builders as b
from reflux.sdk import markers

# `reflux.site.app` is the deployment's app: one per process, built when that module is imported —
# `import reflux` alone builds nothing. A test, or a process that wants a second one, asks for a fresh
# instance with `create_app()`.


@app.page("/", title="Hello")
def home(ctx, match):
    return h.frame(
        h.text("Hello", variant="heading-1"),
        # a field's exit is its group: the loom holds the sink, the field only names its key
        h.loom(h.input(tag="name", id="name"), sink=ctx.slot.name.change),
        h.text(source=ctx.slot.echo, id="echo"),          # a slot: the data plane's name
    )


@app.on(app.slot.name.change)
def on_name(ctx, frame):
    ctx.slot["echo"].set(h.text(str(frame["data"])))   # one frame: set the `echo` slot


if __name__ == "__main__":
    app.serve_forever(8000)
```

What the pieces are:

- **`@app.page("/")`** declares a page on that app's table, right above its handler — the only way a
  route is declared. The handler **returns** its node; the
  framework wraps it in the markers, writes it into the `routes` slot, and `create`s the shell around
  it. Data the page reads is a slot, seeded with a send: `ctx.slot["rows"].append(row)` (what `demo_app`
  does, so its rows arrive before the structure that reads them). `ctx.page(*content)` is the other
  way to give a page — it draws instead of returning, which is what a handler driving a delivery by
  hand (`@app.on`) reaches for; a handler does one or the other, and doing both is a startup error.
- **`markers.page(path, title, *children)`** is what `ctx.page` builds: the two markers the page runtime
  mirrors into the address bar and the tab title, then your content. It is a convention, not a wire type
  — reach for it directly only when you are assembling a page by hand.
- **`h.*`** are the generated constructors: one per accrete type, named after the wire's own `type`
  values. `h.text(source=…)` reads a slot and `h.loom(…, sink=…)` speaks to a dest — both take a
  handle from `ctx.slot`, never a string. A field has no exit of its own: `tag` makes it a member of
  the enclosing loom, and the loom owns the address (`attrs.submit` says when, `attrs.reset` what
  its fields become afterwards, `attrs.sends` how many times it may send). A handle nests: `ctx.slot.chat.send` is the name `chat.send`, so a
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

Signing in is therefore not a framework event. Connect anonymously, draw a login loom when you need
one (it is a downlink message like any other), register the destination it posts to, and after your
own verification (`user = check_credentials(...)`, an external service, whatever) hang the result on
the connection and redraw:

```python
@app.on(app.slot.login)
def on_login(ctx, frame):
    user = check_credentials(frame["data"])     # yours; may call an external service
    if user is None:
        ctx.emit(wire.set("form.error", h.text("wrong password")))
        return
    device.data["user"] = user
    device.draw()                               # one frame, now with an identity
```

The socket itself is a **route in a table**, next to whatever else you mount:

```python
app = create_app()                           # mounts == {"/ws": CHANNEL}
app.mount("/health", lambda request: "ok")   # Request in; Response, (status, body) or a body out
app.unmount("/ws"); app.mount("/socket", CHANNEL)   # move the channel
```

`Request` carries `method`, `path`, `query`, `headers` (lower-cased), `peer` and `body`; a route that
raises answers 500 and the server keeps serving. This layer is deliberately thin — reflux is not an
HTTP framework, and anything bigger belongs behind a real server.

## The wire

Eight actions. A frame **is** the list of them — a bare JSON array, with nothing wrapped around it. An
address inside the tree is a `slot` (`""` = the layout root); an uplink's landing point is a `dest`
(`Outflow.dest`; a `sink` is the `Bind` that names it) — two words, because the directions are not
symmetric: one writes into a place in the page, the other names a target on the host. `event` stays
with the DOM and with the host's own events; it never appears on this wire:

| action | payload | meaning |
|---|---|---|
| `create` | `slot: ""`, `data` (a node) | replace the layout root |
| `set` | `slot`, `data` | replace the node in a data slot |
| `append` | `slot`, `data`, `position?` | add a row to a list slot |
| `remove` | `slot`, `id` | drop a row by identity |
| `patch` | `slot`, `path` (JSON Pointer), `op`, `value`, `id?` | change one value inside the addressed plane |
| `tmpl` | `name`, `params`, `data` (a node, or its JSON text) | register a template: a tree with `$name` holes and the names it takes |
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

`python3 tools/gate_t10.py` builds eight frames with each SDK and compares them **byte for byte**.

## The reference app: one page per file, in two languages

`examples/` holds the same application written twice — not one tree with a translation table on top:

```
examples/zh/   UI, comments and docstrings in Chinese      python3 -m examples.zh.demo_app --port 8000
examples/en/   UI, comments and docstrings in English      python3 -m examples.en.demo_app --port 8001
```

Both serve the same four pages, and both can run at once (each tree declares its own route table, so
`/` in one is not `/` in the other). The trees are byte-for-byte the same code apart from their words:
`tests/test_two_trees.py` draws every page in both and compares the node ids, then checks that no
Chinese survives in `examples/en/` and no English docstring survives in `examples/zh/`.

Each tree is one page per file:

```
demo_app.py     the app, its shell, `/` (the vocabulary, as cards) and `/about`; `/status`
demo_slots.py   every name the app speaks, in one Protocol (the editor's view of them)
demo_chat.py    "/chat" — a conversation per connection, streamed, stoppable, refusable
demo_counter.py "/counter" — the API on the most ordinary page there is: a number, three buttons, an
                input, a capped history; state per connection, handlers as closures
demo/page.py    "/demo" — fluxen's own walkthrough, played by a floating button
demo/scene.py   the walkthrough's text, chart specs and graph
chat_model.py   the model seam: `Scripted` (offline) or an OpenAI-compatible SSE client
```

A page declares its route where it is written, and its handlers beside it — the declaration and the
thing it draws are one thought:

```python
# examples/zh/demo_app.py
@app.page("/", title="演示")              # "/" and "演示" are the page's: the framework writes the markers
def home_page(ctx, match):
    return h.frame(h.text("演示", variant="heading-1"), ...)
```

`h` is the vocabulary (`from reflux.sdk import h`), named the way front-end code names it. Two entry
points, and the difference is where the page comes from: `h.frame(...)` is a page a person writes — each
node type keeps its generated signature, so keywords complete and a typo is a `TypeError` at the line;
`h.node(("frame", props, children))` is a page that *is* data — a chip described by a payload, rows read
from a slot — and its props are still the builder's own keywords, so the refusals survive.

A handler for a page's own event is written beside the frame that sends to it, as a closure. The
closure is handed the event's value and holds its slots; the framework names it when the page is drawn:

```python
@app.page("/", title="演示")
def home_page(ctx, match):
    slots = slots_of(ctx)

    def echo(value):                      # a loom submits its pack: {tag: value}
        slots.echo.set(h.text(value.get("name", "")))

    def add_row(value):
        slots.rows.append(row_node(...))

    return h.frame(
        h.loom(h.input(tag="name"), sink=echo, submit=["enter"]),
            # a button has no exit of its own: a press submits the loom, which owns the sink, the
            # payload and the id (ADR 0039 §2a)
            h.loom(h.button("加一行"), sink=add_row, submit=["button"]),
            h.text(source=slots.echo),
        )
    )
```

A slot holds a node, and most slots hold one *value* — a number, a line of text. That decision is a
**view**, declared once beside the page, so the writes take values and the node's id and variant are
written in one place:

```python
app.view("counter.count", lambda value: h.text(str(value), variant="heading-1", id="counter-value"))

slots.count.set(3)              # the view makes the node
slots.count.set(h.text("3"))    # already a node: goes through untouched
```

`@app.on(slot)` stays for the landing points whose name must exist before any page is drawn: a slot
with **several sources**, an identity that belongs to a row rather than to the page, the framework's own
verbs (`reflux:login`), and events that outlive a page. A gate rides the landing point rather than the
handler — `sink=gated(save)` — because that is where the reader asks the question.

A page that lives in its own module cannot import the app (under `-m` the app module runs as
`__main__`, so importing it would build a second copy), so it takes the app as an argument and declares
its page as a call — `app.page("/chat", title="对话")(page)` — in the same `register` that hangs
its handlers:

```python
# examples/zh/demo_chat.py — the page, its route and its two uplinks, together
def register(app, slots):
    app.page("/chat", title="对话")(page)
    app.on(slots.chat.send, on_send)
    app.on(slots.chat.stop, on_stop)
```

- **The shell is drawn once.** The first frame is `create(shell)` plus the page in the `routes` slot;
  every page turn after that writes only that slot, so the nav is never sent twice. Declare no shell
  and the framework supplies one — a single full-screen `routes` — so a page lands in that slot either
  way, which is why `demo_app` could grow a nav without touching a page.
- **A chart is a canvas with a spec.** `h.canvas(value=<G2 grammar>, url="/assets/g2chart/index.js")`;
  the module that draws it is a file, and `app.mount("/assets/g2chart", path)` is how a page gets the
  files its modules need — the walkthrough page does exactly that, for two charts, two viewers and an
  editor. A 3D viewport is the same node with another url: accrete has one module host, and which
  renderer it mounts lives in the url.
- **The address carries what the backend needs.** `hello` brings `path` and `query`, so `/chat` and
  `/?filter=…` open the right thing on the first frame; the URL belongs to the browser.
- **A page turn is one call.** `device.go("/chat")` moves that device's address and draws the page the
  way a click on a link would; `device.draw()` redraws where it already stands (a refresh, or after a
  login changed what the page should show). The address bar follows on its own, because the page says
  which address it is.
- **Three names belong to the host** — `connect` / `location` / `disconnect` — registered like any
  other name, and refused if a client tries to send them.
- **The socket is one entry in the HTTP table, and an operator's endpoint is another.**
  `@app.mount("/status")` puts a plain function next to `/ws`; it takes a `Request` and answers JSON,
  because a monitor asks a question that is neither a page nor a frame:

  ```python
  @app.mount("/status")
  def status(request):
      return Response(200, json.dumps({"devices": len(app.live()), ...}), "application/json")
  ```

  `mount` returns the function, so the name stays bound and the declaration sits on the handler. A `str`
  or `Path` as the second argument means a directory served file by file instead; the channel is
  `mount("/socket", CHANNEL)`.

```
python3 -m examples.zh.demo_app --port 8000         # /、/about、/chat、/demo
python3 tools/gate_t9.py                         # the reference app: 15, over a socket and in Chromium
python3 tools/gate_chat.py                       # the chat page: 12 — streaming, stop, refusals, the window
python3 tools/gate_demo.py                       # the walkthrough page: 19
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
python3 -m unittest discover -s tests -t .     # 305 tests, no browser
python3 tools/gate_ingest.py                   # the two boundaries, over a real socket
python3 tools/gate_t0.py                       # the page's request set and asset hashes
python3 tools/gate_t2.py                       # every action, asserted in a real browser
python3 tools/gate_t3.py                       # the whole vocabulary, drawn and styled
python3 tools/gate_t4.py                       # typing, clicking, loom submits
python3 tools/gate_t6.py                       # address bar, history, deep links
python3 tools/gate_t7.py                       # devices: reload and death
python3 tools/gate_t8.py                       # what a bad frame does (and does not) do
python3 tools/gate_t9.py                       # the reference app end to end, auth included
python3 tools/gate_t10.py                      # Rust vs Python frames (needs cargo)
python3 tools/gate_chat.py                     # the chat page, over a socket and in a browser
python3 tools/measure.py                       # bytes, DOM changes, first paint, CPU
```

Every gate needs the renderer installed first: `python3 tools/vendor.py fetch`.

The browser gates drive a real headless Chromium over CDP using only the standard library; the first
`cargo build` needs crates.io.

## Layout

```
reflux/            the host: app, devices, wire, ingest, routes, dests, cli
reflux/sdk/        the Python SDK — generated types/builders, hand-written parse/markers
www/               the page: index.html, reflux.js runtime, css (the renderer loom is
                   installed into www/static/vendor/fluxen/ by tools/vendor.py, not committed)
schema/ profile/   the wire's snapshot and this framework's selection over it
sdks/rust/         the second SDK, generated from the same two files
tools/             generators, gates, the CDP fixture, the measurement script, vendor.py
examples/          the reference app, twice: examples/zh (Chinese) and examples/en (English)
                   page (demo/), the model seam (chat_model.py)
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