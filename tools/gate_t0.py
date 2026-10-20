#!/usr/bin/env python3
"""T0 gate — the page boots with nothing but its own pinned assets.

Does the page load with zero console errors and zero off-origin requests? The answer is pinned to a
manifest: the request set must be *exactly* what `www/vendor/fluxen/versions.json` says plus the
page's own stylesheet, and every served byte must hash to the value in that manifest. A stale
vendored file, a hand-edited manifest, or a mount pointing at the wrong directory all fail here
rather than in a browser someone has to read.

    python3 tools/gate_t0.py

Needs no renderer checkout: the bundle is vendored under `www/`. Exit code 0 = gate passed.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cdp import console_errors, external_requests, report, open_page  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
WWW = REPO / "www"
VERSIONS = WWW / "static" / "vendor" / "fluxen" / "versions.json"
PAGE = "/"
STATIC = "/static/"

BOOT = "!!(window.fluxen && document.querySelector('#main').children.length)"


def manifest() -> dict:
    return json.loads(VERSIONS.read_text(encoding="utf-8"))


def served_paths(cdp) -> list[str]:
    """Same-origin request paths (query dropped), document and socket excluded."""
    urls = [p.get("request", {}).get("url", "") for p in cdp.of("Network.requestWillBeSent")]
    out: list[str] = []
    for url in urls:
        if url.startswith(("data:", "blob:", "about:")):
            continue
        path = "/" + url.split("://", 1)[1].split("/", 1)[1] if "://" in url else url
        path = path.split("?", 1)[0]
        out.append(path)
    return out


def fetch_sha(base: str, path: str) -> str:
    with urllib.request.urlopen(base + path, timeout=10) as res:
        return hashlib.sha256(res.read()).hexdigest()


def main() -> int:
    versions = manifest()
    assets = {STATIC + rel: want["sha256"] for rel, want in versions["files"].items()}
    expected = set(assets) | {
        PAGE,
        STATIC + "reflux.css",
        STATIC + "reflux.js",
        STATIC + "vendor/fluxen/versions.json",
    }
    checks: list[tuple[str, bool, str]] = []

    with open_page(path=PAGE, settle=0.8) as (cdp, base):
        mounted = cdp.eval("document.querySelector('#main').children.length")
        checks.append(("the page boots at the origin root", bool(mounted), f"#main children={mounted}"))

        total, foreign = external_requests(cdp, base)
        checks.append((
            "zero external requests",
            not foreign,
            f"{total} requests, all same-origin" if not foreign else f"external: {foreign}",
        ))

        seen = set(served_paths(cdp))
        checks.append((
            "the request set is exactly the pinned set",
            seen == expected,
            f"extra={sorted(seen - expected)} missing={sorted(expected - seen)}",
        ))

        bad = [path for path, want in assets.items() if fetch_sha(base, path) != want]
        checks.append((
            "every served byte matches its pinned sha256",
            not bad,
            f"{len(assets)} assets" if not bad else f"drifted: {bad}",
        ))

        # A missing module must never come back as the page: it would fail inside the browser in a
        # way nobody can read. The mount table's honest answer is a 404.
        try:
            urllib.request.urlopen(base + STATIC + "vendor/nope.js", timeout=10)
            refused = None
        except urllib.error.HTTPError as exc:
            refused = exc.code
            exc.close()
        checks.append(
            (
                "a missing module is a 404, not the page",
                refused == 404,
                f"GET {STATIC}vendor/nope.js -> {refused}",
            )
        )

        cdp.call("Page.navigate", url=base + PAGE + "blog/a/post")
        deadline = time.time() + 20
        while time.time() < deadline and not cdp.eval(BOOT):
            time.sleep(0.2)
        deep = cdp.eval("document.querySelector('#main').children.length")
        checks.append((
            "a deep link under the prefix gets the page",
            bool(deep),
            f"#main children={deep}",
        ))

        errors = console_errors(cdp)
        checks.append(("zero console errors", not errors, "none" if not errors else str(errors)))

    return report(checks, gate="T0 GATE")


if __name__ == "__main__":
    sys.exit(main())