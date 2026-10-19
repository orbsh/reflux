/* reflux 的客户端 runtime —— 只碰浏览器的事实。
 *
 * 它不认识树、不认识帧、不碰 socket：上行走渲染器发布的 window.fluxen.send，下行帧它一概看不见。
 * 它读的两个标记是普通节点（`placeholder` 会把节点 id 落到 DOM 上），由 SDK 的糖生成、由 reflux
 * 自己的样式表藏起来。它只镜像，不猜：没有标记就停在旧值。
 *
 * 页面挂在哪条前缀下由页面的 <base href> 说（迁移期 "/__next/"，之后 "/"）：标记里写的是**应用
 * 路径**（"/b"），地址栏是挂载后的路径（"/__next/b"），换算只在下面 toApp / toBrowser 一处发生。
 */
const PATH_ID = "reflux:path";
const TITLE_ID = "reflux:title";

// "/" -> "", "/__next/" -> "/__next"：前缀本身，不带尾斜杠。
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

function mirror() {
  const raw = marker(PATH_ID);
  // 标记里只认路径：带查询串/锚点的写法按路径处理（查询串是浏览器的，不是生产者的）
  const path = raw === null ? null : raw.split(/[?#]/)[0];
  if (path && path.startsWith("/") && toBrowser(path) !== location.pathname) {
    history.pushState(null, "", toBrowser(path));
  }
  const title = marker(TITLE_ID);
  if (title !== null && title !== document.title) document.title = title;
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
  window.fluxen.send("reflux:hello", { path: toApp(location.pathname) });
  addEventListener("popstate", () => {
    // 后退/前进：浏览器已经把地址栏换了，这里只负责把请求送上去
    window.fluxen.send("reflux:nav", { path: toApp(location.pathname) });
  });
  const root = document.getElementById("main") || document.body;
  new MutationObserver(schedule).observe(root, {
    childList: true,
    subtree: true,
    characterData: true, // attributes 故意不看：输入框的 class 天天在变
  });
  mirror(); // 首屏：DOM 里已有的那批标记
}