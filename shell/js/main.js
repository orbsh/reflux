// Reflux shell — boot.
//
// T0: prove the vendored SolidJS ESM graph, the native import map, the reactive store and the
// hyperscript builder work with no build step and no network beyond this origin.
// T2: the interpreter (interp.js) owns the tree and the slots and validates every frame
// against the generated table.
// T3: the renderer (render.js) dispatches components and keeps local state; the probe stays
// as the view until a tree arrives.

import { createEffect } from "solid-js";
import h from "solid-js/h";
import { render } from "solid-js/web";

import { COMPONENTS } from "./components.generated.js";
import { createInterp } from "./interp.js";
import { createRenderContext, implemented, renderNode } from "./render.js";

const mount = document.getElementById("app");
const interp = createInterp();
const { state, apply, snapshot, counters, errors, setSlot } = interp;
const ctx = createRenderContext(state, counters);

// A dynamic child must be an accessor: without a compiler nothing rewrites `state.slots.boot`
// into a tracked read (the price of the no-build path — the T0 gate asserts the write lands).
const probeView = () =>
  h(
    "div",
    { class: "probe" },
    h("span", { class: "dot" }),
    h("code", null, () => state.slots.boot ?? "…"),
  );

// Solid's render() evaluates its argument ONCE (`insert(element, code(), ...)` in the
// runtime), so the reactive part must be the function it *returns*: `insert` tracks an
// accessor handed to it, not the value passed through render. Hence the curried form.
// A `create` swaps the tree's identity (the view is rebuilt once); every later op is
// handled inside the components' own effects.
render(() => () => (state.tree ? renderNode(() => state.tree, ctx) : probeView()), mount);

// create's optional title is a shell-side DOM fact, so the shell applies it.
createEffect(() => {
  if (state.title) document.title = state.title;
});

// Exposed for the dev loop and for the gates: they assert on the very store and DOM the
// components use, and `implemented` vs `components` is what keeps the spec honest.
window.reflux = {
  state,
  apply,
  snapshot,
  counters,
  errors,
  setSlot,
  effect: createEffect,
  implemented: implemented(),
  components: Object.keys(COMPONENTS).sort(),
};
window.__reflux = { booted: true };

// A store write must reach the DOM with no further plumbing: this is the
// fine-grained path the whole design rests on.
setSlot("boot", "reflux shell · boot ok · store live");

mount.dataset.probe = "booted";