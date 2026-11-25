"""A closure as a landing point: `sink=add_row` on the loom its button submits, and the name the
wire gets instead.

Two kinds of landing point, one wire. The registry's (`@app.on(slot)`) is a name that exists before
any page is drawn — the answer to "one slot, several sources". The closure's is sugar for the common
case, a page and the handler it answers with written as one thought:

    def add_row(value):                 # the value, not a frame
        slots.rows.append(row(...))

    h.loom(h.button("Add a row"), sink=add_row, submit=["button"])

The framework names it at draw time (`<path>.<function>`), registers it on the device being drawn, and
replaces the draw's table on the next turn. These cases pin that contract.
"""

from __future__ import annotations

import unittest

from reflux import Auth, wire
from reflux.app import App, gated
from reflux.routes import Routes
from reflux.sdk import h
from tests.fakes import FakeDevice


def sinks(node: object, out: list) -> list:
    """Every sink address in a drawn tree, in order."""
    if isinstance(node, dict):
        if "sink" in node:
            out.append(node["sink"])
        for kid in node.get("children") or []:
            sinks(kid, out)
    elif isinstance(node, (list, tuple)):
        for kid in node:
            sinks(kid, out)
    return out


def drawn_page(device: FakeDevice) -> dict:
    """The last `set routes` the device was sent — the page, as the client receives it."""
    for frame in reversed(device.frames):
        for operation in frame:
            if operation.get("action") == "set" and operation.get("slot") == "routes":
                return operation["data"]
    raise AssertionError("no page was drawn")


class AClosureIsALandingPoint(unittest.TestCase):
    def setUp(self) -> None:
        self.calls: list = []
        self.app = App(routes=Routes())

        @self.app.page("/", title="test")
        def home(ctx, match):
            slots = ctx.slot

            def add(value):
                self.calls.append(("add", value))
                slots.rows.append(h.text(f"row {value}"))

            ctx.page(
                h.frame(
                    h.text("t"),
                    h.loom(h.button("Add a row"), sink=add, submit=["button"], id="add-row"),
                    id="root",
                )
            )

        self.device = FakeDevice(app=self.app)
        self.app._draw(self.device)

    def test_the_frame_carries_a_name_not_a_function(self) -> None:
        addresses = sinks(drawn_page(self.device), [])
        self.assertEqual([a["dest"] for a in addresses], ["/.add"])

    def test_the_name_resolves_to_the_closure(self) -> None:
        self.assertTrue(self.app.dests.dispatch(self.device, {"dest": "/.add", "data": 7}))
        self.assertEqual(self.calls, [("add", 7)])

    def test_the_closure_gets_the_value_and_writes_its_own_slots(self) -> None:
        self.app.dests.dispatch(self.device, {"dest": "/.add", "data": 3})
        written = [op for frame in self.device.frames for op in frame if op.get("slot") == "rows"]
        self.assertEqual(written[-1]["data"]["source"]["default"], "row 3")

    def test_a_name_the_page_did_not_draw_is_refused(self) -> None:
        self.assertFalse(self.app.dests.dispatch(self.device, {"dest": "/.nope", "data": 1}))


