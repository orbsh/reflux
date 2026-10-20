"""reflux's Python SDK: accrete's wire types, generated from the schema, plus reflux's profile.

    from reflux.sdk import case, text, input, form, JsType, parse, dump
    from reflux.sdk import markers

- `types` / `builders` are generated (`python3 tools/gen_sdk.py`) — never edit them.
- `markers` is hand-written: the page's two reserved ids (`reflux:path`, `reflux:title`) and the
  `page()` that puts them in front of a page. It is not the vocabulary — the spec does not know the
  words `path` or `title` — so it is not generated either.
- `profile` is reflux's selection over that vocabulary, read from `profile/profile.json`.
- `parse` validates a node; `dump` turns a built node back into the wire's dict.

The constructors are named after the wire's own `type` values, because the vocabulary has exactly
one source: `case`, `text`, `input`, `rack`, … Nothing here invents a second name for a node.
"""

from __future__ import annotations

from . import markers, profile
from ._parse import dump, parse
from .builders import *  # noqa: F401,F403
from .builders import __all__ as _builders
from .types import *  # noqa: F401,F403

__all__ = [*_builders, "parse", "dump", "profile", "markers"]