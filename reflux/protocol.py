"""The protocol's own numbers — the rules the wire states about itself.

Not vocabulary, all of it: the operation cap, the namespace the framework reserves for its own
names, the slot a routed page is written into, and the names of the events the host raises (they
are not wire addresses — the client never sends them).

They used to live in `tables_generated.py` because a hand-written spec happened to describe the
whole wire. The vocabulary is no longer ours (it is accrete's types, reached through
`reflux/sdk`), so these are reflux's own statements about its own protocol: an operation cap, a
namespace, one slot name and a set of host event names. They do not follow a spec out of the repo,
and a spec that generates four constants would be a generator for four constants.

Hand-written, and read from one place each: `app` / `dests` take the prefix and the host events,
`ingest` and `wire` take the cap, `app` writes the routes slot.
"""

from __future__ import annotations

__all__ = ["HOST_EVENTS", "MAX_OPS_PER_FRAME", "RESERVED_PREFIX", "ROUTES_SLOT"]

# How many operations one `draw` frame may carry. The producer refuses to build a frame over it
# (`wire.draw`) and the server refuses to put one on a socket (`ingest.check_frame`): the same rule
# read from the same number at both ends of one wire.
MAX_OPS_PER_FRAME = 1024

# The framework's namespace (`reflux:hello`, `reflux:nav`, and the two reserved ids the client
# runtime reads). An application registering on it is a startup error; the framework's own wire
# names come in through `Registry.builtin`.
RESERVED_PREFIX = "reflux:"

# The data slot a routed page is written into when the app supplies a shell (the frame around its
# pages). The shell is the app's own view, so it declares the reader; the framework only writes the
# name. Without a shell there is no routes slot and the page replaces the layout root.
ROUTES_SLOT = "routes"

# Events the **host** raises: `connect` when the client's hello lands, `location` when it navigates
# (back/forward), `disconnect` when its device ends. An application registers them like any other
# name — `@app.dests.register("connect")` — but they have no wire address, so an uplink frame
# addressed to one of them is refused: a client cannot fake its own connect, and cannot navigate
# without the browser having done it first.
HOST_EVENTS = ("connect", "location", "disconnect")
