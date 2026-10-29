#!/usr/bin/env python3
"""T11 — measure the wire instead of arguing about it.

    python3 tools/measure.py                  # all four sections, markdown on stdout
    python3 tools/measure.py --only bytes,paint

Sections:

- **bytes** — one turn's JSON for each shape the reference app produces (offline). Also the
  envelope's own cost and the per-operation cost, so a future SDK in another language has a
  baseline to compare against byte for byte.
- **mutations** — how much DOM one turn changes, per plane (real browser). The claim under
  measurement is the one DESIGN makes: a turn is one transaction and the change lands on the plane
  it addresses, not on the whole tree.
- **paint** — the pinned assets' size, DOMContentLoaded, and the time from document start to a
  drawn tree (three runs, median).
- **cpu** — 100 sessions × 50 frames/s for 5 s. The clients run in a **child process**, so the CPU
  number is the server's own; frames are the denominator, not seconds.

What this does not do: it does not tune anything. Numbers that look wrong are a design question for
the next round, not a cue to add a cache here.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import statistics
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cdp import Ws, open_page  # noqa: E402

from reflux import ingest, wire  # noqa: E402
import reflux.demo_app as demo  # noqa: E402
from reflux.sdk import builders as b  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
VERSIONS = REPO / "www" / "static" / "vendor" / "fluxen" / "versions.json"
SESSION = "measure1"  # a session id of the right shape; no session is involved in the byte counts


def size(obj) -> int:
    """The wire is JSON text: this is what one turn costs on a socket."""
    return len(json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def table(title: str, header: list[str], rows: list[list[str]]) -> None:
    print(f"\n### {title}\n")
    print("| " + " | ".join(header) + " |")
    print("|" + "|".join("---" for _ in header) + "|")
    for row in rows:
        print("| " + " | ".join(row) + " |")


# --- bytes ---------------------------------------------------------------------------------


def seed_frame() -> dict:
    """The frame a fresh page gets: the structure, plus the rows the slot it reads needs."""
    return wire.draw(
wire.create(demo.demo.home()),
        *[wire.append(demo.ROWS, demo.row_node(row)) for row in demo.demo.rows])


def section_bytes() -> None:
    turns: list[tuple[str, dict]] = [
        ("echo (`set`)", wire.draw(wire.set(demo.ECHO, b.text("hello")))),
        (
            "add row (`append`)",
            wire.draw(wire.append(demo.ROWS, demo.row_node({"id": "row-4", "text": "第 4 行"}))),
        ),
        ("remove row (`remove`)", wire.draw(wire.remove(demo.ROWS, "row-1"))),
        (
            "form submit (`set`)",
            wire.draw(wire.set(demo.SUBMITTED, b.text('已提交 {"pass": "secret", "user": "ada"}'))),
        ),
        ("page turn (`create` + 2 seeded rows)", seed_frame()),
    ]
    rows = [[label, str(size(frame)), str(len(json.dumps(frame, ensure_ascii=False)))] for label, frame in turns]

    envelope = wire.draw(wire.empty())
    eleven = wire.draw(*[wire.empty()] * 11)
    per_op = (size(eleven) - size(envelope)) / 10
    rows.append(["1 `empty` op (a frame is just the array)", str(size(envelope)), "—"])
    rows.append(["each further `empty` op", f"{per_op:.1f}", "—"])

    table("one turn on the wire", ["turn", "bytes (utf-8)", "characters"], rows)


# --- mutations -----------------------------------------------------------------------------

OBSERVE = """
window.__muts = 0;
window.__mo = new MutationObserver(ms => { window.__muts += ms.length; });
window.__mo.observe(document.body, {childList: true, subtree: true, characterData: true});
true
"""


def section_mutations() -> None:
    app = demo.make_app()
    rows: list[list[str]] = []
    with open_page(path="/", app=app, settle=0.5) as (cdp, base):
        session = next(iter(app.live()), None)
        if session is None:
            print("\n### one turn's DOM changes\n\nno session: the page never connected")
            return
        cdp.eval(OBSERVE)

        def turn(label: str, frame: dict, marker: str) -> None:
            cdp.eval("window.__muts = 0")
            session.send(frame)
            deadline = time.time() + 5
            while time.time() < deadline:
                if marker in (cdp.eval("document.body.innerText") or ""):
                    break
                time.sleep(0.02)
            time.sleep(0.15)  # let the microtask-scheduled mirror and the animation frame flush
            rows.append([label, str(cdp.eval("window.__muts") or 0), marker])

        turn(
            "narrow: `set` on a data slot",
            wire.draw(wire.set(demo.ECHO, b.text("measured-echo"))),
            "measured-echo",
        )
        turn(
            "list: `append` one row",
            wire.draw(wire.append(demo.ROWS, demo.row_node({"id": "row-m", "text": "measured-row"}))),
            "measured-row",
        )
        turn(
            "whole tree: `create`",
            wire.draw(wire.create(b.case(b.text("rebuilt-page", id="probe")))),
            "rebuilt-page",
        )

    table(
        "one turn's DOM mutations (childList + characterData, subtree)",
        ["turn", "mutations", "the DOM it was waited on"],
        rows,
    )


# --- paint ---------------------------------------------------------------------------------

PAINT = """
window.__rx = { t0: performance.now(), first: 0 };
(function poll() {
  const m = document.getElementById("main");
  if (m && m.children.length) { window.__rx.first = performance.now() - window.__rx.t0; return; }
  setTimeout(poll, 4);
})();
"""


def section_paint() -> None:
    manifest = json.loads(VERSIONS.read_text(encoding="utf-8"))
    renderer = sum(item["size"] for item in manifest["files"].values())
    own = sum((REPO / "www" / "static" / name).stat().st_size for name in ("reflux.css", "reflux.js"))

    runs: list[float] = []
    dcls: list[float] = []
    app = demo.make_app()
    with open_page(path="/", app=app, settle=0.3) as (cdp, base):
        cdp.call("Page.addScriptToEvaluateOnNewDocument", source=PAINT)
        for _ in range(3):
            cdp.call("Page.navigate", url=base + "/")
            deadline = time.time() + 20
            first = 0
            while time.time() < deadline:
                first = cdp.eval("(window.__rx && window.__rx.first) || 0") or 0
                if first:
                    break
                time.sleep(0.05)
            dcl = cdp.eval(
                "(() => { const n = performance.getEntriesByType('navigation')[0];"
                " return n ? n.domContentLoadedEventEnd : 0; })()"
            ) or 0
            if first:
                runs.append(float(first))
                dcls.append(float(dcl))

    rows = [
        ["pinned renderer bundle", f"{renderer:,} B", "js + wasm + 2 css, from versions.json"],
        ["reflux's own assets", f"{own:,} B", "reflux.css + reflux.js"],
        [
            "document start → drawn tree (median of 3)",
            f"{statistics.median(runs):.0f} ms" if runs else "n/a",
            f"runs={[round(r) for r in runs]}",
        ],
        [
            "DOMContentLoaded (median of 3)",
            f"{statistics.median(dcls):.0f} ms" if dcls else "n/a",
            f"runs={[round(d) for d in dcls]}",
        ],
    ]
    table("first paint", ["what", "size / time", "how"], rows)


# --- cpu -----------------------------------------------------------------------------------

SESSIONS = 100
PER_SECOND = 50
SECONDS = 5.0


def _client(url: str, per_second: int, seconds: float, ready) -> None:
    """One child process full of clients: the server's CPU must not include them."""
    conns: list[Ws] = []

    def one() -> None:
        try:
            ws = Ws(url)
        except OSError:
            return
        conns.append(ws)
        gap = 1.0 / per_second
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                ws.send({"dest": "measure.ping", "id": "x", "data": "v"})
                ws.recv()
            except (EOFError, OSError):
                return
            time.sleep(gap)

    threads = [threading.Thread(target=one, daemon=True) for _ in range(SESSIONS)]
    for thread in threads:
        thread.start()
    time.sleep(1.0)  # let the connections land before the server's clock starts
    ready.set()
    for thread in threads:
        thread.join(timeout=seconds + 5)
    for ws in conns:
        try:
            ws.close()
        except OSError:
            pass


