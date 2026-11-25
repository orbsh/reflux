//! The outbound frame layer: accrete's eight actions, verbatim.
//!
//! Fields are the wire's, taken from the renderer's `content` crate: `create` / `set` carry
//! `Influx{event, data}`, `append` `AppendOp{event, position, data}`, `remove` `RemoveOp{event, id}`,
//! `patch` `PatchOp{event, id?, path, op, value}`, `inject` `InjectOp{slot, event?, id?, data}`,
//! `tmpl` `InfluxTmpl{name, data}`, and `empty` carries nothing.
//!
//! **A frame is the action list** — a bare JSON array, one element per operation. The envelope
//! (`Message{ev, sender, created?}`) is the host's and this layer has none (fluxen ADR 0021
//! decision 6): there is one verb here, so an `ev` would only restate it.
//!
//! This mirrors `reflux/wire.py`. Both are hand-written on purpose — what the *specification* owns is
//! the vocabulary (`types`), not the shape of a frame. Where Python raises (`ValueError`) this
//! returns a value: the checks Python does here are the server's ingest checks, and the two sides
//! would otherwise disagree about who refuses what.

use serde_json::{Map, Value};

fn put(map: &mut Map<String, Value>, key: &str, value: Value) {
    map.insert(key.to_string(), value);
}

fn s(value: &str) -> Value {
    Value::String(value.to_string())
}

/// Replace the whole layout root. `Influx.event` is required and unread — we write `""`.
pub fn create(data: Value) -> Value {
    let mut op = Map::new();
    put(&mut op, "action", s("create"));
    put(&mut op, "slot", s(""));
    put(&mut op, "data", data);
    Value::Object(op)
}

/// Replace the node in the named data slot.
pub fn set(slot: &str, data: Value) -> Value {
    let mut op = Map::new();
    put(&mut op, "action", s("set"));
    put(&mut op, "slot", s(slot));
    put(&mut op, "data", data);
    Value::Object(op)
}

/// Add a row to the list slot `slot` at `position`.
///
/// `0` is the tail and is left off the wire (absent means 0): `+n` counts in from the tail, `-n`
/// from the head.
pub fn append(slot: &str, data: Value, position: i64) -> Value {
    let mut op = Map::new();
    put(&mut op, "action", s("append"));
    put(&mut op, "slot", s(slot));
    put(&mut op, "data", data);
    if position != 0 {
        put(&mut op, "position", Value::from(position));
    }
    Value::Object(op)
}

/// Drop the row carrying `id` from the list slot.
pub fn remove(slot: &str, id: &str) -> Value {
    let mut op = Map::new();
    put(&mut op, "action", s("remove"));
    put(&mut op, "slot", s(slot));
    put(&mut op, "id", s(id));
    Value::Object(op)
}

/// Change one value by JSON Pointer inside the addressed plane.
///
/// Plane: `slot == ""` → the layout root; `id` set → that row of the list slot **by identity**;
/// otherwise the named data slot. `op`: `"replace"` or `"append"`.
pub fn patch(slot: &str, path: &str, value: Value, op_kind: &str, id: Option<&str>) -> Value {
    let mut op = Map::new();
    put(&mut op, "action", s("patch"));
    put(&mut op, "slot", s(slot));
    put(&mut op, "path", s(path));
    put(&mut op, "op", s(op_kind));
    put(&mut op, "value", value);
    if let Some(row) = id {
        put(&mut op, "id", s(row));
    }
    Value::Object(op)
}

/// Move the row carrying `id` inside the list slot to `position`.
///
/// `position` counts the list with that row taken out (one shorter), so `-1` is the tail: `+n`
/// counts in from the tail, `-n` from the head. The row node is reused — focus and caret come with
/// it — which is what separates a move from a remove plus an append (ADR 0040).
pub fn move_row(slot: &str, id: &str, position: i64) -> Value {
    let mut op = Map::new();
    put(&mut op, "action", s("move"));
    put(&mut op, "slot", s(slot));
    put(&mut op, "id", s(id));
    put(&mut op, "position", Value::from(position));
    Value::Object(op)
}

/// Register a template: a tree with `$name` holes in its strings, plus the names it takes.
///
/// `data` is either the tree itself or its JSON as text, which is what a hand-written frame carries.
/// Registering is checking (ADR 0037): every `$name` must be in `params` and every param must be
/// used; that judgment lives in the renderer, so this layer only writes the shape.
pub fn tmpl(name: &str, params: &[&str], data: Value) -> Value {
    let mut op = Map::new();
    put(&mut op, "action", s("tmpl"));
    put(&mut op, "name", s(name));
    if !params.is_empty() {
        put(
            &mut op,
            "params",
            Value::Array(params.iter().map(|each| s(each)).collect()),
        );
    }
    put(&mut op, "data", data);
    Value::Object(op)
}

/// An op that does nothing — the wire's own no-op.
pub fn empty() -> Value {
    let mut op = Map::new();
    put(&mut op, "action", s("empty"));
    Value::Object(op)
}

/// One turn = one frame: the operations, in order. Nothing wraps them.
pub fn draw(operations: &[Value]) -> Value {
    Value::Array(operations.to_vec())
}
