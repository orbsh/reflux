"""A module that cannot be imported. Discovery must die on it — a skipped module is a set of
routes that silently does not exist."""

from __future__ import annotations

raise ImportError("this module is a fixture for a startup failure")