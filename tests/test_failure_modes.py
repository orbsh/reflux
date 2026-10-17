"""失败模式里这一轮新做的那几条：批量上限、重复行 id（生产者侧）、慢客户端。

三条都要求"降级要可见"：上限与重复 id 在发送前大声（`ValueError`），慢客户端丢帧与重同步
走计数（`stats["shed"]` / `stats["resync"]`），不静默。

重复 id 的规则是**帧级**的：它由 `ops.draw` 在帧离开时查（一支 op 还没成帧，谈不上"同一帧
里 id 唯一"）。慢客户端那组同样不给时钟：flusher 会被"有帧在等"唤醒，写线程在假 channel 的
`send` 里被一个事件卡住——溢出、标记陈旧、放行后排空并重同步，全是确定性的等待。
"""

from __future__ import annotations

import json
import threading
import time
import unittest

from reflux import ops, ui
from reflux.app import App
from reflux.channel import Channel
from reflux.tables_generated import MAX_OPS_PER_FRAME


class BlockingChannel(Channel):
    """A channel whose writer blocks inside `send` until it is let go."""

    def __init__(self) -> None:
        self.hold = threading.Event()  # keeps the connection in the table
        self.gate = threading.Event()  # the writer waits here until released
        self.inside = threading.Event()  # set once the writer is in `send`
        self.written: list[str] = []
        self.closed_with: int | None = None
        self.aborted = False

    def __iter__(self):
        self.hold.wait()
        yield from ()

    def send(self, text: str) -> None:
        self.inside.set()
        self.gate.wait(5.0)
        self.written.append(text)

    def ping(self, payload: bytes = b"") -> None:
        pass

    def close(self, code: int = 1000) -> None:
        self.closed_with = code

    def abort(self) -> None:
        self.aborted = True


class FastChannel(BlockingChannel):
    def send(self, text: str) -> None:
        self.written.append(text)


def run_connections(app: App, *channels: Channel) -> list[threading.Thread]:
    threads = [
        threading.Thread(target=app.handle, args=(channel,), daemon=True) for channel in channels
    ]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + 2.0
    while len(app.sessions) < len(channels) and time.monotonic() < deadline:
        time.sleep(0.005)
    return threads


class TestFrameCap(unittest.TestCase):
    def test_a_frame_over_the_cap_is_refused_before_it_is_sent(self) -> None:
        one = ops.patch("/slots/x", 1)
        self.assertEqual(len(ops.draw(*[one] * MAX_OPS_PER_FRAME)["ops"]), MAX_OPS_PER_FRAME)
        with self.assertRaises(ValueError):
            ops.draw(*[one] * (MAX_OPS_PER_FRAME + 1))


class TestDuplicateRowIds(unittest.TestCase):
    """一帧之内的节点数组里，行身份必须唯一——keyed 渲染靠它。"""

    def test_a_frame_carrying_a_duplicate_in_a_slot_value_is_refused(self) -> None:
        rows = [ui.text("a", id="row-1"), ui.text("b", id="row-1")]
        with self.assertRaises(ValueError):
            ops.draw(ops.patch("/slots/rows", rows))

    def test_the_same_check_reaches_into_the_tree(self) -> None:
        def page():
            return ui.stack(ui.row(ui.text("a", id="r"), ui.text("b", id="r")))

        with self.assertRaises(ValueError):
            ops.draw(ops.create(page()))
        with self.assertRaises(ValueError):
            ops.draw(ops.insert("/slots/rows", ui.stack(ui.row(ui.text("a", id="r"), ui.text("b", id="r"))), anchor="end"))

    def test_unique_ids_pass_and_rows_without_ids_are_legal(self) -> None:
        ops.draw(ops.patch("/slots/rows", [ui.text("a", id="row-1"), ui.text("b", id="row-2")]))
        ops.draw(ops.patch("/slots/rows", [ui.text("a"), ui.text("b")]))  # 位置行：没有身份，合法
        ops.draw(ops.create(ui.stack(ui.row(ui.text("a", id="r1"), ui.text("b", id="r2")))))

    def test_free_data_in_a_slot_is_not_walked(self) -> None:
        # 槽里放的不是节点时不查 id：那是数据，行身份的规则管不到它
        ops.draw(ops.patch("/slots/rows", [{"id": "same"}, {"id": "same"}]))


class TestSlowClient(unittest.TestCase):
    def setUp(self) -> None:
        self.app = App(heartbeat=10.0, dead_after=30.0, outbox=4)
        self.app.page = lambda session, path: ui.text("resync")

    def tearDown(self) -> None:
        self.app.stop()

    def test_a_slow_client_sheds_frames_and_resyncs_without_touching_others(self) -> None:
        slow, fast = BlockingChannel(), FastChannel()
        threads = run_connections(self.app, slow, fast)
        slow_session = self.app.sessions[slow]
        fast_session = self.app.sessions[fast]
        try:
            slow_session.draw(ops.patch("/slots/x", "first"))  # 让 flusher 进到 send 里
            self.assertTrue(slow.inside.wait(2.0), "flusher 应当已经进到 send 里并被卡住")

            for i in range(12):  # 远超 outbox=4
                slow_session.draw(ops.patch("/slots/x", i))

            self.assertGreaterEqual(self.app.stats["shed"], 1, "溢出必须计数")
            self.assertTrue(slow_session.stale, "丢过帧就要标记陈旧")
            self.assertLessEqual(len(slow_session.outbox), 4, "出帧队列是有界的")

            # 别的会话照常：慢客户端不能按住别人
            fast_session.draw(ops.patch("/slots/y", "ok"))
            deadline = time.monotonic() + 2.0
            while not fast.written and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(fast.written, "另一个会话的帧照常落地")

            slow.gate.set()
            deadline = time.monotonic() + 3.0
            while self.app.stats["resync"] < 1 and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertGreaterEqual(self.app.stats["resync"], 1, "排空后必须重同步一帧")
            last = json.loads(slow.written[-1])
            self.assertEqual(last["ops"][0]["op"], "create", "重同步就是用一帧 create 重画")
            self.assertFalse(slow_session.stale, "重同步之后不再陈旧")
        finally:
            slow.gate.set()
            slow.hold.set()
            fast.hold.set()
            for thread in threads:
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()