#!/usr/bin/env python3
"""T0 gate — the shell loads with zero console errors and zero external requests.

Runs the real thing: serves `shell/` from this repo, loads it in headless chromium over CDP
(the harness lives in tools/cdp.py), and asserts on what the browser actually did.

    python3 tools/gate_t0.py

Exit code 0 = gate passed. Every check prints its evidence.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cdp import console_errors, external_requests, report, shell_page  # noqa: E402


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    with shell_page() as (cdp, base):
        total, foreign = external_requests(cdp, base)
        checks.append(
            (
                "zero external requests",
                not foreign,
                f"{total} requests, all same-origin" if not foreign else f"external: {foreign}",
            )
        )

        errors = console_errors(cdp)
        checks.append(("zero console errors", not errors, "none" if not errors else str(errors)))

        probe = cdp.eval("document.getElementById('app').dataset.probe")
        checks.append(("mount probe", probe == "booted", f"data-probe={probe!r}"))

        text = cdp.eval("document.getElementById('app').innerText") or ""
        checks.append(
            ("store write reached the DOM", "store live" in text, f"innerText={text.strip()!r}")
        )

    return report(checks, gate="T0 GATE")


if __name__ == "__main__":
    sys.exit(main())