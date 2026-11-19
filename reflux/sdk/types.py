from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, RootModel, conint


# ADR 0031 §1: where a value is authoritative is a closed enumeration, not a namespace.
Scope = Literal['remote', 'local', 'both']

__all__ = ["ButtonAttr", "ClassAttr", "Direction", "DockExpand", "FrameAttr", "ImageAttr", "JsType", "LinkShape1", "LinkShape", "PagesDisplay", "PanelPlace", "PanelState", "RackDirection", "RackEnter", "RackLayout", "RackPause", "RackPlay1", "RackPlay", "RackScroll", "RackView", "SizeAttr", "StyleAttr", "SubmitMode", "SubmitSet", "Template", "TextAttr", "Theme1", "Theme", "Bind", "BundleAttr", "Button", "Canvas", "DockAttr", "ForceGraphStyle", "Image", "Input", "Pages", "PanelAttr", "Path", "RackAttr", "Text", "ForceGraph", "Bundle", "Dock", "Frame", "Grab", "Group", "Panel", "Rack", "Select", "Svg", "Table", "Tbody", "Td", "Th", "Thead", "Tr", "Accrete", "Scope"]



class ButtonAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    oneshot: bool | None = False
    selector: str | None = None


class ClassAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    horizontal: bool | None = Field(
        None,
        description='容器自身的排布方向（同 FrameAttr 字段；ADR 0010 缺陷修复：\n此前只有 Case 认识 horizontal，select/rack 的 col 类无法被\n自己的 attrs 推翻——父 case 的 horizontal 只管父 div）。',
    )
    selector: str | None = None


class Direction(Enum):
    U = 'U'
    D = 'D'
    L = 'L'
    R = 'R'


class DockExpand(Enum):
    reveal = 'reveal'
    reserved = 'reserved'


class FrameAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    grid: dict[str, Any] | None = None
    horizontal: bool | None = None
    selector: str | None = None


class ImageAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    desc: str | None = None
    height: str | None = None
    selector: str | None = None
    thumb: bool | None = False
    width: str | None = None


class JsType(Enum):
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
        description='图渲染器的旋钮。语义与 canvas 的 `options` 同级：挂载期配置，改它要\n重新挂载（不进 update 腿）。区别只在于这是自家渲染器的词表，所以可以\n类型化、可以被 schema 和 patch 校验。\n边的走向。两种朝向都是"节点上的接口"：连线从一个朝向离开，再从另一端的\n朝向进入，中间用三次曲线接起来。',
    )


class PagesDisplay(Enum):
    render = 'render'
    dom = 'dom'


class PanelPlace(Enum):
    inline = 'inline'
    anchor = 'anchor'
    viewport = 'viewport'


class PanelState(Enum):
    toggle = 'toggle'
    bound = 'bound'


class RackDirection(Enum):
    vertical = 'vertical'
    horizontal = 'horizontal'


class RackEnter(Enum):
    none = 'none'
    fade = 'fade'
    translate = 'translate'


class RackLayout(Enum):
    adaptive = 'adaptive'
    fixed = 'fixed'
    exclusive = 'exclusive'


class RackPause(Enum):
    off = 'off'
    click = 'click'
    hover = 'hover'


class RackPlay1(Enum):
    newest = 'newest'
    rotate = 'rotate'


class RackPlay(RootModel[RackPlay1 | Literal['dwell']]):
    root: RackPlay1 | Literal['dwell'] = Field(
        ...,
        description="Who decides which row is current: the newest one (as before), or a rotation of the renderer's.",
    )


class RackScroll(Enum):
    none = 'none'
    bar = 'bar'
    indicator = 'indicator'
    arrow = 'arrow'


class RackView(BaseModel):
    count: conint(ge=0) | None = Field(
        None, description='`fixed` 露出几行；其余布局不看这个数。'
    )
    direction: RackDirection | None = RackDirection('vertical')
    enter: RackEnter | None = RackEnter('none')
    enter_ms: conint(ge=0) | None = Field(
        None,
        description="How long `enter` and `leave` take, in ms. Absent = 350, the number the CSS was written\nwith; the renderer only ever writes them through the container's custom properties, so how\na row moves is still CSS's business (ADR 0024).",
    )
    every: conint(ge=0) | None = Field(
        None,
        description='一行在台上待多久（毫秒）：`rotate` 的一步（然后轮到下一行），`dwell` 的全部（到点就下台）。\n缺席 = 4000，渲染器另有下限 200。',
    )
    layout: RackLayout | None = RackLayout('adaptive')
    leave_ms: conint(ge=0) | None = None
    pause: RackPause | None = RackPause('off')
    play: RackPlay | None = Field('newest', validate_default=True)
    scroll: RackScroll | None = RackScroll('none')


class SizeAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    height: str | None = None
    selector: str | None = None
    width: str | None = None


class StyleAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    selector: str | None = None
    style: dict[str, Any] | None = None


class SubmitMode(Enum):
    enter = 'enter'
    button = 'button'
    change = 'change'


class SubmitSet(RootModel[SubmitMode | list[SubmitMode]]):
    root: SubmitMode | list[SubmitMode] = Field(
        ...,
        description='A bare string or a list on the wire: `submit: enter` and `submit: [enter]`\nsay the same thing, so the one-mode case (nearly every frame) does not have\nto remember the list syntax.',
    )


class Template(BaseModel):
    data: dict[str, Any]
    name: str
    type: Literal['template'] = 'template'


class TextAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    format: str | None = None
    selector: str | None = None


class Theme1(Enum):
    light = 'light'


class Theme(RootModel[Theme1 | Literal['dark']]):
    root: Theme1 | Literal['dark'] = Field(
        ...,
        description='图所在的底色。两套配色只差明度：莫兰迪色低彩度，同一套色在浅底上够\n对比就会在深底上糊成一团，反之亦然。',
    )


class Bind(BaseModel):
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
    type: JsType | None = None


class BundleAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    selector: str | None = None
    submit: SubmitSet | None = Field(
        None, description='When to send. Absent = `[enter]`.'
    )


class Button(BaseModel):
    attrs: ButtonAttr | None = None
    id: str | None = None
    sink: Bind | None = None
    source: Bind | None = None
    type: Literal['button'] = 'button'


class Canvas(BaseModel):
    attrs: SizeAttr | None = None
    id: str | None = None
    options: Any | None = Field(
        None,
        description='模块私有选项的**动态袋**（ADR 0017）：核心不认识的渲染器配置\n（3d-force-graph 的节点/边尺寸、力参数、配色……）打包放这里，\n宿主原样交给模块的 `mount(el, data, host, options)`，一个键都不解释。\n这是"变体不进 accrete"的落点：换渲染器只换 url + options，DSL 不变。\n缺省/Null = `{}`（模块自己套默认值）；与 `url` 同一语义——挂载期配置，\n不进 update 热更新腿（改它要靠重新挂载）。',
    )
    source: Bind | None = Field(
        None,
        description='`bind["value"]`：载荷惯例与 Chart/diagram 同族——`kind: source` 指向\n具名数据槽（槽内节点的 `bind.value.default` 原始 JSON 即模块 data 区），\n流式喂数据 = 对该槽 `set`/`patch`（指针 `/bind/value/default/...`）。',
    )
    url: str = Field(
        ...,
        description='CDN 上的 ES module 地址（导出 mount/update/resize/unmount 契约）。',
    )
    type: Literal['canvas'] = 'canvas'


class DockAttr(BaseModel):
    accept: list[str] | None = Field(
        None,
        description='收哪些 `grab.kind`。缺席 = 全收（只有一个落点时不必写）；写了就是闭集合\n比对，配不上的拖拽落在这里等于没落（不发射、不高亮）。',
    )
    class_: list[str] | None = Field(None, alias='class')
    expand: DockExpand | None = None
    selector: str | None = None


class ForceGraphStyle(BaseModel):
    auto_fit: bool | None = Field(
        True, description='首批数据后自动取景到整张图；之后的追加不重排、不飞相机。'
    )
    background: str | None = None
    charge: float | None = Field(-30.0, description='斥力，负值 = 相互推开。')
    fit_padding_px: float | None = 40.0
    glow_alpha: float | None = Field(
        0.44999998807907104,
        description='高亮节点的标记强度：光晕核心与每一圈波纹的峰值不透明度。',
    )
    highlight_reach: bool | None = Field(
        True,
        description='高亮可达路径（从选中/聚焦节点向外 `reach_hops` 条边），而不是压暗其它部分。',
    )
    label_max_nodes: conint(ge=0) | None = Field(
        150,
        description='超过这个节点数只画不标（标签层是逐帧投影的 DOM，量大就成噪声）。',
    )
    label_px: float | None = 12.0
    labels: bool | None = Field(True, description='常显名字标签层。')
    link_distance: float | None = 30.0
    link_opacity: float | None = 0.800000011920929
    link_shape: LinkShape | None = Field(
        'straight',
        description='边的走向：`straight` 直连；`axes` 从六个坐标朝向里取最近的一个；\n`tetra` 从正四面体的四个顶点方向里取最近的。',
        validate_default=True,
    )
    link_strength: float | None = None
    link_width_px: float | None = 2.5
    node_size_px: float | None = Field(
        0.0,
        description='节点基础半径（屏幕像素）。\n节点半径（屏幕像素）；0 = 由 `node_size_ratio` 推导。',
    )
    node_size_ratio: float | None = Field(
        2.0, description='节点球直径相对边宽的倍数（默认 2）。'
    )
    node_size_step_px: float | None = Field(
        0.6000000238418579,
        description='每档权重增加的半径（屏幕像素）；档数见 `node_tiers`。',
    )
    node_tiers: conint(ge=0, le=255) | None = 3
    palette: list[str] | None = Field(
        [],
        description='节点配色，按 `kind` 轮取；空 = 用 `theme` 对应的内置莫兰迪方案。',
    )
    reach_hops: conint(ge=0) | None = Field(1, description='可达的跳数。')
    theme: Theme | None = Field(
        'dark',
        description='底色：浅底 / 深底。只换配色与面板背景，不改布局。',
        validate_default=True,
    )
    velocity_decay: float | None = 0.4000000059604645


