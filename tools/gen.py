#!/usr/bin/env python3
"""One source → two artifacts.

    python3 tools/gen.py            # write shell/js/components.generated.js and
                                    # reflux/components_generated.py from spec/components.json
    python3 tools/gen.py --check    # exit 1 if either artifact drifts from the spec

Everything the shell validates against and every builder a producer calls comes from the
spec. Hand-writing either side is what the drift check exists to prevent.
"""

from __future__ import annotations

import json
import pprint
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SPEC = REPO / "spec" / "components.json"
JS_OUT = REPO / "shell" / "js" / "components.generated.js"
TABLES_OUT = REPO / "reflux" / "tables_generated.py"
PY_OUT = REPO / "reflux" / "components_generated.py"

DOMAIN_KINDS = {"enum", "string", "url", "int", "bool"}


class SpecError(Exception):
    pass


def domain_kind(domain: dict) -> str | None:
    """A domain is either {"enum": [...]} or {"type": "string" | "url" | "int" | "bool"}."""
    if "enum" in domain:
        return "enum"
    kind = domain.get("type")
    return kind if kind in DOMAIN_KINDS else None


def load_spec(path: Path = SPEC) -> dict:
    spec = json.loads(path.read_text(encoding="utf-8"))
    validate(spec)
    return spec


def validate(spec: dict) -> None:
    for key in (
        "spec_version",
        "reserved_prefix",
        "ops",
        "max_ops_per_frame",
        "bind_keys",
        "fire_events",
        "components",
    ):
        if key not in spec:
            raise SpecError(f"spec is missing {key}")
    if not isinstance(spec["max_ops_per_frame"], int) or spec["max_ops_per_frame"] < 1:
        raise SpecError("max_ops_per_frame must be a positive int — both sides refuse over it")
    if not spec["reserved_prefix"].endswith(":"):
        raise SpecError("reserved_prefix must end with ':' (it is a namespace, not a word)")
    fire_events = spec["fire_events"]
    if not fire_events or len(set(fire_events)) != len(fire_events):
        raise SpecError("fire_events must be non-empty and unique (the shell delegates over it)")
    for name, comp in spec["components"].items():
        where = f"component {name}"
        if comp.get("children") not in spec["children_cardinality"]:
            raise SpecError(f"{where}: bad children cardinality {comp.get('children')!r}")
        if not set(comp.get("bind", [])) <= set(spec["bind_keys"]):
            raise SpecError(f"{where}: bind keys outside {spec['bind_keys']}")
        if not isinstance(comp.get("local"), list):
            raise SpecError(f"{where}: local must be a list")
        fire = comp.get("fire")
        if not isinstance(fire, list):
            raise SpecError(f"{where}: fire must be a list (empty when the component uplinks nothing)")
        if not set(fire) <= set(fire_events):
            raise SpecError(f"{where}: fire events outside {fire_events}")
        # the uplink timing is part of the contract: a component that accepts `event` must say
        # when it fires, and a component that accepts no event must fire on nothing
        if bool(fire) != ("event" in comp.get("bind", [])):
            raise SpecError(f"{where}: fire must be non-empty exactly when bind accepts 'event'")
        for attr, dom in comp.get("attrs", {}).items():
            kind = domain_kind(dom)
            if kind is None:
                raise SpecError(f"{where}.{attr}: unknown domain kind, got {dom}")
            if kind == "enum":
                values = dom["enum"]
                if not values or len(set(values)) != len(values):
                    raise SpecError(f"{where}.{attr}: enum must be non-empty and unique")
                if "default" in dom and dom["default"] not in values:
                    raise SpecError(f"{where}.{attr}: default outside the enum")
            if kind == "int":
                if dom.get("min", 0) > dom.get("max", 0):
                    raise SpecError(f"{where}.{attr}: min > max")
            if kind == "bool" and not isinstance(dom.get("default", False), bool):
                raise SpecError(f"{where}.{attr}: bool default must be a bool")
        # payload entries must name declared local state
        if "payload" in comp.get("bind", []) and not comp.get("local"):
            raise SpecError(f"{where}: declares payload but carries no local state")
        primary = comp.get("primary")
        if primary is not None:
            if comp.get("children") != "none":
                raise SpecError(f"{where}: primary is only for leaf components (children: none)")
            if primary not in comp.get("attrs", {}):
                raise SpecError(f"{where}: primary {primary!r} is not one of its attrs")
            if "default" in comp["attrs"][primary]:
                raise SpecError(f"{where}: primary {primary!r} must be required (no default)")


def js_text(spec: dict) -> str:
    components = json.dumps(spec["components"], indent=2, ensure_ascii=False, sort_keys=True)
    ops = json.dumps(spec["ops"], ensure_ascii=False)
    binds = json.dumps(spec["bind_keys"], ensure_ascii=False)
    fires = json.dumps(spec["fire_events"], ensure_ascii=False)
    return (
        "// GENERATED from spec/components.json — do not edit.\n"
        "// Regenerate: python3 tools/gen.py      Verify: python3 tools/gen.py --check\n"
        "\n"
        f"export const SPEC_VERSION = {json.dumps(spec['spec_version'])};\n"
        f"export const RESERVED_PREFIX = {json.dumps(spec['reserved_prefix'])};\n"
        f"export const OPS = {ops};\n"
        f"export const MAX_OPS_PER_FRAME = {spec['max_ops_per_frame']};\n"
        f"export const BIND_KEYS = {binds};\n"
        f"export const FIRE_EVENTS = {fires};\n"
        f"export const COMPONENTS = {components};\n"
    )


