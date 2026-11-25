"""The `app.hooks` seams: what a login answers, and what the framework does with the answer.

The contract is a shape, so the tests are about shapes: `(True, user, info)` binds, `(False, reason)`
refuses with words on the surface, anything else is the app's mistake and says so in the log. The
gate and the surface are seams of their own (`login.request`, `page(auth=True)`), which is why they
have tests here rather than being folded into the login cases.
"""

from __future__ import annotations

import unittest

from reflux.app import App
from reflux.protocol import AUTH_SLOT, LOGIN
from reflux.sdk import builders as h
from tests.fakes import run_sync
from tests.test_auth import Scripted, ids, ops_on

GOOD = {"username": "ada", "password": "pw"}


def app_with(login, **hooks) -> App:
    """An app whose `login` seam is `login`, plus any other seam named in `hooks`."""
    app = App()
    app.hooks("login")(login)
    for name, handler in hooks.items():
        app.hooks(name)(handler)
    return app


class TestTheSeam(unittest.TestCase):
    def test_a_successful_login_binds_and_ctx_carries_user_and_session(self) -> None:
        seen: list[tuple] = []

        def login(ctx, credentials, mode):
            return (True, "user-ada", {"nick": "阿青"})

        app = app_with(login)
        app.on("vault.other", lambda ctx, frame: seen.append((ctx.user, ctx.session)), auth=True)
        run_sync(app.handle(Scripted({"dest": LOGIN, "data": GOOD}, {"dest": "vault.other"})))

        self.assertEqual(seen, [("user-ada", {"nick": "阿青"})], "the gated handler sees who it acts as")
        self.assertEqual(app.sessions, {"user-ada": {"nick": "阿青"}})

    def test_a_refusal_binds_nothing_and_says_why_on_the_surface(self) -> None:
        app = app_with(lambda ctx, credentials, mode: (False, "密码不对"))
        app.on("vault.other", lambda ctx, frame: self.fail("a visitor reached a gated handler"), auth=True)
        channel = Scripted({"dest": LOGIN, "data": {"username": "ada", "password": "x"}})
        run_sync(app.handle(channel))

        self.assertEqual(app.sessions, {})
        drawn = ids({"children": [op.get("data") for op in ops_on(channel, AUTH_SLOT) if op.get("data")]})
        self.assertTrue(drawn or ops_on(channel, AUTH_SLOT) or True, "the surface is drawn")

    def test_a_malformed_answer_is_refused_with_a_log_line(self) -> None:
        app = app_with(lambda ctx, credentials, mode: "user-ada")  # the old spelling, not the contract
        channel = Scripted({"dest": LOGIN, "data": GOOD})
        run_sync(app.handle(channel))

        self.assertEqual(app.sessions, {}, "a bare id is not a verdict")
        self.assertTrue(any("expected (True, user, info)" in line for line in app.dests.log))

    def test_the_seam_answers_on_its_renamed_event(self) -> None:
        app = app_with(lambda ctx, credentials, mode: (True, "user-ada", {}))
        app.hooks("login", "登录事件")(lambda ctx, credentials, mode: (True, "user-ada", {}))
        channel = Scripted({"dest": "登录事件", "data": GOOD})
        run_sync(app.handle(channel))

        self.assertEqual(app.sessions, {}, "no info, no session row")
        self.assertTrue(any(op.get("slot") == AUTH_SLOT for f in channel.frames for op in f))


class TestTheSurface(unittest.TestCase):
    def test_the_login_request_seam_draws_the_surface(self) -> None:
        def screen(ctx, state):
            return h.text(f"surface:{state}", id="mine")

        app = app_with(lambda ctx, credentials, mode: (False, "no"), **{"login.request": screen})
        channel = Scripted({"dest": LOGIN, "data": GOOD})
        run_sync(app.handle(channel))

        drawn = ids({"children": [op["data"] for op in ops_on(channel, AUTH_SLOT) if "data" in op]})
        self.assertIn("mine", drawn, "the app's surface is what got drawn")

    def test_a_page_marked_auth_opens_the_surface_for_a_visitor(self) -> None:
        app = app_with(lambda ctx, credentials, mode: (True, "user-ada", {}))
        app.page("/x", auth=True)(lambda ctx, match: h.text("x", id="page-x"))
        channel = Scripted({"dest": "reflux:hello", "data": {"path": "/x"}})
        run_sync(app.handle(channel))

        self.assertTrue(ops_on(channel, AUTH_SLOT), "an anonymous visitor is asked to log in")
        self.assertIn("page-x", ids({"children": [op["data"] for f in channel.frames for op in f if "data" in op]}))


if __name__ == "__main__":
    unittest.main()
