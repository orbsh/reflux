"""The demo's content: what the page says and what the hosts draw, as data.

Ported from fluxen's `examples/walkthrough.py` and `examples/yaml/00.radar.yaml` (extracted
2026-11-24, fluxen `8f8fd84`). Those two files stay the origin of the story; this one is what reflux
can read without a YAML parser or a checkout of the other repo. A change there does not reach here —
re-run the extraction if the story itself moves.

Nothing in this module knows about slots, frames or the page: it is text, chart specs and a graph.
`page.py` is the player that puts them on screen.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "ANALYTICS",
    "BEATS",
    "DEPTS",
    "GRAPH_LINKS",
    "GRAPH_NODES",
    "GRAPH_REVEAL",
    "GRAPH_SEED",
    "PATCH",
    "PATCH_CODE",
    "RADARS",
    "REVIEW",
    "SAY_CAR",
    "SAY_GRAPH",
    "SAY_SHOE",
    "SUMMARY",
    "TAIL_DAYS",
    "TREND",
    "graph_payload",
]

# ---- six passages of narration: verbatim from walkthrough.py ------------------------------------------
ANALYTICS = """Start with a set of simulated numbers: 11 people, 3 departments, each person scored every day on their own dimensions — R&D on five, Marketing on six, Operations on seven — 0 to 5, for 30 days straight. The first chart below is the daily average per department; the second lays every person of a department into one coordinate system so their shapes can be compared (three radars, 5 / 6 / 7 axes — the axis count follows the data). Below that, a review table: change a score per person and submit it."""
SUMMARY = """Summary: over the last 30 days the three departments' averages held steady and drifted up; R&D was the most volatile (3.20–4.07), Marketing next, Operations the steadiest and finishing high — and all three fell together over the last two days."""
SAY_CAR = """Start with the big one. This car is not a mesh — no faces, no UVs, no textures. It is tens of thousands of Gaussian ellipsoids stacked by position, scale and orientation (the academic name is 3D Gaussian Splatting).

Think of it as a cloud of glowing fog: every point carries its own colour, opacity and direction; rendering sorts them by view direction, projects each ellipsoid onto the screen and blends — it never rebuilds triangles and lights them. The gain is direct: what it keeps is how the real thing looked. The reflections in the paint, the thickness of the window glass, the highlight along the edge all arrive at once, with no hand-modelling and no guessing at material parameters. The cost is just as clear: large files, a sort per view, and no easy way to edit topology or rig a skeleton for animation the way a mesh allows. So its place today is "bring a real scene into the browser", not "replace the game's mesh assets".

Drag the car to turn it; scroll to move closer. The depth you see is its own — which is why this kind of reconstruction reads as more "solid" than a low-poly model."""
SAY_SHOE = """Something small next. What these two share is that neither argues from a specification sheet — both argue from what they look like and how they turn. So the text gives only what is needed, and the rest is a model you can spin.

The problem this shoe solves is not "run faster", it is "still have feet afterwards". The value of a shoe is rarely the two seconds it saves on one run; it is whether you want to go out tomorrow. The midsole is two densities: the top layer is soft and takes the impact of landing, the bottom layer is firmer and gives the energy back. Step down and most of the shock is absorbed before the shoe pushes you off the ground, so it does not behave like a purely soft sole — deep compression, no return. The lacing is a quick-pull: one hand, one tighten, workable with gloves on. The upper is one piece of knit with no seams to rub a hard edge across the instep or the outside of the toes over a long run. The last is neutral, with about a thumb's width in front of the toes, so a wide foot still fits.

Below is the model: drag with the left button to orbit and look at the sidewall's support and the tread; drag with the right button to pan, scroll to zoom."""
PATCH = """One more turn of direction. Everything so far was "look"; this is "change". The editor below is Monaco — the kernel VS Code uses. The code is not embedded in the page: it arrives as an argument with the message, exactly like the two products above, and is written into a data slot that the editor subscribes to.

That means two things. First, the library's download follows the payload: the text of this section arrives first, and Monaco's four-odd megabytes are fetched only once real code is sent — so "the message contains an editor" is not "the first paint is four megabytes heavier". Second, the uplink is the same leg: edit a line or two, press Ctrl/Cmd+S, and the whole block goes back to the producer with its language id, along the channel the review table submits on; the producer writes the file or opens a review.

Try changing a line — collect() to something else — then press Ctrl/Cmd+S and watch the `<-` block in the stage console."""
SAY_GRAPH = """One last look at the graph on the left — it has been there the whole time; you just did not notice it. This page's layout has had this shape since the first second: a persistent relationship graph on the left, one stream on the right. No menu, no tabs, no channel list. The old interface handed "where do I go" to a taxonomy, and a taxonomy is a one-time judgement written once and never revised; here "where do I go" is handed to relations, and relations are present-tense — "who else is connected to this" is a question a tree-shaped menu cannot answer.

The graph is this system itself: the dots are crates / components / external modules, the lines are "who renders whom, who mounts whom"; the bigger the dot and the thicker the line, the heavier its place in the chain. Two things are worth a look. First, it is not outsourced to some JS charting library: rendering, force layout, camera and picking all live in this wasm, so the knobs are the DSL's typed fields (node size, edge width, force parameters), not a black-box config passed through to someone else — and that is also why it is not three.js's 1.4 MB. Second, the graph grows: the full snapshots sent earlier are diffed by node id, so components are added in batches and the dots already in place do not re-shuffle; the last move is one focus transition — the camera flies to a few nodes and the rest do not disappear, they simply step back. That is how search lands.

Drag with the left button to turn the view, scroll to zoom, click a node and it sends one event up."""

