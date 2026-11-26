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

Two implementations ship, and they are the interface's two shapes rather than two products:
`MemoryStore` (the default — a process's lifetime, which is what a test or a single-node demo wants)
and `SqliteStore` (the SQL example, and the smallest thing that survives a restart). Redis and a KV
engine implement the same two calls; they are adapters, not the interface.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Protocol

__all__ = ["MemoryStore", "SqliteStore", "Store"]


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