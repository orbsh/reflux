// GENERATED from schema/accrete.schema.json + profile/profile.json by tools/gen_sdk.py — do not edit.
//
// The node builders: one function per exposed accrete type, in the profile's keyword order.
//
// Key order is load-bearing. On the Python side a node's keys come out in its class's declaration
// order (pydantic serializes in declaration order, and that order came from the schema), attrs in
// the attrs class's order, and a bind entry in its arm's order — which is *not* alphabetical,
// because serde's flattened unions declare `Bind1` as `default, type, kind, path, source`. This
// module writes into an order-preserving map in the same orders, so a frame built here is
// byte-identical to the same frame built by the Python SDK. The crate therefore depends on
// serde_json's `preserve_order`; without it `Map` is a BTreeMap and every key would come out sorted.
//
// Regenerate: python3 tools/gen_sdk.py      Verify: python3 tools/gen_sdk.py --check

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

/// The closed set of variant names the profile declares for `case`.
///
/// Each name is the profile's, and the class string behind it is the profile's too. This is
/// the only way a class reaches the wire.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CaseVariant {
    Card,
}

impl CaseVariant {
    pub fn token(self) -> &'static str {
        match self {
            Self::Card => "rx-card",
        }
    }
}

/// The closed set of variant names the profile declares for `text`.
///
/// Each name is the profile's, and the class string behind it is the profile's too. This is
/// the only way a class reaches the wire.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TextVariant {
    Heading1,
    Heading2,
    Heading3,
    Code,
    Muted,
    Danger,
}

impl TextVariant {
    pub fn token(self) -> &'static str {
        match self {
            Self::Heading1 => "rx-heading-1",
            Self::Heading2 => "rx-heading-2",
            Self::Heading3 => "rx-heading-3",
            Self::Code => "rx-code",
            Self::Muted => "rx-muted",
            Self::Danger => "rx-danger",
        }
    }
}

/// accrete's `JsType`: what an input's boundary value is (a sibling of the variant, not one).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum JsType {
    Bool,
    Number,
    Text,
    Password,
    Button,
    Submit,
}

impl JsType {
    pub fn token(self) -> &'static str {
        match self {
            Self::Bool => "bool",
            Self::Number => "number",
            Self::Text => "text",
            Self::Password => "password",
            Self::Button => "button",
            Self::Submit => "submit",
        }
    }
}

/// Build a `case` node (the wire type `case`).
pub fn case(children: &[Value], grid: Option<Value>, horizontal: Option<bool>, id: Option<&str>, variant: Option<CaseVariant>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = variant {
        put(&mut attrs, "class", array(&[s(v.token())]));
    }
    if let Some(v) = grid {
        put(&mut attrs, "grid", v.clone());
    }
    if let Some(v) = horizontal {
        put(&mut attrs, "horizontal", Value::Bool(v));
    }
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if !children.is_empty() {
        put(&mut node, "children", array(children));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "type", s("case"));
    Value::Object(node)
}

/// Build a `placeholder` node (the wire type `placeholder`).
pub fn placeholder(children: &[Value], horizontal: Option<bool>, source: Option<&str>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = horizontal {
        put(&mut attrs, "horizontal", Value::Bool(v));
    }
    let mut bind = Map::new();
    if let Some(v) = source {
        let entry = ordered(&[("source", s(v)), ("kind", s("source"))], &["default", "type", "kind", "path", "source"]);
        put(&mut bind, "value", entry);
    }
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if !bind.is_empty() {
        put(&mut node, "bind", Value::Object(bind));
    }
    if !children.is_empty() {
        put(&mut node, "children", array(children));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "type", s("placeholder"));
    Value::Object(node)
}

