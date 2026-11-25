#!/usr/bin/env python3
"""Install the renderer bundle into `www/static/vendor/fluxen/`, always the newest one.

The bundle is **not** in git: it is a build product of another repository (fluxen's
`crates/ui_leptos`, `trunk build --release`), it is ~3 MB of hashed names, and every
commit of it would be a binary diff that says nothing.

There is no pin (2026-11-25): reflux follows the renderer's newest release, so what a
`fetch` installs depends on when it runs. `versions.json` stays next to the bundle as a
*record* — the rev, and a sha256 + size per file — and every gate reads it (`gate_t0`
over HTTP), so a truncated or hand-edited bundle fails loudly instead of half-loading.
It describes what landed; it does not constrain what may land.

Three ways in, one output layout:

    python3 tools/vendor.py fetch                     # the newest release, resolved now
    python3 tools/vendor.py build --fluxen ../fluxen  # trunk build a checkout, then install it
    python3 tools/vendor.py install --dist ../fluxen/dist-release

`fetch` is what CI and a fresh clone use (no Rust toolchain needed). `build`/`install`
are for someone changing the renderer: point them at a fluxen checkout and they adopt
whatever that checkout just built, writing an honest `rev`.

Layout written (paths in `versions.json` are prefixed — the prefix is *this* host's
business, per fluxen's `scripts/ui_dist.py` header):

    www/static/vendor/fluxen/versions.json
    www/static/vendor/fluxen/ui_leptos-<hash>.js
    www/static/vendor/fluxen/ui_leptos-<hash>_bg.wasm
    www/static/vendor/fluxen/assets/core.css
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
PREFIX = "vendor/fluxen/"
CORE = ("assets/core.css", "assets/custom.css")
# Who publishes the bundle. No rev is recorded ahead of time: `fetch` asks for the newest release.
RELEASE_REPO = "orbsh/fluxen"


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
    """Drop everything an older build left in the vendor tree — a stale `.wasm` or a renamed
    stylesheet next to the live one is a trap: it loads, it looks right, and nothing reads it."""
    if not VENDOR.exists():
        return
    for path in VENDOR.rglob("*"):
        if path.is_file() and path.name not in keep and path.name != "versions.json":
            path.unlink()
            print(f"vendor: dropped stale {path.relative_to(VENDOR).as_posix()}")


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
    prune({js[0].name, wasm[0].name, *(pathlib.PurePosixPath(rel).name for rel in CORE)})
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


MANIFESTS = ("manifest.json", "versions.json")


def unpack(blob: bytes, rev: str) -> dict:
    """Extract a release tarball into the vendor tree, then re-derive `versions.json`.

    The tarball is fluxen's own (`fluxen-ui-<tag>.tar.gz`, cut by its `scripts/ui_dist.py` and published
    by its CI): four files plus a `manifest.json` naming the entry, and a `SHA256SUMS` beside it. Reflux
    used to re-cut its own copy under `versions.json`; reading the producer's manifest directly means one
    less duplicate of the same bytes and one less release to keep.
    """
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
        manifest_bytes = None
        files_only = []
        for member in tar.getmembers():
            if member.name in MANIFESTS:
                manifest_bytes = tar.extractfile(member).read()  # type: ignore[union-attr]
                continue
            if member.name == "SHA256SUMS":
                continue  # fluxen's own checksums; `versions.json` re-derives what it pins
            if not (member.name.startswith("ui_leptos-") or member.name in CORE):
                die(f"unexpected member in the bundle: {member.name}")
            target = (VENDOR / member.name).resolve()
            if VENDOR.resolve() not in target.parents:
                die(f"refusing to write outside the vendor tree: {member.name}")
            files_only.append(member)
        # Only the payload: the producer's manifest is read for its `entry`, not installed — this tree's
        # contract with its readers is `versions.json`, and two manifests side by side is two answers.
        tar.extractall(VENDOR, members=files_only)  # noqa: S202 — member names checked just above
    if manifest_bytes is None:
        die("the bundle carries no manifest.json")
    shipped = json.loads(manifest_bytes)
    files = {}
    for rel in [*CORE, *(p.name for p in VENDOR.glob("ui_leptos-*"))]:
        p = VENDOR / rel
        if not p.exists():
            die(f"the bundle promised {rel} but did not carry it")
        files[rel] = {"sha256": sha256(p), "size": p.stat().st_size}
    # A bundle with a new hash leaves the previous pair behind; a stale `ui_leptos-*.wasm` in the vendor
    # tree is 3 MB nobody loads and a second answer to "which renderer is this".
    for stale in VENDOR.glob("ui_leptos-*"):
        if stale.name not in files:
            stale.unlink()
    manifest = write_versions(rev, files, shipped.get("entry", {}))
    total = sum(m["size"] for m in manifest["files"].values())
    print(f"fetched {rev}: {manifest['entry'].get('js')} + {len(files) - 1} more, {total:,} B")
    return manifest


def _api(path: str) -> dict:
    """One GitHub API call. Unauthenticated, so the rate limit is a caller's problem, not ours."""
    url = f"https://api.github.com/{path}"
    try:
        with urllib.request.urlopen(url, timeout=60) as r:  # noqa: S310 — https, api.github.com
            return json.loads(r.read())
    except Exception as e:  # urllib raises a zoo; the message is what matters
        die(f"GitHub API failed for {path} ({e})")


