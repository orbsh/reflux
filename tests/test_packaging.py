"""What `pip install` has to produce: one wheel, and everything a served page needs inside it.

The page tree lives at the repository root (`www/`), but a wheel cannot reach the repository: the build
copies it to `reflux/www/` and fetches the pinned renderer into it first (`hatch_build.py`). These tests
hold the two halves that are checkable without building: the declarations that make the wheel what it is,
and the layout `PAGE_ROOT` resolves to — in a checkout, and inside an installed package.
"""

from __future__ import annotations

import json
import pathlib
import tomllib
import unittest

from reflux.app import PAGE_ROOT, STATIC_PREFIX

ROOT = pathlib.Path(__file__).resolve().parent.parent
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
BUNDLE = PAGE_ROOT / "static" / "vendor" / "fluxen"


class TheBuild(unittest.TestCase):
    def test_a_build_backend_is_declared(self) -> None:
        # Without this, `pip install reflux` is not a thing that exists: no backend, no wheel.
        self.assertEqual(PYPROJECT["build-system"]["build-backend"], "hatchling.build")

    def test_the_command_is_an_entry_point(self) -> None:
        self.assertEqual(PYPROJECT["project"]["scripts"]["reflux"], "reflux.cli:main")

    def test_the_hook_is_wired(self) -> None:
        # The hook is what puts `www/` into `reflux/www/` and fetches the bundle. Declared in pyproject,
        # implemented in `hatch_build.py` at the root.
        self.assertIn("hooks", PYPROJECT["tool"]["hatch"]["build"]["targets"]["wheel"])
        self.assertTrue((ROOT / "hatch_build.py").is_file())

    def test_an_sdist_can_still_build_a_wheel(self) -> None:
        # A wheel built *from* the sdist needs the page tree (what it serves), the pin, and the fetch
        # script (what fills the vendored bundle). Missing any of the three, the sdist is a dead end.
        include = PYPROJECT["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
        for needed in ("/www", "/vendor", "/tools/vendor.py", "/hatch_build.py"):
            self.assertIn(needed, include)

    def test_the_wheel_carries_the_package(self) -> None:
        self.assertEqual(PYPROJECT["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"], ["reflux"])


class ThePageRoot(unittest.TestCase):
    def test_it_is_a_directory_with_a_page(self) -> None:
        self.assertTrue(PAGE_ROOT.is_dir(), f"PAGE_ROOT {PAGE_ROOT} does not exist")
        page = (PAGE_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('<base href="/">', page)

    def test_it_resolves_inside_the_package_when_one_is_there(self) -> None:
        # A wheel has `reflux/www`; a checkout has `www/` next to `reflux/`. Whichever exists is what the
        # server serves, and only the wheel's copy can be reached from site-packages.
        import reflux

        package = pathlib.Path(reflux.__file__).resolve().parent
        self.assertEqual(PAGE_ROOT.parent, package if (package / "www").is_dir() else package.parent)

    def test_the_framework_assets_are_with_it(self) -> None:
        for name in ("reflux.js", "reflux.css", "logo.svg"):
            self.assertTrue((PAGE_ROOT / STATIC_PREFIX.strip("/") / name).is_file(), name)

    def test_the_renderer_bundle_is_the_one_the_pin_names(self) -> None:
        manifest = BUNDLE / "versions.json"
        if not manifest.is_file():
            self.skipTest("the renderer bundle is not installed here — run tools/vendor.py fetch")
        pin = json.loads((ROOT / "vendor" / "pin.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["rev"], pin["rev"])


if __name__ == "__main__":
    unittest.main()