/// Build a `chart` node (the wire type `chart`).
pub fn chart(value: Option<&str>, horizontal: Option<bool>, url: Option<&str>, source: Option<&str>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = horizontal {
        put(&mut attrs, "horizontal", Value::Bool(v));
    }
    let mut bind = Map::new();
    {
        let given = [value.is_some(), source.is_some()].into_iter().filter(|v| *v).count();
        assert!(given <= 1, "chart: bind[value] takes one 落点 at a time, got {}", given);
    }
    if let Some(v) = value {
        let entry = ordered(&[("default", s(v)), ("kind", s("default"))], &["default", "type", "kind"]);
        put(&mut bind, "value", entry);
    } else if let Some(v) = source {
        let entry = ordered(&[("source", s(v)), ("kind", s("source"))], &["default", "type", "kind", "path", "source"]);
        put(&mut bind, "value", entry);
    }
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if !bind.is_empty() {
        put(&mut node, "bind", Value::Object(bind));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "url", s(url.unwrap_or("/assets/g2chart/index.js")));
    put(&mut node, "type", s("chart"));
    Value::Object(node)
}

/// Build a `diagram` node (the wire type `diagram`).
pub fn diagram(value: Option<&str>, horizontal: Option<bool>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = horizontal {
        put(&mut attrs, "horizontal", Value::Bool(v));
    }
    let mut bind = Map::new();
    if let Some(v) = value {
        let entry = ordered(&[("default", s(v)), ("kind", s("default"))], &["default", "type", "kind"]);
        put(&mut bind, "value", entry);
    }
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if !bind.is_empty() {
        put(&mut node, "bind", Value::Object(bind));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "type", s("diagram"));
    Value::Object(node)
}

