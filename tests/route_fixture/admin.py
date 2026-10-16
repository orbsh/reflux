"""A layout, a catch-all path, and metadata — the shapes the CLI prints."""

from __future__ import annotations

from reflux import route


def admin_layout(session, match, page):
    """A layout is an ordinary callable: it is handed the page and decides where it goes."""
    return {"layout": match.route.meta.get("title"), "page": page}


@route("/admin", layout=admin_layout, title="后台")
def admin(session, match):
    return "admin"