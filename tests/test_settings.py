"""The settings page's server half (ADR 0001): unpack, validate, merge, remember, seed.

The browser half is `STYLE` in `www/static/reflux.js` and it is asserted by `tools/gate_settings.py`
(real Chromium, real socket); what is testable without a browser is what the server does with an
uplink and what it puts in the first frame.
"""

from __future__ import annotations

import asyncio
import json
import re
import tempfile
import unittest
from pathlib import Path

from examples.zh import demo_settings as settings
from reflux.application import create_app, App
from tests.fakes import FakeDevice, run_sync


def ctx_for(device: FakeDevice):
    """A context for a device, with no route behind it: enough for `slot` and `data`."""
    return device.app.context(device)


def body(device: FakeDevice) -> dict:
    return {op["slot"]: op["data"] for frame in device.frames for op in frame}


class TestFlatten(unittest.TestCase):
    def test_the_renderers_field_shape_is_unwrapped(self):
        self.assertEqual(
            settings.flatten({"sketch": {"data": True}, "round": {"data": 8}}),
            {"sketch": True, "round": 8},
        )

    def test_bare_values_pass_through(self):
        self.assertEqual(settings.flatten({"accent": "#ffffff"}), {"accent": "#ffffff"})

    def test_a_malformed_payload_is_empty_not_an_exception(self):
        for payload in (None, [], "nope", 3, {"sketch": {"nope": 1}}, {"accent": None}):
            with self.subTest(payload=payload):
                self.assertEqual(settings.flatten(payload), {})


class TestMerge(unittest.TestCase):
    def base(self) -> dict:
        return dict(settings.DEFAULTS)

    def test_a_member_outside_the_whitelist_is_dropped(self):
        merged, rejected = settings.merge(self.base(), {"nonsense": 1, "round": 4})
        self.assertEqual(rejected, ["nonsense"])
        self.assertEqual(merged["round"], "4")
        self.assertNotIn("nonsense", merged)

    def test_a_bad_colour_is_dropped(self):
        for value in ("red", "#fff", "#12345g", "0.5 0.1", "0.5 0.1 200 1", 8):
            with self.subTest(value=value):
                merged, rejected = settings.merge(self.base(), {"accent": value})
                self.assertEqual(rejected, ["accent"])
                self.assertNotIn("accent", merged, "a refused member keeps whatever was there — nothing")

    def test_a_colour_is_a_triple_and_is_normalised(self):
        for written, expected in (
            ("  0.70 0.120 182.49 ", "0.7 0.12 182.49"),
            ("0.7,0.1,200", "0.7 0.1 200"),
            ("oklch(0.7 0.1 200)", "0.7 0.1 200"),  # a written-out oklch is accepted
            ("0.65	0.2	30", "0.65 0.2 30"),
        ):
            with self.subTest(written=written):
                merged, rejected = settings.merge(self.base(), {"accent": written})
                self.assertEqual(rejected, [])
                self.assertEqual(merged["accent"], expected)

    def test_a_colour_outside_its_ranges_is_dropped(self):
        for value in ("1.2 0.1 200", "-0.1 0.1 200", "0.5 0.9 200", "0.5 0.1 400", "0.5 -0.1 200"):
            with self.subTest(value=value):
                self.assertEqual(settings.merge(self.base(), {"accent": value})[1], ["accent"])

    def test_a_length_is_a_number_in_range(self):
        for written, expected in (("12", "12"), ("12px", "12"), (3.5, "3.5"), ("0", "0")):
            with self.subTest(written=written):
                merged, rejected = settings.merge(self.base(), {"round": written})
                self.assertEqual(rejected, [])
                self.assertEqual(merged["round"], expected)
        for value in (-1, 65, True, "wide", "10em"):
            with self.subTest(value=value):
                merged, rejected = settings.merge(self.base(), {"round": value})
                self.assertEqual(rejected, ["round"], "bool is an int subclass and must not pass")
                self.assertNotIn("round", merged)

    def test_a_keyword_is_one_of_the_five(self):
        self.assertEqual(settings.merge(self.base(), {"border-style": "solid"})[0]["border-style"], "solid")
        self.assertEqual(settings.merge(self.base(), {"border-style": "DASHED"})[0]["border-style"], "dashed")
        self.assertEqual(settings.merge(self.base(), {"border-style": "wavy"})[1], ["border-style"])

    def test_an_empty_value_clears_the_member(self):
        """Clearing a field is "not set", not an error: core's default (and its light-dark pair) returns."""
        merged, rejected = settings.merge({"accent": "0.7 0.1 200"}, {"accent": "   "})
        self.assertEqual(rejected, [], "an empty field arrives on every frame and is not a mistake")
        self.assertNotIn("accent", merged)

    def test_sketch_takes_a_bool_or_its_two_spellings(self):
        self.assertTrue(settings.merge(self.base(), {"sketch": True})[0]["sketch"])
        self.assertTrue(settings.merge(self.base(), {"sketch": "true"})[0]["sketch"])
        self.assertFalse(settings.merge(self.base(), {"sketch": "false"})[0]["sketch"])
        self.assertEqual(settings.merge(self.base(), {"sketch": 1})[1], ["sketch"])


