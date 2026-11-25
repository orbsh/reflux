// GENERATED from schema/accrete.schema.json + profile/profile.json by tools/gen_sdk.py — do not edit.
//
// The node builders: one function per exposed accrete type, in the profile's keyword order.
//
// Key order is load-bearing. On the Python side a node's keys come out in its class's declaration
// order (pydantic serializes in declaration order, and that order came from the schema), attrs in
// the attrs class's order, and a `Source` / `Sink` in its own declaration order (`default, path,
// scope, slot` / `dest, path, scope` — the type layer's order, not alphabetical). This module
// writes into an order-preserving map
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
/// so the emitter passes that order in rather than trusting insertion order at each call site. The
/// fields are owned because they are collected per call (an address's own fields, ADR 0039).
fn ordered_pairs(fields: &[(String, Value)], order: &[&str]) -> Value {
    let mut map = Map::new();
    for name in order {
        if let Some((_, value)) = fields.iter().find(|(key, _)| key == name) {
            put(&mut map, name, value.clone());
        }
    }
    Value::Object(map)
}

/// The read direction of one value (ADR 0039): where it comes from, who is authoritative about it,
/// which member of it, and what to show while the slot is empty.
///
/// Written as a struct literal, so a call site names what it sets:
///
///     Source { slot: Some("draft".into()), ..Default::default() }
///
/// `scope` is a closed set with `remote` as its default, and it is always written: the Python side
/// declares `scope: Scope = 'remote'`, so a value with no scope named serializes as `"remote"` and
/// the Rust object must read the same bytes. The narrowing this SDK carries: `default` is a
/// `String` (a structured default is built by hand).
#[derive(Clone, Default)]
pub struct Source {
    pub slot: Option<String>,
    pub default: Option<String>,
    pub scope: Option<String>,
    pub path: Option<String>,
}

impl Source {
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
        ordered_pairs(&fields, SOURCE_ORDER)
    }
}

/// The write direction of one value (ADR 0039): where it goes, and who is authoritative about it.
///
/// No `default`: a write has no value of its own to fall back on, and the wire refuses one. `dest`
/// is what an uplink is called (ADR 0023), so a `Sink` is the same object an outflow carries.
#[derive(Clone, Default)]
pub struct Sink {
    pub dest: Option<String>,
    pub scope: Option<String>,
    pub path: Option<String>,
}

impl Sink {
    /// The wire's object, keys in the type layer's declaration order.
    pub fn value(&self) -> Value {
        let mut fields: Vec<(String, Value)> = Vec::new();
        if let Some(v) = &self.dest {
            fields.push(("dest".to_string(), s(v)));
        }
        if let Some(v) = &self.path {
            fields.push(("path".to_string(), s(v)));
        }
        fields.push(("scope".to_string(), s(self.scope.as_deref().unwrap_or("remote"))));
        ordered_pairs(&fields, SINK_ORDER)
    }
}

/// A channel with nothing to say is absent, not an empty object (`scope` is always written, so it
/// never counts as something to say).
fn emit_read(source: Option<Source>) -> Option<Value> {
    let source = source?;
    if source.slot.is_none() && source.default.is_none() && source.path.is_none() {
        return None;
    }
    Some(source.value())
}

/// The same rule for a write: an address is a `dest`, a `path`, or both — neither is no channel.
fn emit_write(sink: Option<Sink>) -> Option<Value> {
    let sink = sink?;
    if sink.dest.is_none() && sink.path.is_none() {
        return None;
    }
    Some(sink.value())
}

/// A read channel with the positional constant folded in as its `default` — what the Python
/// builder's `value=` means. An explicit `default` on the `Source` wins.
fn read(given: Option<Source>, constant: Option<&str>) -> Option<Value> {
    let mut source = given.unwrap_or_default();
    if source.default.is_none() {
        source.default = constant.map(|c| c.to_string());
    }
    emit_read(Some(source))
}

