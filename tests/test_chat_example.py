"""The chat example's backend, offline: no browser, no WebSocket, no model provider.

`tools/gate_chat.py` covers the same behaviour over a real socket; these cases pin the parts that are
pure — the window, the refusals, the chunk stream, the failure surface, and the SSE reader (against a
stub, since there is no key on this machine to call a real provider with).
"""

from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from examples.app import chat
from examples.app.model import CHUNK, OpenAI, Turn, parse_sse, scripted_reply
from tests.fakes import FakeDevice


def context(device: FakeDevice, frame: dict | None = None):
    """A delivery built the way the app builds one — handlers take the context, not the device."""
    return chat.app.context(device, frame)


def status_text(device: FakeDevice) -> str:
    """The last status line a run of frames wrote."""
    for frame in reversed(device.frames):
        for op in frame:
            if op.get("action") == "set" and op.get("slot") == "status":
                return ((op.get("data") or {}).get("bind") or {}).get("value", {}).get("default", "")
    return ""


def patched(device: FakeDevice) -> str:
    """Everything the run appended into slots, in order."""
    out = []
    for frame in device.frames:
        for op in frame:
            if op.get("action") == "patch" and isinstance(op.get("value"), str):
                out.append(op["value"])
    return "".join(out)


class ScriptedModel(unittest.TestCase):
    def test_the_reply_is_deterministic_and_chunked(self):
        context = [Turn("user", "你好")]
        once = list(scripted_reply(context, 12))
        twice = list(scripted_reply(context, 12))
        self.assertEqual(once, twice)
        self.assertEqual(len(once[0]), CHUNK)
        self.assertTrue(all(len(chunk) <= CHUNK for chunk in once))
        self.assertIn("你好", "".join(once))

    def test_it_states_the_window_and_the_turn_number(self):
        text = "".join(scripted_reply([Turn("user", "一"), Turn("assistant", "二"), Turn("user", "三")], 7))
        self.assertIn("第 2 轮", text)  # two user turns so far
        self.assertIn("上限 7 条", text)

    def test_it_reads_the_last_question_not_the_first(self):
        text = "".join(scripted_reply([Turn("user", "旧问题"), Turn("user", "新问题")], 12))
        self.assertIn("新问题", text)


class Window(unittest.TestCase):
    def test_turns_are_trimmed_and_counted(self):
        conversation = chat.Chat(model=chat.Scripted(), window=4)
        for i in range(6):
            conversation.record("user", f"第 {i} 条")
        self.assertEqual(len(conversation.turns), 4)
        self.assertEqual([t.text for t in conversation.turns], ["第 2 条", "第 3 条", "第 4 条", "第 5 条"])
        self.assertEqual(conversation.trimmed, 2)
        self.assertEqual(conversation.total, 6)

    def test_the_status_line_reports_both_counts(self):
        conversation = chat.Chat(model=chat.Scripted(), window=2)
        for i in range(5):
            conversation.record("user", f"m{i}")
        line = conversation.status()
        self.assertIn("5 轮", line)  # everything ever recorded
        self.assertIn("窗口 2/2", line)
        self.assertIn("裁掉 3", line)


class Refusals(unittest.TestCase):
    def setUp(self):
        self.device = FakeDevice()
        self.conversation = chat.Chat(model=chat.Scripted(), delay=0.0)

    def test_an_empty_message_is_refused_with_a_reason(self):
        chat.send(context(self.device), self.conversation, "   ")
        self.assertEqual(status_text(self.device), "空消息没有发出去")
        self.assertEqual(len(self.device.frames), 1)  # one status line, no rows
        self.assertEqual(self.conversation.total, 0)

    def test_an_oversized_message_is_refused_at_the_apps_own_boundary(self):
        chat.send(context(self.device), self.conversation, "字" * (chat.MAX_CHARS + 1))
        self.assertIn("太长", status_text(self.device))
        self.assertIn(str(chat.MAX_CHARS), status_text(self.device))
        self.assertEqual(self.conversation.total, 0)

    def test_a_second_message_while_streaming_is_refused_not_dropped(self):
        self.conversation.busy = True
        chat.send(context(self.device), self.conversation, "再说一句")
        self.assertEqual(status_text(self.device), "上一条还在流：按「停止」或等它结束")
        self.assertEqual(self.conversation.total, 0)

    def test_accepted_message_puts_two_rows_on_screen(self):
        device, conversation = self.device, self.conversation
        original = chat.spawn
        chat.spawn = lambda target, args: None  # do not start the reply: this case is the send
        try:
            chat.send(context(device), conversation, "你好")
        finally:
            chat.spawn = original
        ops = [op for frame in device.frames for op in frame]
        actions = [op.get("action") for op in ops]
        self.assertEqual(actions, ["append", "append", "set", "set"])
        self.assertEqual(ops[0]["slot"], "messages")
        self.assertEqual(ops[1]["data"]["id"], "row-bot-1")
        self.assertEqual(ops[2]["slot"], "reply.1")
        self.assertTrue(conversation.busy)
        self.assertEqual([t.role for t in conversation.turns], ["user"])


