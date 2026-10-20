"""The page: its pinned bundle, and the mounts that serve it.

Two failure modes this catches before a browser sees them:
  1. a vendored renderer file was swapped or rebuilt without refreshing versions.json (or the
     manifest was edited by hand and now names a file that is not there)
  2. the page starts naming a hashed asset itself, or addresses an asset relatively — the names
     must come from the manifest, and the paths must be origin-absolute, or a deep link resolves
     them against the deep-link directory and the page dies in a browser only

The mounts are tested over real HTTP, without chromium: the root rule, the deep-link rule, the
prefix redirect and "a missing module never comes back as HTML" are server facts, not browser facts.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import re
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WWW = REPO / "www"
STATIC = WWW / "static"
VENDOR = STATIC / "vendor" / "fluxen"
VERSIONS = VENDOR / "versions.json"
INDEX = WWW / "index.html"

ASSET_REF = re.compile(r"""(?:href|src)="([^"]+)\"""")
IMPORT_URL = re.compile(r"""@import\s+url\(\s*["']([^"']+)["']\s*\)""")

# The page is the origin root now: one mount for it, one for its assets.
PAGE = "/"
STATIC_PREFIX = "/static/"


def manifest() -> dict:
    return json.loads(VERSIONS.read_text(encoding="utf-8"))


def pinned() -> dict[str, dict]:
    """The manifest's files, keyed relative to www/static (so a URL is STATIC_PREFIX + key)."""
    return manifest()["files"]


class TestPinnedRenderer(unittest.TestCase):
    def test_manifest_lists_exactly_the_vendored_files(self) -> None:
        on_disk = {
            path.relative_to(STATIC).as_posix()
            for path in VENDOR.rglob("*")
            if path.is_file() and path.name != VERSIONS.name
        }
        self.assertEqual(
            set(pinned()),
            on_disk,
            "versions.json and the directory disagree — re-run the bump procedure",
        )

    def test_sha256_and_size_match_disk(self) -> None:
        for rel, want in sorted(pinned().items()):
            data = (STATIC / rel).read_bytes()
            self.assertEqual(len(data), want["size"], f"{rel}: size drifted")
            self.assertEqual(hashlib.sha256(data).hexdigest(), want["sha256"], f"{rel}: content drifted")

    def test_entry_points_are_pinned_files(self) -> None:
        entry = manifest()["entry"]
        for name in (entry["js"], entry["wasm"]):
            self.assertIn(f"vendor/fluxen/{name}", pinned(), f"{name} is the entry but not listed")

    def test_page_names_no_hashed_asset_itself(self) -> None:
        self.assertNotIn("ui_leptos-", INDEX.read_text(encoding="utf-8"))

    def test_the_base_is_the_root_the_page_is_mounted_at(self) -> None:
        """The runtime translates markers with <base>; it must name the prefix the app mounts."""
        from reflux.app import App

        app = App()
        self.assertEqual(app.root, WWW, "the app's default root is the page tree")
        self.assertIn('<base href="/">', INDEX.read_text(encoding="utf-8"))

    def test_page_references_are_origin_absolute(self) -> None:
        """A relative reference would resolve against the deep-link path, not the mount root."""
        for ref in ASSET_REF.findall(INDEX.read_text(encoding="utf-8")):
            self.assertTrue(
                ref.startswith(("/", "data:")),
                f"{ref} is relative — a page served at /blog/x would resolve it there",
            )

    def test_page_references_only_pinned_assets_or_its_own_files(self) -> None:
        html = INDEX.read_text(encoding="utf-8")
        refs = [ref for ref in ASSET_REF.findall(html) if ref.startswith(STATIC_PREFIX)]
        self.assertTrue(refs, "the page references no asset at all?")
        for ref in refs:
            rel = ref[len(STATIC_PREFIX) :]
            if rel.startswith("vendor/"):
                self.assertIn(rel, pinned(), f"{ref} is not pinned in versions.json")
            else:
                self.assertTrue((STATIC / rel).is_file(), f"{ref} does not exist under www/static/")
        self.assertIn(STATIC_PREFIX + "vendor/fluxen/versions.json", html)

    def test_every_css_import_is_a_pinned_sibling(self) -> None:
        for rel in pinned():
            if not rel.endswith(".css"):
                continue
            css = (STATIC / rel).read_text(encoding="utf-8")
            for ref in IMPORT_URL.findall(css):
                sibling = (Path(rel).parent / ref).as_posix()
                self.assertIn(sibling, pinned(), f"{rel} imports {ref}, which is not pinned")


class TestMounts(unittest.TestCase):
    """One origin, two mounts: the page at /, its assets at /static/."""

    @classmethod
    def setUpClass(cls) -> None:
        from reflux.app import App

        cls.app = App()
        cls.server = cls.app.make_server(0)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.app.stop()

    def get(self, path: str) -> tuple[int, str]:
        with urllib.request.urlopen(self.base + path, timeout=5) as res:
            return res.status, res.read().decode("utf-8", "replace")

    def test_the_page_is_the_root(self) -> None:
        status, body = self.get(PAGE)
        self.assertEqual(status, 200)
        self.assertIn('id="main"', body)

    def test_a_deep_link_gets_the_page(self) -> None:
        status, body = self.get("/blog/a/post")
        self.assertEqual(status, 200)
        self.assertIn('id="main"', body)

    def test_the_page_assets_come_from_the_static_mount(self) -> None:
        status, body = self.get(STATIC_PREFIX + "vendor/fluxen/versions.json")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["renderer"], "fluxen")

    def test_an_asset_mount_without_its_slash_redirects_to_it(self) -> None:
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1])
        conn.request("GET", STATIC_PREFIX.rstrip("/"))
        res = conn.getresponse()
        self.assertEqual(res.status, 301)
        self.assertEqual(res.getheader("Location"), STATIC_PREFIX)
        conn.close()

    def test_a_missing_module_is_a_404_not_the_page(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get(STATIC_PREFIX + "vendor/nope.js")
        self.assertEqual(caught.exception.code, 404)
        caught.exception.close()


if __name__ == "__main__":
    unittest.main()