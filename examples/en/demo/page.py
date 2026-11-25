"""The walkthrough page: fluxen's own story, contributed to the reference app as `/demo`.

    python3 -m examples.en.demo_app --port 8000      # then /demo, or the nav's "Walkthrough"

`fluxen/examples/walkthrough.py` is one message box that streams two charts, three radars, a review
table, two 3D models, a code editor and a growing relationship graph into itself. There the script
POSTs frames to `stage`'s console on a keyboard's rhythm (`Enter` per step) and the terminal is the
control; here the story is one route of the reference app, the script runs on the server for the
device that asked, and a floating button in the window's corner plays, pauses, resumes and replays.

The page is four regions and each region reads one slot — the island shape the renderer's own note
asks for (`fluxen/docs/ideas/islands.md`: a page divided into regions, one slot each, and a part is
declared rather than loaded):

    graph    the left column: a native forcegraph, fed cumulative snapshots
    stream   the right column: one row whose every child is bound to its own slot
    pins     the chips a drag dropped on the rail at the window's edge
    control  the floating button, and the line that says which beat is running

Two things are worth naming, because they are the reasons this is written the way it is:

- **A beat writes slots, never the page.** A slot write wakes only its reader, so a chart appearing
  re-renders its band and does not rebuild the message or remount a 3D viewer that is already up.
  That is why the row's children each have a slot, and why the page is drawn once per turn.
- **The button's label is a node, not a slot-bound string.** `button_` reads its label from
  `source.default` (`fluxen/crates/ui_core/src/widgets/button.rs`), so a label cannot come from a
  slot; the control region holds `frame(source=control)`, and the player writes the *node* the
  current state looks like. A frame's `source` mounts one node (ADR 0027), so one region, one slot,
  four states, and no page turn (a turn would remount every module inside the row).

The playback state hangs off `device.data`: a socket is one device, so two viewers each run their
own script, and closing the tab ends it. Nothing is shared, nothing persists.

The content is `demo_scene.py`'s (text, chart specs, a graph) — this module is the player, and it
knows nothing about what the story says.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from reflux import Context, Match
from reflux.sdk import h
from reflux.sdk.types import Accrete, Source
from reflux.slots import Slot

from . import scene

__all__ = [
    "BEATS",
    "PAGE",
    "PRESENT",
    "ROW_ID",
    "Run",
    "Settings",
    "Walkthrough",
    "install",
    "page",
    "register",
    "settings",
    "slots_of",
    "start",
    "state",
]

# ---- the module hosts this page draws with ------------------------------------------------------

HERE = Path(__file__).resolve().parents[2]  # the repository root: examples/demo/ is two levels down
VENDOR = HERE / "www" / "static" / "vendor"
ASSETS = Path(
    os.environ.get("REFLUX_ASSETS", HERE.parent / "fluxen" / "examples" / "renderer" / "assets")
)

CHART_URL = "/assets/g2chart/index.js"
VIEWER_URL = "/assets/3dbrowser/index.js"
SPLAT_URL = "/assets/splatviewer/index.js"
EDITOR_URL = "/assets/editor/index.js"
SHOE_URL = "/assets/3dbrowser/MaterialsVariantsShoe.glb"
TRUCK_URL = "/assets/splatviewer/truck.ksplat"


def _find(name: str, probe: str) -> Path | None:
    """A module's directory: a local vendor copy first, then a fluxen checkout."""
    for where in (VENDOR / name, ASSETS / name):
        if (where / probe).exists():
            return where
    return None


CHART = _find("g2chart", "index.js")
VIEWER = _find("3dbrowser", "index.js")
SPLAT = _find("splatviewer", "index.js")
EDITOR = _find("editor", "index.js")
# The editor module loads its own `../monaco/vs/…` and there is no `index.js` in that tree — the
# loader's entry is `vs/loader.js`, which is what the probe names.
MONACO = _find("monaco", "vs")

MOUNTS: dict[str, Any] = {
    "/assets/g2chart": CHART,
    "/assets/3dbrowser": VIEWER,
    "/assets/splatviewer": SPLAT,
    "/assets/editor": EDITOR,
    "/assets/monaco": MONACO,
}

