"""The vocabulary: one model of what a producer may build, read by every emitter.

    schema/accrete.schema.json   the wire's snapshot — types, fields, value domains
    profile/profile.json         reflux's selection — which types are exposed, which keywords exist,
                                 which bind 落点 each one carries, which variant names are closed
    reflux/sdk/types.py          the generated type layer — **field order** comes from here, because
                                 that order is what `model_dump` writes on the wire

Three inputs, one shape: `vocabulary()` returns `TypeModel`s, and an emitter (Python in
`tools/gen_sdk.py`, Rust in `tools/gen_rust.py`) does nothing but format them. Nothing here may be
target-specific: if an emitter finds itself deciding *what* the vocabulary contains, the decision
belongs in this file.

Why the field order is not this file's opinion: the wire's byte order for a node is its class's
declaration order in `types.py` (pydantic serializes in declaration order, and the codegen's order
came from the schema). Reading it from the generated file — rather than recomputing "alphabetical,
probably" — is what lets a second language emit the same bytes. A bind entry is the same story
with a twist: serde's flattened unions gave the `Bind1..6` classes an order that is *not*
alphabetical (`default, type, kind, path, source`), so the order is read, never assumed.
"""

from __future__ import annotations

import ast
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "accrete.schema.json"
PROFILE_PATH = ROOT / "profile" / "profile.json"
TYPES_PATH = ROOT / "reflux" / "sdk" / "types.py"

SHARED_FIELDS = {"type", "attrs", "bind", "children", "item", "id"}
HIDDEN_ATTRS = {"class", "selector"}


class ModelError(SystemExit):
    """A profile or schema that cannot produce a vocabulary — loud at generation time."""


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


def _annotated_names(node: ast.ClassDef) -> list[str]:
    names: list[str] = []
    for stmt in node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            names.append(stmt.target.id)
    return names


def _literal(stmt: ast.AnnAssign) -> str | None:
    """The `Literal['…']` a class declares for a field (used to find each Bind arm's kind)."""
    text = ast.unparse(stmt.annotation)
    m = re.search(r"Literal\['([^']+)'\]", text)
    return m.group(1) if m else None


def read_orders(types_src: str) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """(class → field order, bind kind → field order) read from the generated type layer."""
    classes: dict[str, list[str]] = {}
    bind_orders: dict[str, list[str]] = {}
    for node in ast.parse(types_src).body:
        if not isinstance(node, ast.ClassDef):
            continue
        order = _annotated_names(node)
        classes[node.name] = order
        if not re.fullmatch(r"Bind\d+", node.name):
            continue
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.target.id == "kind":
                kind = _literal(stmt)
                if kind:
                    bind_orders[kind] = order
    return classes, bind_orders


def rkind(fragment: dict, defs: dict) -> str:
    """How a second language should type this field: `str`, `bool`, `int`, `float`, or `json`.

    A `$ref` to a string enum is `str`: the closure of an enum is a wire rule, and this side of the
    fence does not re-check the fence (the server's ingest does, for every language the same way).
    Anything with structure is `json` — a producer that needs map-shaped values says so explicitly.
    """
    if "$ref" in fragment:
        name = fragment["$ref"].rsplit("/", 1)[1]
        target = defs.get(name) or {}
        if isinstance(target.get("enum"), list) and all(isinstance(v, str) for v in target["enum"]):
            return "str"
        return "json"
    for key in ("anyOf", "oneOf"):
        if key in fragment:
            kinds = {rkind(sub, defs) for sub in fragment[key]}
            kinds.discard("null")
            return kinds.pop() if len(kinds) == 1 else "json"
    t = fragment.get("type")
    if isinstance(t, list):
        kinds = [x for x in t if x != "null"]
        t = kinds[0] if len(kinds) == 1 else None
    key = t if isinstance(t, str) else ""
    return {"string": "str", "boolean": "bool", "integer": "int", "number": "float"}.get(key, "json")


def annotation(fragment: dict) -> str:
    """A JSON-Schema fragment → a Python annotation (only the shapes this schema uses)."""
    if "$ref" in fragment:
        return fragment["$ref"].rsplit("/", 1)[1]
    for key in ("anyOf", "oneOf"):
        if key in fragment:
            return " | ".join(annotation(sub) for sub in fragment[key])
    t = fragment.get("type")
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
    if t == "array":
        base = f"list[{annotation(node_items)}]" if (node_items := fragment.get("items")) else "list[Any]"
    if nullable and base != "Any":
        base = f"{base} | None"
    return base


def literal(fragment: dict) -> str | None:
    return repr(fragment["default"]) if "default" in fragment else None


def attrs_def_name(defn: dict) -> str | None:
    for sub in walk((defn.get("properties") or {}).get("attrs") or {}):
        if "$ref" in sub:
            return sub["$ref"].rsplit("/", 1)[1]
    return None


class Param:
    """One keyword of a builder: what it is called, what it may hold, where it lands."""

    __slots__ = ("kwarg", "annotation", "default", "rkind", "lane", "wire")

    def __init__(self, kwarg: str, annotation: str, default: str | None, rkind: str, lane: str, wire: str):
        self.kwarg, self.annotation, self.default = kwarg, annotation, default
        self.rkind, self.lane, self.wire = rkind, lane, wire


class BindOp:
    """One 落点 on one bind key: `value=default`, `options=source`, `value=field` + payload, …"""

    __slots__ = ("key", "kind", "kwarg", "param")

    def __init__(self, key: str, kind: str, kwarg: str | None, param: Param | None):
        self.key, self.kind, self.kwarg, self.param = key, kind, kwarg, param


