"""The settings page: three things written into the page-options slot, live locally and remembered
by the server (ADR 0001).

Page options are fluxen's mechanism, not this page's invention: `#main` carries no `data-config`, so
the slot hanging off it is the default name `__CONFIG__` (fluxen ADR 0038 §2), the slot holds one
object, and members are decided **member by member** — the page's own half first, the far side (the
producer) after. The renderer then mirrors scalar members onto the document root as `data-<member>`,
and the browser-side table (`STYLE` in `www/static/reflux.js`) turns those into `:root` custom
properties. So this page adds no frame and no action — only three ordinary things:

1. **write** — one group's outlet is `Sink(dest="__CONFIG__", scope="both", path="/")`; `both` means
   "assign locally, then mirror up" (fluxen ADR 0031 §1), and a group has exactly one outlet, so this
   requirement has no other legal shape.
2. **remember** — `demo_app` hands the uplink to `on_config`, which applies the whitelist and the value
   ranges, merges, and schedules a throttled write. Persistence belongs to the example, not to the
   framework: `App` does not touch disk.
3. **starting value** — the first time a device is drawn, the shell writes the stored object into this
   slot, so a new connection, a refresh or another device shows the user's choices in its very first
   frame instead of flashing "default, then yours".

Three things can change: `sketch` (wireframe, boolean), `accent` (a `#rrggbb` colour) and `round` (an
integer 0–24). Anything outside the whitelist is dropped, and so is anything outside a value range —
both sides check, because the browser is not the trusted side and this file is read back by the next
process.
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

__all__ = ["CONFIG", "DEFAULTS", "MEMBERS", "Store", "flatten", "merge", "on_config", "page", "register", "seed", "state"]

CONFIG = "__CONFIG__"  # fluxen's page-options slot: `#main` has no `data-config`, so this is the default

DEFAULTS: dict[str, Any] = {"sketch": False, "accent": "#4fb3a5", "round": 10}

# One check per member: it returns the tidied value, or None when this member is dropped (the rest are
# still taken).
ACCENT = re.compile(r"^#[0-9a-fA-F]{6}$")


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in ("true", "false"):
        return value.lower() == "true"
    return None


def _accent(value: Any) -> str | None:
    cleaned = value.strip() if isinstance(value, str) else ""
    return cleaned.lower() if ACCENT.match(cleaned) else None


def _round(value: Any) -> int | None:
    if isinstance(value, bool):  # bool is an int subclass; it must not pass here
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if 0 <= number <= 24 else None


MEMBERS: dict[str, Any] = {"sketch": _bool, "accent": _accent, "round": _round}


def flatten(payload: Any) -> dict:
    """Unwrap a renderer-packed field group into `{member: value}`.

    A group's outlet sends each field with its own record (`{field: {"data": value, ...}}`, the same
    shape the chat page's `prompt_of` unwraps), while this page wants the members themselves — that
    layer is the renderer's, not the protocol's, so it is unwrapped here and unwrapped completely: a
    malformed frame gives `{}`, never an exception.
    """
    if not isinstance(payload, dict):
        return {}
    out: dict[str, Any] = {}
    for name, entry in payload.items():
        if isinstance(entry, dict):
            if "data" not in entry:  # a record without its value is malformed, not an object member
                continue
            entry = entry["data"]
        if entry is not None:
            out[name] = entry
    return out


def merge(state: dict, patch: dict) -> tuple[dict, list[str]]:
    """The state after the whitelist and the ranges, plus the members that were dropped.

    Only members that pass **and actually differ** are replaced, so an uplink that changed nothing
    never moves the disk.
    """
    merged = dict(state)
    rejected: list[str] = []
    for name, value in patch.items():
        check = MEMBERS.get(name)
        if check is None:
            rejected.append(name)
            continue
        clean = check(value)
        if clean is None:
            rejected.append(name)
            continue
        merged[name] = clean
    return merged, rejected


class Store:
    """The one thing this application remembers: its page options.

    The write is **throttled**: `submit=["change"]` means one uplink per keystroke (sliders and text
    fields alike), so several changes in a short window write only the last one, and a change that
    changed nothing writes nothing at all. The write is atomic (`.tmp`, then `replace`), because the
    next process reads it back.
    """

    def __init__(self, path: str | Path = ".demo-settings.json", delay: float = 0.35) -> None:
        self.path = Path(path)
        self.delay = delay
        self.state: dict[str, Any] = dict(DEFAULTS)
        self.writes = 0  # how many times it hit the disk: tests and the snapshot read this
        self.rejected: list[str] = []
        self._timer: asyncio.TimerHandle | None = None

    def load(self) -> dict:
        """Read what was stored (a missing file, bad JSON and out-of-whitelist members are just "none")."""
        try:
            stored = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return self.state
        self.state, _ = merge(self.state, stored if isinstance(stored, dict) else {})
        return self.state

    def apply(self, payload: Any) -> dict:
        """One uplink: merge, and schedule a write when something moved. Returns the merged state."""
        before = dict(self.state)
        self.state, self.rejected = merge(self.state, flatten(payload))
        if self.state != before:
            self.save_soon()
        return self.state

    def save_soon(self) -> None:
        """Schedule a write; the throttle window is `delay`, and another change inside it pushes it back."""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # no loop (a test calling the handler by hand): write now, don't pretend
            self.flush()
            return
        self._timer = loop.call_later(self.delay, self.flush)

    def flush(self) -> None:
        """Write once, now. `self.writes` counts them, so a test can tell "scheduled" from "written"."""
        self._timer = None
        temp = self.path.with_name(self.path.name + ".tmp")
        try:
            temp.write_text(json.dumps(self.state, ensure_ascii=False, indent=1), encoding="utf-8")
            temp.replace(self.path)
        except OSError as exc:  # there is no "disk full" setting: log it, don't turn a click into a crash
            print(f"[settings] could not write {self.path}: {exc!r}", flush=True)
            return
        self.writes += 1


settings = Store()


def state() -> Store:
    """The one store: there is one app."""
    return settings


def seed(ctx: Context) -> None:
    """The first time a device is drawn, write this slot (ADR 0001 §5).

    The order is the point: a slot write is a `send`, and the page's frame leaves at the end of
    `_draw`, so the value arrives first and the structure second — the renderer has the members
    before it paints the first page tree.
    """
    if ctx.data.get("config_seeded"):
        return
    ctx.data["config_seeded"] = True
    # The slot holds an **object**: fluxen reads this node's `source.default` (`config_members`), so it
    # is handed over in a `frame` with no shape of its own — the walkthrough's `payload()` spelling.
    ctx.slot(CONFIG).set(h.frame(source=Source(default=dict(state().state))))


def field(label: str, name: str, kind: str, value: Any) -> Accrete:
    """One setting: a line of prose and a field. The field's `tag` is the member name — the group's
    outlet packs by it."""
    return h.frame(
        h.text(label, variant="muted"),
        h.input(tag=name, kind=kind, selector="cfg", source=Source(default=value), id=f"cfg-{name}"),
        grid={"grid-template-columns": "1fr 2fr", "gap": "8px", "align-items": "center"},
        id=f"setting-{name}",
    )


def page(ctx: Context, match) -> Accrete:
    """The settings page — one group, three fields, one outlet.

    The outlet is written once (a group has exactly one); `submit=["change"]` says "send when a value
    changes", and `reset="keep"` says "don't clear after sending" — clearing is for forms, and a
    setting is not something that expires once submitted.
    """
    now = state().state
    return h.frame(
        h.text("Settings", variant="heading-1"),
        h.text(
            "These three go into the page-options slot `__CONFIG__`: live on this client at once, and "
            "mirrored up so the server remembers (ADR 0001). Wireframe belongs to the renderer (it draws "
            "borders off `data-sketch`); accent and round belong to `:root` custom properties.",
            variant="muted",
        ),
        h.loom(
            # a loom is one flex row: three rows go inside a frame — layout is the page's business
            # (the same shape as the review form).
            h.frame(
                field("Wireframe", "sketch", "bool", now["sketch"]),
                field("Accent", "accent", "text", now["accent"]),
                field("Round (0–24)", "round", "number", now["round"]),
                grid={"grid-template-rows": "auto auto auto", "gap": "10px"},
                id="config-rows",
            ),
            sink=Sink(dest=CONFIG, scope="both", path="/"),
            submit=["change"],
            reset="keep",
            id="config-form",
        ),
        h.text("Members outside the whitelist or outside a value range are dropped; both sides check, "
               "because the browser is not the trusted side.", variant="muted"),
        id="settings-page",
        grid={"grid-template-rows": "auto auto auto auto", "gap": "12px", "align-content": "start"},
    )


async def on_config(ctx: Context, frame: dict) -> None:
    """One settings uplink: merge, validate, schedule the write. The note line says what was dropped."""
    store = state()
    before = dict(store.state)
    store.apply(frame.get("data"))
    lost = [name for name in store.rejected if name]
    if lost:
        ctx.slot("settings.note").set(h.text(f"not accepted: {', '.join(sorted(lost))} (whitelist or range)"))
    elif store.state != before:
        ctx.slot("settings.note").set(h.text(f"saved: {', '.join(sorted(store.state))}"))


def register(app, slots: Any = None) -> None:
    """Put this page on the app: its route, and its one uplink."""
    app.page("/settings", title="Settings")(page)
    app.on(CONFIG, on_config)