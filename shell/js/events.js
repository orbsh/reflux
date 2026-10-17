// Reflux shell — the delegated event path: interaction in, uplink frame out.
//
// One listener per DOM event type in the spec's `fire_events`, mounted at the root, so
// inserting or removing nodes never churns listeners. Two rules decide what happens:
//
// 1. The nearest component that *claims* the event type owns the interaction — claiming is
//    declared in the spec's `fire` table, so a container never steals a child's event.
// 2. A claim without `bind.event` sends nothing: the node said it only watches a slot.
//
// The frame is `{event, id, data}`. `id` is the claiming node's *own* id — a row's identity
// reaches the frame by putting the row's id on that node, never by guessing an ancestor.
// `data` carries exactly the local state the node's `payload` declared, in declaration order:
// the declaration is a contract, not a hint. A declared field the shell cannot read refuses the
// uplink (counted) rather than sending the key missing — the producer could not tell "missing"
// from "this field was never there".

import { COMPONENTS, FIRE_EVENTS } from "./components.generated.js";

export function createDelegate(root, send, onRefuse = () => {}) {
  // Walk up from the target to the nearest host that fires on this DOM event type.
  function claim(target, domEvent) {
    for (let el = target; el && el !== root; el = el.parentElement) {
      const handle = el.__rx;
      if (!handle) continue;
      const node = handle.node();
      const fire = COMPONENTS[node?.type]?.fire ?? [];
      if (fire.includes(domEvent)) return { el, handle, node };
    }
    return null;
  }

  function onEvent(domEvent, event) {
    const hit = claim(event.target, domEvent);
    if (!hit) return;
    // The shell owns the submit: the browser must not navigate on it.
    if (domEvent === "submit") event.preventDefault();
    const name = hit.node.bind?.event;
    if (!name) return;
    const locals = hit.handle.locals(hit.el);
    const data = {};
    for (const key of hit.node.bind.payload ?? []) {
      // `key in locals`, not truthiness: "" and false are values, absence is a defect. The shell
      // also cannot invent it: the declaration is the producer's, the locals are the shell's, and
      // only this point sees both.
      if (!(key in locals)) {
        onRefuse(
          `payload ${JSON.stringify(key)} of ${hit.node.type} ${hit.node.id ?? "(no id)"} ` +
            `cannot be read — uplink refused`,
        );
        return;
      }
      data[key] = locals[key];
    }
    send({ event: name, id: hit.node.id ?? null, data });
  }

  for (const domEvent of FIRE_EVENTS) {
    root.addEventListener(domEvent, (e) => onEvent(domEvent, e));
  }
  return { claim };
}