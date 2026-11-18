from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, RootModel, conint


__all__ = ["ButtonAttr", "ClassAttr", "Direction", "DirectionAttr", "DockExpand", "FoldAttr", "FormAttr", "FrameAttr", "ImageAttr", "Input", "JsType", "LayerAttr", "LinkShape1", "LinkShape", "PagesDisplay", "Path", "PortalAttr", "PositionAttr", "RackDirection", "RackEnter", "RackLayout", "RackPause", "RackPlay", "RackScroll", "RackView", "SizeAttr", "StyleAttr", "Template", "TextArea", "TextAttr", "Theme1", "Theme", "Bind1", "Bind2", "Bind3", "Bind4", "Bind5", "Bind6", "Button", "Canvas", "DockAttr", "ForceGraphStyle", "Image", "Pages", "RackAttr", "Text", "ForceGraph", "Dock", "Float", "Fold", "Form", "Frame", "Grab", "Group", "Layer", "Popup", "Portal", "Rack", "Select", "Svg", "Table", "Tbody", "Td", "Th", "Thead", "Tr", "Accrete", "Bind"]



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


class DirectionAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    direction: Direction | None = None
    selector: str | None = None


class DockExpand(Enum):
    reveal = 'reveal'
    reserved = 'reserved'


class FoldAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    float_body: bool | None = None
    replace_header: bool | None = None
    selector: str | None = None


class FormAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    instant: bool | None = None
    selector: str | None = None


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


class Input(BaseModel):
    attrs: ClassAttr | None = None
    bind: dict[str, Bind] | None = None
    id: str | None = None
    type: Literal['input'] = 'input'


class JsType(Enum):
    bool = 'bool'
    number = 'number'
    text = 'text'
    password = 'password'
    button = 'button'
    submit = 'submit'


class LayerAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    dismiss: bool | None = Field(
        None,
        description='dismiss（ADR 0014）：点层自身（模糊区，而非模态内容）清空所绑槽。\n本页瞬时状态：只写 local/data 平面，不上线协议。',
    )
    selector: str | None = None


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


class Path(BaseModel):
    attrs: ClassAttr | None = None
    bind: dict[str, Bind] | None = None
    id: str | None = None
    type: Literal['path'] = 'path'


class PortalAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    selector: str | None = None
    to: str = Field(
        ...,
        description='目标挂载点：CSS 选择器，选中应用显式声明的 layer 宿主（ADR 0014：挂载点由\n应用声明，渲染器不加固定逻辑；解析不到就不渲染 + warn）。',
    )


class PositionAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    selector: str | None = None
    left: str | None = None
    right: str | None = None
    top: str | None = None
    bottom: str | None = None


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


class RackPlay(Enum):
    newest = 'newest'
    rotate = 'rotate'


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
        None, description='`rotate` 每一步停留多久（毫秒）。'
    )
    layout: RackLayout | None = RackLayout('adaptive')
    leave_ms: conint(ge=0) | None = None
    pause: RackPause | None = RackPause('off')
    play: RackPlay | None = RackPlay('newest')
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


class Template(BaseModel):
    data: dict[str, Any]
    name: str
    type: Literal['template'] = 'template'


class TextArea(BaseModel):
    attrs: ClassAttr | None = None
    bind: dict[str, Bind] | None = None
    id: str | None = None
    type: Literal['textarea'] = 'textarea'


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


class Bind1(BaseModel):
    default: Any | None = None
    type: JsType | None = None
    kind: Literal['source']
    path: str | None = Field(
        None,
        description='可选 JSON Pointer（ADR 0008）：进槽内节点的 WIRE SHAPE 提取\n子值（与 ADR 0005 patch 路径同一词法）；省略 = 取槽节点自己的\n`bind[<key>].default`（同 key 直传惯例）。',
    )
    source: str


