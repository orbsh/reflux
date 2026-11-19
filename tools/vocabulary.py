"""The vocabulary: one model of what a producer may build, read by every emitter.

    schema/accrete.schema.json   the wire's snapshot — types, fields, value domains
    profile/profile.json         reflux's selection — which types are exposed, which keywords exist,
                                 which value channels each one offers, which variant names are closed
    reflux/sdk/types.py          the generated type layer — **field order** comes from here, because
                                 that order is what `model_dump` writes on the wire

Three inputs, one shape: `vocabulary()` returns `TypeModel`s, and an emitter (Python in
`tools/gen_sdk.py`, Rust in `tools/gen_rust.py`) does nothing but format them. Nothing here may be
target-specific: if an emitter finds itself deciding *what* the vocabulary contains, the decision
belongs in this file.

Why the field order is not this file's opinion: the wire's byte order for a node is its class's
declaration order in `types.py` (pydantic serializes in declaration order, and the codegen's order
came from the schema). Reading it from the generated file — rather than recomputing "alphabetical,
probably" — is what lets a second language emit the same bytes. A `Bind` (ADR 0031's one value, one
address, one scope) is the same story: its field order (`default, path, scope, slot, type`) is an
accident of serde's struct, not alphabetical, so the emitter reads it rather than assuming it.

The two directions (ADR 0031 §2) are the only value surface a builder offers: `source` is where a
value comes from, `sink` is where it goes, and the profile says which of them the renderer actually
reads/writes for that type. A node's *named second* values (`options`, `select`, `placeholder`) are
not channels — each is one field of its own type, found in the schema.
"""

from __future__ import annotations

import ast
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "accrete.schema.json"
PROFILE_PATH = ROOT / "profile" / "profile.json"
TYPES_PATH = ROOT / "reflux" / "sdk" / "types.py"

SHARED_FIELDS = {"type", "attrs", "source", "sink", "children", "item", "id"}
# `class` is the token lane's alone: a producer reaches a class by name (`variant=`), never by
# string. `selector` is *not* here — since ADR 0031 §4 it is the name of an `entry`'s field, so it
# is data a producer must be able to write.
HIDDEN_ATTRS = {"class"}
# The two directions, in flow order: in, then out (ADR 0031 §2).
CHANNELS = ("source", "sink")


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


def read_orders(types_src: str) -> dict[str, list[str]]:
    """class → field order, read from the generated type layer (the wire's byte order)."""
    classes: dict[str, list[str]] = {}
    for node in ast.parse(types_src).body:
        if not isinstance(node, ast.ClassDef):
            continue
        classes[node.name] = _annotated_names(node)
    return classes


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


class Channel:
    """One direction of a value on a node (ADR 0031 §2): `source` in, `sink` out.

    `default` is the profile's word for "a bare constant is a legal value here" — a read with a
    constant is `{default: …}`, a write with one is a slot name, so only a read can have it.
    """

    __slots__ = ("name", "default")

    def __init__(self, name: str, default: bool):
        self.name, self.default = name, default


class TypeModel:
    __slots__ = ("wire", "cls", "positional", "params", "attrs", "extras", "channels", "values",
                 "item", "variants", "node_order", "attrs_order")

    def __init__(self, wire: str, cls: str, positional: str | None):
        self.wire, self.cls, self.positional = wire, cls, positional
        self.params: list[Param] = []
        self.attrs: list[Param] = []
        self.extras: list[Param] = []
        self.channels: list[Channel] = []
        self.values: list[Param] = []
        self.item = False
        self.variants: dict[str, str] = {}
        self.node_order: list[str] = []
        self.attrs_order: list[str] = []

    def param(self, kwarg: str) -> Param:
        for p in self.params:
            if p.kwarg == kwarg:
                return p
        raise ModelError(f"{self.wire}: no keyword {kwarg!r}")


def is_bind(fragment: dict) -> bool:
    """Is this schema fragment `Bind` (a value's address), rather than a plain payload?"""
    return any((sub.get("$ref") or "").rsplit("/", 1)[-1] == "Bind" for sub in walk(fragment))


def _enum_of(fragment: dict, defs: dict) -> list[str] | None:
    """The strings of a `$ref`-to-string-enum fragment, or None when it is anything else."""
    name = (fragment.get("$ref") or "").rsplit("/", 1)[-1]
    values = (defs.get(name) or {}).get("enum")
    if isinstance(values, list) and all(isinstance(v, str) for v in values):
        return values
    return None


def is_string_set(fragment: dict, defs: dict) -> bool:
    """Is this a `SubmitSet`-shaped domain — one string, or a list of them (ADR 0032's `submit`)?"""
    name = (fragment.get("$ref") or "").rsplit("/", 1)[-1]
    target = defs.get(name) or {}
    branches = target.get("anyOf") or target.get("oneOf") or []
    if len(branches) != 2:
        return False
    kinds = [_enum_of(b.get("items") or {}, defs) if b.get("type") == "array" else _enum_of(b, defs)
             for b in branches]
    return kinds[0] is not None and kinds[0] == kinds[1]


def _string_domain(fragment: dict, defs: dict) -> bool:
    """Is this a closed set of strings — an `enum`, or a branch mix of string enums and consts?

    `Wrap` is `oneOf: [{enum: [wrap, wrap-reverse]}, {const: nowrap}]`: serde cannot derive a
    `NoWrap` variant, so the third word is a const. The caller still writes `wrap="nowrap"`, so a
    branch that names its strings either way counts.
    """
    if _enum_of(fragment, defs) is not None:
        return True
    name = (fragment.get("$ref") or "").rsplit("/", 1)[-1]
    target = defs.get(name) or {}
    branches = target.get("anyOf") or target.get("oneOf") or []
    return bool(branches) and all(
        b.get("type") == "string" and ("const" in b or isinstance(b.get("enum"), list)) for b in branches
    )


