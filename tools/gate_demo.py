"""The walkthrough page's gate: the script over a real socket, then the page in Chromium.

Phase A is a client like any other — `hello` for `/demo`, then the floating button, and the frames
the server sends back for the whole story. What it proves that the offline suite cannot: the frames
cross a socket (nothing refused), the pause really stops a worker thread mid-typewriter, and the
story's text arrives whole when it is resumed.

Phase B opens the same page in Chromium and looks at the pixels: the control is fixed to the
window's corner, pressing it starts playback, and a chart module gets a size. A module that is not
on disk is reported as skipped, not failed (the page says where it looked instead).

Run it with `python3 tools/gate_demo.py` (needs Chromium for phase B).
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # the cdp fixture
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # the example package

from cdp import console_errors, open_page, report  # noqa: E402

from examples.zh import demo_app as example  # noqa: E402
from examples.zh.demo import page as demo  # noqa: E402
from examples.zh.demo import scene  # noqa: E402
from examples.zh.demo import page as assets  # the module hosts live with the page that draws them
from tools.wire_probe import Socket  # noqa: E402

# The story is ~500 frames; this pace leaves room to pause inside it and still ends in seconds.
demo.settings.pace = 0.008
demo.settings.hold = 0.05
demo.settings.day = 0.02

PORT = 0


def wait_for(probe, timeout: float = 20.0, step: float = 0.15):
    """Poll a probe until it is truthy (or the deadline passes, and it answers once more)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = probe()
        if value:
            return value
        time.sleep(step)
    return probe()


def read_until(ws: Socket, quiet: float) -> list[list[dict]]:
    """Every frame until the socket has been quiet for `quiet` seconds."""
    frames: list[list[dict]] = []
    while True:
        try:
            frame = ws.recv(timeout=quiet)
        except TimeoutError:
            return frames
        if frame is None:
            return frames
        frames.append(frame)


def read_for(ws: Socket, seconds: float) -> list[list[dict]]:
    """Every frame that arrives in the next `seconds` — the reader for a stream that never pauses.

    `read_until` cannot be used while the typewriter is running: it waits for a quiet window, and a
    stream at 8 ms a chunk never gives one, so it would return only after the whole story.
    """
    frames: list[list[dict]] = []
    end = time.monotonic() + seconds
    while (left := end - time.monotonic()) > 0:
        try:
            frame = ws.recv(timeout=left)
        except TimeoutError:
            return frames
        if frame is None:
            return frames
        frames.append(frame)
    return frames


def ops(frames: list[list[dict]], action: str, slot: str) -> list[dict]:
    return [op for frame in frames for op in frame if op.get("action") == action and op.get("slot") == slot]


def nodes(node, out: list[dict] | None = None) -> list[dict]:
    """Every node of a tree (or of every op in every frame), flattened."""
    out = [] if out is None else out
    if isinstance(node, list):
        for item in node:
            nodes(item, out)
    elif isinstance(node, dict):
        out.append(node)
        for key in ("children", "item"):
            nodes(node.get(key) or [], out)
    return out


def sources_of(node) -> set[str]:
    return {
        child["source"]["slot"]
        for child in nodes(node)
        if isinstance(child.get("source"), dict) and child["source"].get("slot")
    }


def label_of(control: dict | None) -> str:
    """The label a control-slot node carries — the button's own `source.default`."""
    for node in nodes(control or {}):
        if node.get("type") == "button":
            return ((node.get("source") or {}).get("default")) or ""
    return ""


def beat_of(op: dict) -> str:
    return ((op.get("data") or {}).get("source") or {}).get("default") or ""


# --- phase A: the wire -----------------------------------------------------------------------


