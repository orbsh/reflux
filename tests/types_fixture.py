"""One minimal, legal node per exposed accrete type — the fixture T3′ and its offline test share.

`profile.exposed()` is the authority on which types a producer may draw; `test_types_drawable`
asserts this table is exactly that set, so adding a type to the profile without giving it a node
fails there rather than quietly shrinking what the gate draws.

The spelling is ADR 0031/0032/0034/0035/0039's, not the retired one: a read is a `Source` (slot,
scope, path, default), a write a `Sink` (dest, scope, path), a `loom` packs its fields (each field
named by its own `tag`, the exit on the loom's `sink`, the timing in `attrs.submit`), and a
multi-line field is `input` with `multiline`. The types that used to be separate are folded: `fold`/`popup`/`layer`/
`float`/`portal` are one `panel` (`place` + `state`), `form` is `loom`, `textarea` is
`input.multiline`, `group`/`grab`/`dock` are one `frame` (`style` / `draggable` / `accept` + `sink`),
and a row of a grid is `entry`.

Two marks, both facts rather than taste:

- `ASSET_BACKED` — `canvas` mounts an external ES module (`mount_module(url)`). Its capability is a
  deployment artifact, not vocabulary, so the live gate draws everything else and this one stays on
  the offline table (a stub module would prove the stub, not the type). The framework's own old
  kinds (`chart`/`editor`/`diagram`) are canvases with a url now — accrete has one module host.
- `STATIC` — nodes whose value is a URL/asset rather than text; harmless to draw, but nothing to
  assert about them beyond "it did not error".
"""

from __future__ import annotations

from typing import Any

ASSET_BACKED = frozenset({"canvas"})


def text(value: str, **rest: Any) -> dict:
    """A `text` leaf carrying `value` — the cheapest way to put something visible in a container."""
    return {"type": "text", "source": {"default": value}, **rest}


def field(tag: str, **rest: Any) -> dict:
    """A loomd field: `tag` is the key the enclosing loom packs it under; the exit is the loom's."""
    return {"type": "input", "tag": tag, **rest}

# A button's label is its `source`, its uplink its `sink` (ADR 0032 dropped the `submit` kind). It
# lives inside a `loom` — that is the only place the renderer mounts one.
# A button reads its label and sends nothing itself: a press submits the enclosing loom, which
# holds the exit (ADR 0039 §2a).
BUTTON: dict = {"type": "button", "source": {"default": "提交"}}