class Bind2(BaseModel):
    default: Any | None = None
    type: JsType | None = None
    kind: Literal['local']
    name: str | None = Field(
        None,
        description='包装里的那个名字，缺省 = 槽名。另起的名字才写它——落点本身是 `slot`。',
    )
    path: str | None = None
    report: str | None = Field(
        None,
        description='本地切换之外的第二个去向：这是**点击**，venue 也需要知道（ADR 0028）。\n一次导航点击既是"页面里的选中值变了"，也是"这个人走到了某个岛"——前者是本地\n值槽，后者只有 venue 能记住（跨设备续上）。写本地槽之后再照发一份，事件名由\n帧给（框架不认识"岛"这个词），载荷是这次的值本身。',
    )
    slot: str


class Bind3(BaseModel):
    default: Any | None = None
    type: JsType | None = None
    dest: str
    kind: Literal['dest']


class Bind4(BaseModel):
    default: Any | None = None
    type: JsType | None = None
    field: str
    kind: Literal['field']
    payload: Any | None = None


class Bind5(BaseModel):
    default: Any | None = None
    type: JsType | None = None
    kind: Literal['submit']


class Bind6(BaseModel):
    default: Any | None = None
    type: JsType | None = None
    kind: Literal['default']


class Button(BaseModel):
    attrs: ButtonAttr | None = None
    bind: dict[str, Bind] | None = None
    id: str | None = None
    type: Literal['button'] = 'button'