/// Build a `canvas` node (the wire type `canvas`).
pub fn canvas(value: Option<&str>, height: Option<&str>, width: Option<&str>, url: Option<&str>, source: Option<&str>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = height {
        put(&mut attrs, "height", s(v));
    }
    if let Some(v) = width {
        put(&mut attrs, "width", s(v));
    }
    let mut bind = Map::new();
    {
        let given = [value.is_some(), source.is_some()].into_iter().filter(|v| *v).count();
        assert!(given <= 1, "canvas: bind[value] takes one 落点 at a time, got {}", given);
    }
    if let Some(v) = value {
        let entry = ordered(&[("default", s(v)), ("kind", s("default"))], &["default", "type", "kind"]);
        put(&mut bind, "value", entry);
    } else if let Some(v) = source {
        let entry = ordered(&[("source", s(v)), ("kind", s("source"))], &["default", "type", "kind", "path", "source"]);
        put(&mut bind, "value", entry);
    }
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if !bind.is_empty() {
        put(&mut node, "bind", Value::Object(bind));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    if let Some(v) = url {
        put(&mut node, "url", s(v));
    }
    put(&mut node, "type", s("canvas"));
    Value::Object(node)
}

/// Build a `editor` node (the wire type `editor`).
pub fn editor(value: Option<&str>, height: Option<&str>, width: Option<&str>, url: Option<&str>, source: Option<&str>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = height {
        put(&mut attrs, "height", s(v));
    }
    if let Some(v) = width {
        put(&mut attrs, "width", s(v));
    }
    let mut bind = Map::new();
    {
        let given = [value.is_some(), source.is_some()].into_iter().filter(|v| *v).count();
        assert!(given <= 1, "editor: bind[value] takes one 落点 at a time, got {}", given);
    }
    if let Some(v) = value {
        let entry = ordered(&[("default", s(v)), ("kind", s("default"))], &["default", "type", "kind"]);
        put(&mut bind, "value", entry);
    } else if let Some(v) = source {
        let entry = ordered(&[("source", s(v)), ("kind", s("source"))], &["default", "type", "kind", "path", "source"]);
        put(&mut bind, "value", entry);
    }
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if !bind.is_empty() {
        put(&mut node, "bind", Value::Object(bind));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "url", s(url.unwrap_or("/assets/editor/index.js")));
    put(&mut node, "type", s("editor"));
    Value::Object(node)
}

/// Build a `float` node (the wire type `float`).
pub fn float(children: &[Value], left: Option<&str>, right: Option<&str>, top: Option<&str>, bottom: Option<&str>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = left {
        put(&mut attrs, "left", s(v));
    }
    if let Some(v) = right {
        put(&mut attrs, "right", s(v));
    }
    if let Some(v) = top {
        put(&mut attrs, "top", s(v));
    }
    if let Some(v) = bottom {
        put(&mut attrs, "bottom", s(v));
    }
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if !children.is_empty() {
        put(&mut node, "children", array(children));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "type", s("float"));
    Value::Object(node)
}

/// Build a `layer` node (the wire type `layer`).
pub fn layer(children: &[Value], dismiss: Option<bool>, source: Option<&str>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = dismiss {
        put(&mut attrs, "dismiss", Value::Bool(v));
    }
    let mut bind = Map::new();
    if let Some(v) = source {
        let entry = ordered(&[("source", s(v)), ("kind", s("source"))], &["default", "type", "kind", "path", "source"]);
        put(&mut bind, "value", entry);
    }
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if !bind.is_empty() {
        put(&mut node, "bind", Value::Object(bind));
    }
    if !children.is_empty() {
        put(&mut node, "children", array(children));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "type", s("layer"));
    Value::Object(node)
}

/// Build a `portal` node (the wire type `portal`).
pub fn portal(children: &[Value], to: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = to {
        put(&mut attrs, "to", s(v));
    }
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if !children.is_empty() {
        put(&mut node, "children", array(children));
    }
    put(&mut node, "type", s("portal"));
    Value::Object(node)
}

/// Build a `fold` node (the wire type `fold`).
pub fn fold(children: &[Value], float_body: Option<bool>, replace_header: Option<bool>, value: Option<&str>, item: Option<&[Value]>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = float_body {
        put(&mut attrs, "float_body", Value::Bool(v));
    }
    if let Some(v) = replace_header {
        put(&mut attrs, "replace_header", Value::Bool(v));
    }
    let mut bind = Map::new();
    if let Some(v) = value {
        let entry = ordered(&[("default", s(v)), ("kind", s("default"))], &["default", "type", "kind"]);
        put(&mut bind, "value", entry);
    }
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if !bind.is_empty() {
        put(&mut node, "bind", Value::Object(bind));
    }
    if !children.is_empty() {
        put(&mut node, "children", array(children));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    if let Some(v) = item {
        if !v.is_empty() {
            put(&mut node, "item", array(v));
        }
    }
    put(&mut node, "type", s("fold"));
    Value::Object(node)
}

/// Build a `form` node (the wire type `form`).
pub fn form(children: &[Value], instant: Option<bool>, event: Option<&str>, local: Option<&str>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = instant {
        put(&mut attrs, "instant", Value::Bool(v));
    }
    let mut bind = Map::new();
    {
        let given = [event.is_some(), local.is_some()].into_iter().filter(|v| *v).count();
        assert!(given <= 1, "form: bind[value] takes one 落点 at a time, got {}", given);
    }
    if let Some(v) = event {
        let entry = ordered(&[("event", s(v)), ("kind", s("event"))], &["default", "type", "event", "kind"]);
        put(&mut bind, "value", entry);
    } else if let Some(v) = local {
        let entry = ordered(&[("slot", s(v)), ("kind", s("local"))], &["default", "type", "event", "kind", "path", "slot"]);
        put(&mut bind, "value", entry);
    }
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if !bind.is_empty() {
        put(&mut node, "bind", Value::Object(bind));
    }
    if !children.is_empty() {
        put(&mut node, "children", array(children));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "type", s("form"));
    Value::Object(node)
}

/// Build a `popup` node (the wire type `popup`).
pub fn popup(children: &[Value], direction: Option<Value>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = direction {
        put(&mut attrs, "direction", v.clone());
    }
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if !children.is_empty() {
        put(&mut node, "children", array(children));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "type", s("popup"));
    Value::Object(node)
}

/// Build a `svg` node (the wire type `svg`).
pub fn svg(children: &[Value], height: Option<&str>, width: Option<&str>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = height {
        put(&mut attrs, "height", s(v));
    }
    if let Some(v) = width {
        put(&mut attrs, "width", s(v));
    }
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if !children.is_empty() {
        put(&mut node, "children", array(children));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "type", s("svg"));
    Value::Object(node)
}

/// Build a `group` node (the wire type `group`).
pub fn group(children: &[Value], style: Option<Value>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = style {
        put(&mut attrs, "style", v.clone());
    }
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if !children.is_empty() {
        put(&mut node, "children", array(children));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "type", s("group"));
    Value::Object(node)
}

/// Build a `path` node (the wire type `path`).
pub fn path(value: Option<&str>, horizontal: Option<bool>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = horizontal {
        put(&mut attrs, "horizontal", Value::Bool(v));
    }
    let mut bind = Map::new();
    if let Some(v) = value {
        let entry = ordered(&[("default", s(v)), ("kind", s("default"))], &["default", "type", "kind"]);
        put(&mut bind, "value", entry);
    }
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if !bind.is_empty() {
        put(&mut node, "bind", Value::Object(bind));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "type", s("path"));
    Value::Object(node)
}

/// Build a `rack` node (the wire type `rack`).
pub fn rack(scroll: Option<bool>, source: Option<&str>, item: Option<&[Value]>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    put(&mut attrs, "scroll", Value::Bool(scroll.unwrap_or(false)));
    let mut bind = Map::new();
    if let Some(v) = source {
        let entry = ordered(&[("source", s(v)), ("kind", s("source"))], &["default", "type", "kind", "path", "source"]);
        put(&mut bind, "value", entry);
    }
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if !bind.is_empty() {
        put(&mut node, "bind", Value::Object(bind));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    if let Some(v) = item {
        if !v.is_empty() {
            put(&mut node, "item", array(v));
        }
    }
    put(&mut node, "type", s("rack"));
    Value::Object(node)
}

/// Build a `pages` node (the wire type `pages`).
pub fn pages(horizontal: Option<bool>, display: Option<Value>, source: Option<&str>, select_source: Option<&str>, select_local: Option<&str>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = horizontal {
        put(&mut attrs, "horizontal", Value::Bool(v));
    }
    let mut bind = Map::new();
    if let Some(v) = source {
        let entry = ordered(&[("source", s(v)), ("kind", s("source"))], &["default", "type", "kind", "path", "source"]);
        put(&mut bind, "value", entry);
    }
    {
        let given = [select_source.is_some(), select_local.is_some()].into_iter().filter(|v| *v).count();
        assert!(given <= 1, "pages: bind[select] takes one 落点 at a time, got {}", given);
    }
    if let Some(v) = select_source {
        let entry = ordered(&[("source", s(v)), ("kind", s("source"))], &["default", "type", "kind", "path", "source"]);
        put(&mut bind, "select", entry);
    } else if let Some(v) = select_local {
        let entry = ordered(&[("slot", s(v)), ("kind", s("local"))], &["default", "type", "event", "kind", "path", "slot"]);
        put(&mut bind, "select", entry);
    }
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if !bind.is_empty() {
        put(&mut node, "bind", Value::Object(bind));
    }
    if let Some(v) = display {
        put(&mut node, "display", v.clone());
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "type", s("pages"));
    Value::Object(node)
}

/// Build a `button` node (the wire type `button`).
pub fn button(value: Option<&str>, oneshot: Option<bool>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    put(&mut attrs, "oneshot", Value::Bool(oneshot.unwrap_or(false)));
    let mut bind = Map::new();
    if let Some(v) = value {
        let entry = ordered(&[("default", s(v)), ("kind", s("submit"))], &["default", "type", "kind"]);
        put(&mut bind, "value", entry);
    }
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if !bind.is_empty() {
        put(&mut node, "bind", Value::Object(bind));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "type", s("button"));
    Value::Object(node)
}

/// Build a `image` node (the wire type `image`).
pub fn image(value: Option<&str>, desc: Option<&str>, height: Option<&str>, thumb: Option<bool>, width: Option<&str>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = desc {
        put(&mut attrs, "desc", s(v));
    }
    if let Some(v) = height {
        put(&mut attrs, "height", s(v));
    }
    put(&mut attrs, "thumb", Value::Bool(thumb.unwrap_or(false)));
    if let Some(v) = width {
        put(&mut attrs, "width", s(v));
    }
    let mut bind = Map::new();
    if let Some(v) = value {
        let entry = ordered(&[("default", s(v)), ("kind", s("default"))], &["default", "type", "kind"]);
        put(&mut bind, "value", entry);
    }
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if !bind.is_empty() {
        put(&mut node, "bind", Value::Object(bind));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "type", s("image"));
    Value::Object(node)
}

/// Build a `input` node (the wire type `input`).
pub fn input(horizontal: Option<bool>, event: Option<&str>, field: Option<&str>, payload: Option<Value>, kind: Option<JsType>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = horizontal {
        put(&mut attrs, "horizontal", Value::Bool(v));
    }
    let mut bind = Map::new();
    {
        let given = [event.is_some(), field.is_some()].into_iter().filter(|v| *v).count();
        assert!(given <= 1, "input: bind[value] takes one 落点 at a time, got {}", given);
    }
    if payload.is_some() || kind.is_some() {
        assert!(field.is_some(), "input: payload / kind need a落点 to ride on");
    }
    if let Some(v) = event {
        let entry = ordered(&[("event", s(v)), ("kind", s("event"))], &["default", "type", "event", "kind"]);
        put(&mut bind, "value", entry);
    } else if let Some(v) = field {
        let mut fields: Vec<(&str, Value)> = vec![("field", s(v))];
        if let Some(p) = payload {
            fields.push(("payload", p));
        }
        if let Some(j) = kind {
            fields.push(("type", s(j.token())));
        }
        fields.push(("kind", s("field")));
        put(&mut bind, "value", ordered(&fields, &["default", "type", "field", "kind", "payload"]));
    }
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if !bind.is_empty() {
        put(&mut node, "bind", Value::Object(bind));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "type", s("input"));
    Value::Object(node)
}

/// Build a `select` node (the wire type `select`).
pub fn select(horizontal: Option<bool>, value: Option<&str>, source: Option<&str>, event: Option<&str>, options_source: Option<&str>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = horizontal {
        put(&mut attrs, "horizontal", Value::Bool(v));
    }
    let mut bind = Map::new();
    {
        let given = [value.is_some(), source.is_some(), event.is_some()].into_iter().filter(|v| *v).count();
        assert!(given <= 1, "select: bind[value] takes one 落点 at a time, got {}", given);
    }
    if let Some(v) = value {
        let entry = ordered(&[("default", s(v)), ("kind", s("default"))], &["default", "type", "kind"]);
        put(&mut bind, "value", entry);
    } else if let Some(v) = source {
        let entry = ordered(&[("source", s(v)), ("kind", s("source"))], &["default", "type", "kind", "path", "source"]);
        put(&mut bind, "value", entry);
    } else if let Some(v) = event {
        let entry = ordered(&[("event", s(v)), ("kind", s("event"))], &["default", "type", "event", "kind"]);
        put(&mut bind, "value", entry);
    }
    if let Some(v) = options_source {
        let entry = ordered(&[("source", s(v)), ("kind", s("source"))], &["default", "type", "kind", "path", "source"]);
        put(&mut bind, "options", entry);
    }
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if !bind.is_empty() {
        put(&mut node, "bind", Value::Object(bind));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "type", s("select"));
    Value::Object(node)
}

/// Build a `table` node (the wire type `table`).
pub fn table(children: &[Value], id: Option<&str>) -> Value {
    let mut node = Map::new();
    if !children.is_empty() {
        put(&mut node, "children", array(children));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "type", s("table"));
    Value::Object(node)
}

/// Build a `thead` node (the wire type `thead`).
pub fn thead(children: &[Value], id: Option<&str>) -> Value {
    let mut node = Map::new();
    if !children.is_empty() {
        put(&mut node, "children", array(children));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "type", s("thead"));
    Value::Object(node)
}

/// Build a `tbody` node (the wire type `tbody`).
pub fn tbody(children: &[Value], id: Option<&str>) -> Value {
    let mut node = Map::new();
    if !children.is_empty() {
        put(&mut node, "children", array(children));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "type", s("tbody"));
    Value::Object(node)
}

/// Build a `tr` node (the wire type `tr`).
pub fn tr(children: &[Value], id: Option<&str>) -> Value {
    let mut node = Map::new();
    if !children.is_empty() {
        put(&mut node, "children", array(children));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "type", s("tr"));
    Value::Object(node)
}

/// Build a `th` node (the wire type `th`).
pub fn th(children: &[Value], id: Option<&str>) -> Value {
    let mut node = Map::new();
    if !children.is_empty() {
        put(&mut node, "children", array(children));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "type", s("th"));
    Value::Object(node)
}

/// Build a `td` node (the wire type `td`).
pub fn td(children: &[Value], id: Option<&str>) -> Value {
    let mut node = Map::new();
    if !children.is_empty() {
        put(&mut node, "children", array(children));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "type", s("td"));
    Value::Object(node)
}

/// Build a `text` node (the wire type `text`).
pub fn text(value: Option<&str>, format: Option<&str>, source: Option<&str>, id: Option<&str>, variant: Option<TextVariant>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = variant {
        put(&mut attrs, "class", array(&[s(v.token())]));
    }
    if let Some(v) = format {
        put(&mut attrs, "format", s(v));
    }
    let mut bind = Map::new();
    {
        let given = [value.is_some(), source.is_some()].into_iter().filter(|v| *v).count();
        assert!(given <= 1, "text: bind[value] takes one 落点 at a time, got {}", given);
    }
    if let Some(v) = value {
        let entry = ordered(&[("default", s(v)), ("kind", s("default"))], &["default", "type", "kind"]);
        put(&mut bind, "value", entry);
    } else if let Some(v) = source {
        let entry = ordered(&[("source", s(v)), ("kind", s("source"))], &["default", "type", "kind", "path", "source"]);
        put(&mut bind, "value", entry);
    }
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if !bind.is_empty() {
        put(&mut node, "bind", Value::Object(bind));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "type", s("text"));
    Value::Object(node)
}

/// Build a `textarea` node (the wire type `textarea`).
pub fn textarea(horizontal: Option<bool>, value: Option<&str>, source: Option<&str>, event: Option<&str>, placeholder: Option<&str>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = horizontal {
        put(&mut attrs, "horizontal", Value::Bool(v));
    }
    let mut bind = Map::new();
    {
        let given = [value.is_some(), source.is_some(), event.is_some()].into_iter().filter(|v| *v).count();
        assert!(given <= 1, "textarea: bind[value] takes one 落点 at a time, got {}", given);
    }
    if let Some(v) = value {
        let entry = ordered(&[("default", s(v)), ("kind", s("default"))], &["default", "type", "kind"]);
        put(&mut bind, "value", entry);
    } else if let Some(v) = source {
        let entry = ordered(&[("source", s(v)), ("kind", s("source"))], &["default", "type", "kind", "path", "source"]);
        put(&mut bind, "value", entry);
    } else if let Some(v) = event {
        let entry = ordered(&[("event", s(v)), ("kind", s("event"))], &["default", "type", "event", "kind"]);
        put(&mut bind, "value", entry);
    }
    if let Some(v) = placeholder {
        let entry = ordered(&[("default", s(v)), ("kind", s("default"))], &["default", "type", "kind"]);
        put(&mut bind, "placeholder", entry);
    }
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if !bind.is_empty() {
        put(&mut node, "bind", Value::Object(bind));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    put(&mut node, "type", s("textarea"));
    Value::Object(node)
}
