// Reflux shell — component dispatch and local state.
//
// One implementation per entry in the generated component table, dispatched by a switch over
// `type` (a table in code, not a runtime registry). Two rules shape every implementation:
//
// 1. Read each field you draw, inside the effect that draws it. A store write only notifies
//    the expressions that read the written path — reading a parent object never fires (T2's
//    gate proved that), so a component that reads `node()` and paints from it is static.
// 2. Local state (an input buffer, whether a panel is open) lives here and never goes up
//    unless the node's `bind.payload` asks for it. A store write must not clobber what the
//    user is typing.

import { createEffect, createSignal, onCleanup } from "solid-js";
import { COMPONENTS } from "./components.generated.js";

const GAP = { none: "0", sm: "0.25rem", md: "0.5rem", lg: "1rem" };
const ALIGN = {
  start: "flex-start",
  center: "center",
  end: "flex-end",
  stretch: "stretch",
  baseline: "baseline",
};

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

/**
 * Reconcile `node`'s children into `host`. Rows carrying an `id` keep their DOM node (and
 * therefore their local state) across inserts; positional rows follow their index and lose
 * it on reorder — the documented consequence of not carrying a key, not an accident.
 */
function mountChildren(host, nodeA, renderChild) {
  let entries = []; // { key, type, el, index, id, accessor }
  createEffect(() => {
    const kids = nodeA()?.children ?? [];
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
          const ns = nodeA()?.children ?? [];
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
  mountChildren(body, nodeA, (childA) => renderNode(childA, ctx));
  return host;
}

function textish(nodeA, tag, cls) {
  const el = make(tag, cls);
  attr(nodeA, "value", (v) => {
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
            host.style.gap = GAP[a.gap] ?? GAP.md;
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
            host.style.gap = GAP[a.gap] ?? GAP.md;
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
          attr(n, "density", (v) => {
            host.dataset.density = v;
          });
          attr(n, "empty_text", (v) => {
            host.dataset.emptyText = v ?? "";
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
  text(nodeA) {
    const el = textish(nodeA, "p", "rx-text");
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
  heading(nodeA) {
    const el = textish(nodeA, "h2", "rx-heading");
    attr(nodeA, "level", (v) => {
      el.dataset.level = String(v);
    });
    return el;
  },
  badge(nodeA) {
    const el = textish(nodeA, "span", "rx-badge");
    attr(nodeA, "tone", (v) => {
      el.dataset.tone = v;
    });
    return el;
  },
  code(nodeA) {
    const el = textish(nodeA, "pre", "rx-code");
    const inner = make("code", "rx-code__inner");
    el.textContent = "";
    el.append(inner);
    inner.append(document.createTextNode(""));
    attr(nodeA, "value", (v) => {
      inner.textContent = v ?? "";
    });
    attr(nodeA, "lang", (v) => {
      el.dataset.lang = v ?? "";
    });
    return el;
  },
  image(nodeA) {
    const el = make("img", "rx-image");
    attr(nodeA, "src", (v) => {
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
  link(nodeA) {
    const el = make("a", "rx-link");
    attr(nodeA, "href", (v) => {
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
  progress(nodeA) {
    const host = make("div", "rx-progress");
    const bar = make("div", "rx-progress__bar");
    const caption = make("span", "rx-progress__label");
    attr(nodeA, "value", (v) => {
      host.dataset.value = String(v ?? 0);
      bar.style.inlineSize = `${Math.max(0, Math.min(100, Number(v) || 0))}%`;
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
  empty(nodeA) {
    const host = make("div", "rx-empty");
    const caption = textish(nodeA, "p", "rx-empty__text");
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
  const impl = IMPL[nodeA()?.type];
  return impl ? impl(nodeA, ctx) : unsupported(nodeA, ctx);
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