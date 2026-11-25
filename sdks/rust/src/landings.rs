//! Landing points: a closure as a sink, named when the page is drawn.
//!
//! The Python SDK writes `sink=add_row` and the framework names the closure at draw time
//! (`App._name_landings`). Rust has no runtime function names, so the same shape needs one thing
//! spelled by the caller: the name. Everything else is the rule the Python side implements —
//! `<path>.<name>`, one name per bound handler, a second *different* handler of the same name
//! getting `#2` — and this module keeps that rule in one place so a Rust host and the Python app
//! agree on the bytes.
//!
//! What it deliberately is not: a dispatcher. A host hands the table's closure the event's value,
//! exactly as `reflux/dests.py` does for the Python side; the SDK's job is still the bytes.

use std::collections::BTreeMap;

use serde_json::Value;

/// The handler a page bound to a sink, and whether that landing point needs a bound user.
pub type Handler = Box<dyn Fn(&Value) + Send>;

/// One draw's landing points for one page.
///
/// A page is drawn per connection, so this table belongs to a connection and is replaced on the
/// next draw — the address it was built for is part of the name, which is what keeps two pages'
/// `add_row` from colliding.
pub struct Landings {
    path: String,
    table: BTreeMap<String, (Handler, bool)>,
    counts: BTreeMap<String, usize>,
}

impl Landings {
    /// One page's table, addressed by the path the page was drawn for.
    pub fn new(path: &str) -> Self {
        Self {
            path: path.to_string(),
            table: BTreeMap::new(),
            counts: BTreeMap::new(),
        }
    }

    /// Bind a handler and return the name a sink takes: `landings.bind("echo", |value| …)`.
    ///
    /// Binding the same name twice is one landing point (a loom carries the sink its button sends
    /// with); a second *different* handler under the same name gets `#2`, the same rule the Python
    /// side follows for a second closure with the same function name.
    pub fn bind<F>(&mut self, name: &str, handler: F) -> String
    where
        F: Fn(&Value) + Send + 'static,
    {
        self.bind_with(name, handler, false)
    }

    /// The same, gated: only a device with a user bound may send to it.
    pub fn bind_gated<F>(&mut self, name: &str, handler: F) -> String
    where
        F: Fn(&Value) + Send + 'static,
    {
        self.bind_with(name, handler, true)
    }

    fn bind_with<F>(&mut self, name: &str, handler: F, auth: bool) -> String
    where
        F: Fn(&Value) + Send + 'static,
    {
        let base = format!("{}.{}", self.path, name);
        let seen = self.counts.entry(base.clone()).or_insert(0);
        *seen += 1;
        let resolved = if *seen == 1 {
            base
        } else {
            format!("{}#{}", base, seen)
        };
        self.table
            .entry(resolved.clone())
            .or_insert_with(|| (Box::new(handler) as Handler, auth));
        resolved
    }

    /// The handler a drawn sink name resolves to, if this draw registered one.
    pub fn get(&self, name: &str) -> Option<&(Handler, bool)> {
        self.table.get(name)
    }

    /// Every name this draw put on the wire, in order — what a host would answer.
    pub fn names(&self) -> Vec<&str> {
        self.table.keys().map(String::as_str).collect()
    }

    /// Does this landing point need a bound user? False for a name this draw did not register.
    pub fn gated(&self, name: &str) -> bool {
        self.table.get(name).map(|row| row.1).unwrap_or(false)
    }
}