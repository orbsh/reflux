"""The ingest boundary: closure, the frame's own shape, and the two doors that call it.

Table-driven on purpose — every refusal class is exercised once with the reason it must produce,
because the point of this layer is that nothing about a bad frame is left to the renderer's
one-line `warn`. A legal frame must pass through *unchanged*: the boundary refuses, it never edits.

The shapes here are the renderer's `content` crate (each action's field set) and accrete's node
vocabulary (read off the generated models, never retyped in this file).
"""

from __future__ import annotations

import json
import time
import unittest
from typing import Any

from reflux import ingest, wire
from reflux.app import App, Session
from reflux.channel import Channel
from reflux.ingest import Refused
from reflux.sdk import builders as b
from reflux.sdk._parse import dump
from reflux.tables_generated import MAX_OPS_PER_FRAME


def frame(*ops: dict, sender: str = "s-1") -> dict:
    return {"ev": "draw", "sender": sender, "content": list(ops)}


def hand(action: str, node: Any, **rest: Any) -> dict:
    """One op written out by hand — the frame a producer bypassing the SDK would build.

    Its nodes are hand-written too: `wire`'s builders would refuse a bad one at construction time
    (that is the *first* fence), so going around them is the only way to reach this one.
    """
    return {"action": action, "event": "", "data": node, **rest}


def refused(case: unittest.TestCase, bad: dict, expects: str) -> None:
    """The frame is refused whole, and the reason names the defect."""
    with case.assertRaises(Refused) as caught:
        ingest.check_frame(bad)
    case.assertIn(expects, str(caught.exception))


class TestTheFrame(unittest.TestCase):
    def test_a_legal_frame_passes_untouched(self) -> None:
        good = frame(
            wire.tmpl("t1", '{"type":"text"}'),
            wire.create(b.case(b.text("hi", id="a"), b.rack(source="rows"))),
            wire.append("rows", b.text("row", id="r1")),
            wire.inject("chan", {"v": 1}),
        )
        ingest.check_frame(good)  # returns: nothing to report
        self.assertEqual(good["ev"], "draw")

    def test_the_retiring_shell_dialect_is_not_this_layers_business(self) -> None:
        # The shell's own validator refuses what it cannot render; M1.7 retires it.
        ingest.check_frame({"ev": "draw", "ops": [{"op": "patch", "path": "/slots/x", "value": 1}]})

    def test_the_envelope_shape(self) -> None:
        cases = [
            ("not an object", [], "frame is list"),
            ("an unknown key", {**frame(wire.empty()), "extra": 1}, "envelope: 'extra'"),
            ("a second ev", {**frame(wire.empty()), "ev": "nav"}, "ev is 'nav'"),
            ("no sender", frame(wire.empty(), sender=""), "sender is ''"),
            ("content not a list", {"ev": "draw", "sender": "s", "content": {}}, "content is dict"),
            ("no operations", frame(), "content is empty"),
            (
                "over the cap",
                frame(*[wire.empty()] * (MAX_OPS_PER_FRAME + 1)),
                f"the cap is {MAX_OPS_PER_FRAME}",
            ),
        ]
        for label, bad, expects in cases:
            with self.subTest(label):
                refused(self, bad, expects)

    def test_an_unknown_action(self) -> None:
        refused(self, frame({"action": "move"}), "'move' is not one of the eight actions")
        refused(self, frame({"op": "create", "root": {}}), "is not one of the eight actions")

    def test_each_actions_field_set(self) -> None:
        node = dump(b.text("x"))
        cases = [
            ("create grows a field", {"action": "create", "event": "", "data": node, "root": 1}, "'root'"),
            ("set needs its slot", {"action": "set", "data": node}, "'event' is required"),
            ("append's position is an int", {"action": "append", "event": "rows", "data": node, "position": "0"}, "position is '0'"),
            ("remove needs an id", {"action": "remove", "event": "rows"}, "'id' is required"),
            ("patch's pointer", {"action": "patch", "event": "", "path": "a/b", "op": "replace", "value": 1}, "not a JSON Pointer"),
            ("patch's op", {"action": "patch", "event": "", "path": "", "op": "insert", "value": 1}, '"replace" or "append"'),
            ("patch needs a value", {"action": "patch", "event": "", "path": "", "op": "replace"}, "'value' is required"),
            ("inject's slot", {"action": "inject", "slot": "", "data": 1}, "is not a non-empty string"),
            ("tmpl's body", {"action": "tmpl", "name": "t", "data": {"k": 1}}, "not the template's JSON as text"),
            ("tmpl's body text", {"action": "tmpl", "name": "t", "data": "{nope"}, "data is not JSON"),
            ("empty carries nothing", {"action": "empty", "data": 1}, "'data' is not a field"),
        ]
        for label, op, expects in cases:
            with self.subTest(label):
                refused(self, frame(op), expects)


