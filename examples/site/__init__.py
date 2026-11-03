"""A routed site: a shell that stays, and the page inside the `routes` slot.

    python3 -m examples.site.app --port 8200            # the app
    python3 -m examples.site.walkthrough --auto         # the demo, no browser

`app.make_app()` is the whole application: one shell, two routes, and the three host events
(`connect` / `location` / `disconnect`) recorded on the app.
"""

from .app import PAGES, SHELL_ID, app, go, make_app, shell, site

__all__ = ["PAGES", "SHELL_ID", "app", "go", "make_app", "shell", "site"]