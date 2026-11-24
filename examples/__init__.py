"""The reference application, in two languages.

    python3 -m examples.zh.demo_app --port 8000     # 中文版：界面、注释、函数文档都是中文
    python3 -m examples.en.demo_app --port 8001     # English: UI, comments and docstrings, all English

`examples/zh/` and `examples/en/` are the same application written twice — not one tree with a
translation table. A reader opens the tree for their language and finds nothing else in it. Each tree
declares its own route table, so the two apps can serve the same paths at the same time.
"""

__all__ = ["en", "zh"]