class TestTheNode(unittest.TestCase):
    def test_an_unknown_type(self) -> None:
        refused(self, frame(hand("create", {"type": "widget"})), "'widget' is not one of the wire's types")
        refused(self, frame(hand("create", {"id": "x"})), "no `type` tag")

    def test_an_unknown_field(self) -> None:
        refused(self, frame(hand("create", {"type": "text", "name": "x"})), "'name' is not a field of 'text'")

    def test_attributes_are_the_schemas_minus_the_hidden_ones(self) -> None:
        # `class` and `selector` exist in accrete; the profile keeps them out of a producer's reach.
        refused(self, frame(hand("create", {"type": "text", "attrs": {"class": ["x"]}})), "'class' is not an attribute")
        refused(self, frame(hand("create", {"type": "text", "attrs": {"selector": "x"}})), "'selector' is not an attribute")
        refused(
            self,
            frame(hand("create", {"type": "text", "attrs": {"format": "x", "nope": 1}})),
            "'nope' is not an attribute",
        )

    def test_a_leaked_python_spelling_is_refused(self) -> None:
        # `class_` is the model's name for the wire's `class`; the renderer's serde would drop it.
        refused(self, frame(hand("create", {"type": "text", "attrs": {"class_": ["x"]}})), "'class_' is not an attribute")

    def test_the_bind_map_is_closed_per_kind(self) -> None:
        refused(
            self,
            frame(hand("create", {"type": "text", "bind": {"value": {"kind": "elsewhere"}}})),
            "not one of the wire's binding kinds",
        )
        # `payload` rides a `field`落点 only — on a `source` entry it is a silent drop anywhere else.
        refused(
            self,
            frame(
                hand(
                    "create",
                    {"type": "text", "bind": {"value": {"kind": "source", "source": "s", "payload": ["a"]}}},
                )
            ),
            "'payload' is not a field of a 'source' binding",
        )

    def test_value_domains_are_pydantics(self) -> None:
        refused(self, frame(hand("create", {"type": "input", "id": 7})), "content[0] (create).data")
        refused(self, frame(hand("create", {"type": "input", "kind": "nope"})), "content[0] (create).data")

    def test_a_defect_deep_in_the_tree_names_its_path(self) -> None:
        bad = {"type": "case", "children": [{"type": "text", "bind": {"value": {"kind": "default", "default": "x"}}}, {"type": "nope"}]}
        with self.assertRaises(Refused) as caught:
            ingest.check_frame(frame(hand("create", bad)))
        self.assertIn("children[1]", str(caught.exception))

    def test_the_substitution_node_is_legal_on_the_wire(self) -> None:
        # `template` has no builder (the profile's `expose` is the builder surface, not the wire's
        # closure): it is what `tmpl` expands, and a producer may place one.
        ingest.check_frame(frame(hand("create", {"type": "template", "name": "t1", "data": {"label": "x"}})))

    def test_every_node_of_the_turn_is_checked(self) -> None:
        ops = [
            {"action": "set", "event": "echo", "data": dump(b.text("x"))},
            {"action": "append", "event": "rows", "data": {"type": "nope"}},
        ]
        refused(self, frame(*ops), "content[1] (append).data")


class TestRowIdentity(unittest.TestCase):
    def test_two_appends_of_one_id_in_one_frame(self) -> None:
        refused(
            self,
            frame(wire.append("rows", b.text("a", id="r")), wire.append("rows", b.text("b", id="r"))),
            "row id 'r' appears twice in one frame",
        )

    def test_different_slots_or_different_ids_are_fine(self) -> None:
        ingest.check_frame(frame(wire.append("left", b.text("a", id="r")), wire.append("right", b.text("b", id="r"))))
        ingest.check_frame(frame(wire.append("rows", b.text("a", id="r1")), wire.append("rows", b.text("b", id="r2"))))

    def test_rows_without_identity_may_repeat(self) -> None:
        ingest.check_frame(frame(wire.append("rows", b.text("a")), wire.append("rows", b.text("b"))))


