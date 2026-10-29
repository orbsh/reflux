"""The outbound frame layer speaks accrete's eight actions, verbatim.

The shapes asserted here are copied from the renderer's `content` crate (`Influx`, `AppendOp`,
`RemoveOp`, `PatchOp`, `InjectOp`, `InfluxTmpl`, and the `Content` tag): a shape that drifts from that
file is a frame the renderer refuses whole, so this table is a contract, not a sample. The refusals
matter just as much — a producer's bad pointer or out-of-type position has to fail on this side.
"""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from reflux import wire
from reflux.sdk import builders as b
from reflux.sdk._parse import dump, parse


class TestShapes(unittest.TestCase):
    def test_create_carries_the_empty_event_and_the_node(self) -> None:
        node = b.text("hi")
        self.assertEqual(
            wire.create(node),
            {"action": "create", "slot": "", "data": dump(node)},
        )

    def test_set_replaces_a_named_slot(self) -> None:
        node = b.text("hi")
        self.assertEqual(
            wire.set("echo", node),
            {"action": "set", "slot": "echo", "data": dump(node)},
        )

    def test_append_leaves_the_default_position_off_the_wire(self) -> None:
        op = wire.append("rows", b.text("a"))
        self.assertEqual(op["action"], "append")
        self.assertEqual(op["slot"], "rows")
        self.assertNotIn("position", op, "position 0 is the default — writing it is noise")

    def test_append_carries_a_real_position(self) -> None:
        self.assertEqual(wire.append("rows", b.text("a"), position=1)["position"], 1)
        self.assertEqual(wire.append("rows", b.text("a"), position=-1)["position"], -1)

    def test_remove_is_by_identity(self) -> None:
        self.assertEqual(
            wire.remove("rows", "row-2"),
            {"action": "remove", "slot": "rows", "id": "row-2"},
        )

    def test_patch_defaults_to_replace(self) -> None:
        op = wire.patch("echo", "/bind/value/default", "x")
        self.assertEqual(op["action"], "patch")
        self.assertEqual(op["slot"], "echo")
        self.assertEqual(op["path"], "/bind/value/default")
        self.assertEqual(op["op"], "replace")
        self.assertNotIn("id", op)

    def test_patch_addresses_the_layout_root_with_an_empty_slot(self) -> None:
        self.assertEqual(wire.patch("", "/children/0", {})["slot"], "")

    def test_patch_append_extends_a_string(self) -> None:
        self.assertEqual(wire.patch("echo", "/bind/value/default", "!", op="append")["op"], "append")

    def test_patch_can_address_a_row(self) -> None:
        self.assertEqual(wire.patch("rows", "/bind/value/default", "x", id="row-2")["id"], "row-2")

    def test_inject_writes_the_vals_plane(self) -> None:
        self.assertEqual(
            wire.inject("chan", {"v": 1}),
            {"action": "inject", "slot": "chan", "data": {"v": 1}},
        )

    def test_inject_can_carry_a_name_and_an_id(self) -> None:
        op = wire.inject("chan", None, name="chan", id="row-1")
        self.assertEqual(op["name"], "chan")
        self.assertEqual(op["id"], "row-1")

    def test_tmpl_registers_a_body_string(self) -> None:
        self.assertEqual(
            wire.tmpl("t1", '{"type":"text"}'),
            {"action": "tmpl", "name": "t1", "data": '{"type":"text"}'},
        )

    def test_empty_carries_nothing(self) -> None:
        self.assertEqual(wire.empty(), {"action": "empty"})

    def test_a_frame_is_the_action_list(self) -> None:
        frame = wire.draw(wire.empty(), wire.create(b.text("hi")))
        self.assertEqual([op["action"] for op in frame], ["empty", "create"])
        self.assertIsInstance(frame, list, "no envelope: the host wraps its own")


class TestRefusals(unittest.TestCase):
    def test_a_path_that_is_not_a_pointer(self) -> None:
        with self.assertRaises(ValueError):
            wire.patch("echo", "bind/value", "x")

    def test_an_unknown_patch_op(self) -> None:
        with self.assertRaises(ValueError):
            wire.patch("echo", "/bind/value/default", "x", op="insert")

    def test_a_position_that_is_not_an_int(self) -> None:
        with self.assertRaises(ValueError):
            wire.append("rows", b.text("a"), position="1")
        with self.assertRaises(ValueError):
            wire.append("rows", b.text("a"), position=True)

    def test_a_node_that_is_not_accrete(self) -> None:
        # An unknown type is the closure's refusal (the shared walk), a bad domain pydantic's —
        # both are `ValueError`s: the builder is loud either way.
        with self.assertRaises(ValueError) as caught:
            wire.create({"type": "not-a-type"})
        self.assertIn("not one of the wire's types", str(caught.exception))
        with self.assertRaises(ValidationError):
            wire.create({"type": "input", "id": 7})
        with self.assertRaises(ValueError):
            wire.create(object())

    def test_empty_slots_and_ids(self) -> None:
        for call in (
            lambda: wire.set("", b.text("x")),
            lambda: wire.remove("rows", ""),
            lambda: wire.inject("", None),
            lambda: wire.tmpl("", "{}"),
        ):
            with self.assertRaises(ValueError):
                call()

    def test_draw_needs_operations_and_known_actions(self) -> None:
        with self.assertRaises(ValueError):
            wire.draw()
        with self.assertRaises(ValueError):
            wire.draw({"op": "create", "root": {}})



class TestTheBuildersBoundary(unittest.TestCase):
    """The first fence: a hand-written node fails where it is built, not inside the renderer."""

    def test_a_hand_written_node_is_checked_before_it_is_dumped(self) -> None:
        # `parse` alone would have *dropped* the typo (accrete ignores unknown fields), so the
        # builders run the same closure the server's boundary runs.
        with self.assertRaises(ValueError) as caught:
            wire.create({"type": "text", "name": "typo"})
        self.assertIn("'name' is not a field of 'text'", str(caught.exception))
        with self.assertRaises(ValueError):
            wire.set("echo", {"type": "text", "attrs": {"class": ["leak"]}})

    def test_the_wire_names_are_the_models_aliases(self) -> None:
        # accrete says `class`; the model's field is `class_`. `dump` is the wire's dict, so the
        # Python spelling must not reach it (the renderer's serde would drop the key silently).
        node = parse({"type": "text", "attrs": {"class": ["token"]}})
        self.assertEqual(dump(node)["attrs"], {"class": ["token"]})


if __name__ == "__main__":
    unittest.main()