"""The generated SDK's gate: the type layer validates the wire, and the profile and the schema agree.

Offline by design — no codegen, no cargo, no browser. Two commands make up this task's gate:

    python3 tools/gen_sdk.py --check              the artifacts on disk match schema + profile
    python3 -m unittest tests.test_sdk_generated  behavior + agreement (this file)

What this file pins, and why each one is here rather than assumed:

- every one of the wire's types parses into *its own* class. The codegen's raw output failed this for
  18 of them ({"type": "float"} validated as `Case`), so the regression is a first-class check.
- an unknown or missing `type` is refused, and so is an unknown `bind.kind`.
- `bind` is a typed map (not `dict[str, Any]`) and `PositionAttr`'s flattened keys survive a round
  trip — both were silently dropped by the raw output.
- the profile's keys are exactly the schema's 30 types, the builders expose exactly the profile's
  exposed set, the hidden attributes are unreachable, and every builder's defaults are the schema's.
"""

from __future__ import annotations

import inspect
import json
import pathlib
import unittest

import pydantic

from reflux import sdk

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "schema" / "accrete.schema.json").read_text())
PROFILE = json.loads((ROOT / "profile" / "profile.json").read_text())
ARMS = [(a["properties"]["type"]["const"], a["$ref"].rsplit("/", 1)[1]) for a in SCHEMA["oneOf"]]
DEFS = SCHEMA["$defs"]


def fill(node: dict):
    """A minimal value for a schema fragment: enough to satisfy `required`, nothing more."""
    if "$ref" in node:
        return fill(DEFS[node["$ref"].rsplit("/", 1)[1]])
    for key in ("anyOf", "oneOf"):
        if key in node:
            branches = [b for b in node[key] if b.get("type") != "null" and b != {}]
            return fill(branches[0]) if branches else None
    t = node.get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), None)
    if t == "object":
        return {name: fill(sub) for name, sub in (node.get("properties") or {}).items()
                if name in (node.get("required") or [])}
    if t == "array":
        return []
    if t == "boolean":
        return False
    if t == "integer":
        return 0
    if t == "string":
        return "x"
    return None


def minimal_sample(const: str, cls: str) -> dict:
    defn = DEFS[cls]
    node = {"type": const}
    for name in defn.get("required") or []:
        node[name] = fill((defn.get("properties") or {})[name])
    return node


def contains(small, big, path="") -> None:
    """Every key/value the minimal node states must survive the round trip unchanged."""
    if isinstance(small, dict):
        for k, v in small.items():
            assert k in big, f"{path}/{k} disappeared"
            contains(v, big[k], f"{path}/{k}")
    elif isinstance(small, list):
        assert len(small) == len(big), f"{path}: list length changed"
        for i, v in enumerate(small):
            contains(v, big[i], f"{path}/{i}")
    else:
        assert small == big, f"{path}: {small!r} became {big!r}"


class UnionTest(unittest.TestCase):
    def test_every_type_parses_into_its_own_class(self):
        for const, cls in ARMS:
            with self.subTest(type=const):
                sample = minimal_sample(const, cls)
                node = sdk.parse(sample)
                self.assertEqual(type(node).__name__, cls)
                self.assertEqual(sdk.dump(node)["type"], const)

    def test_the_regression_the_codegen_had(self):
        """{"type": "float"} used to validate as `Case`; the tag is what makes this true."""
        for const in ("case", "float", "rack", "select", "layer"):
            with self.subTest(type=const):
                node = sdk.parse({"type": const, "children": []})
                self.assertEqual(type(node).__name__, const.capitalize() if const != "svg" else "Svg")

    def test_round_trip_keeps_what_the_wire_said(self):
        for const, cls in ARMS:
            with self.subTest(type=const):
                sample = minimal_sample(const, cls)
                contains(sample, sdk.dump(sdk.parse(sample)), const)

    def test_unknown_or_missing_type_is_refused(self):
        for bad in ({"type": "nope"}, {"children": []}, {"type": "Case"}):
            with self.subTest(node=bad):
                with self.assertRaises(pydantic.ValidationError):
                    sdk.parse(bad)

    def test_bind_is_a_typed_map_discriminated_on_kind(self):
        kinds = {
            "default": {"kind": "default", "default": "x"},
            "source": {"kind": "source", "source": "slot"},
            "event": {"kind": "event", "event": "save"},
            "field": {"kind": "field", "field": "name", "payload": {"k": 1}},
            "submit": {"kind": "submit", "default": "提交"},
            "local": {"kind": "local", "slot": "draft"},
        }
        for name, entry in kinds.items():
            with self.subTest(kind=name):
                node = sdk.parse({"type": "input", "bind": {"value": entry}})
                self.assertEqual(sdk.dump(node)["bind"]["value"], entry)
        with self.assertRaises(pydantic.ValidationError):
            sdk.parse({"type": "input", "bind": {"value": {"kind": "nope"}}})

    def test_position_attrs_survive(self):
        """serde's #[flatten] hides left/right/top/bottom from `properties`; they are wire fields."""
        node = sdk.float(sdk.text("x"), left="10px", top="2px")
        self.assertEqual(sdk.dump(node)["attrs"], {"left": "10px", "top": "2px"})


