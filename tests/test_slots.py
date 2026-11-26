"""Slots: the name and its verbs, one frame each, and the turn that holds several together."""

from __future__ import annotations

import unittest

from reflux import App
from reflux import signals
from reflux.sdk import h
from reflux.sdk import dump
from reflux.slots import Slot, Slots
from reflux.application import create_app

from tests.fakes import FakeDevice


class TheSlot(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        self.device = FakeDevice()
        self.ctx = self.app.context(self.device)

    def test_a_slot_is_its_name_and_says_so(self) -> None:
        status = self.ctx.slot("status")
        self.assertEqual(status.name, "status")
        self.assertEqual(status, Slot("status", self.ctx))  # two handles, one plane
        self.assertEqual(len({status, (self.ctx.slot / "status")}), 1)  # hashable, equal, not duplicated

    def test_a_name_nests(self) -> None:
        """`ctx.slot / "go" / "dashboard"` is the name "go.dashboard" — a dest reads off the same view."""
        self.assertEqual((self.ctx.slot / "go" / "dashboard").name, "go.dashboard")
        self.assertEqual((self.ctx.slot / "chat" / "send").name, "chat.send", "one `/` per segment")
        self.assertEqual(self.ctx.slot / "go" / "dashboard", self.ctx.slot("go.dashboard"))

    def test_a_child_carries_the_delivery(self) -> None:
        (self.ctx.slot / "chat" / "status").set(h.text("x"))
        self.assertEqual(self.device.frames[0][0]["slot"], "chat.status")

    def test_nesting_keeps_the_verbs_verbs(self) -> None:
        for verb in ("set", "append", "patch", "remove"):
            self.assertTrue(callable(getattr(self.ctx.slot / "chat", verb)))

    def test_a_name_ending_in_a_verb_is_still_just_a_name(self) -> None:
        """`remove` is a verb on the handle; a slot called `remove` is built with `/` and never collides."""
        self.assertEqual((self.ctx.slot / "row" / "remove").name, "row.remove")
        self.assertTrue(callable((self.ctx.slot / "row").remove), "the verb, not a name")

    def test_the_two_forms_are_one_slot(self) -> None:
        self.assertEqual(self.ctx.slot("chat/status").name, (self.ctx.slot / "chat/status").name)
        self.assertEqual((self.ctx.slot / "status").name, self.ctx.slot("status").name)

    def test_a_path_is_carried_through(self) -> None:
        # Hierarchical names are allowed and nothing reads the `/` yet: the name goes out as written.
        self.ctx.slot("chat/status").set(h.text("就绪"))
        self.assertEqual(self.device.frames[0][0]["slot"], "chat/status")

    def test_the_layout_root_is_not_a_slot(self) -> None:
        """`slot: ""` addresses the page, and the page has its own verb: `ctx.page(...)`.

        A slot with no name would be a second way to say "replace everything", right next to the one
        that also knows about the shell and the `routes` slot — so it is refused, not aliased.
        """
        with self.assertRaises(ValueError):
            self.ctx.slot("")

    def test_each_verb_is_one_frame(self) -> None:
        slot = (self.ctx.slot / "messages")
        slot.set(h.text("here"))
        slot.append(h.text("row"))
        slot.patch("/bind/value/default", "more", op="append")
        slot.remove("row-1")
        self.assertEqual(
            [(frame[0]["action"], frame[0]["slot"]) for frame in self.device.frames],
            [("set", "messages"), ("append", "messages"), ("patch", "messages"), ("remove", "messages")],
        )
        self.assertEqual(len(self.device.frames), 4, "each verb is one frame on its own")

    def test_a_slot_stands_for_its_name_in_a_node(self) -> None:
        # A handle reaches the wire as its name in the `Bind` the channel carries (ADR 0031 §1–2).
        node = h.text(source=(self.ctx.slot / "status"))
        assert node.source is not None  # optional on the wire, never on a node built with one
        self.assertEqual(node.source.slot, "status")

    def test_a_declaration_is_recorded_on_the_app(self) -> None:
        (self.ctx.slot / "status").set(h.text("x"))
        self.assertEqual(self.app.declared, {"status"})

        self.ctx.slot("chat/reply").set(h.text("y"))
        self.assertEqual(self.app.declared, {"status", "chat/reply"})


class TheValue(unittest.TestCase):
    """A signal a page declares: one per name per connection, seeded once, read and written on the signal."""

    def setUp(self) -> None:
        self.app = create_app()
        self.device = FakeDevice()
        self.ctx = self.app.context(self.device)

    def test_the_slash_builds_a_name_and_leaves_the_dot_to_the_verbs(self) -> None:
        self.assertEqual((self.ctx.slot / "counter" / "count").name, "counter.count")
        self.assertEqual((self.ctx.slot / "chat" / "remove").name, "chat.remove", "a name, not a verb")
        self.assertEqual(self.ctx.slot / "a" / "b", self.ctx.slot("a.b"), "one plane, two spellings")
        with self.assertRaises(ValueError):
            self.ctx.slot / ""

    def test_a_signal_seeds_the_slot_once_then_reads_and_writes_the_value(self) -> None:
        with signals.drawing(self.ctx):  # a page's draw: the first write waits for the view
            count = (
                signals.Signal(0)
                .bind(self.ctx.slot / "counter" / "count")
                .view(lambda value: h.text(str(value)))
            )
        seed = self.device.frames[0][0]
        self.assertEqual((seed["action"], seed["slot"]), ("set", "counter.count"))
        self.assertEqual(seed["data"]["source"]["default"], "0", "the seed went through the view")
        self.assertEqual(count.value, 0)

        count.value = 3

        self.assertEqual(self.device.frames[1][0]["data"]["source"]["default"], "3", "a write is one frame")
        self.assertEqual(count.value, 3)

    def test_a_value_with_no_view_is_refused_at_the_end_of_the_draw(self) -> None:
        with self.assertRaises(ValueError) as caught:
            with signals.drawing(self.ctx):
                signals.Signal(0).bind(self.ctx.slot / "raw")
        self.assertIn("accrete node", str(caught.exception), "the write says what it could not frame")

    def test_drawing_again_hands_back_the_same_signal(self) -> None:
        draw = lambda: signals.Signal(0).bind(self.ctx.slot / "counter" / "count").view(  # noqa: E731
            lambda value: h.text(str(value))
        )
        with signals.drawing(self.ctx):
            first = draw()
        first.value = 5
        sent = len(self.device.frames)

        with signals.drawing(self.ctx):
            again = draw()

        self.assertIs(again, first, "the page's second draw keeps the same signal")
        self.assertEqual(again.value, 5)
        self.assertEqual(len(self.device.frames), sent, "and seeds nothing")

    def test_a_slot_has_no_value_of_its_own(self) -> None:
        slot = self.ctx.slot("counter.count")
        self.assertFalse(hasattr(type(slot), "value"), "a value lives on a signal, not on the address")

    def test_a_computed_is_mirrored_and_read_only(self) -> None:
        step = signals.Signal(1)
        with signals.drawing(self.ctx):
            hint = (
                signals.Computed(lambda: f"step {step.value}")
                .bind(self.ctx.slot / "counter" / "hint")
                .view(lambda value: h.text(value))
            )
        self.assertEqual(hint.value, "step 1")

        step.value = 2

        self.assertEqual(hint.value, "step 2")
        self.assertEqual(self.device.frames[-1][0]["data"]["source"]["default"], "step 2")
        with self.assertRaises(AttributeError):
            hint.value = "mine"  # type: ignore[misc]

    def test_a_keyed_signal_owns_the_rows(self) -> None:
        with signals.drawing(self.ctx):
            log = (
                signals.Signal([])
                .keyed(lambda item, row_id: h.text(item, id=row_id))
                .bind(self.ctx.slot / "log")
            )

        log.value = [("a", "1"), ("b", "2")]
        self.assertEqual(
            [operation["action"] for frame in self.device.frames for operation in frame],
            ["append", "append"],
        )

        log.value = [("b", "2"), ("a", "1")]
        self.assertEqual(self.device.frames[-1][0]["action"], "move", "an order change is a move")
        self.assertEqual(log.value, [("b", "2"), ("a", "1")], "the signal is the rows")

    def test_the_chain_declares_the_view_and_stays_on_the_signal(self) -> None:
        with signals.drawing(self.ctx):
            count = (
                signals.Signal(0)
                .bind(self.ctx.slot / "chain" / "count")
                .view(lambda value: h.text(str(value), id="counter-value"))
            )
        self.assertEqual(count.slot.name, "chain.count", "the signal knows where it writes")

        count.value = 3

        node = self.device.frames[-1][0]["data"]
        self.assertEqual(node["type"], "text", "a value became a node through the view")
        self.assertEqual(node["id"], "counter-value")


class TheAddressesInNodes(unittest.TestCase):
    """`source=` and `sink=` take handles (ADR 0031 §2); a bare value means what each side can hold.

    A read has a constant to fall back on (for the types the profile gives one), so a bare value
    there is that constant, never a name. A write has nothing to default to, so a bare string there
    is its `dest` — the same string, read as the one thing it could mean.
    """

    def setUp(self) -> None:
        self.app = create_app()
        self.ctx = self.app.context(FakeDevice())

    def test_a_source_handle_reaches_the_wire_as_its_name(self) -> None:
        self.assertEqual(h.text(source=(self.ctx.slot / "status")).source.slot, "status")

    def test_a_sink_handle_reaches_the_wire_as_its_name(self) -> None:
        node = h.loom(h.button("send"), sink=self.ctx.slot("chat.send"))
        self.assertEqual(node.sink.dest, "chat.send")

    def test_a_bare_value_is_a_constant_on_a_read_and_a_name_on_a_write(self) -> None:
        self.assertEqual(dump(h.text(source="status"))["source"], {"default": "status", "scope": "remote"})
        self.assertEqual(dump(h.loom(sink="chat.send"))["sink"], {"dest": "chat.send", "scope": "remote"})

    def test_a_read_with_no_constant_refuses_a_bare_string(self) -> None:
        # A `tiles` has no `default` in the profile: a bare value there is neither a constant nor a
        # name, so the builder refuses instead of guessing which one was meant.
        for build in (lambda: h.tiles(source="rows"), lambda: h.frame(source="rows")):
            with self.assertRaises(TypeError):
                build()

    def test_the_message_says_where_the_handle_comes_from(self) -> None:
        with self.assertRaises(TypeError) as caught:
            h.tiles(source="rows")
        self.assertIn("ctx.slot('rows')", str(caught.exception))

    def test_a_slot_with_no_delivery_can_name_but_not_write(self) -> None:
        handle = Slot("rows")
        self.assertEqual(h.tiles(source=handle).source.slot, "rows")
        with self.assertRaises(RuntimeError):
            handle.append(h.text("row"))


class TheTurn(unittest.TestCase):
    """A turn is what one client sees at once: several writes, one frame."""

    def setUp(self) -> None:
        self.app = create_app()
        self.device = FakeDevice()
        self.ctx = self.app.context(self.device)

    def test_writes_inside_a_turn_leave_as_one_frame(self) -> None:
        slots = self.ctx.slot
        with self.ctx.turn():
            (slots / "messages").append(h.text("row"))
            (slots / "status").set(h.text("就绪"))
        self.assertEqual(len(self.device.frames), 1)
        self.assertEqual([op["action"] for op in self.device.frames[0]], ["append", "set"])

    def test_outside_a_turn_each_write_is_its_own_frame(self) -> None:
        slots = self.ctx.slot
        (slots / "messages").append(h.text("row"))
        (slots / "status").set(h.text("就绪"))
        self.assertEqual(len(self.device.frames), 2)

    def test_an_empty_turn_sends_nothing(self) -> None:
        with self.ctx.turn():
            pass
        self.assertEqual(self.device.frames, [])


class TheGroup(unittest.TestCase):
    def test_a_group_without_an_app_still_hands_out_slots(self) -> None:
        # `Context(app=None, …)` is what a test builds when it only reads names.
        group = Slots(ctx=_Bare())
        self.assertEqual((group / "status").name, "status")
        self.assertEqual((group / "chat" / "send").name, "chat.send")


class _Bare:
    """A delivery's shape without an app: `Slots` reads `app` and `emit`, nothing else."""

    app = None

    def emit(self, *operations: dict) -> None:  # pragma: no cover - not reached in these tests
        raise AssertionError("nothing should be sent")


if __name__ == "__main__":
    unittest.main()