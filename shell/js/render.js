// Reflux shell — component dispatch, local state, and the two things a binding reads.
//
// One implementation per entry in the generated component table, dispatched by a switch over
// `type` (a table in code, not a runtime registry). Three rules shape every implementation:
//
// 1. Read each field you draw, inside the effect that draws it. A store write only notifies
//    the expressions that read the written path — reading a parent object never fires (T2's
//    gate proved that), so a component that reads `node()` and paints from it is static.
// 2. `bind.source` names the slot the component watches: a leaf paints it as its primary
//    value, a value-carrying input uses it as its value, a container mounts it as children.
//    The attr the node was built with is the fallback until the slot is written.
// 3. Local state (an input buffer, whether a panel is open) lives here, is readable by the
//    delegate (`el.__rx.locals`), and never goes up unless the node's `bind.payload` asks
//    for it. A store write must not clobber what the user is typing.

import { createEffect, createSignal, onCleanup } from "solid-js";
import { COMPONENTS } from "./components.generated.js";

// Nothing here maps a variant to a style: the stylesheet owns the scale (a variant is a
// data attribute, a datum is a custom property) — the shell never writes a class string.

function make(tag, cls) {
  const el = document.createElement(tag);
  el.className = cls;
  return el;
}

// Attribute readers: each returns an effect that paints exactly the fields it reads.
function attr(nodeA, name, apply) {
  createEffect(() => {
    const node = nodeA();
    if (node) apply(node.attrs?.[name], node);
  });
}

// The primary value a component paints: the slot named by `source` once the producer has
// written one that fits the attr it replaces, else the attr itself. Type-matched on purpose —
// a node parked in a text slot paints the fallback rather than "[object Object]".
function slotted(nodeA, ctx, name, apply) {
  createEffect(() => {
    const node = nodeA();
    if (!node) return;
    const built = node.attrs?.[name];
    const source = node.bind?.source;
    if (source === undefined) return apply(built, node);
    const watched = ctx.readSlot(source);
    apply(typeof watched === typeof built && watched !== undefined ? watched : built, node);
  });
}

// The children a node mounts: its own `children`, or the slot its `source` names when the
// producer wrote structure there (a list slot: an array of rows; a fragment: one node).
// A value a component uses as its data (a select's) simply falls through to `children`.
function nodeChildren(nodeA, ctx) {
  const node = nodeA();
  if (!node) return [];
  const source = node.bind?.source;
  if (source !== undefined) {
    const watched = ctx.readSlot(source);
    if (Array.isArray(watched)) return watched;
    if (watched && typeof watched === "object" && typeof watched.type === "string") {
      return [watched];
    }
  }
  return node.children ?? [];
}

// A form's `fields` local state: every descendant that declares a `source`, keyed by it —
// the slot name is the field's address, so one submit carries them all at once.
function collectFields(host) {
  const out = {};
  for (const el of host.querySelectorAll("*")) {
    const handle = el.__rx;
    if (!handle) continue;
    const source = handle.node()?.bind?.source;
    if (source === undefined) continue;
    const locals = handle.locals(el);
    if ("value" in locals) out[source] = locals.value;
    else if ("checked" in locals) out[source] = locals.checked;
  }
  return out;
}

// Each component's local state, read off the DOM at the moment the delegate asks. Where the
// user's editing buffer lives is a DOM fact, so the buffer IS the value a payload carries.
const LOCALS = {
  input: (el) => ({ value: el.value, focus: document.activeElement === el }),
  textarea: (el) => ({ value: el.value, focus: document.activeElement === el }),
  select: (el) => ({ value: el.value }),
  checkbox: (el) => ({ checked: el.querySelector("input").checked }),
  switch: (el) => ({ checked: el.querySelector("input").checked }),
  rack: (el) => ({ scroll: el.scrollTop }),
  form: (el) => ({ fields: collectFields(el) }),
};

/**
 * Reconcile the children `childrenA` reports into `host`. Rows carrying an `id` keep their DOM
 * node (and therefore their local state) across inserts; positional rows follow their index and
 * lose it on reorder — the documented consequence of not carrying a key, not an accident.
 */