class Canvas(BaseModel):
    attrs: SizeAttr | None = None
    bind: dict[str, Any] | None = Field(
        None,
        description='`bind["value"]`：载荷惯例与 Chart/diagram 同族——`kind: source` 指向\n具名数据槽（槽内节点的 `bind.value.default` 原始 JSON 即模块 data 区），\n流式喂数据 = 对该槽 `set`/`patch`（指针 `/bind/value/default/...`）。',
    )
    id: str | None = None
    options: Any | None = Field(
        None,
        description='模块私有选项的**动态袋**（ADR 0017）：核心不认识的渲染器配置\n（3d-force-graph 的节点/边尺寸、力参数、配色……）打包放这里，\n宿主原样交给模块的 `mount(el, data, host, options)`，一个键都不解释。\n这是"变体不进 accrete"的落点：换渲染器只换 url + options，DSL 不变。\n缺省/Null = `{}`（模块自己套默认值）；与 `url` 同一语义——挂载期配置，\n不进 update 热更新腿（改它要靠重新挂载）。',
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
    bind: dict[str, Bind] | None = None
    id: str | None = None
    type: Literal['image'] = 'image'


class Pages(BaseModel):
    attrs: ClassAttr | None = None
    bind: dict[str, Bind] | None = None
    display: PagesDisplay | None = PagesDisplay('render')
    id: str | None = None
    type: Literal['pages'] = 'pages'


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
    bind: dict[str, Bind] | None = None
    id: str | None = None
    type: Literal['text'] = 'text'


class ForceGraph(BaseModel):
    attrs: SizeAttr | None = None
    bind: dict[str, Bind] | None = None
    id: str | None = None
    style: ForceGraphStyle | None = Field(
        None, description='渲染器旋钮，全部有缺省值；缺省时不进 wire。'
    )
    type: Literal['forcegraph'] = 'forcegraph'


class Dock(BaseModel):
    attrs: DockAttr | None = None
    bind: dict[str, Any] | None = Field(
        None,
        description='`bind["value"]`：`event` 上行（事件名就是这里的名字），或 `local` 写槽\n（包装与上行同形，ADR 0010）。带什么货由源（`grab`）给，落点不再附加任何\n元数据——事件名与帧的 `id` 已经唯一确定是哪个落点。',
    )
    children: list[Accrete] | None = None
    id: str | None = None
    type: Literal['dock'] = 'dock'


class Float(BaseModel):
    attrs: PositionAttr | None = None
    bind: dict[str, Bind] | None = None
    children: list[Accrete] | None = None
    id: str | None = None
    type: Literal['float'] = 'float'


class Fold(BaseModel):
    attrs: FoldAttr | None = None
    bind: dict[str, Bind] | None = None
    children: list[Accrete] | None = None
    id: str | None = None
    item: list[Accrete] | None = None
    type: Literal['fold'] = 'fold'


class Form(BaseModel):
    attrs: FormAttr | None = None
    bind: dict[str, Bind] | None = None
    children: list[Accrete] | None = None
    id: str | None = None
    type: Literal['form'] = 'form'


class Frame(BaseModel):
    attrs: FrameAttr | None = None
    bind: dict[str, Bind] | None = None
    children: list[Accrete] | None = None
    id: str | None = None
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
    bind: dict[str, Bind] | None = None
    children: list[Accrete] | None = None
    id: str | None = None
    type: Literal['group'] = 'group'


class Layer(BaseModel):
    attrs: LayerAttr | None = None
    bind: dict[str, Bind] | None = None
    children: list[Accrete] | None = None
    id: str | None = None
    type: Literal['layer'] = 'layer'


class Popup(BaseModel):
    attrs: DirectionAttr | None = None
    bind: dict[str, Bind] | None = None
    children: list[Accrete] | None = None
    id: str | None = None
    type: Literal['popup'] = 'popup'


class Portal(BaseModel):
    attrs: PortalAttr | None = None
    children: list[Accrete] | None = None
    type: Literal['portal'] = 'portal'


class Rack(BaseModel):
    attrs: RackAttr | None = None
    bind: dict[str, Bind] | None = None
    children: list[Accrete] | None = None
    id: str | None = None
    item: list[Accrete] | None = None
    type: Literal['rack'] = 'rack'


class Select(BaseModel):
    attrs: ClassAttr | None = None
    bind: dict[str, Bind] | None = None
    children: list[Accrete] | None = None
    id: str | None = None
    type: Literal['select'] = 'select'


class Svg(BaseModel):
    attrs: SizeAttr | None = None
    bind: dict[str, Bind] | None = None
    children: list[Accrete] | None = None
    id: str | None = None
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
Accrete = Annotated[Union[Frame | Canvas | ForceGraph | Float | Layer | Portal | Fold | Form | Popup | Svg | Group | Path | Rack | Pages | Button | Image | Input | Select | Table | Thead | Tbody | Tr | Th | Td | Text | TextArea | Template | Grab | Dock], Field(discriminator='type')]

# `bind` is a map of these, discriminated on `kind`.
Bind = Annotated[Union[Bind1 | Bind2 | Bind3 | Bind4 | Bind5 | Bind6], Field(discriminator='kind')]


# Forward references (`children: list[Accrete]`) resolve here, now that the aliases exist.
ButtonAttr.model_rebuild()
ClassAttr.model_rebuild()
DirectionAttr.model_rebuild()
FoldAttr.model_rebuild()
FormAttr.model_rebuild()
FrameAttr.model_rebuild()
ImageAttr.model_rebuild()
Input.model_rebuild()
LayerAttr.model_rebuild()
Path.model_rebuild()
PortalAttr.model_rebuild()
PositionAttr.model_rebuild()
RackView.model_rebuild()
SizeAttr.model_rebuild()
StyleAttr.model_rebuild()
Template.model_rebuild()
TextArea.model_rebuild()
TextAttr.model_rebuild()
Bind1.model_rebuild()
Bind2.model_rebuild()
Bind3.model_rebuild()
Bind4.model_rebuild()
Bind5.model_rebuild()
Bind6.model_rebuild()
Button.model_rebuild()
Canvas.model_rebuild()
DockAttr.model_rebuild()
ForceGraphStyle.model_rebuild()
Image.model_rebuild()
Pages.model_rebuild()
RackAttr.model_rebuild()
Text.model_rebuild()
ForceGraph.model_rebuild()
Dock.model_rebuild()
Float.model_rebuild()
Fold.model_rebuild()
Form.model_rebuild()
Frame.model_rebuild()
Grab.model_rebuild()
Group.model_rebuild()
Layer.model_rebuild()
Popup.model_rebuild()
Portal.model_rebuild()
Rack.model_rebuild()
Select.model_rebuild()
Svg.model_rebuild()
Table.model_rebuild()
Tbody.model_rebuild()
Td.model_rebuild()
Th.model_rebuild()
Thead.model_rebuild()
Tr.model_rebuild()
