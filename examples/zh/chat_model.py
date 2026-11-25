"""模型接缝：一段对话进去，一串分块出来（异步迭代，ADR 0002 P4）。

两个实现，因为示例要能在光秃秃的 `python3` 上跑：

- `Scripted` —— 离线、确定。它的回话把**后端**刚做了什么说出来（第几轮、窗口多大、块间多慢），
  所以一次演示读起来像文档，而不是罐头文案。
- `OpenAI` —— OpenAI 兼容的 `/chat/completions` 流式客户端（SSE），**读的是框架共享的那个
  `ClientSession`**（`app.http`，在 `@app.startup` 里建）：它由 `demo_app` 的启动钩子塞进来，所以
  这个类自己不建连接池、也不关它。由环境变量配置（`OPENAI_BASE_URL`、`OPENAI_API_KEY`、
  `OPENAI_MODEL`）。**本仓没有对真实端点跑过**：SSE 读取器是拿本地桩测的
  （`tests/test_chat_example.py`），因为那一半能独立于厂商出错。

接缝故意只有这一个方法。聊天后端需要模型给三样东西——上下文进去、分块出来、失败看得见——而这里
没有任何一处知道「一块怎么变成一帧」。`reply` 是**异步迭代器**：模型是远端系统，等它的字节不该
占一个线程。
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

CHUNK = 3  # 脚本模型每块几个字符——约等于一个中文词元


@dataclass(frozen=True)
class Turn:
    """对话里的一条消息。`role` 是 `user` 或 `assistant`。"""

    role: str
    text: str


class Model(Protocol):
    """应用需要模型提供的东西：状态行上的一个名字，和一串分块。"""

    name: str

    def reply(self, context: list[Turn]) -> AsyncIterator[str]: ...


class Scripted:
    """离线、确定、不要 key：缺省实现，所以演示就一条命令。

    回话是上下文的函数——第几轮、上一句问的什么、窗口多大——不是固定字符串，所以走三句的走查会
    读到三段不同的回答。
    """

    name = "scripted"

    def __init__(self, window: int = 12) -> None:
        self.window = window  # 只用来在回话里描述窗口；节奏是应用的事

    async def reply(self, context: list[Turn]) -> AsyncIterator[str]:
        for piece in scripted_reply(context, self.window):
            yield piece


def scripted_reply(context: list[Turn], window: int) -> Iterator[str]:
    """脚本模型的回答，一块一块给。纯函数，所以测试可以直接断言它。"""
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
    """OpenAI 兼容的流式客户端，读的是框架共享的会话。

    `reply` 产出的是厂商自己的增量——块多大是模型的事，不是我们的事。会话从 `http` 来
    （`demo_app` 在 `@app.startup` 里放的就是 `app.http`）：一个应用一个连接池，模型不拥有它。
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
        self.http = http  # aiohttp 的 ClientSession；启动钩子给的

    def parts(self, context: list[Turn]) -> tuple[str, dict, dict]:
        """(url, body, headers) —— 请求的形状单独拿出来，所以桩服务器能逐字断言它。"""
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


# `data: [DONE]` —— 流说完了，与"这一行什么都不带"是两件事。
END = object()


def sse_piece(raw: bytes) -> str | None | object:
    """一行 SSE 说了什么：一段文本、None（这行没有增量）、或 `END`（`[DONE]`）。

    与请求分开，是为了这个读取器能对着桩测：厂商的差别在怎么包事件（`event:`、注释行、空行），
    不在 `data: {...}` —— 而 `choices[0].delta.content` 缺失或为 null 的事件是只带角色、只带结束的，
    不是文本。
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
        return None  # keep-alive 或厂商自己的说明文字；不是增量
    choices = event.get("choices") or []
    if not choices:
        return None
    delta = choices[0].get("delta") or {}
    piece = delta.get("content")
    return piece if isinstance(piece, str) and piece else None


def parse_sse(lines: Iterable[bytes]) -> Iterator[str]:
    """同步读器：给已经拿在手里的行用一个（测试、离线重放）。"""
    for raw in lines:
        piece = sse_piece(raw)
        if piece is END:
            return
        if isinstance(piece, str):
            yield piece


async def parse_sse_async(lines: AsyncIterator[bytes]) -> AsyncIterator[str]:
    """异步读器：`response.content` 就是一个异步字节行迭代器，等字节挂起的是协程不是线程。"""
    async for raw in lines:
        piece = sse_piece(raw)
        if piece is END:
            return
        if isinstance(piece, str):
            yield piece