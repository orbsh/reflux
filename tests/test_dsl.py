"""The writing layer: `ui` addresses the spec's builders, `ops` builds the frames.

What these tests protect is the *absence* of a second vocabulary: `ui.<name>` is the generated
builder for that component, an unknown name dies listing the closed set, and an op builder is
loud about any shape the client would otherwise drop or refuse and count.
"""

from __future__ import annotations

import inspect
import json
import unittest

import reflux
from reflux import components_generated, ops, ui
from reflux.tables_generated import COMPONENTS


class TestTheComponentNamespace(unittest.TestCase):
    def test_every_component_is_reachable_and_nothing_else_is(self) -> None:
        self.assertEqual(sorted(dir(ui)), sorted(COMPONENTS))

    def test_each_name_is_the_generated_builder(self) -> None:
        for name in COMPONENTS:
            with self.subTest(component=name):
                self.assertIs(getattr(ui, name).__wrapped__, getattr(components_generated, name))
                self.assertEqual(
                    inspect.signature(getattr(ui, name)),
                    inspect.signature(getattr(components_generated, name)),
                )

    def test_an_unknown_name_dies_with_the_vocabulary(self) -> None:
        with self.assertRaises(AttributeError) as caught:
            ui.div  # primitives are not in the vocabulary
        self.assertIn("closed", str(caught.exception))
        for name in sorted(COMPONENTS)[:3]:
            self.assertIn(name, str(caught.exception))

    def test_children_may_arrive_as_a_list(self) -> None:
        one, two = ui.text("a"), ui.text("b")
        self.assertEqual(ui.stack([one, two], gap="sm"), ui.stack(one, two, gap="sm"))

    def test_the_boundary_still_guards_the_namespace(self) -> None:
        with self.assertRaises(ValueError):
            ui.text("x", tone="purple")  # the enum is closed, DSL or not
        with self.assertRaises(TypeError):
            ui.text("x", cls="flex")  # and no free class strings reach the wire

    def test_a_view_can_be_written_and_dumped(self) -> None:
        page = ui.stack(
            ui.heading("看板", level=1),
            ui.input(placeholder="名字", source="name", event="name.change", payload=["value"]),
            gap="lg",
        )
        wire = json.loads(page.dump())
        self.assertEqual(wire["type"], "stack")
        self.assertEqual(wire["children"][1]["bind"]["payload"], ["value"])


class TestTheFrameBuilders(unittest.TestCase):
    def test_the_four_ops_have_the_documented_shape(self) -> None:
        node = ui.text("x")
        self.assertEqual(ops.create(node, title="看板"), {"op": "create", "root": node, "title": "看板"})
        self.assertEqual(ops.create(node), {"op": "create", "root": node})
        self.assertEqual(ops.patch("/slots/echo", "你好"), {"op": "patch", "path": "/slots/echo", "value": "你好"})
        self.assertEqual(
            ops.insert("/slots/rows", node, anchor={"id": "row-2"}),
            {"op": "insert", "path": "/slots/rows", "anchor": {"id": "row-2"}, "node": node},
        )
        self.assertEqual(ops.insert("/slots/rows", node), {"op": "insert", "path": "/slots/rows", "anchor": "end", "node": node})
        self.assertEqual(ops.remove("/slots/rows"), {"op": "remove", "path": "/slots/rows"})
        self.assertEqual(ops.remove("/slots/rows", id="row-2"), {"op": "remove", "path": "/slots/rows", "id": "row-2"})

    def test_a_frame_is_one_turn(self) -> None:
        frame = ops.draw(ops.patch("/slots/a", 1), ops.remove("/slots/rows", id="row-1"))
        self.assertEqual(frame["ev"], "draw")
        self.assertEqual([op["op"] for op in frame["ops"]], ["patch", "remove"])
        json.dumps(frame)  # the frame is JSON, one frame per turn

    def test_a_bad_path_is_loud_here_not_a_counted_drop_over_there(self) -> None:
        with self.assertRaises(ValueError):
            ops.patch("slots/echo", "x")  # a JSON Pointer starts with /
        with self.assertRaises(ValueError):
            ops.remove(7)  # type: ignore[arg-type]

    def test_a_bad_anchor_is_loud(self) -> None:
        node = ui.text("x")
        for anchor in ("middle", {"index": -1}, {"id": ""}, {"index": 1, "id": "row-1"}, {"nope": 1}):
            with self.subTest(anchor=anchor):
                with self.assertRaises(ValueError):
                    ops.insert("/slots/rows", node, anchor=anchor)

    def test_a_non_node_is_loud(self) -> None:
        with self.assertRaises(ValueError):
            ops.create({"nope": True})  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            ops.insert("/slots/rows", "not a node")  # type: ignore[arg-type]

    def test_draw_refuses_a_non_op(self) -> None:
        with self.assertRaises(ValueError):
            ops.draw({"op": "frobnicate"})
        with self.assertRaises(ValueError):
            ops.draw(ops.patch("/slots/a", 1), "nope")  # type: ignore[arg-type]

    def test_no_op_name_shadows_a_component(self) -> None:
        # `ui` and `ops` are two namespaces with one meaning each; a component named `patch`
        # would make `ui.patch` ambiguous, so the vocabulary and the ops must stay apart.
        self.assertEqual(set(ops.__all__) & set(COMPONENTS), set())
        self.assertEqual(reflux.OPS, ["create", "patch", "insert", "remove"])


if __name__ == "__main__":
    unittest.main()