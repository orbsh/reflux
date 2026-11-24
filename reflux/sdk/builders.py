from __future__ import annotations

from typing import Any

from ._parse import as_set, as_sink, as_source, drop_none, parse, token_attrs
from .types import *  # noqa: F403 — the wire's names are the SDK's names
from .types import Accrete


__all__ = ["bundle", "button", "canvas", "entry", "forcegraph", "frame", "image", "input", "panel", "path", "select", "svg", "text", "tiles"]

def frame(
    *children: Accrete,
    accept: Accept | dict[str, Any] | None = None,
    draggable: Draggable | dict[str, Any] | None = None,
    grid: dict[str, Any] | None = None,
    horizontal: bool | None = None,
    selector: str | None = None,
    style: dict[str, Any] | None = None,
    source: Any = None,
    sink: Any = None,
    id: str | None = None,
    variant: str | None = None,
) -> Frame:
    """Build a `frame` node (the wire type `frame`)."""
    attrs = token_attrs(drop_none(accept=accept, draggable=draggable, grid=grid, horizontal=horizontal, selector=selector, style=style), variant, 'frame')
    source = as_source(source, constants=False)
    sink = as_sink(sink)
    return parse(drop_none(type='frame', attrs=attrs, source=source, sink=sink, id=id, children=list(children) or None), Frame)


def canvas(
    value: Any = None,
    *,
    height: str | None = None,
    selector: str | None = None,
    width: str | None = None,
    source: Any = None,
    options: Any | None = None,
    url: str | None = None,
    id: str | None = None,
) -> Canvas:
    """Build a `canvas` node (the wire type `canvas`)."""
    attrs = drop_none(height=height, selector=selector, width=width)
    source = as_source(source, default=value)
    return parse(drop_none(type='canvas', attrs=attrs, source=source, id=id, options=options, url=url), Canvas)


def forcegraph(
    value: Any = None,
    *,
    height: str | None = None,
    selector: str | None = None,
    width: str | None = None,
    source: Any = None,
    style: ForceGraphStyle | dict[str, Any] | None = None,
    theme: Any = None,
    id: str | None = None,
) -> ForceGraph:
    """Build a `forcegraph` node (the wire type `forcegraph`)."""
    attrs = drop_none(height=height, selector=selector, width=width)
    source = as_source(source, default=value)
    theme = as_source(theme)
    return parse(drop_none(type='forcegraph', attrs=attrs, source=source, theme=theme, id=id, style=style), ForceGraph)


def panel(
    *children: Accrete,
    direction: Direction | str | None = None,
    dismiss: bool | None = None,
    place: PanelPlace | str | None = None,
    replace_header: bool | None = None,
    selector: str | None = None,
    state: PanelState | str | None = None,
    width: str | None = None,
    left: str | None = None,
    right: str | None = None,
    top: str | None = None,
    bottom: str | None = None,
    source: Any = None,
    id: str | None = None,
) -> Panel:
    """Build a `panel` node (the wire type `panel`)."""
    attrs = drop_none(direction=direction, dismiss=dismiss, place=place, replace_header=replace_header, selector=selector, state=state, width=width, left=left, right=right, top=top, bottom=bottom)
    source = as_source(source, constants=False)
    return parse(drop_none(type='panel', attrs=attrs, source=source, id=id, children=list(children) or None), Panel)


def bundle(
    *children: Accrete,
    reset: ResetMode | str | None = None,
    selector: str | None = None,
    sends: int | None = None,
    submit: list[str] | str | None = None,
    sink: Any = None,
    tag: str | None = None,
    id: str | None = None,
) -> Bundle:
    """Build a `bundle` node (the wire type `bundle`)."""
    attrs = drop_none(reset=reset, selector=selector, sends=sends, submit=as_set(submit))
    sink = as_sink(sink)
    return parse(drop_none(type='bundle', attrs=attrs, sink=sink, id=id, children=list(children) or None, tag=tag), Bundle)


def svg(
    *children: Accrete,
    height: str | None = None,
    selector: str | None = None,
    width: str | None = None,
    id: str | None = None,
) -> Svg:
    """Build a `svg` node (the wire type `svg`)."""
    attrs = drop_none(height=height, selector=selector, width=width)
    return parse(drop_none(type='svg', attrs=attrs, id=id, children=list(children) or None), Svg)