class TypeModel:
    __slots__ = ("wire", "cls", "positional", "value_kind", "params", "head", "attrs", "extras",
                 "binds", "ops", "item", "variants", "js_kind", "node_order", "attrs_order")

    def __init__(self, wire: str, cls: str, positional: str | None, value_kind: str | None):
        self.wire, self.cls, self.positional, self.value_kind = wire, cls, positional, value_kind
        self.params: list[Param] = []
        self.head: tuple[str, ...] = ()
        self.attrs: list[Param] = []
        self.extras: list[Param] = []
        self.binds: list[tuple[str, list[str]]] = []
        self.ops: list[BindOp] = []
        self.item = False
        self.variants: dict[str, str] = {}
        self.js_kind = False
        self.node_order: list[str] = []
        self.attrs_order: list[str] = []

    def param(self, kwarg: str) -> Param:
        for p in self.params:
            if p.kwarg == kwarg:
                return p
        raise ModelError(f"{self.wire}: no keyword {kwarg!r}")


def vocabulary(schema: dict, profile: dict, types_src: str) -> list[TypeModel]:
    """Every exposed type, in the schema's order, with its keywords and its wire order."""
    arms = arm_list(schema)
    defs = schema["$defs"]
    entries = profile["types"]
    hidden = set(profile.get("hidden_attrs", [])) | HIDDEN_ATTRS
    renames = profile.get("kwarg_renames", {})
    tokens = profile.get("tokens") or {}
    classes, bind_orders = read_orders(types_src)

    unknown = [c for c in entries if c not in {c for c, _ in arms}]
    missing = [c for c, _ in arms if c not in entries]
    if unknown:
        raise ModelError(f"profile/profile.json names types the schema does not have: {', '.join(unknown)}")
    if missing:
        raise ModelError(f"profile/profile.json is missing types: {', '.join(missing)}")

    models: list[TypeModel] = []
    for const, cls in arms:
        entry = entries[const]
        if not entry.get("expose"):
            continue
        defn = defs[cls]
        props = defn.get("properties") or {}
        positional = entry.get("positional")
        kinds = (entry.get("bind") or {}).get("value", [])
        # The positional value's 落点: `default` when the type has one, else the only kind it has
        # (a button's positional *is* its submit binding).
        value_kind = None
        if positional == "value":
            value_kind = "default" if "default" in kinds else (kinds[0] if len(kinds) == 1 else "default")

        model = TypeModel(const, cls, positional, value_kind)
        model.head = () if positional is None else (positional,)
        model.variants = dict(tokens.get(const) or {})
        model.js_kind = bool(entry.get("js_kind"))
        model.item = bool(entry.get("item"))
        model.node_order = classes.get(cls, [])
        model.binds = [(key, list(key_kinds)) for key, key_kinds in (entry.get("bind") or {}).items()]

        ref = attrs_def_name(defn)
        if ref:
            attr_def = defs[ref]
            model.attrs_order = classes.get(ref, [])
            fields = dict(attr_def.get("properties") or {})
            for name in flattened_properties(attr_def):
                fields.setdefault(name, {"type": ["string", "null"]})
            for name, sub in fields.items():
                if name in hidden:
                    continue
                kw = renames.get(name, name)
                param = Param(kw, annotation(sub), literal(sub), rkind(sub, defs), "attrs", name)
                model.attrs.append(param)
                model.params.append(param)

        for name, sub in props.items():
            if name in SHARED_FIELDS:
                continue
            kw = renames.get(name, name)
            param = Param(kw, annotation(sub), literal(sub), rkind(sub, defs), "extra", name)
            model.extras.append(param)
            model.params.append(param)

        for key, key_kinds in model.binds:
            for kind in key_kinds:
                if key == "value" and positional == "value" and kind == model.value_kind:
                    model.ops.append(BindOp(key, kind, None, None))
                    continue
                if kind == "submit":  # the positional value is the submit's
                    if positional != "value":
                        raise ModelError(f"{const}: a `submit` 落点 needs a positional value")
                    model.ops.append(BindOp(key, kind, None, None))
                    continue
                kw = kind if key == "value" else (key if kind == "default" else f"{key}_{kind}")
                if kw == "default":
                    kw = "value"
                param = Param(kw, "Any", None, "json", "bind", key)
                model.ops.append(BindOp(key, kind, kw, param))
                if not any(p.kwarg == kw for p in model.params):
                    model.params.append(param)
            if key == "value" and "field" in key_kinds:
                param = Param("payload", "Any", None, "json", "bind", "payload")
                model.ops.append(BindOp(key, "payload", "payload", param))
                model.params.append(param)
            if key == "value" and model.js_kind:
                param = Param("kind", "JsType", None, "str", "bind", "type")
                model.ops.append(BindOp(key, "type", "kind", param))
                model.params.append(param)
            if "local" in key_kinds:
                # `path` rides a local落点: a client-side slot holds the wrapper an in-page emit
                # wrote, so a reader that wants the payload itself points into it.
                param = Param("path", "str | None", None, "str", "bind", "path")
                model.ops.append(BindOp(key, "path", "path", param))
                model.params.append(param)

        if model.item:
            model.params.append(Param("item", "Any", None, "json", "item", "item"))
        model.params.append(Param("id", "str | None", None, "str", "id", "id"))
        if model.variants:
            model.params.append(Param("variant", "str | None", None, "str", "variant", "class"))
        models.append(model)

    return models


def current() -> list[TypeModel]:
    """The vocabulary as it stands on disk (schema + profile + the type layer's order)."""
    return vocabulary(load(SCHEMA_PATH), load(PROFILE_PATH), TYPES_PATH.read_text())