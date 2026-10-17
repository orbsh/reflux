from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field


__all__ = ["ButtonAttr", "CaseAttr", "ClassAttr", "Diagram", "Direction", "DirectionAttr", "FoldAttr", "FormAttr", "ImageAttr", "Input", "JsType", "LayerAttr", "PagesDisplay", "Path", "PortalAttr", "PositionAttr", "RackAttr", "SizeAttr", "StyleAttr", "Template", "TextArea", "TextAttr", "Bind1", "Bind2", "Bind3", "Bind4", "Bind5", "Bind6", "Button", "Canvas", "Chart", "Editor", "Image", "Pages", "Text", "Case", "Float", "Fold", "Form", "Group", "Layer", "Placeholder", "Popup", "Portal", "Rack", "Select", "Svg", "Table", "Tbody", "Td", "Th", "Thead", "Tr", "Accrete", "Bind"]



class ButtonAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    oneshot: bool | None = False
    selector: str | None = None


class CaseAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    grid: dict[str, Any] | None = None
    horizontal: bool | None = None
    selector: str | None = None


class ClassAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    horizontal: bool | None = Field(
        None,
        description='容器自身的排布方向（同 CaseAttr 字段；ADR 0010 缺陷修复：\n此前只有 Case 认识 horizontal，select/rack 的 col 类无法被\n自己的 attrs 推翻——父 case 的 horizontal 只管父 div）。',
    )
    selector: str | None = None


class Diagram(BaseModel):
    attrs: ClassAttr | None = None
    bind: dict[str, Bind] | None = None
    id: str | None = None
    type: Literal['diagram'] = 'diagram'


class Direction(Enum):
    U = 'U'
    D = 'D'
    L = 'L'
    R = 'R'


class DirectionAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    direction: Direction | None = None
    selector: str | None = None


class FoldAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    float_body: bool | None = None
    replace_header: bool | None = None
    selector: str | None = None


class FormAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    instant: bool | None = None
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


class RackAttr(BaseModel):
    class_: list[str] | None = Field(None, alias='class')
    scroll: bool | None = False
    selector: str | None = None


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
    event: str | None = None
    kind: Literal['local']
    path: str | None = None
    slot: str


class Bind3(BaseModel):
    default: Any | None = None
    type: JsType | None = None
    event: str
    kind: Literal['event']


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
    url: str = Field(
        ...,
        description='CDN 上的 ES module 地址（导出 mount/update/resize/unmount 契约）。',
    )
    type: Literal['canvas'] = 'canvas'


class Chart(BaseModel):
    attrs: ClassAttr | None = None
    bind: dict[str, Any] | None = Field(
        None,
        description='`bind["value"]`：G2 spec（纯数据，GoG 词汇——type/data/encode/\ntransform/scale/interaction）。流式更新 = set/patch 指针进\n`/data` 等节点，封装模块整 spec 重设 + `chart.update()` 增量重绘。',
    )
    id: str | None = None
    url: str | None = Field(
        '/assets/g2chart/index.js',
        description='G2 封装模块的 ES module 地址（ADR 0009：ADR 0007 契约，\nmount/update/resize/unmount）。默认指向自家静态资产——\n版本固定，换渲染实现/CDN 时显式覆盖。',
    )
    type: Literal['chart'] = 'chart'


class Editor(BaseModel):
    attrs: SizeAttr | None = None
    bind: dict[str, Bind] | None = None
    id: str | None = None
    url: str | None = Field(
        '/assets/editor/index.js',
        description='封装模块的 ES module 地址（ADR 0007 契约）。默认指向自家静态资产。',
    )
    type: Literal['editor'] = 'editor'


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


class Text(BaseModel):
    attrs: TextAttr | None = None
    bind: dict[str, Bind] | None = None
    id: str | None = None
    type: Literal['text'] = 'text'


class Case(BaseModel):
    attrs: CaseAttr | None = None
    bind: dict[str, Bind] | None = None
    children: list[Accrete] | None = None
    id: str | None = None
    type: Literal['case'] = 'case'


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


class Placeholder(BaseModel):
    attrs: ClassAttr | None = None
    bind: dict[str, Bind] | None = None
    children: list[Accrete] | None = None
    id: str | None = None
    type: Literal['placeholder'] = 'placeholder'


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
Accrete = Annotated[Union[Case | Placeholder | Chart | Diagram | Canvas | Editor | Float | Layer | Portal | Fold | Form | Popup | Svg | Group | Path | Rack | Pages | Button | Image | Input | Select | Table | Thead | Tbody | Tr | Th | Td | Text | TextArea | Template], Field(discriminator='type')]

# `bind` is a map of these, discriminated on `kind`.
Bind = Annotated[Union[Bind1 | Bind2 | Bind3 | Bind4 | Bind5 | Bind6], Field(discriminator='kind')]


# Forward references (`children: list[Accrete]`) resolve here, now that the aliases exist.
ButtonAttr.model_rebuild()
CaseAttr.model_rebuild()
ClassAttr.model_rebuild()
Diagram.model_rebuild()
DirectionAttr.model_rebuild()
FoldAttr.model_rebuild()
FormAttr.model_rebuild()
ImageAttr.model_rebuild()
Input.model_rebuild()
LayerAttr.model_rebuild()
Path.model_rebuild()
PortalAttr.model_rebuild()
PositionAttr.model_rebuild()
RackAttr.model_rebuild()
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
Chart.model_rebuild()
Editor.model_rebuild()
Image.model_rebuild()
Pages.model_rebuild()
Text.model_rebuild()
Case.model_rebuild()
Float.model_rebuild()
Fold.model_rebuild()
Form.model_rebuild()
Group.model_rebuild()
Layer.model_rebuild()
Placeholder.model_rebuild()
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
