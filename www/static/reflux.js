/* reflux 的客户端 runtime —— 只碰浏览器的事实。
 *
 * 它不认识树、不认识帧、不碰 socket：上行走渲染器发布的 window.fluxen.send，下行帧它一概看不见。
 * 它读的两个标记是普通节点（`placeholder` 会把节点 id 落到 DOM 上），由 SDK 的糖生成、由 reflux
 * 自己的样式表藏起来。它只镜像，不猜：没有标记就停在旧值。
 *
 * 页面挂在哪条前缀下由页面的 <base href> 说（现在是 "/" 即源站根）：标记里写的是**应用路径**
 * （"/b"），地址栏是挂载后的路径，换算只在下面 toApp / toBrowser 一处发生。
 *
 * 凭证是第三条标记（`reflux:token`），也是它替浏览器保管的唯一一件东西：框架说一次，它存下来，
 * 下次握手带上，空标记就没收。存的是浏览器自己的存储，所以刷新还是同一个用户——这正是 token 存在
 * 的理由；下行帧它看不见，凭证只能走标记。
 *
 * 第五件事是 `TOKENS` 那张表（ADR 0001 §3）：页面选项的成员被渲染器镜像成文档根上的 `data-<member>`，
 * 而 CSS 读不到属性值——`attr()` 落不进 `var()`——所以把值变成 `--*` 必须有人做，做的人就是这里。
 * 表是**闭集**：表里没有的成员一概不碰（`sketch` 归渲染器，它按 `data-sketch` 画边框），值域校验
 * 也在表里，因为 `data-*` 是任何人都能写的面。
 *
 * 表里写的是**名字与种类**，不是"成员 → 变量"的对照：名字去掉 `--` 就是 core.css 的令牌名，映射因此
 * 是一条规则。颜色成员存的是 `L C H` 三元组，`oklch(...)` 只在这里合成一次 —— 颜色空间是一个决定。
 */
const PATH_ID = "reflux:path";
const TITLE_ID = "reflux:title";
const TOKEN_ID = "reflux:token";
const TOKEN_KEY = "reflux:token";

// core.css 的 `:root` 令牌面 -> 种类。表是白名单：成员不在表里，就不上色。变量名由成员名加 `--` 得到，
// 所以没有第二张对照表；加一个令牌是加一行（服务端那张表是同一份事实，测试钉着两边相等）。
const TOKENS = {
  fg: "color",
  bg: "color",
  surface: "color",
  accent: "color",
  primary: "color",
  secondary: "color",
  disabled: "color",
  warn: "color",
  error: "color",
  "border-color": "color",
  round: "length",
  "input-round": "length",
  "border-width": "length",
  "border-style": "keyword",
};

const KEYWORDS = new Set(["solid", "dashed", "dotted", "double", "none"]);

// 一个成员值 -> 这个成员该写进 `--*` 的东西。null 表示"不设"（空值）或"不合法"，两种都撤掉属性：
// 前者是用户的意图（回到样式表的缺省），后者是不猜一个近似的。
function tokenValue(kind, raw) {
  const text = raw.trim();
  if (text === "") return null;
  if (kind === "color") {
    const parts = text.split(/[\s,]+/).filter(Boolean);
    if (parts.length !== 3) return null;
    const [light, chroma, hue] = parts.map((part) => Number(part.replace(/%$/, "")));
    if (![light, chroma, hue].every(Number.isFinite)) return null;
    if (light < 0 || light > 1 || chroma < 0 || chroma > 0.4 || hue < 0 || hue > 360) return null;
    return `oklch(${light} ${chroma} ${hue})`;
  }
  if (kind === "length") {
    const value = Number(text.replace(/px$/i, ""));
    return Number.isFinite(value) && value >= 0 && value <= 64 ? `${value}px` : null;
  }
  const keyword = text.toLowerCase();
  return KEYWORDS.has(keyword) ? keyword : null;
}

function paint() {
  // 属性 -> 自定义属性，一条规则对所有令牌（名字即变量名）。
  const root = document.documentElement;
  for (const [member, kind] of Object.entries(TOKENS)) {
    const raw = root.getAttribute(`data-${member}`);
    const value = raw === null ? null : tokenValue(kind, raw);
    const variable = `--${member}`;
    if (value === null) root.style.removeProperty(variable);
    else root.style.setProperty(variable, value);
  }
}

// "/" -> ""：<base> 的前缀本身，不带尾斜杠。
const base = (() => {
  const path = new URL(document.baseURI).pathname;
  return path.endsWith("/") ? path.slice(0, -1) : path;
})();

