"""Every exposed accrete type is drawable: one legal node each, and the set is the profile's.

What the framework owes is the fact the old T3 (the shell's dispatch table) used to prove: **the
vocabulary a producer may address is complete and every member of it survives the boundary**. That
is a closed-set question, so it is answered offline — `profile.exposed()` against
`tests/types_fixture.NODES`, each node through the closure and through `parse`, then all of them
together through one frame.

The live half (that the renderer draws them) is `tools/gate_t3.py`, which imports the same
fixture; the three module-backed types stay out of it on purpose (see the fixture's docstring).
"""

from __future__ import annotations

import unittest

from reflux import ingest, wire
from reflux.ingest import Refused
from reflux.sdk import closed, profile
from reflux.sdk._parse import dump, parse
from tests.types_fixture import ASSET_BACKED, NODES


class TestTheVocabularyIsComplete(unittest.TestCase):
    def test_the_fixture_covers_exactly_the_exposed_types(self) -> None:
        exposed = set(profile.exposed())
        self.assertEqual(set(NODES), exposed, "a type without a node would shrink what the gate draws")
        # The one wire type with no builder: `template` is the substitution node `tmpl` expands.
        self.assertNotIn("template", NODES)
        self.assertEqual(set(closed.arms()) - set(NODES), {"template"})

    def test_the_asset_backed_four_are_named(self) -> None:
        # Three mount an ES module, one fetches mermaid: all four need a deployment artifact.
        self.assertEqual(set(ASSET_BACKED), {"canvas", "chart", "editor", "diagram"})
        self.assertLessEqual(set(ASSET_BACKED), set(NODES))


class TestEveryTypeIsLegal(unittest.TestCase):
    def test_each_node_passes_the_closure_and_its_domains(self) -> None:
        for tag, node in NODES.items():
            with self.subTest(tag):
                self.assertIsNone(closed.problem(node, tag))
                self.assertIsNotNone(parse(node))

    def test_each_node_survives_the_builders_boundary(self) -> None:
        # `wire.create` is the producer's own door: closure + parse, then the wire's dict.
        for tag, node in NODES.items():
            with self.subTest(tag):
                op = wire.create(node)
                self.assertEqual(op["action"], "create")
                self.assertEqual(op["data"]["type"], tag)

    def test_all_of_them_in_one_frame(self) -> None:
        tree = {"type": "case", "children": list(NODES.values())}
        ingest.check_frame(wire.draw("s-1", wire.create(tree)))

    def test_a_defect_in_any_of_them_is_still_caught(self) -> None:
        # The fixture must not be legal *by accident*: the same boundary refuses a typo in it.
        broken = {**NODES["case"], "attrs": {"nope": 1}}
        with self.assertRaises(Refused):
            ingest.check_frame({"ev": "draw", "sender": "s-1", "content": [{"action": "create", "event": "", "data": broken}]})

    def test_the_round_trip_is_the_wire_s_dict(self) -> None:
        # dump(parse(x)) is what actually leaves on the socket; it must drop nothing the node meant.
        for tag, node in NODES.items():
            with self.subTest(tag):
                once = dump(parse(node))
                self.assertEqual(dump(parse(once)), once, "a second trip must be a fixed point")


if __name__ == "__main__":
    unittest.main()