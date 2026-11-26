from __future__ import annotations

from typing import Any

from ._parse import as_set, as_sink, as_source, drop_none, parse, token_attrs
from .types import *  # noqa: F403 — the wire's names are the SDK's names
from .types import Accrete


__all__ = ["button", "canvas", "color", "entry", "forcegraph", "frame", "image", "input", "loom", "panel", "path", "picker", "svg", "text", "tiles"]

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


def loom(
    *children: Accrete,
    reset: ResetMode | str | None = None,
    selector: str | None = None,
    sends: int | None = None,
    submit: list[str] | str | None = None,
    sink: Any = None,
    tag: str | None = None,
    id: str | None = None,
) -> Loom:
    """Build a `loom` node (the wire type `loom`)."""
    attrs = drop_none(reset=reset, selector=selector, sends=sends, submit=as_set(submit))
    sink = as_sink(sink)
    return parse(drop_none(type='loom', attrs=attrs, sink=sink, id=id, children=list(children) or None, tag=tag), Loom)


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
    id: str | None = None,
) -> Button:
    """Build a `button` node (the wire type `button`)."""
    attrs = drop_none(oneshot=oneshot, selector=selector)
    source = as_source(source, default=value)
    return parse(drop_none(type='button', attrs=attrs, source=source, id=id), Button)


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
    emit: Emit | dict[str, Any] | None = None,
    kind: InputKind | str | None = None,
    multiline: bool | None = None,
    placeholder: Any = None,
    tag: str | None = None,
    id: str | None = None,
) -> Input:
    """Build a `input` node (the wire type `input`)."""
    attrs = drop_none(horizontal=horizontal, selector=selector)
    source = as_source(source, constants=False)
    placeholder = as_source(placeholder)
    return parse(drop_none(type='input', attrs=attrs, source=source, placeholder=placeholder, id=id, emit=emit, kind=kind, multiline=multiline, tag=tag), Input)


def picker(
    *,
    dir: Dir | str | None = None,
    expand: bool | None = None,
    multiple: bool | None = None,
    selector: str | None = None,
    source: Any = None,
    kind: PickerKind | str | dict[str, Any] | None = None,
    options: Any = None,
    tag: str | None = None,
    id: str | None = None,
) -> Picker:
    """Build a `picker` node (the wire type `picker`)."""
    attrs = drop_none(dir=dir, expand=expand, multiple=multiple, selector=selector)
    source = as_source(source)
    options = as_source(options)
    return parse(drop_none(type='picker', attrs=attrs, source=source, options=options, id=id, kind=kind, tag=tag), Picker)


def color(
    *,
    selector: str | None = None,
    source: Any = None,
    emit: Emit | dict[str, Any] | None = None,
    tag: str | None = None,
    id: str | None = None,
) -> Color:
    """Build a `color` node (the wire type `color`)."""
    attrs = drop_none(selector=selector)
    source = as_source(source)
    return parse(drop_none(type='color', attrs=attrs, source=source, id=id, emit=emit, tag=tag), Color)


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
