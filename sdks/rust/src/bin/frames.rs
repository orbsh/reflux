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
    bundle, button, frame, input, text, tiles, Bind, FrameVariant, JsType, TextVariant,
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

/// One row: a draggable frame (the cargo) inside the bundle whose submit carries the row id up.
///
/// The cargo frame names itself `<id>-cargo`: a drop reports the dragged node's own id, and the
/// bundle already owns `<id>` — one id per tree, on both sides of the wire (ADR 0034).
///
/// Both children say how the row is divided: a bundle is a flex row whose items all grow, so the
/// cargo takes the width and the ✕ keeps its own size, centred in the height it does not fill.
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
            Some(json!({"flex": "1 1 auto"})),
            None,
            None,
            Some(&cargo),
            None,
        ),
        frame(
            &[button(Some("删"), None, None, None, Some(remove.clone()), None)],
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
    let echo = card(
        &[
            text(Some("回声"), None, None, None, None, Some(TextVariant::Heading3)),
            text(
                Some("一个 input 在回车时把缓冲上行；上行不带包装，处理器拿到的 `data` 就是那个字符串。"),
                None,
                None,
                None,
                None,
                Some(TextVariant::Muted),
            ),
            input(
                None,
                None,
                None,
                Some(remote_slot("name.change")),
                None,
                None,
                None,
                Some("name-input"),
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
                Some(json!({"place-items": "center"})),
                None,
                None,
                Some(json!({"border": "var(--border)", "border-style": "dashed", "min-height": "72px"})),
                None,
                Some(remote_slot("row.archive")),
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
            // The credential bundle speaks the framework's verb: this app never sees the password.
            bundle(
                &[
                    frame(
                        &[
                            input(None, None, None, None, None, None, Some("user"), Some("f-user")),
                            input(None, None, None, Some(remote_type(JsType::Password)), None, None,
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
                        &[press("登录", LOGIN)],
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