def newest(repo: str) -> tuple[str, str, str]:
    """`(tag, rev, asset_url)` of that repo's newest release.

    The rev is the tag's commit, because that is what `versions.json` records and what a reader
    compares against a checkout. An annotated tag points at a tag object first, one hop from the
    commit.
    """
    rel = _api(f"repos/{repo}/releases/latest")
    tag = rel.get("tag_name") or die(f"{repo} has no releases")
    assets = [a for a in rel.get("assets", []) if a["name"].endswith(".tar.gz")]
    if not assets:
        die(f"{repo} {tag} ships no .tar.gz asset")
    ref = _api(f"repos/{repo}/git/ref/tags/{tag}")["object"]
    if ref["type"] == "tag":
        ref = _api(f"repos/{repo}/git/tags/{ref['sha']}")["object"]
    return tag, ref["sha"][:7], assets[0]["browser_download_url"]


def fetch(repo: str, tag: str | None = None) -> dict:
    if tag:
        asset = f"fluxen-ui-{tag}.tar.gz"
        url = f"https://github.com/{repo}/releases/download/{tag}/{asset}"
        ref = _api(f"repos/{repo}/git/ref/tags/{tag}")["object"]
        if ref["type"] == "tag":
            ref = _api(f"repos/{repo}/git/tags/{ref['sha']}")["object"]
        rev = ref["sha"][:7]
    else:
        tag, rev, url = newest(repo)
    print(f"GET {tag} ({rev}): {url}")
    try:
        with urllib.request.urlopen(url, timeout=120) as r:  # noqa: S310 — https, the release itself
            blob = r.read()
    except Exception as e:  # urllib raises a zoo; the message is what matters
        die(f"download failed ({e}) — build locally with `build --fluxen <path>` if offline")
    return unpack(blob, rev)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="download the newest release (or a named tag)")
    f.add_argument("--repo", default=RELEASE_REPO, help=f"owner/name (default: {RELEASE_REPO})")
    f.add_argument("--tag", help="a specific tag instead of the newest")

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

    if a.cmd == "fetch":
        fetch(a.repo, a.tag)
    elif a.cmd == "build":
        src = pathlib.Path(a.fluxen).resolve()
        if not (src / "crates/ui_leptos/Trunk.toml").exists():
            die(f"{src} does not look like a fluxen checkout")
        if not a.no_build:
            subprocess.run(["trunk", "build", "--release"], cwd=src / "crates/ui_leptos", check=True)
        rev = a.rev or subprocess.run(
            ["git", "-C", str(src), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        install(src / "crates/ui_leptos/dist", rev)
        if a.tag:
            tarball(ROOT / "dist-release", a.tag, rev)
    else:
        install(pathlib.Path(a.dist).resolve(), a.rev)
        if a.tag:
            tarball(ROOT / "dist-release", a.tag, a.rev)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())