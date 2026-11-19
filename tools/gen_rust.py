"""The Rust emitter: the vocabulary, formatted as one Rust module of node builders.

    tools/vocabulary.py  →  sdks/rust/src/types.rs

Only the *node builders* are generated here. The op layer (`create`/`set`/…​) is hand-written in
`sdks/rust/src/wire.rs`, mirroring `reflux/wire.py` — the split between generated vocabulary and
hand-written wire is the same in both languages, on purpose: what the spec owns is *what a producer
may build*, not how a frame is shaped.

Two things this emitter must get right, both read from `vocabulary`, never guessed:

1. **Field order.** A node's keys come out in its class's declaration order, attrs in the attrs
   class's order, a `Bind` in *its* declaration order (`default, path, scope, slot, type` — serde's
   struct order, not alphabetical). The Rust side inserts into an order-preserving
   `serde_json::Map` (the crate enables `preserve_order`) in exactly those orders, so the bytes match
   Python's without either side sorting anything.
2. **What is closed.** The profile's variant names become real enums, so an unknown variant is a
   compile error rather than a class the stylesheet never heard of. Schema enums stay `&str`: the
   closure of the wire's own value domains is checked by the server's ingest for every producer
   alike, and this SDK does not re-check the fence.

Known narrowing, written down rather than hidden: a `Bind`'s `default` is a `String` — the minimal
SDK carries the shapes the reference app needs. A producer that needs a structured default builds
that entry by hand until a typed lane earns its name.
"""

from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import vocabulary  # noqa: E402

HEADER = '''// GENERATED from schema/accrete.schema.json + profile/profile.json by tools/gen_sdk.py — do not edit.
//
// The node builders: one function per exposed accrete type, in the profile's keyword order.
//
// Key order is load-bearing. On the Python side a node's keys come out in its class's declaration
// order (pydantic serializes in declaration order, and that order came from the schema), attrs in
// the attrs class's order, and a `Bind` in its own declaration order (`default, path, scope, slot,
// type` — serde's struct order, not alphabetical). This module writes into an order-preserving map
// in the same orders, so a frame built here is byte-identical to the same frame built by the Python
// SDK. The crate therefore depends on serde_json's `preserve_order`; without it `Map` is a BTreeMap
// and every key would come out sorted.
//
// Regenerate: python3 tools/gen_sdk.py      Verify: python3 tools/gen_sdk.py --check
//
// This file is deliberately not `cargo fmt`-shaped: the generator writes wide signatures, and
// formatting it would make `--check` fail on a clean tree. Format the hand-written files by name
// (`rustfmt src/lib.rs src/wire.rs src/markers.rs src/bin/frames.rs`) and leave this one alone.

#![allow(clippy::too_many_arguments)]

use serde_json::{Map, Value};

fn put(map: &mut Map<String, Value>, key: &str, value: Value) {
    map.insert(key.to_string(), value);
}

fn s(value: &str) -> Value {
    Value::String(value.to_string())
}

fn array(values: &[Value]) -> Value {
    Value::Array(values.to_vec())
}

/// A map whose keys come out in `order` — the wire's order is the type layer's declaration order,
/// so the emitter passes that order in rather than trusting insertion order at each call site.
fn ordered(fields: &[(&str, Value)], order: &[&str]) -> Value {
    let mut map = Map::new();
    for name in order {
        if let Some((_, value)) = fields.iter().find(|(key, _)| key == name) {
            put(&mut map, name, value.clone());
        }
    }
    Value::Object(map)
}

/// The same, for a `Bind`'s own fields (owned keys, because they are collected per call).
fn ordered_pairs(fields: &[(String, Value)], order: &[&str]) -> Value {
    let mut map = Map::new();
    for name in order {
        if let Some((_, value)) = fields.iter().find(|(key, _)| key == name) {
            put(&mut map, name, value.clone());
        }
    }
    Value::Object(map)
}

/// One value's address and scope (ADR 0031 §1-2): the wire's `Bind`.
///
/// Written as a struct literal, so a call site names what it sets:
///
///     Bind { slot: Some("draft".into()), scope: Some("local".into()), ..Default::default() }
///
/// `scope` is a closed set with `remote` as its default, and it is always written: the Python side
/// declares `scope: Scope = 'remote'`, so a value with no scope named serializes as `"remote"` and
/// the Rust object must read the same bytes. The narrowing this SDK carries: `default` is a
/// `String` (a structured default is built by hand).
#[derive(Clone, Default)]
pub struct Bind {
    pub slot: Option<String>,
    pub default: Option<String>,
    pub scope: Option<String>,
    pub path: Option<String>,
    pub js_type: Option<JsType>,
}

impl Bind {
    /// The wire's object, keys in the type layer's declaration order.
    pub fn value(&self) -> Value {
        let mut fields: Vec<(String, Value)> = Vec::new();
        if let Some(v) = &self.default {
            fields.push(("default".to_string(), s(v)));
        }
        if let Some(v) = &self.path {
            fields.push(("path".to_string(), s(v)));
        }
        fields.push(("scope".to_string(), s(self.scope.as_deref().unwrap_or("remote"))));
        if let Some(v) = &self.slot {
            fields.push(("slot".to_string(), s(v)));
        }
        if let Some(v) = self.js_type {
            fields.push(("type".to_string(), s(v.token())));
        }
        ordered_pairs(&fields, BIND_ORDER)
    }
}

/// A channel with nothing to say is absent, not an empty object.
fn emit(bind: Bind) -> Option<Value> {
    if bind.slot.is_none() && bind.default.is_none() && bind.path.is_none() && bind.js_type.is_none() {
        return None;
    }
    Some(bind.value())
}

/// A read channel with the positional constant folded in as its `default` — what the Python
/// builder's `value=` means. An explicit `default` on the `Bind` wins.
fn read(given: Option<Bind>, constant: Option<&str>) -> Option<Value> {
    let mut bind = given.unwrap_or_default();
    if bind.default.is_none() {
        bind.default = constant.map(|c| c.to_string());
    }
    emit(bind)
}
'''