# What the page can draw, asked once: a directory that is not on disk mounts nothing and its URL
# answers 404, so `/status` reports this and a reader can tell a missing file from a blank page.
PRESENT: dict[str, bool] = {
    "chart": CHART is not None,
    "viewer": VIEWER is not None,
    "splat": SPLAT is not None,
    "editor": EDITOR is not None,
    "monaco": MONACO is not None,
}


def install(app: Any) -> None:
    """Mount every module directory that is on disk — the app's HTTP table, not a page's.

    None of these is in git (`www/static/vendor/` is ignored and the 3D viewer is 30 MB with a model
    beside it), so each is served from wherever it exists. A host with nothing behind it reads as a
    bug on screen, which is why the page says where it looked instead of drawing an empty box.
    """
    for path, where in MOUNTS.items():
        if where is not None:
            app.mount(path, where)


# ---- the names ----------------------------------------------------------------------------------

# The page's four uplinks. A name is a slot and an uplink at once (ADR 0023): the rail's `sink` is
# `PIN`, and the handler that answers it is registered under the same name.
TOGGLE = Slot("demo.toggle")
PIN = Slot("demo.pin")
SAVE = Slot("demo.save")
REVIEW = Slot("demo.review")


class Walkthrough(Protocol):
    """This page's slots — the editor's view of them; the wire only ever sees the names.

    Every name in here is `demo.<field>`, so one handle (`ctx.slot("demo")`) reaches all of them and
    the page reads `s.stream`, not a string.
    """

    graph: Slot  # the left column's forcegraph
    stream: Slot  # the right column's row
    pins: Slot  # what a drag landed on the rail
    control: Slot  # the floating button's node
    beat: Slot  # which beat is running
    echo: Slot  # the app's answer to the last uplink
    analytics: Slot  # the intro paragraph
    trend: Slot  # the 30-day chart spec
    radar_rd: Slot
    radar_mkt: Slot
    radar_ops: Slot
    summary: Slot
    review_form: Slot  # the table + the form, one node so they arrive in one turn
    review_rows: Slot  # the table's rows
    say_car: Slot
    intro_car: Slot
    say_shoe: Slot
    intro_shoe: Slot
    say_patch: Slot
    patch_code: Slot
    say_graph: Slot
    toggle: Slot  # == TOGGLE: the rail's and the button's sink
    pin: Slot
    save: Slot
    review: Slot


def slots_of(ctx: Context) -> "Walkthrough":
    """One delivery's names for this page — `ctx.slot("demo")` nested, so `s.stream` is `demo.stream`."""
    return ctx.slot("demo")  # type: ignore[return-value]


PAGE = "/demo"
ROW_ID = "demo-row"
TEXT_VALUE = "/source/default"  # pointer into a text node stored in a slot
TREND_DATA = "/source/default/data"  # pointer into the trend spec's rows
PIN_TAG = "snippet"  # the rail only takes cargo tagged this way (ADR 0034)


@dataclass
class Settings:
    """How fast the story talks — a deployment's choice, filled from the command line."""

    pace: float = 0.03  # seconds per typewriter chunk (3 characters)
    hold: float = 0.35  # seconds between beats
    day: float = 0.12  # seconds per appended day on the trend


settings = Settings()


@dataclass
class Run:
    """One device's playback: what it may speak, where it stands, and what the graph shows.

    `phase` is explicit rather than inferred from the thread — a worker that has not been spawned
    yet and one that is mid-beat answer the same question differently, and the button has to know
    which case it is in.
    """

    phase: str = "idle"  # idle | playing | paused | done
    beat: int = 0  # 1-based index of the beat on screen; 0 = nothing drawn yet
    label: str = ""
    revealed: set[str] = field(default_factory=lambda: set(scene.GRAPH_SEED))
    resume: threading.Event = field(default_factory=threading.Event)  # set = the script may speak


def state(ctx: Context) -> Run:
    """This connection's playback, hung on `ctx.data` — it dies with the connection."""
    run = ctx.data.get("demo")
    if run is None:
        run = Run()
        ctx.data["demo"] = run
    return run


# ---- the page -------------------------------------------------------------------------------

