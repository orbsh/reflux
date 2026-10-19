#!/usr/bin/env python3
"""M1.1 gate — the renderer's page-level uplink handle (`window.fluxen.send`).

The renderer opens the socket itself (`mount()` builds the transport from `#main`), so the page's
own JS had no way to send anything up. M1.1 adds the door: `#main` carries `data-path` /
`data-codec`, and after mounting the renderer publishes `window.fluxen.send`.

The probe is assembled around the **vendored** bundle (`www/static/vendor/fluxen/`, named by its
`versions.json`), so this gate needs no sibling checkout and runs against exactly the bytes the
page ships: losing the handle in a renderer bump fails here.

    python3 tools/gate_m1_1.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cdp import console_errors, report, shell_page  # noqa: E402
from reflux.app import App  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
VENDOR = REPO / "www" / "static" / "vendor" / "fluxen"

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


def probe_root(vendor: Path) -> Path:
    """A throwaway document root: the pinned bundle, its stylesheets, and the probe page."""
    versions_path = vendor / "versions.json"
    if not versions_path.is_file():
        raise SystemExit(f"no pinned bundle at {vendor} — run the M1.2 bump procedure first")
    entry = json.loads(versions_path.read_text(encoding="utf-8"))["entry"]
    for name in (entry["js"], entry["wasm"]):
        if not (vendor / name).is_file():
            raise SystemExit(f"{name} is in versions.json but not on disk ({vendor})")

    root = Path(tempfile.mkdtemp(prefix="reflux-m1-1-"))
    shutil.copy2(vendor / entry["js"], root / entry["js"])
    shutil.copy2(vendor / entry["wasm"], root / entry["wasm"])
    (root / "assets").mkdir()
    # 渲染器自带的样式表（main.css 还会引到 custom.css）：缺一件就是一条 404，而 404 在这道门里
    # 算一条 console error —— 所以按清单里真有的那几件挂上去，不猜。
    links: list[str] = []
    for rel in ("assets/main.css", "assets/custom.css"):
        src = vendor / rel
        if src.is_file():
            shutil.copy2(src, root / rel)
            links.append(f'  <link rel="stylesheet" href="/{rel}" />')
    (root / "index.html").write_text(
        PAGE.replace("@@CSS@@", "\n".join(links))
        .replace("@@JS@@", entry["js"])
        .replace("@@WASM@@", entry["wasm"]),
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
    root = probe_root(VENDOR)
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