class Streaming(unittest.TestCase):
    def setUp(self):
        self.device = FakeDevice()
        self.conversation = chat.Chat(model=chat.Scripted(window=12), delay=0.0)

    def test_a_reply_lands_chunk_by_chunk_and_becomes_a_turn(self):
        chat.stream(context(self.device), self.conversation, context(self.device).slot("reply.1"), [Turn("user", "你好")])
        expected = "".join(scripted_reply([Turn("user", "你好")], 12))
        self.assertEqual(patched(self.device), expected)
        self.assertGreater(len(self.device.frames), 3)  # many small patches, not one write
        self.assertEqual([t.role for t in self.conversation.turns], ["assistant"])
        self.assertFalse(self.conversation.busy)
        self.assertIn("就绪", status_text(self.device))

    def test_stop_keeps_the_half_sentence_out_of_the_context(self):
        conversation = self.conversation

        class Stoppable:
            name = "stoppable"

            def reply(self, context):
                for i, piece in enumerate("abcdefghij"):
                    if i == 3:
                        conversation.stop.set()  # the user pressed 停止 mid-stream
                    yield piece

        conversation.model = Stoppable()
        chat.stream(context(self.device), conversation, context(self.device).slot("reply.1"), [Turn("user", "hi")])
        landed = patched(self.device)
        self.assertTrue(landed.startswith("abc"), landed)  # stopped at a chunk boundary
        self.assertIn("⏹", landed)  # and says so in the bubble itself
        self.assertTrue(5 > len(landed.replace(" ⏹", "")))
        self.assertEqual(conversation.turns, [])  # nothing half-finished enters the context
        self.assertIn("已停止", status_text(self.device))
        self.assertFalse(conversation.busy)

    def test_a_failing_model_becomes_a_bubble_not_a_raise(self):
        class Broken:
            name = "broken"

            def reply(self, context):
                raise RuntimeError("boom")
                yield  # pragma: no cover — the protocol needs a generator

        self.conversation.model = Broken()
        chat.stream(context(self.device), self.conversation, context(self.device).slot("reply.1"), [Turn("user", "hi")])
        self.assertIn("模型出错：boom", patched(self.device))
        self.assertTrue(status_text(self.device).startswith("出错：RuntimeError"))
        self.assertFalse(self.conversation.busy)
        self.assertEqual(self.conversation.turns, [])


class OneExchange(unittest.TestCase):
    """The shape `fluxen/docs/interaction-patterns.md` names, as the example actually sends it.

    A cross-repo contract is only worth its prose if something fails when it breaks, so these are
    the three that matter: the fact lands before the picture, the batch carries the row the bubble
    and the region, and every later frame addresses only what the batch built.
    """

    def setUp(self) -> None:
        self.device = FakeDevice()
        self.conversation = chat.Chat(model=chat.Scripted(window=12), delay=0.0)

    def sent(self) -> None:
        """Send one message with the reply held back — `send` is the subject in the first two cases."""
        original = chat.spawn
        chat.spawn = lambda target, args: None
        try:
            chat.send(context(self.device), self.conversation, "你好")
        finally:
            chat.spawn = original

    def test_the_fact_lands_before_the_first_frame_leaves(self):
        conversation, device = self.conversation, self.device
        recorded: list[int] = []
        emit = device.emit

        def capture(*ops):
            recorded.append(len(conversation.turns))  # what the fact count was when this frame left
            emit(*ops)

        device.emit = capture
        self.sent()
        self.assertEqual(recorded[0], 1)  # the turn was a fact already when the picture went out
        self.assertEqual([t.role for t in conversation.turns], ["user"])

    def test_one_batch_carries_the_row_the_bubble_and_the_region(self):
        self.sent()
        self.assertEqual(len(self.device.frames), 1)  # one turn is one frame
        frame = self.device.frames[0]
        self.assertEqual([op["action"] for op in frame], ["append", "append", "set", "set"])
        self.assertEqual(frame[0]["data"]["id"], "row-user-1")
        self.assertEqual(frame[1]["data"]["id"], "row-bot-1")
        self.assertEqual(frame[1]["data"]["children"][0]["bind"]["value"]["source"], "reply.1")
        self.assertEqual(frame[2]["slot"], "reply.1")  # the region the bubble reads, made in the same batch

    def test_every_later_frame_only_addresses_that_region(self):
        original = chat.spawn
        chat.spawn = lambda target, args: target(*args)  # the whole reply, inline
        try:
            chat.send(context(self.device), self.conversation, "你好")
        finally:
            chat.spawn = original
        later = self.device.frames[1:]
        self.assertGreater(len(later), 3)
        for frame in later[:-1]:
            self.assertEqual([op["action"] for op in frame], ["patch"])
            self.assertEqual([op["slot"] for op in frame], ["reply.1"])  # nothing re-paints the stage
        self.assertEqual([op["slot"] for op in later[-1]], ["status"])  # the end is said


