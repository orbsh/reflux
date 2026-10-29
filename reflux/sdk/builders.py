from __future__ import annotations

from typing import Any

from ._parse import bind_entry, bind_value, drop_none, parse, token_attrs
from .types import *  # noqa: F403 — the wire's names are the SDK's names
from .types import Accrete


__all__ = ["button", "canvas", "case", "chart", "diagram", "editor", "float", "fold", "form", "group", "image", "input", "layer", "pages", "path", "placeholder", "popup", "portal", "rack", "select", "svg", "table", "tbody", "td", "text", "textarea", "th", "thead", "tr"]

def case(
    *children: Accrete,
    grid: dict[str, Any] | None = None,
    horizontal: bool | None = None,
    id: str | None = None,
    variant: str | None = None,
) -> Case:
    """Build a `case` node (the wire type `case`)."""
    attrs = token_attrs(drop_none(grid=grid, horizontal=horizontal), variant, 'case')
    bind = None
    return parse(drop_none(type='case', attrs=attrs, bind=bind, id=id, children=list(children) or None), Case)


def placeholder(
    *children: Accrete,
    horizontal: bool | None = None,
    source: Any = None,
    id: str | None = None,
) -> Placeholder:
    """Build a `placeholder` node (the wire type `placeholder`)."""
    attrs = drop_none(horizontal=horizontal)
    bind = drop_none(value=bind_value(source=source))
    return parse(drop_none(type='placeholder', attrs=attrs, bind=bind, id=id, children=list(children) or None), Placeholder)


def chart(
    value: Any = None,
    *,
    horizontal: bool | None = None,
    url: str = '/assets/g2chart/index.js',
    source: Any = None,
    id: str | None = None,
) -> Chart:
    """Build a `chart` node (the wire type `chart`)."""
    attrs = drop_none(horizontal=horizontal)
    bind = drop_none(value=bind_value(default=value, source=source))
    return parse(drop_none(type='chart', attrs=attrs, bind=bind, id=id, url=url), Chart)


def diagram(
    value: Any = None,
    *,
    horizontal: bool | None = None,
    id: str | None = None,
) -> Diagram:
    """Build a `diagram` node (the wire type `diagram`)."""
    attrs = drop_none(horizontal=horizontal)
    bind = drop_none(value=bind_value(default=value))
    return parse(drop_none(type='diagram', attrs=attrs, bind=bind, id=id), Diagram)


def canvas(
    value: Any = None,
    *,
    height: str | None = None,
    width: str | None = None,
    url: str = None,
    source: Any = None,
    id: str | None = None,
) -> Canvas:
    """Build a `canvas` node (the wire type `canvas`)."""
    attrs = drop_none(height=height, width=width)
    bind = drop_none(value=bind_value(default=value, source=source))
    return parse(drop_none(type='canvas', attrs=attrs, bind=bind, id=id, url=url), Canvas)


def editor(
    value: Any = None,
    *,
    height: str | None = None,
    width: str | None = None,
    url: str = '/assets/editor/index.js',
    source: Any = None,
    id: str | None = None,
) -> Editor:
    """Build a `editor` node (the wire type `editor`)."""
    attrs = drop_none(height=height, width=width)
    bind = drop_none(value=bind_value(default=value, source=source))
    return parse(drop_none(type='editor', attrs=attrs, bind=bind, id=id, url=url), Editor)


def float(
    *children: Accrete,
    left: str | None = None,
    right: str | None = None,
    top: str | None = None,
    bottom: str | None = None,
    id: str | None = None,
) -> Float:
    """Build a `float` node (the wire type `float`)."""
    attrs = drop_none(left=left, right=right, top=top, bottom=bottom)
    bind = None
    return parse(drop_none(type='float', attrs=attrs, bind=bind, id=id, children=list(children) or None), Float)


def layer(
    *children: Accrete,
    dismiss: bool | None = None,
    source: Any = None,
    id: str | None = None,
) -> Layer:
    """Build a `layer` node (the wire type `layer`)."""
    attrs = drop_none(dismiss=dismiss)
    bind = drop_none(value=bind_value(source=source))
    return parse(drop_none(type='layer', attrs=attrs, bind=bind, id=id, children=list(children) or None), Layer)


