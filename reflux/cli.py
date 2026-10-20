"""The producer's command line: print what an imported app registered.

    python3 -m reflux.cli routes myapp
    python3 -m reflux.cli events myapp.main:make_app

`routes` imports the packages you name — their decorators register as a side effect of import —
and prints the table: path, source module, metadata fields. Nothing is derived from a file name, so
the source column is where the route was written, not where the framework guessed.

`events` prints the event-name registry, and that needs an **app**, not a package: the registry hangs
off one `App` instance, and registering a handler has no import side effect to wait for. So it takes a
**target** — `module:attr`, where `attr` is called with no arguments when it is callable and taken as
it is when it is already an `App`:

    python3 -m reflux.cli events reflux.demo_app:make_app
    python3 -m reflux.cli events myapp.main:app

Two rules this verb follows, both about not inventing conventions:

- **No guessing.** It does not look for `make_app`, then `app`, then `create_app`. A convention that
  is guessed is a convention nobody can find; the error says the shape and stops.
- **What exists, not what happened.** The table is the registry (name, source, kind). The runtime
  counters (`calls`, `refused`, `log`) describe a running app and would read as data in a fresh
  process.

There is no Rust counterpart on purpose: a registry belongs to a **host**, not to the producer's
vocabulary, so this is a Python-side developer tool rather than something the second SDK must mirror.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from typing import Sequence

from .app import App
from .routes import DEFAULT, Routes, discover


def print_routes(packages: Sequence[str], table: Routes | None = None) -> int:
    """Import the packages, then print the table (path, source module, metadata fields)."""
    imported = discover(*packages)
    if imported:
        print(f"[routes] imported {len(imported)} module(s) from {', '.join(packages)}")
    rows = (table if table is not None else DEFAULT).table()
    if not rows:
        print("[routes] nothing registered")
        return 0
    width = max(len(path) for path, _, _ in rows)
    print(f"{'path':<{width}}  {'source':<32} metadata")
    for path, source, meta in rows:
        fields = " ".join(f"{key}={value!r}" for key, value in sorted(meta.items()))
        print(f"{path:<{width}}  {source:<32} {fields}".rstrip())
    return 0


def resolve_app(target: str) -> App:
    """`module:attr` → the `App` it names.

    `attr` is called when it is callable (a factory) and taken as it is when it already is an `App`;
    anything else is an error that says what it got. See the module docstring for why nothing here is
    guessed.
    """
    module_name, sep, attr = target.partition(":")
    if not sep or not module_name or not attr:
        raise SystemExit(
            f"[events] expected a target of the form `module:attr` "
            f"(e.g. reflux.demo_app:make_app), got {target!r}"
        )
    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        raise SystemExit(f"[events] cannot import {module_name!r}: {e}") from e
    if not hasattr(module, attr):
        raise SystemExit(f"[events] {module_name} has no attribute {attr!r}")
    value = getattr(module, attr)
    app = value() if callable(value) and not isinstance(value, App) else value
    if not isinstance(app, App):
        raise SystemExit(
            f"[events] {target} gave {type(app).__name__}; expected an App or a callable returning one"
        )
    return app


def print_events(target: str) -> int:
    """Print one app's event registry: name, kind, source."""
    app = resolve_app(target)
    rows = app.events.table()
    if not rows:
        print(f"[events] {target} registered no event names")
        return 0
    width = max(len(name) for name, _, _ in rows)
    print(f"{'event':<{width}}  {'kind':<8} source")
    for name, source, kind in rows:
        print(f"{name:<{width}}  {kind:<8} {source}")
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
    events = verbs.add_parser("events", help="print an app's event-name registry")
    events.add_argument(
        "target",
        help="`module:attr` — a factory returning an App, or an App itself (e.g. reflux.demo_app:make_app)",
    )
    args = parser.parse_args(argv)
    if args.verb == "routes":
        return print_routes(args.packages)
    if args.verb == "events":
        return print_events(args.target)
    return 2  # unreachable: the subparser is required


if __name__ == "__main__":
    sys.exit(main())