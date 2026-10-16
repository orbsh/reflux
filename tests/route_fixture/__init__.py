"""A package whose modules declare routes on import — the fixture for discovery and the CLI.

Nothing here is a test: a test imports the package, and each module declares its routes where its
handlers are written (no file name becomes a URL).
"""

from __future__ import annotations