class TestTheUplink(unittest.TestCase):
    def test_a_legal_uplink(self) -> None:
        ingest.check_uplink({"event": "name.change", "data": {"value": "x"}})
        ingest.check_uplink({"event": "name.change", "id": "input-1", "data": {}})

    def test_its_failures(self) -> None:
        cases = [
            ("not an object", "x", "frame is str"),
            ("an unknown key", {"event": "e", "data": 1, "path": "/a"}, "envelope: 'path'"),
            ("no event", {"data": 1}, "event is None"),
            ("an empty event", {"event": "", "data": 1}, "event is ''"),
            ("a non-string id", {"event": "e", "id": 3, "data": 1}, "id is 3"),
            ("an empty id", {"event": "e", "id": "", "data": 1}, "id is ''"),
            ("no data", {"event": "e"}, "data is missing"),
        ]
        for label, bad, expects in cases:
            with self.subTest(label):
                with self.assertRaises(Refused) as caught:
                    ingest.check_uplink(bad)
                self.assertIn(expects, str(caught.exception))


class ScriptedChannel(Channel):
    """A connection that delivers the frames it was given, then closes."""

    def __init__(self, *messages: dict) -> None:
        self.messages = [json.dumps(m) for m in messages]
        self.last_seen = time.monotonic()
        self.frames: list[dict] = []
        self.closed_with: int | None = None
        self.aborted = False

    def __iter__(self):
        yield from self.messages

    def send(self, text: str) -> None:
        self.frames.append(json.loads(text))

    def ping(self, payload: bytes = b"") -> None:
        pass

    def close(self, code: int = 1000) -> None:
        self.closed_with = code

    def abort(self) -> None:
        self.aborted = True


class TestTheOutboundDoor(unittest.TestCase):
    """`Session.send` is the one door every outbound frame passes."""

    def make(self) -> Session:
        self.stats = {"refused": 0, "shed": 0}
        self.log: list[str] = []
        return Session(
            "s-1",
            channel=ScriptedChannel(),
            record=lambda *a: None,
            stats=self.stats,
            note=self.log.append,
        )

    def test_a_bad_frame_never_queues_and_is_counted_with_its_session(self) -> None:
        session = self.make()
        session.send(frame({"action": "move"}))
        self.assertEqual(session.outbox, [])
        self.assertEqual(session.sent, 0)
        self.assertEqual(self.stats["refused"], 1)
        self.assertTrue(any("s-1" in line and "eight actions" in line for line in self.log), self.log)

    def test_a_good_frame_queues(self) -> None:
        session = self.make()
        good = frame(wire.create(b.text("x")))
        session.send(good)
        self.assertEqual(session.outbox, [good])
        self.assertEqual(self.stats["refused"], 0)


class TestTheInboundDoor(unittest.TestCase):
    """`App.handle` refuses before the registry can see the frame, and the session lives on."""

    def test_a_hand_written_bad_uplink_is_refused_and_the_session_survives(self) -> None:
        app = App(heartbeat=0.05, dead_after=0.5)
        seen: list[dict] = []

        @app.events.register("gate.ok")
        def ok(session, received):
            seen.append(received)
            session.send(frame(wire.create(b.text("ok")), sender=session.id))

        channel = ScriptedChannel(
            {"event": "gate.ok", "data": {"n": 1}, "extra": "hand written"},  # refused: unknown key
            {"event": "gate.ok", "id": 7, "data": {}},                     # refused: id is not a string
            {"event": "gate.ok", "data": {"n": 2}},                        # dispatched
        )
        app.handle(channel)  # returns when the scripted connection ends

        self.assertEqual(len(seen), 1, seen)
        self.assertEqual(seen[0]["data"], {"n": 2})
        self.assertEqual(app.stats["refused"], 2)
        self.assertEqual(app.stats["issued"], 1)
        self.assertEqual(app.stats["reclaimed"], 1)
        self.assertTrue(any("refused uplink" in line and "extra" in line for line in app.events.log), app.events.log)
        app.stop()


if __name__ == "__main__":
    unittest.main()