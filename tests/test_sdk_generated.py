"""The generated SDK's gate: the type layer validates the wire, and the profile and the schema agree.

Offline by design — no codegen, no cargo, no browser. Two commands make up this task's gate:

    python3 tools/gen_sdk.py --check              the artifacts on disk match schema + profile
    python3 -m unittest tests.test_sdk_generated  behavior + agreement (this file)

What this file pins, and why each one is here rather than assumed:

- every one of the wire's types parses into *its own* class. The codegen's raw output keyed each arm
  on a synthesised inline class (10 duplicated as `Accrete1..10`, the named classes untagged), so the
  regression is a first-class check.
- an unknown or missing `type` is refused, and so is an unknown key on a value or an out-of-domain
  `scope` (ADR 0031 made the scope a closed set; an open one is what that ADR retires).
- `source` / `sink` are typed `Bind`s (one plain model, not a free-form map) and `PanelAttr`'s
  flattened keys survive a round trip — both were silently dropped by the raw output.
- the profile's keys are exactly the schema's 18 types, the builders expose exactly the profile's
  exposed set, the hidden attribute (`class`) is unreachable, and every builder's defaults are the
  schema's.
"""

from __future__ import annotations

import inspect
import json
import pathlib
import unittest

import pydantic

from reflux import sdk
from reflux.slots import Slot

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
        """`{"type": "panel"}` used to land on a synthesised copy; the tag is what makes this true."""
        for const, cls in (("frame", "Frame"), ("panel", "Panel"), ("tiles", "Tiles"),
                           ("select", "Select"), ("entry", "Entry"), ("svg", "Svg")):
            with self.subTest(type=const):
                node = sdk.parse({"type": const, "children": []})
                self.assertEqual(type(node).__name__, cls)

    def test_round_trip_keeps_what_the_wire_said(self):
        for const, cls in ARMS:
            with self.subTest(type=const):
                sample = minimal_sample(const, cls)
                contains(sample, sdk.dump(sdk.parse(sample)), const)

    def test_unknown_or_missing_type_is_refused(self):
        for bad in ({"type": "nope"}, {"children": []}, {"type": "Frame"}):
            with self.subTest(node=bad):
                with self.assertRaises(pydantic.ValidationError):
                    sdk.parse(bad)

    def test_a_read_is_a_source_and_a_write_is_a_sink(self):
        """ADR 0039: two directions, two shapes — a read has slot/default, a write has dest."""
        reads = {
            "constant": {"default": "x"},
            "slot": {"slot": "notice"},
            "both": {"slot": "draft", "scope": "both"},
            "local+path": {"slot": "chan", "scope": "local", "path": "/data"},
            "whole": {"slot": "s", "scope": "local", "default": "0", "path": "/n"},
        }
        for name, entry in reads.items():
            with self.subTest(read=name):
                node = sdk.parse({"type": "input", "source": entry})
                self.assertEqual(sdk.dump(node)["source"], {**entry, "scope": entry.get("scope", "remote")})
        writes = {
            "dest": {"dest": "save"},
            "both": {"dest": "draft", "scope": "both"},
            "local+path": {"dest": "chan", "scope": "local", "path": "/data"},
        }
        for name, entry in writes.items():
            with self.subTest(write=name):
                node = sdk.parse({"type": "loom", "sink": entry})
                self.assertEqual(sdk.dump(node)["sink"], {**entry, "scope": entry.get("scope", "remote")})
        # The two directions do not borrow each other's words.
        for bad in (
            {"type": "input", "source": {"dest": "s"}},
            {"type": "input", "source": {"kind": "source"}},
            {"type": "loom", "sink": {"slot": "s"}},
            {"type": "loom", "sink": {"dest": "s", "default": "x"}},
        ):
            with self.subTest(node=bad):
                with self.assertRaises(pydantic.ValidationError):
                    sdk.parse(bad)
        # A field has no exit of its own any more (ADR 0032 §2, revised): `sink` is not its field.
        with self.assertRaises(pydantic.ValidationError):
            sdk.parse({"type": "input", "tag": "f", "sink": {"dest": "s"}})
        # The scope is closed: a typo is an error, not a new namespace.
        with self.assertRaises(pydantic.ValidationError):
            sdk.parse({"type": "input", "source": {"slot": "s", "scope": "loca"}})

    def test_position_attrs_survive(self):
        """serde's #[flatten] hides left/right/top/bottom from `properties`; they are wire fields."""
        node = sdk.panel(sdk.text("x"), left="10px", top="2px")
        self.assertEqual(sdk.dump(node)["attrs"], {"left": "10px", "top": "2px"})