# The floating control's box. `style` is written inline by the frame itself, so position is the
# page's to say; `border: var(--border)` is a shorthand token and must not be spelled out.
FLOAT = {
    "position": "fixed",
    "right": "24px",
    "bottom": "24px",
    "z-index": "50",
    "padding": "10px 14px",
    "background": "var(--bg)",
    "border": "var(--border)",
    "border-radius": "var(--round)",
    "box-shadow": "0 0.5rem 1.5rem rgba(0, 0, 0, 0.18)",
}

# The page is exactly one window tall, and it says so in the window's own units. `height: 100%` has
# nothing to resolve against here: a page is mounted into a node the renderer sizes by its content
# (`#page-root`, `flex: 1 0 auto`), so a percentage of it is a percentage of the page itself. The 83 px
# is the shell around this page as measured — two 16 px paddings, the 12 px gap and the 39 px nav row.
WINDOW = "calc(100vh - 97px)"

# The landing zone: a strip inside the stream column's right edge, over the page and not in it —
# a drag must not move what is under the pointer.
RAIL = {
    "position": "absolute",
    "top": "0",
    "right": "0",
    "bottom": "0",
    "width": "12px",
    "z-index": "5",
    "border-radius": "var(--round)",
}


def control(label: str) -> Accrete:
    """The floating button, in one of its four states: play → pause → resume → replay.

    The button is a bundle's confirm key (it has a sink and the bundle names the timing), and the
    label is the state's — which is why this whole node rides a slot instead of being drawn into
    the page.
    """
    return h.bundle(
        h.button(label, sink=TOGGLE),
        sink=TOGGLE,
        submit="button",
        id="demo-toggle",
    )


def page(ctx: Context, match: Match) -> None:
    """The page, and — once per connection — what the control region starts out holding.

    The floating control's first node is a *send*, like every seed: the page supplies structure, and
    a region's content is written to its slot. Seeding is guarded on the device because a slot
    outlives a `create` — drawing twice must not append the same chip twice.
    """
    s: Walkthrough = slots_of(ctx)
    if not ctx.data.get("demo_seeded"):
        ctx.data["demo_seeded"] = True
        s.control.set(control("▶ Play"))
        s.beat.set(h.text("not started · the button is bottom-right"))
        s.echo.set(h.text(""))
    return (
        h.frame(
            h.frame(  # the left column: one region, one slot
                h.forcegraph(
                    source=s.graph,
                    width="100%",
                    height="100%",
                    style={"fit_padding_px": 56},
                    id="graph",
                ),
                grid={"grid-template-rows": "1fr"},
                style={"min-height": "0", "min-width": "0"},
                id="demo-graph",
            ),
            h.frame(  # the right column: what landed, the stream, and the app's answers
                h.tiles(source=s.pins, dir="row", wrap="wrap", id="pins"),
                # The stream scrolls inside its own box: the row it holds is taller than any window,
                # and a page that grows with it drags the graph's canvas along (measured: a 3.9k-tall
                # forcegraph next to a 600-wide stream).
                h.frame(
                    h.tiles(source=s.stream, id="stream"),
                    grid={"grid-template-rows": "1fr"},
                    style={"overflow": "auto", "min-height": "0"},
                    id="stream-box",
                ),
                h.text(source=s.echo, variant="muted", id="echo"),
                h.frame(accept={"tag": PIN_TAG}, sink=s.pin, style=RAIL, id="rail"),
                grid={"grid-template-rows": "auto 1fr auto"},
                style={"min-height": "0", "min-width": "0", "position": "relative", "padding-right": "18px"},
                id="demo-stream-column",
            ),
            h.frame(  # the control region: fixed to the window, drawn once
                h.frame(source=s.control, id="demo-control"),
                h.text(source=s.beat, variant="muted", id="demo-beat"),
                grid={"grid-template-columns": "auto auto", "gap": "10px", "align-items": "center"},
                style=FLOAT,
                id="demo-playback",
            ),
            grid={"grid-template-columns": "minmax(0, 1fr) minmax(360px, 620px)", "gap": "12px"},
            style={"height": WINDOW, "min-height": "0", "box-sizing": "border-box"},
            id="demo-page",
        )
    )


# ---- the row --------------------------------------------------------------------------------

