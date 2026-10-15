# Reflux — 实施状态

任务清单与理由在 [`DESIGN.md`](DESIGN.md)（「实施计划」一节）。本文件只记**状态**与**复验命令**——
一条任务没跑过它的门槛命令，就不算完成。

| 任务 | 状态 | 复验 |
|------|------|------|
| T0 骨架与零工具链证明 | ✅ 2026-10-15 | `python3 tools/gate_t0.py` |
| T1 规格（规格 → 壳表 + SDK，无漂移） | ✅ 2026-10-15 | `python3 tools/gen.py --check` ＋ `python3 -m unittest discover -s tests -t .` |
| T2 壳的 store 与解释器（四个操作、路径寻址、槽订阅） | ✅ 2026-10-15 | `python3 tools/gate_t2.py` |
| T3 组件分派与本地态 | ⏳ | — |
| T4 绑定与事件（source / event / payload） | ⏳ | — |
| T5 路由 | ⏳ | — |
| T6 导航 | ⏳ | — |
| T7 会话与心跳 | ⏳ | — |
| T8 故障注入 | ⏳ | — |
| T9 Python SDK（demo 应用跑通四类交互） | ⏳ | — |
| T10 第二个语言的 SDK（最小） | ⏳ | — |
| T11 测量 | ⏳ | — |

## 已落地的形状

```
spec/components.json              单一来源：组件/属性白名单/取值域/绑定/操作/保留前缀
tools/gen.py                      规格 → 三件产物；--check 做漂移门
tools/gate_t0.py                  T0 门：真起 chromium，经 CDP 断言（stdlib-only）
reflux/tables_generated.py        ← 生成：纯数据（壳与各 SDK 共用的词表）
reflux/components_generated.py    ← 生成：各组件构造器（签名由规格派生）
reflux/node.py                    线上形状 + 校验边界 make()
reflux/server.py / demo.py        伺服壳（静态、无缓存、同源）；操作通道在 T2 落地
shell/index.html + js/main.js     静态壳：import map 加载 vendored SolidJS，无编译
shell/vendor/solid-js/            钉版本的四个 ESM 文件（sha256 记在 shell/VERSIONS）
tests/                            规格漂移、两边词表一致、边界校验、签名形状、资产哈希
```

Python SDK 就是这个仓的 `reflux/` 包（语言无关的东西在 `spec/`，别的语言日后落在
`sdks/<lang>/`）。

## T0 门的实测结果（2026-10-15）

```
[1/4] PASS  zero external requests           8 requests, all same-origin
[2/4] PASS  zero console errors              none
[3/4] PASS  mount probe                      data-probe='booted'
[4/4] PASS  store write reached the DOM      innerText='reflux shell · boot ok · store live'
```

门抓到的两件事（都已修）：

- `/favicon.ico` 404 会算作一条 console error —— 现在壳自带 `favicon.svg` 并在 `index.html` 里声明。
- **无编译路径的真实代价**：动态子节点必须显式写成取值函数（`h("code", null, () => state.slots.boot)`）。
  写普通值只在首次插入时生效一次，之后 store 的写不会进 DOM——第 4 条断言就是钉这个的。

## T1 门的实测结果（2026-10-15）

```
[gen] up to date: spec v0.1.0, 21 components, 3 artifacts
Ran 16 tests ... OK
```

规格校验器在写第一版规格时就抓到两处自相矛盾（当场改掉，没进产物）：`form` 与 `button`
声明了 `payload` 却没有本地态。规则随之立住：**`payload` 只能列本组件自己的本地态**——
于是 `form` 拿到 `local: ["fields"]`（一次提交多个字段的机制所在），`button` 的绑定收敛为
`["event"]`（行身份走节点 `id`，不塞进 payload）。

## T2 门的实测结果（2026-10-15）

```
[1/10]  zero console errors                    none
[2/10]  create: tree + title                   title='看板' children=['row-greeting','row-name','row-go']
[3/10]  patch: pointer into a child            value='你好'
[4/10]  insert: after an id anchor             order=['row-greeting','row-extra','row-name','row-go']
[5/10]  remove: by row id                      order=['row-greeting','row-name','row-go']
[6/10]  unknown path: op dropped, rest applied dropped+1 placeholder='名字'
[7/10]  malformed frame: refused whole         rejected+1 value='你好'
[8/10]  other category: ignored                ignored+1
[9/10]  atomicity: 3 ops, 1 store update       effect runs=1
[10/10] counters account for every frame       ops=8 dropped=1 rejected=1 ignored=1
```

落地的形状：`shell/js/interp.js`（四个操作 + 路径 + id 锚点 + 计数 + 整批原子）、
`tools/cdp.py`（两个门共用的 CDP/浏览器夹具，T0 的门已改用它）、`tools/gate_t2.py`。

门抓到的两件事：

- **寻址的根**：第一跑里除 `create` 之外全部被 drop——`locate()` 拿 `tree` 当根，而路径写的是
  `/tree/...`。正形是**以客户端状态为根**（`tree` 结构 / `slots` 数据两个可写面），文档里那句
  「`""` 是根」也因此写清楚了。
- **浅读看不见深写**：原子性断言最初让观察者只读 `state.tree`，于是三操作帧里它一次都没重跑——
  既说明批处理是对的（写确实生效了），也说明**渲染层必须逐个字段读它真正要画的东西**：读父对象
  不会有通知。这条直接约束 T3 的写法。