from __future__ import annotations

from typing import Any

from ._parse import as_set, as_sink, as_source, drop_none, parse, token_attrs
from .types import *  # noqa: F403 — the wire's names are the SDK's names
from .types import Accrete


__all__ = ["bundle", "button", "canvas", "dock", "forcegraph", "frame", "grab", "group", "image", "input", "pages", "panel", "path", "rack", "select", "svg", "table", "tbody", "td", "text", "th", "thead", "tr"]

def frame(
    *children: Accrete,
    grid: dict[str, Any] | None = None,
    horizontal: bool | None = None,
    source: Any = None,
    id: str | None = None,
    variant: str | None = None,
) -> Frame:
    """Build a `frame` node (the wire type `frame`)."""
    attrs = token_attrs(drop_none(grid=grid, horizontal=horizontal), variant, 'frame')
    source = as_source(source, constants=False)
    return parse(drop_none(type='frame', attrs=attrs, source=source, id=id, children=list(children) or None), Frame)


def canvas(
    value: Any = None,
    *,
    height: str | None = None,
    width: str | None = None,
    source: Any = None,
    options: Any | None = None,
    url: str | None = None,
    id: str | None = None,
) -> Canvas:
    """Build a `canvas` node (the wire type `canvas`)."""
    attrs = drop_none(height=height, width=width)
    source = as_source(source, default=value)
    return parse(drop_none(type='canvas', attrs=attrs, source=source, id=id, options=options, url=url), Canvas)


def forcegraph(
    value: Any = None,
    *,
    height: str | None = None,
    width: str | None = None,
    source: Any = None,
    style: ForceGraphStyle | None = None,
    theme: Any = None,
    id: str | None = None,
) -> ForceGraph:
    """Build a `forcegraph` node (the wire type `forcegraph`)."""
    attrs = drop_none(height=height, width=width)
    source = as_source(source, default=value)
    theme = as_source(theme)
    return parse(drop_none(type='forcegraph', attrs=attrs, source=source, theme=theme, id=id, style=style), ForceGraph)


def panel(
    *children: Accrete,
    direction: Direction | None = None,
    dismiss: bool | None = None,
    place: PanelPlace | None = None,
    replace_header: bool | None = None,
    state: PanelState | None = None,
    width: str | None = None,
    left: str | None = None,
    right: str | None = None,
    top: str | None = None,
    bottom: str | None = None,
    source: Any = None,
    id: str | None = None,
) -> Panel:
    """Build a `panel` node (the wire type `panel`)."""
    attrs = drop_none(direction=direction, dismiss=dismiss, place=place, replace_header=replace_header, state=state, width=width, left=left, right=right, top=top, bottom=bottom)
    source = as_source(source, constants=False)
    return parse(drop_none(type='panel', attrs=attrs, source=source, id=id, children=list(children) or None), Panel)


def bundle(
    *children: Accrete,
    submit: list[str] | str | None = None,
    sink: Any = None,
    tag: str | None = None,
    id: str | None = None,
) -> Bundle:
    """Build a `bundle` node (the wire type `bundle`)."""
    attrs = drop_none(submit=as_set(submit))
    sink = as_sink(sink)
    return parse(drop_none(type='bundle', attrs=attrs, sink=sink, id=id, children=list(children) or None, tag=tag), Bundle)


def svg(
    *children: Accrete,
    height: str | None = None,
    width: str | None = None,
    id: str | None = None,
) -> Svg:
    """Build a `svg` node (the wire type `svg`)."""
    attrs = drop_none(height=height, width=width)
    return parse(drop_none(type='svg', attrs=attrs, id=id, children=list(children) or None), Svg)


def group(
    *children: Accrete,
    style: dict[str, Any] | None = None,
    id: str | None = None,
) -> Group:
    """Build a `group` node (the wire type `group`)."""
    attrs = drop_none(style=style)
    return parse(drop_none(type='group', attrs=attrs, id=id, children=list(children) or None), Group)


def path(
    value: Any = None,
    *,
    horizontal: bool | None = None,
    source: Any = None,
    id: str | None = None,
) -> Path:
    """Build a `path` node (the wire type `path`)."""
    attrs = drop_none(horizontal=horizontal)
    source = as_source(source, default=value)
    return parse(drop_none(type='path', attrs=attrs, source=source, id=id), Path)


def rack(
    *,
    horizontal: bool | None = None,
    scroll: bool = False,
    view: RackView | None = None,
    source: Any = None,
    item: Any = None,
    id: str | None = None,
) -> Rack:
    """Build a `rack` node (the wire type `rack`)."""
    attrs = drop_none(horizontal=horizontal, scroll=scroll, view=view)
    source = as_source(source, constants=False)
    return parse(drop_none(type='rack', attrs=attrs, source=source, id=id, item=list(item) if item else None), Rack)