class Frames(unittest.TestCase):
    def test_the_page_draws_and_seeds_its_slot_once(self):
        device = FakeDevice()
        match = chat.app.routes.match("/chat")
        ctx = context(device)
        self.assertIsNone(chat.page(ctx, match))  # a page handler says nothing by returning
        page = ctx.take_page()
        self.assertEqual(page.type, "case")  # it drew a page instead
        self.assertEqual(len(device.frames), 1)  # the seed left as a send, once
        self.assertEqual(device.frames[0][0]["action"], "set")
        self.assertEqual(device.frames[0][0]["slot"], "status")
        chat.page(ctx, match)  # a second look seeds nothing new
        self.assertEqual(len(device.frames), 1)

    def test_the_page_is_one_route_of_the_application(self):
        """A second address is the table's business now, not this page's: `/chat` or nothing."""
        self.assertEqual([route.path for route in chat.app.routes], ["/", "/chat"])
        self.assertIsNone(chat.app.routes.match("/nope"))

    def test_prompt_unwraps_the_renderers_field_shape(self):
        self.assertEqual(chat.prompt_of({"data": {"text": {"data": "你好"}}}), "你好")
        self.assertEqual(chat.prompt_of({"data": {"text": "你好"}}), "你好")  # a bare field
        self.assertIsNone(chat.prompt_of({"data": {}}))
        self.assertIsNone(chat.prompt_of({"data": {"text": {"data": 3}}}))
        self.assertIsNone(chat.prompt_of({}))


class Sse(unittest.TestCase):
    def test_only_text_deltas_come_through(self):
        lines = [
            b": keep-alive\n",
            b"\n",
            b"event: message\n",
            b'data: {"choices":[{"delta":{"role":"assistant"}}]}\n',
            b'data: {"choices":[{"delta":{"content":"\xe4\xbd\xa0"}}]}\n',
            b'data: {"choices":[{"delta":{"content":null},"finish_reason":"stop"}]}\n',
            b"data: [DONE]\n",
            b'data: {"choices":[{"delta":{"content":"never"}}]}\n',
        ]
        self.assertEqual(list(parse_sse(lines)), ["你"])

    def test_a_broken_line_does_not_end_the_run(self):
        lines = [b"data: not json\n", b'data: {"choices":[{"delta":{"content":"ok"}}]}\n']
        self.assertEqual(list(parse_sse(lines)), ["ok"])

    def test_an_event_without_choices_is_skipped(self):
        self.assertEqual(list(parse_sse([b'data: {"error":{"message":"nope"}}\n'])), [])


class _Stub(BaseHTTPRequestHandler):
    """A one-shot SSE endpoint: enough to exercise the client's request and reader."""

    seen: dict = {}

    def do_POST(self) -> None:  # noqa: N802 — http.server's spelling
        length = int(self.headers.get("content-length") or 0)
        type(self).seen = {
            "path": self.path,
            "auth": self.headers.get("authorization"),
            "body": json.loads(self.rfile.read(length) or b"{}"),
        }
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.end_headers()
        for line in (
            b": hello\n\n",
            b'data: {"choices":[{"delta":{"role":"assistant"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"\xe4\xbd\xa0\xe5\xa5\xbd"}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"\xef\xbc\x8c\xe4\xb8\x96\xe7\x95\x8c"}}]}\n\n',
            b"data: [DONE]\n\n",
        ):
            self.wfile.write(line)
            self.wfile.flush()

    def log_message(self, format, *args) -> None:  # keep the test output clean
        pass


class OpenAIClient(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Stub)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_it_asks_for_a_stream_and_yields_the_deltas(self):
        client = OpenAI(model="stub-1", base_url=f"http://127.0.0.1:{self.port}/v1", api_key="test-key")
        pieces = list(client.reply([Turn("user", "打个招呼")]))
        self.assertEqual(pieces, ["你好", "，世界"])
        seen = _Stub.seen
        self.assertEqual(seen["path"], "/v1/chat/completions")
        self.assertEqual(seen["auth"], "Bearer test-key")
        self.assertTrue(seen["body"]["stream"])
        self.assertEqual(seen["body"]["model"], "stub-1")
        self.assertEqual(seen["body"]["messages"], [{"role": "user", "content": "打个招呼"}])


if __name__ == "__main__":
    unittest.main()