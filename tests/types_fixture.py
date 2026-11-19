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
        "attrs": {"place": "inline", "replace_header": True},
        "children": [text("panel-header"), text("panel-body")],
    },
    # ADR 0032: the bundle packs its fields into one object and owns the exit (`sink`) and the
    # timing (`attrs.submit`); each field's name is its own `tag`, never the sink's address.
    "bundle": {
        "type": "bundle",
        "attrs": {"submit": ["enter", "button"]},
        "sink": {"slot": "gate.bundle"},
        "children": [
            field("name"),
            field("body", multiline=True, placeholder={"default": "写点什么"}),
            {"type": "select", "tag": "kind", "options": {"slot": "opts"}, "source": {"default": "a"}},
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
    "rack": {"type": "rack", "item": [text("row")], "source": {"slot": "rows"}},
    # `source` is the list of page rows (key = row id); `select` is the vals plane, and because the
    # uplink lands the Outflow wrapper there (`{event, data}`) the key is read through `path`.
    "pages": {
        "type": "pages",
        "display": "render",
        "source": {"slot": "sel"},
        "select": {"slot": "pages-key", "scope": "local", "path": "/data"},
    },
    # A button's label is its `source`, its uplink its `sink` (ADR 0032 dropped the `submit` kind).
    "button": {"type": "button", "source": {"default": "提交"}, "sink": {"slot": "submit"}},
    # `image` renders an `<img>` only when it has a `default` value **and** some attrs
    # (`&& let Some(x) = accrete.attrs` in the renderer) — without attrs it draws an empty div.
    "image": {"type": "image", "attrs": {"desc": "a dot"}, "source": {"default": "/static/logo.svg"}},
    # No `source` prefill: the renderer starts an input from its js-kind's default ("" for text)
    # and reads neither `default` nor `source` for display — measured, and the reason the profile
    # no longer offers a constant source for `input`.
    "input": {"type": "input", "sink": {"slot": "gate.input"}},
    "select": {
        "type": "select",
        "options": {"slot": "opts"},
        "source": {"default": "a"},
    },
    "table": {
        "type": "table",
        "children": [
            {"type": "thead", "children": [{"type": "tr", "children": [{"type": "th", "children": [text("head")]}]}]},
            {"type": "tbody", "children": [{"type": "tr", "children": [{"type": "td", "children": [text("cell")]}]}]},
        ],
    },
    "thead": {"type": "thead", "children": [text("thead")]},
    "tbody": {"type": "tbody", "children": [text("tbody")]},
    "tr": {"type": "tr", "children": [text("tr")]},
    "th": {"type": "th", "children": [text("th")]},
    "td": {"type": "td", "children": [text("td")]},
    "text": text("text"),
}

STATIC = frozenset({"image", "path"})