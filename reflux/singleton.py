"""The deployment's app — built when this module is imported, and not before.

    from reflux.singleton import app

    @app.page("/", title="演示")
    def home(ctx, match): ...

`import reflux` builds nothing: a library that is imported by a tool, a test or another library must not
pay for an app it does not serve. The cost is the module name in the import — one line, said at the place
where a deployment decides it has one.

Two apps in one process is not this module's problem: ask `create_app()` for a second one, which shares
nothing with this one.
"""

from __future__ import annotations

from .application import create_app

# The one app of this process. Every declaration in the deployment hangs on it; the demos use
# `create_app()` instead because the zh and en trees have to coexist in a single process.
app = create_app()
