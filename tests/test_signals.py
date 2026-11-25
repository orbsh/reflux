"""The signals layer: one value, its readers, and the round that tells them.

Nothing here knows about pages or slots except the two adapters at the bottom (`bound`, `into`, `keyed`),
which write through a `ctx.slot` — so the tests drive a fake context and read the operations the effect
would have sent.
"""

from __future__ import annotations

import unittest

from reflux import signals


def _append_index(length: int, position: int) -> int | None:
    """Where `append` lands a row (fluxen `content::append_index`, the same table `move` borrows)."""
    if position == 0:
        return length
    if position > 0:
        spot = length - position
        return spot if 0 <= spot <= length else None
    spot = -position - 1
    return spot if 0 <= spot < length else None


class FakeSlot:
    """A slot that records what it was told, in order — and keeps the rows so the result can be read.

    The position arithmetic is the renderer's, not the tester's: `move` is counted on the list with the
    row lifted out, and out of range is refused rather than clamped (fluxen ADR 0005), so a wrong
    position in `keyed` shows up as a refused move and a list in the wrong order.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.ops: list[tuple] = []
        self.rows: list[str] = []
        self.refused: list[tuple] = []

    def set(self, value: object) -> None:
        self.ops.append(("set", value))

    def append(self, node: object) -> None:
        row_id = getattr(node, "id", node)
        self.ops.append(("append", row_id))
        self.rows.append(row_id)

    def remove(self, row_id: str) -> None:
        self.ops.append(("remove", row_id))
        self.rows.remove(row_id)

    def move(self, row_id: str, position: int) -> None:
        self.ops.append(("move", row_id, position))
        spot = _append_index(len(self.rows) - 1, position)
        if row_id not in self.rows or spot is None:
            self.refused.append((row_id, position))
            return
        self.rows.remove(row_id)
        self.rows.insert(spot, row_id)


class FakeCtx:
    """The part of a delivery the adapters use: named slots."""

    def __init__(self) -> None:
        self.slots: dict[str, FakeSlot] = {}

    def slot(self, name: str) -> FakeSlot:
        return self.slots.setdefault(name, FakeSlot(name))


class Node:
    def __init__(self, row_id: str, text: str = "") -> None:
        self.id = row_id
        self.text = text


class TestSignal(unittest.TestCase):
    def test_a_reader_runs_now_and_again_when_the_value_changes(self) -> None:
        count = signals.Signal(0)
        seen: list[int] = []
        signals.effect(lambda: seen.append(count.value))

        count.value = 1
        count.value = 2

        self.assertEqual(seen, [0, 1, 2])

    def test_an_equal_write_is_not_a_change(self) -> None:
        count = signals.Signal(0)
        seen: list[int] = []
        signals.effect(lambda: seen.append(count.value))

        count.value = 0

        self.assertEqual(seen, [0], "writing the same value is not news")

    def test_a_reader_only_hears_what_it_read(self) -> None:
        left, right = signals.Signal(0), signals.Signal(0)
        seen: list[int] = []
        signals.effect(lambda: seen.append(left.value))

        right.value = 99

        self.assertEqual(seen, [0])

    def test_an_effect_stops_depending_on_what_it_stopped_reading(self) -> None:
        flag, left, right = signals.Signal(True), signals.Signal("l"), signals.Signal("r")
        seen: list[str] = []
        signals.effect(lambda: seen.append(left.value if flag.value else right.value))

        flag.value = False  # the second run reads `right`, not `left`
        left.value = "l2"
        self.assertEqual(seen, ["l", "r"], "a stale dependency must not wake the reader")

        right.value = "r2"
        self.assertEqual(seen, ["l", "r", "r2"])


class TestComputed(unittest.TestCase):
    def test_it_computes_once_and_caches(self) -> None:
        base = signals.Signal(1)
        runs: list[int] = []

        def double() -> int:
            runs.append(base.value)
            return base.value * 2

        twice = signals.Computed(double)
        self.assertEqual((twice.value, twice.value), (2, 2))
        self.assertEqual(runs, [1], "a clean computed does not recompute")

        base.value = 2
        self.assertEqual(twice.value, 4)
        self.assertEqual(runs, [1, 2])

    def test_two_readers_of_one_signal_hear_it_once_each(self) -> None:
        base = signals.Signal(1)
        summed = signals.Computed(lambda: base.value + 1)
        seen: list[int] = []
        # The same signal reached by two paths: through `base` and through `summed`.
        signals.effect(lambda: seen.append(base.value + summed.value))

        base.value = 2

        # 1 + (1+1) = 3, then 2 + (2+1) = 5: one write, one run.
        self.assertEqual(seen, [3, 5], "one write, one run")

    def test_a_computed_that_comes_out_the_same_does_not_wake_its_reader(self) -> None:
        rows = signals.Signal([1, 2, 3])
        evens = signals.Computed(lambda: [n for n in rows.value if n % 2 == 0])
        seen: list[list[int]] = []
        signals.effect(lambda: seen.append(evens.value))

        rows.value = [1, 2, 3, 4]
        self.assertEqual(seen, [[2], [2, 4]])

        rows.value = [9, 2, 7, 4]  # same evens, different list: the effect must not run
        self.assertEqual(seen, [[2], [2, 4]], "the answer did not change, so nobody is told")


class TestBatch(unittest.TestCase):
    def test_a_batch_writes_the_page_once(self) -> None:
        left, right = signals.Signal(0), signals.Signal(0)
        seen: list[tuple[int, int]] = []
        signals.effect(lambda: seen.append((left.value, right.value)))

        with signals.batch():
            left.value = 1
            right.value = 2

        self.assertEqual(seen, [(0, 0), (1, 2)], "one round, one run")

    def test_nested_batches_still_run_once(self) -> None:
        count = signals.Signal(0)
        seen: list[int] = []
        signals.effect(lambda: seen.append(count.value))

        with signals.batch():
            with signals.batch():
                count.value = 1
            count.value = 2

        self.assertEqual(seen, [0, 2])


class TestTheAdapters(unittest.TestCase):
    def test_bound_owns_a_slot(self) -> None:
        ctx = FakeCtx()
        count = signals.bound(ctx, "counter.count", 0)

        self.assertEqual(ctx.slots["counter.count"].ops, [("set", 0)], "the first value seeds the slot")
        count.value = 3
        self.assertEqual(ctx.slots["counter.count"].ops, [("set", 0), ("set", 3)])

    def test_into_mirrors_a_computed(self) -> None:
        ctx, step = FakeCtx(), signals.Signal(1)
        signals.into(ctx, "counter.hint", signals.Computed(lambda: f"step {step.value}"))

        step.value = 2

        self.assertEqual(
            ctx.slots["counter.hint"].ops, [("set", "step 1"), ("set", "step 2")], "once now, once per change"
        )

    def test_keyed_moves_a_row_that_moved_to_the_head(self) -> None:
        ctx, rows = FakeCtx(), signals.Signal([])
        signals.keyed(ctx, "log", rows, lambda item, row_id: Node(row_id, item))
        rows.value = [("a", "1"), ("b", "2"), ("c", "3")]
        ctx.slots["log"].ops.clear()

        rows.value = [("c", "3"), ("a", "1"), ("b", "2")]

        slot = ctx.slots["log"]
        self.assertEqual(slot.ops, [("move", "c", -1)], "one move, and it is the row that left its place")
        self.assertEqual(slot.rows, ["c", "a", "b"])
        self.assertEqual(slot.refused, [])

    def test_keyed_leaves_the_rows_that_stayed_in_order(self) -> None:
        ctx, rows = FakeCtx(), signals.Signal([])
        signals.keyed(ctx, "log", rows, lambda item, row_id: Node(row_id, item))
        rows.value = [("a", ""), ("b", ""), ("c", ""), ("d", "")]
        ctx.slots["log"].ops.clear()

        rows.value = [("a", ""), ("c", ""), ("b", ""), ("d", "")]

        slot = ctx.slots["log"]
        self.assertEqual(len(slot.ops), 1, "one of the two rows moved, not both")
        self.assertEqual(slot.ops[0][0], "move")
        self.assertIn(slot.ops[0][1], {"b", "c"}, "either swap is one move; the other three stayed")
        self.assertEqual(slot.rows, ["a", "c", "b", "d"])

    def test_keyed_rotates_with_one_move(self) -> None:
        ctx, rows = FakeCtx(), signals.Signal([])
        signals.keyed(ctx, "log", rows, lambda item, row_id: Node(row_id, item))
        rows.value = [("a", ""), ("b", ""), ("c", ""), ("d", "")]
        ctx.slots["log"].ops.clear()

        rows.value = [("b", ""), ("c", ""), ("d", ""), ("a", "")]

        slot = ctx.slots["log"]
        self.assertEqual(slot.ops, [("move", "a", 0)], "a rotation is one row going to the end")
        self.assertEqual(slot.rows, ["b", "c", "d", "a"])

    def test_keyed_adds_removes_and_reorders_in_one_pass(self) -> None:
        ctx, rows = FakeCtx(), signals.Signal([])
        signals.keyed(ctx, "log", rows, lambda item, row_id: Node(row_id, item))
        rows.value = [("a", ""), ("b", ""), ("c", "")]
        ctx.slots["log"].ops.clear()

        rows.value = [("c", ""), ("x", ""), ("a", "")]

        slot = ctx.slots["log"]
        self.assertEqual(slot.ops, [("remove", "b"), ("append", "x"), ("move", "a", 0)])
        self.assertEqual(slot.rows, ["c", "x", "a"])

    def test_keyed_writes_nothing_when_the_order_did_not_change(self) -> None:
        ctx, rows = FakeCtx(), signals.Signal([])
        signals.keyed(ctx, "log", rows, lambda item, row_id: Node(row_id, item))
        rows.value = [("a", ""), ("b", "")]
        ctx.slots["log"].ops.clear()

        rows.value = [("a", ""), ("b", "")]

        self.assertEqual(ctx.slots["log"].ops, [], "the same table in the same order is not a change")

    def test_keyed_appends_what_is_new_and_removes_what_is_gone(self) -> None:
        ctx, rows = FakeCtx(), signals.Signal([])
        signals.keyed(ctx, "log", rows, lambda item, row_id: Node(row_id, item))

        rows.value = [("a", "first"), ("b", "second")]
        rows.value = [("b", "second"), ("c", "third")]

        self.assertEqual(
            ctx.slots["log"].ops,
            [("append", "a"), ("append", "b"), ("remove", "a"), ("append", "c")],
            "a row that is still there is not touched",
        )


if __name__ == "__main__":
    unittest.main()