PATCH_CODE = """pub fn render(nodes: &[Node]) -> Frame {
    // change a line or two, then Ctrl/Cmd+S: the block goes back up the same channel, with its language id
    nodes.iter().map(Node::draw).collect()
}
"""

# the 15 days the trend adds beyond the summary (09-18 … 10-02): one frame per day, appended to `trend`;
# the three numbers are the three departments' daily averages, in `DEPTS` order.
DEPTS = ('R&D', 'Marketing', 'Operations')
TAIL_DAYS = [
    ('09-18', 3.53, 3.53, 3.53),
    ('09-19', 3.64, 3.42, 3.77),
    ('09-20', 3.45, 3.38, 3.9),
    ('09-21', 3.28, 3.37, 3.67),
    ('09-22', 3.36, 3.51, 3.7),
    ('09-23', 3.55, 3.41, 3.8),
    ('09-24', 3.6, 3.45, 3.78),
    ('09-25', 3.77, 3.68, 3.77),
    ('09-26', 3.85, 3.46, 3.87),
    ('09-27', 3.92, 3.7, 4.03),
    ('09-28', 3.81, 3.65, 4.11),
    ('09-29', 3.57, 3.63, 3.95),
    ('09-30', 3.38, 3.41, 4.08),
    ('10-01', 3.2, 3.28, 4.03),
    ('10-02', 3.39, 3.2, 4.0),
]

# the splatted car's camera: a 3DGS scene brings its own coordinate convention, and this group is the one
# GaussianSplats3D's demo page (demo/truck.html) uses for this scene — the viewer's defaults leave it askew.
TRUCK_CAMERA = {
    "up": [0, -1, -0.17],
    "position": [-5, -1, -1],
    "lookAt": [-1.72477, 0.05395, -0.00147],
}

