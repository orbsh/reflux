//! The reference application's frames, as JSON lines — the subject of `tools/gate_t10.py`.
//!
//! The reference app's turns, the same ones the Python SDK produces (and the same ones
//! `tools/measure.py` weighs): an echo, an added row, a removed row, the login surface, a page turn
//! with its seeded rows, an about page, and a node with a `local` landing. Each is one frame, and a
//! frame is the array of operations — nothing wraps them. The gate builds these with the Python SDK
//! and compares bytes; nothing here talks to a server, because producing the frame is the SDK's
//! whole job.
//!
//! The vocabulary is ADR 0031/0032's: a form is a `bundle` (fields tagged, timing in `attrs.submit`,
//! the exit on `sink`), a list/grid is `tiles`, and every value rides one `Bind` — `source` in,
//! `sink` out, `scope` naming where it is authoritative (`remote` unless a node reads the page's
//! own vals plane).

use reflux_sdk::markers;
use reflux_sdk::types::{
    bundle, button, frame, input, text, tiles, Bind, JsType, TextVariant,
};
use reflux_sdk::wire::{append, create, draw, remove, set};
use serde_json::{json, Value};
use std::io::Write;

const ECHO: &str = "echo";
const ROWS: &str = "rows";
const SECRET: &str = "secret";
const LOGIN: &str = "reflux:login";
const LOGOUT: &str = "reflux:logout";
const AUTH_SLOT: &str = "auth";

/// A remote address: the scope every ordinary slot and uplink lives in.
fn remote_slot(slot: &str) -> Bind {
    Bind {
        slot: Some(slot.to_string()),
        ..Default::default()
    }
}

/// An uplink whose boundary value is typed (`type: password`), with no slot: a bundle field.
fn remote_type(kind: JsType) -> Bind {
    Bind {
        js_type: Some(kind),
        ..Default::default()
    }
}

/// The page's own vals plane, one level in (`path: "/data"` out of the emitted wrapper).
fn local_slot(slot: &str, path: &str) -> Bind {
    Bind {
        slot: Some(slot.to_string()),
        path: Some(path.to_string()),
        scope: Some("local".to_string()),
        ..Default::default()
    }
}

/// The button of a one-button bundle: its label is a `source`, its exit the bundle's own `sink`.
fn press(label: &str, sink: &str) -> Value {
    button(Some(label), None, None, None, Some(remote_slot(sink)), None)
}

/// A one-button bundle — the vocabulary's only clickable, and the demo's way between pages.
fn nav_bundle(label: &str, event: &str) -> Value {
    bundle(
        &[press(label, event)],
        None,
        Some(&["button"]),
        Some(remote_slot(event)),
        None,
        Some(&format!("nav-{event}")),
    )
}

/// One row: a draggable frame (the cargo) inside the bundle whose submit carries the row id up.
///
/// The cargo frame names itself `<id>-cargo`: a drop reports the dragged node's own id, and the
/// bundle already owns `<id>` — one id per tree, on both sides of the wire (ADR 0034).
fn row_node(id: &str, value: &str) -> Value {
    let remove = remote_slot("row.remove");
    let cargo = format!("{id}-cargo");
    let children = [
        frame(
            &[text(Some(value), None, None, None, None, None)],
            None,
            Some(json!({"tag": "row"})),
            None,
            None,
            None,
            None,
            None,
            None,
            Some(&cargo),
            None,
        ),
        button(Some("删"), None, None, None, Some(remove.clone()), None),
    ];
    bundle(
        &children,
        None,
        Some(&["button"]),
        Some(remove),
        None,
        Some(id),
    )
}