def band(*children: Accrete, rows: str, columns: str | None = None, id: str) -> Accrete:
    """A borderless container that gives its charts a definite size (ADR 0009).

    A canvas has no size of its own: it mounts a 100×100 surface and the page looks blank with zero
    console errors, so the size comes from the box it sits in.
    """
    grid: dict[str, str] = {"grid-template-rows": rows}
    if columns is not None:
        grid["grid-template-columns"] = columns
    return h.frame(*children, grid=grid, id=id)


def pin_tile(name: str, title: str) -> Accrete:
    """The row's one draggable unit: the cargo IS this subtree, read at dragstart (ADR 0034).

    `attrs.draggable` tags the box `snippet`, the rail's `accept` takes only that tag, and what
    lands is `{id, kind}` — the source adds no size or style of its own, so what the reader sees is
    the chip inside it.
    """
    return h.frame(
        h.text(f"≡ drag \u201c{title}\u201d to the right", variant="muted"),
        draggable={"tag": PIN_TAG},
        variant="card",
        id=f"pin-{name}",
    )


def row(s: Demo) -> Accrete:
    """One row, every child bound to its own slot — the reason a stream re-renders one segment.

    An empty data area takes no room (ADR 0012), so the box opens holding nothing and grows a
    segment at a time: a chart, a model or the editor appears the moment its payload lands, and
    nothing already on screen is rebuilt.
    """
    return h.frame(
        h.text(source=s.analytics, format="md", id="say-analytics"),
        pin_tile("analytics", "Analytics intro"),
        band(h.canvas(source=s.trend, url=CHART_URL, id="chart-trend"), rows="260px", id="band-trend"),
        band(
            h.canvas(source=s.radar_rd, url=CHART_URL, id="chart-rd"),
            h.canvas(source=s.radar_mkt, url=CHART_URL, id="chart-mkt"),
            h.canvas(source=s.radar_ops, url=CHART_URL, id="chart-ops"),
            rows="340px",
            columns="repeat(3, minmax(0, 1fr))",
            id="band-radar",
        ),
        h.text(source=s.summary, format="md", id="say-summary"),
        h.frame(source=s.review_form, id="review-here"),
        h.text(source=s.say_car, format="md", id="say-car"),
        h.canvas(source=s.intro_car, url=SPLAT_URL, width="100%", height="460px", id="car"),
        h.text(source=s.say_shoe, format="md", id="say-shoe"),
        h.canvas(source=s.intro_shoe, url=VIEWER_URL, width="100%", height="420px", id="shoe"),
        h.text(source=s.say_patch, format="md", id="say-patch"),
        h.canvas(source=s.patch_code, url=EDITOR_URL, width="100%", height="280px", id="editor"),
        h.text(source=s.say_graph, format="md", id="say-graph"),
        grid={"gap": "10px"},
        id=ROW_ID,
    )


REVIEW_FIELDS = [
    {"key": "score", "title": "Item", "width": "7rem"},
    {"key": "name", "title": "Name"},
    {"key": "dept", "title": "Dept"},
    {"key": "avg", "title": "Daily avg", "width": "5rem", "align": "end"},
    {"key": "note", "title": "Note"},
]

# What each field kind is called on screen — the wire's `number` / `bool` / `text` are the
# renderer's words, and a reader's are these.
KINDS = {"number": "number", "bool": "check", "text": "text"}


def review_row(key: str, initial: Any, name: str, dept: str, avg: str, note: str) -> Accrete:
    """One row of the table: an `entry` whose cells carry `selector` = the field's key.

    There is no table/thead/tr/td family (ADR 0031 §4): a `tiles` with `fields` places cells by
    key, and the header is derived from the fields' titles.
    """
    return h.entry(
        h.text(str(initial), selector="score"),
        h.text(name, selector="name"),
        h.text(dept, selector="dept"),
        h.text(avg, selector="avg"),
        h.text(note, selector="note"),
        id=f"review-{key}",
    )


