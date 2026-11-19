"""reflux's profile over accrete's vocabulary — the readable data behind the builders and the gates.

It carries no type definitions (those come from the schema, through `types.py`): selection, defaults
and the class-token vocabulary. The file itself is `profile/profile.json` at the repo root, so every
language's SDK reads the same one.
"""

from __future__ import annotations

import json
import pathlib
from functools import lru_cache

PATH = pathlib.Path(__file__).resolve().parents[2] / "profile" / "profile.json"

__all__ = ["PATH", "load", "types", "exposed", "hidden_attrs", "tokens"]


@lru_cache(maxsize=1)
def load() -> dict:
    return json.loads(PATH.read_text())


def types() -> dict:
    return load()["types"]


def exposed() -> list[str]:
    """The wire types that make up the app surface, in the schema's order."""
    return [name for name, entry in types().items() if entry.get("expose")]


def hidden_attrs() -> set[str]:
    """The attributes the builders never expose (`class` — the token lane's only path).

    `selector` is not one of them: it is the name an entry's field carries (ADR 0031 §4), so a
    producer writes it like any other attribute.
    """
    return set(load().get("hidden_attrs", [])) | {"class"}


def tokens() -> dict:
    """Enum value → class token. Empty until the styling layer lands; the producers see no classes."""
    return load().get("tokens", {})