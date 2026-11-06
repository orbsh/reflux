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
from reflux.channel import Channel
from reflux.protocol import AUTH_SLOT, LOGIN, LOGOUT, SIGNUP


class Scripted(Channel):
    """A connection with a script: yields its frames, then ends (so `handle` returns)."""

    def __init__(self, *frames: dict) -> None:
        self.script = [json.dumps(frame) for frame in frames]
        self.last_seen = time.monotonic()
        self.frames: list[list[dict]] = []

    def __iter__(self):
        yield from self.script

    def send(self, text: str) -> None:
        self.frames.append(json.loads(text))

    def ping(self, payload: bytes = b"") -> None:
        pass

    def close(self, code: int = 1000) -> None:
        pass

    def abort(self) -> None:
        pass


def settle(channel: Scripted, minimum: int = 1, timeout: float = 2.0) -> None:
    """Wait for the writer thread to drain what the handlers queued.

    Frames are queued per device and written by that device's own thread, so `handle` returning does
    not mean the client has them yet. Polling is the honest wait; a sleep would only be luckier.
    """
    deadline = time.monotonic() + timeout
    while len(channel.frames) < minimum and time.monotonic() < deadline:
        time.sleep(0.005)


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
        app = App(auth=Auth(verify=verify))
        called: list[dict] = []

        def handler(ctx, frame):
            called.append(frame)

        app.on("vault.other", handler, auth=True)
        channel = Scripted({"dest": "vault.other", "data": {"x": 1}})
        app.handle(channel)
        settle(channel)

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
        app = App(auth=Auth(verify=verify))
        seen: list[dict] = []
        app.on("vault.open", lambda ctx, frame: seen.append(ctx.data), auth=True)
        channel = Scripted(
            {"dest": LOGIN, "data": {"username": {"data": "ada", "payload": None},
                                     "password": {"data": "pw", "payload": None}}},
            {"dest": "vault.open", "data": {}},
        )
        app.handle(channel)
        settle(channel, minimum=2)

        self.assertEqual(len(seen), 1, "after a login the gated event reaches its handler")
        self.assertEqual(seen[0]["user"], "user-ada")
        self.assertEqual(app.stats["refused"], 0)
        # The token went out as a marker: that is the only way the runtime can be told.
        drawn = ops_on(channel, AUTH_SLOT)
        self.assertTrue(any("reflux:token" in ids(op.get("data")) for op in drawn))

    def test_a_wrong_password_draws_the_surface_and_binds_nothing(self) -> None:
        app = App(auth=Auth(verify=verify))
        app.on("vault.open", lambda ctx, frame: None, auth=True)
        channel = Scripted(
            {"dest": LOGIN, "data": {"username": "ada", "password": "nope"}},
            {"dest": "vault.open", "data": {}},
        )
        app.handle(channel)
        settle(channel)

        self.assertEqual(app.stats["refused"], 1, "the gated event is still refused")
        surface = ops_on(channel, AUTH_SLOT)
        self.assertTrue(surface, "a refusal keeps the surface up")

    def test_without_a_declaration_there_is_no_gate(self) -> None:
        app = App()  # no auth= at all
        seen: list[dict] = []
        app.on("vault.open", lambda ctx, frame: seen.append(frame))
        channel = Scripted({"dest": "vault.open", "data": {}})
        app.handle(channel)
        settle(channel)
        self.assertEqual(len(seen), 1, "no gate declared, no gate enforced")

    def test_without_auth_the_verbs_do_not_exist(self) -> None:
        app = App()
        self.assertNotIn(LOGIN, app.dests.names())
        self.assertNotIn(SIGNUP, app.dests.names())
        self.assertNotIn(LOGOUT, app.dests.names())
        channel = Scripted({"dest": LOGIN, "data": {}})
        app.handle(channel)
        settle(channel)
        self.assertEqual(app.dests.refused, 1, "no door: the name is simply not registered")
        self.assertTrue(any("unregistered event" in line for line in app.dests.log))


class TestTheToken(unittest.TestCase):
    def test_a_token_carries_the_same_user_onto_a_new_connection(self) -> None:
        app = App(auth=Auth(verify=verify))
        who: list = []

        def on_connect(ctx, frame):
            who.append(ctx.data.get("user"))

        app.on("connect", on_connect)
        first = Scripted({"dest": LOGIN, "data": {"username": "ada", "password": "pw"}})
        app.handle(first)
        settle(first)
        self.assertEqual(len(app.tokens), 1)
        token = next(iter(app.tokens._rows))

        second = Scripted({"dest": "reflux:hello", "data": {"path": "/", "token": token}})
        app.handle(second)
        settle(second)
        self.assertEqual(who, ["user-ada"], "hello adopts the token before anything is drawn")

    def test_a_revoked_token_leaves_the_next_connection_anonymous(self) -> None:
        app = App(auth=Auth(verify=verify))
        who: list = []
        app.on("connect", lambda ctx, frame: who.append(ctx.data.get("user")))

        first = Scripted(
            {"dest": LOGIN, "data": {"username": "ada", "password": "pw"}},
            {"dest": LOGOUT, "data": {}},
        )
        app.handle(first)
        settle(first)
        self.assertEqual(len(app.tokens), 0, "logout drops the row")

        stale = "0" * 64
        second = Scripted({"dest": "reflux:hello", "data": {"path": "/", "token": stale}})
        app.handle(second)
        settle(second)
        self.assertEqual(who, [None], "an unknown token is simply a visitor")

    def test_the_idle_window_expires_a_token_on_its_lookup(self) -> None:
        table = Tokens(idle_window=0.01)
        token = table.mint("u1")
        self.assertEqual(table.touch(token), "u1")
        time.sleep(0.02)
        self.assertIsNone(table.touch(token), "a token gone quiet past the window is not a user")
        self.assertEqual(len(table), 0, "and looking it up is what drops it")

    def test_a_login_on_the_same_connection_rotates_its_token(self) -> None:
        app = App(auth=Auth(verify=verify))
        channel = Scripted(
            {"dest": LOGIN, "data": {"username": "ada", "password": "pw"}},
            {"dest": LOGIN, "data": {"username": "ada", "password": "pw"}},
        )
        app.handle(channel)
        settle(channel)
        self.assertEqual(len(app.tokens), 1, "the second login replaced the first token")


class TestTheLog(unittest.TestCase):
    def test_the_log_keeps_no_password_and_no_token(self) -> None:
        app = App(auth=Auth(verify=lambda ctx, creds, mode: "user-ada"))
        channel = Scripted(
            {"dest": SIGNUP, "data": {"username": "ada", "password": "hunter2"}},
        )
        app.handle(channel)
        settle(channel)
        lines = json.dumps(app.log)
        self.assertNotIn("hunter2", lines)
        token = next(iter(app.tokens._rows))
        second = Scripted({"dest": "reflux:hello", "data": {"path": "/", "token": token}})
        app.handle(second)
        settle(second)
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