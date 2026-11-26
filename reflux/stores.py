"""Stores: where a value lives when it outlives the connection.

A signal can be told to keep its value past one connection — `Signal(0).store("counter.step")`. An
anonymous device keeps it in the delivery's own data (the session, which dies with the connection), and
an authenticated user keeps it in the app's store, keyed by the user id, so the same value follows them
across connections and devices.

The interface is two calls, because that is all a value needs:

    store.load(user, key) -> value | None
    store.save(user, key, value) -> None

Values are JSON: what survives a reconnect has to be something that can be written down. A node is not
(`h.text(...)` is the page's, not a fact about the user) — store the number, let a view draw it.

Three implementations ship, and they are three shapes of the same two calls:
`MemoryStore` (the default — a process's lifetime, which is what a test or a single-node demo wants),
`SqliteStore` (the SQL example, and the smallest thing that survives a restart), and `KvStore` (a KV
engine or Redis: the client is the backend, and `get`/`set` are all it has to have).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Protocol

__all__ = ["FjallStore", "KvStore", "MemoryStore", "SqliteStore", "Store", "make_store"]


class Store(Protocol):
    """Two calls: the value for (user, key), and the new value. No keys enumeration, no listing."""

    def load(self, user: str, key: str) -> Any | None: ...

    def save(self, user: str, key: str, value: Any) -> None: ...


def _encode(user: str, key: str, value: Any) -> str:
    """A stored value is JSON — say which value was not, instead of writing a frame the store can't read."""
    try:
        return json.dumps(value)
    except (TypeError, ValueError) as error:
        raise TypeError(
            f"store({key!r}) for user {user!r}: a stored value must be JSON, got {type(value).__name__} "
            f"({error}); store the value and let a view draw the node"
        ) from error


