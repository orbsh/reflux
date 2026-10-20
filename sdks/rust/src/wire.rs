//! The outbound frame layer: accrete's eight actions, verbatim.
//!
//! Fields are the wire's, taken from the renderer's `content` crate: `create` / `set` carry
//! `Influx{event, data}`, `append` `AppendOp{event, position, data}`, `remove` `RemoveOp{event, id}`,
//! `patch` `PatchOp{event, id?, path, op, value}`, `inject` `InjectOp{slot, event?, id?, data}`,
//! `tmpl` `InfluxTmpl{name, data}`, and `empty` carries nothing. The frame is
//! `Message{ev, sender, created?, content}`: we write `ev = "draw"` and leave `created` out.
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
    put(&mut op, "event", s(""));
    put(&mut op, "data", data);
    Value::Object(op)
}

/// Replace the node in the named data slot.
pub fn set(slot: &str, data: Value) -> Value {
    let mut op = Map::new();
    put(&mut op, "action", s("set"));
    put(&mut op, "event", s(slot));
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
    put(&mut op, "event", s(slot));
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
    put(&mut op, "event", s(slot));
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
    put(&mut op, "event", s(slot));
    put(&mut op, "path", s(path));
    put(&mut op, "op", s(op_kind));
    put(&mut op, "value", value);
    if let Some(row) = id {
        put(&mut op, "id", s(row));
    }
    Value::Object(op)
}

/// Write the vals plane as if the page had emitted a `local` event on `slot`.
///
/// `data` is a bare JSON value: the vals plane's currency is not display form (no node). The
/// renderer short-circuits an equal value, so this is safe to repeat.
pub fn inject(slot: &str, data: Value, event: Option<&str>, id: Option<&str>) -> Value {
    let mut op = Map::new();
    put(&mut op, "action", s("inject"));
    put(&mut op, "slot", s(slot));
    put(&mut op, "data", data);
    if let Some(name) = event {
        put(&mut op, "event", s(name));
    }
    if let Some(row) = id {
        put(&mut op, "id", s(row));
    }
    Value::Object(op)
}

/// Register a `{{key}}` substitution table. `body` is the template's own Accrete JSON, as text.
pub fn tmpl(name: &str, body: &str) -> Value {
    let mut op = Map::new();
    put(&mut op, "action", s("tmpl"));
    put(&mut op, "name", s(name));
    put(&mut op, "data", s(body));
    Value::Object(op)
}

/// An op that does nothing — the wire's own no-op.
pub fn empty() -> Value {
    let mut op = Map::new();
    put(&mut op, "action", s("empty"));
    Value::Object(op)
}

/// One turn = one frame. `sender` is the session id the envelope requires.
pub fn draw(sender: &str, operations: &[Value]) -> Value {
    let mut frame = Map::new();
    put(&mut frame, "ev", s("draw"));
    put(&mut frame, "sender", s(sender));
    put(&mut frame, "content", Value::Array(operations.to_vec()));
    Value::Object(frame)
}