def portal(
    *children: Accrete,
    to: str = None,
    id: str | None = None,
) -> Portal:
    """Build a `portal` node (the wire type `portal`)."""
    attrs = drop_none(to=to)
    bind = None
    return parse(drop_none(type='portal', attrs=attrs, bind=bind, id=id, children=list(children) or None), Portal)


def fold(
    *children: Accrete,
    float_body: bool | None = None,
    replace_header: bool | None = None,
    value: Any = None,
    item: Any = None,
    id: str | None = None,
) -> Fold:
    """Build a `fold` node (the wire type `fold`)."""
    attrs = drop_none(float_body=float_body, replace_header=replace_header)
    bind = drop_none(value=bind_value(default=value))
    return parse(drop_none(type='fold', attrs=attrs, bind=bind, id=id, children=list(children) or None, item=list(item) if item else None), Fold)


def form(
    *children: Accrete,
    instant: bool | None = None,
    dest: Any = None,
    local: Any = None,
    path: str | None = None,
    id: str | None = None,
) -> Form:
    """Build a `form` node (the wire type `form`)."""
    attrs = drop_none(instant=instant)
    bind = drop_none(value=bind_value(dest=dest, local=local, path=path))
    return parse(drop_none(type='form', attrs=attrs, bind=bind, id=id, children=list(children) or None), Form)


def popup(
    *children: Accrete,
    direction: Direction | None = None,
    id: str | None = None,
) -> Popup:
    """Build a `popup` node (the wire type `popup`)."""
    attrs = drop_none(direction=direction)
    bind = None
    return parse(drop_none(type='popup', attrs=attrs, bind=bind, id=id, children=list(children) or None), Popup)


def svg(
    *children: Accrete,
    height: str | None = None,
    width: str | None = None,
    id: str | None = None,
) -> Svg:
    """Build a `svg` node (the wire type `svg`)."""
    attrs = drop_none(height=height, width=width)
    bind = None
    return parse(drop_none(type='svg', attrs=attrs, bind=bind, id=id, children=list(children) or None), Svg)


def group(
    *children: Accrete,
    style: dict[str, Any] | None = None,
    id: str | None = None,
) -> Group:
    """Build a `group` node (the wire type `group`)."""
    attrs = drop_none(style=style)
    bind = None
    return parse(drop_none(type='group', attrs=attrs, bind=bind, id=id, children=list(children) or None), Group)


def path(
    value: Any = None,
    *,
    horizontal: bool | None = None,
    id: str | None = None,
) -> Path:
    """Build a `path` node (the wire type `path`)."""
    attrs = drop_none(horizontal=horizontal)
    bind = drop_none(value=bind_value(default=value))
    return parse(drop_none(type='path', attrs=attrs, bind=bind, id=id), Path)


def rack(
    *,
    scroll: bool = False,
    source: Any = None,
    item: Any = None,
    id: str | None = None,
) -> Rack:
    """Build a `rack` node (the wire type `rack`)."""
    attrs = drop_none(scroll=scroll)
    bind = drop_none(value=bind_value(source=source))
    return parse(drop_none(type='rack', attrs=attrs, bind=bind, id=id, item=list(item) if item else None), Rack)


def pages(
    *,
    horizontal: bool | None = None,
    display: PagesDisplay = 'render',
    source: Any = None,
    select_source: Any = None,
    select_local: Any = None,
    path: str | None = None,
    id: str | None = None,
) -> Pages:
    """Build a `pages` node (the wire type `pages`)."""
    attrs = drop_none(horizontal=horizontal)
    bind = drop_none(value=bind_value(source=source), select=bind_entry('select', source=select_source, local=select_local, path=path))
    return parse(drop_none(type='pages', attrs=attrs, bind=bind, id=id, display=display), Pages)


def button(
    value: Any = None,
    *,
    oneshot: bool = False,
    id: str | None = None,
) -> Button:
    """Build a `button` node (the wire type `button`)."""
    attrs = drop_none(oneshot=oneshot)
    bind = drop_none(value=bind_value(submit=value))
    return parse(drop_none(type='button', attrs=attrs, bind=bind, id=id), Button)