def review_form(s: Demo) -> Accrete:
    """The table (rows arrive through a slot) and the form (fields a bundle can pack).

    Both halves are here because they cannot be one: `bundle` claims a field by walking its own
    static children (`hooks.rs`, `collect`), so a row that arrives through a slot is not one of its
    fields. The table is therefore the read-out and the three inputs below it are the form — a
    submit carries `{zw, cj, sy}`, one value per row, whichever kind that row's cell is.
    """
    return h.bundle(
        # One vertical box: a bundle is a flex row, so its children side by side squeeze the prose
        # into a column of single words (measured) — the layout inside is the page's to say.
        h.frame(
            h.text(
                "Review: the table above is this run's data (its rows come from a slot). Change one value in each"
                "of the three fields below (number / check / text) and submit: it goes up as `demo.review`.",
                format="md",
            ),
            h.tiles(
                fields=REVIEW_FIELDS,
                header={"selector": "review-head"},
                source=s.review_rows,
                id="review-table",
            ),
            h.frame(
                *(
                    h.input(
                        tag=key,
                        selector="score",
                        kind=kind, source=Source(default=initial),
                        placeholder=f"{name} · {KINDS.get(kind, kind)}",
                        id=f"field-{key}",
                    )
                    for key, kind, initial, name, *_ in scene.REVIEW
                ),
                h.button("Submit review", sink=s.review),
                grid={"grid-template-columns": "repeat(3, minmax(0, 1fr)) auto", "gap": "8px", "align-items": "center"},
                id="review-fields",
            ),
            grid={"grid-template-rows": "auto auto auto", "gap": "8px"},
            id="review-body",
        ),
        sink=s.review,
        submit=["enter", "button"],
        id="review-form",
    )


# ---- the beats ------------------------------------------------------------------------------

def payload(value: Any) -> Accrete:
    """A slot's value with no structure: a `frame` whose `source.default` IS the payload.

    A `frame` is the one node that owns a value (ADR 0027), and a module host reads its payload
    from its slot's node's `source.default` — so this is how a chart spec, a graph snapshot or a
    scene reaches a host.
    """
    return h.frame(source=Source(default=value))


def hold(run: Run, seconds: float) -> None:
    """A sleep that stops with the script: time spent paused does not count against it.

    `Event.wait` is not a sleep — a set event returns at once, which is exactly the wrong shape
    here. So the pause is a block (`wait()` with no timeout) and the clock is a real sleep in
    slices, which keeps a pause landing within 50 ms without giving up the pacing.
    """
    left = seconds
    while left > 0:
        if not run.resume.is_set():
            run.resume.wait()  # paused: block until the button says otherwise
        span = min(left, 0.05)
        time.sleep(span)
        left -= span


def type_out(run: Run, slot: Slot, text: str) -> None:
    """Three characters a frame, the way a model streams tokens — and a pause is a wait.

    The pause is read *before* each chunk, so a stopped script writes nothing new; the chunk already
    in flight still lands, which is why a gate reads a quiet window rather than one frame.
    """
    for at in range(0, len(text), 3):
        run.resume.wait()
        slot.patch(TEXT_VALUE, text[at : at + 3], op="append")
        hold(run, settings.pace)


def grow(run: Run, s: Demo, label: str) -> None:
    """Push the snapshot for what has appeared so far — the graph grows with the stream."""
    ids = next((ids for name, ids in scene.GRAPH_REVEAL if name == label), ())
    if not ids:
        return
    run.revealed.update(ids)
    s.graph.set(payload(scene.graph_payload(run.revealed)))


def beat_row(ctx: Context, run: Run, s: Demo) -> None:
    """The one row, the six text slots it will be typed into, and the graph's first snapshot."""
    with ctx.turn():  # the reader sees the box and its empty segments arrive together
        s.stream.append(row(s))
        for slot in (s.analytics, s.summary, s.say_car, s.say_shoe, s.say_patch, s.say_graph):
            slot.set(h.text(""))  # a patch needs a node to append into
        s.graph.set(payload(scene.graph_payload(run.revealed)))


def beat_analytics(ctx: Context, run: Run, s: Demo) -> None:
    type_out(run, s.analytics, scene.ANALYTICS)


def beat_charts(ctx: Context, run: Run, s: Demo) -> None:
    """Four specs in one frame: the line chart and the three radars fill their bands."""
    with ctx.turn():
        for name, spec in (("trend", scene.TREND), *scene.RADARS.items()):
            getattr(s, name).set(payload(spec))


