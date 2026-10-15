// Reflux shell — the interpreter: the four ops applied to the client-side store.
//
// This layer moves data and structure and knows nothing about components (dispatch lands in
// T3). It is the shell's *only* writer of the tree and the slots, and every degraded path
// leaves a counter behind — silent degradation is not an option in this design.
//
// Frame contract (spec/components.json carries the closed sets):
//   {ev: "draw", ops: [create|patch|insert|remove, ...]}
//   - a malformed frame, or one with an unknown op name, is rejected whole (nothing applied)
//   - an op whose path does not resolve is dropped, counted, and the rest of the frame applies
//
// Addressing root: the *client state*, whose two writable areas are `tree` (structure) and
// `slots` (data) — so `/tree/children/0/attrs/value` and `/slots/name` are both valid paths,
// and "" means "the tree as a whole" (create's job, and what a whole-tree patch replaces).

import { batch } from "solid-js";
import { createStore, produce, unwrap } from "solid-js/store";

const OPS = new Set(["create", "patch", "insert", "remove"]);

function steps(path) {
  if (path === "") return [];
  if (typeof path !== "string" || path[0] !== "/") return null; // RFC 6901: the root is ""
  return path
    .slice(1)
    .split("/")
    .map((s) => s.replaceAll("~1", "/").replaceAll("~0", "~"));
}

function isIndex(s) {
  return /^(0|[1-9][0-9]*)$/.test(s);
}

// The parent of the target plus the final key, so callers can read, set or delete it.
// Returns null when the path does not resolve — that is a "drop", not a crash.
function locate(node, path) {
  const st = steps(path);
  if (st === null) return null;
  if (st.length === 0) return { parent: null, key: null };
  let cur = node;
  for (let i = 0; i < st.length - 1; i++) {
    const s = st[i];
    if (Array.isArray(cur)) {
      if (!isIndex(s) || Number(s) >= cur.length) return null;
      cur = cur[Number(s)];
    } else if (cur !== null && typeof cur === "object" && s in cur) {
      cur = cur[s];
    } else {
      return null;
    }
  }
  return { parent: cur, key: st[st.length - 1] };
}

function validOp(op) {
  if (op === null || typeof op !== "object" || !OPS.has(op.op)) return false;
  switch (op.op) {
    case "create":
      return op.root !== null && typeof op.root === "object" && !Array.isArray(op.root);
    case "patch":
      return typeof op.path === "string" && "value" in op;
    case "insert":
      return typeof op.path === "string" && op.node !== null && typeof op.node === "object";
    case "remove":
      return typeof op.path === "string";
    default:
      return false;
  }
}

export function createInterp() {
  const [state, setState] = createStore({ tree: null, title: "", slots: {} });

  const counters = { frames: 0, ops: 0, dropped: 0, rejected: 0, ignored: 0 };

  // returns "ok" | "drop"  (a rejected op is caught by validOp before anything is applied)
  function applyOp(draft, op) {
    switch (op.op) {
      case "create": {
        draft.tree = op.root;
        if (typeof op.title === "string") draft.title = op.title;
        return "ok";
      }
      case "patch": {
        if (op.path === "") {
          draft.tree = op.value;
          return "ok";
        }
        const at = locate(draft, op.path);
        if (!at) return "drop";
        at.parent[at.key] = op.value;
        return "ok";
      }
      case "insert": {
        const at = locate(draft, op.path);
        if (!at || !Array.isArray(at.parent[at.key])) return "drop";
        const arr = at.parent[at.key];
        const anchor = op.anchor === undefined ? "end" : op.anchor;
        let index;
        if (anchor === "end") {
          index = arr.length;
        } else if (anchor && typeof anchor === "object" && "index" in anchor) {
          const n = anchor.index;
          if (!Number.isInteger(n) || n < 0 || n > arr.length) return "drop";
          index = n;
        } else if (anchor && typeof anchor === "object" && "id" in anchor) {
          const found = arr.findIndex((n) => n !== null && typeof n === "object" && n.id === anchor.id);
          if (found < 0) return "drop";
          index = found + 1; // immediately after the anchor row
        } else {
          return "drop";
        }
        arr.splice(index, 0, op.node);
        return "ok";
      }
      case "remove": {
        const at = locate(draft, op.path);
        if (!at) return "drop";
        if (op.id !== undefined && op.id !== null) {
          const arr = at.parent[at.key];
          if (!Array.isArray(arr)) return "drop";
          const found = arr.findIndex((n) => n !== null && typeof n === "object" && n.id === op.id);
          if (found < 0) return "drop";
          arr.splice(found, 1);
          return "ok";
        }
        if (at.parent === null) {
          draft.tree = null;
          return "ok";
        }
        if (Array.isArray(at.parent)) {
          if (!isIndex(at.key) || Number(at.key) >= at.parent.length) return "drop";
          at.parent.splice(Number(at.key), 1);
          return "ok";
        }
        if (typeof at.parent === "object" && at.key in at.parent) {
          delete at.parent[at.key];
          return "ok";
        }
        return "drop";
      }
      default:
        return "drop";
    }
  }

  function apply(frame) {
    counters.frames++;
    if (frame === null || typeof frame !== "object" || typeof frame.ev !== "string") {
      counters.rejected++;
      return false;
    }
    if (frame.ev !== "draw") {
      counters.ignored++; // another category's frame: logged, never rendered
      return false;
    }
    if (!Array.isArray(frame.ops) || !frame.ops.every(validOp)) {
      counters.rejected++; // whole frame refused: nothing is applied, not even the good ops
      return false;
    }
    const before = counters.dropped;
    batch(() => {
      setState(
        produce((draft) => {
          for (const op of frame.ops) {
            if (applyOp(draft, op) === "ok") counters.ops++;
            else counters.dropped++;
          }
        }),
      );
    });
    return counters.dropped === before;
  }

  return {
    state,
    counters,
    apply,
    setSlot(name, value) {
      batch(() => setState("slots", name, value));
    },
    snapshot() {
      return JSON.parse(JSON.stringify(unwrap(state)));
    },
  };
}