def check_cost() -> list[list[str]]:
    """What the two fences cost per frame — the price M1.5 accepted without a number."""
    op = wire.set(demo.ECHO, b.text("pong"))
    frame = wire.draw(op)
    uplink = {"dest": "measure.ping", "id": "x", "data": "v"}
    rounds = 3000

    def per_call(fn) -> float:
        start = time.perf_counter()
        for _ in range(rounds):
            fn()
        return (time.perf_counter() - start) / rounds * 1e6

    return [
        ["build one `set` op (`wire.set`)", f"{per_call(lambda: wire.set(demo.ECHO, b.text('pong'))):.1f} µs", "closed walk + parse + dump"],
        ["outbound fence (`ingest.check_frame`)", f"{per_call(lambda: ingest.check_frame(frame)):.1f} µs", "same walk again, at the socket"],
        ["inbound fence (`ingest.check_uplink`)", f"{per_call(lambda: ingest.check_uplink(uplink)):.1f} µs", "shape only, no node"],
    ]


def section_cpu() -> None:
    app = demo.make_app()
    app.dests.register("measure.ping", lambda session, frame: session.draw(wire.set(demo.ECHO, b.text("pong"))))
    server = app.make_server(0)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    ctx = multiprocessing.get_context("fork")
    ready = ctx.Event()
    child = ctx.Process(
        target=_client, args=(f"ws://127.0.0.1:{port}/ws", PER_SECOND, SECONDS, ready), daemon=True
    )
    child.start()
    ready.wait(timeout=30)

    peak = [0]
    sampling = threading.Event()

    def sample() -> None:
        while not sampling.is_set():
            peak[0] = max(peak[0], len(app.live()))
            time.sleep(0.05)

    threading.Thread(target=sample, daemon=True).start()

    # The burst is over when no new frame has landed for half a second — seconds are not the
    # denominator of anything here, frames are.
    cpu_before, wall_before = time.process_time(), time.monotonic()
    handled, quiet_since = app.dests.calls, time.monotonic()
    deadline = wall_before + SECONDS * 2 + 20
    while time.monotonic() < deadline:
        time.sleep(0.05)
        if app.dests.calls != handled:
            handled, quiet_since = app.dests.calls, time.monotonic()
        elif time.monotonic() - quiet_since > 0.5:
            break
    cpu, wall = time.process_time() - cpu_before, time.monotonic() - wall_before
    sampling.set()
    child.join(timeout=10)

    frames = app.dests.calls
    expected = SESSIONS * PER_SECOND * SECONDS
    rows = [
        ["connections issued", f"{app.stats['issued']:,}", f"of {SESSIONS} clients"],
        ["sessions live (peak)", f"{peak[0]:,}", "sampled every 50 ms during the burst"],
        ["frames handled", f"{frames:,}", f"of ~{expected:,} attempted ({frames / expected * 100:.1f} %)"],
        ["refused", str(app.stats["refused"]), "a non-zero here means the numbers are not clean"],
        ["server CPU", f"{cpu:.2f} s", f"process_time over {wall:.1f} s of wall clock"],
        ["per frame", f"{(cpu / frames * 1e6):.0f} µs" if frames else "n/a", "server CPU only, clients excluded"],
        [
            "sustained rate",
            f"{frames / wall:,.0f} frames/s" if wall else "n/a",
            f"target was {SESSIONS * PER_SECOND:,}/s — the clients share this machine, so the"
            " shortfall is a ceiling, not a throughput claim",
        ],
    ]
    table("server CPU under load", ["what", "value", "how"], rows)
    table("what one frame's checks cost (offline, median of 3000)", ["call", "per call", "what it does"], check_cost())

    server.shutdown()
    server.server_close()
    app.stop()


SECTIONS = {
    "bytes": section_bytes,
    "mutations": section_mutations,
    "paint": section_paint,
    "cpu": section_cpu,
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="measure", description="T11: measure the wire.")
    ap.add_argument(
        "--only", default=",".join(SECTIONS), help=f"comma-separated subset of {', '.join(SECTIONS)}"
    )
    args = ap.parse_args(argv)
    wanted = [name.strip() for name in args.only.split(",") if name.strip()]
    unknown = [name for name in wanted if name not in SECTIONS]
    if unknown:
        print(f"unknown section(s): {unknown}; pick from {list(SECTIONS)}")
        return 2
    for name in wanted:
        SECTIONS[name]()
    return 0


if __name__ == "__main__":
    sys.exit(main())