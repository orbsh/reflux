// Node validation against the generated table.
//
// The shell is the second half of "parse, don't validate": a producer that builds nodes by
// hand (stage, curl, another language's SDK) gets checked here, and a structure that does
// not fit the closed vocabulary refuses the whole frame — counted, never half-rendered.
//
// Only *structure* is validated this way. A patch that lands in `slots` carries free data,
// so a value only gets node-checked when it sits under `tree`.

import { BIND_KEYS, COMPONENTS, MAX_OPS_PER_FRAME, RESERVED_PREFIX } from "./components.generated.js";

function isPlainObject(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function checkAttr(where, attr, domain, value) {
  const at = `${where}.${attr}`;
  if (domain.enum) {
    return domain.enum.includes(value)
      ? null
      : `${at}: ${JSON.stringify(value)} outside ${JSON.stringify(domain.enum)}`;
  }
  switch (domain.type) {
    case "bool":
      return typeof value === "boolean" ? null : `${at}: expected bool, got ${typeof value}`;
    case "int": {
      if (!Number.isInteger(value)) return `${at}: expected int, got ${typeof value}`;
      if (domain.min !== undefined && value < domain.min) return `${at}: ${value} below ${domain.min}`;
      if (domain.max !== undefined && value > domain.max) return `${at}: ${value} above ${domain.max}`;
      return null;
    }
    case "string":
      return typeof value === "string" ? null : `${at}: expected string, got ${typeof value}`;
    case "url": {
      if (typeof value !== "string") return `${at}: expected string, got ${typeof value}`;
      const ok =
        value.startsWith("http://") || value.startsWith("https://") || value.startsWith("/");
      return ok ? null : `${at}: ${JSON.stringify(value)} must be http(s) or an internal path`;
    }
    default:
      return `${at}: unknown domain ${JSON.stringify(domain)}`;
  }
}

/** Validate one node and its subtree. Returns an error string, or null when it fits. */
export function validateNode(node, where = "") {
  if (!isPlainObject(node)) return `${where || "/tree"}: a node must be an object`;
  const spec = COMPONENTS[node.type];
  if (!spec) {
    return `${where}: unknown component ${JSON.stringify(node.type)} — the vocabulary is closed (${Object.keys(COMPONENTS).length} components)`;
  }
  if (node.id !== null && node.id !== undefined && typeof node.id !== "string") {
    return `${where}.id: expected a string or null`;
  }

  const attrs = node.attrs ?? {};
  if (!isPlainObject(attrs)) return `${where}.attrs: expected an object`;
  for (const [attr, value] of Object.entries(attrs)) {
    const domain = spec.attrs[attr];
    if (!domain) {
      return `${where}.${attr}: not an attr of ${node.type} (it takes ${Object.keys(spec.attrs).join(", ")})`;
    }
    const err = checkAttr(where, attr, domain, value);
    if (err) return err;
  }
  for (const [attr, domain] of Object.entries(spec.attrs)) {
    if (domain.default === undefined && !(attr in attrs)) {
      return `${where}.${attr}: required attr missing`;
    }
  }

  const bind = node.bind ?? {};
  if (!isPlainObject(bind)) return `${where}.bind: expected an object`;
  for (const [key, value] of Object.entries(bind)) {
    if (!BIND_KEYS.includes(key)) {
      return `${where}.bind.${key}: not a bind key (${BIND_KEYS.join(" / ")})`;
    }
    if (!spec.bind.includes(key)) {
      return `${where}.bind.${key}: ${node.type} accepts ${spec.bind.join(" / ") || "no binding"}`;
    }
    if (key === "event") {
      if (typeof value !== "string" || !value) return `${where}.bind.event: must be a non-empty string`;
      if (value.startsWith(RESERVED_PREFIX)) {
        return `${where}.bind.event: ${JSON.stringify(value)} uses the reserved prefix ${RESERVED_PREFIX}`;
      }
    } else if (key === "payload") {
      if (!Array.isArray(value)) return `${where}.bind.payload: expected an array`;
      for (const name of value) {
        if (!spec.local.includes(name)) {
          return `${where}.bind.payload: ${JSON.stringify(name)} is not local state of ${node.type} (${spec.local.join(" / ") || "none"})`;
        }
      }
    } else if (typeof value !== "string" || !value) {
      return `${where}.bind.${key}: must be a non-empty string`;
    }
  }

  const kids = node.children ?? [];
  if (!Array.isArray(kids)) return `${where}.children: expected an array`;
  if (spec.children === "none" && kids.length !== 0) {
    return `${where}.children: ${node.type} takes no children, got ${kids.length}`;
  }
  if (spec.children === "one" && kids.length !== 1) {
    return `${where}.children: ${node.type} takes exactly one child, got ${kids.length}`;
  }
  const seen = new Set();
  for (let i = 0; i < kids.length; i++) {
    const kid = kids[i];
    if (kid && typeof kid.id === "string") {
      if (seen.has(kid.id)) {
        return `${where}.children: duplicate row id ${JSON.stringify(kid.id)} — rows in one array must be unique`;
      }
      seen.add(kid.id);
    }
    const err = validateNode(kid, `${where}/children/${i}`);
    if (err) return err;
  }
  return null;
}

const hasNodeShape = (v) => isPlainObject(v) && typeof v.type === "string";
const inTree = (path) => path === "" || path === "/tree" || path.startsWith("/tree/");

// Same JSON Pointer spelling the interpreter uses (kept local: validate.js must not import
// the interpreter, or the module graph cycles).
function pointerSteps(path) {
  return path.slice(1).split("/").map((s) => s.replaceAll("~1", "/").replaceAll("~0", "~"));
}

function nodeAt(tree, steps) {
  let cur = tree;
  for (const step of steps) {
    if (cur === null || typeof cur !== "object") return null;
    cur = Array.isArray(cur) ? cur[Number(step)] : cur[step];
    if (cur === undefined) return null;
  }
  return cur;
}

/**
 * Validate the nodes a frame introduces, plus any attr it patches by pointer.
 * Returns an error string, or null.
 *
 * `tree` is the current structure: a patch that writes an attr value has to resolve its
 * target to know which component's domain applies (`/tree/.../attrs/tone` on a badge is a
 * closed set; the same path on a slot is free data).
 */
export function validateFrame(ops, tree = null) {
  if (ops.length > MAX_OPS_PER_FRAME) {
    return `${ops.length} ops in one frame — the cap is ${MAX_OPS_PER_FRAME} (a runaway producer is a defect, not something to apply halfway)`;
  }
  for (const op of ops) {
    if (op.op === "create") {
      const err = validateNode(op.root, "/tree");
      if (err) return err;
    } else if (op.op === "insert") {
      const err = validateNode(op.node, op.path ?? "/tree");
      if (err) return err;
    } else if (op.op === "patch" && inTree(op.path)) {
      if (hasNodeShape(op.value)) {
        const err = validateNode(op.value, op.path || "/tree");
        if (err) return err;
        continue;
      }
      if (tree === null || !op.path.startsWith("/tree/")) continue;
      const parts = pointerSteps(op.path);
      if (parts.length < 4 || parts[parts.length - 2] !== "attrs") continue;
      const target = nodeAt(tree, parts.slice(1, -2));
      if (!target || !COMPONENTS[target.type]) continue;
      const attr = parts[parts.length - 1];
      const domain = COMPONENTS[target.type].attrs[attr];
      if (!domain) {
        return `${op.path}: ${JSON.stringify(attr)} is not an attr of ${target.type}`;
      }
      const nodePath = `/${parts.slice(0, -1).join("/")}`;
      const err = checkAttr(nodePath, attr, domain, op.value);
      if (err) return err;
    }
  }
  return null;
}