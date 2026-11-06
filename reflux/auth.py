"""Authentication the framework owns: the verbs' rules, the token table, and the two seams.

The shape, and why it is the framework's rather than the application's:

- **A declaration says who may enter.** `@app.on(name, auth=True)` marks one landing point as
  served only to a device with a user bound to it. Absent is public — an app that never declares a
  gate has none.
- **The verdict is a door, not a policy engine.** The gate answers one question (*is there a user*)
  at the one place every frame passes (`App.handle`, before `dests.dispatch`), so a gated event from
  an anonymous connection never reaches a handler. Roles and permissions are the application's, or
  belong inside `verify`.
- **The credential is a token, and it outlives the socket.** A device is one connection; a refresh
  is a new device. Without a token "logged in" would mean "this socket", which is not what a browser
  does — so `login` mints one, the client keeps it, and `hello` hands it back on the next connect.
  That is the whole reason the token exists, and it is why it is the framework's rather than a
  hook's: the carrier (a marker down, a hello field up) is the framework's own contract with its
  runtime, and a hook could not reach either end.
- **Two seams stay a deployment's.** `verify(ctx, credentials) -> user_id | None` proves a
  credential (in-memory rows, an external IdP, LDAP — the framework never looks); `view(ctx, state)`
  draws the login surface (the framework ships one, an app may replace it). A third, optional seam
  (`store`) makes the token table survive a restart; without it the table is memory, and a restart
  logs everyone out — a deployment that wants more supplies three callables.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from .protocol import LOGIN, SIGNUP
from .sdk import builders as b
from .sdk.types import Accrete, JsType

__all__ = ["Auth", "TokenStore", "Tokens", "credentials_of", "default_view", "DEFAULT_IDLE_WINDOW"]

# A month. Long enough that an ordinary person is not asked again, short enough that an abandoned
# browser does not stay a key. The clock judges the TOKEN, not the socket: a connection that keeps
# being used never expires, and a device that goes quiet expires on its own.
DEFAULT_IDLE_WINDOW = 30 * 24 * 3600.0


class TokenStore(Protocol):
    """The optional persistence seam: three calls, no query language.

    `load()` is read once at startup and returns `{token: row}`; `put` / `drop` are called on every
    mint, refresh and revocation. A store that raises is the store's defect — the framework does not
    wrap it, because a token table that half-works is worse than one that says so loudly.
    """

    def load(self) -> dict[str, dict[str, Any]]: ...

    def put(self, token: str, row: dict[str, Any]) -> None: ...

    def drop(self, token: str) -> None: ...


class Tokens:
    """The token table: opaque strings in, a user id out, one clock over the whole set.

    A token is 32 random bytes in hex — long enough that guessing is not a strategy, and opaque so
    the table is the only authority (no claims to parse, nothing to forge). Rotation is the mint: a
    second login on the same table issues a NEW token, and the device's previous one is dropped by
    the caller that knows which one it was.
    """

    def __init__(self, idle_window: float = DEFAULT_IDLE_WINDOW, store: TokenStore | None = None):
        self.idle_window = float(idle_window)
        self._store = store
        self._rows: dict[str, dict[str, Any]] = store.load() if store is not None else {}

    def mint(self, user: str) -> str:
        """Issue a token for `user`. The caller drops whatever token the device held before."""
        token = secrets.token_hex(32)
        now = time.time()
        row = {"user": user, "issued": now, "seen": now}
        self._rows[token] = row
        if self._store is not None:
            self._store.put(token, row)
        return token

    def touch(self, token: Any) -> str | None:
        """The user this token names, refreshing its clock — or None (unknown, or idle too long).

        An expired token is dropped here rather than swept by a thread: the only moment it matters
        is the moment someone presents it, and one lookup is cheaper than a watchdog.
        """
        if not isinstance(token, str) or not token:
            return None
        row = self._rows.get(token)
        if row is None:
            return None
        now = time.time()
        if now - float(row["seen"]) > self.idle_window:
            self.drop(token)
            return None
        row["seen"] = now
        if self._store is not None:
            self._store.put(token, row)
        return str(row["user"])

    def drop(self, token: Any) -> None:
        """Forget a token. A token nobody holds any more is a token that cannot be presented."""
        if isinstance(token, str) and self._rows.pop(token, None) is not None:
            if self._store is not None:
                self._store.drop(token)

    def __len__(self) -> int:  # a table's size is a fact a test or /status may want
        return len(self._rows)


def credentials_of(frame: Any) -> dict[str, Any]:
    """The frame's payload as `{name: value}`, whichever way it was written.

    A page's form sends every field as `{"data": value, "payload": null}` (the renderer's own shape,
    and the null is its `Option`, not our lane); a program sends the flat dict. Unwrapping at the
    entry keeps that difference out of `verify` — the same rule the reference app's form follows.
    """
    data = frame.get("data") if isinstance(frame, dict) else None
    if not isinstance(data, dict):
        return {}
    flat: dict[str, Any] = {}
    for name, entry in data.items():
        if isinstance(entry, dict) and "data" in entry:
            flat[str(name)] = entry["data"]
        else:
            flat[str(name)] = entry
    return flat


def default_view(ctx: Any, state: str) -> Accrete:
    """The framework's own login screen: two fields, one button, one verb.

    `state` is `login` (the ordinary ask), `signup` (the same screen, the other verb) or `refused`
    (the same screen plus a line saying the attempt did not land). It is drawn into the `auth` slot
    by the framework, so an application that declares nothing still has a working surface.
    """
    verb = SIGNUP if state == "signup" else LOGIN
    lines: list[Accrete] = [b.text("登录", variant="heading-1")]
    if state == "refused":
        lines.append(b.text("用户名或密码不对", variant="muted"))
    return b.case(
        *lines,
        b.form(
            b.input(field="username", id="auth-user"),
            b.input(field="password", kind=JsType.password, id="auth-pass"),
            b.button("继续"),
            dest=ctx.slot(verb),
            id="auth-form",
        ),
    )

@dataclass
class Auth:
    """What a deployment supplies, and the defaults it may keep.

    `verify` is the one callable every deployment must write:
    `(ctx, credentials, mode) -> user id | None`, where `mode` is `login` or `signup` — one seam, and
    the mode is what lets a deployment create an account on the same call it checks one. It receives
    the frame's payload already unwrapped (`credentials_of`), so a page's form and a program's flat
    dict arrive the same shape. Returning None is an ordinary refusal, not an error.
    `view` left None means the framework's own screen (`default_view`): a deployment replaces the
    surface, never the mechanics around it.
    """

    verify: Callable[[Any, dict[str, Any], str], str | None]
    view: Callable[[Any, str], Accrete] | None = None
    store: TokenStore | None = None
    idle_window: float = DEFAULT_IDLE_WINDOW

    def screen(self, ctx: Any, state: str) -> Accrete:
        """The login surface for this moment: the app's view when it declared one."""
        view = self.view or default_view
        return view(ctx, state)