function toApp(urlPath) {
  // 地址栏 -> 应用路径
  if (base && urlPath.startsWith(base)) return urlPath.slice(base.length) || "/";
  return urlPath;
}

function toBrowser(appPath) {
  // 应用路径 -> 地址栏（"/" 要留住尾斜杠，否则挂在前缀下的页面会落到前缀外）
  return base + (appPath === "/" ? "/" : appPath);
}

function marker(id) {
  const el = document.getElementById(id);
  const text = el ? (el.textContent || "").trim() : "";
  return text === "" ? null : text;
}

// 存储可能不可用（隐私模式、无存储的子框架）：拿不到就当作没有凭证，不抛。
function remembered() {
  try {
    return window.localStorage.getItem(TOKEN_KEY) || null;
  } catch {
    return null;
  }
}

function remember(token) {
  try {
    window.localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* 存不了：这条连接仍是绑定的，只是刷新之后要重新登录 */
  }
}

function forget() {
  try {
    window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* 本来就没存 */
  }
}

function adoptToken() {
  // 标记在就照它办：有内容 -> 存，空 -> 没收。标记不在就不动（换一帧页面不等于登出）。
  const el = document.getElementById(TOKEN_ID);
  if (!el) return;
  const token = (el.textContent || "").trim();
  if (token === "") forget();
  else if (token !== remembered()) remember(token);
}

function mirror() {
  const raw = marker(PATH_ID);
  // 标记里只认路径：带查询串/锚点的写法按路径处理（查询串是浏览器的，不是生产者的）
  const path = raw === null ? null : raw.split(/[?#]/)[0];
  if (path && path.startsWith("/") && toBrowser(path) !== location.pathname) {
    history.pushState(null, "", toBrowser(path));
  }
  const title = marker(TITLE_ID);
  if (title !== null && title !== document.title) document.title = title;
  adoptToken();
}

function where() {
  // 地址栏的两件东西一起交给后端：路径按应用路径换算，查询串原样（它属于浏览器，解释权在后端）。
  // 没有查询串时这个字段不写——帧里不写没有信息的东西，与 append 的 position 同一条规矩。
  const path = toApp(location.pathname);
  const query = location.search;
  const frame = query ? { path, query } : { path };
  // 凭证同理：没有就不写。服务端拿它把这条连接绑回同一个人，所以刷新不是换人。
  const token = remembered();
  if (token) frame.token = token;
  return frame;
}

let scheduled = false;
function schedule() {
  // 一帧里的多次改动合并成一次读，别对每一处 DOM 变更都跑一趟
  if (scheduled) return;
  scheduled = true;
  queueMicrotask(() => {
    scheduled = false;
    mirror();
  });
}

/**
 * How this host mounts the renderer. The codec is the host's word — the wire is ours, and a JSON
 * uplink is the one this runtime reads — and so is the path. Neither belongs to the renderer, and
 * neither belongs in a page's markup: a page that mounts reflux asks this module for them (ADR 0046
 * put the same split inside fluxen: the boot decides nothing about the address).
 */
export const BOOT = {
  codec: "json",
  path: "/ws",
  hooks: {
    // 握手挂在连接的门口，不挂在"页面启动"上：重连是另一次握手，服务端那时是另一个人
    // （它不认识旧的 socket），所以每一新连接都要重新说我们在哪、我们是谁（ADR 0047）。
    open: (send) => send("reflux:hello", where()),
  },
};

export function start() {
  if (!window.fluxen || typeof window.fluxen.send !== "function") {
    throw new Error("reflux runtime: window.fluxen.send is missing — is the renderer mounted?");
  }
  // hello 已经在 `BOOT.hooks.open` 里说了（每次连接一次）；这里只管页面自己的事。
  addEventListener("popstate", () => {
    // 后退/前进：浏览器已经把地址栏换了，这里只负责把请求送上去
    window.fluxen.send("reflux:nav", where());
  });
  const root = document.getElementById("main") || document.body;
  new MutationObserver(schedule).observe(root, {
    childList: true,
    subtree: true,
    characterData: true, // attributes 故意不看：输入框的 class 天天在变
  });
  mirror(); // 首屏：DOM 里已有的那批标记
  paint(); // 首屏的页面选项（渲染器可能比这里先跑）
  new MutationObserver(paint).observe(document.documentElement, {
    attributes: true,
    attributeFilter: Object.keys(TOKENS).map((member) => `data-${member}`),
  });
}