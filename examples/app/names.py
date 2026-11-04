"""示例应用的全部名字，集中在这一处。

页面的读（`source=`）、说话（`dest=`）与应答它的处理器（`@app.on`）用的都是同一个字符串，运行时那张表
（`app.slot` / `ctx.slot`）认任何名字，所以这里的 `Protocol` 只是注解：它让三个模块不必把同一个名字写三遍，
也让编辑器能补全。一个应用的名字放一个文件够用；两个应用共用一部分名字时，把那份 `Protocol` 挪到共用模块即可
——注解不 import 任何会跑起来的东西。
"""

from typing import Protocol

from reflux.slots import Slot


class Go(Protocol):
    """导航表单的两个落点。"""

    dashboard: Slot
    chat: Slot


class Chat(Protocol):
    """对话框的两个上行。"""

    send: Slot
    stop: Slot


class Dashboard(Protocol):
    """概览页的上行。"""

    refresh: Slot


class Names(Protocol):
    """外框读的那个槽、两页的名字，以及这个应用听的宿主事件。"""

    routes: Slot  # 外框的读取器：框架把页面写进这个槽
    status: Slot  # 对话页的状态行
    messages: Slot  # 对话页的列表
    go: Go
    chat: Chat
    dashboard: Dashboard
    connect: Slot  # 宿主事件：注册与别的名字一样，但没有线上地址
    location: Slot
    disconnect: Slot


__all__ = ["Chat", "Dashboard", "Go", "Names"]