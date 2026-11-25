"""The walkthrough page's backend, offline: no browser, no socket, no module on disk.

`tools/gate_demo.py` walks the same script over a real socket and draws it in Chromium; these cases
pin the parts that are pure — the page's shape (one region, one slot), what each beat writes, that a
pause is a wait rather than a stop, the four states of the floating button, and the three uplinks.

The script runs **inline** here (`demo.spawn` is replaced), so a whole playback is a function call;
the one case that needs the clock (pause/resume) starts a real thread and is written to be tolerant
of where the pause lands.
"""

from __future__ import annotations

import time
import unittest

from reflux.sdk._parse import dump

from examples.zh import demo_app as _app
from examples.zh.demo import page as demo
from examples.zh.demo import scene
from tests.fakes import FakeDevice

# The page lives in the reference app; one built app serves every case, the way the gates build one.
app = _app.app

PAGE = demo.PAGE
ROW = demo.ROW_ID


def delivery(device: FakeDevice, frame: dict | None = None):
    """A delivery built the way the app builds one — handlers take the context, not the device."""
    return app.context(device, frame or {})


def walk(node):
    """Every node of a built tree, depth first."""
    if not isinstance(node, dict):
        return
    yield node
    for child in node.get("children") or []:
        yield from walk(child)


def slots(page: dict, key: str) -> set[str]:
    """Every name a tree binds on one channel: a read's `slot`, a write's `dest` (ADR 0039)."""
    field = "dest" if key == "sink" else "slot"
    return {
        node[key][field]
        for node in walk(page)
        if isinstance(node.get(key), dict) and node[key].get(field)
    }


def ops(frames, action: str, slot: str) -> list[dict]:
    return [op for frame in frames for op in frame if op.get("action") == action and op.get("slot") == slot]


class DemoCase(unittest.TestCase):
    """A device standing on /demo, with the player's clocks set to zero."""

    def setUp(self) -> None:
        self.saved = (demo.settings.pace, demo.settings.hold, demo.settings.day, demo.spawn)
        demo.settings.pace = demo.settings.hold = demo.settings.day = 0.0
        demo.spawn = lambda target, args: target(*args)  # the whole story, inline
        self.device = FakeDevice(path=PAGE, app=app)
        self.page()

    def tearDown(self) -> None:
        demo.settings.pace, demo.settings.hold, demo.settings.day, demo.spawn = self.saved

    def page(self):
        """The page the app draws for this address — through the lookup, not around it."""
        ctx = delivery(self.device, {"dest": "reflux:hello", "data": {"path": PAGE}})
        return dump(app.routes.match(PAGE).resolve(ctx))

    def toggle(self) -> None:
        demo.on_toggle(delivery(self.device, {"dest": "demo.toggle", "data": {}}), {})

    def run_inline(self) -> list[list[dict]]:
        self.device.frames.clear()
        self.state().resume.set()  # `play` waits for permission before its first beat; `start` sets it
        demo.play(delivery(self.device))
        return self.device.frames

    def state(self) -> demo.Run:
        return demo.state(delivery(self.device))

    def beat_line(self) -> str:
        """The control's status line as it stands after the frames so far."""
        text = ""
        for op in ops(self.device.frames, "set", "demo.beat"):
            text = ((op.get("data") or {}).get("source") or {}).get("default", text)
        return text

    def control(self) -> str:
        """The label the floating button currently carries."""
        label = ""
        for op in ops(self.device.frames, "set", "demo.control"):
            for node in walk(op.get("data") or {}):
                if node.get("type") == "button":
                    label = ((node.get("source") or {}).get("default")) or label
        return label