def path(
    value: Any = None,
    *,
    horizontal: bool | None = None,
    selector: str | None = None,
    source: Any = None,
    id: str | None = None,
) -> Path:
    """Build a `path` node (the wire type `path`)."""
    attrs = drop_none(horizontal=horizontal, selector=selector)
    source = as_source(source, default=value)
    return parse(drop_none(type='path', attrs=attrs, source=source, id=id), Path)


def tiles(
    *children: Accrete,
    dir: Dir | str | None = None,
    fields: list[Field | dict[str, Any]] | None = None,
    header: Header | dict[str, Any] | None = None,
    selector: str | None = None,
    step: Step | dict[str, Any] | None = None,
    window: Window | dict[str, Any] | None = None,
    wrap: Wrap | str | None = None,
    source: Any = None,
    id: str | None = None,
) -> Tiles:
    """Build a `tiles` node (the wire type `tiles`)."""
    attrs = drop_none(dir=dir, fields=fields, header=header, selector=selector, step=step, window=window, wrap=wrap)
    source = as_source(source, constants=False)
    return parse(drop_none(type='tiles', attrs=attrs, source=source, id=id, children=list(children) or None), Tiles)


def entry(
    *children: Accrete,
    horizontal: bool | None = None,
    selector: str | None = None,
    id: str | None = None,
) -> Entry:
    """Build a `entry` node (the wire type `entry`)."""
    attrs = drop_none(horizontal=horizontal, selector=selector)
    return parse(drop_none(type='entry', attrs=attrs, id=id, children=list(children) or None), Entry)


def button(
    value: Any = None,
    *,
    oneshot: bool = False,
    selector: str | None = None,
    source: Any = None,
    sink: Any = None,
    id: str | None = None,
) -> Button:
    """Build a `button` node (the wire type `button`)."""
    attrs = drop_none(oneshot=oneshot, selector=selector)
    source = as_source(source, default=value)
    sink = as_sink(sink)
    return parse(drop_none(type='button', attrs=attrs, source=source, sink=sink, id=id), Button)


def image(
    value: Any = None,
    *,
    desc: str | None = None,
    height: str | None = None,
    selector: str | None = None,
    thumb: bool = False,
    width: str | None = None,
    source: Any = None,
    id: str | None = None,
) -> Image:
    """Build a `image` node (the wire type `image`)."""
    attrs = drop_none(desc=desc, height=height, selector=selector, thumb=thumb, width=width)
    source = as_source(source, default=value)
    return parse(drop_none(type='image', attrs=attrs, source=source, id=id), Image)


def input(
    *,
    horizontal: bool | None = None,
    selector: str | None = None,
    source: Any = None,
    sink: Any = None,
    multiline: bool | None = None,
    placeholder: Any = None,
    tag: str | None = None,
    id: str | None = None,
) -> Input:
    """Build a `input` node (the wire type `input`)."""
    attrs = drop_none(horizontal=horizontal, selector=selector)
    source = as_source(source, constants=False)
    sink = as_sink(sink)
    placeholder = as_source(placeholder)
    return parse(drop_none(type='input', attrs=attrs, source=source, sink=sink, placeholder=placeholder, id=id, multiline=multiline, tag=tag), Input)


def select(
    *,
    horizontal: bool | None = None,
    selector: str | None = None,
    source: Any = None,
    sink: Any = None,
    options: Any = None,
    tag: str | None = None,
    id: str | None = None,
) -> Select:
    """Build a `select` node (the wire type `select`)."""
    attrs = drop_none(horizontal=horizontal, selector=selector)
    source = as_source(source)
    sink = as_sink(sink)
    options = as_source(options)
    return parse(drop_none(type='select', attrs=attrs, source=source, sink=sink, options=options, id=id, tag=tag), Select)


def text(
    value: Any = None,
    *,
    format: str | None = None,
    selector: str | None = None,
    source: Any = None,
    id: str | None = None,
    variant: str | None = None,
) -> Text:
    """Build a `text` node (the wire type `text`)."""
    attrs = token_attrs(drop_none(format=format, selector=selector), variant, 'text')
    source = as_source(source, default=value)
    return parse(drop_none(type='text', attrs=attrs, source=source, id=id), Text)
