"""A counter: the most ordinary page there is, here so the API itself is easy to read.

The pages before this one each argue something (the vocabulary, the walkthrough, the conversation);
this one has no ambition about content — a number, three buttons, an input, a short history — so every
line it is made of is only a use of the API. A few things to read:

- `@app.page(...)`: the decorator is used in this file. It sits inside `register(app)` because a page
  module must not import the app (`python3 -m examples.en.demo_app` runs the app module as `__main__`),
  so the app arrives as an argument — and the decorator is still the decorator.
- `h.*`: the page's vocabulary. A node's name is the wire's `type`; its keywords are that node's fields.
- **Names are built with `/`, verbs are members**: `ctx.slot / "counter" / "count"` is a slot's name and
  `slot.set(...)` is its verb — construction and membership stop sharing one dot.
- **A closure sink**: the three buttons' handlers are written beside the buttons, they receive the
  event's value, and the handles are captured. One request, one answer — that is how it is written.
- **State follows the connection**: `ctx.data` belongs to one socket, so two tabs count separately and a
  refresh starts over. This page has no database and needs none.
- **A slot can own a value** (`reflux.signals`): `.signal(0)` gives a slot a cell and from then on
  `.value` reads and writes it; `.computed(fn)` is a read-only derivation; `.keyed(row)` keeps a list
  slot aligned by id. One cell per name per connection, so drawing the page again does not seed it back.
  `step` and `refusal` have no cell — they never reach the wire, they are local in-between values.
"""

from __future__ import annotations

from typing import Any, cast

from reflux import Context, signals
from reflux.sdk import h

__all__ = ["HISTORY", "PAGE", "State", "register", "state", "step_line"]

PAGE = "/counter"
HISTORY = 6  # how many entries the log keeps; past that the oldest one is removed


def step_line(step: int) -> str:
    """What `counter.hint` normally says. One sentence, so it is written once."""
    return f"step {step} · one press moves it this far"


def _row(label: str, row_id: str) -> Any:
    """One history line: the id comes from the data (handed back by `keyed`), never from the position."""
    return h.text(label, variant="muted", id=row_id)


class State:
    """One connection's count. Two tabs are two States.

    Three slots each own a cell (`count`'s, `hint`'s, `history`'s), and a cell is registered per name on
    the connection, so drawing this page again hands back the same one. `step` and `refusal` are the two
    signals with no cell — they never reach the wire, so the whole State still lives in `ctx.data`.
    """

    def __init__(self, ctx: Context) -> None:
        counter = ctx.slot / "counter"
        self.step = signals.Signal(1)
        self.refusal = signals.Signal("")
        self.count = (counter / "count").signal(0)
        self.hint = (counter / "hint").computed(self._hint)
        self.history = (counter / "history").keyed(_row)
        self.seq = 0  # a row's identity comes from the data: `log-1`, `log-2`, …

    def _hint(self) -> str:
        return self.refusal.value or step_line(self.step.value)

    def record(self, label: str) -> None:
        """Add a line; whatever falls off the cap leaves with the table (`keyed` removes by id, not by slot)."""
        self.seq += 1
        row = (f"log-{self.seq}", f"{label} → {self.count.value}")
        self.history.value = (self.history.value + [row])[-HISTORY:]


def state(ctx: Context) -> State:
    """This connection's count, made on first use (`ctx.data` lives and dies with the connection).

    A slot's cell is idempotent, but `step` and `refusal` are not — building a State per draw and
    throwing it away would reset those two, so the whole State is still cached.
    """
    # Not `setdefault(..., State(ctx))`: that builds a State on every draw and throws it away.
    current = ctx.data.get("counter")
    if current is None:
        current = ctx.data["counter"] = State(ctx)
    return cast(State, current)


def register(app: Any) -> None:
    """Put this page on the app: its route (the decorator is right here), two views, three names.

    Every landing point is a closure, so none of them is in the app's table — they exist once this page
    has been drawn and are gone when it turns. That is why `register` has nothing else to declare: no
    name has to be registered ahead of the page, except the route itself.
    """

    # A slot carries a node on the wire; these two carry one **value** — a number, a line of text. So
    # what that value looks like is said here once, and something writes values: `current.count.value = 3`.
    # A node still goes through untouched (`slot.set(h.text("3"))`): already a node, not a value.
    counter = app.slot / "counter"
    (counter / "count").view(
        lambda value: h.text(str(value), variant="heading-1", id="counter-value")
    )
    (counter / "hint").view(lambda value: h.text(value, variant="muted", id="counter-hint"))

    # The names are declared here once: `/status` and `inspect` list "names in use", and should not
    # wait for someone to open this page first.
    for name in ("count", "hint", "history"):
        app.declare(f"counter.{name}")

    @app.page(PAGE, title="Counter")
    def counter_page(ctx: Context, match) -> None:
        """One draw of the counter: the value comes from the connection's State, the handlers from below."""
        current = state(ctx)

        def change(by: int) -> None:
            with signals.batch():  # one press: the value moves, a line is written, the page hears once
                current.count.value += by * current.step.value
                current.record(f"{by * current.step.value:+d}")

        def up(value: object) -> None:
            change(+1)

        def down(value: object) -> None:
            change(-1)

        def reset(value: object) -> None:
            with signals.batch():
                current.count.value = 0
                current.record("reset")

        def set_step(value: object) -> None:
            # A loom submits the object it packed ({field: value}), and the value is a string — so this
            # both parses it and refuses it.
            raw = value.get("step") if isinstance(value, dict) else None
            text = raw.strip() if isinstance(raw, str) else ""
            try:
                step = int(text)
            except ValueError:
                current.refusal.value = f"“{text}” is not a whole number; the step is still {current.step.value}"
                return
            with signals.batch():
                current.step.value = min(max(step, 1), 10)
                current.refusal.value = ""  # a good input retires the refusal

        return (
            h.frame(
                h.text("Counter", variant="heading-1", id="counter-title"),
                h.text(
                    "The state hangs on the connection (`ctx.data`): open two tabs and each counts for itself; "
                    "a refresh starts over.",
                    variant="muted",
                    id="counter-blurb",
                ),
                # Reading a slot takes the handles above: each name is written once, never twice.
                h.text(source=current.count, id="counter-slot"),
                h.text(source=current.hint, id="counter-hint-slot"),
                h.frame(
                    # A `button` lives inside a `loom`, and the loom's `submit` names the press —
                    # so each press is a loom's submit, not a button that speaks on its own (ADR 0032 §3).
                    h.loom(h.button("−"), sink=down, submit=["button"], id="counter-down"),
                    h.loom(h.button("＋"), sink=up, submit=["button"], id="counter-up"),
                    h.loom(h.button("Reset"), sink=reset, submit=["button"], id="counter-reset"),
                    horizontal=True,
                    grid={"grid-template-columns": "max-content max-content max-content", "gap": "8px",
                          "justify-content": "start"},
                    id="counter-buttons",
                ),
                h.frame(
                    h.text("Step", variant="muted"),
                    # A field's exit is the group it sits in: `tag` is the key it packs under, `submit` the timing.
                    h.loom(
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
                    h.tiles(source=current.history, id="counter-history"),
                    grid={"grid-auto-rows": "auto", "gap": "6px", "align-content": "start"},
                    variant="card",
                    id="counter-log",
                ),
                grid={"grid-auto-rows": "auto", "gap": "16px", "align-content": "start"},
                id="counter-page",
            )
        )