JS_TYPE = {
    "bool": "Bool",
    "number": "Number",
    "text": "Text",
    "password": "Password",
    "button": "Button",
    "submit": "Submit",
}


def camel(name: str) -> str:
    """`heading-1` → `Heading1`, `float_body` → `FloatBody`."""
    parts = [p for p in re.split(r"[^0-9A-Za-z]+", name) if p]
    return "".join(p[:1].upper() + p[1:] for p in parts)


def wire_name(name: str) -> str:
    """The type layer spells the wire's `class` as `class_` (a Python keyword); the wire does not."""
    return "class" if name == "class_" else name


def rust_type(kind: str) -> str:
    base = {"str": "&str", "bool": "bool", "int": "i64", "float": "f64", "strlist": "&[&str]",
            "json": "Value"}.get(kind, "Value")
    return f"Option<{base}>"


def value_of(kind: str, expr: str) -> str:
    return {
        "str": f"s({expr})",
        "bool": f"Value::Bool({expr})",
        "int": f"Value::from({expr})",
        "float": f"Value::from({expr})",
        # A set-valued attribute (ADR 0032's `submit`): the wire takes a bare string or a list,
        # the builder writes the list — the same normalisation the Python side's `as_set` does.
        "strlist": f"array(&{expr}.iter().map(|item| s(*item)).collect::<Vec<Value>>())",
        "json": f"{expr}.clone()",
    }.get(kind, f"{expr}.clone()")


def enum_for(type_name: str, tokens: dict[str, str]) -> list[str]:
    variants = [(camel(display), token) for display, token in tokens.items()]
    name = f"{camel(type_name)}Variant"
    return [
        f"/// The closed set of variant names the profile declares for `{type_name}`.",
        "///",
        "/// Each name is the profile's, and the class string behind it is the profile's too. This is",
        "/// the only way a class reaches the wire.",
        "#[derive(Clone, Copy, Debug, PartialEq, Eq)]",
        f"pub enum {name} {{",
        *[f"    {member}," for member, _ in variants],
        "}",
        "",
        f"impl {name} {{",
        "    pub fn token(self) -> &'static str {",
        "        match self {",
        *[f'            Self::{member} => "{token}",' for member, token in variants],
        "        }",
        "    }",
        "}",
        "",
    ]


def js_type_enum(values: list[str]) -> list[str]:
    return [
        "/// accrete's `JsType`: what an input's boundary value is (a sibling of the variant, not one).",
        "#[derive(Clone, Copy, Debug, PartialEq, Eq)]",
        "pub enum JsType {",
        *[f"    {JS_TYPE[v]}," for v in values],
        "}",
        "",
        "impl JsType {",
        "    pub fn token(self) -> &'static str {",
        "        match self {",
        *[f'            Self::{JS_TYPE[v]} => "{v}",' for v in values],
        "        }",
        "    }",
        "}",
        "",
    ]


def bind_order(orders: dict[str, list[str]]) -> list[str]:
    """The `Bind`'s field order, read from the type layer — emitted as the emitter's own constant."""
    order = orders.get("Bind") or []
    if not order:
        raise SystemExit("the type layer has no `Bind` class — regenerate with tools/gen_sdk.py")
    names = ", ".join(f'"{name}"' for name in order)
    return ["", f"const BIND_ORDER: &[&str] = &[{names}];", ""]


def signature(model) -> list[str]:
    params: list[str] = []
    if model.positional == "children":
        params.append("children: &[Value]")
    elif model.positional == "value":
        params.append("value: Option<&str>")
    for param in model.params:
        if param.lane in ("attrs", "extra"):
            params.append(f"{param.kwarg}: {rust_type(param.rkind)}")
        elif param.lane in ("channel", "value"):
            # One direction of a value: a complete `Bind`, or nothing.
            params.append(f"{param.kwarg}: Option<Bind>")
        elif param.lane == "item":
            params.append("item: Option<&[Value]>")
        elif param.lane == "id":
            # A type whose wire form has no `id` field gets no `id` keyword here. The Python
            # builders accept one and the type layer silently drops it (the schema says the field
            # does not exist); that is looseness on that side, not something to copy.
            if "id" in model.node_order:
                params.append("id: Option<&str>")
        elif param.lane == "variant":
            params.append(f"variant: Option<{camel(model.wire)}Variant>")
    return params