class TestStore(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "settings.json"
        self.store = settings.Store(self.path, delay=0.0)

    def tearDown(self) -> None:
        self.dir.cleanup()

    def test_a_missing_file_is_the_defaults(self):
        self.assertEqual(self.store.load(), settings.DEFAULTS)

    def test_bad_json_is_the_defaults(self):
        self.path.write_text("{not json", encoding="utf-8")
        self.assertEqual(self.store.load(), settings.DEFAULTS)

    def test_unknown_members_in_the_file_are_dropped_on_load(self):
        self.path.write_text(json.dumps({"round": 3, "sneaky": True}), encoding="utf-8")
        self.store.load()
        self.assertEqual(self.store.state["round"], "3")
        self.assertNotIn("sneaky", self.store.state)

    def test_a_change_is_written_once(self):
        # No loop here (a plain test), so `save_soon` writes at once instead of scheduling.
        self.store.apply({"round": {"data": 6}})
        self.assertEqual(self.store.state["round"], "6")
        self.assertEqual(self.store.writes, 1)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["round"], "6")

    def test_a_change_that_changes_nothing_writes_nothing(self):
        self.store.apply({"round": "6"})
        self.store.apply({"round": "6"})
        self.assertEqual(self.store.writes, 1, "the second uplink said the same thing")
        self.store.apply({"accent": "  "})
        self.assertEqual(self.store.writes, 1, "an empty field on every frame is not a change")

    def test_rejected_members_do_not_write(self):
        self.store.apply({"accent": "red"})
        self.assertEqual(self.store.rejected, ["accent"])
        self.assertEqual(self.store.writes, 0, "nothing was scheduled, so nothing was written")

    def test_the_write_is_throttled_to_the_last_change(self):
        async def burst() -> int:
            self.store.delay = 0.05
            self.store.apply({"round": {"data": 4}})
            self.store.apply({"round": {"data": 5}})
            self.store.apply({"round": {"data": 6}})
            self.assertEqual(self.store.writes, 0, "nothing hits the disk inside the window")
            await asyncio.sleep(0.12)
            return self.store.writes

        self.assertEqual(run_sync(burst()), 1, "three changes in one window, one write")

    def test_the_file_is_replaced_atomically(self):
        self.store.apply({"accent": {"data": "0.7 0.1 200"}})
        self.store.flush()
        leftovers = [p.name for p in self.path.parent.iterdir()]
        self.assertEqual(leftovers, ["settings.json"], "no .tmp survives a successful write")


class TestSeed(unittest.TestCase):
    def test_the_first_draw_writes_the_slot_once(self):
        app = create_app()
        device = FakeDevice(app=app)
        ctx = app.context(device)
        settings.seed(ctx)
        settings.seed(ctx)
        frames = [op for frame in device.frames for op in frame]
        self.assertEqual(len(frames), 1, "a second draw must not repeat the seed")
        self.assertEqual(frames[0]["action"], "set")
        self.assertEqual(frames[0]["slot"], settings.CONFIG)
        self.assertEqual(frames[0]["data"]["source"]["default"], dict(settings.settings.state))

    def test_the_seed_carries_the_stored_choice(self):
        with tempfile.TemporaryDirectory() as where:
            settings.settings.path = Path(where) / "s.json"
            settings.settings.state = dict(settings.DEFAULTS)
            settings.settings.apply({"round": {"data": 21}})
            device = FakeDevice(app=create_app())
            settings.seed(device.app.context(device))
            landed = body(device)[settings.CONFIG]
            self.assertEqual(landed["source"]["default"]["round"], "21")
            settings.settings.state = dict(settings.DEFAULTS)