class TheTableIsOneDraws(unittest.TestCase):
    def test_one_closure_bound_twice_is_one_name(self) -> None:
        # A loom carries the sink its button sends with, so the same author-written handler lands
        # on two nodes. That is one landing point, not two.
        app = App(routes=Routes())

        def pick(value):
            pass

        @app.page("/", title="t")
        def home(ctx, match):
            ctx.page(
                h.frame(
                    h.loom(h.button("a"), sink=pick, submit=["button"], id="a"),
                    h.loom(h.button("b"), sink=pick, submit=["button"], id="b"),
                    id="r",
                )
            )

        device = FakeDevice(app=app)
        app._draw(device)
        self.assertEqual([a["dest"] for a in sinks(drawn_page(device), [])], ["/.pick", "/.pick"])

    def test_two_different_closures_are_two_names(self) -> None:
        # A per-row handler is a different closure per row: that is what a name per instance buys.
        app = App(routes=Routes())
        ids = ["a", "b"]

        @app.page("/", title="t")
        def home(ctx, match):
            def pick(value):
                pass

            buttons = []
            for name in ids:
                def hit(value, name=name):
                    pass

                buttons.append(h.loom(h.button(name), sink=hit, submit=["button"], id=name))
            ctx.page(h.frame(*buttons, id="r"))

        device = FakeDevice(app=app)
        app._draw(device)
        self.assertEqual([a["dest"] for a in sinks(drawn_page(device), [])], ["/.hit", "/.hit#2"])

    def test_a_page_turn_replaces_the_table(self) -> None:
        app = App(routes=Routes())

        def hit(value):
            pass

        @app.page("/", title="t")
        def home(ctx, match):
            ctx.page(h.frame(h.loom(h.button("x"), sink=hit, submit=["button"], id="x"), id="r"))

        device = FakeDevice(app=app)
        app._draw(device)
        before = sorted(device.landings)
        app._draw(device)
        self.assertEqual(sorted(device.landings), before, "the same page draws the same names")
        app.dests.dispatch(device, {"dest": before[0], "data": 1})
        self.assertTrue(before)

    def test_each_device_has_its_own_closures(self) -> None:
        app = App(routes=Routes())
        seen: list = []

        @app.page("/", title="t")
        def home(ctx, match):
            who = ctx.device.id

            def hit(value):
                seen.append((who, value))

            ctx.page(h.frame(h.loom(h.button("x"), sink=hit, submit=["button"], id="x"), id="r"))

        one, two = FakeDevice(id="one", app=app), FakeDevice(id="two", app=app)
        app._draw(one)
        app._draw(two)
        self.assertEqual(sorted(one.landings), sorted(two.landings), "the same names, per device")
        app.dests.dispatch(one, {"dest": "/.hit", "data": "a"})
        app.dests.dispatch(two, {"dest": "/.hit", "data": "b"})
        self.assertEqual(seen, [("one", "a"), ("two", "b")])


class GatedLandings(unittest.TestCase):
    def setUp(self) -> None:
        self.calls: list = []
        self.app = App(
            routes=Routes(),
            auth=Auth(verify=lambda ctx, credentials, mode: "user-ada"),
        )

        @self.app.page("/", title="t")
        def home(ctx, match):
            def secret(value):
                self.calls.append(value)

            ctx.page(h.frame(h.loom(h.button("secret"), sink=gated(secret), submit=["button"], id="s"), id="r"))

        self.device = FakeDevice(app=self.app)
        self.app._draw(self.device)

    def test_an_anonymous_click_never_reaches_the_closure(self) -> None:
        # The two lines the server runs for every uplink frame: the gate, then the dispatch.
        frame = {"dest": "/.secret", "data": "x"}
        refused = self.app._refuse_gated(self.device, frame)
        if not refused:
            self.app.dests.dispatch(self.device, frame)
        self.assertTrue(refused)
        self.assertEqual(self.calls, [], "the gate runs before the closure")

    def test_a_bound_device_reaches_it(self) -> None:
        self.device.data["user"] = "user-ada"
        self.assertTrue(self.app.dests.dispatch(self.device, {"dest": "/.secret", "data": "x"}))
        self.assertEqual(self.calls, ["x"])


class BothKindsLiveTogether(unittest.TestCase):
    """One slot, two sources: the case the registry is for, next to a closure that is not."""

    def test_a_graphed_name_and_a_closure_serve_the_same_page(self) -> None:
        app = App(routes=Routes())
        seen: list = []

        @app.on("demo.remote")
        def from_a_module(ctx, frame):
            seen.append(("remote", frame.get("data")))

        @app.page("/", title="t")
        def home(ctx, match):
            def local(value):
                seen.append(("local", value))

            ctx.page(h.frame(h.loom(h.button("local"), sink=local, submit=["button"], id="l"), id="r"))

        device = FakeDevice(app=app)
        app._draw(device)
        app.dests.dispatch(device, {"dest": "/.local", "data": 1})
        app.dests.dispatch(device, {"dest": "demo.remote", "data": 2})
        self.assertEqual(seen, [("local", 1), ("remote", 2)])


if __name__ == "__main__":
    unittest.main()