class ProfileTest(unittest.TestCase):
    def test_profile_covers_the_schema_exactly(self):
        self.assertEqual(sorted(PROFILE["types"]), sorted(const for const, _ in ARMS))

    def test_builders_are_exactly_the_exposed_set(self):
        exposed = sorted(const for const, _ in ARMS if PROFILE["types"][const]["expose"])
        self.assertEqual(sorted(sdk.builders.__all__), exposed)
        for const in exposed:
            self.assertTrue(callable(getattr(sdk, const)), const)

    def test_hidden_attrs_are_unreachable(self):
        with self.assertRaises(TypeError):
            sdk.text("x", class_=["free-form"])
        with self.assertRaises(TypeError):
            sdk.text("x", selector="#nope")

    def test_the_token_lane_is_a_closed_set_of_names(self):
        """`variant=` is a name the profile declares; the class behind it is the profile's."""
        node = sdk.text("Title", variant="heading-2")
        self.assertEqual(sdk.dump(node)["attrs"], {"class": ["rx-heading-2"]})
        self.assertEqual(sdk.dump(sdk.case(sdk.text("x"), variant="card"))["attrs"], {"class": ["rx-card"]})
        with self.assertRaises(ValueError) as caught:
            sdk.text("x", variant="heading-9")
        self.assertIn("heading-1", str(caught.exception))  # the refusal lists the set

    def test_only_declared_types_offer_a_variant(self):
        """A type the profile gives no variants has no `variant=` at all — not an inert one."""
        self.assertIn("variant", inspect.signature(sdk.text).parameters)
        self.assertNotIn("variant", inspect.signature(sdk.image).parameters)
        # Every declared token belongs to a type the builders expose, and vice versa.
        self.assertEqual(sorted(PROFILE["tokens"]), ["case", "text"])
        for tag, variants in PROFILE["tokens"].items():
            self.assertTrue(PROFILE["types"][tag]["expose"], tag)
            self.assertTrue(variants, tag)
            self.assertTrue(all(isinstance(v, str) and v for v in variants.values()), tag)

    def test_builder_defaults_are_the_schema_defaults(self):
        for const, cls in ARMS:
            entry = PROFILE["types"][const]
            if not entry["expose"]:
                continue
            params = inspect.signature(getattr(sdk, const)).parameters
            defn = DEFS[cls]
            for name, sub in (defn.get("properties") or {}).items():
                if name != "attrs":
                    continue
                for attr_def in _refs(sub):
                    for attr, attr_schema in (DEFS[attr_def].get("properties") or {}).items():
                        if attr in PROFILE["hidden_attrs"]:
                            continue
                        if attr not in params:
                            continue
                        with self.subTest(type=const, attr=attr):
                            self.assertEqual(params[attr].default, attr_schema.get("default", None))

    def test_one_off_bind_reaches_the_wire(self):
        self.assertEqual(sdk.dump(sdk.text("hi"))["bind"], {"value": {"kind": "default", "default": "hi"}})
        self.assertEqual(sdk.dump(sdk.text(source="title"))["bind"],
                         {"value": {"kind": "source", "source": "title"}})
        with self.assertRaises(ValueError):
            sdk.text("hi", source="title")  # two sources for one slot
        self.assertEqual(sdk.dump(sdk.button("提交"))["bind"],
                         {"value": {"kind": "submit", "default": "提交"}})
        self.assertEqual(sdk.dump(sdk.select(options_source="rows"))["bind"],
                         {"options": {"kind": "source", "source": "rows"}})
        self.assertEqual(sdk.dump(sdk.textarea(placeholder="写点什么"))["bind"],
                         {"placeholder": {"kind": "default", "default": "写点什么"}})
        node = sdk.input(field="name", kind=sdk.JsType.text)
        self.assertEqual(sdk.dump(node)["bind"],
                         {"value": {"kind": "field", "field": "name", "type": "text"}})
        self.assertEqual(sdk.dump(sdk.input(event="save"))["bind"],
                         {"value": {"kind": "event", "event": "save"}})
        with self.assertRaises(ValueError):
            sdk.input(event="save", field="name")  # one落点 at a time
        with self.assertRaises(ValueError):
            sdk.input(payload={"k": 1})  # payload rides a field落点, not thin air

    def test_children_and_item_come_through(self):
        node = sdk.case(sdk.text("a"), sdk.text("b"))
        self.assertEqual([n["type"] for n in sdk.dump(node)["children"]], ["text", "text"])
        self.assertIsNone(sdk.dump(sdk.case()).get("children"))  # an empty container is noise, not a frame
        rack = sdk.rack(source="rows", item=[sdk.text("row")])
        self.assertEqual(len(sdk.dump(rack)["item"]), 1)


def _refs(node: dict) -> list[str]:
    out: list[str] = []
    if "$ref" in node:
        out.append(node["$ref"].rsplit("/", 1)[1])
    for key in ("anyOf", "oneOf", "allOf"):
        for sub in node.get(key) or ():
            out += _refs(sub)
    return out


if __name__ == "__main__":
    unittest.main()