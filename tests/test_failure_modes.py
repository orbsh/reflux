"""失败模式里这一轮新做的那几条：批量上限、重复 id（生产者侧）、慢客户端。

三条都要求“降级要可见”：上限与重复 id 在发送前大声（`ValueError`），慢客户端丢帧与重同步
走计数（`stats["shed"]` / `stats["resync"]`），不静默。

重复 id 的规则分两层：一棵树里的 id 由 `wire` 在组帧时走（keyed 渲染靠它，重了就是半个列表），
同一帧里给同一个列表槽追加同一个行 id 由服务端的入站校验整帧拒收（见 `tests/test_ingest.py`）。
慢客户端那组不给时钟：flusher 会被“有帧在等”唤醒，写线程在假 channel 的 `send` 里被一个事件
卡住——溢出、标记陈旧、放行后排空并重同步，全是确定性的等待。
"""

from __future__ import annotations

import json
import threading
import time
import unittest

from reflux import wire
from reflux.app import App
from reflux.channel import Channel
from reflux.protocol import MAX_OPS_PER_FRAME
from reflux.sdk import builders as b


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
        def ops(count: int) -> list[dict]:
            return [wire.empty() for _ in range(count)]

        self.assertEqual(len(wire.draw(*ops(MAX_OPS_PER_FRAME))), MAX_OPS_PER_FRAME)
        with self.assertRaises(ValueError):
            wire.draw(*ops(MAX_OPS_PER_FRAME + 1))


class TestDuplicateIds(unittest.TestCase):
    """一棵树里，一个 id 只能落在一个节点上——keyed 渲染靠它。"""

    def test_one_id_twice_in_a_tree_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            wire.create(b.case(b.text("a", id="row-1"), b.text("b", id="row-1")))

    def test_the_same_check_reaches_a_row_template(self) -> None:
        with self.assertRaises(ValueError):
            wire.create(b.rack(item=[b.text("a", id="r"), b.text("b", id="r")]))

    def test_a_slot_value_is_a_node(self) -> None:
        # `set` 换的是槽里那个节点；列表槽的行只走 append／remove，不把一个数组塞进 set
        with self.assertRaises(ValueError):
            wire.set("rows", [{"id": "same"}, {"id": "same"}])  # type: ignore[arg-type]

    def test_unique_ids_pass_and_rows_without_ids_are_legal(self) -> None:
        wire.create(b.case(b.text("a", id="row-1"), b.text("b", id="row-2")))
        wire.create(b.case(b.text("a"), b.text("b")))  # 位置行：没有身份，合法


class TestSlowClient(unittest.TestCase):
    def setUp(self) -> None:
        self.app = App(heartbeat=10.0, dead_after=30.0, outbox=4)
        self.app.page = lambda session, path: b.text("resync")

    def tearDown(self) -> None:
        self.app.stop()

    def test_a_slow_client_sheds_frames_and_resyncs_without_touching_others(self) -> None:
        slow, fast = BlockingChannel(), FastChannel()
        threads = run_connections(self.app, slow, fast)
        slow_session = self.app.sessions[slow]
        fast_session = self.app.sessions[fast]
        try:
            slow_session.draw(wire.patch("x", "/bind/value/default", "first"))  # 让 flusher 进到 send 里
            self.assertTrue(slow.inside.wait(2.0), "flusher 应当已经进到 send 里并被卡住")

            for i in range(12):  # 远超 outbox=4
                slow_session.draw(wire.patch("x", "/bind/value/default", i))

            self.assertGreaterEqual(self.app.stats["shed"], 1, "溢出必须计数")
            self.assertTrue(slow_session.stale, "丢过帧就要标记陈旧")
            self.assertLessEqual(len(slow_session.outbox), 4, "出帧队列是有界的")

            # 别的会话照常：慢客户端不能按住别人
            fast_session.draw(wire.patch("y", "/bind/value/default", "ok"))
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
            self.assertEqual(last[0]["action"], "create", "重同步就是用一帧 create 重画")
            self.assertFalse(slow_session.stale, "重同步之后不再陈旧")
        finally:
            slow.gate.set()
            slow.hold.set()
            fast.hold.set()
            for thread in threads:
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()