# the trend spec (the first 15 days, 09-03 … 09-17): G2's own grammar, data and encoding, no drawing instructions.
# `data` is then appended to 30 days by TAIL_DAYS — the whole spec is set again and the chart grows one notch.
TREND: dict[str, Any] = {
    'type': 'line',
    'data': [
        {'day': '09-03', 'avg': 4.07, 'dept': 'R&D'},
        {'day': '09-03', 'avg': 3.95, 'dept': 'Marketing'},
        {'day': '09-03', 'avg': 4.18, 'dept': 'Operations'},
        {'day': '09-04', 'avg': 3.86, 'dept': 'R&D'},
        {'day': '09-04', 'avg': 3.97, 'dept': 'Marketing'},
        {'day': '09-04', 'avg': 4.11, 'dept': 'Operations'},
        {'day': '09-05', 'avg': 3.64, 'dept': 'R&D'},
        {'day': '09-05', 'avg': 3.97, 'dept': 'Marketing'},
        {'day': '09-05', 'avg': 3.88, 'dept': 'Operations'},
        {'day': '09-06', 'avg': 3.61, 'dept': 'R&D'},
        {'day': '09-06', 'avg': 3.75, 'dept': 'Marketing'},
        {'day': '09-06', 'avg': 3.67, 'dept': 'Operations'},
        {'day': '09-07', 'avg': 3.57, 'dept': 'R&D'},
        {'day': '09-07', 'avg': 3.92, 'dept': 'Marketing'},
        {'day': '09-07', 'avg': 3.48, 'dept': 'Operations'},
        {'day': '09-08', 'avg': 3.43, 'dept': 'R&D'},
        {'day': '09-08', 'avg': 3.98, 'dept': 'Marketing'},
        {'day': '09-08', 'avg': 3.71, 'dept': 'Operations'},
        {'day': '09-09', 'avg': 3.47, 'dept': 'R&D'},
        {'day': '09-09', 'avg': 3.93, 'dept': 'Marketing'},
        {'day': '09-09', 'avg': 3.95, 'dept': 'Operations'},
        {'day': '09-10', 'avg': 3.24, 'dept': 'R&D'},
        {'day': '09-10', 'avg': 4.11, 'dept': 'Marketing'},
        {'day': '09-10', 'avg': 3.84, 'dept': 'Operations'},
        {'day': '09-11', 'avg': 3.2, 'dept': 'R&D'},
        {'day': '09-11', 'avg': 3.92, 'dept': 'Marketing'},
        {'day': '09-11', 'avg': 3.75, 'dept': 'Operations'},
        {'day': '09-12', 'avg': 3.36, 'dept': 'R&D'},
        {'day': '09-12', 'avg': 3.76, 'dept': 'Marketing'},
        {'day': '09-12', 'avg': 3.79, 'dept': 'Operations'},
        {'day': '09-13', 'avg': 3.43, 'dept': 'R&D'},
        {'day': '09-13', 'avg': 3.69, 'dept': 'Marketing'},
        {'day': '09-13', 'avg': 3.81, 'dept': 'Operations'},
        {'day': '09-14', 'avg': 3.21, 'dept': 'R&D'},
        {'day': '09-14', 'avg': 3.47, 'dept': 'Marketing'},
        {'day': '09-14', 'avg': 3.66, 'dept': 'Operations'},
        {'day': '09-15', 'avg': 3.3, 'dept': 'R&D'},
        {'day': '09-15', 'avg': 3.44, 'dept': 'Marketing'},
        {'day': '09-15', 'avg': 3.57, 'dept': 'Operations'},
        {'day': '09-16', 'avg': 3.34, 'dept': 'R&D'},
        {'day': '09-16', 'avg': 3.41, 'dept': 'Marketing'},
        {'day': '09-16', 'avg': 3.47, 'dept': 'Operations'},
        {'day': '09-17', 'avg': 3.49, 'dept': 'R&D'},
        {'day': '09-17', 'avg': 3.51, 'dept': 'Marketing'},
        {'day': '09-17', 'avg': 3.34, 'dept': 'Operations'},
    ],
    'encode': {'x': 'day', 'y': 'avg', 'color': 'dept', 'shape': 'smooth'},
    'style': {'lineWidth': 2},
    'scale': {'y': {'domain': [3.0, 5.0]}},
    'interaction': {'tooltip': {'crosshairs': True}},
}

