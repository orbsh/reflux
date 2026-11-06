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

__all__ = [
    "AUTH_SLOT",
    "AUTH_VERBS",
    "HOST_EVENTS",
    "LOGIN",
    "LOGOUT",
    "MAX_OPS_PER_FRAME",
    "RESERVED_PREFIX",
    "ROUTES_SLOT",
    "SIGNUP",
]

# How many operations one `draw` frame may carry. The producer refuses to build a frame over it
# (`wire.draw`) and the server refuses to put one on a socket (`ingest.check_frame`): the same rule
# read from the same number at both ends of one wire.
MAX_OPS_PER_FRAME = 1024

# The framework's namespace (`reflux:hello`, `reflux:nav`, and the two reserved ids the client
# runtime reads). An application registering on it is a startup error; the framework's own wire
# names come in through `Registry.builtin`.
RESERVED_PREFIX = "reflux:"

# The data slot a routed page is written into: the reader is the shell, the frame around every page.
# That frame is the app's own view when it declares one, otherwise the framework's default — a single
# full-screen `routes` — so either way the page lands in this slot and the framework only writes the
# name.
ROUTES_SLOT = "routes"

# Events the **host** raises: `connect` when the client's hello lands, `location` when it navigates
# (back/forward), `disconnect` when its device ends. An application registers them like any other
# name — `@app.on("connect")` — but they have no wire address, so an uplink frame
# addressed to one of them is refused: a client cannot fake its own connect, and cannot navigate
# without the browser having done it first.
HOST_EVENTS = ("connect", "location", "disconnect")

# The slot the login surface is drawn into. `auth` is the one application-facing name the platform
# reserves: a page declares it as a `placeholder` region, the framework (or the app's own `Auth.view`)
# writes the screen into it. The name is a slot, not a verb, because the surface is a place in the page.
AUTH_SLOT = "auth"

# The framework's own uplink verbs — authentication the venue owns, not the application's business.
# They carry the reserved prefix like `reflux:hello`, so an application registering one is a startup
# error and no app can shadow the door: `Registry.builtin` is the only way in. They exist only when
# the app declared `auth=`, which is the same rule as everything else here — no declaration, no door.
LOGIN = f"{RESERVED_PREFIX}login"
SIGNUP = f"{RESERVED_PREFIX}signup"
LOGOUT = f"{RESERVED_PREFIX}logout"
AUTH_VERBS = (LOGIN, SIGNUP, LOGOUT)
