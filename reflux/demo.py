"""Serve the page by hand: the static tree plus the `/ws` channel.

    python3 -m reflux.demo                # 127.0.0.1:8000, the library's own www/
    python3 -m reflux.demo --port 0       # free port, printed
    python3 -m reflux.demo --root ./site  # serve a produced site instead

No page is declared, so the page loads, connects and draws nothing: this is the dev loop's
"serve the page and drive the planes by hand", not an application. To run an application, give it
its own App (`reflux.demo_app` is one).

uv is available but not required: the producer side has no dependencies.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .app import PAGE_ROOT, App


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="reflux.demo", description="Serve the reflux page.")
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
    srv = app.make_server(args.port, args.host)
    host, port = srv.server_address[0], srv.server_address[1]
    print(f"[reflux] serving {args.root} on http://{host}:{port}/  (ws {host}:{port}/ws)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())