def json_alt(fragment: dict, defs: dict) -> str | None:
    """The wire's own JSON spelling of a keyword the type layer types as a model or an enum.

    `dir: row`, `step: {timer: 4000}`, `header: {selector, layers}`, `fields: [{key}]` are what the
    schema, the ADR's YAML and every hand-written frame say. The builder validates through pydantic,
    which takes either the generated model or its JSON — so the annotation has to offer both, or a
    type checker refuses the documented call. This is `SubmitSet`'s lesson (`submit: enter` next to
    `submit: [enter]`) applied to the rest of the attribute surface; the Rust emitter has always
    shipped these as `&str` / `Value` for the same reason.
    """
    if _string_domain(fragment, defs):
        return "str"
    for key in ("anyOf", "oneOf"):
        if key in fragment:
            # A nullable union is one shape with `None` beside it: widen the shape, not the union.
            rest = [b for b in fragment[key] if b.get("type") != "null"]
            return json_alt(rest[0], defs) if len(rest) == 1 else None
    name = (fragment.get("$ref") or "").rsplit("/", 1)[-1]
    target = defs.get(name) or {}
    if fragment.get("properties") or target.get("properties"):
        return "dict[str, Any]"
    branches = target.get("anyOf") or target.get("oneOf") or []
    if branches and all(json_alt(branch, defs) == "dict[str, Any]" for branch in branches):
        return "dict[str, Any]"  # `Step`'s `{timer}` / `{slot}` arms
    t = fragment.get("type")
    if t == "array" or (isinstance(t, list) and "array" in t):
        return json_alt(fragment.get("items") or {}, defs)
    return None


def with_alt(annotation_text: str, alt: str) -> str:
    """`list[Column] | None` + `dict[str, Any]` → `list[Column | dict[str, Any]] | None`.

    The alternative goes *inside* the list (a caller passes a list of dicts) and before the
    nullability (which stays last, where a reader expects it).
    """
    suffix = " | None"
    trailing = suffix if annotation_text.endswith(suffix) else ""
    core = annotation_text[: -len(suffix)] if trailing else annotation_text
    head = "list["
    if core.startswith(head):
        close = core.index("]")
        core = f"{head}{core[len(head):close]} | {alt}]{core[close + 1:]}"
    else:
        core = f"{core} | {alt}"
    return core + trailing


def keyword_type(fragment: dict, defs: dict) -> tuple[str, str]:
    """(the keyword's annotation, the second language's kind) for a node or attrs field.

    A field the schema leaves nullable stays nullable here: every keyword defaults to `None`, and
    an annotation that hides that (`multiline: bool = None`) would lie about what absence means.
    A bare-or-list string domain (`submit`) is exposed as what a caller actually passes, not as
    the codegen's `RootModel` wrapper.
    """
    if is_string_set(fragment, defs):
        return "list[str] | str | None", "strlist"
    annotation_text = annotation(fragment)
    alt = json_alt(fragment, defs)
    if alt is not None:
        annotation_text = with_alt(annotation_text, alt)
    if literal(fragment) is None and "None" not in annotation_text:
        annotation_text = f"{annotation_text} | None"
    return annotation_text, rkind(fragment, defs)


def vocabulary(schema: dict, profile: dict, types_src: str) -> list[TypeModel]:
    """Every exposed type, in the schema's order, with its keywords and its wire order."""
    arms = arm_list(schema)
    defs = schema["$defs"]
    entries = profile["types"]
    hidden = set(profile.get("hidden_attrs", [])) | HIDDEN_ATTRS
    renames = profile.get("kwarg_renames", {})
    tokens = profile.get("tokens") or {}
    classes = read_orders(types_src)

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
        facts = entry.get("channels") or {}
        offered = [name for name in CHANNELS if facts.get(name)]
        stray = [name for name in offered if name not in props]
        if stray:
            # A channel the schema does not carry on this node is a frame error on the wire; a
            # builder that offered it would emit a field serde drops.
            raise ModelError(f"{const}: the profile declares channels the schema does not have: {', '.join(stray)}")
        if positional == "value" and "source" not in offered:
            raise ModelError(f"{const}: a positional value is a constant source, but the profile offers no source")
        if positional == "value" and not facts.get("default"):
            raise ModelError(f"{const}: a positional value is a constant, but the profile offers no default")
        if facts.get("default") and "source" not in offered:
            raise ModelError(f"{const}: `default` needs a source to be the default of")

        model = TypeModel(const, cls, positional)
        model.variants = dict(tokens.get(const) or {})
        model.item = bool(entry.get("item"))
        model.node_order = classes.get(cls, [])
        model.channels = [Channel(name, bool(facts.get("default")) if name == "source" else False)
                          for name in offered]

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
                ann, kind = keyword_type(sub, defs)
                model.attrs.append(Param(kw, ann, literal(sub), kind, "attrs", name))

        model.params.extend(model.attrs)
        for name in offered:
            model.params.append(Param(name, "Any", None, "json", "channel", name))

        for name, sub in props.items():
            if name in SHARED_FIELDS or name in offered:
                continue
            kw = renames.get(name, name)
            # A Bind-valued field of its own (`options`, `select`, `placeholder`, …) is a named
            # second value: same Bind-or-value rule as a channel, its own keyword.
            lane = "value" if is_bind(sub) else "extra"
            ann, kind = ("Any", "json") if lane == "value" else keyword_type(sub, defs)
            param = Param(kw, ann, None if lane == "value" else literal(sub), kind, lane, name)
            (model.values if lane == "value" else model.extras).append(param)
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