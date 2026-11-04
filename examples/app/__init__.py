"""The example application: a dashboard at `/`, a chat at `/chat`, one shell around both.

    python3 -m examples.app --port 8100

Importing this package is what declares the routes: `app.py` builds the app and its shell, then
`dashboard` and `chat` — one page per file — hang their pages on it. There is no list of pages to keep
in step, and nothing to register by hand.
"""

from .app import app, heard, main, shell

from . import chat, dashboard  # noqa: F401,E402  — importing a page module declares its route

__all__ = ["app", "chat", "dashboard", "heard", "main", "shell"]