class MemoryStore:
    """A dict, held for the process's lifetime — the default, and what a test's app gets."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], str] = {}

    def load(self, user: str, key: str) -> Any | None:
        raw = self._rows.get((user, key))
        return None if raw is None else json.loads(raw)

    def save(self, user: str, key: str, value: Any) -> None:
        self._rows[(user, key)] = _encode(user, key, value)

    def __repr__(self) -> str:
        return f"<MemoryStore {len(self._rows)} values>"


class KvStore:
    """The KV shape: one key per (user, key), the value as JSON.

    A client is anything with `get(name)` and `set(name, value)` — an embedded KV engine's Python client
    and a server's client are the same two calls — so the backend is a client, not an adapter class.
    Keys carry a prefix so one database can hold more than this app's values.

    There is no query here on purpose: `.store(key)` reads and writes one key at a time, and a value that
    needs to be found by what it says is not a stored value — it is an index, and that belongs to the
    app's own store.
    """

    def __init__(self, client: Any, *, prefix: str = "reflux:") -> None:
        self._client = client
        self._prefix = prefix

    def _key(self, user: str, key: str) -> str:
        return f"{self._prefix}{user}:{key}"

    def load(self, user: str, key: str) -> Any | None:
        raw = self._client.get(self._key(user, key))
        if raw is None:
            return None
        return json.loads(raw.decode() if isinstance(raw, bytes) else raw)

    def save(self, user: str, key: str, value: Any) -> None:
        self._client.set(self._key(user, key), _encode(user, key, value))

    def __repr__(self) -> str:
        return f"<KvStore {self._prefix!r}>"


class SqliteStore:
    """The SQL shape: one row per (user, key), the value as JSON — the example, not the ceiling.

    `sqlite3` is synchronous, and so is this interface: a page declares its stored values while it is
    being drawn, so a read is one row lookup. A store that is slow or remote (Redis, a KV server) gets
    wrapped in a thread rather than making the whole signal layer async.
    """

    def __init__(self, path: str | Path = ":memory:") -> None:
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        with self._lock:
            self._db.execute(
                "create table if not exists state ("
                "  scope text not null, key text not null, value text not null,"
                "  primary key (scope, key)"
                ")"
            )
            self._db.commit()

    def load(self, user: str, key: str) -> Any | None:
        with self._lock:
            row = self._db.execute(
                "select value from state where scope = ? and key = ?", (user, key)
            ).fetchone()
        return None if row is None else json.loads(row[0])

    def save(self, user: str, key: str, value: Any) -> None:
        payload = _encode(user, key, value)
        with self._lock:
            self._db.execute(
                "insert into state (scope, key, value) values (?, ?, ?) "
                "on conflict (scope, key) do update set value = excluded.value",
                (user, key, payload),
            )
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()


class FjallStore:
    """fjall through its own Python bindings (`pip install pyfjall`): an LSM engine in a directory.

    One database, one keyspace, the key `f"{user}:{key}"`, the value JSON. `durable=True` persists each
    write with `sync_all` (an fsync per change); the default leaves it to the engine's own flush, which
    is what a page's stored value usually wants — losing the last few seconds of a counter is not data
    loss the way losing an order would be.
    """

    def __init__(self, path: str | Path, *, keyspace: str = "reflux", durable: bool = False) -> None:
        try:
            from pyfjall import Database
        except ImportError as error:  # the backend is a client, so its absence is a message, not a crash
            raise RuntimeError(
                "the fjall store needs `pip install reflux[fjall]` (pyfjall, fjall's Python bindings)"
            ) from error
        self._db = Database(str(path))
        self._keys = self._db.keyspace(keyspace)
        self._durable = durable
        self._keyspace = keyspace

    def load(self, user: str, key: str) -> Any | None:
        raw = self._keys.get(f"{user}:{key}".encode())
        if raw is None:
            return None
        return json.loads(raw.decode() if isinstance(raw, bytes) else raw)

    def save(self, user: str, key: str, value: Any) -> None:
        self._keys[f"{user}:{key}".encode()] = _encode(user, key, value).encode()
        if self._durable:
            self._db.persist("sync_all")

    def close(self) -> None:
        for name in ("close", "shutdown"):
            closer = getattr(self._db, name, None)
            if callable(closer):
                closer()
                return

    def __repr__(self) -> str:
        return f"<FjallStore {self._keyspace!r}>"


def make_store(backend: Any, config: dict[str, Any] | None = None, **kwargs: Any) -> Store:
    """A store by name: `make_store("redis", {"host": "127.0.0.1", "port": 6379})`.

    | name      | what it takes                                                     |
    |-----------|-------------------------------------------------------------------|
    | `memory`  | nothing — the process's lifetime (the default)                    |
    | `sqlite`  | `path` (`:memory:` when absent)                                   |
    | `kv`      | `client` — anything with `get`/`set`, plus `prefix`               |
    | `fjall`   | `path`, plus `keyspace` and `durable`                             |
    | `redis`   | whatever `redis.Redis(**config)` takes: `host`, `port`, `db`, …   |

    `redis` is last on purpose, and it is tolerated rather than recommended: it puts a page's stored
    value behind a network hop, when the whole point of `.store(key)` is one number that outlives a
    redraw. It is here because deployments have it, not because this is a good place for it.

    A name this table does not know is a `ValueError` that lists the ones it does.
    """
    settings = dict(config or {}) | kwargs
    name = (backend or "memory").lower() if isinstance(backend, str) else "memory"
    if name == "memory":
        return MemoryStore()
    if name == "sqlite":
        return SqliteStore(settings.pop("path", ":memory:"))
    if name == "kv":
        client = settings.pop("client", None)
        if client is None:
            raise ValueError("the kv store needs a client: make_store(\"kv\", {\"client\": …})")
        return KvStore(client, prefix=settings.pop("prefix", "reflux:"))
    if name == "fjall":
        path = settings.pop("path", None)
        if path is None:
            raise ValueError("the fjall store needs a path: make_store(\"fjall\", {\"path\": …})")
        return FjallStore(path, **settings)
    if name in ("redis", "valkey"):
        try:
            import redis  # type: ignore[import-not-found]  # a named backend is the deployment's
        except ImportError as error:
            raise RuntimeError("the redis store needs `pip install reflux[redis]` (redis-py)") from error
        prefix = settings.pop("prefix", "reflux:")
        return KvStore(redis.Redis(**settings), prefix=prefix)
    raise ValueError(f"unknown store {backend!r}: memory, sqlite, kv, redis, fjall")