/// The closed set of variant names the profile declares for `frame`.
///
/// Each name is the profile's, and the class string behind it is the profile's too. This is
/// the only way a class reaches the wire.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FrameVariant {
    Card,
}

impl FrameVariant {
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


const SOURCE_ORDER: &[&str] = &["default", "path", "scope", "slot"];
const SINK_ORDER: &[&str] = &["dest", "path", "scope"];

/// Build a `frame` node (the wire type `frame`).
pub fn frame(children: &[Value], accept: Option<Value>, draggable: Option<Value>, grid: Option<Value>, horizontal: Option<bool>, selector: Option<&str>, style: Option<Value>, source: Option<Source>, sink: Option<Sink>, id: Option<&str>, variant: Option<FrameVariant>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = accept {
        put(&mut attrs, "accept", v.clone());
    }
    if let Some(v) = variant {
        put(&mut attrs, "class", array(&[s(v.token())]));
    }
    if let Some(v) = draggable {
        put(&mut attrs, "draggable", v.clone());
    }
    if let Some(v) = grid {
        put(&mut attrs, "grid", v.clone());
    }
    if let Some(v) = horizontal {
        put(&mut attrs, "horizontal", Value::Bool(v));
    }
    if let Some(v) = selector {
        put(&mut attrs, "selector", s(v));
    }
    if let Some(v) = style {
        put(&mut attrs, "style", v.clone());
    }
    let source = emit_read(source);
    let sink = emit_write(sink);
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
    if let Some(v) = sink {
        put(&mut node, "sink", v.clone());
    }
    if let Some(v) = source {
        put(&mut node, "source", v.clone());
    }
    put(&mut node, "type", s("frame"));
    Value::Object(node)
}

/// Build a `canvas` node (the wire type `canvas`).
pub fn canvas(value: Option<&str>, height: Option<&str>, selector: Option<&str>, width: Option<&str>, source: Option<Source>, options: Option<Value>, url: Option<&str>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = height {
        put(&mut attrs, "height", s(v));
    }
    if let Some(v) = selector {
        put(&mut attrs, "selector", s(v));
    }
    if let Some(v) = width {
        put(&mut attrs, "width", s(v));
    }
    let source = read(source, value);
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    if let Some(v) = options {
        put(&mut node, "options", v.clone());
    }
    if let Some(v) = source {
        put(&mut node, "source", v.clone());
    }
    if let Some(v) = url {
        put(&mut node, "url", s(v));
    }
    put(&mut node, "type", s("canvas"));
    Value::Object(node)
}

/// Build a `forcegraph` node (the wire type `forcegraph`).
pub fn forcegraph(value: Option<&str>, height: Option<&str>, selector: Option<&str>, width: Option<&str>, source: Option<Source>, style: Option<Value>, theme: Option<Source>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = height {
        put(&mut attrs, "height", s(v));
    }
    if let Some(v) = selector {
        put(&mut attrs, "selector", s(v));
    }
    if let Some(v) = width {
        put(&mut attrs, "width", s(v));
    }
    let source = read(source, value);
    let theme = emit_read(theme);
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    if let Some(v) = source {
        put(&mut node, "source", v.clone());
    }
    if let Some(v) = style {
        put(&mut node, "style", v.clone());
    }
    if let Some(v) = theme {
        put(&mut node, "theme", v.clone());
    }
    put(&mut node, "type", s("forcegraph"));
    Value::Object(node)
}

/// Build a `panel` node (the wire type `panel`).
pub fn panel(children: &[Value], direction: Option<Value>, dismiss: Option<bool>, place: Option<Value>, replace_header: Option<bool>, selector: Option<&str>, state: Option<Value>, width: Option<&str>, left: Option<&str>, right: Option<&str>, top: Option<&str>, bottom: Option<&str>, source: Option<Source>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = direction {
        put(&mut attrs, "direction", v.clone());
    }
    if let Some(v) = dismiss {
        put(&mut attrs, "dismiss", Value::Bool(v));
    }
    if let Some(v) = place {
        put(&mut attrs, "place", v.clone());
    }
    if let Some(v) = replace_header {
        put(&mut attrs, "replace_header", Value::Bool(v));
    }
    if let Some(v) = selector {
        put(&mut attrs, "selector", s(v));
    }
    if let Some(v) = state {
        put(&mut attrs, "state", v.clone());
    }
    if let Some(v) = width {
        put(&mut attrs, "width", s(v));
    }
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
    let source = emit_read(source);
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
    if let Some(v) = source {
        put(&mut node, "source", v.clone());
    }
    put(&mut node, "type", s("panel"));
    Value::Object(node)
}

/// Build a `loom` node (the wire type `loom`).
pub fn loom(children: &[Value], reset: Option<&str>, selector: Option<&str>, sends: Option<i64>, submit: Option<&[&str]>, sink: Option<Sink>, tag: Option<&str>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = reset {
        put(&mut attrs, "reset", s(v));
    }
    if let Some(v) = selector {
        put(&mut attrs, "selector", s(v));
    }
    if let Some(v) = sends {
        put(&mut attrs, "sends", Value::from(v));
    }
    if let Some(v) = submit {
        put(&mut attrs, "submit", array(&v.iter().map(|item| s(*item)).collect::<Vec<Value>>()));
    }
    let sink = emit_write(sink);
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
    if let Some(v) = sink {
        put(&mut node, "sink", v.clone());
    }
    if let Some(v) = tag {
        put(&mut node, "tag", s(v));
    }
    put(&mut node, "type", s("loom"));
    Value::Object(node)
}

/// Build a `svg` node (the wire type `svg`).
pub fn svg(children: &[Value], height: Option<&str>, selector: Option<&str>, width: Option<&str>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = height {
        put(&mut attrs, "height", s(v));
    }
    if let Some(v) = selector {
        put(&mut attrs, "selector", s(v));
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

/// Build a `path` node (the wire type `path`).
pub fn path(value: Option<&str>, horizontal: Option<bool>, selector: Option<&str>, source: Option<Source>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = horizontal {
        put(&mut attrs, "horizontal", Value::Bool(v));
    }
    if let Some(v) = selector {
        put(&mut attrs, "selector", s(v));
    }
    let source = read(source, value);
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    if let Some(v) = source {
        put(&mut node, "source", v.clone());
    }
    put(&mut node, "type", s("path"));
    Value::Object(node)
}

/// Build a `tiles` node (the wire type `tiles`).
pub fn tiles(children: &[Value], dir: Option<Value>, fields: Option<Value>, header: Option<Value>, selector: Option<&str>, step: Option<Value>, window: Option<Value>, wrap: Option<Value>, source: Option<Source>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = dir {
        put(&mut attrs, "dir", v.clone());
    }
    if let Some(v) = fields {
        put(&mut attrs, "fields", v.clone());
    }
    if let Some(v) = header {
        put(&mut attrs, "header", v.clone());
    }
    if let Some(v) = selector {
        put(&mut attrs, "selector", s(v));
    }
    if let Some(v) = step {
        put(&mut attrs, "step", v.clone());
    }
    if let Some(v) = window {
        put(&mut attrs, "window", v.clone());
    }
    if let Some(v) = wrap {
        put(&mut attrs, "wrap", v.clone());
    }
    let source = emit_read(source);
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
    if let Some(v) = source {
        put(&mut node, "source", v.clone());
    }
    put(&mut node, "type", s("tiles"));
    Value::Object(node)
}

/// Build a `entry` node (the wire type `entry`).
pub fn entry(children: &[Value], horizontal: Option<bool>, selector: Option<&str>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = horizontal {
        put(&mut attrs, "horizontal", Value::Bool(v));
    }
    if let Some(v) = selector {
        put(&mut attrs, "selector", s(v));
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
    put(&mut node, "type", s("entry"));
    Value::Object(node)
}

/// Build a `button` node (the wire type `button`).
pub fn button(value: Option<&str>, oneshot: Option<bool>, selector: Option<&str>, source: Option<Source>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    put(&mut attrs, "oneshot", Value::Bool(oneshot.unwrap_or(false)));
    if let Some(v) = selector {
        put(&mut attrs, "selector", s(v));
    }
    let source = read(source, value);
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    if let Some(v) = source {
        put(&mut node, "source", v.clone());
    }
    put(&mut node, "type", s("button"));
    Value::Object(node)
}

/// Build a `image` node (the wire type `image`).
pub fn image(value: Option<&str>, desc: Option<&str>, height: Option<&str>, selector: Option<&str>, thumb: Option<bool>, width: Option<&str>, source: Option<Source>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = desc {
        put(&mut attrs, "desc", s(v));
    }
    if let Some(v) = height {
        put(&mut attrs, "height", s(v));
    }
    if let Some(v) = selector {
        put(&mut attrs, "selector", s(v));
    }
    put(&mut attrs, "thumb", Value::Bool(thumb.unwrap_or(false)));
    if let Some(v) = width {
        put(&mut attrs, "width", s(v));
    }
    let source = read(source, value);
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    if let Some(v) = source {
        put(&mut node, "source", v.clone());
    }
    put(&mut node, "type", s("image"));
    Value::Object(node)
}

/// Build a `input` node (the wire type `input`).
pub fn input(horizontal: Option<bool>, selector: Option<&str>, source: Option<Source>, emit: Option<Value>, kind: Option<Value>, multiline: Option<bool>, placeholder: Option<Source>, tag: Option<&str>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = horizontal {
        put(&mut attrs, "horizontal", Value::Bool(v));
    }
    if let Some(v) = selector {
        put(&mut attrs, "selector", s(v));
    }
    let source = emit_read(source);
    let placeholder = emit_read(placeholder);
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if let Some(v) = emit {
        put(&mut node, "emit", v.clone());
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    if let Some(v) = kind {
        put(&mut node, "kind", v.clone());
    }
    if let Some(v) = multiline {
        put(&mut node, "multiline", Value::Bool(v));
    }
    if let Some(v) = placeholder {
        put(&mut node, "placeholder", v.clone());
    }
    if let Some(v) = source {
        put(&mut node, "source", v.clone());
    }
    if let Some(v) = tag {
        put(&mut node, "tag", s(v));
    }
    put(&mut node, "type", s("input"));
    Value::Object(node)
}

/// Build a `select` node (the wire type `select`).
pub fn select(horizontal: Option<bool>, selector: Option<&str>, source: Option<Source>, options: Option<Source>, tag: Option<&str>, id: Option<&str>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = horizontal {
        put(&mut attrs, "horizontal", Value::Bool(v));
    }
    if let Some(v) = selector {
        put(&mut attrs, "selector", s(v));
    }
    let source = emit_read(source);
    let options = emit_read(options);
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    if let Some(v) = options {
        put(&mut node, "options", v.clone());
    }
    if let Some(v) = source {
        put(&mut node, "source", v.clone());
    }
    if let Some(v) = tag {
        put(&mut node, "tag", s(v));
    }
    put(&mut node, "type", s("select"));
    Value::Object(node)
}

/// Build a `text` node (the wire type `text`).
pub fn text(value: Option<&str>, format: Option<&str>, selector: Option<&str>, source: Option<Source>, id: Option<&str>, variant: Option<TextVariant>) -> Value {
    let mut attrs = Map::new();
    if let Some(v) = variant {
        put(&mut attrs, "class", array(&[s(v.token())]));
    }
    if let Some(v) = format {
        put(&mut attrs, "format", s(v));
    }
    if let Some(v) = selector {
        put(&mut attrs, "selector", s(v));
    }
    let source = read(source, value);
    let mut node = Map::new();
    if !attrs.is_empty() {
        put(&mut node, "attrs", Value::Object(attrs));
    }
    if let Some(v) = id {
        put(&mut node, "id", s(v));
    }
    if let Some(v) = source {
        put(&mut node, "source", v.clone());
    }
    put(&mut node, "type", s("text"));
    Value::Object(node)
}