# three radars: one closed polygon per person in a department, the axis count set by the data's `dim` values (5 / 6 / 7);
# there is no "number of dimensions" knob in the spec — colour = name.
RADARS: dict[str, Any] = {
    'radar_rd': {
        'type': 'view',
        'data': [
            {'dept': 'R&D', 'name': 'Zhang Wei', 'dim': 'Attendance', 'value': 4.4},
            {'dept': 'R&D', 'name': 'Zhang Wei', 'dim': 'Quality', 'value': 4.1},
            {'dept': 'R&D', 'name': 'Zhang Wei', 'dim': 'Workload', 'value': 3.6},
            {'dept': 'R&D', 'name': 'Zhang Wei', 'dim': 'Collaboration', 'value': 4.7},
            {'dept': 'R&D', 'name': 'Zhang Wei', 'dim': 'Learning', 'value': 4.0},
            {'dept': 'R&D', 'name': 'Li Na', 'dim': 'Attendance', 'value': 3.9},
            {'dept': 'R&D', 'name': 'Li Na', 'dim': 'Quality', 'value': 4.6},
            {'dept': 'R&D', 'name': 'Li Na', 'dim': 'Workload', 'value': 4.2},
            {'dept': 'R&D', 'name': 'Li Na', 'dim': 'Collaboration', 'value': 3.6},
            {'dept': 'R&D', 'name': 'Li Na', 'dim': 'Learning', 'value': 4.4},
            {'dept': 'R&D', 'name': 'Wang Qiang', 'dim': 'Attendance', 'value': 4.6},
            {'dept': 'R&D', 'name': 'Wang Qiang', 'dim': 'Quality', 'value': 4.9},
            {'dept': 'R&D', 'name': 'Wang Qiang', 'dim': 'Workload', 'value': 4.5},
            {'dept': 'R&D', 'name': 'Wang Qiang', 'dim': 'Collaboration', 'value': 3.2},
            {'dept': 'R&D', 'name': 'Wang Qiang', 'dim': 'Learning', 'value': 3.6},
            {'dept': 'R&D', 'name': 'Liu Yang', 'dim': 'Attendance', 'value': 3.6},
            {'dept': 'R&D', 'name': 'Liu Yang', 'dim': 'Quality', 'value': 3.8},
            {'dept': 'R&D', 'name': 'Liu Yang', 'dim': 'Workload', 'value': 4.8},
            {'dept': 'R&D', 'name': 'Liu Yang', 'dim': 'Collaboration', 'value': 4.0},
            {'dept': 'R&D', 'name': 'Liu Yang', 'dim': 'Learning', 'value': 4.6},
        ],
        'coordinate': {'type': 'polar'},
        'scale': {'x': {'padding': 0.5, 'align': 0}, 'y': {'domain': [0, 5], 'tickCount': 5}},
        'axis': {'x': {'grid': True, 'title': None}, 'y': False},
        'legend': {'color': {'layout': {'justContent': True}}},
        'children': [
            {
                'type': 'area',
                'encode': {'x': 'dim', 'y': 'value', 'color': 'name'},
                'style': {'fillOpacity': 0.15, 'lineWidth': 0},
            },
            {
                'type': 'line',
                'encode': {'x': 'dim', 'y': 'value', 'color': 'name'},
                'style': {'lineWidth': 2, 'join': 'round', 'cap': 'round'},
            },
        ],
        'interaction': {'tooltip': {}},
    },
    'radar_mkt': {
        'type': 'view',
        'data': [
            {'dept': 'Marketing', 'name': 'Chen Jing', 'dim': 'Attendance', 'value': 4.2},
            {'dept': 'Marketing', 'name': 'Chen Jing', 'dim': 'Quality', 'value': 3.7},
            {'dept': 'Marketing', 'name': 'Chen Jing', 'dim': 'Workload', 'value': 4.8},
            {'dept': 'Marketing', 'name': 'Chen Jing', 'dim': 'Collaboration', 'value': 4.5},
            {'dept': 'Marketing', 'name': 'Chen Jing', 'dim': 'Learning', 'value': 3.4},
            {'dept': 'Marketing', 'name': 'Chen Jing', 'dim': 'Innovation', 'value': 3.9},
            {'dept': 'Marketing', 'name': 'Yang Fan', 'dim': 'Attendance', 'value': 4.6},
            {'dept': 'Marketing', 'name': 'Yang Fan', 'dim': 'Quality', 'value': 4.2},
            {'dept': 'Marketing', 'name': 'Yang Fan', 'dim': 'Workload', 'value': 3.8},
            {'dept': 'Marketing', 'name': 'Yang Fan', 'dim': 'Collaboration', 'value': 4.1},
            {'dept': 'Marketing', 'name': 'Yang Fan', 'dim': 'Learning', 'value': 4.5},
            {'dept': 'Marketing', 'name': 'Yang Fan', 'dim': 'Innovation', 'value': 4.9},
            {'dept': 'Marketing', 'name': 'Zhao Lei', 'dim': 'Attendance', 'value': 3.8},
            {'dept': 'Marketing', 'name': 'Zhao Lei', 'dim': 'Quality', 'value': 4.0},
            {'dept': 'Marketing', 'name': 'Zhao Lei', 'dim': 'Workload', 'value': 4.2},
            {'dept': 'Marketing', 'name': 'Zhao Lei', 'dim': 'Collaboration', 'value': 4.8},
            {'dept': 'Marketing', 'name': 'Zhao Lei', 'dim': 'Learning', 'value': 3.2},
            {'dept': 'Marketing', 'name': 'Zhao Lei', 'dim': 'Innovation', 'value': 3.6},
        ],
        'coordinate': {'type': 'polar'},
        'scale': {'x': {'padding': 0.5, 'align': 0}, 'y': {'domain': [0, 5], 'tickCount': 5}},
        'axis': {'x': {'grid': True, 'title': None}, 'y': False},
        'legend': {'color': {'layout': {'justContent': True}}},
        'children': [
            {
                'type': 'area',
                'encode': {'x': 'dim', 'y': 'value', 'color': 'name'},
                'style': {'fillOpacity': 0.15, 'lineWidth': 0},
            },
            {
                'type': 'line',
                'encode': {'x': 'dim', 'y': 'value', 'color': 'name'},
                'style': {'lineWidth': 2, 'join': 'round', 'cap': 'round'},
            },
        ],
        'interaction': {'tooltip': {}},
    },
    'radar_ops': {
        'type': 'view',
        'data': [
            {'dept': 'Operations', 'name': 'Sun Yue', 'dim': 'Attendance', 'value': 4.8},
            {'dept': 'Operations', 'name': 'Sun Yue', 'dim': 'Quality', 'value': 4.1},
            {'dept': 'Operations', 'name': 'Sun Yue', 'dim': 'Workload', 'value': 4.5},
            {'dept': 'Operations', 'name': 'Sun Yue', 'dim': 'Collaboration', 'value': 4.3},
            {'dept': 'Operations', 'name': 'Sun Yue', 'dim': 'Learning', 'value': 3.5},
            {'dept': 'Operations', 'name': 'Sun Yue', 'dim': 'Innovation', 'value': 3.2},
            {'dept': 'Operations', 'name': 'Sun Yue', 'dim': 'Customer focus', 'value': 4.0},
            {'dept': 'Operations', 'name': 'Zhou Jun', 'dim': 'Attendance', 'value': 5.0},
            {'dept': 'Operations', 'name': 'Zhou Jun', 'dim': 'Quality', 'value': 3.9},
            {'dept': 'Operations', 'name': 'Zhou Jun', 'dim': 'Workload', 'value': 4.4},
            {'dept': 'Operations', 'name': 'Zhou Jun', 'dim': 'Collaboration', 'value': 4.0},
            {'dept': 'Operations', 'name': 'Zhou Jun', 'dim': 'Learning', 'value': 3.7},
            {'dept': 'Operations', 'name': 'Zhou Jun', 'dim': 'Innovation', 'value': 3.4},
            {'dept': 'Operations', 'name': 'Zhou Jun', 'dim': 'Customer focus', 'value': 3.8},
            {'dept': 'Operations', 'name': 'Wu Min', 'dim': 'Attendance', 'value': 4.1},
            {'dept': 'Operations', 'name': 'Wu Min', 'dim': 'Quality', 'value': 4.3},
            {'dept': 'Operations', 'name': 'Wu Min', 'dim': 'Workload', 'value': 4.6},
            {'dept': 'Operations', 'name': 'Wu Min', 'dim': 'Collaboration', 'value': 4.9},
            {'dept': 'Operations', 'name': 'Wu Min', 'dim': 'Learning', 'value': 4.0},
            {'dept': 'Operations', 'name': 'Wu Min', 'dim': 'Innovation', 'value': 3.6},
            {'dept': 'Operations', 'name': 'Wu Min', 'dim': 'Customer focus', 'value': 4.5},
            {'dept': 'Operations', 'name': 'Zheng Hua', 'dim': 'Attendance', 'value': 4.5},
            {'dept': 'Operations', 'name': 'Zheng Hua', 'dim': 'Quality', 'value': 4.0},
            {'dept': 'Operations', 'name': 'Zheng Hua', 'dim': 'Workload', 'value': 4.2},
            {'dept': 'Operations', 'name': 'Zheng Hua', 'dim': 'Collaboration', 'value': 4.1},
            {'dept': 'Operations', 'name': 'Zheng Hua', 'dim': 'Learning', 'value': 3.8},
            {'dept': 'Operations', 'name': 'Zheng Hua', 'dim': 'Innovation', 'value': 3.5},
            {'dept': 'Operations', 'name': 'Zheng Hua', 'dim': 'Customer focus', 'value': 3.9},
        ],
        'coordinate': {'type': 'polar'},
        'scale': {'x': {'padding': 0.5, 'align': 0}, 'y': {'domain': [0, 5], 'tickCount': 5}},
        'axis': {'x': {'grid': True, 'title': None}, 'y': False},
        'legend': {'color': {'layout': {'justContent': True}}},
        'children': [
            {
                'type': 'area',
                'encode': {'x': 'dim', 'y': 'value', 'color': 'name'},
                'style': {'fillOpacity': 0.15, 'lineWidth': 0},
            },
            {
                'type': 'line',
                'encode': {'x': 'dim', 'y': 'value', 'color': 'name'},
                'style': {'lineWidth': 2, 'join': 'round', 'cap': 'round'},
            },
        ],
        'interaction': {'tooltip': {}},
    },
}

