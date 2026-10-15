"""The spec is the single source: both artifacts must be exactly what it generates.

This is T1's gate. It fails when either the shell's component table or the Python SDK
drifts from `spec/components.json` — the failure mode that N hand-written SDKs would
produce by construction (I5).
"""

from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GEN = REPO / "tools" / "gen.py"


def _load_gen():
    spec = importlib.util.spec_from_file_location("reflux_gen", GEN)
    assert spec and spec.loader, f"cannot load {GEN}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gen = _load_gen()
spec = gen.load_spec()


class TestSpecToArtifacts(unittest.TestCase):
    def test_artifacts_match_the_spec(self) -> None:
        live = gen.load_spec()
        for path, emit in gen.ARTIFACTS.items():
            with self.subTest(artifact=path.name):
                self.assertTrue(path.is_file(), f"{path} missing — run python3 tools/gen.py")
                self.assertEqual(
                    path.read_text(encoding="utf-8"),
                    emit(live),
                    f"{path.name} drifted from the spec — run python3 tools/gen.py",
                )

    def test_cli_check_mode_agrees(self) -> None:
        self.assertEqual(gen.main(["--check"]), 0)


class TestSpecShape(unittest.TestCase):
    def test_families_are_one_of_four(self) -> None:
        families = {c["family"] for c in spec["components"].values()}
        self.assertTrue(families <= {"container", "input", "display", "nav", "feedback"})

    def test_closed_sets(self) -> None:
        self.assertEqual(spec["ops"], ["create", "patch", "insert", "remove"])
        self.assertEqual(spec["bind_keys"], ["source", "event", "payload"])
        self.assertEqual(spec["reserved_prefix"], "reflux:")

    def test_every_component_states_local_state_and_bind(self) -> None:
        for name, comp in spec["components"].items():
            with self.subTest(component=name):
                self.assertIn("local", comp)
                self.assertIn("bind", comp)
                self.assertTrue(comp["attrs"], "a component with no attrs carries no data")


class TestBothSidesAgree(unittest.TestCase):
    def test_shell_table_equals_sdk_table(self) -> None:
        js = (REPO / "shell" / "js" / "components.generated.js").read_text(encoding="utf-8")
        literal = re.search(r"export const COMPONENTS = (\{.*?\});\n", js, re.S)
        self.assertIsNotNone(literal, "shell table not found in the generated file")
        assert literal is not None
        from_shell = json.loads(literal.group(1))

        import reflux

        self.assertEqual(from_shell, reflux.COMPONENTS)
        self.assertEqual(reflux.SPEC_VERSION, spec["spec_version"])


class TestBoundary(unittest.TestCase):
    """`make` is where a malformed node dies — before the wire, not on the client."""

    def test_builds_a_valid_node(self) -> None:
        import reflux

        node = reflux.stack(
            reflux.text("hello", source="greeting"),
            reflux.button("+", event="counter.inc"),
            gap="lg",
        )
        self.assertEqual(node["type"], "stack")
        self.assertEqual(node["attrs"]["gap"], "lg")
        self.assertEqual(node["attrs"]["direction"], "column")  # default filled
        self.assertEqual(node["children"][0]["attrs"]["value"], "hello")
        self.assertEqual(node["children"][0]["bind"], {"source": "greeting"})
        self.assertEqual(node["children"][1]["bind"], {"event": "counter.inc"})
        self.assertEqual(json.loads(node.dump())["type"], "stack")

    def test_generated_signatures_have_the_intended_shape(self) -> None:
        """Leaf: primary attr positional, the rest keyword-only. Container: children positional."""
        import inspect

        import reflux

        text_params = inspect.signature(reflux.text).parameters
        self.assertEqual([p.name for p in text_params.values()][:1], ["value"])
        self.assertIs(text_params["value"].kind, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        self.assertIs(text_params["tone"].kind, inspect.Parameter.KEYWORD_ONLY)

        stack_params = inspect.signature(reflux.stack).parameters
        self.assertIs(stack_params["children"].kind, inspect.Parameter.VAR_POSITIONAL)
        self.assertIs(stack_params["gap"].kind, inspect.Parameter.KEYWORD_ONLY)

    def test_rejects_unknown_component_and_attr(self) -> None:
        import reflux

        with self.assertRaises(ValueError):
            reflux.make("div")  # primitives are not in the vocabulary
        # two ways to die, both at the boundary: the typed builder's signature (TypeError)
        # and the generic path's validation (ValueError). No free class strings either way.
        with self.assertRaises(TypeError):
            reflux.text("x", cls="flex")
        with self.assertRaises(ValueError):
            reflux.make("text", {"value": "x", "cls": "flex"})

    def test_rejects_enum_and_range_violations(self) -> None:
        import reflux

        with self.assertRaises(ValueError):
            reflux.text("x", tone="purple")
        with self.assertRaises(ValueError):
            reflux.heading("x", level=7)
        with self.assertRaises(ValueError):
            reflux.image("https://example.com/a.png", fit="stretch")

    def test_rejects_missing_required_and_bad_urls(self) -> None:
        import reflux

        with self.assertRaises(ValueError):
            reflux.make("text", {})  # value is required
        with self.assertRaises(ValueError):
            reflux.image("javascript:alert(1)")

    def test_rejects_bind_and_children_violations(self) -> None:
        import reflux

        with self.assertRaises(ValueError):
            reflux.make("text", {"value": "x"}, event="x.y")  # text accepts source only
        with self.assertRaises(ValueError):
            reflux.button("go", event="reflux:nav")  # reserved prefix
        with self.assertRaises(ValueError):
            reflux.input(event="save", payload=["fields"])  # not this component's local state
        with self.assertRaises(ValueError):
            reflux.field(reflux.text("a"), reflux.text("b"), label="L")  # exactly one child
        with self.assertRaises(ValueError):
            reflux.make("button", {"label": "go"}, children=[reflux.text("label")])  # no children


if __name__ == "__main__":
    unittest.main()