def beat_days(ctx: Context, run: Run, s: Demo) -> None:
    """One frame per day, three appends each — the line grows to thirty days while the reader watches."""
    for day, *scores in scene.TAIL_DAYS:
        hold(run, settings.day)
        with ctx.turn():
            for dept, avg in zip(scene.DEPTS, scores):
                s.trend.patch(TREND_DATA, {"day": day, "avg": avg, "dept": dept}, op="append")


def beat_summary(ctx: Context, run: Run, s: Demo) -> None:
    type_out(run, s.summary, scene.SUMMARY)


def beat_review(ctx: Context, run: Run, s: Demo) -> None:
    with ctx.turn():  # the table arrives complete: its frame and its three rows together
        s.review_form.set(review_form(s))
        for key, _kind, initial, *cells in scene.REVIEW:
            s.review_rows.append(review_row(key, initial, *cells))


def beat_car(ctx: Context, run: Run, s: Demo) -> None:
    type_out(run, s.say_car, scene.SAY_CAR)
    s.intro_car.set(payload({"assets": {"scene": TRUCK_URL}, "camera": scene.TRUCK_CAMERA}))


def beat_shoe(ctx: Context, run: Run, s: Demo) -> None:
    type_out(run, s.say_shoe, scene.SAY_SHOE)
    s.intro_shoe.set(payload({"assets": {"shoe": SHOE_URL}}))


def beat_editor(ctx: Context, run: Run, s: Demo) -> None:
    """The code is a parameter like the two models: Monaco is fetched when the payload arrives."""
    type_out(run, s.say_patch, scene.PATCH)
    s.patch_code.set(payload({"code": scene.PATCH_CODE, "lang": "rust", "event": str(SAVE)}))


def beat_graph(ctx: Context, run: Run, s: Demo) -> None:
    type_out(run, s.say_graph, scene.SAY_GRAPH)


def beat_focus(ctx: Context, run: Run, s: Demo) -> None:
    """The equivalent of a search landing: the camera flies to a cluster, nothing else leaves."""
    snapshot = scene.graph_payload(run.revealed)
    snapshot["focus"] = {"ids": ["accrete", "content", "transport"], "seq": 1}
    s.graph.set(payload(snapshot))


BEATS: tuple[tuple[str, Callable[[Context, Run, Demo], None]], ...] = (
    ("message in", beat_row),
    ("analytics intro", beat_analytics),
    ("charts arrive", beat_charts),
    ("thirty days", beat_days),
    ("summary", beat_summary),
    ("review table", beat_review),
    ("splatted car", beat_car),
    ("shoe mesh", beat_shoe),
    ("code editor", beat_editor),
    ("graph passage", beat_graph),
    ("focus", beat_focus),
)


# ---- the player -----------------------------------------------------------------------------

def spawn(target: Callable[..., None], args: tuple) -> None:
    """Put the script on a thread. A module-level seam so a test can run it inline instead."""
    threading.Thread(target=target, args=args, daemon=True).start()


def play(ctx: Context) -> None:
    """The script, beat by beat. Synchronous on purpose: the thread is the caller's choice."""
    run = state(ctx)
    s: Walkthrough = slots_of(ctx)
    try:
        for index, (label, step) in enumerate(BEATS, start=1):
            run.resume.wait()  # a paused script does not start the next beat
            run.beat, run.label = index, label
            s.beat.set(h.text(f"{index}/{len(BEATS)} · {label}"))
            step(ctx, run, s)
            grow(run, s, label)
            hold(run, settings.hold)
    except Exception as failure:  # a demo's defect is a line on screen, not a dead thread
        run.phase = "done"
        s.control.set(control("↻ Replay"))
        s.beat.set(h.text(f"error: {type(failure).__name__} · {failure}"))
        return
    run.phase = "done"
    s.control.set(control("↻ Replay"))
    s.beat.set(h.text("done · 30 days of trend, a review that submits, an editor that writes back"))


