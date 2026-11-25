"""The vocabulary under `h`: `h.frame(...)` for a page written by hand, `h.node(...)` for one that is data.

Two spellings, one set of builders. What this file pins is that they are the same builders — the frame
that comes out is the same frame, byte for byte — and that the data form is a constructor, not a second
dialect: its props are the builder's own keywords, so a typo is still refused.
"""

from __future__ import annotations

import unittest

from reflux.app import App
from reflux.routes import Routes
from reflux.sdk import dump, h
from tests.fakes import run_sync, FakeDevice


class TheSameFrame(unittest.TestCase):
    def test_attribute_form_and_data_form_agree(self) -> None:
        written = h.frame(
            h.text("hi", variant="muted"),
            h.button("go"),
            grid={"gap": "8px"},
            variant="card",
            id="root",
        )
        as_data = h.node(
            (
                "frame",
                {"grid": {"gap": "8px"}, "variant": "card", "id": "root"},
                [("text", {"variant": "muted"}, "hi"), ("button", {}, "go")],
            )
        )
        self.assertEqual(dump(written), dump(as_data))

    def test_one_bare_value_is_the_nodes_positional(self) -> None:
        self.assertEqual(dump(h.node(("text", {}, "hi"))), dump(h.text("hi")))

    def test_a_list_is_several_nodes_in_order(self) -> None:
        built = h.node([("text", {}, "a"), ("text", {}, "b")])
        self.assertEqual([dump(node)["source"]["default"] for node in built], ["a", "b"])

    def test_a_tree_may_mix_built_nodes_with_data(self) -> None:
        ready = h.text("ready", id="ready")
        built = h.node(("frame", {"id": "root"}, [ready, ("text", {}, "after")]))
        self.assertEqual(dump(built)["children"][0]["id"], "ready")


class TheRefusalsStay(unittest.TestCase):
    def test_an_unknown_type_names_the_vocabulary(self) -> None:
        with self.assertRaises(ValueError) as caught:
            h.node(("framee", {}, []))
        self.assertIn("frame", str(caught.exception), "the message lists what does exist")

    def test_an_unknown_property_is_a_type_error(self) -> None:
        # The builder gets the props as keywords, so its own refusal is the one a reader meets —
        # `h.frame(varient=…)` and `h.node(("frame", {"varient": …}))` fail the same way.
        with self.assertRaises(TypeError):
            h.node(("frame", {"varient": "card"}, []))

    def test_a_node_needs_a_type(self) -> None:
        with self.assertRaises(ValueError):
            h.node(())


class AClosureInsideData(unittest.TestCase):
    def test_a_data_tree_can_carry_a_closure_sink(self) -> None:
        app = App(routes=Routes())
        calls: list = []

        def hit(value):
            calls.append(value)

        @app.page("/", title="t")
        def home(ctx, match):
            # The landing rides the loom: a press is the loom's send, not the button's.
            ctx.page(
                h.node(
                    ("frame", {"id": "r"}, [
                        ("loom", {"sink": hit, "submit": ["button"], "id": "g"},
                         [("button", {"id": "b"}, "press")]),
                    ])
                )
            )

        device = FakeDevice(app=app)
        run_sync(app._draw(device))
        self.assertEqual(sorted(device.landings), ["/.hit"])
        self.assertTrue(run_sync(app.dests.dispatch(device, {"dest": "/.hit", "data": 1})))
        self.assertEqual(calls, [1])


if __name__ == "__main__":
    unittest.main()