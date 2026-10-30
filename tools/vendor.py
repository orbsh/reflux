#!/usr/bin/env python3
"""Install the pinned renderer bundle into `www/static/vendor/fluxen/`.

The bundle is **not** in git: it is a build product of another repository (fluxen's
`examples/renderer`, `trunk build --release`), it is ~3 MB of hashed names, and every
commit of it would be a binary diff that says nothing. What *is* in git is the pin —
`vendor/pin.json` — and the reader's contract with it: `versions.json` next to the
bundle, carrying the rev and a sha256 + size per file. Every gate reads that file
(`gate_t0` over HTTP), so a stale or hand-edited bundle fails loudly instead of
half-loading.

Three ways in, one output layout:

    python3 tools/vendor.py fetch                    # from the release the pin names
    python3 tools/vendor.py build --fluxen ../fluxen # trunk build, then install
    python3 tools/vendor.py install --dist ../fluxen/examples/renderer/dist

`fetch` is what CI and a fresh clone use (no Rust toolchain needed). `build`/`install`
are for someone changing the renderer: point them at a fluxen checkout and they adopt
whatever that checkout just built, writing an honest `rev`.

Layout written (paths in `versions.json` are prefixed — the prefix is *this* host's
business, per fluxen's `scripts/ui_dist.py` header):

    www/static/vendor/fluxen/versions.json
    www/static/vendor/fluxen/ui_leptos-<hash>.js
    www/static/vendor/fluxen/ui_leptos-<hash>_bg.wasm
    www/static/vendor/fluxen/assets/main.css
    www/static/vendor/fluxen/assets/custom.css
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import pathlib
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from typing import NoReturn

ROOT = pathlib.Path(__file__).resolve().parent.parent
VENDOR = ROOT / "www" / "static" / "vendor" / "fluxen"
PIN = ROOT / "vendor" / "pin.json"
PREFIX = "vendor/fluxen/"
CORE = ("assets/main.css", "assets/custom.css")


def die(msg: str) -> NoReturn:
    print(f"vendor: {msg}", file=sys.stderr)
    raise SystemExit(1)


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_versions(rev: str, files: dict[str, dict], entry: dict[str, str]) -> dict:
    """The manifest every gate and page reads: rev, entry names, per-path sha256 + size."""
    manifest = {
        "renderer": "fluxen",
        "rev": rev,
        "entry": entry,
        "files": {PREFIX + rel: meta for rel, meta in sorted(files.items())},
    }
    VENDOR.mkdir(parents=True, exist_ok=True)
    (VENDOR / "versions.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def prune(keep: set[str]) -> None:
    """Drop bundles from an older build — a stale `.wasm` next to the live one is a trap."""
    for f in VENDOR.glob("ui_leptos-*"):
        if f.name not in keep:
            f.unlink()


def install(dist: pathlib.Path, rev: str) -> dict:
    """Take a trunk `dist/` (or any dir with the same shape) and become it."""
    js = sorted(dist.glob("ui_leptos-*.js"))
    wasm = sorted(dist.glob("ui_leptos-*_bg.wasm"))
    if len(js) != 1 or len(wasm) != 1:
        die(f"{dist} holds {len(js)} .js and {len(wasm)} .wasm — a release has exactly one of each")
    wanted = [js[0], wasm[0], *(dist / rel for rel in CORE)]
    for p in wanted:
        if not p.exists():
            die(f"{p} is missing from {dist}")
    prune({js[0].name, wasm[0].name})
    VENDOR.mkdir(parents=True, exist_ok=True)
    files: dict[str, dict] = {}
    for p in wanted:
        rel = p.relative_to(dist).as_posix()
        dest = VENDOR / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
        files[rel] = {"sha256": sha256(dest), "size": dest.stat().st_size}
    manifest = write_versions(rev, files, {"js": js[0].name, "wasm": wasm[0].name})
    total = sum(m["size"] for m in manifest["files"].values())
    print(f"installed {rev}: {manifest['entry']['js']} + {len(files) - 1} more, {total:,} B")
    return manifest


def tarball(out_dir: pathlib.Path, tag: str, rev: str) -> pathlib.Path:
    """One file per release: the bundle plus its manifest, byte-identical per build input."""
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"fluxen-renderer-{rev}.tar.gz"
    target = out_dir / name
    entries = sorted([VENDOR / "versions.json", *VENDOR.glob("ui_leptos-*"), *(VENDOR / rel for rel in CORE)])
    with target.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w") as tar:
                for p in entries:
                    info = tar.gettarinfo(str(p), arcname=p.relative_to(VENDOR).as_posix())
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    info.mtime = 0
                    with p.open("rb") as f:
                        tar.addfile(info, f)
    sums = out_dir / "SHA256SUMS"
    line = f"{sha256(target)}  {name}\n"
    with sums.open("a") as f:
        f.write(line)
    print(f"wrote {target.relative_to(ROOT)} ({target.stat().st_size:,} B)\n      {line.strip()}")
    return target


def unpack(blob: bytes, rev: str) -> dict:
    """Extract a release tarball into the vendor tree, then re-derive `versions.json`."""
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
        manifest_bytes = None
        for member in tar.getmembers():
            if member.name == "versions.json":
                manifest_bytes = tar.extractfile(member).read()  # type: ignore[union-attr]
                continue
            if not (member.name.startswith("ui_leptos-") or member.name in CORE):
                die(f"unexpected member in the bundle: {member.name}")
            target = (VENDOR / member.name).resolve()
            if VENDOR.resolve() not in target.parents:
                die(f"refusing to write outside the vendor tree: {member.name}")
        tar.extractall(VENDOR)  # noqa: S202 — member names checked just above
    if manifest_bytes is None:
        die("the bundle carries no versions.json")
    shipped = json.loads(manifest_bytes)
    files = {}
    for rel in [*CORE, *(p.name for p in VENDOR.glob("ui_leptos-*"))]:
        p = VENDOR / rel
        if not p.exists():
            die(f"the bundle promised {rel} but did not carry it")
        files[rel] = {"sha256": sha256(p), "size": p.stat().st_size}
    manifest = write_versions(rev, files, shipped.get("entry", {}))
    total = sum(m["size"] for m in manifest["files"].values())
    print(f"fetched {rev}: {manifest['entry'].get('js')} + {len(files) - 1} more, {total:,} B")
    return manifest


def fetch(tag: str, rev: str, asset: str) -> dict:
    pin = json.loads(PIN.read_text())
    url = pin.get("asset_url") or (
        f"https://github.com/{pin['releases']}/releases/download/{tag}/{asset}"
    )
    print(f"GET {url}")
    try:
        with urllib.request.urlopen(url, timeout=120) as r:  # noqa: S310 — https, pinned tag
            blob = r.read()
    except Exception as e:  # urllib raises a zoo; the message is what matters
        die(f"download failed ({e}) — build locally with `build --fluxen <path>` if offline")
    return unpack(blob, rev)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="download the release the pin names")
    f.add_argument("--tag", help="release tag (default: the pin's)")
    f.add_argument("--asset", help="asset name (default: the pin's)")

    b = sub.add_parser("build", help="trunk build a fluxen checkout, then install it")
    b.add_argument("--fluxen", required=True, help="path to a fluxen checkout")
    b.add_argument("--no-build", action="store_true", help="use whatever its dist/ already holds")
    b.add_argument("--rev", help="rev to record (default: the checkout's HEAD)")
    b.add_argument("--tag", help="also cut a release tarball under dist-release/")

    i = sub.add_parser("install", help="install an existing dist/ directory")
    i.add_argument("--dist", required=True)
    i.add_argument("--rev", required=True)
    i.add_argument("--tag", help="also cut a release tarball under dist-release/")

    a = ap.parse_args(argv)
    pin = json.loads(PIN.read_text()) if PIN.exists() else {}

    if a.cmd == "fetch":
        fetch(a.tag or pin["tag"], pin["rev"], a.asset or pin["asset"])
    elif a.cmd == "build":
        src = pathlib.Path(a.fluxen).resolve()
        if not (src / "examples/renderer/Trunk.toml").exists():
            die(f"{src} does not look like a fluxen checkout")
        if not a.no_build:
            subprocess.run(["trunk", "build", "--release"], cwd=src / "examples/renderer", check=True)
        rev = a.rev or subprocess.run(
            ["git", "-C", str(src), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        install(src / "examples/renderer/dist", rev)
        if a.tag:
            tarball(ROOT / "dist-release", a.tag, rev)
    else:
        install(pathlib.Path(a.dist).resolve(), a.rev)
        if a.tag:
            tarball(ROOT / "dist-release", a.tag, a.rev)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())