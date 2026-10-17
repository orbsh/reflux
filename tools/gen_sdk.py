#!/usr/bin/env python3
"""Generate the Python SDK from accrete's schema and reflux's profile.

    schema/accrete.schema.json   the wire's snapshot (tools/sync_schema.py refreshes it)
    profile/profile.json         reflux-side selection, defaults, tokens — no type definitions
        ↓ datamodel-codegen (pinned) — the off-the-shelf JSON-Schema consumer: the type layer
        ↓ post-pass — the repairs that output needs (below)
    reflux/sdk/types.py          one class per wire type, plus the discriminated `Accrete` union
    reflux/sdk/builders.py       the constructor surface: one function per exposed type

    python3 tools/gen_sdk.py            write both artifacts
    python3 tools/gen_sdk.py --check    exit 1 when the disk copies drift from schema + profile

Repairs applied to the codegen's output — each one is a measured defect of that output, not a taste:

  1. `type` tags and a discriminated root union. 18 of the 30 arms lost their `type` const, so
     {"type": "float", …} validated as `Case` (measured); the other 12 were inlined anonymously
     (`Accrete1..12`) while their named classes sat unreferenced. We tag every member and build the
     union over the 30 named classes.
  2. `bind: dict[str, Bind]`, with `Bind` discriminated on `kind`. The codegen flattened the map to
     `dict[str, Any]` and left the `Bind` model unreferenced — free-form bindings on the wire.
  3. `PositionAttr` gains the flattened `left`/`right`/`top`/`bottom` keys. serde's `#[flatten]` hides
     them from `properties` (they arrive in `allOf`), so the codegen emitted only class/selector plus
     two unreferenced fragments — `float`'s positioning deserialized as silently dropped.
  4. A stable header. The codegen's own header carries a timestamp, which would make a drift gate
     report a difference on every run.
"""

from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "accrete.schema.json"
PROFILE_PATH = ROOT / "profile" / "profile.json"
SDK_DIR = ROOT / "reflux" / "sdk"
TYPES_PATH = SDK_DIR / "types.py"
BUILDERS_PATH = SDK_DIR / "builders.py"
CODEGEN = "datamodel-code-generator==0.85.0"

REGEN = "Regenerate: python3 tools/gen_sdk.py      Verify: python3 tools/gen_sdk.py --check"

TYPES_HEADER = f'''"""GENERATED from schema/accrete.schema.json by tools/gen_sdk.py — do not edit.

The wire's types: one class per accrete type, plus the `Accrete` union discriminated on `type` and
the `Bind` union discriminated on `kind`. Field names are the wire's names (`class_` carries the
alias `class`); a value that is `None` is absent on this wire.

{REGEN}
"""
'''

BUILDERS_HEADER = f'''"""GENERATED from schema/accrete.schema.json + profile/profile.json by tools/gen_sdk.py — do not edit.

The constructor surface: one function per type the profile exposes, named after the wire's own
`type` value. Which arguments are positional, which bind keys exist, and what is hidden is decided
by the profile; annotations and defaults come from the schema. Every builder validates through the
type layer before returning, so a node that contradicts the wire is refused at construction.

{REGEN}
"""
'''

TYPES_IMPORTS = """from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field

"""

BUILDERS_IMPORTS = """from __future__ import annotations

from typing import Any

from ._parse import bind_entry, bind_value, drop_none, parse
from .types import *  # noqa: F403 — the wire's names are the SDK's names
from .types import Accrete
"""

ANON = re.compile(r"^Accrete\d+$")
# Dropped and rebuilt by the post-pass: the codegen's root RootModel (we emit the union alias
# instead), the `Bind` RootModel (same, discriminated on `kind`), and the two fragments it hoisted
# out of PositionAttr's flattened union.
REBUILT = {"Accrete", "Bind", "PositionAttr1", "PositionAttr2"}

SHARED_FIELDS = {"type", "attrs", "bind", "children", "item", "id"}
HIDDEN_ATTRS = {"class", "selector"}


def load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text())


