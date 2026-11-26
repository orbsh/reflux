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
- **The signal is the subject, the slot is where it goes** (`reflux.signals`): `Signal(0).bind(slot)`
  says which slot the value writes through, `.view(fn)` says what the value looks like, `.keyed(row)`
  says a list is kept aligned by id, `.store(key)` says the value outlives the connection. Every
  declaration sits at the top of the page function, one per line; a redraw hands back the same signal,
  so the slot is never seeded back.
- **`step` / `refusal` / `seq` never reach the wire**: they have no slot, only `.store(key)` — an
  anonymous connection keeps them in its own data, an authenticated user in the app's store, by user id.
"""

from __future__ import annotations

from typing import Any

from reflux import Context, signals
from reflux.sdk import h

__all__ = ["HISTORY", "PAGE", "register", "step_line"]

PAGE = "/counter"
HISTORY = 6  # how many entries the log keeps; past that the oldest one is removed


def step_line(step: int) -> str:
    """What `counter.hint` normally says. One sentence, so it is written once."""
    return f"step {step} · one press moves it this far"


def _row(label: str, row_id: str) -> Any:
    """One history line: the id comes from the data (handed back by `keyed`), never from the position."""
    return h.text(label, variant="muted", id=row_id)


def register(app: Any) -> None:
    """Put this page on the app: its route, and those three names.

    Every landing point is a closure, so none of them is in the app's table — they exist once this page
    has been drawn and are gone when it turns. That is why `register` has nothing else to declare: no
    name has to be registered ahead of the page, except the route itself.
    """

    # The names are declared here once: `/status` and `inspect` list "names in use", and should not
    # wait for someone to open this page first.
    for name in ("count", "hint", "history"):
        app.declare(f"counter.{name}")

    @app.page(PAGE, title="Counter")
    def counter_page(ctx: Context, match) -> None:
        """One draw of the counter: the state is declared at the top, the handlers below are closures."""
        slots = ctx.slot
        # Three that never reach the wire: only `.store(key)`, no slot. An anonymous connection keeps
        # them in its own data (the session); an authenticated user keeps them in the app's store, by
        # user id — so another tab carries on where this one left off.
        step = signals.Signal(1).store("counter.step")
        refusal = signals.Signal("").store("counter.refusal")
        seq = signals.Signal(0).store("counter.seq")
        # Three that do: the value writes through to its slot, `.view` says what it looks like, and
        # `.keyed` keeps the list aligned by id.
        count = signals.Signal(0).bind(slots / "counter" / "count").view(
            lambda value: h.text(str(value), variant="heading-1", id="counter-value")
        )
        hint = signals.Computed(lambda: refusal.value or step_line(step.value)).bind(
            slots / "counter" / "hint"
        ).view(lambda value: h.text(value, variant="muted", id="counter-hint"))
        history = signals.Signal([]).keyed(_row).bind(slots / "counter" / "history")

        def record(label: str) -> None:
            """Add a line; whatever falls off the cap leaves with the table (`keyed` removes by id)."""
            seq.value += 1
            row = (f"log-{seq.value}", f"{label} → {count.value}")
            history.value = (history.value + [row])[-HISTORY:]

        def change(by: int) -> None:
            with signals.batch():  # one press: the value moves, a line is written, the page hears once
                count.value += by * step.value
                record(f"{by * step.value:+d}")

        def up(value: object) -> None:
            change(+1)

        def down(value: object) -> None:
            change(-1)

        def reset(value: object) -> None:
            with signals.batch():
                count.value = 0
                record("reset")

        def set_step(value: object) -> None:
            # A loom submits the object it packed ({field: value}), and the value is a string — so this
            # both parses it and refuses it.
            raw = value.get("step") if isinstance(value, dict) else None
            text = raw.strip() if isinstance(raw, str) else ""
            try:
                wanted = int(text)
            except ValueError:
                refusal.value = f"“{text}” is not a whole number; the step is still {step.value}"
                return
            with signals.batch():
                step.value = min(max(wanted, 1), 10)
                refusal.value = ""  # a good input retires the refusal

        return (
            h.frame(
                h.text("Counter", variant="heading-1", id="counter-title"),
                h.text(
                    "The state hangs on the connection (`ctx.data`): open two tabs and each counts for itself; "
                    "a refresh starts over.",
                    variant="muted",
                    id="counter-blurb",
                ),
                # Reading a slot takes the signals above: each name is written once, never twice.
                h.text(source=count, id="counter-slot"),
                h.text(source=hint, id="counter-hint-slot"),
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
                    h.tiles(source=history, id="counter-history"),
                    grid={"grid-auto-rows": "auto", "gap": "6px", "align-content": "start"},
                    variant="card",
                    id="counter-log",
                ),
                grid={"grid-auto-rows": "auto", "gap": "16px", "align-content": "start"},
                id="counter-page",
            )
        )