# the review table's rows: key / field type / initial value / name / dept / daily avg / note. One of each field
# kind (number / bool / text) — the initial value is what that cell shows, the type is how the reader changes it.
REVIEW: tuple[tuple[str, str, Any, str, str, str, str], ...] = [
    ('zw', 'number', 4.13, 'Zhang Wei', 'R&D', '4.13', 'falls in the second half'),
    ('cj', 'bool', False, 'Chen Jing', 'Marketing', '4.24', 'most volatile'),
    ('sy', 'text', 'reviewed', 'Sun Yue', 'Operations', '4.28', 'ends high'),
]

# the graph on the left: this system itself. The dots are crates / components / external modules, the lines are
# "who renders whom, who mounts whom"; `weight` sets a dot's size and `strength` an edge's thickness. 33 dots / 42 lines —
# small graphs all clump, and this page is exactly not after a clump.
GRAPH_NODES = [
    {'id': 'accrete', 'name': 'accrete', 'kind': 'crate', 'weight': 9},
    {'id': 'ui_leptos', 'name': 'ui_leptos', 'kind': 'crate', 'weight': 8},
    {'id': 'stage', 'name': 'stage', 'kind': 'crate', 'weight': 6},
    {'id': 'content', 'name': 'content', 'kind': 'crate', 'weight': 7},
    {'id': 'transport', 'name': 'transport', 'kind': 'crate', 'weight': 5},
    {'id': 'transport_ws', 'name': 'transport_ws', 'kind': 'crate', 'weight': 4},
    {'id': 'forcegraph', 'name': 'forcegraph', 'kind': 'crate', 'weight': 7},
    {'id': 'ui_assets', 'name': 'ui_assets', 'kind': 'crate', 'weight': 4},
    {'id': 'accrete_macro', 'name': 'accrete_macro', 'kind': 'crate', 'weight': 3},
    {'id': 'ui_leptos_macro', 'name': 'ui_leptos_macro', 'kind': 'crate', 'weight': 3},
    {'id': 'fluxen', 'name': 'fluxen', 'kind': 'crate', 'weight': 6},
    {'id': 'frame', 'name': 'frame', 'kind': 'component', 'weight': 7},
    {'id': 'canvas', 'name': 'canvas', 'kind': 'component', 'weight': 7},
    {'id': 'rack', 'name': 'rack', 'kind': 'component', 'weight': 6},
    {'id': 'pages', 'name': 'pages', 'kind': 'component', 'weight': 5},
    {'id': 'form', 'name': 'form', 'kind': 'component', 'weight': 6},
    {'id': 'popup', 'name': 'popup', 'kind': 'component', 'weight': 4},
    {'id': 'layer', 'name': 'layer', 'kind': 'component', 'weight': 5},
    {'id': 'fold', 'name': 'fold', 'kind': 'component', 'weight': 4},
    {'id': 'svg', 'name': 'svg', 'kind': 'component', 'weight': 4},
    {'id': 'portal', 'name': 'portal', 'kind': 'component', 'weight': 3},
    {'id': '3dbrowser', 'name': '3dbrowser', 'kind': 'module', 'weight': 5},
    {'id': 'splatviewer', 'name': 'splatviewer', 'kind': 'module', 'weight': 5},
    {'id': 'g2chart', 'name': 'g2chart', 'kind': 'module', 'weight': 4},
    {'id': 'monaco', 'name': 'monaco', 'kind': 'module', 'weight': 6},
    {'id': 'mermaid', 'name': 'mermaid', 'kind': 'module', 'weight': 3},
    {'id': 'leptos', 'name': 'leptos', 'kind': 'lib', 'weight': 7},
    {'id': 'wasm_bindgen', 'name': 'wasm_bindgen', 'kind': 'lib', 'weight': 6},
    {'id': 'web_sys', 'name': 'web_sys', 'kind': 'lib', 'weight': 6},
    {'id': 'serde', 'name': 'serde', 'kind': 'lib', 'weight': 5},
    {'id': 'tokio', 'name': 'tokio', 'kind': 'lib', 'weight': 4},
    {'id': 'binaryen', 'name': 'binaryen', 'kind': 'tool', 'weight': 3},
    {'id': 'trunk', 'name': 'trunk', 'kind': 'tool', 'weight': 3},
]

