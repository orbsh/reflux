"""The vendored shell assets are pinned, and the import map covers what they import.

Two failure modes this catches before a browser sees them:
  1. a vendored file was swapped or re-downloaded without refreshing shell/VERSIONS
  2. a version bump introduced a bare specifier the import map doesn't map — which
     would show up only as a runtime module-resolution error in the browser
"""

from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SHELL = REPO / "shell"
VERSIONS = SHELL / "VERSIONS"
INDEX = SHELL / "index.html"

BARE_IMPORT = re.compile(r"""(?:^|[\s;])from\s+['"]([^'"./][^'"]*)['"]""")


def pinned_assets() -> dict[str, tuple[str, int]]:
    out: dict[str, tuple[str, int]] = {}
    for line in VERSIONS.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 4 and parts[0].startswith("vendor/") and parts[1] == "sha256":
            out[parts[0]] = (parts[2], int(parts[3]))
    return out


class TestVendoredAssets(unittest.TestCase):
    def test_versions_lists_the_four_solid_files(self) -> None:
        self.assertEqual(len(pinned_assets()), 4, "expected four pinned solid-js files")

    def test_sha256_and_size_match_disk(self) -> None:
        for rel, (want_hash, want_size) in sorted(pinned_assets().items()):
            path = SHELL / rel
            self.assertTrue(path.is_file(), f"{rel} missing")
            data = path.read_bytes()
            self.assertEqual(len(data), want_size, f"{rel}: size drifted")
            self.assertEqual(
                hashlib.sha256(data).hexdigest(), want_hash, f"{rel}: content drifted"
            )

    def test_import_map_covers_every_bare_specifier(self) -> None:
        imports = set(re.findall(r'"([^"]+)":\s*"/[^"]+"', INDEX.read_text(encoding="utf-8")))
        needed: set[str] = set()
        for path in sorted((SHELL / "vendor" / "solid-js").glob("*.js")):
            needed |= set(BARE_IMPORT.findall(path.read_text(encoding="utf-8")))
        # the shell's own modules import these too, and they must resolve as well
        needed |= {"solid-js", "solid-js/web", "solid-js/store", "solid-js/h"}
        self.assertTrue(
            needed <= imports,
            f"import map misses {sorted(needed - imports)}",
        )

    def test_index_mounts_a_module_script(self) -> None:
        html = INDEX.read_text(encoding="utf-8")
        self.assertIn('type="importmap"', html)
        self.assertRegex(html, r'<script type="module" src="/js/main\.js">')
        self.assertIn('id="app"', html)


if __name__ == "__main__":
    unittest.main()