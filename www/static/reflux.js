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
 */
const PATH_ID = "reflux:path";
const TITLE_ID = "reflux:title";
const TOKEN_ID = "reflux:token";
const TOKEN_KEY = "reflux:token";

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

export function start() {
  if (!window.fluxen || typeof window.fluxen.send !== "function") {
    throw new Error("reflux runtime: window.fluxen.send is missing — is the renderer mounted?");
  }
  // 握手先走：连接那一刻生产者还不知道客户端站在哪条路径上（见「连接与握手」）
  window.fluxen.send("reflux:hello", where());
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
}