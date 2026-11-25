//! The reference application's frames, as JSON lines — the subject of `tools/gate_t10.py`.
//!
//! The reference app's turns, the same ones the Python SDK produces (and the same ones
//! `tools/measure.py` weighs): an echo, an added row, a removed row, the login surface, a page turn
//! with its seeded rows, an about page, and a node with a `local` landing. Each is one frame, and a
//! frame is the array of operations — nothing wraps them. The gate builds these with the Python SDK
//! and compares bytes; nothing here talks to a server, because producing the frame is the SDK's
//! whole job.
//!
//! The vocabulary is ADR 0031/0032/0039's: a form is a `loom` (fields tagged, timing in
//! `attrs.submit`, the exit on `sink`), a list/grid is `tiles`, and each direction has its own
//! address — a `Source` in, a `Sink` out — with `scope` naming where it is authoritative
//! (`remote` unless a node reads the page's own vals plane). A field's parse and element type are
//! its own `kind`, not a channel's.

use reflux_sdk::landings::Landings;
use reflux_sdk::markers;
use reflux_sdk::types::{
    loom, button, frame, input, text, tiles, FrameVariant, JsType, Sink, Source, TextVariant,
};
use reflux_sdk::wire::{append, create, draw, move_row, remove, set};
use serde_json::{json, Value};
use std::io::Write;

const ECHO: &str = "echo";
const ROWS: &str = "rows";
const SECRET: &str = "secret";
const LOGIN: &str = "reflux:login";
const LOGOUT: &str = "reflux:logout";
const AUTH_SLOT: &str = "auth";

/// A remote address: the scope every ordinary slot and uplink lives in.
fn remote_slot(slot: &str) -> Source {
    Source {
        slot: Some(slot.to_string()),
        ..Default::default()
    }
}

/// A remote exit: where a value goes, with no slot to read — the write direction's address.
fn remote_sink(dest: &str) -> Sink {
    Sink {
        dest: Some(dest.to_string()),
        ..Default::default()
    }
}

/// A field's own type — the element and the parse, one declaration (`kind`), not a channel.
fn field_kind(kind: JsType) -> Option<Value> {
    Some(Value::String(kind.token().to_string()))
}

/// The page's own vals plane, one level in (`path: "/data"` out of the emitted wrapper).
fn local_slot(slot: &str, path: &str) -> Source {
    Source {
        slot: Some(slot.to_string()),
        path: Some(path.to_string()),
        scope: Some("local".to_string()),
        ..Default::default()
    }
}

/// The button of a one-button loom: its label is a `source`, and a press submits the loom, which
/// holds the exit (ADR 0039 §2a — a button has no `sink` of its own).
fn press(label: &str) -> Value {
    button(Some(label), None, None, None, None)
}

/// A one-button loom — the vocabulary's only clickable, and the demo's way between pages.
fn nav_loom(label: &str, event: &str) -> Value {
    loom(
        &[press(label)],
        None,  // reset,
        None,  // selector,
        None,  // sends,
        Some(&["button"]),
        Some(remote_sink(event)),
        None,
        Some(&format!("nav-{event}")))
}

/// A card: the `card` variant, and its children stacked at their own heights.
fn card(children: &[Value], id: &str) -> Value {
    frame(
        children,
        None,
        None,
        Some(json!({"grid-auto-rows": "auto", "gap": "10px", "align-content": "start"})),
        None,
        None,
        None,
        None,
        None,
        Some(id),
        Some(FrameVariant::Card),
    )
}

