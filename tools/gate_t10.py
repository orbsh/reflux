#!/usr/bin/env python3
"""T10's gate: the same specification, a second language, the same bytes.

    python3 tools/gate_t10.py

The claim under test is narrow and checkable: the Rust SDK (`sdks/rust/`) is generated from the same
schema and profile as the Python SDK, so a frame it builds is **byte for byte** the frame Python
builds. Not "structurally equivalent", not "parses to the same object" — the same bytes, in the same
key order, with the same values.

Five turns, the reference app's own shapes:

  echo · add row · remove row · form submit · page turn (structure + two seeded rows)

Those are the same five `tools/measure.py` weighs, so the byte counts in `docs/PERF.md` double as the
expected sizes here.

The comparison is on **compact** JSON (no spaces around `:` and `,`). Whitespace is not part of the
contract — `App.send` writes Python's `json.dumps` default spacing and the renderer parses JSON — so
both sides are normalised to compact form before comparing. Key order and values are the contract.

Requires `cargo`; the first run needs crates.io reachable (serde_json, with `preserve_order`).
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CRATE = ROOT / "sdks" / "rust"
SESSION = "measure1"


def compact(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def python_turns() -> list[tuple[str, dict]]:
    """The reference app's five turns, built with the Python SDK."""
    sys.path.insert(0, str(ROOT))
    import reflux.demo_app as demo
    from reflux import wire
    from reflux.sdk import builders as b

    return [
        ("echo", wire.draw(wire.set(demo.ECHO, b.text("hello")))),
        (
            "add row",
            wire.draw(wire.append(demo.ROWS, demo.row_node({"id": "row-4", "text": "第 4 行"}))),
        ),
        ("remove row", wire.draw(wire.remove(demo.ROWS, "row-1"))),
        (
            "form submit",
            wire.draw(
wire.set(demo.SUBMITTED, b.text('已提交 {"pass": "secret", "user": "ada"}'))),
        ),
        (
            "page turn",
            wire.draw(
wire.create(demo.demo.home()),
                *[wire.append(demo.ROWS, demo.row_node(row)) for row in demo.demo.rows]),
        ),
        # The second page, through the same sugar: it proves `markers.page` on both sides and
        # covers a page whose node mix is not the reference page's.
        ("about page", wire.draw(wire.create(demo.demo.about()))),
        # The `local` 落点 and its `path` rider: a client-side slot, addressed one level in.
        (
            "local binding",
            wire.draw(
wire.create(b.case(b.text(local="chan", path="/data", id="local-echo"), id="root"))),
        ),
    ]


def rust_frames() -> list[bytes]:
    """`cargo run --bin frames` — the same five turns, built by the Rust SDK."""
    out = subprocess.run(
        ["cargo", "run", "--quiet", "--bin", "frames"],
        cwd=CRATE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if out.returncode != 0:
        tail = out.stderr.decode(errors="replace").strip().splitlines()[-12:]
        raise SystemExit("`cargo run --bin frames` failed:\n  " + "\n  ".join(tail))
    return [line.encode("utf-8") for line in out.stdout.decode("utf-8").splitlines() if line.strip()]


def first_difference(left: bytes, right: bytes) -> str:
    """Where two JSON texts part ways, with a little context on both sides."""
    offset = next((i for i, (a, b) in enumerate(zip(left, right)) if a != b), min(len(left), len(right)))
    start = max(0, offset - 40)
    return (
        f"first difference at byte {offset} (python {len(left)} B, rust {len(right)} B)\n"
        f"    python: …{left[start:offset + 40].decode('utf-8', 'replace')}…\n"
        f"    rust  : …{right[start:offset + 40].decode('utf-8', 'replace')}…"
    )


def main() -> int:
    checks: list[tuple[str, bool, str]] = []
    expected = python_turns()
    actual = rust_frames()

    if len(actual) != len(expected):
        print(f"FAIL: rust printed {len(actual)} frames, python built {len(expected)}")
        return 1

    for (label, frame), got in zip(expected, actual):
        want = compact(frame)
        ok = want == got
        checks.append((label, ok, f"{len(want)} B" if ok else first_difference(want, got)))

    # The frames are distinct turns, not the same frame N times: a green run that compared a
    # constant against itself would prove nothing.
    distinct = len({bytes(got) for got in actual}) == len(actual)
    checks.append((f"{len(actual)} distinct frames", distinct, f"{len(set(actual))} unique of {len(actual)}"))

    for index, (label, ok, detail) in enumerate(checks, 1):
        print(f"[{index}/{len(checks)}] {'PASS' if ok else 'FAIL'}  {label}: {detail}")
    passed = sum(1 for _, ok, _ in checks if ok)
    print(f"\nT10 GATE {'PASSED' if passed == len(checks) else 'FAILED'} — {passed}/{len(checks)} checks")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())