"""`reflux uplinks` — the registry a real app registers, plus the one check that earns its keep.

Offline by design: no browser, no socket, no cargo. Two jobs:

- the **command** prints what exists (name, kind, source) and refuses a target it cannot resolve
  loudly, because a target that silently becomes "nothing registered" would teach people that the
  verb is broken rather than their spelling;
- the **check** the tests here are really for: every event a page can send has a handler. Walking the
  reference app's two pages and collecting `bind.kind == "intent"` catches `form(dest="login.submit")`
  typos before a browser run does, and it keeps the demo honest as it grows.

`kind=builtin` is the framework's own names (`reflux:hello`, `reflux:nav`); everything else is `app`.
"""

from __future__ import annotations

import contextlib
import io
import unittest

import reflux.demo_app as demo
from reflux import cli
from reflux.app import App
from reflux.sdk import dump


def sent_dests(node) -> set[str]:
    """Every uplink destination the nodes of one page can send.

    `bind.kind == "dest"` is the uplink target and its `dest` is where it goes: an input's Enter, a
    form's submit, a row's own button. `submit`/`field`/`default` bindings carry values, not
    destinations, so they are not collected.
    """
    names: set[str] = set()

    def walk(node) -> None:
        if not isinstance(node, dict):
            return
        for entry in (node.get("bind") or {}).values():
            if isinstance(entry, dict) and entry.get("kind") == "dest":
                name = entry.get("dest")
                if isinstance(name, str):
                    names.add(name)
        for key in ("children", "item"):
            for kid in node.get(key) or ():
                walk(kid)

    walk(dump(node))
    return names


class EventsCommand(unittest.TestCase):
    def setUp(self) -> None:
        self.app = demo.make_app()

    def test_the_reference_app_lists_every_name_it_registers(self) -> None:
        rows = self.app.dests.table()
        names = [name for name, _, _ in rows]
        self.assertEqual(names, sorted(names), "the table is sorted by name")
        self.assertEqual(
            names,
            [
                "go.about",
                "go.home",
                "login.submit",
                "name.change",
                "reflux:hello",
                "reflux:nav",
                "row.add",
                "row.remove",
            ],
        )

    def test_builtin_names_are_marked_and_app_names_are_not(self) -> None:
        kinds = {name: kind for name, _, kind in self.app.dests.table()}
        self.assertEqual(kinds["reflux:hello"], "builtin")
        self.assertEqual(kinds["reflux:nav"], "builtin")
        self.assertEqual(kinds["row.add"], "app")

    def test_the_source_column_is_where_the_handler_was_written(self) -> None:
        sources = {name: source for name, source, _ in self.app.dests.table()}
        self.assertEqual(sources["row.add"], "reflux.demo_app.Demo.on_add")
        self.assertTrue(sources["reflux:hello"].startswith("reflux."), sources["reflux:hello"])

    def test_this_app_is_not_the_only_app_the_registry_serves(self) -> None:
        # A fresh App is not "the app": the registry belongs to the instance, so its table is the
        # builtin protocol names only — the demo's names live on the demo's instance.
        alone = App()
        self.assertEqual([name for name, _, _ in alone.dests.table()], ["reflux:hello", "reflux:nav"])


class TargetResolution(unittest.TestCase):
    def test_a_factory_is_called(self) -> None:
        app = cli.resolve_app("reflux.demo_app:make_app")
        self.assertIsInstance(app, App)
        self.assertIn("row.add", app.dests.names())

    def test_an_app_instance_is_taken_as_it_is(self) -> None:
        mine = App()
        setattr(demo, "app_for_the_test", mine)
        try:
            self.assertIs(cli.resolve_app("reflux.demo_app:app_for_the_test"), mine)
        finally:
            delattr(demo, "app_for_the_test")

    def test_a_target_without_a_colon_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            cli.resolve_app("reflux.demo_app")
        self.assertIn("module:attr", str(caught.exception))

    def test_a_missing_attribute_is_refused_and_named(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            cli.resolve_app("reflux.demo_app:no_such_factory")
        self.assertIn("no_such_factory", str(caught.exception))

    def test_an_attribute_that_is_not_an_app_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            cli.resolve_app("reflux.demo_app:GO")  # a dict of navigation targets
        self.assertIn("dict", str(caught.exception))


class EverySendableDestHasAHandler(unittest.TestCase):
    """The check that makes this file more than a formatter test."""

    def setUp(self) -> None:
        self.app = demo.make_app()
        self.registered = set(self.app.dests.names())

    def test_the_reference_page_sends_only_registered_dests(self) -> None:
        sent = sent_dests(demo.demo.home())
        self.assertTrue(sent, "the home page has uplinks; an empty set means the walk is wrong")
        self.assertEqual(sent - self.registered, set(), "the page sends an event nobody handles")

    def test_the_about_page_sends_only_registered_dests(self) -> None:
        sent = sent_dests(demo.demo.about())
        self.assertTrue(sent)
        self.assertEqual(sent - self.registered, set())

    def test_the_walk_sees_the_row_forms_the_page_does_not_contain(self) -> None:
        # Rows arrive through `append`, not through the page tree, so the row template is its own
        # subject — a row's remove event is exactly the kind of thing a page walk would miss.
        row = demo.row_node({"id": "row-9", "text": "x"})
        self.assertEqual(sent_dests(row), {"row.remove"})
        self.assertIn("row.remove", self.registered)


class Printing(unittest.TestCase):
    def run_cli(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(list(argv))
        return code, out.getvalue()

    def test_intents_prints_a_header_and_one_line_per_name(self) -> None:
        code, text = self.run_cli("dests", "reflux.demo_app:make_app")
        self.assertEqual(code, 0)
        lines = [line for line in text.splitlines() if line.strip()]
        self.assertTrue(lines[0].startswith("event"))
        self.assertIn("kind", lines[0])
        self.assertIn("source", lines[0])
        self.assertEqual(len(lines), 1 + 8, "header + the eight names the demo registers")
        self.assertTrue(any(line.startswith("row.remove") for line in lines))

    def test_routes_still_works(self) -> None:
        code, text = self.run_cli("routes", "reflux.demo_app")
        self.assertEqual(code, 0)
        self.assertIn("/about", text)


if __name__ == "__main__":
    unittest.main()