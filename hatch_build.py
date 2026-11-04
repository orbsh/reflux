"""Put the page tree inside the wheel, with the renderer bundle the pin names already in it.

`pip install reflux` has to give a server that serves pages: the page tree, the framework's own
runtime (`reflux.js`, `reflux.css`), and the renderer's js + wasm. The last part is a build product of
another repository (~3 MB of hashed names) and lives in git only as a pin, so it is fetched **here**,
while the wheel is being built, and copied in with everything else:

    www/                      →  reflux/www/                      (the wheel)
    www/static/vendor/fluxen/ →  reflux/www/static/vendor/fluxen/  (fetched, never committed)

The repository keeps its `www/` at the root; the package-internal copy exists only inside a built
wheel, which is why `reflux/app.py` looks for `reflux/www` first and falls back to the root (a checkout,
and an editable install, see the root).

No network when it is not needed: a bundle already at the pinned revision is reused, so a local
`uv build` after one `tools/vendor.py fetch` is offline and reproducible. A build that does have to
fetch fails loudly rather than shipping a server with no pages.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

ROOT = pathlib.Path(__file__).resolve().parent
PAGES = ROOT / "www"
PIN = ROOT / "vendor" / "pin.json"
BUNDLE = PAGES / "static" / "vendor" / "fluxen"


# Where a Linux puts its trust store. Only tried when the build interpreter has none of its own.
CA_CANDIDATES = (
    "/etc/ssl/certs/ca-certificates.crt",
    "/etc/ssl/certs/ca-bundle.crt",
    "/etc/pki/tls/certs/ca-bundle.crt",
)


def ensure_ca_bundle() -> None:
    """Point urllib at a CA bundle when the build interpreter's own default is missing.

    A build backend runs under an interpreter we did not choose. A uv-managed one can be compiled with
    an openssl default path that does not exist on the machine building the wheel (NixOS keeps its own
    in the store), and then every https fetch fails with CERTIFICATE_VERIFY_FAILED — a fact about the
    builder, not about the release. `SSL_CERT_FILE` is the knob urllib obeys.
    """
    current = os.environ.get("SSL_CERT_FILE")
    if current and pathlib.Path(current).is_file():
        return
    for candidate in CA_CANDIDATES:
        if pathlib.Path(candidate).is_file():
            os.environ["SSL_CERT_FILE"] = candidate
            return


class VendorHook(BuildHookInterface):
    """Fetch what the pin names, then hand every file of `www/` to the wheel as `reflux/www/…`."""

    PLUGIN_NAME = "vendor"

    def initialize(self, version: str, build_data: dict) -> None:
        if self.target_name != "wheel":
            return  # an sdist carries the pin and the fetch script; the wheel is what needs pages
        self._ensure_bundle()
        for path in sorted(PAGES.rglob("*")):
            if not path.is_file() or not self._ship(path):
                continue
            build_data["force_include"][str(path)] = f"reflux/www/{path.relative_to(PAGES)}"

    def _ship(self, path: pathlib.Path) -> bool:
        """Only the pinned renderer goes in with the vendored tree.

        `www/static/vendor/` also collects what an example needs — the charts module looks for
        `vendor/g2chart` — and those are the example's business, not a server's that never asks for
        a chart. The pin is the one bundle a page cannot load without.
        """
        parts = path.relative_to(PAGES).parts
        if parts[:3] != ("static", "vendor", "fluxen") and parts[:2] == ("static", "vendor"):
            return False
        return True

    def _ensure_bundle(self) -> None:
        pin = json.loads(PIN.read_text(encoding="utf-8"))
        if _installed_rev() == pin["rev"] and (BUNDLE / "versions.json").is_file():
            return
        print(f"vendor: fetching {pin['tag']} into the wheel", file=sys.stderr)
        ensure_ca_bundle()
        subprocess.run(
            [sys.executable, str(ROOT / "tools" / "vendor.py"), "fetch"],
            check=True,
            cwd=str(ROOT),
        )
        if _installed_rev() != pin["rev"]:
            raise SystemExit(f"vendor: fetch left {_installed_rev()!r} in place, pin says {pin['rev']!r}")


def _installed_rev() -> str | None:
    """The revision of the bundle sitting in `www/`, if there is one and it reads as a manifest."""
    manifest = BUNDLE / "versions.json"
    if not manifest.is_file():
        return None
    try:
        return json.loads(manifest.read_text(encoding="utf-8")).get("rev")
    except ValueError:
        return None