def arm_list(schema: dict) -> list[tuple[str, str]]:
    """(the wire's `type` value, the `$defs` name behind it), in the schema's own order."""
    return [(a["properties"]["type"]["const"], a["$ref"].rsplit("/", 1)[1]) for a in schema["oneOf"]]


def walk(node: dict):
    yield node
    for key in ("anyOf", "oneOf", "allOf"):
        for sub in node.get(key) or ():
            yield from walk(sub)


def flattened_properties(defn: dict) -> list[str]:
    """Property names hiding inside `allOf` (serde's `#[flatten]`): flat siblings on the wire."""
    names: list[str] = []
    for entry in defn.get("allOf") or ():
        for variant in walk(entry):
            for name in (variant.get("properties") or {}):
                if name not in names:
                    names.append(name)
    return names


class Block:
    __slots__ = ("name", "header", "body", "bases")

    def __init__(self, name: str, header: str, body: list[str], bases: tuple[str, ...] = ()):
        self.name, self.header, self.body, self.bases = name, header, body, bases

    @property
    def text(self) -> list[str]:
        return [self.header, *self.body]


def class_blocks(src: str) -> list[Block]:
    """Every top-level class, located by ast and cut by line (so the body text stays verbatim)."""
    lines = src.splitlines()
    blocks: list[Block] = []
    for node in ast.parse(src).body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = tuple(ast.unparse(base) for base in node.bases)
        end = node.end_lineno or node.lineno
        blocks.append(Block(node.name, lines[node.lineno - 1], lines[node.lineno : end], bases))
    return blocks