def socket_phase() -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []
    app = example.make_app()
    srv = app.make_server(0)
    global PORT
    PORT = int(srv.server_address[1])
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    frames: list[list[dict]] = []
    try:
        with Socket(PORT) as ws:
            ws.send({"dest": "reflux:hello", "data": {"path": "/demo"}})
            opening = read_until(ws, 0.5)
            frames += opening

            # 1 — the shell once, the page into the routes slot, both in one frame (T9's shape).
            # A page that seeds sends those writes first (`ctx.emit` is a send, and the framework
            # composes the structure after the handler returns), so the frame is *found*, not assumed.
            structure = next((f for f in opening if any(op.get("slot") == "routes" for op in f)), [])
            page = next((op.get("data") for op in structure if op.get("slot") == "routes"), None)
            checks.append(
                (
                    "connect draws the shell and the /demo page in one frame",
                    [op.get("action") for op in structure] == ["create", "set"] and page is not None,
                    f"frames={[len(f) for f in opening]} structure={[op.get('action') for op in structure]}",
                )
            )

            # 2 — the island shape: four regions, one slot each, and the control is the fixed one.
            regions = sources_of(page)
            floating = [n for n in nodes(page) if (n.get("attrs") or {}).get("style", {}).get("position") == "fixed"]
            checks.append(
                (
                    "the page is four regions reading four slots",
                    {"demo.graph", "demo.stream", "demo.pins", "demo.echo", "demo.control", "demo.beat"} <= regions
                    and len(floating) == 1,
                    f"regions={sorted(regions)[:8]} fixed={len(floating)}",
                )
            )

            # 3 — the control arrives seeded, and says the story has not started.
            control = next((op.get("data") for op in (o for f in opening for o in f) if op.get("slot") == "demo.control"), None)
            beat = next((beat_of(op) for op in (o for f in opening for o in f) if op.get("slot") == "demo.beat"), "")
            checks.append(
                (
                    "the control starts as a play button",
                    label_of(control) == "▶ 播放" and "未开始" in beat,
                    f"label={label_of(control)!r} beat={beat!r}",
                )
            )

            # 4 — pressing it: the row lands once, and the six text slots are seeded before any typing.
            ws.send({"dest": "demo.toggle", "id": "demo-toggle", "data": {}})
            started = read_for(ws, 0.35)
            frames += started
            appends = ops(started, "append", "demo.stream")
            seeds = {op["slot"] for op in (o for f in started for o in f) if op.get("action") == "set" and op["slot"] in
                     {"demo.analytics", "demo.summary", "demo.say_car", "demo.say_shoe", "demo.say_patch", "demo.say_graph"}}
            first_patch = next((i for i, f in enumerate(started) for op in f if op.get("action") == "patch" and op.get("slot") == "demo.analytics"), None)
            seeded_first = first_patch is not None and all(
                any(op.get("action") == "set" and op["slot"] == name for f in started[:first_patch] for op in f) for name in seeds
            )
            checks.append(
                (
                    "the story starts: one row, six seeded slots, then typing",
                    len(appends) == 1 and appends[0]["data"]["id"] == demo.ROW_ID and len(seeds) == 6 and seeded_first,
                    f"rows={len(appends)} seeds={len(seeds)} first_patch={first_patch}",
                )
            )

            # 5 — what the typewriter does on the wire: three characters a frame, one slot, one pointer.
            patches = ops(started, "patch", "demo.analytics")
            checks.append(
                (
                    "the typewriter appends three characters a frame",
                    bool(patches)
                    and all(op["path"] == demo.TEXT_VALUE and op["op"] == "append" and len(op["value"]) <= 3 for op in patches),
                    f"patches={len(patches)} sample={patches[0]['value']!r}" if patches else "patches=0",
                )
            )

            # 6 — pause: the worker stops at a chunk boundary, and the control says which state it is in.
            ws.send({"dest": "demo.toggle", "id": "demo-toggle", "data": {}})
            paused = read_for(ws, 0.2)
            frames += paused
            control = next((op.get("data") for op in (o for f in reversed(paused) for o in reversed(f)) if op.get("slot") == "demo.control"), None)
            half = "".join(op["value"] for op in ops(frames, "patch", "demo.analytics"))
            quiet = read_until(ws, 0.35)
            frames += quiet
            checks.append(
                (
                    "pause stops the stream mid-paragraph and the button offers to continue",
                    label_of(control) == "▶ 继续"
                    and quiet == []
                    and 0 < len(half) < len(scene.ANALYTICS)
                    and scene.ANALYTICS.startswith(half),
                    f"label={label_of(control)!r} typed={len(half)}/{len(scene.ANALYTICS)} frames_while_paused={len(quiet)}",
                )
            )

            # 7 — resume: the rest of the story, and the paragraph is whole (no gap, no repeat).
            ws.send({"dest": "demo.toggle", "id": "demo-toggle", "data": {}})
            rest: list[list[dict]] = []
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                rest += read_for(ws, 0.5)
                said = [beat_of(op) for op in (o for f in rest for o in f) if op.get("slot") == "demo.beat"]
                if said and said[-1].startswith("完"):
                    break
            frames += rest
            typed = "".join(op["value"] for op in ops(frames, "patch", "demo.analytics"))
            control = next((op.get("data") for op in (o for f in reversed(rest) for o in reversed(f)) if op.get("slot") == "demo.control"), None)
            checks.append(
                (
                    "resume finishes the story and the paragraph arrives whole",
                    typed == scene.ANALYTICS and label_of(control) == "↻ 重播",
                    f"typed={len(typed)}/{len(scene.ANALYTICS)} label={label_of(control)!r}",
                )
            )

            # 8 — the four chart specs, exactly as the example ships them.
            trend = ops(frames, "set", "demo.trend")
            radars = {
                slot: len({row["dim"] for row in ops(frames, "set", f"demo.{slot}")[0]["data"]["source"]["default"]["data"]})
                for slot in ("radar_rd", "radar_mkt", "radar_ops")
            }
            checks.append(
                (
                    "the charts carry a 15-day line and three radars of 5/6/7 axes",
                    len(trend) == 1
                    and len(trend[0]["data"]["source"]["default"]["data"]) == 45
                    and radars == {"radar_rd": 5, "radar_mkt": 6, "radar_ops": 7},
                    f"rows={len(trend[0]['data']['source']['default']['data']) if trend else 0} radars={radars}",
                )
            )

            # 9 — the line grows one frame a day, three appends a frame.
            days = ops(frames, "patch", "demo.trend")
            checks.append(
                (
                    "the line grows fifteen frames of three appends",
                    len(days) == len(scene.TAIL_DAYS) * 3
                    and all(op["path"] == demo.TREND_DATA and op["op"] == "append" for op in days)
                    and days[-1]["value"]["day"] == "10-02",
                    f"appends={len(days)} last={days[-1]['value']['day'] if days else None}",
                )
            )

            # 10 — the review: a table whose rows come from a slot, and a form a bundle can pack.
            formed = ops(frames, "set", "demo.review_form")
            form = formed[0]["data"] if formed else {}
            table = next((n for n in nodes(form) if n.get("type") == "tiles"), {})
            tagged = sorted(n["tag"] for n in nodes(form) if n.get("type") == "input" and n.get("tag"))
            rows = [op["data"]["id"] for op in ops(frames, "append", "demo.review_rows")]
            checks.append(
                (
                    "the review table and its three-field form arrive",
                    len(formed) == 1
                    and form.get("sink", {}).get("slot") == "demo.review"
                    and [f["key"] for f in (table.get("attrs") or {}).get("fields") or []] == ["score", "name", "dept", "avg", "note"]
                    and tagged == ["cj", "sy", "zw"]
                    and rows == [f"review-{key}" for key, *_ in scene.REVIEW],
                    f"fields={len(table.get('attrs', {}).get('fields') or [])} tagged={tagged} rows={len(rows)}",
                )
            )

            # 11 — the three payloads are the ones the modules read.
            car = (ops(frames, "set", "demo.intro_car") or [{"data": {}}])[0]["data"].get("source", {}).get("default", {})
            shoe = (ops(frames, "set", "demo.intro_shoe") or [{"data": {}}])[0]["data"].get("source", {}).get("default", {})
            code = (ops(frames, "set", "demo.patch_code") or [{"data": {}}])[0]["data"].get("source", {}).get("default", {})
            checks.append(
                (
                    "the two models and the editor get their payloads",
                    (car.get("assets") or {}).get("scene") == assets.TRUCK_URL
                    and (shoe.get("assets") or {}).get("shoe") == assets.SHOE_URL
                    and code.get("lang") == "rust"
                    and code.get("event") == "demo.save"
                    and code.get("code") == scene.PATCH_CODE,
                    f"car={bool(car)} shoe={bool(shoe)} code={len(code.get('code') or '')}",
                )
            )

            # 12 — the graph: cumulative snapshots, ending with the focus that a search would land.
            sizes = [len(op["data"]["source"]["default"]["nodes"]) for op in ops(frames, "set", "demo.graph")]
            focus = (ops(frames, "set", "demo.graph") or [{"data": {}}])[-1]["data"].get("source", {}).get("default", {}).get("focus")
            checks.append(
                (
                    "the graph only ever grows, and ends focused",
                    bool(sizes) and sizes == sorted(sizes) and sizes[-1] == len(scene.GRAPH_NODES) and focus == {"ids": ["accrete", "content", "transport"], "seq": 1},
                    f"sizes={sizes} focus={focus}",
                )
            )

            # 13 — the three uplinks answer on the page itself (this is what `stage`'s console was).
            ws.send({"dest": "demo.pin", "id": "rail", "data": {"id": "widget", "kind": "snippet"}})
            ws.send({"dest": "demo.review", "id": "review-form", "data": {"zw": 4.1, "cj": False, "sy": "已复核"}})
            ws.send({"dest": "demo.save", "id": "editor", "data": {"code": "fn main() {}", "lang": "rust"}})
            answered = read_until(ws, 0.6)
            frames += answered
            pins = ops(answered, "append", "demo.pins")
            echo = [beat_of(op) for op in (o for f in answered for o in f) if op.get("slot") == "demo.echo"]
            checks.append(
                (
                    "a dropped pin, a submitted form and a saved editor all answer",
                    len(pins) == 1 and any("复核已提交" in line for line in echo) and any("编辑器回传" in line for line in echo),
                    f"pins={len(pins)} echo={echo[-2:]}",
                )
            )

            # 14 — nothing the app produced was refused or raised along the way.
            checks.append(
                (
                    "nothing was refused",
                    app.stats["refused"] == 0,
                    f"refused={app.stats['refused']}",
                )
            )
    finally:
        app.stop()
        srv.shutdown()
        srv.server_close()
    return checks


