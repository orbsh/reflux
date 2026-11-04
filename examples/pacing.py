"""The pacing every walkthrough shares: a numbered step, an Enter, and reading a quiet wire.

Borrowed from fluxen's `examples/walkthrough.py` — the skeleton (a numbered step, one Enter, and the
frames printed as they land) is the same wherever the subject changes, so the two pieces that carry
no subject live here and each example spends its lines on what it is demonstrating.

`--auto` runs the same steps without waiting: a gate, a CI run, or a reader in a hurry.
"""

from __future__ import annotations

import time

from tools.wire_probe import Socket

__all__ = ["Step", "read_for"]


def read_for(ws: Socket, seconds: float) -> list[dict]:
    """Every frame that lands within `seconds` (reading stops early once the wire goes quiet)."""
    frames: list[dict] = []
    deadline = time.monotonic() + seconds
    while True:
        left = deadline - time.monotonic()
        if left <= 0:
            return frames
        try:
            frame = ws.recv(timeout=left)
        except TimeoutError:
            return frames
        if frame is None:
            return frames
        frames.append(frame)


class Step:
    """The Enter gate: numbered, auto-run or hand-paced. It is the pacing, not the subject."""

    def __init__(self, auto: bool, pause: float = 0.4) -> None:
        self.auto = auto
        self.pause = pause
        self.n = 0

    def wait(self, title: str) -> None:
        self.n += 1
        print(f"\n[{self.n}] {title}")
        if self.auto:
            time.sleep(self.pause)
        else:
            try:
                input("    ↵ 回车继续 … ")
            except EOFError:
                print("    (stdin closed — switching to --auto)")
                self.auto = True