NODES: dict[str, dict] = {
    # One node, two states (ADR 0027): `children` is the static shape, a `source` binding is the
    # region a slot fills. The fixture takes the static form; the shell's `routes` reader is the
    # other one, and it is what puts a reserved id on the DOM.
    # ADR 0034: a frame is the only box that carries cargo, and the two directions share the box —
    # as a source (`draggable`, its cargo the subtree itself), as a landing (`accept` + `sink`), or
    # both. This one is both, so the gate sees each: the drop class, the sink and the style surface
    # `group` used to have.
    "frame": {
        "type": "frame",
        "id": "t3-frame",
        "attrs": {
            "draggable": {"tag": "note"},
            "accept": {"tag": "note"},
            "style": {"padding": "2px"},
        },
        "sink": {"dest": "gate.dock"},
        "children": [text("frame")],
    },
    "canvas": {"type": "canvas", "url": "/module.js"},
    # The native graph (ADR 0018/0029): its renderer is in the wasm, so there is no module host, no
    # role class and no DOM id — the gate proves it by the canvas it mounts (nothing else in this
    # tree can make one). Payload is the snapshot `{nodes, links}`; the node needs a real box or the
    # drawing buffer is 0x0.
    "forcegraph": {
        "type": "forcegraph",
        "attrs": {"height": "260px"},
        "source": {
            "default": {
                "nodes": [{"id": "a", "name": "a"}, {"id": "b", "name": "b"}],
                "links": [{"source": "a", "target": "b"}],
            }
        },
    },
    # One node, two axes (ADR 0030): `place` says where it sits, `state` says who decides. The old
    # `fold` is `inline` + a header child (`replace_header`), `popup` is `anchor`, and `layer` /
    # `float` / `portal` are `viewport` at an edge.
    "panel": {
        "type": "panel",
        "id": "t3-panel",
        "attrs": {"place": "inline", "replace_header": True},
        "children": [text("panel-header"), text("panel-body")],
    },
    # ADR 0032: the loom packs its fields into one object and owns the exit (`sink`) and the
    # timing (`attrs.submit`); each field's name is its own `tag`, never the sink's address. Its
    # button is the press the `submit: [button]` names — a button renders nowhere else.
    "loom": {
        "type": "loom",
        "attrs": {"submit": ["enter", "button"]},
        "sink": {"dest": "gate.loom"},
        "children": [
            field("name"),
            field("body", multiline=True, placeholder={"default": "写点什么"}),
            {"type": "select", "tag": "kind", "options": {"slot": "opts"}, "source": {"default": "a"}},
            BUTTON,
        ],
    },
    "svg": {"type": "svg", "children": [text("svg")]},
    "path": {"type": "path", "source": {"default": "M0 0 L1 1"}},
    # ADR 0031 §4 / 0035: `rack` and `pages` are this one node with different steppers (`step`) and
    # a `window`, and the table family is *not* markup here — `fields` makes each item an `entry`
    # whose fields are named by their own `attrs.selector`. `dir` names the axis the ITEMS flow on
    # (absent = `col`, the table every frame already draws), and the header is a hook (one selector
    # for the whole line) with `layers` — a count of header lines, not a direction word.
    "tiles": {
        "type": "tiles",
        "attrs": {
            "dir": "col",
            "fields": [{"key": "name", "title": "Name"}, {"key": "qty", "align": "end"}],
            "header": {"selector": "gate-grid-head", "layers": 1},
            "window": {"size": 1},
            "step": {"timer": 4000},
        },
        "source": {"slot": "rows"},
        "children": [
            {
                "type": "entry",
                "attrs": {"selector": "gate-row"},
                "children": [
                    text("name", attrs={"selector": "name"}),
                    text("1", attrs={"selector": "qty"}),
                ],
            }
        ],
    },
    # An entry is one item of a grid: named fields, each a child whose `selector` is the field's
    # name. No `id` here — an item that does not name itself is keyed by where it arrived.
    "entry": {
        "type": "entry",
        "children": [text("entry-field", attrs={"selector": "name"})],
    },
    # A button's label is its `source`, its uplink its `sink` (ADR 0032 dropped the `submit` kind).
    "button": BUTTON,
    # `image` renders an `<img>` only when it has a `default` value **and** some attrs
    # (`&& let Some(x) = accrete.attrs` in the renderer) — without attrs it draws an empty div.
    "image": {"type": "image", "attrs": {"desc": "a dot"}, "source": {"default": "/static/logo.svg"}},
    # No `source` prefill: the renderer starts an input from its js-kind's default ("" for text)
    # and reads neither `default` nor `source` for display — measured, and the reason the profile
    # no longer offers a constant source for `input`.
    # A field's uplink is its loom's, and `tag` is what makes it a member (ADR 0032 §2, revised):
    # `sink` is not a field's property on the wire at all, so the only way to send is a tag.
    "input": {"type": "input", "tag": "gate.input", "kind": "text"},
    # The option rows are a list plane: `options` is the wire's own field, and the renderer
    # currently reads the list off the primary `source` — so the fixture names the slot on both,
    # which is legal either way and lets the live gate see the rows.
    "select": {
        "type": "select",
        "options": {"slot": "opts"},
        "source": {"slot": "opts", "default": "a"},
    },
    "text": text("text"),
    # A disc in the oklch plane (fluxen ADR 0048): the angle picks the hue, the radius the chroma, the
    # `attrs.light` pins the term a face cannot show, and what it packs is the written-out `L C H` triple a
    # colour member takes.
    "disc": {
        "type": "disc",
        "tag": "gate.disc",
        "attrs": {"light": 0.7},
        "source": {"default": "0.7 0.12 200"},
    },
}

STATIC = frozenset({"image", "path"})