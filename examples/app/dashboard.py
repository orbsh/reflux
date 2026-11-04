"""The dashboard: the numbers, two charts and a 3D model — what the app is, at a glance.

    python3 -m examples.app --port 8100     # / is this page, /chat is the other one

Three things a page of this shape has to get right, and this file is the smallest case of each:

1. **A chart is a node whose value is a plain spec.** `b.chart(value=…, url=…)` carries a G2 grammar
   spec and names the module that draws it; the module is a file this app mounts (`CHART_DIR` below).
   No slot, no frame — the chart is part of the page like any other node.
2. **A module host is a canvas.** `b.canvas(url=…, value=…)` gives a 3D viewer a box and a payload;
   what the payload means belongs to the module (`{"assets": {...}}` here). The framework moves bytes.
3. **A refresh is a page turn.** The button redraws the same path with new numbers, so the whole page
   is replaced — which is exactly what a page is. Nothing keeps state for it.

Neither module is vendored: `www/static/vendor/` is ignored, and the 3D one is 30 MB with a model
beside it. Each is mounted from a fluxen checkout's `examples/renderer/assets` (`REFLUX_ASSETS`) or
from a local copy under `www/static/vendor/`; a module that is not on disk gets a line saying where
the page looked.
"""

from __future__ import annotations

import os
import random
from pathlib import Path
from typing import Any

from reflux import Context, Match
from reflux.sdk import builders as b
from reflux.sdk.types import Accrete

from .app import app

__all__ = ["dashboard", "line_spec", "radar_spec"]

HERE = Path(__file__).resolve().parents[2]          # the repo root
CHART_MODULE = "/assets/g2chart/index.js"
VIEWER_MODULE = "/assets/3dbrowser/index.js"
SHOE = "/assets/3dbrowser/MaterialsVariantsShoe.glb"
ASSETS = Path(os.environ.get("REFLUX_ASSETS", HERE.parent / "fluxen" / "examples" / "renderer" / "assets"))

# A route may be a directory, and that is how a page gets the files its modules need. Neither module
# is in git — `www/static/vendor/` is ignored, and 30 MB of 3D viewer is not an example's business —
# so each is mounted from wherever it exists: the local vendor copy under `www/static/vendor/` (the
# README says how to put one there), or a fluxen checkout's own assets.
CHART_DIR = next(
    (where for where in (HERE / "www" / "static" / "vendor" / "g2chart", ASSETS / "g2chart") if (where / "index.js").is_file()),
    None,
)
CHARTS = CHART_DIR is not None
if CHARTS:
    app.mount("/assets/g2chart", CHART_DIR)
VIEWER = (ASSETS / "3dbrowser").is_dir()
if VIEWER:
    app.mount("/assets/3dbrowser", ASSETS / "3dbrowser")

DAYS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
DIMS = ("出勤", "质量", "协作", "成长", "交付")


def line_spec(series: list[int]) -> dict[str, Any]:
    """A line chart in G2's own grammar: the data and what to encode, nothing about how to draw."""
    return {
        "type": "line",
        "data": [{"day": day, "calls": value} for day, value in zip(DAYS, series)],
        "encode": {"x": "day", "y": "calls"},
        "style": {"lineWidth": 2},
        "axis": {"x": {"title": None}, "y": {"title": "次/天"}},
    }


def radar_spec(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """A radar: a polar view over the same data, filled polygons with their outlines.

    The axis count is the data's `dim` values — there is no knob for it in the spec. `scale.x`
    (`padding: 0.5`, `align: 0`) is G2's own radar recipe: each dimension gets a slot and the first
    one lands at the top, so N axes are 360/N apart with no gap at 0°/360°.
    """
    encode = {"x": "dim", "y": "score", "color": "who"}
    return {
        "type": "view",
        "data": rows,
        "coordinate": {"type": "polar"},
        "scale": {
            "x": {"padding": 0.5, "align": 0},
            "y": {"domain": [0, 5], "tickCount": 5},
        },
        "axis": {"x": {"grid": True, "title": None}, "y": False},
        "legend": {"color": {"layout": {"justContent": True}}},
        "children": [
            {"type": "area", "encode": encode, "style": {"fillOpacity": 0.15, "lineWidth": 0}},
            {"type": "line", "encode": encode, "style": {"lineWidth": 2, "join": "round", "cap": "round"}},
        ],
        "interaction": {"tooltip": {}},
    }


def rows() -> list[dict[str, Any]]:
    return [
        {"dim": dim, "score": round(random.uniform(2.5, 5), 1), "who": who}
        for who in ("研发", "市场")
        for dim in DIMS
    ]


def charts(series: list[int]) -> list[Accrete]:
    """The two charts, or one line that says where the module comes from.

    A chart node with no module behind it draws an empty box, which reads as a bug rather than as a
    missing file — so the page says it instead of pretending.
    """
    if not CHARTS:
        return [
            b.text(
                f"这一格里是两张图：把 g2chart 放进 www/static/vendor/g2chart，或让 REFLUX_ASSETS 指到"
                f" fluxen 的 examples/renderer/assets（现在找的是 {ASSETS}）。",
                variant="muted",
                id="charts-note",
            )
        ]
    return [
        b.case(b.chart(value=line_spec(series), url=CHART_MODULE, id="trend"), grid={"grid-template-rows": "260px"}, id="band-trend"),
        b.case(b.chart(value=radar_spec(rows()), url=CHART_MODULE, id="radar"), grid={"grid-template-rows": "320px"}, id="band-radar"),
    ]


def summary(series: list[int]) -> str:
    return f"本周 {sum(series)} 次调用 · 峰值 {max(series)} · 均值 {sum(series) // len(series)}"


@app.route("/", title="概览")
def dashboard(ctx: Context, match: Match) -> None:
    """The page: a heading, the week's numbers, the charts, the viewport, and a way to redraw it.

    Everything hangs off one `case` with a gap — the page owns its own spacing, because the shell
    above only says where the page goes, not what it looks like inside. The address and the title are
    the declaration's, so `ctx.page` alone carries them.
    """
    series = [random.randint(20, 120) for _ in DAYS]
    ctx.page(
        b.case(
            b.text("概览", variant="heading-1"),
            b.text(summary(series), variant="muted", id="summary"),
            *charts(series),
            b.canvas(
                url=VIEWER_MODULE,
                value={"assets": {"shoe": SHOE}},
                width="100%",
                height="320px",
                id="viewer",
            )
            if VIEWER
            else b.text(
                f"这一格里是 3D 模型的位置：把 REFLUX_ASSETS 指向 fluxen 的 examples/renderer/assets"
                f"（现在找的是 {ASSETS}）。上面两张图是 G2 自己的语法，下面这一格是模块宿主。",
                variant="muted",
                id="viewer-note",
            ),
            b.form(b.button("换一组数据"), dest="dashboard.refresh", id="refresh"),
            id="page-dashboard",
            grid={"gap": "12px"},
        ),
    )


@app.dests.register("dashboard.refresh")
def on_refresh(ctx: Context, frame: dict) -> None:
    """New numbers, same page: a page turn is a redraw, so the whole structure comes again."""
    ctx.draw()