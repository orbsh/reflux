"""Slots: the name and its verbs, one frame each, and the turn that holds several together."""

from __future__ import annotations

import unittest

from reflux import App
from reflux.sdk import builders as b
from reflux.slots import Slot, Slots

from tests.fakes import FakeDevice


class TheSlot(unittest.TestCase):
    def setUp(self) -> None:
        self.app = App()
        self.device = FakeDevice()
        self.ctx = self.app.context(self.device)

    def test_a_slot_is_its_name_and_says_so(self) -> None:
        status = self.ctx.slot("status")
        self.assertEqual(status.name, "status")
        self.assertEqual(status, Slot(self.ctx, "status"))  # two handles, one plane
        self.assertEqual(len({status, self.ctx.slot["status"]}), 1)  # hashable, equal, not duplicated

    def test_the_three_forms_are_one_slot(self) -> None:
        self.assertEqual(self.ctx.slot("chat/status").name, self.ctx.slot["chat/status"].name)
        self.assertEqual(self.ctx.slot["status"].name, self.ctx.slot.status.name)  # the Protocol's form

    def test_a_path_is_carried_through(self) -> None:
        # Hierarchical names are allowed and nothing reads the `/` yet: the name goes out as written.
        self.ctx.slot("chat/status").set(b.text("就绪"))
        self.assertEqual(self.device.frames[0][0]["slot"], "chat/status")

    def test_the_layout_root_is_not_a_slot(self) -> None:
        """`slot: ""` addresses the page, and the page has its own verb: `ctx.page(...)`.

        A slot with no name would be a second way to say "replace everything", right next to the one
        that also knows about the shell and the `routes` slot — so it is refused, not aliased.
        """
        with self.assertRaises(ValueError):
            self.ctx.slot("")

    def test_each_verb_is_one_frame(self) -> None:
        slot = self.ctx.slot["messages"]
        slot.set(b.text("here"))
        slot.append(b.text("row"))
        slot.patch("/bind/value/default", "more", op="append")
        slot.remove("row-1")
        self.assertEqual(
            [(frame[0]["action"], frame[0]["slot"]) for frame in self.device.frames],
            [("set", "messages"), ("append", "messages"), ("patch", "messages"), ("remove", "messages")],
        )
        self.assertEqual(len(self.device.frames), 4, "each verb is one frame on its own")

    def test_a_slot_stands_for_its_name_in_a_node(self) -> None:
        node = b.text(source=self.ctx.slot["status"])
        self.assertEqual(node.bind["value"].source, "status")

    def test_a_declaration_is_recorded_on_the_app(self) -> None:
        self.ctx.slot["status"].set(b.text("x"))
        self.assertEqual(self.app.slots, {"status"})

        self.ctx.slot("chat/reply").set(b.text("y"))
        self.assertEqual(self.app.slots, {"status", "chat/reply"})


class TheTurn(unittest.TestCase):
    """A turn is what one client sees at once: several writes, one frame."""

    def setUp(self) -> None:
        self.app = App()
        self.device = FakeDevice()
        self.ctx = self.app.context(self.device)

    def test_writes_inside_a_turn_leave_as_one_frame(self) -> None:
        slots = self.ctx.slot
        with self.ctx.turn():
            slots.messages.append(b.text("row"))
            slots.status.set(b.text("就绪"))
        self.assertEqual(len(self.device.frames), 1)
        self.assertEqual([op["action"] for op in self.device.frames[0]], ["append", "set"])

    def test_outside_a_turn_each_write_is_its_own_frame(self) -> None:
        slots = self.ctx.slot
        slots.messages.append(b.text("row"))
        slots.status.set(b.text("就绪"))
        self.assertEqual(len(self.device.frames), 2)

    def test_an_empty_turn_sends_nothing(self) -> None:
        with self.ctx.turn():
            pass
        self.assertEqual(self.device.frames, [])


class TheGroup(unittest.TestCase):
    def test_a_group_without_an_app_still_hands_out_slots(self) -> None:
        # `Context(app=None, …)` is what a test builds when it only reads names.
        group = Slots(ctx=_Bare())
        self.assertEqual(group["status"].name, "status")
        self.assertEqual(group.status.name, "status")


class _Bare:
    """A delivery's shape without an app: `Slots` reads `app` and `emit`, nothing else."""

    app = None

    def emit(self, *operations: dict) -> None:  # pragma: no cover - not reached in these tests
        raise AssertionError("nothing should be sent")


if __name__ == "__main__":
    unittest.main()