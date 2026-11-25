"""The model seam, English tree: one conversation in, a stream of chunks out (an async iterator,
ADR 0002 P4).

Two implementations, because an example has to run on a bare `python3`:

- `Scripted` — offline and deterministic. Its reply states what the *backend* just did (turn count,
  window size, chunk delay), so a demo run reads as documentation rather than as canned prose.
- `OpenAI` — an OpenAI-compatible `/chat/completions` client over SSE that reads through the
  framework's **shared** `ClientSession` (`app.http`, built in `@app.startup`): `demo_app`'s startup
  hook hands it over, so this class neither builds a pool nor closes one. Configured by environment
  (`OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`) and **not exercised against a live endpoint
  in this repo**: the SSE reader is tested against a local stub (`tests/test_chat_example.py`), which
  is the part that can be wrong independently of the provider.

The seam is deliberately one method. A chat backend needs three things from a model — context in,
chunks out, failure visible — and nothing here knows how a chunk becomes a frame. `reply` is an
**async iterator**: the model is a remote system, and waiting for its bytes should not hold a thread.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, AsyncIterator, Iterable, Iterator, Protocol

__all__ = [
    "CHUNK",
    "END",
    "Model",
    "OpenAI",
    "Scripted",
    "Turn",
    "parse_sse",
    "parse_sse_async",
    "scripted_reply",
    "sse_piece",
]

CHUNK = 3  # characters per chunk for the scripted model — about one CJK token


@dataclass(frozen=True)
class Turn:
    """One message in a conversation. `role` is `user` or `assistant`."""

    role: str
    text: str


class Model(Protocol):
    """What the app needs from a model: a name for the status line, and a stream of chunks."""

    name: str

    def reply(self, context: list[Turn]) -> AsyncIterator[str]: ...


class Scripted:
    """Offline, deterministic, no key: the default, so a demo run is one command.

    The reply is a function of the context — turn number, the last question, the window — not a
    fixed string, so a walkthrough that sends three messages reads three different replies.
    """

    name = "scripted"

    def __init__(self, window: int = 12) -> None:
        self.window = window  # only used to describe the window in the reply; pacing is the app's

    async def reply(self, context: list[Turn]) -> AsyncIterator[str]:
        for piece in scripted_reply(context, self.window):
            yield piece


def scripted_reply(context: list[Turn], window: int) -> Iterator[str]:
    """The scripted model's answer, chunk by chunk. Pure, so a test can assert on it."""
    asked = next((turn.text for turn in reversed(context) if turn.role == "user"), "")
    turns = sum(1 for turn in context if turn.role == "user")
    body = (
        f"Turn {turns}, heard: \"{asked[:40]}{'…' if len(asked) > 40 else ''}\"\n\n"
        f"This sentence is streamed by the backend chunk by chunk: {CHUNK} characters each, with a"
        f" short pause between them. The window holds {len(context)} messages now (cap {window};"
        " anything older is trimmed from the front). Pressing Stop stops at a chunk boundary — the half"
        " sentence stays out of the next turn's context, because it would corrupt what the model thinks"
        " the last question was."
    )
    for at in range(0, len(body), CHUNK):
        yield body[at : at + CHUNK]


class OpenAI:
    """An OpenAI-compatible streaming client that reads through the framework's session.

    `reply` yields the provider's own deltas — chunk sizes belong to the model, not to us. The
    session comes from `http` (`demo_app` puts `app.http` there in `@app.startup`): one app, one
    pool, and the model does not own it.
    """

    name = "openai"

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 120.0,
        http: Any = None,
    ) -> None:
        self.model = model or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY", "")
        self.timeout = timeout
        self.http = http  # aiohttp's ClientSession; handed over by the startup hook

    def parts(self, context: list[Turn]) -> tuple[str, dict, dict]:
        """(url, body, headers) — the request's shape on its own, so a stub server can assert it."""
        body = {
            "model": self.model,
            "stream": True,
            "messages": [{"role": turn.role, "content": turn.text} for turn in context],
        }
        headers = {"authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        return f"{self.base_url}/chat/completions", body, headers

    async def reply(self, context: list[Turn]) -> AsyncIterator[str]:
        session = self.http
        if session is None:
            raise RuntimeError(
                "OpenAI needs app.http: set `model.http = app.http` in @app.startup (ADR 0002 §7)"
            )
        url, body, headers = self.parts(context)
        timeout = session.timeout if self.timeout is None else self.timeout
        async with session.post(url, json=body, headers=headers, timeout=timeout) as response:
            response.raise_for_status()
            async for piece in parse_sse_async(response.content):
                yield piece


# `data: [DONE]` — the stream is over, which is not the same thing as "this line carries nothing".
END = object()


def sse_piece(raw: bytes) -> str | None | object:
    """What one SSE line says: a piece of text, None (no delta on this line), or `END` (`[DONE]`).

    Kept separate from the request so the reader can be tested against a stub: providers differ in
    how they frame events (`event:`, comments, blank lines), not in `data: {...}` — and a
    `choices[0].delta.content` that is absent or null is a role-only or finish-only event, not text.
    """
    line = raw.decode("utf-8", errors="replace").strip()
    if not line or line.startswith(":") or not line.startswith("data:"):
        return None
    data = line[len("data:") :].strip()
    if data == "[DONE]":
        return END
    try:
        event = json.loads(data)
    except ValueError:
        return None  # a keep-alive or a provider's own prose; not a delta
    choices = event.get("choices") or []
    if not choices:
        return None
    delta = choices[0].get("delta") or {}
    piece = delta.get("content")
    return piece if isinstance(piece, str) and piece else None


def parse_sse(lines: Iterable[bytes]) -> Iterator[str]:
    """The synchronous reader: for lines already in hand (tests, an offline replay)."""
    for raw in lines:
        piece = sse_piece(raw)
        if piece is END:
            return
        if isinstance(piece, str):
            yield piece


async def parse_sse_async(lines: AsyncIterator[bytes]) -> AsyncIterator[str]:
    """The async reader: `response.content` is an async iterator of byte lines, so waiting for bytes
    suspends a coroutine instead of holding a thread."""
    async for raw in lines:
        piece = sse_piece(raw)
        if piece is END:
            return
        if isinstance(piece, str):
            yield piece