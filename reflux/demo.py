"""Serve the reflux shell.

    python3 -m reflux.demo                # 127.0.0.1:8000, the library's own shell/
    python3 -m reflux.demo --port 0       # free port, printed
    python3 -m reflux.demo --root ./site  # serve a produced site instead

uv is available but not required: the producer side has no dependencies.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .server import make_server

SHELL_ROOT = Path(__file__).resolve().parent.parent / "shell"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="reflux.demo", description="Serve the reflux shell.")
    ap.add_argument("--port", type=int, default=8000, help="0 picks a free port (default: 8000)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument(
        "--root",
        type=Path,
        default=SHELL_ROOT,
        help="assets root (default: this library's shell/)",
    )
    args = ap.parse_args(argv)

    srv = make_server(args.root, args.port, args.host)
    host, port = srv.server_address[0], srv.server_address[1]
    print(f"[reflux] serving {args.root} on http://{host}:{port}/", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())