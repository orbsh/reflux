"""参考应用的槽名：一个 Protocol、一个取值函数，和导航的四个地址。

槽名在 wire 上是个字符串（框架的 `slots.py`），而框架的表对任何被问到的名字都给一个 `Slot` 句柄 ——
`Slots.__getattr__ -> Slot`，没有词表。所以页面需要的检查只能来自一个把它们写出来的 Protocol，这个
模块就是那份清单：应用说的所有名字在一处，以及页面拿到它们的两条路。

    slots_of(ctx)        页面这一侧的表，带投递 —— 写入走它（`set`、`append`）
    table(app)           应用的表，不带投递 —— 地址走它（`sink=`、`source=`、`@app.on(...)`）

第二条就是 `@app.on` 能有补全的原因：`App.slot` 的类型是 `Slots`，它的 `__getattr__` 接受任何名字，
于是那里的拼写错误会注册一个永远没人发的处理器，而且悄无声息。把表取一次、标上类型，就把检查移到
写名字的那一行。
"""

from __future__ import annotations

from typing import Any, Protocol

from reflux.app import Context
from reflux.slots import Slot

__all__ = ["DemoSlots", "GO", "GO_ABOUT", "GO_CHAT", "GO_DEMO", "GO_HOME", "slots_of", "table"]


class _Change(Protocol):
    """`name` 这一族：一个 input 的上行是 `name.change`。"""

    change: Slot


class _Row(Protocol):
    """`row` 这一族。`remove` 在 `Slot` 上是动词，所以那个名字要下标访问。"""

    add: Slot

    def __getitem__(self, name: str) -> Slot: ...


class _Vault(Protocol):
    vault: Slot
    secret: Slot


class _Chat(Protocol):
    """对话页的两条上行：输入框的发送，和结束一次回答的停止。"""

    send: Slot
    stop: Slot


class _Go(Protocol):
    """导航的四个去处 —— frame 的 `dest` 就是名字。
    """

    home: Slot
    about: Slot
    demo: Slot
    chat: Slot


class DemoSlots(Protocol):
    """参考应用的槽，给编辑器看的 —— 运行时只看见名字。
    
        两半：页面**写**的那些（`echo`、`rows`…… 走 `slots_of(ctx)`，带投递），和页面**寻址**的
        那些（`name.change`、`row.add`、`go.home`…… 走 `table(app)`，不带投递）。一个协议，因为它们是
        一个名字空间：一帧上行的 sink 和回答它的处理器就是同一个名字。
    """

    echo: Slot  # 输入框最后带来的是什么
    rows: Slot  # tiles 节点读的那个列表
    archived: Slot  # 最近一次落点归档了什么 —— 文本槽，由落点处理器写
    secret: Slot  # 只有已登录的点击才写；每次匿名绘制都清掉
    routes: Slot  # 外壳的读槽 —— 页面写在这里

    messages: Slot  # 对话页的记录 —— 列表槽，一条气泡追加一次
    status: Slot  # 对话页的状态行

    name: _Change
    row: _Row
    vault: _Vault
    go: _Go
    chat: _Chat

    def __call__(self, path: str) -> Slot: ...  # `reflux:login`、`reflux:logout`、`reflux:auth`

    #（登录表单的答复是框架的：落在保留的 `auth` 区）


def slots_of(ctx: Context) -> DemoSlots:
    """参考应用这一次投递的槽 —— 页面写东西用的那些名字。"""
    return ctx.slot  # type: ignore[return-value]


def table(app: Any) -> DemoSlots:
    """应用自己的表，带上类型 —— 它寻址的那些名字：`@app.on(slots.name.change)`。

    `app` 写成 `Any` 是这里不导入框架 `App` 的代价：这个模块是名字，导入 `App` 只会把名字绑死在
    某一个应用的形状上，什么也没换来。
    """
    return app.slot  # type: ignore[return-value]


# 导航表单把客户端送去哪里。frame 的 `dest` 就是目标的名字。
GO_HOME, GO_ABOUT, GO_DEMO, GO_CHAT = (
    Slot("go.home"), Slot("go.about"), Slot("go.demo"), Slot("go.chat"),
)
GO = {GO_HOME.name: "/", GO_ABOUT.name: "/about", GO_DEMO.name: "/demo", GO_CHAT.name: "/chat"}