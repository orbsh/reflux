//! The page markers: the two reserved ids the client runtime reads out of the DOM.
//!
//! `www/static/reflux.js` mirrors `reflux:path` into the address bar and `reflux:title` into the
//! document's title. Both are ordinary nodes — a `placeholder` whose id is the reserved name — so
//! producing them is a **convention**, not a wire type: accrete does not know the words `path` or
//! `title`, and the vocabulary must not learn them.
//!
//! Hand-written here for the same reason `wire` is: what the specification owns is the vocabulary of
//! nodes, not this framework's contract with its own runtime. The ids below are the whole of that
//! contract — `tools/gate_t10.py` is what keeps them honest, because a page turn built here must come
//! out byte-identical to the one the Python SDK builds; a changed prefix on either side fails it.

use crate::types::{case, placeholder, text};
use serde_json::Value;

pub const PATH_ID: &str = "reflux:path";
pub const TITLE_ID: &str = "reflux:title";
pub const PAGE_ID: &str = "page-root";

/// The address the page is showing. The runtime copies it into the address bar.
pub fn path_marker(path: &str) -> Value {
    placeholder(
        &[text(Some(path), None, None, None, None, None, None)],
        None,
        None,
        Some(PATH_ID),
    )
}

/// The page's title. The runtime copies it into `document.title`.
pub fn title_marker(title: &str) -> Value {
    placeholder(
        &[text(Some(title), None, None, None, None, None, None)],
        None,
        None,
        Some(TITLE_ID),
    )
}

/// A page: the two markers first (in this order), then the content.
pub fn page(path: &str, title: &str, children: &[Value]) -> Value {
    let mut nodes = vec![path_marker(path), title_marker(title)];
    nodes.extend_from_slice(children);
    case(&nodes, None, None, Some(PAGE_ID), None)
}
