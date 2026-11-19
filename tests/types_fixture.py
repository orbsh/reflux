"""One minimal, legal node per exposed accrete type — the fixture T3′ and its offline test share.

`profile.exposed()` is the authority on which types a producer may draw; `test_types_drawable`
asserts this table is exactly that set, so adding a type to the profile without giving it a node
fails there rather than quietly shrinking what the gate draws.

The spelling is ADR 0031/0032's, not the retired one: every value rides a channel (`source` in,
`sink` out) as one `Bind`, a `bundle` packs its fields (each field named by its own `tag`, the exit
on the bundle's `sink`, the timing in `attrs.submit`), and a multi-line field is `input` with
`multiline`. The types that used to be separate are folded: `fold`/`popup`/`layer`/`float`/`portal`
are one `panel` (`place` + `state`), `form` is `bundle`, `textarea` is `input.multiline`.

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
    """A bundled field: `tag` is the key the enclosing bundle packs it under, `sink` its exit."""
    return {"type": "input", "tag": tag, "sink": {"slot": tag}, **rest}

# A button's label is its `source`, its uplink its `sink` (ADR 0032 dropped the `submit` kind). It
# lives inside a `bundle` — that is the only place the renderer mounts one.
BUTTON: dict = {"type": "button", "source": {"default": "提交"}, "sink": {"slot": "gate.button"}}


NODES: dict[str, dict] = {
    # One node, two states (ADR 0027): `children` is the static shape, a `source` binding is the
    # region a slot fills. The fixture takes the static form; the shell's `routes` reader is the
    # other one, and it is what puts a reserved id on the DOM.
    "frame": {"type": "frame", "children": [text("frame")]},
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
    # ADR 0032: the bundle packs its fields into one object and owns the exit (`sink`) and the
    # timing (`attrs.submit`); each field's name is its own `tag`, never the sink's address. Its
    # button is the press the `submit: [button]` names — a button renders nowhere else.
    "bundle": {
        "type": "bundle",
        "attrs": {"submit": ["enter", "button"]},
        "sink": {"slot": "gate.bundle"},
        "children": [
            field("name"),
            field("body", multiline=True, placeholder={"default": "写点什么"}),
            {"type": "select", "tag": "kind", "options": {"slot": "opts"}, "source": {"default": "a"}},
            BUTTON,
        ],
    },
    # The drag pair (ADR 0019): the source carries the cargo, the landing point owns the event name
    # and what it accepts. A drop is one uplink frame on the dock's own id.
    "grab": {"type": "grab", "id": "t3-grab", "kind": "note", "payload": {"n": 1}, "children": [text("grab")]},
    "dock": {
        "type": "dock",
        "id": "t3-dock",
        "attrs": {"accept": ["note"]},
        "sink": {"slot": "gate.dock"},
        "children": [text("dock")],
    },
    "svg": {"type": "svg", "children": [text("svg")]},
    "group": {"type": "group", "children": [text("group")]},
    "path": {"type": "path", "source": {"default": "M0 0 L1 1"}},
    # ADR 0031 §4: `rack` and `pages` are this one node with different steppers (`stage`/`step`), and
    # the table family is *not* markup here — `columns` makes each item a `record` whose fields are
    # named by their own `attrs.selector`. The header is a hook (one selector for the whole row).
    "tiles": {
        "type": "tiles",
        "attrs": {
            "columns": [{"key": "name", "title": "Name"}, {"key": "qty", "align": "end"}],
            "header": {"selector": "gate-grid-head", "rows": 1},
            "stage": "all",
            "step": {"timer": 4000},
        },
        "source": {"slot": "rows"},
        "children": [
            {
                "type": "record",
                "attrs": {"selector": "gate-row"},
                "children": [
                    text("name", attrs={"selector": "name"}),
                    text("1", attrs={"selector": "qty"}),
                ],
            }
        ],
    },
    # A record is one item of a grid: named fields, each a child whose `selector` is the field's name.
    # No `id` here — an item that does not name itself is keyed by where it arrived (ADR 0031 §4).
    "record": {
        "type": "record",
        "children": [text("record-field", attrs={"selector": "name"})],
    },
    # A button's label is its `source`, its uplink its `sink` (ADR 0032 dropped the `submit` kind).
    "button": BUTTON,
    # `image` renders an `<img>` only when it has a `default` value **and** some attrs
    # (`&& let Some(x) = accrete.attrs` in the renderer) — without attrs it draws an empty div.
    "image": {"type": "image", "attrs": {"desc": "a dot"}, "source": {"default": "/static/logo.svg"}},
    # No `source` prefill: the renderer starts an input from its js-kind's default ("" for text)
    # and reads neither `default` nor `source` for display — measured, and the reason the profile
    # no longer offers a constant source for `input`.
    "input": {"type": "input", "sink": {"slot": "gate.input"}},
    # The option rows are a list plane: `options` is the wire's own field, and the renderer
    # currently reads the list off the primary `source` — so the fixture names the slot on both,
    # which is legal either way and lets the live gate see the rows.
    "select": {
        "type": "select",
        "options": {"slot": "opts"},
        "source": {"slot": "opts", "default": "a"},
    },
    "text": text("text"),
}

STATIC = frozenset({"image", "path"})