"""The model seam: one conversation in, a stream of chunks out.

Two implementations, because an example has to run on a bare `python3`:

- `Scripted` — offline and deterministic. Its reply states what the *backend* just did (turn count,
  window size, chunk delay), so a demo run reads as documentation rather than as canned prose.
- `OpenAI` — an OpenAI-compatible `/chat/completions` client over SSE. Configured by environment
  (`OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`) and **not exercised against a live endpoint
  in this repo**: the SSE reader is tested against a local stub (`tests/test_chat_example.py`), which
  is the part that can be wrong independently of the provider.

The seam is deliberately one method. A chat backend needs three things from a model — context in,
chunks out, failure visible — and nothing here knows how a chunk becomes a frame.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Iterable, Iterator, Protocol

__all__ = ["CHUNK", "Model", "OpenAI", "Scripted", "Turn", "parse_sse"]

CHUNK = 3  # characters per chunk for the scripted model — about one CJK token


@dataclass(frozen=True)
class Turn:
    """One message in a conversation. `role` is `user` or `assistant`."""

    role: str
    text: str


class Model(Protocol):
    """What the app needs from a model: a name for the status line, and a stream of chunks."""

    name: str

    def reply(self, context: list[Turn]) -> Iterator[str]: ...


class Scripted:
    """Offline, deterministic, no key: the default, so a demo run is one command.

    The reply is a function of the context — turn number, the last question, the window — not a
    fixed string, so a walkthrough that sends three messages reads three different replies.
    """

    name = "scripted"

    def __init__(self, window: int = 12) -> None:
        self.window = window  # only used to describe the window in the reply; pacing is the app's

    def reply(self, context: list[Turn]) -> Iterator[str]:
        yield from scripted_reply(context, self.window)


def scripted_reply(context: list[Turn], window: int) -> Iterator[str]:
    """The scripted model's answer, chunk by chunk. Pure, so a test can assert on it."""
    asked = next((turn.text for turn in reversed(context) if turn.role == "user"), "")
    turns = sum(1 for turn in context if turn.role == "user")
    body = (
        f"第 {turns} 轮收到：「{asked[:40]}{'…' if len(asked) > 40 else ''}」\n\n"
        f"这句话是后端一块一块流出来的：每块 {CHUNK} 个字，块与块之间隔一小段时间。"
        f"窗口里现在有 {len(context)} 条消息（上限 {window} 条，超了从头裁）。"
        "按「停止」会在块边界停住——半句话不会进下一轮的上下文，因为它会污染模型对上一问的理解。"
    )
    for at in range(0, len(body), CHUNK):
        yield body[at : at + CHUNK]


class OpenAI:
    """An OpenAI-compatible streaming client. Stdlib only; proxies come from the environment.

    `reply` yields the provider's own deltas — chunk sizes belong to the model, not to us.
    """

    name = "openai"

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.model = model or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY", "")
        self.timeout = timeout

    def request(self, context: list[Turn]) -> urllib.request.Request:
        body = json.dumps(
            {
                "model": self.model,
                "stream": True,
                "messages": [{"role": turn.role, "content": turn.text} for turn in context],
            }
        ).encode("utf-8")
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"
        return urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body, headers=headers, method="POST"
        )

    def reply(self, context: list[Turn]) -> Iterator[str]:
        with urllib.request.urlopen(self.request(context), timeout=self.timeout) as response:
            yield from parse_sse(response)


def parse_sse(lines: Iterable[bytes]) -> Iterator[str]:
    """The text of each `data:` event that carries a delta; `[DONE]` ends the run.

    Kept separate from the request so the reader can be tested against a stub: providers differ in
    how they frame events (`event:`, comments, blank lines), not in `data: {...}` — and a
    `choices[0].delta.content` that is absent or null is a role-only or finish-only event, not text.
    """
    for raw in lines:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line or line.startswith(":") or not line.startswith("data:"):
            continue
        data = line[len("data:") :].strip()
        if data == "[DONE]":
            return
        try:
            event = json.loads(data)
        except ValueError:
            continue  # a keep-alive or a provider's own prose; not a delta
        choices = event.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        piece = delta.get("content")
        if isinstance(piece, str) and piece:
            yield piece