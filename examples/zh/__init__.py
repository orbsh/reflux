"""参考应用的中文版：界面、注释和函数文档都是中文。

    python3 -m examples.zh.demo_app --port 8000     # /、/about、/chat、/demo

`demo_app.py` 是应用本体（外框、两页、`/status`），另外两页各自一个模块（`demo_chat.py`、
`demo/page.py`），三处共用的名字在 `demo_slots.py`，模型接缝在 `chat_model.py`。英文版在
`examples/en/`，是同一件事的另一种语言；两版各自声明路由表，可以同时起服务。
"""

__all__ = ["chat_model", "demo_app", "demo_chat", "demo_slots"]