/// One row: a draggable frame (the cargo) inside the loom whose submit carries the row id up.
///
/// The cargo frame names itself `<id>-cargo`: a drop reports the dragged node's own id, and the
/// loom already owns `<id>` — one id per tree, on both sides of the wire (ADR 0034).
///
/// Both children say how the row is divided: a loom is a flex row whose items all grow, so the
/// cargo takes the width and the ✕ keeps its own size, centred in the height it does not fill.
fn row_node(id: &str, value: &str) -> Value {
    let remove = remote_sink("row.remove");
    let cargo = format!("{id}-cargo");
    let children = [
        frame(
            &[text(Some(value), None, None, None, None, None)],
            None,
            Some(json!({"tag": "row"})),
            None,
            None,
            None,
            Some(json!({"flex": "1 1 auto"})),
            None,
            None,
            Some(&cargo),
            None,
        ),
        frame(
            &[button(Some("删"), None, None, None, None)],
            None,
            None,
            None,
            None,
            None,
            Some(json!({"flex": "0 0 auto", "align-self": "center"})),
            None,
            None,
            None,
            None,
        ),
    ];
    loom(
        &children,
        None,  // reset,
        None,  // selector,
        None,  // sends,
        Some(&["button"]),
        Some(remove),
        None,
        Some(id))
}