class PageShape(DemoCase):
    def test_it_is_one_route_of_the_application(self):
        self.assertIn(PAGE, [route.path for route in app.routes])

    def test_four_regions_each_read_one_slot(self):
        """The island shape: graph / stream (+ pins, echo) / control, one slot each."""
        page = self.page()
        self.assertEqual(slots(page, "source") & {"demo.graph", "demo.stream", "demo.pins", "demo.echo"}, {"demo.graph", "demo.stream", "demo.pins", "demo.echo"})
        self.assertEqual(page["type"], "frame")
        self.assertEqual(len(page["children"]), 3)  # the two columns, then the floating control

    def test_the_control_is_the_one_region_that_is_fixed(self):
        page = self.page()
        floating = [node for node in walk(page) if (node.get("attrs") or {}).get("style", {}).get("position") == "fixed"]
        self.assertEqual(len(floating), 1)
        self.assertEqual(floating[0]["attrs"]["style"]["right"], "24px")

    def test_the_rail_takes_one_tag_and_names_its_dest(self):
        """A landing zone is a frame: `accept` is the pairing rule, `sink` is where the drop goes."""
        page = self.page()
        rail = [node for node in walk(page) if node.get("id") == "rail"]
        self.assertEqual(len(rail), 1)
        self.assertEqual(rail[0]["attrs"]["accept"], {"tag": "snippet"})
        self.assertEqual(rail[0]["sink"]["dest"], "demo.pin")

    def test_the_control_region_is_seeded_once_per_device(self):
        self.device.frames.clear()
        self.page()  # a second look: a slot outlives a create, so nothing is seeded twice
        self.assertEqual(self.device.frames, [])

    def test_every_name_it_writes_is_registered(self):
        """A typo in a `sink` fails here, without a browser."""
        page = self.page()
        written = slots(page, "sink")
        for op in ops(self.run_inline(), "set", "demo.review_form"):  # the row and the form carry sinks too
            written |= slots(op.get("data") or {}, "sink")
        self.assertTrue(written)
        self.assertLessEqual(written, set(app.dests.names()))


