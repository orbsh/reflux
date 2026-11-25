"""Serve the page by hand: the static tree plus the `/ws` channel.

    python3 tools/serve.py                # 127.0.0.1:8000, the library's own www/
    python3 tools/serve.py --port 0       # free port, printed
    python3 tools/serve.py --root ./site  # serve a produced site instead

No page is declared, so the page loads, connects and draws nothing: this is the dev loop's
"serve the page and drive the planes by hand", not an application. To run an application, give it
its own App (`examples/zh/demo_app.py` is one).

uv is available but not required: the producer side has no dependencies.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import sys
from pathlib import Path

from reflux.app import PAGE_ROOT, App


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="serve", description="Serve the reflux page.")
    ap.add_argument("--port", type=int, default=8000, help="0 picks a free port (default: 8000)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument(
        "--root",
        type=Path,
        default=PAGE_ROOT,
        help="assets root (default: this library's www/)",
    )
    args = ap.parse_args(argv)

    app = App(args.root)
    # One entry shape (ADR 0002 §7): the app serves itself, prints where, and stops on Ctrl-C.
    app.serve_forever(args.port, args.host)
    return 0


if __name__ == "__main__":
    sys.exit(main())