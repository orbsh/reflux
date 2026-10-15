#!/usr/bin/env python3
"""T2 gate — the interpreter: four ops, JSON Pointer paths, id anchors, batch atomicity.

Drives the shell in a real browser and runs a scenario inside the page against the very
store the components will read (window.reflux). Nothing is mocked.

    python3 tools/gate_t2.py

Exit code 0 = gate passed.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cdp import console_errors, report, shell_page  # noqa: E402

# One inside-the-page scenario; it returns a plain object the assertions below read.
SCENARIO = r"""
(async () => {
  const R = window.reflux;
  const snap = () => R.snapshot();
  const out = {};

  const tree = {
    type: "stack", id: null,
    attrs: { direction: "column", gap: "md", align: "stretch" },
    bind: {}, children: [
      { type: "text", id: "row-greeting", attrs: { value: "hello" }, bind: { source: "greeting" }, children: [] },
      { type: "input", id: "row-name", attrs: { kind: "text", placeholder: "" }, bind: { source: "name" }, children: [] },
      { type: "button", id: "row-go", attrs: { label: "go" }, bind: { event: "go" }, children: [] },
    ],
  };

  // 1. create: the whole tree plus the browser title
  out.create_ok = R.apply({ ev: "draw", ops: [{ op: "create", root: tree, title: "看板" }] });
  out.title = document.title;
  out.created_children = snap().tree.children.map((n) => n.id);

  // 2. patch a nested value by pointer
  out.patch_ok = R.apply({ ev: "draw", ops: [{ op: "patch", path: "/tree/children/0/attrs/value", value: "你好" }] });
  out.patched = snap().tree.children[0].attrs.value;

  // 3. insert after an id anchor — the anchor is what survives concurrent inserts
  const row = { type: "text", id: "row-extra", attrs: { value: "extra" }, bind: {}, children: [] };
  out.insert_ok = R.apply({ ev: "draw", ops: [{ op: "insert", path: "/tree/children", anchor: { id: "row-greeting" }, node: row }] });
  out.order_after_insert = snap().tree.children.map((n) => n.id);

  // 4. remove by id
  out.remove_ok = R.apply({ ev: "draw", ops: [{ op: "remove", path: "/tree/children", id: "row-extra" }] });
  out.order_after_remove = snap().tree.children.map((n) => n.id);

  // 5. an unresolvable path drops that op and counts it; the rest of the frame applies
  const dropped0 = R.counters.dropped;
  out.frame_with_bad_path = R.apply({ ev: "draw", ops: [
    { op: "patch", path: "/tree/children/99/attrs/value", value: "nope" },
    { op: "patch", path: "/tree/children/1/attrs/placeholder", value: "名字" },
  ] });
  out.dropped_delta = R.counters.dropped - dropped0;
  out.placeholder = snap().tree.children[1].attrs.placeholder;

  // 6. a malformed frame is refused whole: not even its good op lands
  const rejected0 = R.counters.rejected;
  out.bad_frame = R.apply({ ev: "draw", ops: [
    { op: "patch", path: "/tree/children/0/attrs/value", value: "should not land" },
    { op: "frobnicate" },
  ] });
  out.rejected_delta = R.counters.rejected - rejected0;
  out.value_after_bad_frame = snap().tree.children[0].attrs.value;

  // 7. a frame for another category is ignored, never rendered
  const ignored0 = R.counters.ignored;
  out.other_category = R.apply({ ev: "metrics", ops: [{ op: "patch", path: "/tree/children/0/attrs/value", value: "nope" }] });
  out.ignored_delta = R.counters.ignored - ignored0;

  // 8. atomicity: three ops in one frame must look like ONE store update to an observer.
  //    The observer reads exactly the three things those ops write (a deep read is what a
  //    component will do), so an unbatched apply would show three runs.
  let runs = 0;
  R.effect(() => {
    const t = R.state.tree;
    if (t) {
      t.children.length;
      if (t.children[0]) t.children[0].attrs.value;
      if (t.children[1]) t.children[1].attrs.placeholder;
      runs++;
    }
  });
  await new Promise((r) => setTimeout(r, 25));
  runs = 0;
  R.apply({ ev: "draw", ops: [
    { op: "patch", path: "/tree/children/0/attrs/value", value: "a" },
    { op: "patch", path: "/tree/children/1/attrs/placeholder", value: "b" },
    { op: "insert", path: "/tree/children", anchor: "end",
      node: { type: "text", id: "row-last", attrs: { value: "c" }, bind: {}, children: [] } },
  ] });
  await new Promise((r) => setTimeout(r, 40));
  out.effect_runs_for_3_ops = runs;
  out.final_ids = snap().tree.children.map((n) => n.id);

  out.counters = { ...R.counters };
  return out;
})()
"""


def main() -> int:
    checks: list[tuple[str, bool, str]] = []
    with shell_page() as (cdp, base):
        errors = console_errors(cdp)
        checks.append(("zero console errors", not errors, "none" if not errors else str(errors)))

        out = cdp.eval(SCENARIO)
        if not isinstance(out, dict):
            raise RuntimeError(f"the scenario returned {out!r}")

        def check(name: str, ok: bool, evidence: str) -> None:
            checks.append((name, ok, evidence))

        check("create: tree + title", bool(out["create_ok"]) and out["title"] == "看板",
              f"title={out['title']!r} children={out['created_children']}")
        check("patch: pointer into a child", bool(out["patch_ok"]) and out["patched"] == "你好",
              f"value={out['patched']!r}")
        check("insert: after an id anchor",
              bool(out["insert_ok"]) and out["order_after_insert"] == ["row-greeting", "row-extra", "row-name", "row-go"],
              f"order={out['order_after_insert']}")
        check("remove: by row id",
              bool(out["remove_ok"]) and out["order_after_remove"] == ["row-greeting", "row-name", "row-go"],
              f"order={out['order_after_remove']}")
        check("unknown path: op dropped, rest applied",
              out["frame_with_bad_path"] is False and out["dropped_delta"] == 1 and out["placeholder"] == "名字",
              f"dropped+{out['dropped_delta']} placeholder={out['placeholder']!r}")
        check("malformed frame: refused whole",
              out["bad_frame"] is False and out["rejected_delta"] == 1 and out["value_after_bad_frame"] == "你好",
              f"rejected+{out['rejected_delta']} value={out['value_after_bad_frame']!r}")
        check("other category: ignored",
              out["other_category"] is False and out["ignored_delta"] == 1,
              f"ignored+{out['ignored_delta']}")
        check("atomicity: 3 ops, 1 store update", out["effect_runs_for_3_ops"] == 1,
              f"effect runs={out['effect_runs_for_3_ops']} final={out['final_ids']}")
        check("counters account for every frame",
              out["counters"]["rejected"] == 1 and out["counters"]["ignored"] == 1 and out["counters"]["dropped"] == 1,
              f"counters={out['counters']}")

    return report(checks, gate="T2 GATE")


if __name__ == "__main__":
    sys.exit(main())