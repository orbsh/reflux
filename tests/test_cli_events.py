"""`reflux dests` — the registry a real app registers, plus the one check that earns its keep.

Offline by design: no browser, no socket, no cargo. Two jobs:

- the **command** prints what exists (name, kind, source) and refuses a target it cannot resolve
  loudly, because a target that silently becomes "nothing registered" would teach people that the
  verb is broken rather than their spelling;
- the **check** the tests here are really for: every event a page can send has a handler. Walking the
  reference app's two pages and collecting `sink.slot` from every node catches a mistyped
  `loom(sink=…)` before a browser run does, and it keeps the demo honest as it grows.

`kind=builtin` is the framework's own names (`reflux:hello`, `reflux:nav`); everything else is `app`.
"""

from __future__ import annotations

import contextlib
import io
import unittest

from examples.zh import demo_app as demo
from reflux import Context

_CTX = Context(app=None, device=None)  # type: ignore[arg-type]  # only the slot names are read
from reflux import cli
from reflux.application import create_app, App
from reflux.sdk import dump
from tests.fakes import run_sync, FakeDevice  # noqa: F401
from tests.fakes import page_nodes


def sent_dests(node) -> set[str]:
    """Every uplink destination the nodes of one page can send.

    A node's `sink` is where its value flows out (ADR 0031 §2); when the value is an event, the
    address is the handler's name, carried as `sink.dest` (ADR 0039). `source` is the read side — a
    slot the page reads from, never one it speaks to — so it is not collected.
    """
    names: set[str] = set()

    def walk(node) -> None:
        if isinstance(node, (list, tuple)):
            for kid in node:
                walk(kid)
            return
        if not isinstance(node, dict):
            return
        sink = node.get("sink")
        if isinstance(sink, dict):
            name = sink.get("dest")
            if isinstance(name, str):
                names.add(name)
        for key in ("children", "item"):
            for kid in node.get(key) or ():
                walk(kid)

    # A model (what a page builder returns) or an already-dumped dict (what the app sends).
    for item in node if isinstance(node, (list, tuple)) else [node]:
        walk(item if isinstance(item, dict) else dump(item))
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
                "__CONFIG__",
                "chat.send",
                "chat.stop",
                "demo.pin",
                "demo.review",
                "demo.save",
                "demo.toggle",
                "disconnect",
                "go.about",
                "go.chat",
                "go.counter",
                "go.demo",
                "go.home",
                "go.settings",
                "reflux:hello",
                "reflux:login",
                "reflux:logout",
                "reflux:nav",
                "reflux:signup",
                "row.archive",
                "row.remove",
            ],
        )

    def test_builtin_names_are_marked_and_app_names_are_not(self) -> None:
        kinds = {name: kind for name, _, kind in self.app.dests.table()}
        self.assertEqual(kinds["reflux:hello"], "builtin")
        self.assertEqual(kinds["reflux:nav"], "builtin")
        self.assertEqual(kinds["row.remove"], "app")

    def test_the_source_column_is_where_the_handler_was_written(self) -> None:
        sources = {name: source for name, source, _ in self.app.dests.table()}
        self.assertEqual(sources["row.remove"], "examples.zh.demo_app.on_remove")
        self.assertTrue(sources["reflux:hello"].startswith("reflux."), sources["reflux:hello"])

    def test_this_app_is_not_the_only_app_the_registry_serves(self) -> None:
        # A fresh App is not "the app": the registry belongs to the instance, so its table is the
        # builtin protocol names only — the demo's names live on the demo's instance.
        alone = create_app()
        self.assertEqual([name for name, _, _ in alone.dests.table()], ["reflux:hello", "reflux:nav"])


class TargetResolution(unittest.TestCase):
    def test_a_factory_is_called(self) -> None:
        app = cli.resolve_app("examples.zh.demo_app:make_app")
        self.assertIsInstance(app, App)
        self.assertIn("row.remove", app.dests.names())

    def test_an_app_instance_is_taken_as_it_is(self) -> None:
        mine = create_app()
        setattr(demo, "app_for_the_test", mine)
        try:
            self.assertIs(cli.resolve_app("examples.zh.demo_app:app_for_the_test"), mine)
        finally:
            delattr(demo, "app_for_the_test")

    def test_a_target_without_a_colon_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            cli.resolve_app("examples.zh.demo_app")
        self.assertIn("module:attr", str(caught.exception))

    def test_a_missing_attribute_is_refused_and_named(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            cli.resolve_app("examples.zh.demo_app:no_such_factory")
        self.assertIn("no_such_factory", str(caught.exception))

    def test_an_attribute_that_is_not_an_app_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            cli.resolve_app("examples.zh.demo_app:GO")  # a dict of navigation targets
        self.assertIn("dict", str(caught.exception))


class EverySendableDestHasAHandler(unittest.TestCase):
    """The check that makes this file more than a formatter test."""

    def setUp(self) -> None:
        self.app = demo.make_app()
        self.registered = set(self.app.dests.names())

    def test_the_reference_page_sends_only_registered_dests(self) -> None:
        # A page's closures are landing points too, but they are one draw's: they resolve on the
        # device that drew the page, not in the app's registry. So the invariant is "every name the
        # page sends resolves where it was drawn" — which is the stronger half of the old check.
        device = FakeDevice(app=self.app)
        run_sync(self.app._draw(device))
        sent = sent_dests(page_nodes(self.app, '/'))
        self.assertTrue(sent, "the home page has uplinks; an empty set means the walk is wrong")
        self.assertEqual(sent - self.registered - set(device.landings), set(),
                         "the page sends an event nobody handles")

    def test_the_about_page_sends_only_registered_dests(self) -> None:
        sent = sent_dests(page_nodes(self.app, '/about'))
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
        code, text = self.run_cli("dests", "examples.zh.demo_app:make_app")
        self.assertEqual(code, 0)
        lines = [line for line in text.splitlines() if line.strip()]
        self.assertTrue(lines[0].startswith("dest"))
        self.assertIn("kind", lines[0])
        self.assertIn("source", lines[0])
        # header + the demo's own names + the two protocol names + the three auth verbs (it declares
        # `auth=`, so the door exists — an app without one has neither the verbs nor a gate)
        self.assertEqual(len(lines), 1 + 21, "header + every name the demo registers")
        self.assertTrue(any(line.startswith("row.remove") for line in lines))

    def test_routes_still_works(self) -> None:
        code, text = self.run_cli("routes", "examples.zh.demo_app")
        self.assertEqual(code, 0)
        self.assertIn("/about", text)


if __name__ == "__main__":
    unittest.main()