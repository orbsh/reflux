#!/usr/bin/env python3
"""M1.1 gate — the renderer's page-level uplink handle (`window.fluxen.send`).

The renderer opens the socket itself (`mount()` builds the transport from `#main`), so until now
the page's own JS had no way to send anything up. M1.1 adds the door: `#main` carries
`data-path` / `data-codec`, and after mounting the renderer publishes `window.fluxen.send`.

This gate runs the real bundle: it assembles a probe page around fluxen's dist, serves it through
`App` (so the `/ws` channel is the one the renderer reaches), and asserts on what crossed the wire.

    python3 tools/gate_m1_1.py
    REFLUX_FLUXEN_DIST=~/world/fluxen/crates/ui_leptos/dist python3 tools/gate_m1_1.py

The probe needs the renderer's built bundle and this repo does not vendor it yet (M1.2 decides that
form), so — same class as `tools/sync_schema.py` — the gate reads a sibling checkout and is not part
of the default gate set. A missing bundle is a loud failure, never a skip.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cdp import console_errors, report, shell_page  # noqa: E402
from reflux.app import App  # noqa: E402

DEFAULT_DIST = Path.home() / "world/fluxen/crates/ui_leptos/dist"

# The probe page is the smallest thing that exercises the door: `#main` pins the host's path and
# codec, the module waits for the wasm to boot, then calls the handle while the socket is still
# connecting (that call is what proves `emit` parks instead of dropping).
PAGE = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>m1.1 probe</title>
  <link rel="icon" href="data:," />
@@CSS@@
</head>
<body>
  <div id="main" data-codec="json" data-path="/ws"></div>
  <script type="module">
    import init from "/@@JS@@";
    await init({ module_or_path: "/@@WASM@@" });
    window.fluxen.send("early", { at: "before-open" });
    window.__early_called = true;
  </script>
</body>
</html>
"""


def probe_root(dist: Path) -> Path:
    """A throwaway document root: the renderer's bundle, its stylesheet, and the probe page."""
    if not dist.is_dir():
        raise SystemExit(
            f"no renderer bundle at {dist} — build it first "
            f"(cd crates/ui_leptos && trunk build) or point REFLUX_FLUXEN_DIST at one"
        )
    wasm = sorted(dist.glob("*_bg.wasm"))
    if len(wasm) != 1:
        raise SystemExit(f"expected exactly one *_bg.wasm under {dist}, found {len(wasm)}")
    wasm = wasm[0]
    js = dist / wasm.name.replace("_bg.wasm", ".js")
    if not js.is_file():
        raise SystemExit(f"no js glue beside {wasm.name} (expected {js.name})")

    root = Path(tempfile.mkdtemp(prefix="reflux-m1-1-"))
    shutil.copy2(wasm, root / wasm.name)
    shutil.copy2(js, root / js.name)
    (root / "assets").mkdir()
    # 渲染器自带的样式表（main.css 还会引到 custom.css）：缺一件就是一条 404，而 404 在这道门里
    # 算一条 console error —— 所以按 dist 里真有的那几件挂上去，不猜。
    links: list[str] = []
    for name in ("main.css", "custom.css"):
        src = dist / "assets" / name
        if src.is_file():
            shutil.copy2(src, root / "assets" / name)
            links.append(f'  <link rel="stylesheet" href="/assets/{name}" />')
    (root / "index.html").write_text(
        PAGE.replace("@@CSS@@", "\n".join(links))
        .replace("@@JS@@", js.name)
        .replace("@@WASM@@", wasm.name),
        encoding="utf-8",
    )
    return root


def frames(app: App, event: str) -> list[dict]:
    """Inbound frames the producer got under one event name, in arrival order."""
    return [
        frame
        for direction, frame in list(app.log)
        if direction == "recv" and isinstance(frame, dict) and frame.get("event") == event
    ]


def wait_frame(app: App, event: str, timeout: float = 10.0) -> list[dict]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        got = frames(app, event)
        if got:
            return got
        time.sleep(0.05)
    return []


def main() -> int:
    dist = Path(os.environ.get("REFLUX_FLUXEN_DIST", str(DEFAULT_DIST))).expanduser()
    root = probe_root(dist)
    app = App(root)
    checks: list[tuple[str, bool, str]] = []

    try:
        with shell_page(root=root, app=app, boot="window.fluxen && typeof window.fluxen.send === 'function'") as (
            cdp,
            base,
        ):
            mounted = cdp.eval("(document.querySelector('#main') || {children: []}).children.length > 0")
            checks.append(("the renderer mounts into #main", bool(mounted), f"children={'yes' if mounted else 'none'}"))

            sockets = [e.get("url", "") for e in cdp.of("Network.webSocketCreated")]
            expected = base.replace("http://", "ws://") + "/ws?codec=json"
            checks.append(
                (
                    "the socket lands on the host's path and codec",
                    sockets == [expected],
                    f"urls={sockets}",
                )
            )

            cdp.eval("window.fluxen.send('probe', {v: 1})")
            got = wait_frame(app, "probe")
            frame = got[0] if got else {}
            checks.append(
                (
                    "the page-level handle reaches the producer",
                    bool(got) and frame.get("data") == {"v": 1} and "id" not in frame,
                    f"frame={frame!r}",
                )
            )

            early = wait_frame(app, "early")
            early_frame = early[0] if early else {}
            checks.append(
                (
                    "a call before the socket opened is not lost",
                    bool(cdp.eval("window.__early_called === true"))
                    and bool(early)
                    and early_frame.get("data") == {"at": "before-open"},
                    f"frame={early_frame!r}",
                )
            )

            errors = console_errors(cdp)
            checks.append(("zero console errors", not errors, "none" if not errors else str(errors)))
    finally:
        app.stop()
        shutil.rmtree(root, ignore_errors=True)

    return report(checks, gate="M1.1 GATE")


if __name__ == "__main__":
    sys.exit(main())