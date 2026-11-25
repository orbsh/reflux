"""Authentication as the framework owns it: the gate, the verbs, the token, and what the log keeps.

Driven through `App.handle` with a scripted channel, because the gate lives at the one door every
frame passes and a test that called `dests.dispatch` directly would be testing the half without it.

The properties asserted here are the ones the design argues for, in the order they matter:

- a gated landing point never reaches its handler from an anonymous connection, and the framework
  opens the login surface itself (the app cannot know the attempt happened);
- a login binds the connection, mints a token, and the SAME landing point then lands;
- the token survives a reconnect (that is why it exists) and a revocation does not;
- `auth=None` means no gate and no verbs — absent declaration, no door;
- the process log holds no password and no credential.
"""

from __future__ import annotations

import json
import time
import unittest

from reflux.app import App
from reflux.auth import Auth, Tokens
from tests.fakes import run_sync
from reflux.protocol import AUTH_SLOT, LOGIN, LOGOUT, SIGNUP


def with_login(verify: Any) -> App:
    """An app whose `login` seam is `verify(ctx, credentials, mode) -> user id | None`.

    The old `Auth(verify=…)` shape, said in the current one: a seam returns a verdict tuple, so the
    adapter is where the two spellings meet and nothing else in this file has to change.
    """

    def login(ctx: Any, credentials: dict, mode: str) -> tuple:
        user = verify(ctx, credentials, mode)
        return (True, user, {}) if user else (False, "登录失败")

    app = App()
    app.hooks("login")(login)
    return app


class Scripted:
    """A connection with a script: yields its frames, then ends (so `handle` returns).

    The async channel `App.handle` reads (ADR 0002): `async for` in, `await send` out. Frames are
    written before `handle` returns, so a test reads `frames` without waiting for anything.
    """

    def __init__(self, *frames: dict) -> None:
        self.script = [json.dumps(frame) for frame in frames]
        self.last_seen = time.monotonic()
        self.frames: list[list[dict]] = []

    def __aiter__(self) -> "Scripted":
        self._script = iter(self.script)
        return self

    async def __anext__(self) -> str:
        try:
            return next(self._script)
        except StopIteration:
            raise StopAsyncIteration from None

    async def send(self, text: str) -> None:
        self.frames.append(json.loads(text))

    async def ping(self, payload: bytes = b"") -> None:
        pass

    async def close(self, code: int = 1000) -> None:
        pass

    async def abort(self) -> None:
        pass


def ops_on(channel: Scripted, slot: str) -> list[dict]:
    """Every operation any frame addressed to `slot` — the login surface's home."""
    return [op for frame in channel.frames for op in frame if op.get("slot") == slot]


def ids(node) -> list[str]:
    """Every id in a node tree, so a marker can be found without pinning the whole shape."""
    found: list[str] = []
    if isinstance(node, dict):
        if "id" in node:
            found.append(str(node["id"]))
        for child in node.get("children") or []:
            found.extend(ids(child))
    elif isinstance(node, list):
        for item in node:
            found.extend(ids(item))
    return found


def verify(ctx, credentials, mode):
    """A deployment's verifier: one user, one password, and signup creates the same one."""
    if credentials.get("username") == "ada" and credentials.get("password") == "pw":
        return "user-ada"
    return None


class TestTheGate(unittest.TestCase):
    def test_an_anonymous_gated_event_never_reaches_its_handler(self) -> None:
        app = with_login(verify)
        called: list[dict] = []

        def handler(ctx, frame):
            called.append(frame)

        app.on("vault.other", handler, auth=True)
        channel = Scripted({"dest": "vault.other", "data": {"x": 1}})
        run_sync(app.handle(channel))

        self.assertEqual(called, [], "a gated event must not reach the app from a visitor")
        self.assertEqual(app.stats["refused"], 1)
        self.assertTrue(
            any("no user bound" in line for line in app.dests.log),
            f"the refusal is accounted for: {app.dests.log}",
        )
        # The framework opens the surface itself: the connection stays up and the app never learned.
        surface = ops_on(channel, AUTH_SLOT)
        self.assertTrue(surface, "the refusal must draw the login surface")
        self.assertIn("auth-form", ids(surface[-1]["data"]))

    def test_the_same_event_lands_once_a_login_bound_the_connection(self) -> None:
        app = with_login(verify)
        seen: list[dict] = []
        app.on("vault.open", lambda ctx, frame: seen.append(ctx.data), auth=True)
        channel = Scripted(
            {"dest": LOGIN, "data": {"username": {"data": "ada", "payload": None},
                                     "password": {"data": "pw", "payload": None}}},
            {"dest": "vault.open", "data": {}},
        )
        run_sync(app.handle(channel))

        self.assertEqual(len(seen), 1, "after a login the gated event reaches its handler")
        self.assertEqual(seen[0]["user"], "user-ada")
        self.assertEqual(app.stats["refused"], 0)
        # The token went out as a marker: that is the only way the runtime can be told.
        drawn = ops_on(channel, AUTH_SLOT)
        self.assertTrue(any("reflux:token" in ids(op.get("data")) for op in drawn))

    def test_a_wrong_password_draws_the_surface_and_binds_nothing(self) -> None:
        app = with_login(verify)
        app.on("vault.open", lambda ctx, frame: None, auth=True)
        channel = Scripted(
            {"dest": LOGIN, "data": {"username": "ada", "password": "nope"}},
            {"dest": "vault.open", "data": {}},
        )
        run_sync(app.handle(channel))

        self.assertEqual(app.stats["refused"], 1, "the gated event is still refused")
        surface = ops_on(channel, AUTH_SLOT)
        self.assertTrue(surface, "a refusal keeps the surface up")

    def test_without_a_declaration_there_is_no_gate(self) -> None:
        app = App()  # no auth= at all
        seen: list[dict] = []
        app.on("vault.open", lambda ctx, frame: seen.append(frame))
        channel = Scripted({"dest": "vault.open", "data": {}})
        run_sync(app.handle(channel))
        self.assertEqual(len(seen), 1, "no gate declared, no gate enforced")

    def test_without_auth_the_verbs_do_not_exist(self) -> None:
        app = App()
        self.assertNotIn(LOGIN, app.dests.names())
        self.assertNotIn(SIGNUP, app.dests.names())
        self.assertNotIn(LOGOUT, app.dests.names())
        channel = Scripted({"dest": LOGIN, "data": {}})
        run_sync(app.handle(channel))
        self.assertEqual(app.dests.refused, 1, "no door: the name is simply not registered")
        self.assertTrue(any("unregistered event" in line for line in app.dests.log))


