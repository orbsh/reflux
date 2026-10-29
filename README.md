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
| host | `reflux/app.py` | serves the page, owns sessions, routes, the uplink registry |
| page | `www/` | static shell + `reflux.js` runtime + the pinned renderer bundle |

The wire between them is one dialect: accrete's eight actions, and a frame **is** the array of them —
no envelope (the renderer decodes nothing else). `reflux/wire.py` is that layer, and it is the only
place a frame is built.

## Requirements

- Python ≥ 3.11 and `pydantic` 2 — the generated type layer is pydantic models
- `cargo` only if you want to build the Rust SDK

There is nothing to install: the producer side runs from the repository (the package is not a wheel).
Everything except the SDK's type layer is standard library.

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
python3 -m reflux.cli uplinks reflux.demo_app:make_app       # uplink slot → kind → handler source
```

## Your first app

Roughly twenty lines, and every one of them is used:

```python
from reflux import App, route, wire
from reflux.sdk import builders as b
from reflux.sdk import markers


@route("/")
def home(session, match):
    return markers.page(
        "/",
        "Hello",
        b.text("Hello", variant="heading-1"),
        b.input(uplink="name.change", id="name"),
        b.text(source="echo", id="echo"),
    )


app = App()


@app.uplinks.register("name.change")
def on_name(session, frame):
    session.draw(wire.set("echo", b.text(str(frame["data"]))))


if __name__ == "__main__":
    app.serve_forever(8000)
```

What the pieces are:

- **`@route("/")`** registers into the module-level table; `App()` picks it up. The handler returns
  a **node** — the framework wraps it in `create` for you — or a **list of operations** when you
  also need to seed the data slots the page reads (that is what `demo_app` does, so its rows arrive
  with the structure).
- **`markers.page(path, title, *children)`** puts the two markers the page runtime mirrors into the
  address bar and the tab title, then your content. It is a convention, not a wire type.
- **`b.*`** are the generated constructors: one per accrete type, named after the wire's own `type`
  values. `b.text(source="echo")` reads a slot; `b.input(uplink="name.change")` sends one.
- **`@app.uplinks.register("name.change")`** is the only way an uplink frame reaches your code. An
  unregistered name is refused and counted — never dispatched dynamically.
- **`session.draw(*ops)`** is exactly one frame, flushed in order.

Run it with `python3 myapp.py` and open <http://127.0.0.1:8000/>.

## The wire

Eight actions. A frame **is** the list of them — a bare JSON array, with nothing wrapped around it. An
address inside the tree is a `slot` (`""` = the layout root), and so is the uplink's landing point
(`Outflow.slot`) — one word, and the frame's direction says which side it lands on. `event` stays with
the DOM and with the host's own events; it never appears on this wire:

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
- uplinks are `{slot, id?, data}`; the reserved `reflux:` prefix belongs to the framework

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

## An example: an AI chat app

`examples/chat/` is a whole application whose subject is the backend: a conversation per
connection, a reply streamed as `patch` frames, a stop that stops at a chunk boundary, a second
message refused with a reason, the app's own size limits, and a model that fails into a bubble
instead of a traceback.

```
python3 -m examples.chat.app --port 8100       # the app, then http://127.0.0.1:8100/
python3 -m examples.chat.walkthrough --auto    # the same six behaviours, no browser
python3 tools/gate_chat.py                            # 12 assertions: 9 over a socket, 3 in Chromium
```

The model is one method (`Model.reply`). `Scripted` runs offline and deterministic — the default, so
the demo needs no key; `OpenAI` speaks the OpenAI-compatible SSE form and is configured by
`OPENAI_BASE_URL` / `OPENAI_API_KEY` / `OPENAI_MODEL` (its reader is tested against a stub; it has
not been run against a live provider from this repo).

## Verify

```
python3 -m unittest discover -s tests -t .     # 163 tests, no browser
python3 tools/gate_ingest.py                   # the two boundaries, over a real socket
python3 tools/gate_t0.py                       # the page's request set and asset hashes
python3 tools/gate_t2.py                       # every action, asserted in a real browser
python3 tools/gate_t3.py                       # the whole vocabulary, drawn and styled
python3 tools/gate_t4.py                       # typing, clicking, form submits
python3 tools/gate_t6.py                       # address bar, history, deep links
python3 tools/gate_t7.py                       # sessions: reload and death
python3 tools/gate_t8.py                       # what a bad frame does (and does not) do
python3 tools/gate_t9.py                       # the reference app, driven end to end
python3 tools/gate_t10.py                      # Rust vs Python frames (needs cargo)
python3 tools/measure.py                       # bytes, DOM changes, first paint, CPU
```

The browser gates drive a real headless Chromium over CDP using only the standard library; the first
`cargo build` needs crates.io.

## Layout

```
reflux/            the host: app, sessions, wire, ingest, routes, uplinks, cli
reflux/sdk/        the Python SDK — generated types/builders, hand-written parse/markers
www/               the page: index.html, reflux.js runtime, css, pinned renderer bundle
schema/ profile/   the wire's snapshot and this framework's selection over it
sdks/rust/         the second SDK, generated from the same two files
tools/             generators, gates, the CDP fixture, the measurement script
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