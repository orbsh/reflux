// Reflux shell — boot.
//
// T0: prove the vendored SolidJS ESM graph, the native import map, the reactive store and the
// hyperscript builder work with no build step and no network beyond this origin.
// T2: the interpreter (interp.js) owns the tree and the slots and validates every frame
// against the generated table.
// T3: the renderer (render.js) dispatches components and keeps local state; the probe stays
// as the view until a tree arrives.
// T4: the delegate (events.js) turns interaction into uplink frames, the channel (channel.js)
// carries them, and the producer's answer comes back through the interpreter.

import { createEffect } from "solid-js";
import h from "solid-js/h";
import { render } from "solid-js/web";

import { openChannel } from "./channel.js";
import { COMPONENTS, FIRE_EVENTS } from "./components.generated.js";
import { createDelegate } from "./events.js";
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

// The shell speaks first (a hello frame), mounts one listener per firing event type, and
// applies whatever the producer sends back. Anything it cannot send is counted, not dropped
// quietly — `notes` is where the reason lands.
const notes = [];
const channel = openChannel({ onFrame: apply, onNote: (message) => notes.push(message) });
const delegate = createDelegate(mount, channel.send);

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
  fireEvents: FIRE_EVENTS,
  send: channel.send,
  channel: channel.counters,
  notes,
  delegate,
};
window.__reflux = { booted: true };

// A store write must reach the DOM with no further plumbing: this is the
// fine-grained path the whole design rests on.
setSlot("boot", "reflux shell · boot ok · store live");

mount.dataset.probe = "booted";