GRAPH_LINKS = [
    {'source': 'ui_leptos', 'target': 'accrete', 'kind': 'renders', 'strength': 5},
    {'source': 'ui_leptos', 'target': 'ui_leptos_macro', 'kind': 'generates', 'strength': 3},
    {'source': 'accrete', 'target': 'accrete_macro', 'kind': 'generates', 'strength': 3},
    {'source': 'ui_leptos', 'target': 'ui_assets', 'kind': 'loads', 'strength': 3},
    {'source': 'ui_leptos', 'target': 'forcegraph', 'kind': 'mounts', 'strength': 4},
    {'source': 'forcegraph', 'target': 'accrete', 'kind': 'node', 'strength': 4},
    {'source': 'stage', 'target': 'content', 'kind': 'encodes', 'strength': 5},
    {'source': 'stage', 'target': 'ui_leptos', 'kind': 'serves', 'strength': 4},
    {'source': 'stage', 'target': 'transport', 'kind': 'bridges', 'strength': 3},
    {'source': 'transport', 'target': 'transport_ws', 'kind': 'extends', 'strength': 3},
    {'source': 'transport', 'target': 'content', 'kind': 'carries', 'strength': 3},
    {'source': 'content', 'target': 'serde', 'kind': 'derives', 'strength': 3},
    {'source': 'transport', 'target': 'serde', 'kind': 'derives', 'strength': 2},
    {'source': 'transport_ws', 'target': 'tokio', 'kind': 'runs-on', 'strength': 3},
    {'source': 'fluxen', 'target': 'stage', 'kind': 'starts', 'strength': 4},
    {'source': 'fluxen', 'target': 'transport_ws', 'kind': 'starts', 'strength': 3},
    {'source': 'frame', 'target': 'accrete', 'kind': 'node', 'strength': 5},
    {'source': 'frame', 'target': 'ui_leptos', 'kind': 'mounted-by', 'strength': 3},
    {'source': 'canvas', 'target': 'ui_leptos', 'kind': 'mounted-by', 'strength': 3},
    {'source': 'rack', 'target': 'ui_leptos', 'kind': 'mounted-by', 'strength': 3},
    {'source': 'rack', 'target': 'pages', 'kind': 'rows', 'strength': 3},
    {'source': 'pages', 'target': 'frame', 'kind': 'arranges', 'strength': 2},
    {'source': 'form', 'target': 'accrete', 'kind': 'node', 'strength': 3},
    {'source': 'form', 'target': 'ui_leptos', 'kind': 'mounted-by', 'strength': 2},
    {'source': 'popup', 'target': 'ui_leptos', 'kind': 'mounted-by', 'strength': 2},
    {'source': 'layer', 'target': 'ui_leptos', 'kind': 'mounted-by', 'strength': 2},
    {'source': 'fold', 'target': 'layer', 'kind': 'stacks-in', 'strength': 2},
    {'source': 'svg', 'target': 'ui_leptos', 'kind': 'mounted-by', 'strength': 2},
    {'source': 'portal', 'target': 'layer', 'kind': 'escapes-to', 'strength': 2},
    {'source': '3dbrowser', 'target': 'canvas', 'kind': 'mounts', 'strength': 4},
    {'source': 'splatviewer', 'target': 'canvas', 'kind': 'mounts', 'strength': 4},
    {'source': 'g2chart', 'target': 'canvas', 'kind': 'mounts', 'strength': 3},
    {'source': 'monaco', 'target': 'canvas', 'kind': 'mounts', 'strength': 5},
    {'source': 'mermaid', 'target': 'canvas', 'kind': 'mounts', 'strength': 3},
    {'source': 'leptos', 'target': 'wasm_bindgen', 'kind': 'compiles-to', 'strength': 4},
    {'source': 'web_sys', 'target': 'wasm_bindgen', 'kind': 'binds', 'strength': 4},
    {'source': 'ui_leptos', 'target': 'leptos', 'kind': 'built-with', 'strength': 5},
    {'source': 'forcegraph', 'target': 'web_sys', 'kind': 'draws-with', 'strength': 5},
    {'source': 'forcegraph', 'target': 'wasm_bindgen', 'kind': 'binds', 'strength': 3},
    {'source': 'trunk', 'target': 'ui_leptos', 'kind': 'builds', 'strength': 3},
    {'source': 'trunk', 'target': 'binaryen', 'kind': 'shrinks-with', 'strength': 2},
    {'source': 'binaryen', 'target': 'wasm_bindgen', 'kind': 'optimises', 'strength': 2},
]

