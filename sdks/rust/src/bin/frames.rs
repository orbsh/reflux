//! The reference application's frames, as JSON lines — the subject of `tools/gate_t10.py`.
//!
//! Five turns, the same five the Python reference app produces (and the same five `tools/measure.py`
//! weighs): an echo, an added row, a removed row, a form submit, and a page turn with its seeded
//! rows. The gate builds these with the Python SDK and compares bytes; nothing here talks to a
//! server, because producing the frame is the SDK's whole job.

use reflux_sdk::types::{button, case, form, input, placeholder, rack, text, JsType, TextVariant};
use reflux_sdk::wire::{append, create, draw, remove, set};
use serde_json::Value;
use std::io::Write;

const SESSION: &str = "measure1";
const ECHO: &str = "echo";
const ROWS: &str = "rows";
const SUBMITTED: &str = "submitted";
const PATH_MARKER: &str = "reflux:path";
const TITLE_MARKER: &str = "reflux:title";

/// One reserved-id node: a `placeholder` puts its id on the DOM, where the runtime reads it.
fn marker(id: &str, value: &str) -> Value {
    placeholder(&[text(Some(value), None, None, None, None)], None, None, Some(id))
}

/// A page: the two markers the client runtime mirrors, then the content.
fn page(path: &str, title: &str, children: &[Value]) -> Value {
    let mut nodes = vec![marker(PATH_MARKER, path), marker(TITLE_MARKER, title)];
    nodes.extend_from_slice(children);
    case(&nodes, None, None, Some("page-root"), None)
}

/// A one-button form — the vocabulary's only clickable, and the demo's way between pages.
fn nav_form(label: &str, event: &str) -> Value {
    let id = format!("nav-{event}");
    form(&[button(Some(label), None, None)], None, Some(event), None, Some(&id))
}

/// One row: its text, and the form whose submit carries the row's own id up.
fn row_node(id: &str, value: &str) -> Value {
    let children = [text(Some(value), None, None, None, None), button(Some("删"), None, None)];
    form(&children, None, Some("row.remove"), None, Some(id))
}

fn home() -> Value {
    page(
        "/",
        "演示",
        &[
            text(Some("演示"), None, None, None, Some(TextVariant::Heading1)),
            input(None, Some("name.change"), None, None, None, Some("name-input")),
            text(None, None, Some(ECHO), Some("echo"), None),
            form(&[button(Some("加一行"), None, None)], None, Some("row.add"), None, Some("add-row")),
            rack(None, Some(ROWS), None, Some("rows")),
            form(
                &[
                    input(None, None, Some("user"), None, None, Some("f-user")),
                    input(None, None, Some("pass"), None, Some(JsType::Password), Some("f-pass")),
                    button(Some("保存"), None, None),
                ],
                None,
                Some("login.submit"),
                None,
                Some("login"),
            ),
            text(None, None, Some(SUBMITTED), Some("submitted"), None),
            nav_form("关于", "go.about"),
            text(
                Some(
                    "accrete 没有带 URL 的类型：页面之间靠上面那个表单提交，生产者回一帧新结构加上新的路径标记，\
                     runtime 把标记镜像进地址栏。",
                ),
                None,
                None,
                None,
                Some(TextVariant::Muted),
            ),
        ],
    )
}

fn main() {
    let turns = [
        ("echo", draw(SESSION, &[set(ECHO, text(Some("hello"), None, None, None, None))])),
        (
            "add row",
            draw(
                SESSION,
                &[append(ROWS, row_node("row-4", "第 4 行"), 0)],
            ),
        ),
        ("remove row", draw(SESSION, &[remove(ROWS, "row-1")])),
        (
            "form submit",
            draw(
                SESSION,
                &[set(
                    SUBMITTED,
                    text(Some("已提交 {\"pass\": \"secret\", \"user\": \"ada\"}"), None, None, None, None),
                )],
            ),
        ),
        (
            "page turn",
            draw(
                SESSION,
                &[
                    create(home()),
                    append(ROWS, row_node("row-1", "第一行"), 0),
                    append(ROWS, row_node("row-2", "第二行"), 0),
                ],
            ),
        ),
    ];

    let mut out = std::io::stdout().lock();
    for (_label, frame) in turns {
        let line = serde_json::to_string(&frame).expect("a frame is serializable");
        writeln!(out, "{line}").expect("stdout");
    }
}