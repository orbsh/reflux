//! The minimal reflux producer SDK in Rust.
//!
//! Generated: [`types`] — one builder per type the profile exposes (see `tools/gen_rust.py`).
//! Hand-written: [`wire`] — accrete's eight actions and the frame envelope, mirroring
//! `reflux/wire.py` line for line; [`landings`] — a closure as a sink, named at draw time, mirroring
//! the Python side's `App._name_landings`.
//!
//! What this is **not**: no transport, no session, no routing, no ingest. Those belong to a host —
//! the SDK's whole job is to hand a host the bytes, and the server checks every frame the same way
//! for every language. The point of this crate is narrower and sharper: the same specification that
//! generates the Python builders generates these, so a second language is not a second dialect.

pub mod landings;
pub mod markers;
pub mod types;
pub mod wire;

pub use landings::Landings;
pub use markers::page;
pub use types::*;
pub use wire::*;
