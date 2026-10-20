"""One minimal, legal node per exposed accrete type — the fixture T3′ and its offline test share.

`profile.exposed()` is the authority on which types a producer may draw; `test_types_drawable`
asserts this table is exactly that set, so adding a type to the profile without giving it a node
fails there rather than quietly shrinking what the gate draws.

Two marks, both facts rather than taste:

- `ASSET_BACKED` — `canvas` / `chart` / `editor` mount an external ES module (`mount_module(url)`),
  and `diagram` fetches `/assets/mermaid.min.js` on render. Their capability is a deployment
  artifact, not vocabulary, so the live gate draws everything else and these four stay on the
  offline table (a stub module would prove the stub, not the type). The page really does 404 the
  mermaid asset today — measured, not assumed.
- `STATIC` — nodes whose value is a URL/asset rather than text; harmless to draw, but nothing to
  assert about them beyond "it did not error".
"""

from __future__ import annotations

from typing import Any

ASSET_BACKED = frozenset({"canvas", "chart", "editor", "diagram"})


def text(value: str, **rest: Any) -> dict:
    """A `text` leaf carrying `value` — the cheapest way to put something visible in a container."""
    return {"type": "text", "bind": {"value": {"kind": "default", "default": value}}, **rest}


NODES: dict[str, dict] = {
    "case": {"type": "case", "children": [text("case")]},
    "placeholder": {"type": "placeholder", "children": [text("placeholder")]},
    "chart": {"type": "chart", "bind": {"value": {"kind": "default", "default": {"spec": {"type": "interval"}}}}},
    "diagram": {"type": "diagram", "bind": {"value": {"kind": "default", "default": "graph TD"}}},
    "canvas": {"type": "canvas", "url": "/module.js"},
    "editor": {"type": "editor", "url": "/module.js"},
    "float": {"type": "float", "children": [text("float")]},
    "layer": {"type": "layer", "children": [text("layer")]},
    "portal": {"type": "portal", "attrs": {"to": "#main"}, "children": [text("portal")]},
    # A fold's header is `item[0]`; its children are the body and stay hidden until it is opened.
    "fold": {"type": "fold", "item": [text("fold")], "children": [text("fold-body")]},
    # A `button` only renders inside a form (it toggles the form's confirm signal), so the form
    # carries one: the nested button is also the proof that the form registered itself.
    "form": {"type": "form", "children": [text("form"), {"type": "button", "bind": {"value": {"kind": "submit"}}}]},
    # A popup is `children[0]` = the trigger, `children[1]` = the modal; fewer renders nothing.
    "popup": {"type": "popup", "children": [text("popup"), text("popup-modal")]},
    "svg": {"type": "svg", "children": [text("svg")]},
    "group": {"type": "group", "children": [text("group")]},
    "path": {"type": "path", "bind": {"value": {"kind": "default", "default": "M0 0 L1 1"}}},
    "rack": {"type": "rack", "item": [text("row")], "bind": {"value": {"kind": "source", "source": "rows"}}},
    # `value` is the list of page rows (key = row id); `select` is the vals plane, and because
    # `inject` lands the Outflow wrapper there (`{event, data}`) the key is read through `path`.
    "pages": {
        "type": "pages",
        "display": "render",
        "bind": {
            "value": {"kind": "source", "source": "sel"},
            "select": {"kind": "local", "slot": "pages-key", "path": "/data"},
        },
    },
    "button": {"type": "button", "bind": {"value": {"kind": "submit"}}},
    # `image` renders an `<img>` only when it has a `default` value **and** some attrs
    # (`&& let Some(x) = accrete.attrs` in the renderer) — without attrs it draws an empty div.
    "image": {"type": "image", "attrs": {"desc": "a dot"}, "bind": {"value": {"kind": "default", "default": "/static/logo.svg"}}},
    # No `bind.value` prefill: the renderer starts an input from its js-kind's default ("" for
    # text) and reads neither `default` nor `source` for display — measured, and the reason the
    # profile no longer offers them for `input`.
    "input": {"type": "input", "bind": {"value": {"kind": "event", "event": "gate.input"}}},
    "select": {
        "type": "select",
        "bind": {"options": {"kind": "source", "source": "opts"}, "value": {"kind": "default", "default": "a"}},
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
    "textarea": {"type": "textarea", "bind": {"value": {"kind": "default", "default": "textarea"}}},
}

STATIC = frozenset({"image", "path"})