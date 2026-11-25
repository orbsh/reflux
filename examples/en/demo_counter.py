"""A counter: the most ordinary page there is, here so the API itself is easy to read.

The pages before this one each argue something (the vocabulary, the walkthrough, the conversation);
this one has no ambition about content — a number, three buttons, an input, a short history — so every
line it is made of is only a use of the API. Four things to read:

- `@app.page(...)`: the decorator is used in this file. It sits inside `register(app)` because a page
  module must not import the app (`python3 -m examples.en.demo_app` runs the app module as `__main__`),
  so the app arrives as an argument — and the decorator is still the decorator.
- `h.*`: the page's vocabulary. A node's name is the wire's `type`; its keywords are that node's fields.
- **A closure sink**: the three buttons' handlers are written beside the buttons, they receive the
  event's value, and their slots are captured. One request, one answer — that is how it is written.
- **State follows the connection**: `ctx.data` belongs to one socket, so two tabs count separately and a
  refresh starts over. This page has no database and needs none.
"""

from __future__ import annotations

from typing import Any, Protocol, cast

from reflux import Context
from reflux.sdk import h
from reflux.slots import Slot

__all__ = ["HISTORY", "PAGE", "State", "counter_of", "record", "register", "state", "step_line"]

PAGE = "/counter"
HISTORY = 6  # how many entries the log keeps; past that the oldest one is removed


class _Counter(Protocol):
    """The `counter` family: the value, the step line, the history."""

    count: Slot
    hint: Slot
    history: Slot


def counter_of(ctx: Context) -> _Counter:
    """This page's slots, typed — `ctx.slot("counter")` is the same thing without the static check."""
    return cast(_Counter, ctx.slot("counter"))


class State:
    """One connection's count. Two tabs are two States."""

    def __init__(self) -> None:
        self.value = 0
        self.step = 1
        self.ids: list[str] = []  # the history's node ids; removing the oldest needs them


def state(ctx: Context) -> State:
    """This connection's count, made on first use (`ctx.data` lives and dies with the connection)."""
    return cast(State, ctx.data.setdefault("counter", State()))


def step_line(step: int) -> str:
    """What `counter.hint` normally says. One sentence, so it is written once."""
    return f"step {step} · one press moves it this far"


def record(ctx: Context, label: str) -> None:
    """Add a line to the history and drop the oldest past the cap — a list slot's `append` and `remove`."""
    slots = counter_of(ctx)
    current = state(ctx)
    bump = len(current.ids) + 1
    ident = f"log-{bump}"
    current.ids.append(ident)
    slots.history.append(h.text(f"{label} → {current.value}", variant="muted", id=ident))
    while len(current.ids) > HISTORY:
        slots.history.remove(current.ids.pop(0))


def register(app: Any) -> None:
    """Put this page on the app: its route (the decorator is right here), and its four landing points.

    Every landing point is a closure, so none of them is in the app's table — they exist once this page
    has been drawn and are gone when it turns. That is why `register` has nothing else to declare: no
    name has to be registered ahead of the page, except the route itself.
    """

    # A slot carries a node on the wire; these two carry one **value** — a number, a line of text. So
    # what that value looks like is said here once, and the page writes values: `slots.count.set(3)`.
    # A node still goes through untouched (`slots.count.set(h.text("3"))`): already a node, not a value.
    app.view("counter.count", lambda value: h.text(str(value), variant="heading-1", id="counter-value"))
    app.view("counter.hint", lambda value: h.text(value, variant="muted", id="counter-hint"))

    # The names are declared here once: `/status` and `cli dests` list "names in use", and should not
    # wait for someone to open this page first.
    for name in ("count", "hint", "history"):
        app.declare(f"counter.{name}")

    @app.page(PAGE, title="Counter")
    def counter_page(ctx: Context, match) -> None:
        """One draw of the counter: the value comes from the connection's State, the handlers from below."""
        slots = counter_of(ctx)
        current = state(ctx)
        if not ctx.data.get("counter_seeded"):
            # A slot outlives a `create`, so the value is seeded once: seeding again would push the
            # number the reader just changed back to zero.
            ctx.data["counter_seeded"] = True
            slots.count.set(current.value)
            slots.hint.set(step_line(current.step))

        def change(by: int) -> None:
            current.value += by * current.step
            slots.count.set(current.value)
            record(ctx, f"{by * current.step:+d}")

        def up(value: object) -> None:
            change(+1)

        def down(value: object) -> None:
            change(-1)

        def reset(value: object) -> None:
            current.value = 0
            slots.count.set(0)
            record(ctx, "reset")

        def set_step(value: object) -> None:
            # A bundle submits the object it packed ({field: value}), and the value is a string — so this
            # both parses it and refuses it.
            raw = value.get("step") if isinstance(value, dict) else None
            text = raw.strip() if isinstance(raw, str) else ""
            try:
                step = int(text)
            except ValueError:
                slots.hint.set(f"“{text}” is not a whole number; the step is still {current.step}")
                return
            current.step = min(max(step, 1), 10)
            slots.hint.set(step_line(current.step))

        return (
            h.frame(
                h.text("Counter", variant="heading-1", id="counter-title"),
                h.text(
                    "The state hangs on the connection (`ctx.data`): open two tabs and each counts for itself; "
                    "a refresh starts over.",
                    variant="muted",
                    id="counter-blurb",
                ),
                h.text(source=slots.count, id="counter-slot"),
                h.text(source=slots.hint, id="counter-hint-slot"),
                h.frame(
                    # A `button` lives inside a `bundle`, and the bundle's `submit` names the press —
                    # so each press is a bundle's submit, not a button that speaks on its own (ADR 0032 §3).
                    h.bundle(h.button("−"), sink=down, submit=["button"], id="counter-down"),
                    h.bundle(h.button("＋"), sink=up, submit=["button"], id="counter-up"),
                    h.bundle(h.button("Reset"), sink=reset, submit=["button"], id="counter-reset"),
                    horizontal=True,
                    grid={"grid-template-columns": "max-content max-content max-content", "gap": "8px",
                          "justify-content": "start"},
                    id="counter-buttons",
                ),
                h.frame(
                    h.text("Step", variant="muted"),
                    # A field's exit is the group it sits in: `tag` is the key it packs under, `submit` the timing.
                    h.bundle(
                        h.input(tag="step", placeholder="1–10, Enter to apply", id="counter-step"),
                        sink=set_step,
                        submit=["enter"],
                        id="counter-step-form",
                    ),
                    horizontal=True,
                    grid={"grid-template-columns": "auto 1fr", "gap": "8px", "align-items": "center"},
                    variant="card",
                    id="counter-step-box",
                ),
                h.frame(
                    h.text("History", variant="heading-3"),
                    h.tiles(source=slots.history, id="counter-history"),
                    grid={"grid-auto-rows": "auto", "gap": "6px", "align-content": "start"},
                    variant="card",
                    id="counter-log",
                ),
                grid={"grid-auto-rows": "auto", "gap": "16px", "align-content": "start"},
                id="counter-page",
            )
        )