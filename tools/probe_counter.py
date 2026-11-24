"""Look at the counter page in Chromium: does it draw, and does a press move the number?

The offline suite asserts the frames; this checks the pixels and the round trip — the page's own tree
over a real socket, a click on ＋, and the number in the DOM changing from 0 to 1.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cdp import console_errors, open_page  # noqa: E402

from examples.zh import demo_app as example  # noqa: E402

with open_page(app=example.make_app(), path="/counter", settle=1.0) as (cdp, base):
    text = cdp.eval("document.body.innerText")
    print("--- body text ---")
    print(str(text)[:500])
    print("--- errors ---")
    print(console_errors(cdp)[:400])

    cdp.eval(
        """(() => {
             const labels = [...document.querySelectorAll('button')].map(b => b.textContent.trim());
             const plus = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === '＋');
             if (plus) plus.click();
             return labels;
           })()"""
    )
    time.sleep(0.8)
    after = str(cdp.eval("document.body.innerText"))
    print("--- after one press ---")
    print(after[:300])
    shot = cdp.call("Page.captureScreenshot", format="png")
    import base64
    out = Path("/home/master/.hermes/cache/scratch/counter.png")
    out.write_bytes(base64.b64decode(shot["data"]))
    print("screenshot:", out)
    print("base:", base)