class Script(DemoCase):
    def test_every_beat_runs_in_order_and_says_so(self):
        frames = self.run_inline()
        lines = [((op["data"].get("source") or {}).get("default")) for op in ops(frames, "set", "demo.beat")]
        expected = [f"{index}/{len(demo.BEATS)} · {label}" for index, (label, _) in enumerate(demo.BEATS, start=1)]
        self.assertEqual(lines[: len(expected)], expected)
        self.assertTrue(lines[-1].startswith("完"))

    def test_the_row_arrives_once_with_every_child_bound(self):
        frames = self.run_inline()
        appends = ops(frames, "append", "demo.stream")
        self.assertEqual(len(appends), 1)
        row = appends[0]["data"]
        self.assertEqual(row["id"], ROW)
        reads = slots(row, "source")
        self.assertLessEqual(
            {
                "demo.analytics",
                "demo.trend",
                "demo.radar_rd",
                "demo.radar_mkt",
                "demo.radar_ops",
                "demo.summary",
                "demo.review_form",
                "demo.say_car",
                "demo.intro_car",
                "demo.say_shoe",
                "demo.intro_shoe",
                "demo.say_patch",
                "demo.patch_code",
                "demo.say_graph",
            },
            reads,
        )
        self.assertTrue(self.beat_line().startswith("完"))  # nothing was refused on the way

    def test_the_typewriter_appends_three_characters_a_frame(self):
        frames = self.run_inline()
        patches = ops(frames, "patch", "demo.analytics")
        self.assertEqual(len(patches), -(-len(scene.ANALYTICS) // 3))
        self.assertTrue(all(op["path"] == demo.TEXT_VALUE and op["op"] == "append" for op in patches))
        self.assertTrue(all(len(op["value"]) <= 3 for op in patches))
        self.assertEqual("".join(op["value"] for op in patches), scene.ANALYTICS)

    def test_the_line_grows_one_frame_a_day(self):
        frames = self.run_inline()
        sets = ops(frames, "set", "demo.trend")
        self.assertEqual(len(sets), 1)
        self.assertEqual(len(sets[0]["data"]["source"]["default"]["data"]), 45)  # 15 days, three departments
        patches = ops(frames, "patch", "demo.trend")
        self.assertEqual(len(patches), len(scene.TAIL_DAYS) * 3)
        self.assertTrue(all(op["path"] == demo.TREND_DATA and op["op"] == "append" for op in patches))
        self.assertEqual(patches[0]["value"], {"day": "09-18", "avg": 3.53, "dept": "研发部"})
        self.assertEqual(patches[-1]["value"]["day"], "10-02")

    def test_the_radars_carry_five_six_and_seven_axes(self):
        frames = self.run_inline()
        dims = {
            slot: len({row["dim"] for row in ops(frames, "set", f"demo.{slot}")[0]["data"]["source"]["default"]["data"]})
            for slot in ("radar_rd", "radar_mkt", "radar_ops")
        }
        self.assertEqual(dims, {"radar_rd": 5, "radar_mkt": 6, "radar_ops": 7})

    def test_payloads_are_what_the_modules_read(self):
        frames = self.run_inline()
        car = ops(frames, "set", "demo.intro_car")[0]["data"]["source"]["default"]
        self.assertEqual(car["assets"]["scene"], "/assets/splatviewer/truck.ksplat")
        self.assertEqual(car["camera"], scene.TRUCK_CAMERA)
        self.assertEqual(ops(frames, "set", "demo.intro_shoe")[0]["data"]["source"]["default"]["assets"]["shoe"], "/assets/3dbrowser/MaterialsVariantsShoe.glb")
        code = ops(frames, "set", "demo.patch_code")[0]["data"]["source"]["default"]
        self.assertEqual((code["lang"], code["event"]), ("rust", "demo.save"))
        self.assertEqual(code["code"], scene.PATCH_CODE)

    def test_the_graph_grows_and_ends_with_a_focus(self):
        frames = self.run_inline()
        sizes = [len(op["data"]["source"]["default"]["nodes"]) for op in ops(frames, "set", "demo.graph")]
        self.assertEqual(sizes, sorted(sizes))  # cumulative snapshots only ever add
        self.assertEqual(sizes[-1], len(scene.GRAPH_NODES))
        last = ops(frames, "set", "demo.graph")[-1]["data"]["source"]["default"]
        self.assertEqual(last["focus"], {"ids": ["accrete", "content", "transport"], "seq": 1})

    def test_the_review_table_and_the_form_arrive_together(self):
        frames = self.run_inline()
        nodes = ops(frames, "set", "demo.review_form")
        self.assertEqual(len(nodes), 1)
        form = nodes[0]["data"]
        self.assertEqual((form["type"], form["sink"]["dest"], form["attrs"]["submit"]), ("loom", "demo.review", ["enter", "button"]))
        table = [node for node in walk(form) if node.get("type") == "tiles"][0]
        self.assertEqual([field["key"] for field in table["attrs"]["fields"]], ["score", "name", "dept", "avg", "note"])
        self.assertEqual(table["attrs"]["header"]["selector"], "review-head")
        fields = {node["tag"]: node for node in walk(form) if node.get("type") == "input" and node.get("tag")}
        self.assertEqual(sorted(fields), ["cj", "sy", "zw"])  # one packed field per row
        rows = [op["data"]["id"] for op in ops(frames, "append", "demo.review_rows")]
        self.assertEqual(rows, [f"review-{key}" for key, *_ in scene.REVIEW])

    def test_the_rows_are_cells_by_key(self):
        frames = self.run_inline()
        rows = [op["data"] for op in ops(frames, "append", "demo.review_rows")]
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertEqual([cell["attrs"]["selector"] for cell in row["children"]], ["score", "name", "dept", "avg", "note"])


class Control(DemoCase):
    def test_it_reads_idle_play_pause_resume_and_replay(self):
        demo.spawn = lambda target, args: None  # a run that has not started speaking: the states are observable
        self.assertEqual(self.control(), "▶ 播放")
        self.toggle()  # idle -> playing
        self.assertEqual(self.state().phase, "playing")
        self.assertEqual(self.control(), "⏸ 暂停")
        self.toggle()  # playing -> paused
        self.assertEqual(self.state().phase, "paused")
        self.assertEqual(self.control(), "▶ 继续")
        self.assertTrue(self.beat_line().startswith("已暂停"))
        self.toggle()  # paused -> playing
        self.assertEqual(self.state().phase, "playing")
        self.assertEqual(self.control(), "⏸ 暂停")

    def test_a_finished_run_offers_a_replay(self):
        self.toggle()
        self.assertEqual(self.state().phase, "done")
        self.assertEqual(self.control(), "↻ 重播")

    def test_replay_clears_what_the_player_wrote_and_leaves_the_pins(self):
        self.toggle()  # a whole run, inline
        self.device.frames.clear()
        demo.on_pin(delivery(self.device), {"dest": "demo.pin", "id": "rail", "data": {"id": "pin-analytics", "kind": "snippet"}})
        self.device.frames.clear()
        self.toggle()  # replay
        removed = ops(self.device.frames, "remove", "demo.stream")
        self.assertEqual([op["id"] for op in removed], [ROW])
        rows = [op["id"] for op in ops(self.device.frames, "remove", "demo.review_rows")]
        self.assertEqual(rows, [f"review-{key}" for key, *_ in scene.REVIEW])
        self.assertEqual(ops(self.device.frames, "remove", "demo.pins"), [])
        self.assertEqual(self.state().beat, 11)  # the second run played the whole script again
        self.assertTrue(self.beat_line().startswith("完"))


class Pausing(unittest.TestCase):
    """The one case that needs a clock: a pause is a wait, so the text must not be torn."""

    def setUp(self) -> None:
        self.saved = (demo.settings.pace, demo.settings.hold, demo.settings.day, demo.spawn)
        demo.settings.pace, demo.settings.hold, demo.settings.day = 0.004, 0.0, 0.0
        self.device = FakeDevice(path=PAGE, app=app)
        demo.page(delivery(self.device, {"dest": "reflux:hello", "data": {"path": PAGE}}), app.routes.match(PAGE))
        self.device.frames.clear()

    def tearDown(self) -> None:
        demo.settings.pace, demo.settings.hold, demo.settings.day, demo.spawn = self.saved

    def wait_for(self, what, deadline=6.0) -> None:
        end = time.monotonic() + deadline
        while time.monotonic() < end:
            if what():
                return
            time.sleep(0.01)
        self.fail("the script did not reach the state the case waits for")

    def test_pause_stops_the_stream_and_resume_carries_on(self):
        demo.on_toggle(delivery(self.device, {"dest": "demo.toggle", "data": {}}), {})
        self.wait_for(lambda: ops(self.device.frames, "patch", "demo.analytics"))
        demo.on_toggle(delivery(self.device, {"dest": "demo.toggle", "data": {}}), {})  # pause
        quiet = len(self.device.frames)
        time.sleep(0.2)
        self.assertEqual(len(self.device.frames), quiet)  # nothing new while paused
        demo.on_toggle(delivery(self.device, {"dest": "demo.toggle", "data": {}}), {})  # resume
        self.wait_for(lambda: demo.state(delivery(self.device)).phase == "done", deadline=20.0)
        typed = "".join(op["value"] for op in ops(self.device.frames, "patch", "demo.analytics"))
        self.assertEqual(typed, scene.ANALYTICS)  # no chunk lost, none sent twice


class Uplinks(DemoCase):
    def test_a_landed_pin_names_its_cargo(self):
        demo.on_pin(delivery(self.device), {"dest": "demo.pin", "id": "rail", "data": {"id": "pin-analytics", "kind": "snippet"}})
        chips = ops(self.device.frames, "append", "demo.pins")
        self.assertEqual(len(chips), 1)
        self.assertEqual(chips[0]["data"]["id"], "pin-pin-analytics")
        self.assertIn("pin-analytics", self.echo())

    def test_a_pin_without_an_id_is_refused_with_a_reason(self):
        demo.on_pin(delivery(self.device), {"dest": "demo.pin", "data": {}})
        self.assertEqual(ops(self.device.frames, "append", "demo.pins"), [])
        self.assertIn("没有 id", self.echo())

    def test_a_save_reports_the_length_and_language(self):
        demo.on_save(delivery(self.device), {"dest": "demo.save", "data": {"code": "fn main() {}", "lang": "rust"}})
        self.assertIn("12 字", self.echo())
        self.assertIn("rust", self.echo())

    def test_a_save_without_code_is_refused_with_a_reason(self):
        demo.on_save(delivery(self.device), {"dest": "demo.save", "data": {"lang": "rust"}})
        self.assertIn("没有 code", self.echo())

    def test_the_form_reports_what_it_packed(self):
        demo.on_review(delivery(self.device), {"dest": "demo.review", "data": {"zw": 4.13, "cj": False, "sy": "已复核"}})
        line = self.echo()
        self.assertIn("zw=4.13", line)
        self.assertIn("sy='已复核'", line)

    def test_an_empty_submission_says_so(self):
        demo.on_review(delivery(self.device), {"dest": "demo.review", "data": {}})
        self.assertIn("没有字段", self.echo())

    def echo(self) -> str:
        text = ""
        for op in ops(self.device.frames, "set", "demo.echo"):
            text = ((op.get("data") or {}).get("source") or {}).get("default", text)
        return text


if __name__ == "__main__":
    unittest.main()