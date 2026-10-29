"""The producer's event registry — the only authority on which event names exist.

An event name is an address, not a label (§事件名就是寻址契约): an unregistered name is
refused, counted and logged, and never dispatched dynamically (``getattr(module, name)`` is an
arbitrary-attribute surface, and it cannot be checked before the run either). The reserved
prefix belongs to the framework, so an application registering on it is a startup error; the
framework's own protocol names come in through :meth:`Registry.builtin`, which is the one
legitimate use of that prefix.

    intents = Registry()

    @events.register("chat.send")
    def send(session, frame): ...
"""

from __future__ import annotations

import traceback
from typing import Any, Callable, overload

from .protocol import RESERVED_PREFIX

Handler = Callable[[Any, dict], None]


class RegistryError(Exception):
    """A registration that can never be right — raised while the app is still starting."""


class Registry:
    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}
        self._builtin: set[str] = set()
        self.calls = 0
        self.refused = 0
        self.log: list[str] = []

    # --- registration (startup: loud, never a silent overwrite) ---------------------------

    @overload
    def register(self, name: str) -> Callable[[Handler], Handler]: ...

    @overload
    def register(self, name: str, handler: Handler) -> Handler: ...

    def register(
        self, name: str, handler: Handler | None = None
    ) -> Callable[[Handler], Handler] | Handler:
        """``@events.register("name")`` or ``events.register("name", handler)``."""

        def add(fn: Handler) -> Handler:
            self._add(name, fn, builtin=False)
            return fn

        return add if handler is None else add(handler)

    def builtin(self, name: str, handler: Handler) -> Handler:
        """Register one of the framework's own names (``reflux:hello``)."""
        return self._add(name, handler, builtin=True)

    def _add(self, name: str, handler: Handler, *, builtin: bool) -> Handler:
        if not isinstance(name, str) or not name:
            raise RegistryError("an event name must be a non-empty string")
        if not callable(handler):
            raise RegistryError(f"{name!r}: handler must be callable, got {type(handler).__name__}")
        if name.startswith(RESERVED_PREFIX) and not builtin:
            raise RegistryError(
                f"{name!r} uses the reserved prefix {RESERVED_PREFIX!r} — the framework owns that "
                "namespace; register it under a name of your own"
            )
        if name in self._handlers:
            raise RegistryError(f"{name!r} is already registered")
        self._handlers[name] = handler
        if builtin:
            self._builtin.add(name)
        return handler

    # --- dispatch ------------------------------------------------------------------------

    def names(self) -> list[str]:
        """What `reflux events` prints: the whole registry, sorted."""
        return sorted(self._handlers)

    def table(self) -> list[tuple[str, str, str]]:
        """(event name, source, kind) for every name, sorted by name.

        `source` is where the handler was written (`module.qualname`) — the same rule the route
        table's source column follows: report the place it was written, never a guess. `kind` is
        `builtin` for the framework's own protocol names (`reflux:hello`, `reflux:nav`) and `app`
        for everything the application registered.

        Runtime counters (`calls`, `refused`, `log`) are deliberately not here: they describe a
        running app, and mixing them into "what exists" makes a fresh process look like it has data.
        """
        rows: list[tuple[str, str, str]] = []
        for name in sorted(self._handlers):
            handler = self._handlers[name]
            module = getattr(handler, "__module__", None) or type(handler).__module__
            qualname = getattr(handler, "__qualname__", None) or type(handler).__qualname__
            rows.append((name, f"{module}.{qualname}", "builtin" if name in self._builtin else "app"))
        return rows

    def dispatch(self, session, frame: Any) -> bool:
        """Hand one uplink frame to its handler. False when it was refused."""
        if not isinstance(frame, dict) or not isinstance(frame.get("dest"), str):
            self.refused += 1
            self.log.append(f"malformed frame from {session.id}: {frame!r}")
            return False
        name = frame["dest"]
        handler = self._handlers.get(name)
        if handler is None:
            self.refused += 1
            self.log.append(f"unregistered event {name!r} from {session.id} on {session.path}")
            return False
        self.calls += 1
        try:
            handler(session, frame)
        except Exception:  # a handler's defect stays a log line; the session survives
            self.refused += 1
            self.log.append(
                f"handler for {name!r} raised:\n{traceback.format_exc()}"
            )
            return False
        return True