fn home() -> Value {
    markers::page(
        "/",
        "演示",
        &[
            text(Some("演示"), None, None, None, None, Some(TextVariant::Heading1)),
            input(None, None, None, Some(remote_slot("name.change")), None, None, None, Some("name-input")),
            text(None, None, None, Some(remote_slot(ECHO)), Some("echo"), None),
            bundle(
                &[press("加一行", "row.add")],
                None,
                Some(&["button"]),
                Some(remote_slot("row.add")),
                None,
                Some("add-row"),
            ),
            tiles(&[], None, None, None, None, None, None, None, Some(remote_slot(ROWS)), Some("rows")),
            // The landing point names its event and what it accepts.
            frame(
                &[text(Some("拖一行到这里归档"), None, None, None, None, None)],
                Some(json!({"tag": "row"})),
                None,
                None,
                None,
                None,
                None,
                None,
                Some(remote_slot("row.archive")),
                Some("archive"),
                None,
            ),
            text(None, None, None, Some(remote_slot("archived")), Some("archived"), None),
            // The credential bundle speaks the framework's verb: this app never sees the password.
            bundle(
                &[
                    input(None, None, None, None, None, None, Some("user"), Some("f-user")),
                    input(None, None, None, Some(remote_type(JsType::Password)), None, None, Some("pass"), Some("f-pass")),
                    press("登录", LOGIN),
                ],
                None,
                Some(&["enter", "button"]),
                Some(remote_slot(LOGIN)),
                None,
                Some("login"),
            ),
            // The reserved region the framework draws the login surface into.
            frame(
                &[],
                None,
                None,
                None,
                None,
                None,
                None,
                Some(remote_slot(AUTH_SLOT)),
                None,
                Some("auth-region"),
                None,
            ),
            bundle(
                &[press("私密", "vault.secret")],
                None,
                Some(&["button"]),
                Some(remote_slot("vault.secret")),
                None,
                Some("vault"),
            ),
            text(None, None, None, Some(remote_slot(SECRET)), Some("secret"), None),
            bundle(
                &[press("退出", LOGOUT)],
                None,
                Some(&["button"]),
                Some(remote_slot(LOGOUT)),
                None,
                Some("logout"),
            ),
            nav_bundle("关于", "go.about"),
            text(
                Some(
                    "accrete 没有带 URL 的类型：页面之间靠上面那个表单提交，生产者回一帧新结构加上新的路径标记，\
                     runtime 把标记镜像进地址栏。",
                ),
                None,
                None,
                None,
                None,
                Some(TextVariant::Muted),
            ),
        ],
    )
}

fn about() -> Value {
    markers::page(
        "/about",
        "关于",
        &[
            text(
                Some("关于"),
                None,
                None,
                None,
                None,
                Some(TextVariant::Heading1),
            ),
            text(
                Some("这个示例应用只用 SDK 写出来：回声、列表、表单，加两条路由。"),
                None,
                None,
                None,
                None,
                None,
            ),
            nav_bundle("回到演示", "go.home"),
        ],
    )
}

/// The demo's own login surface: a heading, the refusal line, and the credential bundle.
fn login_surface() -> Value {
    frame(
        &[
            text(
                Some("演示登录"),
                None,
                None,
                None,
                None,
                Some(TextVariant::Heading1),
            ),
            text(
                Some("用户或密码不对"),
                None,
                None,
                None,
                None,
                Some(TextVariant::Muted),
            ),
            bundle(
                &[
                    input(
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        Some("user"),
                        Some("auth-user"),
                    ),
                    input(
                        None,
                        None,
                        None,
                        Some(remote_type(JsType::Password)),
                        None,
                        None,
                        Some("pass"),
                        Some("auth-pass"),
                    ),
                    press("确认登录", LOGIN),
                ],
                None,
                Some(&["enter", "button"]),
                Some(remote_slot(LOGIN)),
                None,
                Some("auth-form"),
            ),
        ],
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )
}

fn main() {
    let turns = [
        (
            "echo",
            draw(&[set(ECHO, text(Some("hello"), None, None, None, None, None))]),
        ),
        (
            "add row",
            draw(&[append(ROWS, row_node("row-4", "第 4 行"), 0)]),
        ),
        ("remove row", draw(&[remove(ROWS, "row-1")])),
        ("login surface", draw(&[set(AUTH_SLOT, login_surface())])),
        (
            "page turn",
            draw(&[
                create(home()),
                append(ROWS, row_node("row-1", "第一行"), 0),
                append(ROWS, row_node("row-2", "第二行"), 0),
            ]),
        ),
        ("about page", draw(&[create(about())])),
        (
            "local binding",
            draw(&[create(frame(
                &[text(
                    None,
                    None,
                    None,
                    Some(local_slot("chan", "/data")),
                    Some("local-echo"),
                    None,
                )],
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                Some("root"),
                None,
            ))]),
        ),
    ];

    let mut out = std::io::stdout().lock();
    for (_label, frame) in turns {
        let line = serde_json::to_string(&frame).expect("a frame is serializable");
        writeln!(out, "{line}").expect("stdout");
    }
}