class TestThePage(unittest.TestCase):
    def drawn(self) -> dict:
        app = create_app()
        page = settings.page(app.context(FakeDevice(app=app)), None)
        return json.loads(page.model_dump_json(by_alias=True, exclude_none=True))

    def walk(self, node):
        if isinstance(node, dict):
            yield node
            for child in node.get("children") or []:
                yield from self.walk(child)

    def test_the_group_has_one_outlet_to_the_page_options_slot(self):
        looms = [node for node in self.walk(self.drawn()) if node.get("type") == "loom"]
        self.assertEqual(len(looms), 1)
        loom = looms[0]
        self.assertEqual(loom["sink"], {"dest": settings.CONFIG, "path": "/", "scope": "both"})
        self.assertEqual(loom["attrs"]["submit"], ["change"])
        self.assertEqual(loom["attrs"]["reset"], "keep")

    def test_every_member_is_a_field_of_that_group(self):
        tags = [
            node.get("tag")
            for node in self.walk(self.drawn())
            if node.get("type") in ("input", "picker", "color")  # picked, not typed: colours, words, sizes
        ]
        self.assertEqual(sorted(tags), sorted(settings.MEMBERS))


class TestTheUplink(unittest.TestCase):
    def test_a_dropped_member_is_named_on_the_page(self):
        with tempfile.TemporaryDirectory() as where:
            settings.settings.path = Path(where) / "s.json"
            app = create_app()
            device = FakeDevice(app=app)
            ctx = app.context(device)
            run_sync(
                settings.on_config(
                    ctx, {"dest": settings.CONFIG, "data": {"accent": {"data": "red"}, "round": {"data": 9}}}
                )
            )
            note = body(device)["settings.note"]
            self.assertIn("accent", json.dumps(note, ensure_ascii=False))
            self.assertEqual(settings.settings.state["round"], "9", "the good member still landed")
            settings.settings.state = dict(settings.DEFAULTS)


class TestTheTables(unittest.TestCase):
    """One fact, three readers: the page's fields, the browser's table, and core.css's `:root` block.

    These cases are the only thing keeping "all of core's tokens are exported" honest: a token added to the
    stylesheet by a renderer bump shows up as a missing row here, and a member the browser table forgot shows
    up as a mismatch between two lists that have no other way to agree.
    """

    def root_block(self) -> str:
        css = (Path(__file__).resolve().parent.parent / "www/static/vendor/fluxen/assets/core.css").read_text(encoding="utf-8")
        start = css.index("@layer tokens {")  # the block, not the layer list at the top of the file
        begin = css.index(":root {", start)
        return css[begin : css.index("}", begin)]

    def root_tokens(self) -> set[str]:
        names = set(re.findall(r"--([a-z-]+)\s*:", self.root_block()))
        return names - {"border"}  # `--border` is composed from width, style and colour

    def test_every_root_token_is_exported(self):
        self.assertEqual(sorted(self.root_tokens()), sorted(settings.TOKENS))

    def test_the_browser_table_is_the_server_table(self):
        script = (Path(__file__).resolve().parent.parent / "www/static/reflux.js").read_text(encoding="utf-8")
        block = script[script.index("const TOKENS = {") : script.index("};", script.index("const TOKENS = {"))]
        pairs = re.findall(r'"?([a-z-]+)"?:\s*"(color|length|keyword)"', block)
        self.assertEqual(dict(pairs), settings.TOKENS, "reflux.js and the page must name the same tokens")

    def test_both_trees_export_the_same_tokens(self):
        from examples.en import demo_settings as english

        self.assertEqual(english.TOKENS, settings.TOKENS)
        self.assertEqual(english.KEYWORDS, settings.KEYWORDS)


if __name__ == "__main__":
    unittest.main()