"""The walkthrough page: fluxen's demo story, as one route of the reference application.

The reference app (`reflux/demo_app.py`) is small on purpose — it is what an application looks like
on this wire. This page is content: it draws with the same vocabulary, but it says a great deal, and
its text, chart specs and graph live in `scene.py`. Importing this package registers the page's route
(the framework's discovery is an import, `reflux/routes.py`), and `page.register` puts its four
uplinks on the app that asks for it.
"""

from . import page

__all__ = ["page", "scene"]