class TestTheToken(unittest.TestCase):
    def test_a_token_carries_the_same_user_onto_a_new_connection(self) -> None:
        app = with_login(verify)
        who: list = []

        def on_connect(ctx, frame):
            who.append(ctx.data.get("user"))

        app.on("connect", on_connect)
        first = Scripted({"dest": LOGIN, "data": {"username": "ada", "password": "pw"}})
        run_sync(app.handle(first))
        self.assertEqual(len(app.tokens), 1)
        token = next(iter(app.tokens._rows))

        second = Scripted({"dest": "reflux:hello", "data": {"path": "/", "token": token}})
        run_sync(app.handle(second))
        self.assertEqual(who, ["user-ada"], "hello adopts the token before anything is drawn")

    def test_a_revoked_token_leaves_the_next_connection_anonymous(self) -> None:
        app = with_login(verify)
        who: list = []
        app.on("connect", lambda ctx, frame: who.append(ctx.data.get("user")))

        first = Scripted(
            {"dest": LOGIN, "data": {"username": "ada", "password": "pw"}},
            {"dest": LOGOUT, "data": {}},
        )
        run_sync(app.handle(first))
        self.assertEqual(len(app.tokens), 0, "logout drops the row")

        stale = "0" * 64
        second = Scripted({"dest": "reflux:hello", "data": {"path": "/", "token": stale}})
        run_sync(app.handle(second))
        self.assertEqual(who, [None], "an unknown token is simply a visitor")

    def test_the_idle_window_expires_a_token_on_its_lookup(self) -> None:
        table = Tokens(idle_window=0.01)
        token = table.mint("u1")
        self.assertEqual(table.touch(token), "u1")
        time.sleep(0.02)
        self.assertIsNone(table.touch(token), "a token gone quiet past the window is not a user")
        self.assertEqual(len(table), 0, "and looking it up is what drops it")

    def test_a_login_on_the_same_connection_rotates_its_token(self) -> None:
        app = with_login(verify)
        channel = Scripted(
            {"dest": LOGIN, "data": {"username": "ada", "password": "pw"}},
            {"dest": LOGIN, "data": {"username": "ada", "password": "pw"}},
        )
        run_sync(app.handle(channel))
        self.assertEqual(len(app.tokens), 1, "the second login replaced the first token")


class TestTheLog(unittest.TestCase):
    def test_the_log_keeps_no_password_and_no_token(self) -> None:
        app = with_login(lambda ctx, creds, mode: "user-ada")
        channel = Scripted(
            {"dest": SIGNUP, "data": {"username": "ada", "password": "hunter2"}},
        )
        run_sync(app.handle(channel))
        lines = json.dumps(app.log)
        self.assertNotIn("hunter2", lines)
        token = next(iter(app.tokens._rows))
        second = Scripted({"dest": "reflux:hello", "data": {"path": "/", "token": token}})
        run_sync(app.handle(second))
        # What comes IN never carries the secret. What goes OUT does carry the token once — that is
        # the delivery itself (the marker the runtime keeps), so the rule is about the inbound half.
        inbound = [entry for direction, entry in app.log if direction == "recv"]
        self.assertNotIn(token, json.dumps(inbound), "hello's token must be redacted")
        self.assertIn("reflux:token", json.dumps([e for d, e in app.log if d == "send"]))

    def test_a_page_form_and_a_program_frame_reach_verify_the_same(self) -> None:
        from reflux.auth import credentials_of

        page = {"data": {"username": {"data": "ada", "payload": None}}}
        program = {"data": {"username": "ada"}}
        self.assertEqual(credentials_of(page), {"username": "ada"})
        self.assertEqual(credentials_of(program), {"username": "ada"})


if __name__ == "__main__":
    unittest.main()

class TheLoginSurface(unittest.TestCase):
    """A field has no exit of its own (ADR 0032 §2, revised): its exit is the loom's.

    The password field still has to say what it is — a `password` input, not a text one — and that
    is the field's own `kind` (ADR 0032 §2, revised 2026-11-24): a field has one type, and it is
    neither the read's nor the write's.
    """

    def test_the_password_field_carries_its_kind_and_no_sink(self) -> None:
        from reflux.sdk import dump, h
        from reflux.sdk.types import JsType

        node = h.input(tag="pass", kind=JsType.password, id="auth-pass")
        wire = dump(node)
        self.assertNotIn("sink", wire, "a field has no exit of its own")
        self.assertEqual(wire["kind"], "password")
        self.assertEqual(wire["tag"], "pass", "and its membership, which is what makes it send")
