// Reflux shell — boot.
//
// T0: prove the vendored SolidJS ESM graph, the native import map, the reactive store and
// the hyperscript builder all work with no build step and with no network beyond this origin.
// T2: the interpreter (interp.js) owns the tree and the slots; it is exposed for the dev
// loop and for the gates, which assert on the very store the components will read.

import { createEffect } from "solid-js";
import h from "solid-js/h";
import { render } from "solid-js/web";

import { createInterp } from "./interp.js";

const mount = document.getElementById("app");
const { state, apply, snapshot, counters, setSlot } = createInterp();

render(
  () =>
    h(
      "div",
      { class: "probe" },
      h("span", { class: "dot" }),
      // A dynamic child must be an accessor: without a compiler nothing rewrites
      // `state.slots.boot` into a tracked read (this is the price of the no-build path,
      // and the T0 gate asserts the write really reaches the DOM).
      h("code", null, () => state.slots.boot ?? "…"),
    ),
  mount,
);

// create's optional title is a shell-side DOM fact, so the shell applies it.
createEffect(() => {
  if (state.title) document.title = state.title;
});

window.reflux = { state, apply, snapshot, counters, setSlot, effect: createEffect };
window.__reflux = { booted: true };

// A store write must reach the DOM with no further plumbing: this is the
// fine-grained path the whole design rests on.
setSlot("boot", "reflux shell · boot ok · store live");

mount.dataset.probe = "booted";