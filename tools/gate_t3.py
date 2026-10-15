#!/usr/bin/env python3
"""T3 gate — component dispatch, local state, and how far an update reaches.

Runs the shell in a real browser and measures the DOM: how many mutations a patch causes,
whether sibling elements survive it, whether a slot write reaches only the component that
reads it, and whether local state survives a store write. Nothing is mocked.

    python3 tools/gate_t3.py

Exit code 0 = gate passed.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cdp import console_errors, report, shell_page  # noqa: E402

SCENARIO = r"""
(async () => {
  const R = window.reflux;
  const app = document.getElementById("app");
  const out = {};
  const settle = (ms = 30) => new Promise((r) => setTimeout(r, ms));

  out.components = R.components;
  out.implemented = R.implemented;

  const tree = {
    type: "stack", id: null,
    attrs: { direction: "column", gap: "md", align: "stretch" },
    bind: {}, children: [
      { type: "card", id: "card-1", attrs: { title: "看板", tone: "plain" }, bind: {}, children: [
        { type: "text", id: "text-1", attrs: { value: "initial", tone: "default", size: "md", wrap: true }, bind: {}, children: [] },
        { type: "input", id: "input-1", attrs: { kind: "text", placeholder: "名字", disabled: false, clearable: false }, bind: { source: "name" }, children: [] },
        { type: "button", id: "button-1", attrs: { label: "do", variant: "primary", size: "md", disabled: false }, bind: { event: "do" }, children: [] },
      ] },
      { type: "rack", id: "rack-1", attrs: { density: "normal", empty_text: "", follow: "none" }, bind: {}, children: [
        { type: "badge", id: "row-1", attrs: { value: "one", tone: "neutral" }, bind: {}, children: [] },
        { type: "badge", id: "row-2", attrs: { value: "two", tone: "neutral" }, bind: {}, children: [] },
      ] },
    ],
  };

  out.created = R.apply({ ev: "draw", ops: [{ op: "create", root: tree }] });
  await settle();
  const card = document.querySelector(".rx-card");
  const input = document.querySelector(".rx-input");
  const button = document.querySelector(".rx-button");
  out.root = !!document.querySelector(".rx-stack");
  out.text_before = document.querySelector(".rx-text")?.textContent ?? null;

  // 1. one text patch: one mutation, no element churn, siblings keep their DOM nodes
  const seen = [];
  const mo = new MutationObserver((recs) => seen.push(...recs));
  mo.observe(app, { subtree: true, childList: true, characterData: true, attributes: true });
  R.apply({ ev: "draw", ops: [{ op: "patch", path: "/tree/children/0/children/0/attrs/value", value: "patched" }] });
  await settle();
  mo.disconnect();
  out.mutation_count = seen.length;
  out.mutation_kinds = seen.map((r) => r.type);
  out.element_churn = seen.some(
    (r) => [...r.addedNodes, ...r.removedNodes].some((n) => n.nodeType === 1),
  );
  out.text_after = document.querySelector(".rx-text")?.textContent ?? null;
  out.identity = {
    card: document.querySelector(".rx-card") === card,
    input: document.querySelector(".rx-input") === input,
    button: document.querySelector(".rx-button") === button,
  };

  // 2. a slot write: zero DOM mutations, and it reaches the one input reading that slot
  const seen2 = [];
  const mo2 = new MutationObserver((recs) => seen2.push(...recs));
  mo2.observe(app, { subtree: true, childList: true, characterData: true, attributes: true });
  R.setSlot("name", "from slot");
  await settle();
  mo2.disconnect();
  out.slot_mutations = seen2.length;
  out.input_after_slot = document.querySelector(".rx-input")?.value ?? null;

  // 3. local state: what the user typed survives a store write
  const el = document.querySelector(".rx-input");
  el.focus();
  el.value = "typed by hand";
  el.dispatchEvent(new Event("input", { bubbles: true }));
  R.setSlot("name", "store changed");
  await settle(20);
  out.typing_kept = el.value;

  // 4. an unknown component refuses the whole frame — the good op in it does not land
  const rejected0 = R.counters.rejected;
  out.bad_component = R.apply({ ev: "draw", ops: [
    { op: "patch", path: "/tree/children/0/attrs/title", value: "nope" },
    { op: "insert", path: "/tree/children", anchor: "end",
      node: { type: "div", id: null, attrs: {}, bind: {}, children: [] } },
  ] });
  await settle(20);
  out.rejected_delta = R.counters.rejected - rejected0;
  out.title_after_bad = document.querySelector(".rx-card__title")?.textContent ?? null;
  out.error_bad_component = R.errors[R.errors.length - 1] ?? null;

  // 5. an out-of-domain attr value refuses the frame too
  const rejected1 = R.counters.rejected;
  out.bad_attr = R.apply({ ev: "draw", ops: [
    { op: "patch", path: "/tree/children/1/children/0/attrs/tone", value: "purple" },
  ] });
  out.rejected_delta2 = R.counters.rejected - rejected1;
  out.error_bad_attr = R.errors[R.errors.length - 1] ?? null;

  // 6. create again: the view is rebuilt, exactly one root remains, nothing unsupported
  R.apply({ ev: "draw", ops: [{ op: "create", root: tree }] });
  await settle();
  out.roots = document.querySelectorAll(".rx-stack").length;
  out.unsupported = R.counters.unsupported;
  out.console_silent = true;
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

        missing = sorted(set(out["components"]) - set(out["implemented"]))
        extra = sorted(set(out["implemented"]) - set(out["components"]))
        check(
            "spec == implementations",
            not missing and not extra,
            f"{len(out['components'])} components, missing={missing} extra={extra}",
        )

        check("create renders the tree", out["root"] and out["text_before"] == "initial",
              f"root={out['root']} text={out['text_before']!r}")
        check("one patch = one mutation, no element churn",
              out["mutation_count"] == 1 and not out["element_churn"] and out["text_after"] == "patched",
              f"mutations={out['mutation_count']} kinds={out['mutation_kinds']} churn={out['element_churn']} text={out['text_after']!r}")
        check("siblings keep their DOM nodes",
              all(out["identity"].values()), f"{out['identity']}")
        check("slot write: zero DOM mutations, one reader updated",
              out["slot_mutations"] == 0 and out["input_after_slot"] == "from slot",
              f"mutations={out['slot_mutations']} value={out['input_after_slot']!r}")
        check("local state survives a store write",
              out["typing_kept"] == "typed by hand", f"value={out['typing_kept']!r}")
        check("unknown component: frame refused whole",
              out["bad_component"] is False and out["rejected_delta"] == 1 and out["title_after_bad"] == "看板",
              f"rejected+{out['rejected_delta']} title={out['title_after_bad']!r}")
        check("bad attr value: frame refused",
              out["bad_attr"] is False and out["rejected_delta2"] == 1,
              f"rejected+{out['rejected_delta2']} err={out['error_bad_attr']!r}")
        check("create again: one root, nothing unsupported",
              out["roots"] == 1 and out["unsupported"] == 0,
              f"roots={out['roots']} unsupported={out['unsupported']}")

        if out["error_bad_component"]:
            print(f"    refusal 1: {out['error_bad_component']}")
        if out["error_bad_attr"]:
            print(f"    refusal 2: {out['error_bad_attr']}")

    return report(checks, gate="T3 GATE")


if __name__ == "__main__":
    sys.exit(main())