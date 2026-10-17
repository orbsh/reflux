#!/usr/bin/env python3
"""Re-export accrete's schema from fluxen and diff it against `schema/accrete.schema.json`.

    python3 tools/sync_schema.py            report drift (exit 1 when it differs)
    python3 tools/sync_schema.py --write    accept fluxen's current export

Fluxen's tree is `$REFLUX_FLUXEN` or `~/world/fluxen`. This is the only place in the repo that needs
cargo or another checkout; the generator and the gates read the snapshot instead.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "schema" / "accrete.schema.json"
EXPORT = ["cargo", "run", "-q", "-p", "stage", "--", "schema"]


def fluxen_dir() -> pathlib.Path:
    p = pathlib.Path(os.environ.get("REFLUX_FLUXEN") or pathlib.Path.home() / "world" / "fluxen")
    if not p.is_dir():
        raise SystemExit(f"fluxen not found at {p} — set REFLUX_FLUXEN to its checkout")
    return p


def export(fluxen: pathlib.Path) -> bytes:
    try:
        out = subprocess.run(EXPORT, cwd=fluxen, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError as e:
        raise SystemExit(f"cannot run {EXPORT[0]}: {e}") from e
    if out.returncode != 0:
        tail = out.stderr.decode(errors="replace").strip().splitlines()[-5:]
        raise SystemExit("the export failed:\n  " + "\n  ".join(tail))
    return out.stdout


def consts(blob: bytes) -> list[str]:
    doc = json.loads(blob)
    return [arm["properties"]["type"]["const"] for arm in doc["oneOf"]]


def defs(blob: bytes) -> dict:
    return json.loads(blob)["$defs"]


def describe(old: bytes, new: bytes) -> list[str]:
    """What changed, in the vocabulary that matters: the type list and each type's fields."""
    lines: list[str] = []
    o, n = consts(old), consts(new)
    if o != n:
        gone = [c for c in o if c not in n]
        born = [c for c in n if c not in o]
        if gone:
            lines.append(f"  types gone:    {', '.join(gone)}")
        if born:
            lines.append(f"  types added:   {', '.join(born)}")
        if set(o) == set(n):
            lines.append("  type order changed (the schema's arm order)")
    od, nd = defs(old), defs(new)
    for name in sorted(set(od) | set(nd), key=lambda x: (x not in od, x)):
        if name not in nd:
            lines.append(f"  $defs gone:    {name}")
        elif name not in od:
            lines.append(f"  $defs added:   {name}")
        else:
            op = set((od[name].get("properties") or {}))
            np_ = set((nd[name].get("properties") or {}))
            if op != np_:
                lines.append(
                    f"  {name}: fields "
                    + ", ".join(
                        (f"-{f}" if f in op - np_ else f"+{f}")
                        for f in sorted(op ^ np_)
                    )
                )
            elif od[name] != nd[name]:
                lines.append(f"  {name}: same fields, different detail")
    return lines or ["  (only whitespace-level differences)"]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Re-export accrete's schema and diff it against the snapshot.")
    ap.add_argument("--write", action="store_true", help="overwrite the snapshot with fluxen's export")
    args = ap.parse_args(argv[1:])

    fresh = export(fluxen_dir())
    if SNAPSHOT.exists() and SNAPSHOT.read_bytes() == fresh:
        print(f"in sync — sha256 {hashlib.sha256(fresh).hexdigest()} ({len(fresh)} B)")
        return 0

    print(f"drift: {SNAPSHOT.name} is not fluxen's current export")
    if SNAPSHOT.exists():
        print(f"  snapshot {hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest()} ({SNAPSHOT.stat().st_size} B)")
        print(f"  fluxen   {hashlib.sha256(fresh).hexdigest()} ({len(fresh)} B)")
        for line in describe(SNAPSHOT.read_bytes(), fresh):
            print(line)
    else:
        print("  (no snapshot yet)")
    if not args.write:
        print("\nre-run with --write to accept, then `python3 tools/gen_sdk.py` and read the SDK diff.")
        return 1
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_bytes(fresh)
    print(f"\nwrote {SNAPSHOT.relative_to(ROOT)} — now regenerate: python3 tools/gen_sdk.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))