# what stands at the first frame (the crate layer and the shell that renders it); the rest arrives with the passage
# that names it — an edge appears only once both of its ends are on stage.
GRAPH_SEED = [
    'accrete',
    'accrete_macro',
    'canvas',
    'content',
    'fluxen',
    'forcegraph',
    'form',
    'frame',
    'layer',
    'leptos',
    'pages',
    'rack',
    'serde',
    'stage',
    'transport',
    'transport_ws',
    'ui_assets',
    'ui_leptos',
    'ui_leptos_macro',
    'wasm_bindgen',
    'web_sys',
]

# (the passage's label, the node ids that arrive with it) — the labels are the lines in `BEATS`.
GRAPH_REVEAL = [
    ('analytics intro', ('g2chart', 'fold')),
    ('charts arrive', ('svg', 'mermaid')),
    ('review table', ('popup', 'portal')),
    ('splatted car', ('3dbrowser', 'splatviewer')),
    ('shoe mesh', ('monaco',)),
    ('code editor', ('trunk', 'binaryen', 'tokio')),
    ('graph passage', ()),
]


def graph_payload(revealed: set[str] | frozenset[str]) -> dict[str, Any]:
    """Cumulative snapshot for the ids on screen: a link needs both of its ends.

    Cumulative, not a per-node patch, because one write is one physics push — the component diffs
    by node id, so re-sending what is already there is a no-op and an append never re-frames the
    camera.
    """
    nodes = [node for node in GRAPH_NODES if node["id"] in revealed]
    links = [link for link in GRAPH_LINKS if link["source"] in revealed and link["target"] in revealed]
    return {"nodes": nodes, "links": links, "focus": None}


# the eleven beats of playback: the name is the status line the reader sees, and the key into `GRAPH_REVEAL`.
BEATS: tuple[str, ...] = (
    "message in",
    "analytics intro",
    "charts arrive",
    "thirty days",
    "summary",
    "review table",
    "splatted car",
    "shoe mesh",
    "code editor",
    "graph passage",
    "focus",
)