def codegen(schema_path: pathlib.Path, dest: pathlib.Path) -> None:
    try:
        out = subprocess.run(
            ["uvx", "-q", "--from", CODEGEN, "datamodel-codegen",
             "--input", str(schema_path), "--input-file-type", "jsonschema", "--output", str(dest)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except FileNotFoundError as e:
        raise SystemExit(f"cannot run uvx: {e} — {CODEGEN} is fetched by uvx (first run needs network)") from e
    if out.returncode != 0 or not dest.exists():
        tail = out.stderr.decode(errors="replace").strip().splitlines()[-6:]
        raise SystemExit("datamodel-codegen failed:\n  " + "\n  ".join(tail))


def enum_default(line: str, enums: set[str]) -> str:
    """A string default on an enum-typed field → the enum member (the codegen emits `= 'render'`).

    Left alone, pydantic serializes that field through the enum's schema and warns; the member is
    what the wire means.
    """
    m = re.match(r"^(\s+\w+: ([\w.]+)(?: \| None)? = )'([^']*)'$", line)
    if m and m.group(2) in enums:
        return f"{m.group(1)}{m.group(2)}({m.group(3)!r})"
    return line


def repair(src: str, schema: dict, profile: dict) -> str:
    """datamodel-codegen's output → the type layer we ship (module docstring, repairs 1-4)."""
    arms = arm_list(schema)
    defs = schema["$defs"]
    const_of = {name: const for const, name in arms}
    blocks_all = class_blocks(src)
    enums = {block.name for block in blocks_all if "Enum" in block.bases}
    kept: list[Block] = []

    for block in blocks_all:
        if ANON.fullmatch(block.name) or block.name in REBUILT:
            continue
        body = list(block.body)
        if block.name in const_of and not any(re.match(r"\s+type:", ln) for ln in body):
            tag = repr(const_of[block.name])
            body.append(f"    type: Literal[{tag}] = {tag}")
        if block.name == "PositionAttr":
            for name in flattened_properties(defs["PositionAttr"]):
                body.append(f"    {name}: str | None = None")
        body = [
            re.sub(r"^(\s+)bind: dict\[str, Any\] \| None = None$",
                   r"\1bind: dict[str, Bind] | None = None", ln)
            for ln in body
        ]
        body = [enum_default(ln, enums) for ln in body]
        kept.append(Block(block.name, block.header, body, block.bases))

    names = [block.name for block in kept] + ["Accrete", "Bind"]
    parts = [TYPES_IMPORTS, f"__all__ = {json.dumps(names)}", ""]
    parts += [ln for block in kept for ln in ("", "", *block.text)]

    union = " | ".join(name for _, name in arms)
    bind_union = " | ".join(f"Bind{i}" for i in range(1, 7))
    parts += [
        "",
        "",
        "# The root union, discriminated on `type`: each arm is one of the classes above, so a node",
        "# validates into its own class (no wrapper to unwrap) and an unknown `type` is refused.",
        f"Accrete = Annotated[Union[{union}], Field(discriminator='type')]",
        "",
        "# `bind` is a map of these, discriminated on `kind`.",
        f"Bind = Annotated[Union[{bind_union}], Field(discriminator='kind')]",
        "",
        "",
        "# Forward references (`children: list[Accrete]`) resolve here, now that the aliases exist.",
    ]
    parts += [f"{block.name}.model_rebuild()" for block in kept if "BaseModel" in block.bases]
    return "\n".join(parts) + "\n"


def annotation(node: dict) -> str:
    """A JSON-Schema fragment → a Python annotation (only the shapes this schema uses)."""
    if "$ref" in node:
        return node["$ref"].rsplit("/", 1)[1]
    for key in ("anyOf", "oneOf"):
        if key in node:
            return " | ".join(annotation(sub) for sub in node[key])
    t = node.get("type")
    nullable = False
    if isinstance(t, list):
        nullable = "null" in t
        t = next((x for x in t if x != "null"), None)
    base = {
        "string": "str",
        "boolean": "bool",
        "integer": "int",
        "number": "float",
        "object": "dict[str, Any]",
        "null": "None",
    }.get(t, "Any")
    if "array" == t:
        base = f"list[{annotation(node['items'])}]" if node.get("items") else "list[Any]"
    if nullable and base != "Any":
        base = f"{base} | None"
    return base


def literal(node: dict) -> str | None:
    return repr(node["default"]) if "default" in node else None


def attrs_def_name(defn: dict) -> str | None:
    for sub in walk((defn.get("properties") or {}).get("attrs") or {}):
        if "$ref" in sub:
            return sub["$ref"].rsplit("/", 1)[1]
    return None


def param(name: str, annotation_text: str, default: str | None = None) -> str:
    return f"{name}: {annotation_text}" + (f" = {default}" if default is not None else " = None")


def builders_text(schema: dict, profile: dict) -> str:
    arms = arm_list(schema)
    defs = schema["$defs"]
    types = profile["types"]
    hidden = set(profile.get("hidden_attrs", [])) | HIDDEN_ATTRS
    renames = profile.get("kwarg_renames", {})

    unknown = [c for c in types if c not in {c for c, _ in arms}]
    missing = [c for c, _ in arms if c not in types]
    if unknown:
        raise SystemExit(f"profile/profile.json names types the schema does not have: {', '.join(unknown)}")
    if missing:
        raise SystemExit(f"profile/profile.json is missing types: {', '.join(missing)}")

    exposed = sorted(c for c, _ in arms if types[c].get("expose"))
    parts = [BUILDERS_IMPORTS, "", f"__all__ = {json.dumps(exposed)}", ""]

    for const, cls in arms:
        entry = types[const]
        if not entry.get("expose"):
            continue
        defn = defs[cls]
        props = defn.get("properties") or {}
        positional = entry.get("positional")
        kinds = (entry.get("bind") or {}).get("value", [])
        # The positional value's落点: `default` when the type has one, else the only kind it has
        # (a button's positional *is* its submit binding).
        value_kind = None
        if positional == "value":
            value_kind = "default" if "default" in kinds else (kinds[0] if len(kinds) == 1 else "default")

        head: list[str] = []
        keywords: list[str] = []
        call: list[str] = []
        attrs_kw: list[str] = []

        if positional == "children":
            head.append("*children: Accrete")
        elif positional == "value":
            head += ["value: Any = None", "*"]
        else:
            head.append("*")

        # attrs — the profile's hidden list keeps `class`/`selector` (the token lane's future home)
        # out of the producer's reach.
        ref = attrs_def_name(defn)
        if ref:
            attr_def = defs[ref]
            fields = dict(attr_def.get("properties") or {})
            for name in flattened_properties(attr_def):
                fields.setdefault(name, {"type": ["string", "null"]})
            for name, sub in fields.items():
                if name in hidden:
                    continue
                kwname = renames.get(name, name)
                keywords.append(param(kwname, annotation(sub), literal(sub)))
                attrs_kw.append(kwname)

        # top-level fields beyond the ones every node shares (canvas `url`, pages `display`, …)
        extra = []
        for name, sub in props.items():
            if name in SHARED_FIELDS:
                continue
            kwname = renames.get(name, name)
            keywords.append(param(kwname, annotation(sub), literal(sub)))
            extra.append(kwname)

        # bind — one keyword per (key, kind) the profile declares for this type
        bind_parts: list[str] = []
        for key, key_kinds in (entry.get("bind") or {}).items():
            key_args: list[str] = []
            for kind in key_kinds:
                if key == "value" and kind == value_kind and positional == "value":
                    key_args.append(f"{kind}=value")
                    continue
                if kind == "submit":
                    key_args.append("submit=value")
                    continue
                kwname = kind if key == "value" else (key if kind == "default" else f"{key}_{kind}")
                if kwname == "default":
                    kwname = "value"
                keywords.append(param(kwname, "Any"))
                key_args.append(f"{kind}={kwname}")
            if key == "value" and "field" in key_kinds:
                keywords.append(param("payload", "Any"))
                key_args.append("payload=payload")
            if key == "value" and entry.get("js_kind"):
                keywords.append(param("kind", "JsType"))
                key_args.append("js_kind=kind")
            if key == "value":
                bind_parts.append(f"value=bind_value({', '.join(key_args)})")
            else:
                bind_parts.append(f"{key}=bind_entry({key!r}, {', '.join(key_args)})")
        if entry.get("item"):
            keywords.append(param("item", "Any"))
        keywords.append(param("id", "str | None"))

        body = [
            f"def {const}(",
            *[f"    {p}," for p in head],
            *[f"    {p}," for p in keywords],
            f") -> {cls}:",
            f'    """Build a `{const}` node (the wire type `{const}`)."""',
            f"    attrs = drop_none({', '.join(f'{a}={a}' for a in attrs_kw)})" if attrs_kw else "    attrs = None",
            f"    bind = drop_none({', '.join(bind_parts)})" if bind_parts else "    bind = None",
        ]
        node_args = [f'type={const!r}', "attrs=attrs", "bind=bind", "id=id"]
        if positional == "children":
            node_args.append("children=list(children) or None")
        if entry.get("item"):
            node_args.append("item=list(item) or None")
        node_args += [f"{name}={name}" for name in extra]
        body.append(f"    return parse(drop_none({', '.join(node_args)}), {cls})")
        parts += [*body, "", ""]

    return "\n".join(parts).rstrip("\n") + "\n"


def assemble(schema: dict, profile: dict) -> dict[pathlib.Path, str]:
    with tempfile.TemporaryDirectory() as tmp:
        raw = pathlib.Path(tmp) / "raw_models.py"
        codegen(SCHEMA_PATH, raw)
        raw_src = raw.read_text()
    return {
        TYPES_PATH: repair(raw_src, schema, profile),
        BUILDERS_PATH: builders_text(schema, profile),
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Generate the Python SDK from the schema and the profile.")
    ap.add_argument("--check", action="store_true", help="do not write; exit 1 if the disk drifts")
    args = ap.parse_args(argv[1:])

    artifacts = assemble(load(SCHEMA_PATH), load(PROFILE_PATH))
    drifted: list[str] = []
    for path, text in artifacts.items():
        if args.check:
            if (path.read_text() if path.exists() else "") != text:
                drifted.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            print(f"wrote {path.relative_to(ROOT)} ({len(text)} B)")
    if args.check:
        if drifted:
            print("drift — regenerate with `python3 tools/gen_sdk.py`:\n  " + "\n  ".join(drifted))
            return 1
        print("in sync — types.py and builders.py match the schema and the profile")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))