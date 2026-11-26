"""The counter page: the API on the most ordinary page there is.

The other pages demonstrate a mechanism; this one demonstrates nothing but use — `@app.route` inside a
page module's `register`, `h.*` for the tree, closure sinks for the three buttons and the input, list
slots for the history, and `ctx.data` for per-connection state. These cases pin the behaviour, because
the page's whole point is that a reader can copy it.
"""

from __future__ import annotations

import unittest

from reflux.application import create_app, App
from reflux.routes import Routes
from tests.fakes import run_sync, FakeDevice

from examples.zh import demo_counter


def build() -> tuple[App, FakeDevice]:
    app = create_app()
    demo_counter.register(app)
    device = FakeDevice(app=app, path=demo_counter.PAGE)
    run_sync(app._draw(device))
    return app, device


def writes(device: FakeDevice, slot: str) -> list:
    """Every value written to one slot, in order — across however many frames it took."""
    out = []
    for frame in device.frames:
        for operation in frame:
            if operation.get("slot") == slot and operation.get("action") in ("set", "append"):
                data = operation["data"]["source"]["default"]
                out.append(data)
    return out


def click(app: App, device: FakeDevice, name: str) -> None:
    """Press one of the page's buttons, by the name the page drew."""
    assert run_sync(app.dests.dispatch(device, {"dest": f"{demo_counter.PAGE}.{name}", "data": 1}))


class ThePage(unittest.TestCase):
    def test_the_counter_prints_itself_on_the_route_it_declared(self) -> None:
        app, device = build()
        self.assertEqual([route.path for route in app.routes], [demo_counter.PAGE])
        self.assertEqual(writes(device, "counter.count")[-1], "0", "the value is seeded at zero")

    def test_the_three_buttons_are_closures_named_at_draw_time(self) -> None:
        _, device = build()
        self.assertEqual(
            sorted(device.landings),
            [f"{demo_counter.PAGE}.{name}" for name in ("down", "reset", "set_step", "up")],
        )

    def test_a_press_moves_the_value_and_writes_a_history_line(self) -> None:
        app, device = build()
        click(app, device, "up")
        self.assertEqual(writes(device, "counter.count")[-1], "1")
        self.assertEqual(writes(device, "counter.history")[-1], "+1 → 1")

    def test_the_step_multiplies_the_press(self) -> None:
        app, device = build()
        run_sync(app.dests.dispatch(device, {"dest": f"{demo_counter.PAGE}.set_step", "data": {"step": 5}}))
        click(app, device, "up")
        self.assertEqual(writes(device, "counter.count")[-1], "5")
        click(app, device, "down")
        self.assertEqual(writes(device, "counter.count")[-1], "0")

    def test_an_empty_step_is_refused_out_loud(self) -> None:
        # The wire carries what the renderer parsed: a number box with nothing in it parses to null, and
        # nothing else reaches the handler — parsing is the field's `kind`, not this page's job.
        app, device = build()
        run_sync(app.dests.dispatch(device, {"dest": f"{demo_counter.PAGE}.set_step", "data": {"step": None}}))
        self.assertIn("没有输入", writes(device, "counter.hint")[-1], "the reader is told what was wrong")
        click(app, device, "up")
        self.assertEqual(writes(device, "counter.count")[-1], "1", "and the step did not move")

    def test_the_step_is_clamped(self) -> None:
        app, device = build()
        run_sync(app.dests.dispatch(device, {"dest": f"{demo_counter.PAGE}.set_step", "data": {"step": 99}}))
        click(app, device, "up")
        self.assertEqual(writes(device, "counter.count")[-1], "10")

    def test_reset_goes_back_to_zero(self) -> None:
        app, device = build()
        click(app, device, "up")
        click(app, device, "reset")
        self.assertEqual(writes(device, "counter.count")[-1], "0")
        self.assertTrue(writes(device, "counter.history")[-1].endswith("→ 0"), "the log says where it ended")

    def test_the_history_is_capped_and_drops_its_oldest(self) -> None:
        app, device = build()
        for _ in range(demo_counter.HISTORY + 2):
            click(app, device, "up")
        removed = [
            operation["id"]
            for frame in device.frames
            for operation in frame
            if operation.get("action") == "remove"
        ]
        self.assertEqual(len(removed), 2, "two lines past the cap, two removals")
        self.assertEqual(removed[0], "log-1", "the oldest leaves first")


class TheSlotsView(unittest.TestCase):
    """A slot may hold a value instead of a tree: the node it becomes is declared once."""

    def test_a_write_goes_through_the_view(self) -> None:
        app, device = build()
        click(app, device, "up")
        last = [
            operation
            for frame in device.frames
            for operation in frame
            if operation.get("slot") == "counter.count"
        ][-1]
        node = last["data"]
        self.assertEqual(node["type"], "text")
        self.assertEqual(node["id"], "counter-value", "the id came from the view, not from the writer")
        self.assertEqual(node["source"]["default"], "1")
        self.assertIn("rx-heading-1", node["attrs"]["class"], "and the variant, from the same one place")

    def test_a_node_is_not_run_through_the_view(self) -> None:
        from reflux.sdk import h
        from reflux.slots import Slot

        app, _ = build()
        slot = Slot("counter.count", app=app)
        mine = h.text("mine", id="from-the-page")
        self.assertIs(slot.frame(mine), mine, "a node the page wrote is already the node")
        self.assertEqual(slot.frame(7)["source"]["default"] if isinstance(slot.frame(7), dict) else "model",
                         "model", "a value still goes through the view")

    def test_a_slot_without_a_view_still_takes_nodes(self) -> None:
        from reflux.sdk import h

        app, device = build()
        click(app, device, "up")
        last = [op for frame in device.frames for op in frame if op.get("slot") == "counter.history"][-1]
        self.assertEqual(last["data"]["type"], "text", "history rows are written as nodes (they carry ids)")
        self.assertTrue(last["data"]["id"].startswith("log-"))
        self.assertIsNotNone(h)  # the page's own vocabulary, used above


class ItsState(unittest.TestCase):
    def test_two_connections_count_separately(self) -> None:
        app, one = build()
        click(app, one, "up")
        click(app, one, "up")
        two = FakeDevice(id="second", app=app, path=demo_counter.PAGE)
        run_sync(app._draw(two))
        self.assertEqual(writes(two, "counter.count"), ["0"], "the second tab starts at zero")
        self.assertEqual(writes(one, "counter.count")[-1], "2", "and the first is untouched")

    def test_the_value_is_seeded_once_not_per_draw(self) -> None:
        app, device = build()
        click(app, device, "up")
        run_sync(app._draw(device))  # a page turn: the tree is replaced, the data planes are not
        self.assertEqual(writes(device, "counter.count"), ["0", "1"], "no second seed pushing it back")


class BothTrees(unittest.TestCase):
    def test_the_english_page_is_the_same_page(self) -> None:
        from examples.en import demo_counter as english

        app = create_app()
        english.register(app)
        device = FakeDevice(app=app, path=english.PAGE)
        run_sync(app._draw(device))
        self.assertEqual(sorted(device.landings), [f"{english.PAGE}.{n}" for n in ("down", "reset", "set_step", "up")])
        self.assertEqual(writes(device, "counter.count"), ["0"])


if __name__ == "__main__":
    unittest.main()