def _ann(dom: dict, required: bool) -> tuple[str, str | None]:
    """Annotation and default literal for one attr."""
    if "enum" in dom:
        literal = " | ".join(json.dumps(v) for v in dom["enum"])
        default = repr(dom["default"]) if "default" in dom else None
    elif dom.get("type") == "bool":
        literal, default = "bool", repr(dom["default"]) if "default" in dom else None
    elif dom.get("type") == "int":
        literal, default = "int", repr(dom["default"]) if "default" in dom else None
    else:  # string / url
        literal = "str"
        default = repr(dom["default"]) if "default" in dom else None
    return (literal if required else f"{literal} | None"), default


def ctor(name: str, comp: dict, spec: dict) -> tuple[str, str]:
    """Return (the builder's parameter list, the make() argument list).

    A leaf component's `primary` attr is the positional one (`text("hello")`), containers
    take their children positionally, and everything else is keyword-only.
    """
    attrs = comp.get("attrs", {})
    primary = comp.get("primary")
    positional: list[str] = []
    keyword: list[str] = []
    for attr, dom in sorted(attrs.items()):
        ann, default = _ann(dom, "default" not in dom)
        piece = f"{attr}: {ann}" + ("" if default is None else f" = {default}")
        (positional if attr == primary else keyword).append(piece)
    for key in spec["bind_keys"]:
        if key in comp.get("bind", []):
            ann = "list[str] | None" if key == "payload" else "str | None"
            keyword.append(f"{key}: {ann} = None")
    keyword.append("id: str | None = None")

    leaf = comp.get("children") == "none"
    if not leaf:
        params = ", ".join(["*children: Node", *keyword])
    elif positional:
        params = ", ".join([positional[0], "*", *keyword]) if keyword else positional[0]
    else:
        params = ", ".join(["*", *keyword]) if keyword else ""

    attrs_expr = "{" + ", ".join(f'"{a}": {a}' for a in sorted(attrs)) + "}"
    bind_args = ", ".join(f"{k}={k}" for k in spec["bind_keys"] if k in comp.get("bind", []))
    call = ", ".join(
        x for x in [f'"{name}"', attrs_expr, "children" if not leaf else "()", "id=id", bind_args] if x
    )
    return params, call


def py_text(spec: dict) -> str:
    lines = [
        '"""GENERATED from spec/components.json — do not edit.',
        "",
        "The builders. One layer above `tables_generated` (pure data) and `node.make`",
        "(the validating boundary), so import order never cycles.",
        "",
        "Regenerate: python3 tools/gen.py      Verify: python3 tools/gen.py --check",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from .node import Node, make",
        "from .tables_generated import (",
        "    BIND_KEYS,",
        "    COMPONENTS,",
        "    FIRE_EVENTS,",
        "    OPS,",
        "    RESERVED_PREFIX,",
        "    SPEC_VERSION,",
        ")",
        "",
        "__all__ = [",
        f"    {', '.join(repr(n) for n in sorted(spec['components']))},",
        '    "SPEC_VERSION",',
        '    "RESERVED_PREFIX",',
        '    "OPS",',
        '    "BIND_KEYS",',
        '    "FIRE_EVENTS",',
        '    "COMPONENTS",',
        "]",
        "",
        "",
    ]
    for name, comp in sorted(spec["components"].items()):
        params, call = ctor(name, comp, spec)
        lines += [
            f"def {name}({params}) -> Node:",
            f'    """{comp["family"]}: {comp.get("children")} children'
            + (f'; local state: {", ".join(comp["local"])}' if comp.get("local") else "")
            + '"""',
            f"    return make({call})",
            "",
            "",
        ]
    return "\n".join(lines)


def tables_text(spec: dict) -> str:
    components = json.dumps(spec["components"], indent=2, ensure_ascii=False, sort_keys=True)
    return (
        '"""GENERATED from spec/components.json — do not edit.\n'
        "\n"
        "Pure data: the vocabulary both the shell and every SDK validate against. It imports\n"
        "nothing, so it can be the bottom layer.\n"
        "\n"
        "Regenerate: python3 tools/gen.py      Verify: python3 tools/gen.py --check\n"
        '"""\n'
        "\n"
        "from __future__ import annotations\n"
        "\n"
        "import json\n"
        "\n"
        f"SPEC_VERSION = {spec['spec_version']!r}\n"
        f"RESERVED_PREFIX = {spec['reserved_prefix']!r}\n"
        f"OPS = {spec['ops']!r}\n"
        f"MAX_OPS_PER_FRAME = {spec['max_ops_per_frame']!r}\n"
        f"BIND_KEYS = {spec['bind_keys']!r}\n"
        f"FIRE_EVENTS = {spec['fire_events']!r}\n"
        "\n"
        "COMPONENTS: dict = json.loads(\n"
        '    """\n'
        f"{components}\n"
        '"""\n'
        ")\n"
    )


ARTIFACTS = {JS_OUT: js_text, TABLES_OUT: tables_text, PY_OUT: py_text}


def main(argv: list[str]) -> int:
    check = "--check" in argv
    spec = load_spec()
    drifted: list[Path] = []
    for path, emit in ARTIFACTS.items():
        text = emit(spec)
        if check:
            current = path.read_text(encoding="utf-8") if path.is_file() else ""
            if current != text:
                drifted.append(path)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print(f"[gen] wrote {path.relative_to(REPO)}  ({len(text)} B)")
    if check:
        for path in drifted:
            print(f"[gen] DRIFT: {path.relative_to(REPO)} does not match the spec", file=sys.stderr)
        if drifted:
            print("[gen] run: python3 tools/gen.py", file=sys.stderr)
            return 1
        print(f"[gen] up to date: spec v{spec['spec_version']}, "
              f"{len(spec['components'])} components, {len(ARTIFACTS)} artifacts")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))