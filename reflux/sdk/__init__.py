"""reflux's Python SDK: accrete's wire types, generated from the schema, plus reflux's profile.

    from reflux.sdk import case, text, input, form, JsType, parse, dump

- `types` / `builders` are generated (`python3 tools/gen_sdk.py`) — never edit them.
- `profile` is reflux's selection over that vocabulary, read from `profile/profile.json`.
- `parse` validates a node; `dump` turns a built node back into the wire's dict.

The constructors are named after the wire's own `type` values, because the vocabulary has exactly
one source: `case`, `text`, `input`, `rack`, … Nothing here invents a second name for a node.
"""

from __future__ import annotations

from . import profile
from ._parse import dump, parse
from .builders import *
from .builders import __all__ as _builders
from .types import *

__all__ = [*_builders, "parse", "dump", "profile"]