class ProfileTest(unittest.TestCase):
    def test_profile_covers_the_schema_exactly(self):
        self.assertEqual(sorted(PROFILE["types"]), sorted(const for const, _ in ARMS))

    def test_builders_are_exactly_the_exposed_set(self):
        exposed = sorted(const for const, _ in ARMS if PROFILE["types"][const]["expose"])
        self.assertEqual(sorted(sdk.builders.__all__), exposed)
        for const in exposed:
            self.assertTrue(callable(getattr(sdk, const)), const)

    def test_the_hidden_attr_is_unreachable(self):
        # `class` only reaches the wire through the token lane (`variant=`); there is no free string.
        with self.assertRaises(TypeError):
            sdk.text("x", class_=["free-form"])
        # `selector` is not hidden: ADR 0031 §4 makes it an entry's field name, so it is data.
        self.assertEqual(sdk.dump(sdk.text("x", selector="name"))["attrs"], {"selector": "name"})

    def test_the_token_lane_is_a_closed_set_of_names(self):
        """`variant=` is a name the profile declares; the class behind it is the profile's."""
        node = sdk.text("Title", variant="heading-2")
        self.assertEqual(sdk.dump(node)["attrs"], {"class": ["rx-heading-2"]})
        self.assertEqual(sdk.dump(sdk.frame(sdk.text("x"), variant="card"))["attrs"], {"class": ["is-card"]})
        with self.assertRaises(ValueError) as caught:
            sdk.text("x", variant="heading-9")
        self.assertIn("heading-1", str(caught.exception))  # the refusal lists the set

    def test_only_declared_types_offer_a_variant(self):
        """A type the profile gives no variants has no `variant=` at all — not an inert one."""
        self.assertIn("variant", inspect.signature(sdk.text).parameters)
        self.assertNotIn("variant", inspect.signature(sdk.image).parameters)
        # Every declared token belongs to a type the builders expose, and vice versa.
        self.assertEqual(sorted(PROFILE["tokens"]), ["frame", "text"])
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

    def test_a_constant_is_a_source_default(self):
        """`text("hi")` and `text(source="hi")` are the same node — a constant is not a channel."""
        self.assertEqual(sdk.dump(sdk.text("hi")),
                         {"source": {"default": "hi", "scope": "remote"}, "type": "text"})
        self.assertEqual(sdk.dump(sdk.text(source="hi")),
                         {"source": {"default": "hi", "scope": "remote"}, "type": "text"})
        # A slot with a fallback is what the wire means by `{slot, default}`, so both is one value.
        self.assertEqual(sdk.dump(sdk.text("untitled", source=Slot("draft")))["source"],
                         {"default": "untitled", "scope": "remote", "slot": "draft"})
        self.assertEqual(sdk.dump(sdk.image("/static/logo.svg"))["source"],
                         {"default": "/static/logo.svg", "scope": "remote"})

    def test_a_slot_is_a_name_written_once(self):
        self.assertEqual(sdk.dump(sdk.text(source=Slot("title")))["source"],
                         {"scope": "remote", "slot": "title"})
        # A bare string is not a second spelling of a slot: take the handle, or say `sdk.Source(slot=…)`.
        with self.assertRaises(TypeError):
            sdk.frame(source="title")

    def test_each_direction_reaches_the_wire_where_it_belongs(self):
        # A field has one type and no exit of its own (ADR 0032 §2, revised 2026-11-24): the value
        # it holds is named by `tag`, its exit is the loom's, and its kind is `kind`.
        self.assertEqual(sdk.dump(sdk.input(tag="name", source=Slot("prefill")))["source"],
                         {"scope": "remote", "slot": "prefill"})
        typed = sdk.dump(sdk.input(tag="password", kind=sdk.JsType.password))
        self.assertEqual(typed["kind"], "password")
        self.assertNotIn("sink", typed)
        with self.assertRaises(TypeError):
            sdk.input(tag="name", sink="save")  # a field has no sink to give
        # The write belongs to the loom: the one node that owns an exit for its fields and its
        # button. A button is not a party to the send (ADR 0039 §2a), so it refuses one.
        with self.assertRaises(TypeError):
            sdk.button("提交", sink="submit")  # a button has no exit of its own
        self.assertEqual(sdk.dump(sdk.loom(sink="compose"))["sink"],
                         {"dest": "compose", "scope": "remote"})
        # A local landing is the loom's too: one draw, one write, the reset still applies.
        local = sdk.dump(sdk.loom(sink=sdk.Sink(dest="__CONFIG__", scope="local", path="/")))
        self.assertEqual(local["sink"], {"dest": "__CONFIG__", "path": "/", "scope": "local"})
        self.assertEqual(sdk.dump(sdk.select(options=Slot("rows")))["options"],
                         {"scope": "remote", "slot": "rows"})
        self.assertEqual(sdk.dump(sdk.input(placeholder="写点什么"))["placeholder"],
                         {"default": "写点什么", "scope": "remote"})
        # A channel a type does not accept is not a keyword of its builder — refused where it is built.
        for call in (lambda: sdk.text(sink="x"), lambda: sdk.loom(source="x"), lambda: sdk.tiles(sink="x")):
            with self.assertRaises(TypeError):
                call()

    def test_a_loom_packs_its_fields(self):
        """ADR 0032: fields are named by `tag`, the loom owns the sink, `submit` is its timing."""
        node = sdk.loom(
            sdk.input(tag="name"),
            sdk.input(tag="body", multiline=True),
            sink="compose",
        )
        wire = sdk.dump(node)
        self.assertEqual(wire["sink"], {"dest": "compose", "scope": "remote"})
        self.assertEqual([(child["tag"], child.get("multiline")) for child in wire["children"]],
                         [("name", None), ("body", True)])
        self.assertNotIn("attrs", wire)  # absent `submit` means the wire default, `[enter]`
        # A bare string and a one-item list are the same set; both reach the wire as a list.
        self.assertEqual(sdk.dump(sdk.loom(submit="change"))["attrs"], {"submit": ["change"]})
        self.assertEqual(sdk.dump(sdk.loom(submit=["enter", "button"]))["attrs"],
                         {"submit": ["enter", "button"]})
        # A field's own value is a read (placeholder), and it has no write to carry.
        field = sdk.dump(sdk.input(tag="note", placeholder="写点什么"))
        self.assertEqual(field["placeholder"], {"default": "写点什么", "scope": "remote"})
        self.assertNotIn("sink", field)
        # `multiline` is a layout of `input`, not a type of its own.
        self.assertFalse(hasattr(sdk, "textarea"))

    def test_a_value_carries_its_scope_and_path(self):
        # ADR 0031 §1: scope rides the value, so a local read is a `Source`, not a second keyword.
        self.assertEqual(
            sdk.dump(sdk.text(source=sdk.Source(slot="chan", scope="local", path="/data")))["source"],
            {"path": "/data", "scope": "local", "slot": "chan"},
        )
        self.assertEqual(sdk.dump(sdk.text(source=sdk.Source(slot="chan")))["source"],
                         {"scope": "remote", "slot": "chan"})
        with self.assertRaises(pydantic.ValidationError):
            sdk.text(source=sdk.Source(slot="chan", scope="loca"))
        # A write's word on a read is not a spelling of it: `dest` belongs to the other direction
        # and is refused by the model, not quietly dropped (ADR 0039).
        with self.assertRaises(pydantic.ValidationError):
            sdk.text(source=sdk.Source(dest="chan"))

    def test_a_field_says_how_often_it_is_heard(self):
        # ADR 0032 §8: one window, one way — `debounce` or `throttle`, never both, and absent means the
        # reader's 250 ms default (the wire does not spell it out).
        field = sdk.input(tag="q", emit=sdk.Emit(sdk.Debounce(debounce=300)))
        self.assertEqual(sdk.dump(field)["emit"], {"debounce": 300})
        self.assertEqual(
            sdk.dump(sdk.input(tag="q", emit=sdk.Emit(sdk.Throttle(throttle=50))))["emit"],
            {"throttle": 50},
        )
        self.assertNotIn("emit", sdk.dump(sdk.input(tag="q")))
        # The same window in both shapes is not a shape: the model refuses it, and so does the schema.
        with self.assertRaises(pydantic.ValidationError):
            sdk.input(tag="q", emit={"debounce": 1, "throttle": 2})
        with self.assertRaises(pydantic.ValidationError):
            sdk.input(tag="q", emit={"debounce": -1})

    def test_children_come_through(self):
        node = sdk.frame(sdk.text("a"), sdk.text("b"))
        self.assertEqual([n["type"] for n in sdk.dump(node)["children"]], ["text", "text"])
        self.assertIsNone(sdk.dump(sdk.frame()).get("children"))  # an empty container is noise, not a frame
        grid = sdk.tiles(sdk.entry(sdk.text("a", selector="name")), fields=[{"key": "name"}],
                         source=Slot("rows"))
        wire = sdk.dump(grid)
        self.assertEqual([n["type"] for n in wire["children"]], ["entry"])
        self.assertEqual(wire["children"][0]["children"][0]["attrs"], {"selector": "name"})

    def test_a_grid_is_tiles_with_typed_attrs(self):
        """ADR 0031 §4 / 0035: `fields` projects an entry's fields; `dir`, `wrap`, `window`, `step`,
        `header` are their own shapes."""
        node = sdk.tiles(
            dir="row",
            wrap="nowrap",
            window={"size": 2},
            step={"timer": 4000},
            header={"selector": "grid-head", "layers": 2},
            fields=[{"key": "name", "title": "Name"}, {"key": "qty", "align": "end"}],
        )
        self.assertEqual(sdk.dump(node)["attrs"], {
            "dir": "row",
            "fields": [{"key": "name", "title": "Name"}, {"key": "qty", "align": "end"}],
            "header": {"layers": 2, "selector": "grid-head"},
            "step": {"timer": 4000},
            "window": {"size": 2},
            "wrap": "nowrap",
        })
        # The stepper's other arm, and the closures: a bad direction, wrap, window or alignment is
        # refused at construction.
        self.assertEqual(sdk.dump(sdk.tiles(wrap="wrap-reverse", step={"slot": "page"}))["attrs"],
                         {"step": {"slot": "page"}, "wrap": "wrap-reverse"})
        for bad in (lambda: sdk.tiles(dir="both"), lambda: sdk.tiles(wrap="sideways"),
                    lambda: sdk.tiles(step={"ticks": 1}), lambda: sdk.tiles(window={"size": 0}),
                    lambda: sdk.tiles(fields=[{"key": "a", "align": "middle"}]),
                    lambda: sdk.tiles(header={"selector": "h", "layers": 3})):
            with self.assertRaises(pydantic.ValidationError):
                bad()


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