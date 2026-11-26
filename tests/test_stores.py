"""Where a `.store(key)` value lives: the connection's own data, or the app's store by user id."""

from __future__ import annotations

import unittest

from reflux import signals
from reflux.application import create_app
from reflux.sdk import h
from reflux.stores import MemoryStore, SqliteStore

from tests.fakes import FakeDevice


def device(app, user: str | None = None, id: str = "one") -> FakeDevice:
    made = FakeDevice(id=id, app=app)
    if user is not None:
        made.data["user"] = user
    return made


class Anonymous(unittest.TestCase):
    """No user: the value belongs to the connection, so it survives a redraw and nothing else."""

    def test_a_redraw_hands_back_the_same_signal(self) -> None:
        app = create_app()
        ctx = app.context(device(app))
        with signals.drawing(ctx):
            step = signals.Signal(1).store("counter.step")
        step.value = 4

        with signals.drawing(ctx):
            again = signals.Signal(1).store("counter.step")

        self.assertIs(again, step)
        self.assertEqual(again.value, 4)

    def test_another_connection_starts_at_the_default(self) -> None:
        app = create_app()
        one = app.context(device(app))
        with signals.drawing(one):
            step = signals.Signal(1).store("counter.step")
        step.value = 4

        two = app.context(device(app, id="second"))
        with signals.drawing(two):
            other = signals.Signal(1).store("counter.step")

        self.assertEqual(other.value, 1, "an anonymous value is the connection's, not the process's")


class Authenticated(unittest.TestCase):
    """A user: the value lives in the app's store under their id, so another connection finds it."""

    def test_the_value_follows_the_user_to_another_connection(self) -> None:
        app = create_app()
        first = app.context(device(app, user="ada"))
        with signals.drawing(first):
            step = signals.Signal(1).store("counter.step")
        step.value = 4

        self.assertEqual(app.store.load("ada", "counter.step"), 4, "written on the way out")

        second = app.context(device(app, user="ada", id="second"))
        with signals.drawing(second):
            again = signals.Signal(1).store("counter.step")

        self.assertEqual(again.value, 4, "the same user's next connection reads it back")

    def test_another_user_does_not_see_it(self) -> None:
        app = create_app()
        mine = app.context(device(app, user="ada"))
        with signals.drawing(mine):
            step = signals.Signal(1).store("counter.step")
        step.value = 4

        theirs = app.context(device(app, user="bob", id="second"))
        with signals.drawing(theirs):
            other = signals.Signal(1).store("counter.step")

        self.assertEqual(other.value, 1, "a value is one user's")

    def test_a_sqlite_store_keeps_it_across_apps(self) -> None:
        store = SqliteStore()
        app = create_app(store=store)
        first = app.context(device(app, user="ada"))
        with signals.drawing(first):
            step = signals.Signal(2).store("counter.step")
        step.value = 7

        again = create_app(store=store)
        second = again.context(device(again, user="ada", id="third"))
        with signals.drawing(second):
            step_again = signals.Signal(2).store("counter.step")

        self.assertEqual(step_again.value, 7, "the value outlived the app object")
        self.assertIsInstance(store, SqliteStore)
        store.close()


class Refusals(unittest.TestCase):
    def test_store_after_bind_is_refused(self) -> None:
        app = create_app()
        ctx = app.context(device(app))
        (ctx.slot / "counter" / "count").view(lambda value: h.text(str(value)))
        with self.assertRaises(RuntimeError) as caught:
            with signals.drawing(ctx):
                signals.Signal(0).bind(ctx.slot / "counter" / "count").store("counter.count")
        self.assertIn("before bind", str(caught.exception))

    def test_store_outside_a_draw_is_refused(self) -> None:
        with self.assertRaises(RuntimeError) as caught:
            signals.Signal(0).store("counter.count")
        self.assertIn("delivery", str(caught.exception))

    def test_a_node_cannot_be_stored(self) -> None:
        app = create_app()
        ctx = app.context(device(app, user="ada"))
        with signals.drawing(ctx):
            value = signals.Signal(0).store("counter.count")
        with self.assertRaises(TypeError) as caught:
            value.value = h.text("a node")  # a stored value is JSON; a node is the page's
        self.assertIn("JSON", str(caught.exception))

    def test_a_memory_store_is_the_default(self) -> None:
        self.assertIsInstance(create_app().store, MemoryStore)


if __name__ == "__main__":
    unittest.main()