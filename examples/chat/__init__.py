"""An AI chat app: one page, a streaming backend, and a model seam you can swap.

    python3 -m examples.chat.app --port 8100            # the app
    python3 -m examples.chat.walkthrough --auto         # the demo, no browser

`app.make_app()` is the whole application; `model.Scripted` runs offline and `model.OpenAI` speaks the
OpenAI-compatible SSE form.
"""

from .app import MAX_CHARS, WINDOW, Chat, make_app, page
from .model import Model, Scripted, Turn

__all__ = ["Chat", "MAX_CHARS", "Model", "Scripted", "Turn", "WINDOW", "make_app", "page"]