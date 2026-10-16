"""The producer's command line: print what an imported app registered.

    python3 -m reflux.cli routes myapp

`routes` imports the packages you name — their decorators register as a side effect of import —
and prints the table: path, source module, metadata fields. Nothing is derived from a file name,
so the source column is where the route was written, not where the framework guessed.

`events` (the event-name registry) is not here yet: printing it needs a convention for finding the
application that owns a registry, while routes need none (they live in one default table). That
convention belongs to the task that assembles an app from packages; it is recorded in PLAN.md
rather than left implicit.
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from .routes import DEFAULT, Routes, discover


def print_routes(packages: Sequence[str], table: Routes | None = None) -> int:
    """Import the packages, then print the table (path, source module, metadata fields)."""
    imported = discover(*packages)
    if imported:
        print(f"[routes] imported {len(imported)} module(s) from {', '.join(packages)}")
    rows = (table or DEFAULT).table()
    if not rows:
        print("[routes] nothing registered")
        return 0
    width = max(len(path) for path, _, _ in rows)
    print(f"{'path':<{width}}  {'source':<32} metadata")
    for path, source, meta in rows:
        fields = " ".join(f"{key}={value!r}" for key, value in sorted(meta.items()))
        print(f"{path:<{width}}  {source:<32} {fields}".rstrip())
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m reflux.cli", description="Reflux producer tools.")
    verbs = parser.add_subparsers(dest="verb", required=True)
    routes = verbs.add_parser("routes", help="print the route table")
    routes.add_argument(
        "packages",
        nargs="*",
        help="packages to import first (declaring routes is a side effect of import)",
    )
    args = parser.parse_args(argv)
    if args.verb == "routes":
        return print_routes(args.packages)
    return 2  # unreachable: the subparser is required


if __name__ == "__main__":
    sys.exit(main())