"""GENERATED from spec/components.json — do not edit.

The builders. One layer above `tables_generated` (pure data) and `node.make`
(the validating boundary), so import order never cycles.

Regenerate: python3 tools/gen.py      Verify: python3 tools/gen.py --check
"""

from __future__ import annotations

from .node import Node, make
from .tables_generated import (
    BIND_KEYS,
    COMPONENTS,
    FIRE_EVENTS,
    OPS,
    RESERVED_PREFIX,
    SPEC_VERSION,
)

__all__ = [
    'badge', 'button', 'card', 'checkbox', 'code', 'empty', 'field', 'form', 'heading', 'image', 'input', 'link', 'option', 'progress', 'rack', 'row', 'select', 'stack', 'switch', 'text', 'textarea',
    "SPEC_VERSION",
    "RESERVED_PREFIX",
    "OPS",
    "BIND_KEYS",
    "FIRE_EVENTS",
    "COMPONENTS",
]


def badge(value: str, *, tone: "neutral" | "info" | "success" | "warning" | "danger" | None = 'neutral', source: str | None = None, id: str | None = None) -> Node:
    """display: none children"""
    return make("badge", {"tone": tone, "value": value}, (), id=id, source=source)


def button(label: str, *, disabled: bool | None = False, size: "sm" | "md" | None = 'md', variant: "primary" | "secondary" | "ghost" | "danger" | None = 'secondary', event: str | None = None, id: str | None = None) -> Node:
    """nav: none children"""
    return make("button", {"disabled": disabled, "label": label, "size": size, "variant": variant}, (), id=id, event=event)


def card(*children: Node, title: str | None = '', tone: "plain" | "muted" | "raised" | None = 'plain', source: str | None = None, id: str | None = None) -> Node:
    """container: many children"""
    return make("card", {"title": title, "tone": tone}, children, id=id, source=source)


def checkbox(*, disabled: bool | None = False, label: str, source: str | None = None, event: str | None = None, payload: list[str] | None = None, id: str | None = None) -> Node:
    """input: none children; local state: checked"""
    return make("checkbox", {"disabled": disabled, "label": label}, (), id=id, source=source, event=event, payload=payload)


def code(value: str, *, lang: str | None = '', source: str | None = None, id: str | None = None) -> Node:
    """display: none children"""
    return make("code", {"lang": lang, "value": value}, (), id=id, source=source)


def empty(value: str, *, hint: str | None = '', source: str | None = None, id: str | None = None) -> Node:
    """feedback: none children"""
    return make("empty", {"hint": hint, "value": value}, (), id=id, source=source)


def field(*children: Node, hint: str | None = '', label: str, required: bool | None = False, id: str | None = None) -> Node:
    """container: one children"""
    return make("field", {"hint": hint, "label": label, "required": required}, children, id=id)


def form(*children: Node, disabled: bool | None = False, submit_label: str, event: str | None = None, payload: list[str] | None = None, id: str | None = None) -> Node:
    """container: many children; local state: fields"""
    return make("form", {"disabled": disabled, "submit_label": submit_label}, children, id=id, event=event, payload=payload)


def heading(value: str, *, level: int | None = 2, source: str | None = None, id: str | None = None) -> Node:
    """display: none children"""
    return make("heading", {"level": level, "value": value}, (), id=id, source=source)


def image(src: str, *, alt: str | None = '', fit: "contain" | "cover" | None = 'contain', source: str | None = None, id: str | None = None) -> Node:
    """display: none children"""
    return make("image", {"alt": alt, "fit": fit, "src": src}, (), id=id, source=source)


def input(*, disabled: bool | None = False, kind: "text" | "password" | "email" | "number" | "search" | None = 'text', placeholder: str | None = '', source: str | None = None, event: str | None = None, payload: list[str] | None = None, id: str | None = None) -> Node:
    """input: none children; local state: value, focus"""
    return make("input", {"disabled": disabled, "kind": kind, "placeholder": placeholder}, (), id=id, source=source, event=event, payload=payload)


def link(href: str, *, external: bool | None = False, label: str | None = '', source: str | None = None, id: str | None = None) -> Node:
    """nav: none children"""
    return make("link", {"external": external, "href": href, "label": label}, (), id=id, source=source)


def option(value: str, *, disabled: bool | None = False, label: str | None = '', id: str | None = None) -> Node:
    """input: none children"""
    return make("option", {"disabled": disabled, "label": label, "value": value}, (), id=id)


def progress(value: int, *, indeterminate: bool | None = False, label: str | None = '', source: str | None = None, id: str | None = None) -> Node:
    """feedback: none children"""
    return make("progress", {"indeterminate": indeterminate, "label": label, "value": value}, (), id=id, source=source)


def rack(*children: Node, density: "compact" | "normal" | None = 'normal', empty_text: str | None = '', follow: "none" | "end" | None = 'none', source: str | None = None, id: str | None = None) -> Node:
    """container: many children; local state: scroll"""
    return make("rack", {"density": density, "empty_text": empty_text, "follow": follow}, children, id=id, source=source)


def row(*children: Node, align: "start" | "center" | "end" | "baseline" | None = 'center', gap: "none" | "sm" | "md" | "lg" | None = 'md', wrap: "nowrap" | "wrap" | None = 'nowrap', source: str | None = None, id: str | None = None) -> Node:
    """container: many children"""
    return make("row", {"align": align, "gap": gap, "wrap": wrap}, children, id=id, source=source)


def select(*children: Node, disabled: bool | None = False, source: str | None = None, event: str | None = None, payload: list[str] | None = None, id: str | None = None) -> Node:
    """input: many children; local state: value"""
    return make("select", {"disabled": disabled}, children, id=id, source=source, event=event, payload=payload)


def stack(*children: Node, align: "start" | "center" | "end" | "stretch" | None = 'stretch', direction: "column" | "row" | None = 'column', gap: "none" | "sm" | "md" | "lg" | None = 'md', source: str | None = None, id: str | None = None) -> Node:
    """container: many children"""
    return make("stack", {"align": align, "direction": direction, "gap": gap}, children, id=id, source=source)


def switch(*, disabled: bool | None = False, label: str, source: str | None = None, event: str | None = None, payload: list[str] | None = None, id: str | None = None) -> Node:
    """input: none children; local state: checked"""
    return make("switch", {"disabled": disabled, "label": label}, (), id=id, source=source, event=event, payload=payload)


def text(value: str, *, size: "sm" | "md" | "lg" | None = 'md', tone: "default" | "muted" | "success" | "warning" | "danger" | None = 'default', wrap: bool | None = True, source: str | None = None, id: str | None = None) -> Node:
    """display: none children"""
    return make("text", {"size": size, "tone": tone, "value": value, "wrap": wrap}, (), id=id, source=source)


def textarea(*, disabled: bool | None = False, placeholder: str | None = '', rows: int | None = 4, source: str | None = None, event: str | None = None, payload: list[str] | None = None, id: str | None = None) -> Node:
    """input: none children; local state: value, focus"""
    return make("textarea", {"disabled": disabled, "placeholder": placeholder, "rows": rows}, (), id=id, source=source, event=event, payload=payload)

