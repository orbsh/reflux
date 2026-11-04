"""Two declarations in one module: a parameterised path, and one handler on two paths."""

from __future__ import annotations

from reflux import route


@route("/blog/{slug}", title="文章")
def post(ctx, match):
    ctx.page(f"post:{match.params['slug']}")


@route("/latest")  # an alias is a second decorator — the table gets the same handler on both paths
@route("/posts")
def post_index(ctx, match):
    ctx.page(f"index:{match.path}")


@route("/blog/{rest:path}", title="兜底")
def blog_rest(ctx, match):
    ctx.page(f"rest:{match.params['rest']}")