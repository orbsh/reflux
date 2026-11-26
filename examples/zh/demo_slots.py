"""参考应用的槽名：一个类型别名、两个取值函数，和导航的六个地址。

这里只有**名字**：`@app.on` 那一类落点（身份在页面里、跨页存在、或一个槽有多个来源）。页面内部的
请求-回应不在这里 —— 那些写成闭包，`sink=add_row`，写在发出它的按钮旁边，框架在绘制时给它起名。

槽名在 wire 上是个字符串（框架的 `slots.py`），名字由 `/` 拼出来：`ctx.slot / "echo"`。点号在句柄上
只表示动词与细胞（`set`、`append`、`value`……），不表示名字 —— `Slot.__getattr__` 对别的名字直接拒绝。
所以这个名字空间没有第二份清单：`ctx.slot / "echo"` 与 `app.slot / "echo"` 是同一条槽，拼错一处在运行
期才看得见。这个模块留两件事：

    slots_of(ctx)        页面这一侧的表，带投递 —— 写入走它（`set`、`append`）
    table(app)           应用的表，不带投递 —— 地址走它（`sink=`、`source=`、`@app.on(...)`）

两个返回的都是框架的 `Slots`；`DemoSlots` 是这个应用给它的别名，读起来仍是"这个应用的槽"。
"""

from __future__ import annotations

from typing import Any

from reflux.application import Context
from reflux.slots import Slot, Slots

__all__ = ["DemoSlots", "GO", "GO_ABOUT", "GO_CHAT", "GO_COUNTER", "GO_DEMO", "GO_SETTINGS", "GO_HOME", "slots_of", "table"]

DemoSlots = Slots


def slots_of(ctx: Context) -> DemoSlots:
    """参考应用这一次投递的槽 —— 页面写东西用的那些名字。"""
    return ctx.slot


def table(app: Any) -> DemoSlots:
    """应用自己的表 —— 它寻址的那些名字：`@app.on(app.slot / "row" / "remove")`。

    `app` 写成 `Any` 是这里不导入框架 `App` 的代价：这个模块是名字，导入 `App` 只会把名字绑死在
    某一个应用的形状上，什么也没换来。
    """
    return app.slot


# 导航表单把客户端送去哪里。frame 的 `dest` 就是目标的名字。
GO_HOME, GO_ABOUT, GO_DEMO, GO_CHAT, GO_COUNTER, GO_SETTINGS = (
    Slot("go.home"), Slot("go.about"), Slot("go.demo"), Slot("go.chat"), Slot("go.counter"),
    Slot("go.settings"),
)
GO = {
    GO_HOME.name: "/",
    GO_ABOUT.name: "/about",
    GO_DEMO.name: "/demo",
    GO_CHAT.name: "/chat",
    GO_COUNTER.name: "/counter",
    GO_SETTINGS.name: "/settings",
}