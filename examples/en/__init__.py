"""The reference application, English tree: UI, comments and docstrings, all English.

    python3 -m examples.en.demo_app --port 8001     # /, /about, /chat, /demo

`demo_app.py` is the app itself (shell, two pages, `/status`); `demo_chat.py` is `/chat`,
`demo/page.py` is `/demo`, and `demo_slots.py` holds every name the three share. The Chinese tree is
`examples/zh/` — the same application written again, not a translation table on top of this one. Each
tree declares its own route table, so both can serve `/` at the same time.
"""

__all__ = ["chat_model", "demo_app", "demo_chat", "demo_slots"]