def pages(
    *,
    horizontal: bool | None = None,
    source: Any = None,
    display: PagesDisplay = 'render',
    select: Any = None,
    id: str | None = None,
) -> Pages:
    """Build a `pages` node (the wire type `pages`)."""
    attrs = drop_none(horizontal=horizontal)
    source = as_source(source, constants=False)
    select = as_source(select)
    return parse(drop_none(type='pages', attrs=attrs, source=source, select=select, id=id, display=display), Pages)


def button(
    value: Any = None,
    *,
    oneshot: bool = False,
    source: Any = None,
    sink: Any = None,
    id: str | None = None,
) -> Button:
    """Build a `button` node (the wire type `button`)."""
    attrs = drop_none(oneshot=oneshot)
    source = as_source(source, default=value)
    sink = as_sink(sink)
    return parse(drop_none(type='button', attrs=attrs, source=source, sink=sink, id=id), Button)


def image(
    value: Any = None,
    *,
    desc: str | None = None,
    height: str | None = None,
    thumb: bool = False,
    width: str | None = None,
    source: Any = None,
    id: str | None = None,
) -> Image:
    """Build a `image` node (the wire type `image`)."""
    attrs = drop_none(desc=desc, height=height, thumb=thumb, width=width)
    source = as_source(source, default=value)
    return parse(drop_none(type='image', attrs=attrs, source=source, id=id), Image)


def input(
    *,
    horizontal: bool | None = None,
    source: Any = None,
    sink: Any = None,
    multiline: bool | None = None,
    placeholder: Any = None,
    tag: str | None = None,
    id: str | None = None,
) -> Input:
    """Build a `input` node (the wire type `input`)."""
    attrs = drop_none(horizontal=horizontal)
    source = as_source(source, constants=False)
    sink = as_sink(sink)
    placeholder = as_source(placeholder)
    return parse(drop_none(type='input', attrs=attrs, source=source, sink=sink, placeholder=placeholder, id=id, multiline=multiline, tag=tag), Input)


def select(
    *,
    horizontal: bool | None = None,
    source: Any = None,
    sink: Any = None,
    options: Any = None,
    tag: str | None = None,
    id: str | None = None,
) -> Select:
    """Build a `select` node (the wire type `select`)."""
    attrs = drop_none(horizontal=horizontal)
    source = as_source(source)
    sink = as_sink(sink)
    options = as_source(options)
    return parse(drop_none(type='select', attrs=attrs, source=source, sink=sink, options=options, id=id, tag=tag), Select)


def table(
    *children: Accrete,
    id: str | None = None,
) -> Table:
    """Build a `table` node (the wire type `table`)."""
    attrs = None
    return parse(drop_none(type='table', attrs=attrs, id=id, children=list(children) or None), Table)


def thead(
    *children: Accrete,
    id: str | None = None,
) -> Thead:
    """Build a `thead` node (the wire type `thead`)."""
    attrs = None
    return parse(drop_none(type='thead', attrs=attrs, id=id, children=list(children) or None), Thead)


def tbody(
    *children: Accrete,
    id: str | None = None,
) -> Tbody:
    """Build a `tbody` node (the wire type `tbody`)."""
    attrs = None
    return parse(drop_none(type='tbody', attrs=attrs, id=id, children=list(children) or None), Tbody)


def tr(
    *children: Accrete,
    id: str | None = None,
) -> Tr:
    """Build a `tr` node (the wire type `tr`)."""
    attrs = None
    return parse(drop_none(type='tr', attrs=attrs, id=id, children=list(children) or None), Tr)


def th(
    *children: Accrete,
    id: str | None = None,
) -> Th:
    """Build a `th` node (the wire type `th`)."""
    attrs = None
    return parse(drop_none(type='th', attrs=attrs, id=id, children=list(children) or None), Th)


def td(
    *children: Accrete,
    id: str | None = None,
) -> Td:
    """Build a `td` node (the wire type `td`)."""
    attrs = None
    return parse(drop_none(type='td', attrs=attrs, id=id, children=list(children) or None), Td)


def text(
    value: Any = None,
    *,
    format: str | None = None,
    source: Any = None,
    id: str | None = None,
    variant: str | None = None,
) -> Text:
    """Build a `text` node (the wire type `text`)."""
    attrs = token_attrs(drop_none(format=format), variant, 'text')
    source = as_source(source, default=value)
    return parse(drop_none(type='text', attrs=attrs, source=source, id=id), Text)


def grab(
    *children: Accrete,
    kind: str | None = None,
    payload: Any | None = None,
    id: str | None = None,
) -> Grab:
    """Build a `grab` node (the wire type `grab`)."""
    attrs = None
    return parse(drop_none(type='grab', attrs=attrs, id=id, children=list(children) or None, kind=kind, payload=payload), Grab)


def dock(
    *children: Accrete,
    accept: list[str] | None = None,
    expand: DockExpand | None = None,
    sink: Any = None,
    id: str | None = None,
) -> Dock:
    """Build a `dock` node (the wire type `dock`)."""
    attrs = drop_none(accept=accept, expand=expand)
    sink = as_sink(sink)
    return parse(drop_none(type='dock', attrs=attrs, sink=sink, id=id, children=list(children) or None), Dock)
