"""模型接缝：一段对话进去，一串分块出来。

两个实现，因为示例要能在光秃秃的 `python3` 上跑：

- `Scripted` —— 离线、确定。它的回话把**后端**刚做了什么说出来（第几轮、窗口多大、块间多慢），
  所以一次演示读起来像文档，而不是罐头文案。
- `OpenAI` —— OpenAI 兼容的 `/chat/completions` 流式客户端（SSE）。由环境变量配置
  （`OPENAI_BASE_URL`、`OPENAI_API_KEY`、`OPENAI_MODEL`），**本仓没有对真实端点跑过**：SSE 读取器是
  拿本地桩测的（`tests/test_chat_example.py`），因为那一半能独立于厂商出错。

接缝故意只有这一个方法。聊天后端需要模型给三样东西——上下文进去、分块出来、失败看得见——而这里
没有任何一处知道「一块怎么变成一帧」。
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Iterable, Iterator, Protocol

__all__ = ["CHUNK", "Model", "OpenAI", "Scripted", "Turn", "parse_sse"]

CHUNK = 3  # 脚本模型每块几个字符——约等于一个中文词元


@dataclass(frozen=True)
class Turn:
    """对话里的一条消息。`role` 是 `user` 或 `assistant`。"""

    role: str
    text: str


class Model(Protocol):
    """应用需要模型提供的东西：状态行上的一个名字，和一串分块。"""

    name: str

    def reply(self, context: list[Turn]) -> Iterator[str]: ...


class Scripted:
    """离线、确定、不要 key：缺省实现，所以演示就一条命令。

    回话是上下文的函数——第几轮、上一句问的什么、窗口多大——不是固定字符串，所以走三句的走查会
    读到三段不同的回答。
    """

    name = "scripted"

    def __init__(self, window: int = 12) -> None:
        self.window = window  # 只用来在回话里描述窗口；节奏是应用的事

    def reply(self, context: list[Turn]) -> Iterator[str]:
        yield from scripted_reply(context, self.window)


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
    """OpenAI 兼容的流式客户端。只用标准库；代理从环境变量来。

    `reply` 产出的是厂商自己的增量——块多大是模型的事，不是我们的事。
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
    """每个带增量的 `data:` 事件里的文本；`[DONE]` 结束整段。

    与请求分开，是为了这个读取器能对着桩测：厂商的差别在怎么包事件（`event:`、注释行、空行），
    不在 `data: {...}` —— 而 `choices[0].delta.content` 缺失或为 null 的事件是只带角色、只带结束的，
    不是文本。
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
            continue  # keep-alive 或厂商自己的说明文字；不是增量
        choices = event.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        piece = delta.get("content")
        if isinstance(piece, str) and piece:
            yield piece