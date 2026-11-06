"""The producer's uplink registry — the only authority on which landing points exist.

An uplink's dest is an address, not a label (§上行落点就是寻址契约): an unregistered name is
refused, counted and logged, and never dispatched dynamically (``getattr(module, name)`` is an
arbitrary-attribute surface, and it cannot be checked before the run either). The reserved
prefix belongs to the framework, so an application registering on it is a startup error; the
framework's own protocol names come in through :meth:`Registry.builtin`, which is the one
legitimate use of that prefix.

    intents = Registry()

    @events.register("chat.send")
    def send(ctx, frame): ...        # `ctx.send(...)` answers; a return says nothing
"""

from __future__ import annotations

import traceback
from typing import Any, Callable, overload

from .protocol import RESERVED_PREFIX

Handler = Callable[[Any, dict], None]


class RegistryError(Exception):
    """A registration that can never be right — raised while the app is still starting."""


class Registry:
    def __init__(self, context: Callable[..., Any] | None = None) -> None:
        """`context` builds one delivery (`Context(app, device, frame)`) — the app supplies it, so the
        registry never has to know what a context is, only that a handler is handed one."""
        self._context = context or (lambda device, frame=None: device)
        # name -> (handler, gated). The gate is a property of the DECLARATION, so it is stored
        # exactly where the name is: one lookup answers both "who answers this" and "does it need
        # a user", and there is no second table that could disagree with the first.
        self._handlers: dict[str, tuple[Handler, bool]] = {}
        self._builtin: set[str] = set()
        self.calls = 0
        self.refused = 0
        self.log: list[str] = []

    # --- registration (startup: loud, never a silent overwrite) ---------------------------

    @overload
    def register(self, name: str, *, auth: bool = False) -> Callable[[Handler], Handler]: ...

    @overload
    def register(self, name: str, handler: Handler, *, auth: bool = False) -> Handler: ...

    def register(
        self, name: str, handler: Handler | None = None, *, auth: bool = False
    ) -> Callable[[Handler], Handler] | Handler:
        """``@events.register("name")`` or ``events.register("name", handler)``.

        `auth=True` says this landing point is served only to a device with a user bound to it —
        declared HERE, on the same statement that names the event, because a requirement kept in a
        second table keyed by the same name is a rule free to drift from its subject. Absent is the
        default and means public: an app that never says `auth=True` has no gate at all.
        """

        def add(fn: Handler) -> Handler:
            self._add(name, fn, builtin=False, gated=auth)
            return fn

        return add if handler is None else add(handler)

    def builtin(self, name: str, handler: Handler, *, auth: bool = False) -> Handler:
        """Register one of the framework's own names (``reflux:hello``)."""
        return self._add(name, handler, builtin=True, gated=auth)

    def _add(self, name: str, handler: Handler, *, builtin: bool, gated: bool = False) -> Handler:
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
        self._handlers[name] = (handler, gated)
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
            handler, gated = self._handlers[name]
            module = getattr(handler, "__module__", None) or type(handler).__module__
            qualname = getattr(handler, "__qualname__", None) or type(handler).__qualname__
            kind = "builtin" if name in self._builtin else "app"
            rows.append((name, f"{module}.{qualname}", kind))
        return rows

    def gated(self, name: str) -> bool:
        """Does this landing point need a bound user? False for a name nobody registered.

        An unknown name is the registry's ordinary refusal (`dispatch` answers it), never a gate:
        a name with no declaration cannot be made protected by the absence of one.
        """
        row = self._handlers.get(name)
        return bool(row and row[1])

    def dispatch(self, device: Any, frame: Any) -> bool:
        """Hand one uplink frame to its handler, as a context. False when it was refused."""
        ctx = self._context(device, frame)
        if not isinstance(frame, dict) or not isinstance(frame.get("dest"), str):
            self.refused += 1
            self.log.append(f"malformed frame from {ctx.id}: {frame!r}")
            return False
        name = frame["dest"]
        row = self._handlers.get(name)
        if row is None:
            self.refused += 1
            self.log.append(f"unregistered event {name!r} from {ctx.id} on {ctx.path}")
            return False
        return self._call(name, ctx, frame)

    def announce(self, name: str, device: Any, frame: dict) -> bool:
        """Raise one of the host's own events (`connect` / `location` / `disconnect`).

        Nobody listening is the ordinary case — most apps hear none of them — so absent is not an
        error and does not count as a refusal. A handler that raises is counted and logged exactly
        like a dispatched one: the device outlives its app's defect.
        """
        if name not in self._handlers:
            return False
        return self._call(name, self._context(device, frame), frame)

    def _call(self, name: str, ctx: Any, frame: dict) -> bool:
        """One handler, one accounting — the only place a handler's exception is caught."""
        self.calls += 1
        try:
            self._handlers[name][0](ctx, frame)
        except Exception:  # a handler's defect stays a log line; the device survives
            self.refused += 1
            self.log.append(f"handler for {name!r} raised:\n{traceback.format_exc()}")
            return False
        return True