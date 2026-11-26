"""Where a `.store(key)` value lives: the connection's own data, or the app's store by user id."""

from __future__ import annotations

import sys
import types
import unittest
import unittest.mock

from reflux import signals
from reflux.application import create_app
from reflux.sdk import h
from reflux.stores import FjallStore, KvStore, MemoryStore, SqliteStore, make_store

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


class FakeKv:
    """A KV client's two calls — `redis.Redis` is this, and so is a KV engine's Python client."""

    def __init__(self) -> None:
        self.rows: dict[str, bytes] = {}

    def get(self, name: str) -> bytes | None:
        return self.rows.get(name)

    def set(self, name: str, value: str) -> None:
        self.rows[name] = value.encode()


class BackedByKv(unittest.TestCase):
    """`KvStore` is the backend shape: the client is the database, the key carries the user."""

    def test_the_value_round_trips_through_the_client(self) -> None:
        client = FakeKv()
        store = KvStore(client)
        store.save("ada", "counter.step", 3)

        self.assertEqual(client.rows, {"reflux:ada:counter.step": b"3"}, "one key per (user, key)")
        self.assertEqual(store.load("ada", "counter.step"), 3)

    def test_a_missing_key_is_none(self) -> None:
        self.assertIsNone(KvStore(FakeKv()).load("ada", "nothing"))

    def test_another_user_is_another_key(self) -> None:
        store = KvStore(FakeKv())
        store.save("ada", "counter.step", 3)
        self.assertIsNone(store.load("bob", "counter.step"))

    def test_the_prefix_is_the_deployment_s(self) -> None:
        client = FakeKv()
        KvStore(client, prefix="demo/").save("ada", "k", [1, 2])
        self.assertEqual(list(client.rows), ["demo/ada:k"])

    def test_the_signal_uses_it_like_any_other_store(self) -> None:
        client = FakeKv()
        app = create_app(store=KvStore(client))
        first = app.context(device(app, user="ada"))
        with signals.drawing(first):
            step = signals.Signal(1).store("counter.step")
        step.value = 5

        again = create_app(store=KvStore(client))
        second = again.context(device(again, user="ada", id="second"))
        with signals.drawing(second):
            step_again = signals.Signal(1).store("counter.step")

        self.assertEqual(step_again.value, 5, "the value is in the client, so a new app reads it back")

    def test_a_client_without_get_and_set_is_refused_at_the_first_write(self) -> None:
        store = KvStore(object())  # type: ignore[arg-type]
        with self.assertRaises(AttributeError):
            store.save("ada", "k", 1)



class FakeRedis:
    """`redis.Redis(**config)` as far as this repo uses it: get, set, and the kwargs it was built with."""

    def __init__(self, **config: object) -> None:
        self.config = config
        self.rows: dict[str, bytes] = {}

    def get(self, name: str) -> bytes | None:
        return self.rows.get(name)

    def set(self, name: str, value: str) -> None:
        self.rows[name] = value.encode()


class FakeKeyspace(dict):
    def get(self, key: bytes, default: object = None) -> object:
        return dict.get(self, key, default)


class FakeDatabase:
    """`pyfjall.Database`: a directory, a keyspace, and `persist("sync_all")`."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.space = FakeKeyspace()
        self.persisted = 0
        self.keyspaces: list[str] = []

    def keyspace(self, name: str) -> FakeKeyspace:
        self.keyspaces.append(name)
        return self.space

    def persist(self, mode: str) -> None:
        self.persisted += 1


def fake_module(name: str, **attrs: object) -> types.ModuleType:
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


class ByName(unittest.TestCase):
    """`app.set_store(name, config)` — the deployment names a backend, no page learns which."""

    def test_redis_takes_the_kwargs_redis_does(self) -> None:
        with unittest.mock.patch.dict(sys.modules, {"redis": fake_module("redis", Redis=FakeRedis)}):
            app = create_app().set_store("redis", {"host": "127.0.0.1", "port": 6380})

        self.assertIsInstance(app.store, KvStore)
        client = app.store._client  # the client is the backend
        self.assertEqual(client.config, {"host": "127.0.0.1", "port": 6380})

    def test_fjall_is_a_directory_and_a_keyspace(self) -> None:
        with unittest.mock.patch.dict(
            sys.modules, {"pyfjall": fake_module("pyfjall", Database=FakeDatabase)}
        ):
            store = make_store("fjall", {"path": "/tmp/reflux-store"})

        self.assertIsInstance(store, FjallStore)
        self.assertEqual(store._db.path, "/tmp/reflux-store")
        self.assertEqual(store._db.keyspaces, ["reflux"], "one named keyspace, not the default one")

    def test_fjall_round_trips_and_can_persist_each_write(self) -> None:
        with unittest.mock.patch.dict(
            sys.modules, {"pyfjall": fake_module("pyfjall", Database=FakeDatabase)}
        ):
            quiet = FjallStore("/tmp/a")
            loud = FjallStore("/tmp/b", durable=True)

        quiet.save("ada", "counter.step", 3)
        loud.save("ada", "counter.step", 3)

        self.assertEqual(quiet.load("ada", "counter.step"), 3)
        self.assertEqual(quiet._db.persisted, 0, "the engine's own flush is the default")
        self.assertEqual(loud._db.persisted, 1)

    def test_a_signal_stores_through_fjall(self) -> None:
        with unittest.mock.patch.dict(
            sys.modules, {"pyfjall": fake_module("pyfjall", Database=FakeDatabase)}
        ):
            store = make_store("fjall", {"path": "/tmp/reflux-store"})
            app = create_app(store=store)
            first = app.context(device(app, user="ada"))
            with signals.drawing(first):
                step = signals.Signal(1).store("counter.step")
            step.value = 9

            second = app.context(device(app, user="ada", id="second"))
            with signals.drawing(second):
                again = signals.Signal(1).store("counter.step")

        self.assertEqual(again.value, 9)

    def test_a_name_goes_into_create_app(self) -> None:
        app = create_app(store="sqlite")
        self.assertIsInstance(app.store, SqliteStore)

    def test_the_unknown_name_lists_the_known_ones(self) -> None:
        with self.assertRaises(ValueError) as caught:
            make_store("surrealdb")
        for name in ("memory", "sqlite", "kv", "redis", "fjall"):
            self.assertIn(name, str(caught.exception))

    def test_a_backend_that_is_not_installed_says_how_to_install_it(self) -> None:
        with unittest.mock.patch.dict(sys.modules, {"pyfjall": None}):
            with self.assertRaises(RuntimeError) as caught:
                make_store("fjall", {"path": "/tmp/x"})
        self.assertIn("reflux[fjall]", str(caught.exception))



if __name__ == "__main__":
    unittest.main()