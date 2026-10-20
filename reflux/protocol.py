"""The protocol's own numbers — the rules the wire states about itself.

Two constants that are **not** vocabulary: how many operations one frame may carry, and the prefix
the framework reserves for its own event names (`reflux:hello` / `reflux:nav`).

They used to live in `tables_generated.py` because a hand-written spec happened to describe the
whole wire. The vocabulary is no longer ours (it is accrete's types, reached through
`reflux/sdk`), so these two are reflux's own statements about its own protocol: an operation cap
and a namespace. They do not follow a spec out of the repo, and a spec that generates two
integers would be a generator for two integers.

Hand-written, and read from one place each: `app` / `events` take the prefix, `ingest` and `wire`
take the cap. Nothing here is generated, so nothing here drifts.
"""

from __future__ import annotations

__all__ = ["MAX_OPS_PER_FRAME", "RESERVED_PREFIX"]

# How many operations one `draw` frame may carry. The producer refuses to build a frame over it
# (`wire.draw`) and the server refuses to put one on a socket (`ingest.check_frame`): the same rule
# read from the same number at both ends of one wire.
MAX_OPS_PER_FRAME = 1024

# The framework's namespace (`reflux:hello`, `reflux:nav`, and the two reserved ids the client
# runtime reads). An application registering on it is a startup error; the framework's own names
# come in through `Registry.builtin`.
RESERVED_PREFIX = "reflux:"