function mountChildren(host, childrenA, renderChild) {
  let entries = []; // { key, type, el, index, id, accessor }
  createEffect(() => {
    const kids = childrenA() ?? [];
    const next = [];
    const keep = new Set();
    for (let i = 0; i < kids.length; i++) {
      const kid = kids[i];
      if (!kid) continue;
      const key = typeof kid.id === "string" ? `id:${kid.id}` : `at:${i}`;
      let entry = entries.find((e) => e.key === key && e.type === kid.type);
      if (!entry) {
        entry = { key, type: kid.type, id: kid.id ?? null, index: i, el: null, accessor: null };
        entry.accessor = () => {
          const ns = childrenA() ?? [];
          return entry.id !== null ? ns.find((n) => n && n.id === entry.id) : ns[entry.index];
        };
        entry.el = renderChild(entry.accessor);
      }
      entry.index = i;
      keep.add(entry);
      next.push(entry);
    }
    for (const entry of entries) {
      if (!keep.has(entry)) entry.el.remove();
    }
    next.forEach((entry, i) => {
      if (host.children[i] !== entry.el) host.insertBefore(entry.el, host.children[i] ?? null);
    });
    entries = next;
  });
}

/**
 * Containers mount their children into a body element so component chrome (a card's title, a
 * field's label, a form's submit) keeps its place around them; `.rx-body` is
 * `display: contents`, so the wrapper costs no layout. `bodyIsHost` is for elements that
 * cannot hold a wrapper at all — a select only takes options.
 */
function container(nodeA, opts, ctx) {
  const { tag = "div", cls = "", chrome = null, bodyIsHost = false } = opts;
  const host = make(tag, cls);
  const body = bodyIsHost ? host : make("div", "rx-body");
  if (!bodyIsHost) host.append(body);
  if (chrome) chrome(host, body, nodeA);
  mountChildren(body, () => nodeChildren(nodeA, ctx), (childA) => renderNode(childA, ctx));
  return host;
}

function textish(nodeA, ctx, tag, cls) {
  const el = make(tag, cls);
  slotted(nodeA, ctx, "value", (v) => {
    el.textContent = v;
  });
  return el;
}

// --- the implementations ----------------------------------------------------------------

