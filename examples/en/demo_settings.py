"""The settings page: core.css's token surface written into the page-options slot — instant locally,
remembered by the server (ADR 0001).

Page options are fluxen's mechanism, not this page's invention: `#main` carries no `data-config`, so the
slot hanging on it has the default name `__CONFIG__` (fluxen ADR 0038 §2). The slot holds one object and
its members are decided **one by one** — the page's own half first, the far (producer) side after — and the
renderer mirrors scalar members onto the document root as `data-<member>`, where the browser-side table
(`TOKENS` in `www/static/reflux.js`) turns them into `:root` custom properties. So this page adds no frame
and no verb:

1. **write**: one group's outlet, `Sink(dest="__CONFIG__", scope="both", path="/")` — `both` is "assign
   locally and mirror the change up" (fluxen ADR 0031 §1), and a group has one outlet, so this requirement
   has no other legal shape;
2. **remember**: `demo_app` hands the uplink to `on_config`, which whitelists, checks ranges, merges, and
   writes to disk on a throttle;
3. **start from what is stored**: the first time a device is drawn, the shell writes the stored object into
   the slot, so a new connection, a reload or another device begins with the user's choices.

**What is exported is a table, not a field at a time**: `TOKENS` says which `:root` tokens core.css has that
can be set on their own, and what kind each one is. The page generates the controls from it, the validator
is picked by kind, and the browser table checks by kind too — so the three places share one fact (the name,
i.e. the variable without `--`, and the kind), and adding a token is one row, not three edits.

**The table is `@layer options`**: core keeps the leaves a host may replace whole in that layer — **thirteen**
of them: six palette names (three say what a thing IS: `accent` / `primary` / `secondary`; three say what it
MEANS: `disabled` / `warn` / `error`), four form knobs (`round` / `input-round` / `border-width` /
`border-style`), and three type knobs (`focus-width` / `font-size` / `font-family`). The paired endpoints and
derivatives in `tokens` are not in the table but in `DERIVED`: `fg` / `bg` are `light-dark(a, b)` pairs (one
member can carry one value, so setting one decides for both schemes), `surface` / `wash` / `ring` /
`border-color` are mixed from them, and `ink` / `gloss` / `shadow-color` / `shadow-ink` are the two absolutes
a shadow is built from.

**Colours are `oklch` triples**: a member holds `L C H` (three numbers) and `oklch(...)` is composed exactly
once, in `reflux.js` — so the colour space is one decision instead of a string in every default. An empty
value means "not set", which hands the token back to core.css (including its paired `light-dark(a, b)`).
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from reflux import Context
from reflux.sdk import h
from reflux.sdk.types import Accrete, Sink, Source

__all__ = [
    "CONFIG",
    "CORE",
    "DEFAULTS",
    "DERIVED",
    "GROUPS",
    "KEYWORDS",
    "LABELS",
    "MEMBERS",
    "Store",
    "TOKENS",
    "flatten",
    "merge",
    "on_config",
    "page",
    "register",
    "seed",
    "state",
]

CONFIG = "__CONFIG__"  # fluxen's page-options slot: `#main` has no `data-config`, so this is the default name

# `@layer options` in core.css is the list that counts: **thirteen** leaves a host may replace whole — six
# palette names, four form knobs, three type knobs. The order is the order of the page's controls. Everything
# else lives in `tokens` (paired endpoints and derivatives) and is listed in `DERIVED`.
TOKENS: dict[str, str] = {
    "accent": "color",
    "primary": "color",
    "secondary": "color",
    "disabled": "color",
    "warn": "color",
    "error": "color",
    "round": "length",
    "input-round": "length",
    "border-width": "length",
    "border-style": "keyword",
    "focus-width": "length",
    "font-size": "length",
    "font-family": "font",
}

# The `tokens` layer, with why each is not a setting: paired endpoints or values computed from the options.
# The form only offers choices a person makes directly. `--border` is not here: it is the composition of
# width, style and colour, and the test excludes it by name.
DERIVED: dict[str, str] = {
    "fg": "a light-dark pair: one member can carry one value",
    "bg": "a light-dark pair: one member can carry one value",
    "surface": "a step mixed from bg and fg",
    "border-color": "var(--secondary): the line follows the secondary colour",
    "wash": "12% of fg: the hover ground",
    "ring": "18% of fg: the focus ring's colour",
    "ink": "the absolute black of a shadow",
    "gloss": "the absolute white of glass",
    "shadow-color": "var(--ink)",
    "shadow-ink": "10% of shadow-color",
}

# How the page groups them: layout only, no part of the checks. Three sections follow the options layer's own
# split — what a thing is / means, form, type. Order matches `TOKENS` (the gate addresses by position within a
# kind); colours are one group, the four form knobs are named here, and every other non-colour is the third.
FORM = ["round", "input-round", "border-width", "border-style"]
GROUPS: list[tuple[str, str, list[str]]] = [
    (
        "palette",
        "Palette · six colours (oklch triples L C H)",
        [n for n, k in TOKENS.items() if k == "color"],
    ),
    (
        "form",
        "Form · radii, border width and style",
        FORM,
    ),
    (
        "type",
        "Type and focus · ring width, size, family",
        [n for n in TOKENS if n not in FORM and TOKENS[n] != "color"],
    ),
]

LABELS: dict[str, str] = {
    "accent": "Accent",
    "primary": "Primary",
    "secondary": "Secondary",
    "disabled": "Disabled",
    "warn": "Warning",
    "error": "Error",
    "round": "Corner radius",
    "input-round": "Input radius",
    "border-width": "Border width",
    "border-style": "Border style",
    "focus-width": "Focus ring width",
    "font-size": "Font size",
    "font-family": "Font stack",
}

# core.css's defaults, used only as the inputs' placeholders and as documentation: the real default lives in
# the stylesheet, and this file never writes it.
CORE: dict[str, str] = {
    "accent": "0.7 0.12 182.49",
    "primary": "0.98 0.06 107.14",
    "secondary": "0.93 0 0",
    "disabled": "0.6 0 0",
    "warn": "0.84 0.12 92.82",
    "error": "0.63 0.19 23.03",
    "round": "10",
    "input-round": "0.35em (about 5.6px)",
    "border-width": "1",
    "border-style": "solid",
    "focus-width": "max(2px, 0.15em)",
    "font-size": "20 (1.25rem)",
    "font-family": "Helvetica Neue, Tahoma, Arial, PingFangSC-Regular, Hiragino Sans GB, Microsoft Yahei, sans-serif",
}

KEYWORDS = ("solid", "dashed", "dotted", "double", "none")

# All six colour tokens share one **swatch**: the row holds a colour square and its `oklch()` literal, and a
# hover opens three sliders (L, C, H, each with a number box). What the field packs is the `L C H` triple, so
# the member, the validators and the browser never learn that a control was involved. Lightness is one of the
# three now — there is no per-token constant pinning it any more.

WORDS_SLOT = "palettes.words"

DEFAULTS: dict[str, Any] = {"sketch": False}  # tokens are not defaults: unset means core's default


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in ("true", "false"):
        return value.lower() == "true"
    return None


def _color(value: Any) -> str | None:
    """`L C H` → the same triple, normalised. Ranges: lightness 0–1, chroma 0–0.4, hue 0–360.

    A written-out `oklch(L C H)` is accepted too: this value is read and edited by a person, not only
    written by a program.
    """
    text = value.strip() if isinstance(value, str) else ""
    if text.lower().startswith("oklch(") and text.endswith(")"):
        text = text[6:-1]
    parts = [part for part in re.split(r"[\s,]+", text.strip()) if part]
    if len(parts) != 3:
        return None
    try:
        light, chroma, hue = (float(part.rstrip("%")) for part in parts)
    except ValueError:
        return None
    if not (0.0 <= light <= 1.0 and 0.0 <= chroma <= 0.4 and 0.0 <= hue <= 360.0):
        return None
    return f"{light:g} {chroma:g} {hue:g}"


def _length(value: Any) -> str | None:
    """A number 0–64 (pixels are appended by the browser side). A `px` suffix may be written and is dropped."""
    if isinstance(value, bool):  # bool is an int subclass; it must not pass here
        return None
    text = value.strip() if isinstance(value, str) else value
    if isinstance(text, str) and text.lower().endswith("px"):
        text = text[:-2]
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    if not 0.0 <= number <= 64.0:
        return None
    return f"{number:g}"


def _keyword(value: Any) -> str | None:
    text = value.strip().lower() if isinstance(value, str) else ""
    return text if text in KEYWORDS else None


def _font(value: Any) -> str | None:
    """A font stack: comma-separated names, quoted where needed.

    This value is written into `--font-family` as it stands, so it has to be **one value**: empty, longer
    than 120, multi-line, or carrying `;` / braces / angle brackets is refused — those characters make it
    read like a declaration rather than a font name.
    """
    text = value.strip() if isinstance(value, str) else ""
    if not text or len(text) > 120:
        return None
    if len(text.splitlines()) != 1 or any(ch in "{};<>" for ch in text):
        return None
    return re.sub(r"\s*,\s*", ", ", text)


_BY_KIND = {"color": _color, "length": _length, "keyword": _keyword, "font": _font}

MEMBERS: dict[str, Any] = {"sketch": _bool, **{name: _BY_KIND[kind] for name, kind in TOKENS.items()}}


def flatten(payload: Any) -> dict:
    """Unpack the group's object into `{member: value}`: the payload is `{tag: value}` (ADR 0032 §2), with no wrapper.

    A member's value is a scalar (string / number / bool); `None` means "no value", and an object is
    malformed — neither becomes state. A payload that is not an object yields `{}` and never raises.
    """
    if not isinstance(payload, dict):
        return {}
    return {
        name: value
        for name, value in payload.items()
        if value is not None and not isinstance(value, dict)
    }


def merge(state: dict, patch: dict) -> tuple[dict, list[str]]:
    """The state after the whitelist and the range checks, plus the members that were dropped.

    An empty value is not a bad value: **clearing a field means "not set"**, the member leaves the state,
    and core's default (paired `light-dark` included) comes back. Only "has a value and it is invalid" goes
    into `rejected` — the group's outlet packs every field it holds, so the empty ones arrive on every
    frame, and they are not errors.

    Only members that pass and actually differ are replaced, so an uplink that changes nothing never causes
    a write.
    """
    merged = dict(state)
    rejected: list[str] = []
    for name, value in patch.items():
        check = MEMBERS.get(name)
        if check is None:
            rejected.append(name)
            continue
        if isinstance(value, str) and not value.strip():
            merged.pop(name, None)
            continue
        clean = check(value)
        if clean is None:
            rejected.append(name)
            continue
        merged[name] = clean
    return merged, rejected


class Store:
    """The one thing this app remembers: page options.

    The write is **throttled**: `submit=["change"]` is one uplink per keystroke (sliders and inputs both),
    so a burst of changes writes only the last one, and a value that did not change writes nothing. The
    write is atomic (`.tmp` then `replace`) because the next process reads it back.
    """

    def __init__(self, path: str | Path = ".demo-settings.json", delay: float = 0.35) -> None:
        self.path = Path(path)
        self.delay = delay
        self.state: dict[str, Any] = dict(DEFAULTS)
        self.writes = 0  # how many times it hit the disk: tests and snapshots read it
        self.rejected: list[str] = []
        self._timer: asyncio.TimerHandle | None = None

    def load(self) -> dict:
        """Read back what was stored (a missing file, bad JSON, a member off the whitelist: all just "none")."""
        try:
            stored = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return self.state
        self.state, _ = merge(self.state, stored if isinstance(stored, dict) else {})
        return self.state

    def apply(self, payload: Any) -> dict:
        """One uplink: merge, and schedule a write if anything changed. Returns the merged state."""
        before = dict(self.state)
        self.state, self.rejected = merge(self.state, flatten(payload))
        if self.state != before:
            self.save_soon()
        return self.state

    def save_soon(self) -> None:
        """Schedule one write, throttled by `delay`: another change inside the window pushes it out."""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # no loop (a test calling the handler directly): write now, do not pretend
            self.flush()
            return
        self._timer = loop.call_later(self.delay, self.flush)

    def flush(self) -> None:
        """Write once, now. `self.writes` counts it, which is how tests tell "scheduled" from "written"."""
        self._timer = None
        temp = self.path.with_name(self.path.name + ".tmp")
        try:
            temp.write_text(json.dumps(self.state, ensure_ascii=False, indent=1), encoding="utf-8")
            temp.replace(self.path)
        except OSError as exc:  # there is no "disk is full" setting: log it, do not crash on a click
            print(f"[settings] could not write {self.path}: {exc!r}", flush=True)
            return
        self.writes += 1


settings = Store()


def state() -> Store:
    """The one store: the app is one app."""
    return settings


def seed(ctx: Context) -> None:
    """The first time a device is drawn, write this slot first (ADR 0001 §5).

    Order matters: the slot write is a `send`, and the page's frame leaves at the end of `_draw`, so values
    arrive before the structure — the renderer has the members by the time it gets the first page tree.
    """
    if ctx.data.get("config_seeded"):
        return
    ctx.data["config_seeded"] = True
    # The slot holds an **object**: fluxen reads this node's `source.default` (`config_members`), so a
    # `frame` with no structure carries it — the same shape the walkthrough page's `payload()` uses.
    ctx.slot(CONFIG).set(h.frame(source=Source(default=dict(state().state))))


def field(name: str, kind: str, value: Any) -> Accrete:
    """One token row: a label, a control, and (for colours) a live preview.

    The preview reads the variable itself (`background: var(--accent)`, spelled from the name), so it shows
    the colour in force at that moment — no second copy of the state. A field's `tag` is the member name; the
    group's outlet packs by it.

    A colour is a swatch with a copyable literal, and a hover opens the three sliders (L, C, H); form is three
    number boxes and a word to click; type is a size (number box) and a font stack (text box). All are fields
    whose exit is the group they sit in, so one change is one `change` — a drag coalesces on the field's own
    window.
    """
    if kind == "color":
        control: Accrete = h.color(
            tag=name,
            source=Source(default=value),
            id=f"cfg-{name}",
        )
    elif kind == "keyword":
        # A `select` takes its option rows from the slot in `source` (this renderer reads `source`, not
        # `options` — see ADR 0001 §9). The value does not come from here: the `tag` gives it a copy inside
        # the group, and the group packs and sends it.
        # A folded one: the page shows the word in force, and a click opens the five (ADR 0049).
        control = h.picker(
            tag=name,
            selector="cfg",
            expand=True,
            source=Source(slot=WORDS_SLOT),
            id=f"cfg-{name}",
        )
    elif kind == "font":
        # A font stack is one value, not a word list: a text box, checked once on the server and once in the
        # browser (it may only be a single value).
        control = h.input(
            tag=name,
            kind="text",
            selector="cfg",
            source=Source(default=value),
            placeholder=CORE.get(name, ""),
            id=f"cfg-{name}",
        )
    else:
        control = h.input(
            tag=name,
            # A length is a number, but not an interval (ADR 0050): an `input`'s kind names the form only, and
            # bounds belong to the slider — a `picker`. And an empty number is no longer zero: it packs `null`,
            # which the validator reads as "not set".
            kind="number",
            selector="cfg",
            source=Source(default=value),
            placeholder=CORE.get(name, ""),
            id=f"cfg-{name}",
        )
    preview = (
        h.frame(
            style={
                "background": f"var(--{name})",
                "border": "var(--border)",
                "border-radius": "6px",
                "min-height": "22px",
            },
            id=f"here-{name}",
        )
        if kind == "color"
        else h.text("")
    )
    return h.frame(
        h.text(f"{LABELS.get(name, name)} · {name}", variant="muted"),
        control,
        preview,
        grid={"grid-template-columns": "1fr 3fr 26px", "gap": "8px", "align-items": "center"},
        id=f"setting-{name}",
    )


def page(ctx: Context, match) -> Accrete:
    """The settings page — one group, core's whole token surface generated as fields, one outlet.

    The outlet is written once (a group is unique), `submit=["change"]` says "send when the value moves", and
    `reset="keep"` says "do not clear after sending" — clearing is for forms, and a setting is not something
    that expires after one submit.
    """
    now = state().state
    # A palette is a send, not part of the page tree: a `select` reads its options from a **slot** only
    # (`bind_list` takes a slot), so the three tile sets are written once per connection — a slot outlives a
    # `create`, so the second visit to this page does not write them again.
    if not ctx.data.get(f"{WORDS_SLOT}.seeded"):
        ctx.data[f"{WORDS_SLOT}.seeded"] = True
        words = ctx.slot(WORDS_SLOT)
        for word in KEYWORDS:
            words.append(h.text(word, id=word))
    groups: list[Accrete] = []
    for key, title, names in GROUPS:
        groups.append(
            h.frame(
                h.text(title, variant="heading-3"),
                *[field(name, TOKENS[name], now.get(name, "")) for name in names],
                grid={"grid-template-rows": f"auto repeat({len(names)}, auto)", "gap": "8px"},
                variant="card",
                id=f"group-{key}",
            )
        )
    return h.frame(
        h.text("Settings", variant="heading-1"),
        h.text(
            "core.css's options layer: the palette is **six colours**, each a swatch with a copyable "
            "`oklch()` literal — a hover opens the L / C / H sliders; form is numbers (radii, border width) and "
            "a style to click; type is a size (number) and a font stack (text). What travels is an oklch triple "
            "`L C H` (lightness 0–1, chroma 0–0.4, hue 0–360). A change takes effect locally at once and goes up "
            "to the server to be remembered (ADR 0001).",
            variant="muted",
        ),
        h.loom(
            h.frame(
                h.frame(
                    h.text("Sketch mode (the renderer draws its own borders)", variant="muted"),
                    h.input(
                        tag="sketch",
                        kind="bool",
                        selector="cfg",
                        source=Source(default=now["sketch"]),
                        id="cfg-sketch",
                    ),
                    grid={"grid-template-columns": "1fr 2fr", "gap": "8px", "align-items": "center"},
                    id="setting-sketch",
                ),
                *groups,
                grid={"grid-template-rows": f"auto repeat({len(groups)}, auto)", "gap": "14px"},
                id="config-rows",
            ),
            sink=Sink(dest=CONFIG, scope="both", path="/"),
            submit=["change"],
            reset="keep",
            id="config-form",
        ),
        h.text("Members outside the whitelist or outside their ranges are dropped, checked in both places: the browser is not the trusted side.", variant="muted"),
        h.text(source=Source(slot="settings.note"), id="settings-note"),
        id="settings-page",
        grid={"grid-template-rows": "auto auto auto auto auto", "gap": "12px", "align-content": "start"},
    )


async def on_config(ctx: Context, frame: dict) -> None:
    """One settings uplink: merge, check, write on a throttle. The note says which member was refused."""
    store = state()
    before = dict(store.state)
    store.apply(frame.get("data"))
    lost = [name for name in store.rejected if name]
    if lost:
        ctx.slot("settings.note").set(h.text(f"Refused: {', '.join(sorted(lost))} (whitelist or range)"))
    elif store.state != before:
        ctx.slot("settings.note").set(h.text(f"Saved: {', '.join(sorted(store.state))}"))


def register(app, slots: Any = None) -> None:
    """Put this page on the app: its route, and its one uplink."""
    app.page("/settings", title="Settings")(page)
    app.on(CONFIG, on_config)