def start(ctx: Context, run: Run) -> None:
    """Reset what a finished run left behind, then put the script on a thread.

    Only what the player wrote is cleared: the row (its children are re-seeded by the first beat,
    and its payloads are re-set by theirs) and the table's three rows. What the *reader* dropped on
    the rail stays — replaying the story is not undoing someone's pins.
    """
    s: Walkthrough = slots_of(ctx)
    if run.beat:
        s.stream.remove(ROW_ID)
        for key, *_ in scene.REVIEW:
            s.review_rows.remove(f"review-{key}")
    run.phase = "playing"
    run.beat, run.label = 0, ""
    run.revealed = set(scene.GRAPH_SEED)
    run.resume.set()
    s.control.set(control("⏸ Pause"))
    s.beat.set(h.text(f"0/{len(BEATS)} · start"))
    spawn(play, (ctx,))


def on_toggle(ctx: Context, frame: dict) -> None:
    """One button, four states: play → pause → resume → replay."""
    run = state(ctx)
    s: Walkthrough = slots_of(ctx)
    if run.phase in ("idle", "done"):
        start(ctx, run)
        return
    if run.phase == "playing":
        run.phase = "paused"
        run.resume.clear()
        s.control.set(control("▶ Resume"))
        s.beat.set(h.text(f"paused · {run.beat}/{len(BEATS)} · {run.label}"))
        return
    run.phase = "playing"
    run.resume.set()
    s.control.set(control("⏸ Pause"))
    s.beat.set(h.text(f"{run.beat}/{len(BEATS)} · {run.label}"))


def fields(frame: dict) -> dict:
    """A handler's payload: the frame's `data` as a bag, empty when the frame carries none.

    Every uplink on this page is read defensively — a malformed frame from a module or a stale
    client is a line on screen, not a raised handler (a raise would only reach the log).
    """
    data = frame.get("data")
    return data if isinstance(data, dict) else {}


def on_pin(ctx: Context, frame: dict) -> None:
    """A drag landed on the rail: the cargo's own id and kind, named on screen (ADR 0034)."""
    s: Walkthrough = slots_of(ctx)
    data = fields(frame)
    ident = data.get("id")
    if not ident:
        s.echo.set(h.text("the landing point got cargo with no id; nothing was recorded"))
        return
    kind = data.get("kind") or data.get("tag") or "—"
    # The chip is described by the payload (an id and a kind), so it is built from data: `h.node` and
    # `h.frame` are the same constructor — the first reads like "what a pin is", not "make a frame".
    s.pins.append(
        h.node(
            (
                "frame",
                {"variant": "card", "id": f"pin-{ident}"},
                [("text", {"variant": "muted"}, f"≡ {ident} · {kind}")],
            )
        )
    )
    s.echo.set(h.text(f"landing point got {ident} ({kind})"))


def on_save(ctx: Context, frame: dict) -> None:
    """Ctrl/Cmd+S in the editor: the code and its language, up the same leg the form uses."""
    s: Walkthrough = slots_of(ctx)
    data = fields(frame)
    code = data.get("code")
    if not isinstance(code, str):
        s.echo.set(h.text("the editor wrote back no code; nothing was recorded"))
        return
    s.echo.set(h.text(f"editor wrote back {len(code)} chars · {data.get('lang') or '—'}"))


def on_review(ctx: Context, frame: dict) -> None:
    """The form's fields, as the renderer packed them — one key per row."""
    s: Walkthrough = slots_of(ctx)
    data = frame.get("data") if isinstance(frame.get("data"), dict) else {}
    if not data:
        s.echo.set(h.text("it submitted, but with no fields: this frame only packs the form's own named fields"))
        return
    packed = ", ".join(f"{key}={value!r}" for key, value in data.items())
    s.echo.set(h.text(f"review submitted: {packed}"))


# ---- what an app does with this page --------------------------------------------------------------

def register(app: Any) -> None:
    """Put this page on an app: its route, and the four handlers under the names the page speaks to.

    The route is a call rather than a decorator because this module must not import the app: under
    `python3 -m examples.en.demo_app` the app module runs as `__main__`.
    """
    app.page(PAGE, title="Walkthrough")(page)
    app.on(TOGGLE, on_toggle)
    app.on(PIN, on_pin)
    app.on(SAVE, on_save)
    app.on(REVIEW, on_review)
