// Reflux shell — boot.
//
// T0 scope: prove that the vendored SolidJS ESM graph, the native import map, the
// reactive store and the hyperscript builder all work with no build step and with no
// network access beyond this origin. The wire protocol (ops in, events out) lands in T2/T4.

import { createStore } from "solid-js/store";
import h from "solid-js/h";
import { render } from "solid-js/web";

const mount = document.getElementById("app");

// Client-side state: the wire tree plus the slot values components read.
// The shell is the only place that writes it (I4: working state lives here).
const [state, setState] = createStore({ tree: null, slots: {} });

render(
  () =>
    h(
      "div",
      { class: "probe" },
      h("span", { class: "dot" }),
      // A dynamic child must be an accessor: without a compiler nothing rewrites
      // `state.slots.boot` into a tracked read (this is the price of the no-build path,
      // and the gate asserts the write really reaches the DOM).
      h("code", null, () => state.slots.boot ?? "…"),
    ),
  mount,
);

// A store write must reach the DOM with no further plumbing: this is the
// fine-grained path the whole design rests on.
setState("slots", "boot", "reflux shell · boot ok · store live");

mount.dataset.probe = "booted";
window.__reflux = { booted: true };