fn home() -> Value {
    // The page's own three landing points: closures written where their buttons are written, named
    // by the table the way the Python side names them at draw time.
    let mut landings = Landings::new("/");
    let echo_sink = landings.bind("echo", |_| {});
    let add_row_sink = landings.bind("add_row", |_| {});
    let reveal_sink = landings.bind_gated("reveal", |_| {});

    let echo = card(
        &[
            text(Some("回声"), None, None, None, None, Some(TextVariant::Heading3)),
            text(
                Some("一个输入框的出口是它所在的那个组：回车让组把 {字段: 值} 发给组的 sink，字段自己的 `tag` 就是键。"),
                None,
                None,
                None,
                None,
                Some(TextVariant::Muted),
            ),
            loom(
                &[input(
                    None,
                    None,
                    None, None,
                    None,
                    None,
                    None,
                    Some("name"),
                    Some("name-input"),
                )],
                None,  // reset
                None,  // selector
                None,  // sends
                Some(&["enter"]),
                Some(remote_sink(&echo_sink)),
                None,  // tag
                Some("echo-form"),
            ),
            text(None, None, None, Some(remote_slot(ECHO)), Some("echo"), None),
        ],
        "card-echo",
    );
    let rows = card(
        &[
            text(Some("列表 · 拖拽"), None, None, None, None, Some(TextVariant::Heading3)),
            text(
                Some("行的身份在 id 上：✕ 按 id 删，拖过落点也按 id 归档 —— 手势本身什么都不说，只有落点说话。"),
                None,
                None,
                None,
                None,
                Some(TextVariant::Muted),
            ),
            loom(
                &[press("加一行")],
                None,  // reset,
                None,  // selector,
                None,  // sends,
                Some(&["button"]),
                Some(remote_sink(&add_row_sink)),
                None,
                Some("add-row")),
            tiles(&[], None, None, None, None, None, None, None, Some(remote_slot(ROWS)), Some("rows")),
            // The landing point names its event and what it accepts.
            frame(
                &[text(Some("拖一行到这里归档"), None, None, None, None, None)],
                Some(json!({"tag": "row"})),
                None,
                Some(json!({"place-items": "center"})),
                None,
                None,
                Some(json!({"border": "var(--border)", "border-style": "dashed", "min-height": "72px"})),
                None,
                Some(remote_sink("row.archive")),
                Some("archive"),
                None,
            ),
            text(None, None, None, Some(remote_slot("archived")), Some("archived"), None),
        ],
        "card-rows",
    );
    let login = card(
        &[
            text(Some("登录 · 门"), None, None, None, None, Some(TextVariant::Heading3)),
            text(
                Some("这张表单说的是框架的动词 `reflux:login`：应用只写 verify 和 view，密码它从来读不到。"),
                None,
                None,
                None,
                None,
                Some(TextVariant::Muted),
            ),
            // The credential loom speaks the framework's verb: this app never sees the password.
            loom(
                &[
                    frame(
                        &[
                            input(None, None, None, None, None, None, None, Some("user"), Some("f-user")),
                            input(None, None, None, None, field_kind(JsType::Password), None, None,
                                  Some("pass"), Some("f-pass")),
                        ],
                        None,
                        None,
                        Some(json!({"grid-template-rows": "auto auto", "gap": "8px"})),
                        None,
                        None,
                        None,
                        None,
                        None,
                        Some("login-fields"),
                        None,
                    ),
                    frame(
                        &[press("登录")],
                        None,
                        None,
                        None,
                        None,
                        None,
                        Some(json!({"flex": "0 0 auto", "align-self": "end"})),
                        None,
                        None,
                        Some("login-press"),
                        None,
                    ),
                ],
                None,  // reset,
                None,  // selector,
                None,  // sends,
                Some(&["enter", "button"]),
                Some(remote_sink(LOGIN)),
                None,
                Some("login")),
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
            loom(
                &[press("私密")],
                None,  // reset,
                None,  // selector,
                None,  // sends,
                Some(&["button"]),
                Some(remote_sink(&reveal_sink)),
                None,
                Some("vault")),
            text(None, None, None, Some(remote_slot(SECRET)), Some("secret"), None),
            loom(
                &[press("退出")],
                None,  // reset,
                None,  // selector,
                None,  // sends,
                Some(&["button"]),
                Some(remote_sink(LOGOUT)),
                None,
                Some("logout")),
        ],
        "card-login",
    );
    markers::page(
        "/",
        "演示",
        &[frame(
            &[
                // The title is a grid item too: it spans both columns.
                frame(
                    &[
                        text(Some("演示"), None, None, None, None, Some(TextVariant::Heading1)),
                        text(
                            Some("这个应用只用 SDK 写出来：回声、列表、表单、拖拽，加三条路由。"),
                            None,
                            None,
                            None,
                            None,
                            Some(TextVariant::Muted),
                        ),
                    ],
                    None,
                    None,
                    Some(json!({"grid-template-rows": "auto auto"})),
                    None,
                    None,
                    Some(json!({"grid-column": "1 / -1"})),
                    None,
                    None,
                    Some("home-title"),
                    None,
                ),
                frame(
                    &[echo, rows],
                    None,
                    None,
                    Some(json!({"grid-template-rows": "auto auto", "gap": "16px", "align-content": "start"})),
                    None,
                    None,
                    None,
                    None,
                    None,
                    Some("home-left"),
                    None,
                ),
                login,
                // The footnote spans as well: a text node has no style, so a frame carries it.
                frame(
                    &[text(
                        Some("accrete 没有带 URL 的类型：页面之间靠上面那个表单提交，生产者回一帧新结构加上新的路径标记，runtime 把标记镜像进地址栏。"),
                        None,
                        None,
                        None,
                        None,
                        Some(TextVariant::Muted),
                    )],
                    None,
                    None,
                    None,
                    None,
                    None,
                    Some(json!({"grid-column": "1 / -1"})),
                    None,
                    None,
                    Some("home-note"),
                    None,
                ),
            ],
            None,
            None,
            Some(json!({"grid-template-columns": "minmax(0, 1fr) minmax(280px, 360px)", "gap": "16px", "align-items": "start"})),
            None,
            None,
            None,
            None,
            None,
            Some("home-grid"),
            None,
        )],
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
                Some("这个示例应用只用 SDK 写出来：回声、列表、表单，加三条路由 —— /、/about 和走查。"),
                None,
                None,
                None,
                None,
                None,
            ),
            nav_loom("回到演示", "go.home"),
        ],
    )
}

/// The demo's own login surface: a heading, the refusal line, and the credential loom.
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
            loom(
                &[
                    input(
                        None,
                        None,
                        None, None,
                        None,
                        None,
                        None,
                        Some("user"),
                        Some("auth-user"),
                    ),
                    input(
                        None,
                        None,
                        None, None,
                        field_kind(JsType::Password),
                        None,
                        None,
                        Some("pass"),
                        Some("auth-pass"),
                    ),
                    press("确认登录"),
                ],
                None,  // reset,
                None,  // selector,
                None,  // sends,
                Some(&["enter", "button"]),
                Some(remote_sink(LOGIN)),
                None,
                Some("auth-form")),
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
        // One row to the head of its list: the same id, no new node (ADR 0040).
        ("move row", draw(&[move_row(ROWS, "row-3", -1)])),
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