class Image(BaseModel):
    attrs: ImageAttr | None = None
    id: str | None = None
    source: Bind | None = None
    type: Literal['image'] = 'image'


class Input(BaseModel):
    attrs: ClassAttr | None = None
    id: str | None = None
    multiline: bool | None = Field(
        None, description='Multi-line is a layout of the field, not a different node.'
    )
    placeholder: Bind | None = Field(
        None,
        description='Second value: the placeholder text (literal or slot) — the channel\n`textarea` used to carry on its own type.',
    )
    sink: Bind | None = None
    source: Bind | None = None
    tag: str | None = Field(
        None,
        description="The field's name inside an enclosing bundle: the bundle packs this tag\nas the key, so the sink's address no longer names the field.",
    )
    type: Literal['input'] = 'input'


class Pages(BaseModel):
    attrs: ClassAttr | None = None
    display: PagesDisplay | None = PagesDisplay('render')
    id: str | None = None
    select: Bind | None = Field(
        None, description='Second value (ADR 0031 §2 named field): the selected key.'
    )
    source: Bind | None = None
    type: Literal['pages'] = 'pages'


class PanelAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    direction: Direction | None = Field(
        None,
        description='`viewport` only: which edge the body hugs. Absent = `L` — the left edge of the viewport\n(`Direction` is the same enum `popup` positions with).',
    )
    dismiss: bool | None = Field(
        None,
        description='Closes on a click outside the body — the mask for `viewport`, "anywhere else" for the rest.\nA panel without it can only be closed by its trigger (a bundle that must not lose its work).',
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
    source: Bind | None = None
    type: Literal['path'] = 'path'


class RackAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    horizontal: bool | None = Field(
        None,
        description="The container's own direction. `view.direction` is what a frame should say; this field is\nwhere the renderer lands it (`use_common_css` already reads it — the same field `ClassAttr`\ngrew for the same reason).",
    )
    scroll: bool | None = Field(
        False,
        description='The old boolean scroll switch: `true` means `view.scroll = "bar"`. It stays because frames\nalready say it, and what it meant now has a finer name.',
    )
    selector: str | None = None
    view: RackView | None = Field(
        None,
        description='How the same rows are laid down (ADR 0024). Omitted = exactly what a rack has always done.',
    )


class Text(BaseModel):
    attrs: TextAttr | None = None
    id: str | None = None
    source: Bind | None = None
    type: Literal['text'] = 'text'


class ForceGraph(BaseModel):
    attrs: SizeAttr | None = None
    id: str | None = None
    source: Bind | None = None
    style: ForceGraphStyle | None = Field(
        None, description='渲染器旋钮，全部有缺省值；缺省时不进 wire。'
    )
    theme: Bind | None = Field(
        None, description='Second value: the theme channel (`true`/`"dark"`).'
    )
    type: Literal['forcegraph'] = 'forcegraph'


class Bundle(BaseModel):
    attrs: BundleAttr | None = None
    children: list[Accrete] | None = None
    id: str | None = None
    sink: Bind | None = None
    tag: str | None = Field(
        None,
        description="The key this bundle contributes to its parent's packed object. Only read\nwhen the bundle sits inside another bundle; falls back to `id`.",
    )
    type: Literal['bundle'] = 'bundle'


class Dock(BaseModel):
    attrs: DockAttr | None = None
    children: list[Accrete] | None = None
    id: str | None = None
    sink: Bind | None = Field(
        None,
        description='`bind["value"]`：`event` 上行（事件名就是这里的名字），或 `local` 写槽\n（包装与上行同形，ADR 0010）。带什么货由源（`grab`）给，落点不再附加任何\n元数据——事件名与帧的 `id` 已经唯一确定是哪个落点。',
    )
    type: Literal['dock'] = 'dock'


class Frame(BaseModel):
    attrs: FrameAttr | None = None
    children: list[Accrete] | None = None
    id: str | None = None
    source: Bind | None = None
    type: Literal['frame'] = 'frame'


class Grab(BaseModel):
    children: list[Accrete] | None = None
    id: str | None = Field(
        None,
        description='行身份（可选但强烈建议）：`rack` 的 keyed diff 用**行节点自己**的 id，\n没有就退 `#{idx}` 位置键——中间删一行会让后面所有行重建、本地态丢。\ngrab 就是「一层无样式包装」，可以当行的根节点，所以 id 落在这里。\n渲染器不替它从子节点借 id：那会造出两个同 id 的节点，按 id 定位的行\n操作（append／remove／patch）从此指向不明——身份只能生产者给。',
    )
    kind: str | None = Field(
        None,
        description='货物的标签，供落点配对（`dock.attrs.accept`）。缺省 = 没有标签：\n不限定的落点照收，写了 `accept` 的落点不收（配不上就是配不上）。',
    )
    payload: Any | None = Field(
        None,
        description='货物本身：任意 JSON，原样进上行帧的 `payload`。写的是声明时的快照，\n渲染器不校验它与任何槽是否一致——一致性是生产者的编排责任。',
    )
    type: Literal['grab'] = 'grab'


class Group(BaseModel):
    attrs: StyleAttr | None = None
    children: list[Accrete] | None = None
    id: str | None = None
    source: Bind | None = None
    type: Literal['group'] = 'group'


class Panel(BaseModel):
    attrs: PanelAttr | None = None
    children: list[Accrete] | None = None
    id: str | None = None
    source: Bind | None = None
    type: Literal['panel'] = 'panel'


class Rack(BaseModel):
    attrs: RackAttr | None = None
    children: list[Accrete] | None = None
    id: str | None = None
    item: list[Accrete] | None = None
    source: Bind | None = None
    type: Literal['rack'] = 'rack'


class Select(BaseModel):
    attrs: ClassAttr | None = None
    children: list[Accrete] | None = None
    id: str | None = None
    options: Bind | None = Field(
        None, description='Second value: the option rows (list plane).'
    )
    sink: Bind | None = None
    source: Bind | None = None
    tag: str | None = Field(
        None,
        description="The field's name inside an enclosing bundle (same rule as `input`).",
    )
    type: Literal['select'] = 'select'


class Svg(BaseModel):
    attrs: SizeAttr | None = None
    children: list[Accrete] | None = None
    id: str | None = None
    source: Bind | None = None
    type: Literal['svg'] = 'svg'


class Table(BaseModel):
    children: list[Accrete] | None = None
    id: str | None = None
    type: Literal['table'] = 'table'


class Tbody(BaseModel):
    children: list[Accrete] | None = None
    id: str | None = None
    type: Literal['tbody'] = 'tbody'


class Td(BaseModel):
    children: list[Accrete] | None = None
    id: str | None = None
    type: Literal['td'] = 'td'


class Th(BaseModel):
    children: list[Accrete] | None = None
    id: str | None = None
    type: Literal['th'] = 'th'


class Thead(BaseModel):
    children: list[Accrete] | None = None
    id: str | None = None
    type: Literal['thead'] = 'thead'


class Tr(BaseModel):
    children: list[Accrete] | None = None
    id: str | None = None
    type: Literal['tr'] = 'tr'


# The root union, discriminated on `type`: each arm is one of the classes above, so a node
# validates into its own class (no wrapper to unwrap) and an unknown `type` is refused.
Accrete = Annotated[Union[Frame | Canvas | ForceGraph | Panel | Bundle | Svg | Group | Path | Rack | Pages | Button | Image | Input | Select | Table | Thead | Tbody | Tr | Th | Td | Text | Template | Grab | Dock], Field(discriminator='type')]


# Forward references (`children: list[Accrete]`) resolve here, now that the aliases exist.
ButtonAttr.model_rebuild()
ClassAttr.model_rebuild()
FrameAttr.model_rebuild()
ImageAttr.model_rebuild()
RackView.model_rebuild()
SizeAttr.model_rebuild()
StyleAttr.model_rebuild()
Template.model_rebuild()
TextAttr.model_rebuild()
Bind.model_rebuild()
BundleAttr.model_rebuild()
Button.model_rebuild()
Canvas.model_rebuild()
DockAttr.model_rebuild()
ForceGraphStyle.model_rebuild()
Image.model_rebuild()
Input.model_rebuild()
Pages.model_rebuild()
PanelAttr.model_rebuild()
Path.model_rebuild()
RackAttr.model_rebuild()
Text.model_rebuild()
ForceGraph.model_rebuild()
Bundle.model_rebuild()
Dock.model_rebuild()
Frame.model_rebuild()
Grab.model_rebuild()
Group.model_rebuild()
Panel.model_rebuild()
Rack.model_rebuild()
Select.model_rebuild()
Svg.model_rebuild()
Table.model_rebuild()
Tbody.model_rebuild()
Td.model_rebuild()
Th.model_rebuild()
Thead.model_rebuild()
Tr.model_rebuild()