def image(
    value: Any = None,
    *,
    desc: str | None = None,
    height: str | None = None,
    thumb: bool = False,
    width: str | None = None,
    id: str | None = None,
) -> Image:
    """Build a `image` node (the wire type `image`)."""
    attrs = drop_none(desc=desc, height=height, thumb=thumb, width=width)
    bind = drop_none(value=bind_value(default=value))
    return parse(drop_none(type='image', attrs=attrs, bind=bind, id=id), Image)


def input(
    *,
    horizontal: bool | None = None,
    dest: Any = None,
    field: Any = None,
    payload: Any = None,
    kind: JsType = None,
    id: str | None = None,
) -> Input:
    """Build a `input` node (the wire type `input`)."""
    attrs = drop_none(horizontal=horizontal)
    bind = drop_none(value=bind_value(dest=dest, field=field, payload=payload, js_kind=kind))
    return parse(drop_none(type='input', attrs=attrs, bind=bind, id=id), Input)


def select(
    *,
    horizontal: bool | None = None,
    value: Any = None,
    source: Any = None,
    dest: Any = None,
    options_source: Any = None,
    id: str | None = None,
) -> Select:
    """Build a `select` node (the wire type `select`)."""
    attrs = drop_none(horizontal=horizontal)
    bind = drop_none(value=bind_value(default=value, source=source, dest=dest), options=bind_entry('options', source=options_source))
    return parse(drop_none(type='select', attrs=attrs, bind=bind, id=id), Select)


def table(
    *children: Accrete,
    id: str | None = None,
) -> Table:
    """Build a `table` node (the wire type `table`)."""
    attrs = None
    bind = None
    return parse(drop_none(type='table', attrs=attrs, bind=bind, id=id, children=list(children) or None), Table)


def thead(
    *children: Accrete,
    id: str | None = None,
) -> Thead:
    """Build a `thead` node (the wire type `thead`)."""
    attrs = None
    bind = None
    return parse(drop_none(type='thead', attrs=attrs, bind=bind, id=id, children=list(children) or None), Thead)


def tbody(
    *children: Accrete,
    id: str | None = None,
) -> Tbody:
    """Build a `tbody` node (the wire type `tbody`)."""
    attrs = None
    bind = None
    return parse(drop_none(type='tbody', attrs=attrs, bind=bind, id=id, children=list(children) or None), Tbody)


def tr(
    *children: Accrete,
    id: str | None = None,
) -> Tr:
    """Build a `tr` node (the wire type `tr`)."""
    attrs = None
    bind = None
    return parse(drop_none(type='tr', attrs=attrs, bind=bind, id=id, children=list(children) or None), Tr)


def th(
    *children: Accrete,
    id: str | None = None,
) -> Th:
    """Build a `th` node (the wire type `th`)."""
    attrs = None
    bind = None
    return parse(drop_none(type='th', attrs=attrs, bind=bind, id=id, children=list(children) or None), Th)


def td(
    *children: Accrete,
    id: str | None = None,
) -> Td:
    """Build a `td` node (the wire type `td`)."""
    attrs = None
    bind = None
    return parse(drop_none(type='td', attrs=attrs, bind=bind, id=id, children=list(children) or None), Td)


def text(
    value: Any = None,
    *,
    format: str | None = None,
    source: Any = None,
    local: Any = None,
    path: str | None = None,
    id: str | None = None,
    variant: str | None = None,
) -> Text:
    """Build a `text` node (the wire type `text`)."""
    attrs = token_attrs(drop_none(format=format), variant, 'text')
    bind = drop_none(value=bind_value(default=value, source=source, local=local, path=path))
    return parse(drop_none(type='text', attrs=attrs, bind=bind, id=id), Text)


def textarea(
    *,
    horizontal: bool | None = None,
    value: Any = None,
    source: Any = None,
    dest: Any = None,
    placeholder: Any = None,
    id: str | None = None,
) -> TextArea:
    """Build a `textarea` node (the wire type `textarea`)."""
    attrs = drop_none(horizontal=horizontal)
    bind = drop_none(value=bind_value(default=value, source=source, dest=dest), placeholder=bind_entry('placeholder', default=placeholder))
    return parse(drop_none(type='textarea', attrs=attrs, bind=bind, id=id), TextArea)
