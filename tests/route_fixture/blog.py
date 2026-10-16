"""Two declarations in one module: a parameterised path, and one handler on two paths."""

from __future__ import annotations

from reflux import route


@route("/blog/{slug}", title="文章")
def post(session, match):
    return f"post:{match.params['slug']}"


@route("/")  # an alias is a second decorator — the table gets the same handler on both paths
@route("/posts")
def post_index(session, match):
    return f"index:{match.path}"


@route("/blog/{rest:path}", title="兜底")
def blog_rest(session, match):
    return f"rest:{match.params['rest']}"