const IMPL = {
  // containers
  stack(nodeA, ctx) {
    return container(
      nodeA,
      {
        cls: "rx-stack",
        chrome: (host) => {
          createEffect(() => {
            const a = nodeA()?.attrs ?? {};
            host.dataset.direction = a.direction;
            host.dataset.align = a.align;
            host.dataset.gap = a.gap;
          });
        },
      },
      ctx,
    );
  },
  row(nodeA, ctx) {
    return container(
      nodeA,
      {
        cls: "rx-row",
        chrome: (host) => {
          createEffect(() => {
            const a = nodeA()?.attrs ?? {};
            host.dataset.align = a.align;
            host.dataset.wrap = a.wrap;
            host.dataset.gap = a.gap;
          });
        },
      },
      ctx,
    );
  },
  card(nodeA, ctx) {
    return container(
      nodeA,
      {
        tag: "section",
        cls: "rx-card",
        chrome: (host, body, n) => {
          const title = make("h2", "rx-card__title");
          host.insertBefore(title, body);
          attr(n, "title", (v) => {
            title.textContent = v ?? "";
            title.hidden = !v;
          });
          attr(n, "tone", (v) => {
            host.dataset.tone = v;
          });
        },
      },
      ctx,
    );
  },
  rack(nodeA, ctx) {
    return container(
      nodeA,
      {
        cls: "rx-rack",
        chrome: (host, body, n) => {
          // the empty state is the rack's own furniture, so it sits after the body and the
          // rows keep the place the spec gives them
          const empty = make("p", "rx-rack__empty");
          host.append(empty);
          attr(n, "density", (v) => {
            host.dataset.density = v;
          });
          createEffect(() => {
            const attrs = n()?.attrs ?? {};
            const rows = nodeChildren(n, ctx).filter(Boolean);
            empty.textContent = attrs.empty_text ?? "";
            empty.hidden = rows.length > 0 || !attrs.empty_text;
            // `follow: end` pins the view to the newest row — a no-op unless the rack scrolls
            if (attrs.follow === "end" && rows.length > 0) host.scrollTop = host.scrollHeight;
          });
        },
      },
      ctx,
    );
  },
  field(nodeA, ctx) {
    return container(
      nodeA,
      {
        cls: "rx-field",
        chrome: (host, body, n) => {
          const label = make("label", "rx-field__label");
          const hint = make("span", "rx-field__hint");
          host.insertBefore(label, body);
          host.insertBefore(hint, body);
          attr(n, "label", (v) => {
            label.textContent = v ?? "";
          });
          attr(n, "hint", (v) => {
            hint.textContent = v ?? "";
            hint.hidden = !v;
          });
          attr(n, "required", (v) => {
            host.dataset.required = String(Boolean(v));
          });
        },
      },
      ctx,
    );
  },
  form(nodeA, ctx) {
    return container(
      nodeA,
      {
        tag: "form",
        cls: "rx-form",
        chrome: (host, body, n) => {
          const submit = make("button", "rx-button");
          submit.type = "submit";
          submit.dataset.variant = "primary";
          body.after(submit);
          attr(n, "submit_label", (v) => {
            submit.textContent = v ?? "";
          });
          attr(n, "disabled", (v) => {
            submit.disabled = Boolean(v);
          });
        },
      },
      ctx,
    );
  },

  // inputs — each keeps its own buffer; the store is never written from here
  input(nodeA, ctx) {
    const el = make("input", "rx-input");
    const [typed, setTyped] = createSignal(null); // null = not editing, the store owns the field
    attr(nodeA, "kind", (v) => {
      el.type = v;
    });
    attr(nodeA, "placeholder", (v) => {
      el.placeholder = v ?? "";
    });
    attr(nodeA, "disabled", (v) => {
      el.disabled = Boolean(v);
    });
    createEffect(() => {
      const source = nodeA()?.bind?.source;
      if (!source) return;
      const value = ctx.readSlot(source); // one slot read → only inputs watching it re-run
      if (typed() === null && typeof value === "string") el.value = value;
    });
    el.addEventListener("input", () => setTyped(el.value));
    el.addEventListener("blur", () => setTyped(null));
    return el;
  },
  textarea(nodeA, ctx) {
    const el = make("textarea", "rx-textarea");
    const [typed, setTyped] = createSignal(null);
    attr(nodeA, "placeholder", (v) => {
      el.placeholder = v ?? "";
    });
    attr(nodeA, "rows", (v) => {
      el.rows = v ?? 4;
    });
    attr(nodeA, "disabled", (v) => {
      el.disabled = Boolean(v);
    });
    createEffect(() => {
      const source = nodeA()?.bind?.source;
      if (!source) return;
      const value = ctx.readSlot(source);
      if (typed() === null && typeof value === "string") el.value = value;
    });
    el.addEventListener("input", () => setTyped(el.value));
    el.addEventListener("blur", () => setTyped(null));
    return el;
  },
  select(nodeA, ctx) {
    return container(
      nodeA,
      {
        tag: "select",
        cls: "rx-select",
        bodyIsHost: true, // a select takes only options — its children go straight in
        chrome: (host, body, n) => {
          attr(n, "disabled", (v) => {
            host.disabled = Boolean(v);
          });
          createEffect(() => {
            const source = n()?.bind?.source;
            if (source === undefined) return;
            const value = ctx.readSlot(source);
            if (typeof value === "string") host.value = value;
          });
        },
      },
      ctx,
    );
  },
  option(nodeA) {
    const el = make("option", "rx-option");
    attr(nodeA, "value", (v) => {
      el.value = v;
    });
    attr(nodeA, "label", (v) => {
      el.textContent = v ?? "";
    });
    attr(nodeA, "disabled", (v) => {
      el.disabled = Boolean(v);
    });
    return el;
  },
  checkbox(nodeA, ctx) {
    const host = make("label", "rx-checkbox");
    const el = make("input", "rx-checkbox__box");
    el.type = "checkbox";
    const caption = make("span", "rx-checkbox__label");
    attr(nodeA, "label", (v) => {
      caption.textContent = v ?? "";
    });
    attr(nodeA, "disabled", (v) => {
      el.disabled = Boolean(v);
    });
    createEffect(() => {
      const source = nodeA()?.bind?.source;
      if (source === undefined) return;
      const value = ctx.readSlot(source);
      if (typeof value === "boolean") el.checked = value;
    });
    host.append(el, caption);
    return host;
  },
  switch(nodeA, ctx) {
    const host = make("label", "rx-switch");
    const el = make("input", "rx-switch__box");
    el.type = "checkbox";
    const knob = make("span", "rx-switch__knob");
    const caption = make("span", "rx-switch__label");
    attr(nodeA, "label", (v) => {
      caption.textContent = v ?? "";
    });
    attr(nodeA, "disabled", (v) => {
      el.disabled = Boolean(v);
    });
    createEffect(() => {
      const source = nodeA()?.bind?.source;
      if (source === undefined) return;
      const value = ctx.readSlot(source);
      if (typeof value === "boolean") el.checked = value;
    });
    host.append(el, knob, caption);
    return host;
  },

  // display
  text(nodeA, ctx) {
    const el = textish(nodeA, ctx, "p", "rx-text");
    attr(nodeA, "tone", (v) => {
      el.dataset.tone = v;
    });
    attr(nodeA, "size", (v) => {
      el.dataset.size = v;
    });
    attr(nodeA, "wrap", (v) => {
      el.dataset.wrap = String(Boolean(v));
    });
    return el;
  },
  heading(nodeA, ctx) {
    const el = textish(nodeA, ctx, "h2", "rx-heading");
    attr(nodeA, "level", (v) => {
      el.dataset.level = String(v);
    });
    return el;
  },
  badge(nodeA, ctx) {
    const el = textish(nodeA, ctx, "span", "rx-badge");
    attr(nodeA, "tone", (v) => {
      el.dataset.tone = v;
    });
    return el;
  },
  code(nodeA, ctx) {
    const el = make("pre", "rx-code");
    const inner = make("code", "rx-code__inner");
    el.append(inner);
    slotted(nodeA, ctx, "value", (v) => {
      inner.textContent = v ?? "";
    });
    attr(nodeA, "lang", (v) => {
      el.dataset.lang = v ?? "";
    });
    return el;
  },
  image(nodeA, ctx) {
    const el = make("img", "rx-image");
    slotted(nodeA, ctx, "src", (v) => {
      el.setAttribute("src", v);
    });
    attr(nodeA, "alt", (v) => {
      el.alt = v ?? "";
    });
    attr(nodeA, "fit", (v) => {
      el.dataset.fit = v;
    });
    return el;
  },

  // nav + feedback
  link(nodeA, ctx) {
    const el = make("a", "rx-link");
    slotted(nodeA, ctx, "href", (v) => {
      el.setAttribute("href", v);
    });
    attr(nodeA, "label", (v) => {
      el.textContent = v ?? "";
    });
    attr(nodeA, "external", (v) => {
      el.dataset.external = String(Boolean(v));
    });
    return el;
  },
  button(nodeA) {
    const el = make("button", "rx-button");
    el.type = "button";
    attr(nodeA, "label", (v) => {
      el.textContent = v ?? "";
    });
    attr(nodeA, "variant", (v) => {
      el.dataset.variant = v;
    });
    attr(nodeA, "size", (v) => {
      el.dataset.size = v;
    });
    attr(nodeA, "disabled", (v) => {
      el.disabled = Boolean(v);
    });
    return el;
  },
  progress(nodeA, ctx) {
    const host = make("div", "rx-progress");
    const bar = make("div", "rx-progress__bar");
    const caption = make("span", "rx-progress__label");
    slotted(nodeA, ctx, "value", (v) => {
      host.dataset.value = String(v ?? 0);
      // a datum, not a variant: it rides a custom property the stylesheet consumes
      host.style.setProperty("--rx-value", `${Math.max(0, Math.min(100, Number(v) || 0))}%`);
    });
    attr(nodeA, "label", (v) => {
      caption.textContent = v ?? "";
    });
    attr(nodeA, "indeterminate", (v) => {
      host.dataset.indeterminate = String(Boolean(v));
    });
    host.append(bar, caption);
    return host;
  },
  empty(nodeA, ctx) {
    const host = make("div", "rx-empty");
    const caption = textish(nodeA, ctx, "p", "rx-empty__text");
    const hint = make("span", "rx-empty__hint");
    attr(nodeA, "hint", (v) => {
      hint.textContent = v ?? "";
      hint.hidden = !v;
    });
    host.append(caption, hint);
    return host;
  },
};

/** The component names this file implements — must equal the spec's list (a wish list is a bug). */
export const implemented = () => Object.keys(IMPL).sort();

function unsupported(nodeA, ctx) {
  const host = make("div", "rx-unsupported");
  const type = nodeA()?.type;
  host.textContent = `unsupported component: ${type}`;
  ctx.count("unsupported");
  return host;
}

/** Render one node (and its subtree) into an element. */
export function renderNode(nodeA, ctx) {
  const type = nodeA()?.type;
  const impl = IMPL[type];
  const el = impl ? impl(nodeA, ctx) : unsupported(nodeA, ctx);
  // The handle the delegate walks to: which node this element hosts, and how to read its local
  // state. Set on the host, so a nested target (a checkbox's inner input) still resolves here.
  el.__rx = { node: nodeA, locals: LOCALS[type] ?? (() => ({})) };
  return el;
}

/** Create the context the components read slots and count through. */
export function createRenderContext(state, counters) {
  return {
    readSlot(name) {
      return state.slots[name];
    },
    count(name) {
      counters[name] = (counters[name] ?? 0) + 1;
    },
  };
}

export { COMPONENTS };