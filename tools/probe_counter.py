"""Look at the counter page in Chromium: does it draw, and does a typed step reach the handler as a number?

The offline suite asserts the frames; this checks the pixels and the round trip — the page's own tree over
a real socket, a click on ＋, and `3` typed into the step box. It exits non-zero when a number is wrong.

The step box is the point of the second half: the field declares `kind="number"`, so the renderer parses
what was typed and the page's handler receives a number (`test_counter` can only hand it what it is given).
"""

from __future__ import annotations

import base64
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cdp import console_errors, open_page  # noqa: E402

from examples.zh import demo_app as example  # noqa: E402

# The renderer drops `id` on a text or input leaf, so the number is read where it lands: the first line of
# the page that is nothing but digits.
COUNT = (
    "(() => {"
    "  const lines = document.querySelector('#counter-page').innerText.split('\\n');"
    "  return (lines.find((l) => /^\\d+$/.test(l.trim())) || '').trim();"
    "})()"
)
STEP = "#counter-step-box input"


def press(cdp: Any, label: str) -> None:
    cdp.eval(
        "(() => {"
        f"  const b = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === '{label}');"
        "  if (b) b.click();"
        "})()"
    )
    time.sleep(0.8)


def number_in(cdp: Any, box: str, text: str) -> str:
    """Type into a field and press Enter, the way a person would — no synthetic `change` event."""
    kind = cdp.eval(
        "(() => {"
        f"  const el = document.querySelector('{box}');"
        "  if (!el) return 'missing';"
        "  el.focus(); el.select(); return el.type || 'text';"
        "})()"
    )
    cdp.type_text(text)
    for phase in ("rawKeyDown", "keyUp"):
        cdp.call(
            "Input.dispatchKeyEvent",
            type=phase,
            key="Enter",
            code="Enter",
            windowsVirtualKeyCode=13,
            nativeVirtualKeyCode=13,
        )
    time.sleep(0.8)
    return kind


with open_page(app=example.app, path="/counter", settle=1.0) as (cdp, base):
    print("--- body text ---")
    print(str(cdp.eval("document.body.innerText"))[:400])
    print("--- errors ---")
    print(console_errors(cdp)[:400])

    failures: list[str] = []

    press(cdp, "＋")
    counted = str(cdp.eval(COUNT))
    print("＋ →", counted)
    if counted != "1":
        failures.append(f"one press moved the number to {counted!r}, not 1")

    kind = number_in(cdp, STEP, "3")
    print("step box type:", kind)
    if kind != "number":
        failures.append(f"the step box is a {kind!r} field, so nothing parses what was typed")

    press(cdp, "＋")
    counted = str(cdp.eval(COUNT))
    print("＋ after a step of 3 →", counted)
    if counted != "4":
        failures.append(f"the step did not arrive as a number: the next press gave {counted!r}, not 4")

    shot = cdp.call("Page.captureScreenshot", format="png")
    out = Path("/home/master/.hermes/cache/scratch/counter.png")
    out.write_bytes(base64.b64decode(shot["data"]))
    print("screenshot:", out)
    print("base:", base)

if failures:
    for line in failures:
        print("FAIL", line)
    sys.exit(1)
print("COUNTER PROBE PASSED")