from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, RootModel, conint


# ADR 0031 §1: where a value is authoritative is a closed enumeration, not a namespace.
Scope = Literal['remote', 'local', 'both']

__all__ = ["Accept", "Align", "ButtonAttr", "ClassAttr", "ColorAttr", "Debounce", "Dir", "Direction", "Draggable", "FieldModel", "FrameAttr", "Header", "ImageAttr", "InputKind", "LinkShape1", "LinkShape", "PanelPlace", "PanelState", "PickerAttr", "PickerBare", "PickerStated1", "PickerStated2", "PickerStated", "ResetMode", "Sink", "SizeAttr", "Source", "Stamp", "Step1", "Step2", "Step", "SubmitMode", "SubmitSet", "TextAttr", "Theme1", "Theme", "Throttle", "Window", "Wrap1", "Wrap", "Button", "Canvas", "Emit", "ForceGraphStyle", "Image", "Input", "LoomAttr", "PanelAttr", "Path", "PickerKind", "Text", "TilesAttr", "Color", "ForceGraph", "Entry", "Frame", "Loom", "Panel", "Picker", "Svg", "Tiles", "Accrete", "Scope"]



class Accept(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    tag: str | None = None


class Align(Enum):
    start = 'start'
    center = 'center'
    end = 'end'


class ButtonAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    oneshot: bool | None = False
    selector: str | None = None


class ClassAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    horizontal: bool | None = Field(
        None,
        description="The container's own layout direction (same field as FrameAttr; ADR 0010 defect fix:\npreviously only Case knew about horizontal, so the col class of select/rack could not be\noverridden by its own attrs — the parent case's horizontal only governed the parent div).",
    )
    selector: str | None = None


class ColorAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    selector: str | None = None


class Debounce(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    debounce: conint(ge=0)


class Dir(Enum):
    row = 'row'
    row_reverse = 'row-reverse'
    col = 'col'
    col_reverse = 'col-reverse'


class Direction(Enum):
    U = 'U'
    D = 'D'
    L = 'L'
    R = 'R'


class Draggable(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    tag: str | None = None


class FieldModel(BaseModel):
    align: Align | None = None
    key: str
    selectors: list[str] | None = Field(
        None,
        description="Extra class tokens for this field's cells: a field is not an element, so it is addressed\nthe way the rest of the renderer addresses things (ADR 0031 §4).",
    )
    title: str | None = Field(
        None, description="The header text; absent falls back to the key's leaf."
    )
    width: str | None = Field(
        None,
        description='A CSS track size (`12rem`, `minmax(0, 2fr)`); absent is `minmax(0, 1fr)`.',
    )


class FrameAttr(BaseModel):
    accept: Accept | None = Field(
        None,
        description='What cargo this box takes (ADR 0034). Absent `tag` = takes any. Needs `sink`:\na drop that cannot emit is a frame error at load.',
    )
    class_: list[str] | None = Field(None, alias='class')
    draggable: Draggable | None = Field(
        None,
        description='This box may be dragged away (ADR 0034). Its cargo is its own subtree — there\nis no second payload to keep in step with it.',
    )
    grid: dict[str, Any] | None = None
    horizontal: bool | None = None
    selector: str | None = None
    style: dict[str, Any] | None = Field(
        None,
        description='Inline style, written as it is. This is the surface `group` had: a frame can\nsay everything a `group` could.',
    )


class Header(BaseModel):
    layers: conint(ge=1, le=2) | None = Field(
        None,
        description='`1` (default) or `2`: how many LINES of header cells there are along the field axis. A\ndirection word (`rows`) named where the header sat, which stopped being true the moment\n`dir: row` made the header a column; a layer is one line whatever axis it runs on.',
    )
    selector: str


class ImageAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    desc: str | None = None
    height: str | None = None
    selector: str | None = None
    thumb: bool | None = False
    width: str | None = None


class InputKind(Enum):
    bool = 'bool'
    number = 'number'
    text = 'text'
    password = 'password'
    button = 'button'
    submit = 'submit'


class LinkShape1(Enum):
    straight = 'straight'


class LinkShape(RootModel[LinkShape1 | Literal['axes'] | Literal['tetra']]):
    root: LinkShape1 | Literal['axes'] | Literal['tetra'] = Field(
        ...,
        description='The graph renderer\'s knobs. Same semantics as canvas\'s `options`: mount-time config, changing it takes\na remount (not on the update leg). The only difference is that this is our own renderer\'s vocabulary, so it can be\ntyped and checked by schema and by patch.\nThe direction of an edge. Both orientations are "interfaces on a node": a link leaves from one orientation and enters\nthe other end\'s orientation, joined in between by a cubic curve.',
    )


class PanelPlace(Enum):
    inline = 'inline'
    anchor = 'anchor'
    viewport = 'viewport'


class PanelState(Enum):
    toggle = 'toggle'
    bound = 'bound'


class PickerAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    dir: Dir | None = Field(
        None,
        description='Which way the options run: `row` is a row of buttons, `col` (the default) a list. It lays out both\nthe standing form and what a fold opens.',
    )
    expand: bool | None = Field(
        None,
        description="Whether the options fold away behind the current choice (`true`) or stand in the page as they are\n(the default). Open and closed is the renderer's own state — it never travels.",
    )
    multiple: bool | None = Field(
        None,
        description='Whether more than one option may be chosen. A single choice is one key; several are a list of them,\nwhich is what the field then packs.',
    )
    selector: str | None = None


class PickerBare(Enum):
    text = 'text'
    bool = 'bool'


class PickerStated1(BaseModel):
    max: float
    min: float
    step: float | None = None
    type: Literal['number']


class PickerStated2(BaseModel):
    candidates: list[str] | None = None
    type: Literal['text']


class PickerStated(RootModel[PickerStated1 | PickerStated2]):
    root: PickerStated1 | PickerStated2 = Field(
        ..., description='The picker kinds that declare their domain.'
    )


class ResetMode(Enum):
    keep = 'keep'
    clear = 'clear'
    default = 'default'


class Sink(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    dest: str | None = None
    path: str | None = Field(
        None,
        description='JSON Pointer into the target value. Only a `scope: local` write uses it: it names the member this node\nowns, and the rest of the object is left alone.',
    )
    scope: Scope = 'remote'


class SizeAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    height: str | None = None
    selector: str | None = None
    width: str | None = None


class Source(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    default: Any | None = None
    path: str | None = Field(
        None,
        description="JSON Pointer into the slot's value (ADR 0008): the shape belongs to the\nproducer, the read picks one field out of it. ADR 0031 is silent on\nextraction — it is orthogonal to the address, so it stays.",
    )
    scope: Scope = 'remote'
    slot: str | None = None


class Stamp(BaseModel):
    data: dict[str, Any]
    name: str
    type: Literal['stamp'] = 'stamp'


class Step1(BaseModel):
    timer: conint(ge=0)


class Step2(BaseModel):
    slot: str


class Step(RootModel[Step1 | Step2]):
    root: Step1 | Step2 = Field(
        ...,
        description='What advances the stage (ADR 0031 §4). Exactly two answers, because there are exactly two ways\nan item gets there: a clock this node owns, or a slot the world writes. Omitted = no stepping.',
    )


class SubmitMode(Enum):
    enter = 'enter'
    button = 'button'
    change = 'change'


class SubmitSet(RootModel[SubmitMode | list[SubmitMode]]):
    root: SubmitMode | list[SubmitMode] = Field(
        ...,
        description='A bare string or a list on the wire: `submit: enter` and `submit: [enter]`\nsay the same thing, so the one-mode case (nearly every frame) does not have\nto remember the list syntax.',
    )


class TextAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    format: str | None = None
    selector: str | None = None


class Theme1(Enum):
    light = 'light'


class Theme(RootModel[Theme1 | Literal['dark']]):
    root: Theme1 | Literal['dark'] = Field(
        ...,
        description='The ground colour the graph sits on. The two palettes differ only in lightness: Morandi colours are low-chroma, so a palette with\nenough contrast on a light ground will smear into a blur on a dark one, and vice versa.',
    )


class Throttle(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    throttle: conint(ge=0)


class Window(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    size: conint(ge=1)


class Wrap1(Enum):
    wrap = 'wrap'
    wrap_reverse = 'wrap-reverse'


class Wrap(RootModel[Wrap1 | Literal['nowrap']]):
    root: Wrap1 | Literal['nowrap'] = Field(
        ...,
        description='What the items do when they no longer fit on one line (ADR 0035). `wrap` is absent: a wall of\ncards is the common shape, and `nowrap` is a strip that must stay one strip.',
    )


class Button(BaseModel):
    attrs: ButtonAttr | None = None
    id: str | None = None
    source: Source | None = None
    type: Literal['button'] = 'button'


class Canvas(BaseModel):
    attrs: SizeAttr | None = None
    id: str | None = None
    options: Any | None = Field(
        None,
        description='The **dynamic bag** of module-private options (ADR 0017): renderer configuration the core\ndoes not know (3d-force-graph\'s node/link sizes, force parameters, colours…) packed up here,\nwhich the host hands to the module\'s `mount(el, data, host, options)` as it is, interpreting not one key.\nThis is where "variants do not enter accrete" lands: swapping renderers only swaps url + options, the DSL is unchanged.\nAbsent/Null = `{}` (the module applies its own defaults); same semantics as `url` — mount-time config,\nnot on the update hot-reload leg (changing it takes a remount).',
    )
    source: Source | None = Field(
        None,
        description='`bind["value"]`: the payload convention is kin to Chart/diagram — `kind: source` points at\na named data slot (the raw JSON of `bind.value.default` on the node in the slot is the module\'s data area),\nstreaming data in = `set`/`patch` on that slot (pointer `/bind/value/default/...`).',
    )
    url: str = Field(
        ...,
        description='The address of the ES module on the CDN (exports the mount/update/resize/unmount contract).',
    )
    type: Literal['canvas'] = 'canvas'


class Emit(RootModel[Debounce | Throttle]):
    root: Debounce | Throttle = Field(
        ...,
        description='How a field\'s change reaches the loom (ADR 0032 §8). The keystroke updates the field\'s own copy at\nonce — what this decides is when the *loom* hears about it, which is what `submit: [change]` turns\ninto frames. Closed, and one arm at a time: debounce and throttle answer different questions (wait\nfor quiet, or keep a cadence), and a frame asking for both is asking for a shape nobody wants.\n\nAbsent means `{debounce: 250}`: typing stays instant (the display is the field\'s own signal), while\na per-keystroke `[change]` submit becomes one frame per pause instead of one frame per letter —\nwithout it a `sends: 1` loom spends its only send on the first character. `{debounce: 0}` is the\nway back to "every keystroke, at once".',
    )


class ForceGraphStyle(BaseModel):
    auto_fit: bool | None = Field(
        True,
        description='After the first batch of data, fit the view to the whole graph; later appends neither re-layout nor fly the camera.',
    )
    background: str | None = None
    charge: float | None = Field(
        -30.0, description='Repulsion; a negative value = pushing each other apart.'
    )
    fit_padding_px: float | None = 40.0
    glow_alpha: float | None = Field(
        0.44999998807907104,
        description='Marker strength for highlighted nodes: peak opacity of the halo core and of each ripple ring.',
    )
    highlight_reach: bool | None = Field(
        True,
        description='Highlight the reachable path (`reach_hops` edges out from the selected/focused node) instead of dimming the rest.',
    )
    label_max_nodes: conint(ge=0) | None = Field(
        150,
        description='Above this node count draw only, no labels (the label layer is DOM projected per frame, so at volume it is noise).',
    )
    label_px: float | None = 12.0
    labels: bool | None = Field(True, description='An always-on name label layer.')
    link_distance: float | None = 30.0
    link_opacity: float | None = 0.800000011920929
    link_shape: LinkShape | None = Field(
        'straight',
        description="Edge direction: `straight` connects directly; `axes` takes the nearest of the six coordinate orientations;\n`tetra` takes the nearest of the regular tetrahedron's four vertex directions.",
        validate_default=True,
    )
    link_strength: float | None = None
    link_width_px: float | None = 2.5
    node_size_px: float | None = Field(
        0.0,
        description='Node base radius (screen pixels).\nNode radius (screen pixels); 0 = derived from `node_size_ratio`.',
    )
    node_size_ratio: float | None = Field(
        2.0,
        description='Multiple of the link width for the node sphere diameter (default 2).',
    )
    node_size_step_px: float | None = Field(
        0.6000000238418579,
        description='Radius added per weight tier (screen pixels); the tier count is `node_tiers`.',
    )
    node_tiers: conint(ge=0, le=255) | None = 3
    palette: list[str] | None = Field(
        [],
        description='Node colours, taken in rotation by `kind`; empty = the built-in Morandi scheme for `theme`.',
    )
    reach_hops: conint(ge=0) | None = Field(
        1, description='The number of reachable hops.'
    )
    theme: Theme | None = Field(
        'dark',
        description='Ground: light / dark. Swaps only palette and panel background, not the layout.',
        validate_default=True,
    )
    velocity_decay: float | None = 0.4000000059604645


class Image(BaseModel):
    attrs: ImageAttr | None = None
    id: str | None = None
    source: Source | None = None
    type: Literal['image'] = 'image'


class Input(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    attrs: ClassAttr | None = None
    emit: Emit | None = Field(
        None,
        description="When this field's typing reaches the loom (ADR 0032 §8). Absent = `{debounce: 250}`, which is\nwhat makes a per-keystroke `submit: [change]` bearable; `{debounce: 0}` is a frame per letter.\nTiming, not addressing: `source`/`tag` say where the value lives, this says when it is heard.",
    )
    id: str | None = None
    kind: InputKind | None = Field(
        None,
        description="What kind of field this is — the element type and the parse, one declaration (ADR 0032 §2: a field\nhas one type, and it is not the read's or the write's). Named `kind` because `type` is the node's own\ndiscriminator on the wire. Absent = text.",
    )
    multiline: bool | None = Field(
        None, description='Multi-line is a layout of the field, not a different node.'
    )
    placeholder: Source | None = Field(
        None,
        description='Second value: the placeholder text (literal or slot) — the channel\n`textarea` used to carry on its own type.',
    )
    source: Source | None = None
    tag: str | None = Field(
        None,
        description="The field's name inside an enclosing loom: the loom packs this tag\nas the key, so the sink's address no longer names the field.",
    )
    type: Literal['input'] = 'input'


class LoomAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    reset: ResetMode | None = Field(
        None, description='What the fields become after a send. Absent = `keep`.'
    )
    selector: str | None = None
    sends: int | None = Field(
        None,
        description="How many sends this loom has: absent or `-1` = unlimited, `0` = locked from the start. Each send\ntakes one; at zero the loom's fields are disabled and it refuses to send (ADR 0032 §5).",
    )
    submit: SubmitSet | None = Field(
        None, description='When to send. Absent = `[enter]`.'
    )


class PanelAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    direction: Direction | None = Field(
        None,
        description='`viewport` only: which edge the body hugs. Absent = `L` — the left edge of the viewport\n(`Direction` is the same enum `popup` positions with).',
    )
    dismiss: bool | None = Field(
        None,
        description='Closes on a click outside the body — the mask for `viewport`, "anywhere else" for the rest.\nA panel without it can only be closed by its trigger (a loom that must not lose its work).',
    )
    place: PanelPlace | None = Field(
        None, description='Where it sits. Absent = `inline`.'
    )
    replace_header: bool | None = Field(
        None,
        description='`inline` only: the first child is the header and toggles the body (the old `fold` shape).',
    )
    selector: str | None = None
    state: PanelState | None = Field(
        None, description='Who decides. Absent = `toggle`.'
    )
    width: str | None = Field(
        None,
        description="`viewport` only: the body's width. Absent = whatever the class says.",
    )
    left: str | None = None
    right: str | None = None
    top: str | None = None
    bottom: str | None = None


class Path(BaseModel):
    attrs: ClassAttr | None = None
    id: str | None = None
    source: Source | None = None
    type: Literal['path'] = 'path'


class PickerKind(RootModel[PickerBare | PickerStated]):
    root: PickerBare | PickerStated = Field(
        ...,
        description='How a picker takes its value (ADR 0050). A picker is several components under one name — a menu,\na slider, a switch — so unlike `InputKind` its kind carries the domain: an interval for the\nslider, a word list for the menu, nothing at all for the switch.\n\nThe wire keeps the asymmetry, because the asymmetry carries information: a kind that declares\nnothing is a bare word, and a kind that declares something is a map with a `type`.\n\n```text\nkind: bool\nkind: text\nkind: {type: number, min: 0, max: 64, step: 1}\nkind: {type: text, candidates: [solid, dashed]}\n```',
    )


class Text(BaseModel):
    attrs: TextAttr | None = None
    id: str | None = None
    source: Source | None = None
    type: Literal['text'] = 'text'


class TilesAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    dir: Dir | None = Field(
        None,
        description="Which way the ITEMS flow (ADR 0035), in flex's sense. `row` is a strip: items left to right,\nand each entry's fields run down it, in the grid's ROW axis. `col` (default) is a list: items\ntop to bottom, each entry's fields across it, in the grid's COLUMN axis — the table every\nframe already draws. `row-reverse` / `col-reverse` keep the shape and reverse the order the\nitems arrive in.",
    )
    fields: list[FieldModel] | None = Field(
        None,
        description='Absent = each item is a node drawn as it is, one block per item. Present = each item is an\nENTRY and each field projects one of its children into a cell (ADR 0031 §4).',
    )
    header: Header | None = Field(
        None,
        description='Absent = no header row. The cells carry `selector`, so the frame styles its own header.',
    )
    selector: str | None = None
    step: Step | None = Field(
        None,
        description='What advances the window. Only meaningful with a `window`: a stepper with nothing to step is\na frame error at load, not a clock that ticks for nobody.',
    )
    window: Window | None = Field(
        None,
        description='Absent = every item is laid out and nothing steers; present = that many consecutive items\nare on stage at once, starting at the cursor (ADR 0031 §4).',
    )
    wrap: Wrap | None = Field(
        None,
        description='What happens when the items no longer fit on one line (ADR 0035). Default `wrap`, because\na card wall is the shape that has no other spelling. `wrap-reverse` also puts the FIELDS on\nthe other side of the item axis: the header row below the entries, or the header column on\nthe right — the fields axis is the line axis, so reversing the lines reverses where they land.',
    )


class Color(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    attrs: ColorAttr | None = None
    emit: Emit | None = Field(
        None,
        description="The field's own clock (ADR 0032 §8). A drag is continuous, so one window is one frame rather than one\nframe per pointer event; absent = `{debounce: 250}`, the same as a text field.",
    )
    id: str | None = None
    source: Source | None = Field(
        None, description='The current value, in the triple spelling above.'
    )
    tag: str | None = Field(
        None,
        description="The field's name inside an enclosing loom (same rule as `input`).",
    )
    type: Literal['color'] = 'color'


class ForceGraph(BaseModel):
    attrs: SizeAttr | None = None
    id: str | None = None
    source: Source | None = None
    style: ForceGraphStyle | None = Field(
        None,
        description='Renderer knobs, all with defaults; when default they stay off the wire.',
    )
    theme: Source | None = Field(
        None, description='Second value: the theme channel (`true`/`"dark"`).'
    )
    type: Literal['forcegraph'] = 'forcegraph'


class Entry(BaseModel):
    attrs: ClassAttr | None = None
    children: list[Accrete] | None = Field(
        None,
        description="The fields. A child's `attrs.selector` is the field's name, so a field projects by that\nkey rather than by position — reordering fields cannot move a value to another field.",
    )
    id: str | None = Field(
        None,
        description='The item\'s key (ADR 0031 §4, "Every item has a key"): an entry that names itself keeps that\nname across removals and re-sorts; one that does not is addressed by where it arrived.',
    )
    type: Literal['entry'] = 'entry'


class Frame(BaseModel):
    attrs: FrameAttr | None = None
    children: list[Accrete] | None = None
    id: str | None = None
    sink: Sink | None = Field(
        None,
        description='The landing uplink (ADR 0034): where a drop on this box goes — an event name or\na local slot, the same channel `dock` had.',
    )
    source: Source | None = None
    type: Literal['frame'] = 'frame'


class Loom(BaseModel):
    attrs: LoomAttr | None = None
    children: list[Accrete] | None = None
    id: str | None = None
    sink: Sink | None = None
    tag: str | None = Field(
        None,
        description="The key this loom contributes to its parent's packed object — the same `tag` rule a field follows,\nbecause a nested loom is an input of the enclosing one. Only read when the loom sits inside another\nloom; with no `tag` it packs nothing into its parent (`id` is identity, `dest` is where it sends, and\nneither is a name — ADR 0032 §4).",
    )
    type: Literal['loom'] = 'loom'


class Panel(BaseModel):
    attrs: PanelAttr | None = None
    children: list[Accrete] | None = None
    id: str | None = None
    source: Source | None = None
    type: Literal['panel'] = 'panel'


class Picker(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    attrs: PickerAttr | None = None
    children: list[Accrete] | None = None
    id: str | None = None
    kind: PickerKind | None = Field(
        None,
        description='Which component this picker is (ADR 0050): a menu of rows (absent), a slider that states its\ninterval, or a switch. The kind carries what the component itself needs; the options slot\ncarries the rows a menu shows.',
    )
    options: Source | None = Field(
        None, description='Second value: the option rows (list plane).'
    )
    source: Source | None = None
    tag: str | None = Field(
        None,
        description="The field's name inside an enclosing loom (same rule as `input`).",
    )
    type: Literal['picker'] = 'picker'


class Svg(BaseModel):
    attrs: SizeAttr | None = None
    children: list[Accrete] | None = None
    id: str | None = None
    source: Source | None = None
    type: Literal['svg'] = 'svg'


class Tiles(BaseModel):
    attrs: TilesAttr | None = None
    children: list[Accrete] | None = None
    id: str | None = None
    source: Source | None = None
    type: Literal['tiles'] = 'tiles'


# The root union, discriminated on `type`: each arm is one of the classes above, so a node
# validates into its own class (no wrapper to unwrap) and an unknown `type` is refused.
Accrete = Annotated[Union[Frame | Canvas | ForceGraph | Panel | Loom | Svg | Path | Tiles | Entry | Button | Image | Input | Picker | Color | Text | Stamp], Field(discriminator='type')]


# Forward references (`children: list[Accrete]`) resolve here, now that the aliases exist.
Accept.model_rebuild()
ButtonAttr.model_rebuild()
ClassAttr.model_rebuild()
ColorAttr.model_rebuild()
Debounce.model_rebuild()
Draggable.model_rebuild()
FieldModel.model_rebuild()
FrameAttr.model_rebuild()
Header.model_rebuild()
ImageAttr.model_rebuild()
PickerAttr.model_rebuild()
PickerStated1.model_rebuild()
PickerStated2.model_rebuild()
Sink.model_rebuild()
SizeAttr.model_rebuild()
Source.model_rebuild()
Stamp.model_rebuild()
Step1.model_rebuild()
Step2.model_rebuild()
TextAttr.model_rebuild()
Throttle.model_rebuild()
Window.model_rebuild()
Button.model_rebuild()
Canvas.model_rebuild()
ForceGraphStyle.model_rebuild()
Image.model_rebuild()
Input.model_rebuild()
LoomAttr.model_rebuild()
PanelAttr.model_rebuild()
Path.model_rebuild()
Text.model_rebuild()
TilesAttr.model_rebuild()
Color.model_rebuild()
ForceGraph.model_rebuild()
Entry.model_rebuild()
Frame.model_rebuild()
Loom.model_rebuild()
Panel.model_rebuild()
Picker.model_rebuild()
Svg.model_rebuild()
Tiles.model_rebuild()