def field_lines(param, map_name: str, name: str) -> list[str]:
    """Insert one field, honouring the schema's default the way the Python builder does.

    A defaulted field is *written* when the caller omits it (Python's `drop_none` keeps `False` and
    keeps `'render'`; only `None` is dropped), so a `None` argument here means "use the default"
    rather than "leave it out". The one call this side cannot express is passing `None` to suppress a
    defaulted field — no caller does, and the wire reads the same either way.
    """
    kw = param.kwarg
    if param.default is not None:
        if param.rkind == "bool":
            literal = "true" if param.default == "True" else "false"
            return [f'    put(&mut {map_name}, "{name}", Value::Bool({kw}.unwrap_or({literal})));']
        if param.rkind == "str" and param.default.startswith("'"):
            literal = param.default.strip("'")
            return [f'    put(&mut {map_name}, "{name}", s({kw}.unwrap_or("{literal}")));']
    return [
        f"    if let Some(v) = {kw} {{",
        f'        put(&mut {map_name}, "{name}", {value_of(param.rkind, "v")});',
        "    }",
    ]


def attrs_block(model) -> list[str]:
    by_wire = {wire_name(param.wire): param for param in model.attrs}
    lines = ["    let mut attrs = Map::new();"]
    order = [wire_name(name) for name in model.attrs_order] or list(by_wire)
    for name in order:
        if name == "class" and model.variants:
            lines += [
                "    if let Some(v) = variant {",
                '        put(&mut attrs, "class", array(&[s(v.token())]));',
                "    }",
            ]
            continue
        param = by_wire.get(name)
        if param is None:
            continue
        lines += field_lines(param, "attrs", name)
    return lines


def values_block(model) -> list[str]:
    """One line per channel / named value: the `Bind` as the wire's object, or nothing."""
    lines: list[str] = []
    for channel in model.channels:
        if channel.name == "source" and model.positional == "value":
            lines.append("    let source = read(source, value);")
        else:
            lines.append(f"    let {channel.name} = {channel.name}.and_then(emit);")
    for param in model.values:
        lines.append(f"    let {param.kwarg} = {param.kwarg}.and_then(emit);")
    return lines


def node_block(model, has_attrs: bool) -> list[str]:
    by_wire = {wire_name(p.wire): p for p in model.params if p.lane in ("channel", "value", "extra")}
    lines = ["    let mut node = Map::new();"]
    for name in [wire_name(name) for name in model.node_order]:
        if name == "attrs":
            if has_attrs:
                lines += ["    if !attrs.is_empty() {", '        put(&mut node, "attrs", Value::Object(attrs));', "    }"]
        elif name == "children" and model.positional == "children":
            lines += ["    if !children.is_empty() {", '        put(&mut node, "children", array(children));', "    }"]
        elif name == "id":
            lines += ["    if let Some(v) = id {", '        put(&mut node, "id", s(v));', "    }"]
        elif name == "item" and model.item:
            lines += [
                "    if let Some(v) = item {",
                "        if !v.is_empty() {",
                '            put(&mut node, "item", array(v));',
                "        }",
                "    }",
            ]
        elif name == "type":
            lines.append(f'    put(&mut node, "type", s("{model.wire}"));')
        else:
            param = by_wire.get(name)
            if param is not None:
                lines += field_lines(param, "node", name)
    lines.append("    Value::Object(node)")
    return lines


def types_rs(models, schema: dict, orders: dict[str, list[str]]) -> str:
    parts = [HEADER]
    for model in models:
        if model.variants:
            parts += enum_for(model.wire, model.variants)
    js_values = (schema["$defs"].get("JsType") or {}).get("enum") or []
    if js_values:
        parts += js_type_enum(js_values)
    parts += bind_order(orders)
    for model in models:
        params = signature(model)
        has_attrs = bool(model.attrs or model.variants)
        body = (
            (attrs_block(model) if has_attrs else [])
            + values_block(model)
            + node_block(model, has_attrs)
        )
        parts += [
            f"/// Build a `{model.wire}` node (the wire type `{model.wire}`).",
            f"pub fn {model.wire}({', '.join(params)}) -> Value {{",
            *body,
            "}",
            "",
        ]
    return "\n".join(parts).rstrip("\n") + "\n"


def artifacts(models, schema: dict, root: pathlib.Path, types_src: str) -> dict:
    orders = vocabulary.read_orders(types_src)
    path = root / "sdks" / "rust" / "src" / "types.rs"
    return {path: types_rs(models, schema, orders)}