# --- phase B: the pixels ---------------------------------------------------------------------


def browser_phase() -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []
    with open_page(app=example.make_app(), path="/demo", settle=0.8) as (cdp, base):
        drawn = wait_for(lambda: "未开始" in (cdp.eval("document.body.innerText") or ""), timeout=20)
        checks.append(
            (
                "the demo draws with its control",
                bool(drawn),
                f"body={(cdp.eval('document.body.innerText') or '')[:40]!r}",
            )
        )
        if not drawn:
            print(f"    base={base}")
            return checks

        # 1 — the control is the one thing fixed to the window, at its bottom-right corner.
        corner = cdp.eval(
            "(() => {const el = document.getElementById('demo-playback');"
            " if (!el) return null; const box = el.getBoundingClientRect();"
            " return {position: getComputedStyle(el).position,"
            " right: Math.round(window.innerWidth - box.right),"
            " bottom: Math.round(window.innerHeight - box.bottom)};})()"
        )
        checks.append(
            (
                "the floating control sits at the window's corner",
                bool(corner) and corner["position"] == "fixed" and 0 <= corner["right"] <= 40 and 0 <= corner["bottom"] <= 40,
                f"corner={corner}",
            )
        )

        # 2 — pressing it starts the story: the label flips and the page starts carrying prose.
        cdp.click_js("[...document.querySelectorAll('.button')].filter(el => (el.innerText || '').trim() === '▶ 播放')[0]")
        started = wait_for(lambda: "暂停" in (cdp.eval("document.body.innerText") or ""), timeout=10)
        grew = wait_for(lambda: len(cdp.eval("document.body.innerText") or "") > 200, timeout=25)
        checks.append(
            (
                "pressing it starts the story",
                bool(started) and bool(grew),
                f"paused_label={bool(started)} chars={len(cdp.eval('document.body.innerText') or '')}",
            )
        )

        # 3 — a module host that is on disk gets a real drawing buffer (empty module = a bug, not a page).
        if assets.PRESENT["chart"]:
            size = wait_for(
                lambda: cdp.eval("[...document.querySelectorAll('canvas')].map(c => c.width * c.height).filter(a => a > 20000).length"),
                timeout=25,
            )
            checks.append(("the chart module mounts into its band", bool(size) and int(size) >= 1, f"big canvases={size}"))
        else:
            checks.append(("the chart module mounts into its band", True, f"skipped: g2chart is not on disk (looked in {assets.ASSETS})"))

        errors = console_errors(cdp)
        checks.append(("the page logged no console errors", not errors, f"errors={errors[:2]}"))
    return checks


def main() -> int:
    checks = socket_phase() + browser_phase()
    return report(checks, gate="DEMO GATE")


if __name__ == "__main__":
    raise SystemExit(main())