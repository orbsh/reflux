# Reflux — 实施状态

任务清单与理由在 [`DESIGN.md`](DESIGN.md)（「实施计划」一节）。本文件只记**状态**与**复验命令**——
一条任务没跑过它的门槛命令，就不算完成。

## 方向裁决（2026-10-16）

- **壳退休，reflux 转成集成 fluxen 的 web 框架**（Next 之于 React 的分工）。渲染交给 fluxen 的渲染器；词表的单一来源变成 accrete 的类型——`cargo run -q -p stage -- schema` 导出 draft 2020-12 的 schema，SDK 由它生成。
- 退场的是自带词表的 SolidJS 壳与手写的 `spec/components.json`；`tools/gen.py` 里的构造器生成逻辑留下，输入从规格换成那份 schema。
- **封闭性与跨字段语义归 reflux**（生成的 SDK + 服务端入站校验 + 门）。accrete 刻意不拒未知字段（旧帧兼容），静默丢弃是那边的既定行为，不去改它——代价是绕过 SDK 手写 JSON 的生产者没有封闭性，这条写明。
- **帧定义只有一套**：fluxen 的 `Message` / `Content` / `Outflow`。`ev = "draw"` 归渲染器；`reflux:hello` 与 `reflux:nav` 走上行的 `Outflow`（它的 `data` 是自由的），回答是一次 `draw`——今天没有第二类 ev，要一类下行框架帧得先给那个信封加字段（没走这条路）。
- 不作判据（已裁决，不再论证）：资产体积与跨边界开销；「JS 门槛低、便于外部参与」——实测不成立。
- **词表用 accrete 的既有词表，不往外长**（2026-10-17）：新类型与枚举属性都不加进 accrete；profile 是 reflux 侧一份可读数据——选哪些类型进应用面、哪个属性值是默认、变体落成哪些 class 令牌。现有 21 项与那 30 个根变体不是包含关系（同名 8 项），那 13 项逐条落法在 `DESIGN.md` 的「组件词表」。
- **操作集取 accrete 的八个，逐字，四个平面各有各的寻址**（2026-10-17）：`create` / `set` / `append` / `remove` / `patch` / `inject` / `tmpl` / `empty`，不留翻译层；旧四个与它们的转换、以及代价（按 id 锚定的插入没了、结构数组里插一格要重写那一段、`title` 没有线上落点）写在 `DESIGN.md` 的「操作」。`payload`（声明带哪几件本地态）随之退场——送什么由组件自己定。
- **导航：link 退场，URL 与标题归客户端 runtime**（2026-10-17）：accrete 没有带 URL 的类型，也没有 click 发射面（能上行的只有 input／textarea／select 与 form 的 submit）；「点一下就做事」只剩 canvas 的模块通道。URL 与标题由 runtime 从树里的两个保留 id（`reflux:path`／`reflux:title`）镜像——代价是地址栏与标题成了生产者声明的投影，漏写就停在旧值（进失败模式表，门对着它断言）。
- 迁移的缝已清零：词表 profile、SDK 生成、操作集与帧归属、页内导航都已裁完（见上两条与下表）；M1 可开。
- **迁移期的入口**（2026-10-19）：socket 留在渲染器里开（它已经在做 codec 与 URL 的协商），额外只开两扇小门——`#main` 的 `data-codec`／`data-path`，以及挂载后发布的一个页面级上行把手（与 canvas 的 `host.send` 同形状）。reflux 不自带 wasm 入口（判据在 `DESIGN.md` 的「Why Not」）。迁移期两个页面并存：壳在 `/`、新页在 `/__next`，各跑各的门；M1.6 把 `/__next` 提到 `/` 并删壳。

已落地的 T0–T6 全跑在**退休前那套实现**上（规格 + SolidJS 壳），门槛命令照旧有效，退役不发生在它们身上；迁移任务见下表末尾。

| 任务 | 状态 | 复验 |
|------|------|------|
| T0 骨架与零工具链证明 | ✅ 2026-10-15 | `python3 tools/gate_t0.py` |
| T1 规格（规格 → 壳表 + SDK，无漂移） | ✅ 2026-10-15 | `python3 tools/gen.py --check` ＋ `python3 -m unittest discover -s tests -t .` |
| T2 壳的 store 与解释器（四个操作、路径寻址、槽订阅） | ✅ 2026-10-15 | `python3 tools/gate_t2.py` |
| T3 组件分派与本地态（21 个组件、规格↔实现相等、变更计数） | ✅ 2026-10-15 | `python3 tools/gate_t3.py` |
| T4 绑定与事件（source / event / payload / fire、委托监听、通道与上行帧、拒收） | ✅ 2026-10-16 | `python3 tools/gate_t4.py` |
| T5 路由（装饰器与注册器、发现、择优键、并列歧义、CLI 打印） | ✅ 2026-10-16 | `python3 -m unittest tests.test_routes` ＋ 全套 |
| T6 导航（链接拦截、popstate、hello 带路径、page 钩子、内置 404、页面路径交给壳） | ✅ 2026-10-16 | `python3 tools/gate_t6.py` |
| T7 会话与心跳（会话即连接、断线/判死回收、心跳线程、计数） | ✅ 2026-10-16 | `python3 tools/gate_t7.py` ＋ 全套 |
| T8 故障注入（坏 JSON／未注册名／缺 event／处理器抛异常／批量上限／重复行 id／慢客户端；每条的降级都计数且会话存活） | ✅ 2026-10-16 | `python3 tools/gate_t8.py` ＋ 全套 |
| T9 Python SDK（类型由 accrete 的 schema 生成；demo 应用跑通三类交互；导航按镜像机制测） | ⏳ 先决：M1 | — |
| T10 第二个语言的 SDK（最小；同一份 schema → 另一语言） | ⏳ 先决：M1 | — |
| T11 测量 | ⏳ | — |
| M1 先决：SDK 生成（schema 快照 + profile → `reflux/sdk/`；后处理修形；离线门） | ✅ 2026-10-17 | `python3 tools/gen_sdk.py --check` ＋ `python3 -m unittest tests.test_sdk_generated`（12 例） |
| M1 与 fluxen 合流（渲染器换成它的包；退场：`spec/`、`shell/*`、壳侧生成物；T7–T11 的门重新对到新客户端；封闭性与跨字段语义落到 SDK + 服务端入站 + 门） | ⏳ 可开（已拆成 M1.1–M1.7，见下） | — |
| M1.1 入口把手（`#main` 的 `data-codec`／`data-path`；挂载后发布页面级 send） | ✅ 2026-10-19 | `python3 tools/gate_m1_1.py`（5 条；用仓里钉住的包，无需 fluxen 检出） |
| M1.2 资产与伺服（reflux 出页面；渲染器 dist 按 `VERSIONS` 钉版本；reflux 自己的样式表） | ✅ 2026-10-19 | `python3 tools/gate_t0_next.py`（7 条）＋ `python3 -m unittest tests.test_page` |
| M1.3 客户端 runtime（两个标记的镜像、hello、popstate） | ✅ 2026-10-19 | `python3 tools/gate_t6_next.py`（8 条）＋ `python3 -m unittest tests.test_page` |
| M1.4 出帧层（accrete 的八个 action + `Message` 信封，`reflux/wire.py`） | ✅ 2026-10-19 | `python3 tools/gate_t2_next.py`（12 条）＋ `python3 -m unittest tests.test_wire` |
| M1.5 服务端入站校验（封闭性与跨字段语义的落点） | ⏳ | — |
| M1.6 交互门重对（T2／T3 退场换两条；T4／T8 改写；profile 令牌接线） | ⏳ | — |
| M1.7 退场（`spec/`、`shell/*`、壳侧生成物；`/__next` 提到 `/`；`draw_page`／`not_found` 切到 `wire`） | ⏳ | — |

## 已落地的形状

```
spec/components.json              单一来源：组件/属性白名单/取值域/绑定/上行时机/操作/保留前缀
tools/gen.py                      规格 → 三件产物；--check 做漂移门
tools/gate_t0.py                  T0 门：真起 chromium，经 CDP 断言（stdlib-only）
tools/gate_t2.py / t3.py / t4.py  各任务的门；共用 tools/cdp.py 的夹具（含真鼠标/真按键/真历史）
reflux/tables_generated.py        ← 生成：纯数据（壳与各 SDK 共用的词表，含 FIRE_EVENTS）
reflux/components_generated.py    ← 生成：各组件构造器（签名由规格派生）
reflux/node.py                    线上形状 + 校验边界 make()
reflux/ui.py                      写入层：规格词表寻址成一个模块（ui.stack(...)）
reflux/ops.py                     写入层：四个操作与 draw 的构造器（壳的方言，M1.7 随壳退场）
reflux/wire.py                    出帧层：accrete 的八个 action + draw 信封（新页的方言）
reflux/server.py / demo.py        伺服（挂载表：前缀 → 目录；无缓存、同源）＋ /ws 升级
reflux/channel.py                 WS 端点：升级 + 文本帧编解码（stdlib）
reflux/events.py                  事件名注册表：注册期报错、未注册拒收计数
reflux/app.py                     应用：两个挂载（壳在 /、新页在 /__next/）+ /ws + 注册表 + 一页钩子
reflux/demo_app.py                示例应用（T4 的门用它；T9 的种子）
reflux/routes.py                  路由表：声明（Route）、一次匹配（Match）、择优键、发现
reflux/cli.py                     `python3 -m reflux.cli routes <pkg>` 打印注册表
schema/accrete.schema.json        fluxen 导出物的快照（sha256 与导出命令记在 schema/README.md）
profile/profile.json              reflux 的 profile：选择、默认、class 令牌表（里面没有类型定义）
tools/sync_schema.py              重新导出并逐项对拍（要 fluxen 那个仓；不进默认门）
tools/gate_m1_1.py                M1.1 门：入口把手的探针页（fluxen 的 dist + App 伺服 + CDP；同样要那个仓）
tools/gen_sdk.py                  schema + profile → 下面两件产物；--check 做漂移门
reflux/sdk/types.py               ← 生成：每个线类型一个类 + discriminated 的 Accrete／Bind
reflux/sdk/builders.py            ← 生成：暴露类型的构造器（签名与默认来自 schema）
reflux/sdk/_parse.py              手写：parse／dump 边界与 bind 条目组装
reflux/sdk/profile.py             手写：读 profile/profile.json
www/index.html                    页面：静态；`#main` 钉通道与编码，资源走 /static/ 绝对路径
www/static/reflux.css             框架自己的样式表（今天只藏两个保留标记）
www/static/reflux.js              客户端 runtime：两个标记的镜像、hello、popstate（约 90 行）
www/static/vendor/fluxen/         钉版本的渲染器包：versions.json + js + wasm + assets/*.css
www/static/vendor/fluxen/versions.json  ← 资产清单：rev、逐文件 sha256 与大小（升版只改这里）
tools/gate_t0_next.py             T0′ 门：请求清单 == 清单、逐件哈希（过 HTTP）、深链、壳仍在 /
tools/gate_t6_next.py             T6′ 门：门自己当生产者画页，断言镜像/历史/后退/深链/无标记
tools/gate_t2_next.py             T2′ 门：八个 action 各一条 DOM 断言 + 域外 position + empty + 零错误
tests/test_wire.py                八种 action 形状逐字对表 + 四类拒收（指针/position/op/节点）
shell/index.html + js/main.js     静态壳：import map 加载 vendored SolidJS，无编译
shell/js/interp.js                壳的 store 与四个操作（T2）
shell/js/validate.js              节点与取值域校验：不合词表的帧整帧拒收（T3）
shell/js/render.js                组件分派表 + 本地态 + source 读槽（T3/T4）
shell/js/events.js                委托监听：认领规则、payload 收集、上行帧（T4）
shell/js/channel.js               壳的通道：连上即 hello，下行交解释器（T4）
shell/js/nav.js                   壳的导航：拦截同源点击、写 history、popstate 发同一种请求（T6）
shell/css/main.css                壳自己持有的设计语言：层序 theme/base/layout/element/custom/style
                                  （框架与 fluxen 的 ui-assets 样式一致），变体走 data 属性改指令牌
shell/vendor/solid-js/            钉版本的四个 ESM 文件（sha256 记在 shell/VERSIONS）
tests/                            规格漂移、两边词表一致、边界校验、签名形状、资产哈希、
                                  事件注册表、通道编解码、写入层、路由（含 route_fixture 样例包）、
                                  应用侧页面解析、新页面的清单与挂载规则（test_page）
```

Python SDK 就是这个仓的 `reflux/` 包，别的语言日后落在 `sdks/<lang>/`。

上表里**要退场的一组**（M1）：`spec/components.json`（词表来源换成 accrete 的 schema）、`shell/*`（壳本体、它的生成物、vendored SolidJS、壳自己那份 CSS）、`tools/gen.py` 里生成壳分派表的那一半。留下的是框架那一半：`reflux/` 的路由、会话、通道、伺服、应用，加生成器的构造器逻辑——输入换掉，逻辑不动。

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

## T3 门的实测结果（2026-10-15）

```
[1/16] PASS  zero console errors                    none
[2/16] PASS  spec == implementations                21 components, missing=[] extra=[]
[3/16] PASS  create renders the tree                root=True text='initial'
[4/16] PASS  one patch = one mutation, no element churn mutations=1 kinds=['childList'] churn=False text='patched'
[5/16] PASS  siblings keep their DOM nodes          {'card': True, 'input': True, 'button': True}
[6/16] PASS  slot write: zero DOM mutations, one reader updated mutations=0 value='from slot'
[7/16] PASS  local state survives a store write     value='typed by hand'
[8/16] PASS  unknown component: frame refused whole rejected+1 title='看板'
[9/16] PASS  bad attr value: frame refused          rejected+1 err='.../attrs.tone: "purple" outside [...]'
[10/16] PASS  create again: one root, nothing unsupported roots=1 unsupported=0
[11/16] PASS  layer order declared first             '@layer theme, base, layout, element, custom, style;'
[12/16] PASS  theme tokens applied to a component    border=1px radius=8.8px scheme='light dark'
[13/16] PASS  tone re-points one token, per component danger=oklch(0.55 0.18 25) plain=oklch(0.28 0.02 260) ...
[14/16] PASS  gap is a data attribute, not an inline style lg=16px sm=4px
[15/16] PASS  a datum rides its custom property      token='50%' ratio=0.500
[16/16] PASS  rack shows its empty state when it has no rows visible=True text='还没有记录'
```

第 4 条是这里最硬的一条：一次文本 patch 在 DOM 上就是**一条**变更记录，且记录里没有元素节点
进出——兄弟组件连 DOM 节点对象都是原来那个。第 6 条说明槽写连一条变更都不产生（`input.value`
是属性不是 attribute），只有读它的那个组件动了。

落地的形状：`shell/js/render.js`（21 个组件的实现表、子节点按行 id 复用、本地态）、
`shell/js/validate.js`（节点与取值域校验）、`shell/css/main.css`（层序 + 令牌 + 组件外观，框架取自 fluxen
的 ui-assets 样式：变体是 data 属性改指令牌，数据值走自定义属性，壳不写内联样式）、`tools/gate_t3.py`。

样式那六条断言（11-16）是这一轮加的：层序那一行必须先出现（层序由首次出现决定，写错位置整份样式都会
错位），令牌要真的落到组件上（`border=1px`、圆角来自 `--rx-round`），tone 要真的逐组件改指（danger 的
文字色与 default 不同、两种 badge 底色不同），间距刻度要走 data 属性，进度条要真的吃到自定义属性，
空列表要真的显示 `empty_text`。

`rack` 的 `empty_text` 与 `follow: end` 这一轮补上了实现（空态元素 + 贴底滚动）。规格里的
`input.clearable` 当时是有校验、无外观的属性；到 T4 按「壳无法兑现的属性是规格缺陷」把它从规格里收窄掉了——
清除控件要给叶级替换元素加外壳，那是一次形状变更，不是加一个属性（记在 DESIGN 的开放问题里）。

门抓到的三件事：

- **`render()` 只求值一次**：Solid 运行期是 `insert(element, code(), ...)`——传进 `render` 的那个函数
  不算响应式，被它**返回**的函数才算。壳的「有树画树、没树画探针」因此写成柯里化形式；否则
  `create` 之后 store 明明变了（观察者实测重跑一次），DOM 还停在探针上。
- **容器需要有身子**：子节点是按 `host.children[i]` 落位的，而卡片的标题是先塞进去的 chrome，
  两边抢第 0 位。正形是子节点挂进一个 `.rx-body`（`display: contents`，布局透明），chrome 相对它
  定位——卡片标题在前、表单提交键在后。`select` 是唯一例外（只吃 option，所以 `bodyIsHost`）。
- **取值域校验要能定位**：patch 写的是 `/tree/.../attrs/tone`，值本身不是节点，单看值判不出合法与否。
  `validateFrame(ops, tree)` 拿当前树把路径解到那个节点、取出该组件的域来判；`slots` 下的路径不碰
  （那里是自由数据）。

`select` 的规格同时收窄：去掉 `placeholder` 属性——空选项就是一个普通 `option` 子节点，由生产者送，
壳不合成（规格的约定里记了这条）。

## T4 门的实测结果（2026-10-16）

```
[1/13]  PASS  zero console errors                    none
[2/13]  PASS  hello first (with its path); structure after
                                              first recv='reflux:hello' path='/' first send op='create'
[3/13]  PASS  a rack mounts its rows from the slot   dom rows=2 slot rows=['row-1', 'row-2']
[4/13]  PASS  input echo: type → commit → the producer's slot write comes back
                                              frame={'event': 'name.change', 'id': 'name-input', 'data': {'value': 'alice'}}
[5/13]  PASS  a keystroke is not a turn        frames while typing: 0
[6/13]  PASS  payload is verbatim              keys=['value'] frame keys=['data', 'event', 'id'] id='name-input'
[7/13]  PASS  list add: producer inserts, the row keeps its DOM node
                                              frame={'event': 'row.add', 'id': 'add-row', 'data': {}} rows=3 identity kept=True
[8/13]  PASS  list remove: the frame carries the row's own id
                                              frame id='row-2' rows=2 removed in dom=False
[9/13]  PASS  form: one submit carries every field it holds
                                              frames=1 fields={'user': 'alice', 'pass': 's3cret'} keys=['fields']
[10/13] PASS  payload declared as two keys arrives as exactly two
                                              data={'value': 'abc', 'focus': False} order=['value', 'focus']
[11/13] PASS  unregistered event name: uplinked verbatim, refused, never dispatched
                                              frame=[{'event': 'ghost.press', 'id': 'ghost', 'data': {}}] refused+1 handlers+0
[12/13] PASS  after a refusal the session still works    row.add frames=2 sessions=1
[13/13] PASS  every uplink frame is exactly {event, id, data}   7 frames
```

驱动方式是真交互：`Input.dispatchMouseEvent` 点进输入框、`Input.dispatchKeyEvent` 逐字敲、点别处失焦触发
`change`；断言读的是**过 socket 的帧**（生产者 `app.log`），不是页内的桩。

落地的形状：`shell/js/events.js`（委托监听与上行）、`shell/js/channel.js`（壳的通道）、`reflux/channel.py`、
`reflux/events.py`、`reflux/app.py`、`reflux/ui.py` + `reflux/ops.py`（写入层）、`reflux/demo_app.py`、
`tools/gate_t4.py`；`tools/cdp.py` 加了真鼠标/真按键夹具，壳改由 App 伺服（T0/T2/T3 跟着走这条，它们照旧直接
drive `window.reflux`）。

门抓到的六件事：

- **真输入暴露了夹具的盲区**：默认无头窗口是 800×600，演示页比它高——第 8 行的探针行在折叠线以下，点击落在
  视口外（`document.activeElement` 仍是 `body`），于是敲键无处可去、`change` 自然不响。页内 `dispatchEvent`
  的写法会「通过」这一条。夹具改成 `--window-size=1280,1600` 且点击前先 `scrollIntoView`。
- **帧到了不等于画了**：表单那条断言最初在帧一到达就读 DOM，于是同一份代码一次绿一次红。断言必须等它要断言的
  东西（这里等回显/摘要在 DOM 里出现），等帧只说明生产者收到了。
- **等一个被旧状态满足的条件等于没等**（T5 轮的全套跑动抓到）：「拒收之后会话照常工作」那条写的是
  `wait(lambda: received(app, "row.add"))`，而前一条检查早就收过同名帧——wait 立即返回，断言在第二帧到达
  之前就判了。等新事件要等**增量**（`len(...) > before`）。
- **`register(name)` 只是拿装饰器**：门里写 `events.register("probe.change")` 没给处理器，等于什么都没注册，
  于是探针事件被判未注册拒收。注册表的行为是对的（日志里逐字写着未注册），错的是调用方——门里改成显式传处理器。
- **壳会上行未注册的名字，拒收在生产侧**：这一条最初写成「没有帧上行」，是错的预期——壳不可能知道生产者的
  注册表，所以帧照发，由生产者拒收并计数。断言改成：这一帧逐字过 socket、注册表拒收、处理器一次都没跑。
- **`code` 组件的双写**（T3 遗留）：外层元素上挂的 `value` 效果会在槽写入时把里面的 `code` 子元素抹掉。
  让 `source` 真的读槽时它露了出来；现在 `code` 直接建自己的内层，不再走 `textish`。

## T5 门的实测结果（2026-10-16）

```
Ran 29 tests ... OK          python3 -m unittest tests.test_routes（表驱动，无浏览器）
Ran 77 tests ... OK          全套（原 48）
[gen] up to date: spec v0.2.0, 21 components, 3 artifacts
T0 GATE PASSED   T2 GATE PASSED   T3 GATE PASSED   T4 GATE PASSED
```

`python3 -m reflux.cli routes tests.route_fixture` 的输出：

```
[routes] imported 3 module(s) from tests.route_fixture
path               source                           metadata
/                  tests.route_fixture.blog
/admin             tests.route_fixture.admin        title='后台'
/blog/{rest:path}  tests.route_fixture.blog         title='兜底'
/blog/{slug}       tests.route_fixture.blog         title='文章'
/posts             tests.route_fixture.blog
```

落地的形状：`reflux/routes.py`（`Route` 一条声明、`Match` 一次匹配、`Routes` 表；
`compile_path` / `rank` / `can_both_match` / `match_segments` 四个纯函数；`discover` 导入给定包并遍历
子模块，一个模块导入失败即启动错误；默认表 `DEFAULT` 与挂在它上面的 `route`）、`reflux/cli.py`（`routes`
动词，打印路径、来源模块、元数据字段）、`tests/test_routes.py`（29 例）、`tests/route_fixture/` 与
`tests/route_fixture_broken/`（后者有一个导入即失败的模块，专供「不跳过」那条断言）。

**路由这一层第一跑就绿**（29/29），没抓到设计缺陷——表驱动把每一形状都写成了案例，包括「换 import 顺序
匹配结果逐例一致」和「两个都能匹配同一路径且择优键相同 ⇒ 启动即报错」。`reflux events` 那一栏推迟到 T9，
理由记在 DESIGN 的路由节（打印事件表要先有「从包装配出应用」的约定，路由表不需要）。

## T6 门的实测结果（2026-10-16）

```
[1/12]  PASS  zero console errors                    none
[2/12]  PASS  cold start: hello carries the deep link, that page is drawn
        hello={'path': '/about', 'token': None} session.path='/about' location='/about' headings=['关于']
[3/12]  PASS  a link click is a request, not a page load
        nav frames=1 hellos=1 sessions=1 mark='alive' location='/'
[4/12]  PASS  address bar, page and server-side route agree
        session.path='/' location='/' route='/' last nav={'path': '/'}
[5/12]  PASS  a page turn carries its slot seed in the same frame    rack rows=2
[6/12]  PASS  back: the previous page, the same request    location='/about' headings=['关于'] nav frames=2
[7/12]  PASS  forward: the page again, one more request    location='/' headings=['演示'] nav frames=3
[8/12]  PASS  a ctrl-click is not intercepted        nav frames+0 location='/'
[9/12]  PASS  a querystring link: the address keeps it, the frame does not
        location='/about?x=1' nav={'path': '/about'}
[10/12] PASS  unknown path: the built-in 404 structure, nothing else moved
        location='/nope' headings=['404'] sessions=2 (was 2) session.path='/nope'
[11/12] PASS  a registered {rest:path} answers instead of the 404    headings=['兜底'] location='/nope'
[12/12] PASS  every nav frame is exactly {event, data:{path}}    6 frames
```

落地的形状：`shell/js/nav.js`（拦截判据、URL 真变才 pushState、popstate 是同一个请求）、`shell/js/main.js`
（挂上导航，对开发回路露出 `navigate`）、`reflux/app.py`（`page(session, path)` 钩子、`App.routes`、
`reflux:nav` 与 hello 走同一条、内置 404、`view` 退休）、`reflux/demo_app.py`（长出 `/` 与 `/about` 两条路由
和一对链接）、`reflux/server.py`（页面路径交给壳）、`tools/gate_t6.py`、`tests/test_app.py`（10 例离线：页面
解析、内置 404、尾兜底、钩子覆盖、demo 的帧形状）。

门抓到的三件事：

- **深链在门里根本起不来——伺服进程把 `/about` 当文件**：没有这个文件就 404，壳没机会启动。这是真漏项：
  设计写了「冷启动直接打开 `/blog/x` 落在该页」，却没人规定伺服那一侧做什么。规则现在是「无扩展名且无对应
  文件 ⇒ 回 `index.html`；有扩展名仍按文件处理（缺文件就是 404），绝不回一坨 HTML 冒充模块」。
- **Ctrl+点击真的开了新标签页**，那个标签页自己也会连上来 ⇒ 多一个会话。于是「未知路径不改会话」不能写成
  「会话数 == 1」（它被前一条检查合法地改掉了），要写成「这一击没有新增会话 + 原来那个还在、路径跟着客户端走」。
- **地址栏先变、页面后到**：带查询串那条最初在 `location.search` 一变就断言，读到的是上一页的标题——还是
  「等你要断言的东西」，这里要等的是 DOM。

`reflux events`、重定向、路由中间件与数据 loader 仍按 DESIGN 的开放问题挂着，不在这一轮。

## T7 门的实测结果（2026-10-16）

```
[1/4] PASS  a connection is one session, standing where its hello said
      issued=1 live=1 path='/'
[2/4] PASS  a reload leaves exactly one session    issued=2 reclaimed=1 live=1
[3/4] PASS  a connection registers a session       live=1
[4/4] PASS  a deaf client is judged dead and the table empties live=0 dead=1 reclaimed=0
```

[1]/[2] 走真浏览器（起壳、读表、`Page.reload`、再读表，用默认心跳所以没有竞速）；[3]/[4] 走 stdlib 客户端，
心跳参数缩到 0.1s / 0.3s——那条客户端读完 hello 就不再应答、也不发 FIN。

落地的形状：`reflux/app.py`（会话表按**连接身份**键、`handle` 登记与回收、`watch()` 一次判死扫描、心跳线程、
计数、读快照的 `App.live()`）、`reflux/channel.py`（`last_seen`、写锁、`ping()`、`abort()`、`JUDGED_DEAD`）、
`shell/js/channel.js`（hello 不再带 token）、`tests/test_session.py`（5 例，除心跳线程那例外都不给时钟——直接
调一次 `watch()`）、`tools/gate_t7.py`（4 条，两段时钟）。

这一轮改了三件设计：

- **token 与 cookie 一起退场**（裁决）：会话就是连接，socket 本身就是持续连接，没有跨连接要搬的状态；身份改成
  连接上的一个 `login` 事件（对外部署才需要）。原第三条门槛「伪造 token 只开新会话」随之退休——没有 token
  就没有可伪造的东西。
- **判死要真的能回收线程**：只写一个 close 帧唤不醒阻塞在 `read` 上的连接线程，所以 `Channel` 拿到了 socket
  并多一个 `abort()`（`shutdown`）。没有这一条，「会话表归零」只是表上的归零，线程还挂着。
- **判死与断线不能计两次**：判死那条先出表、再记账——否则被 `shutdown` 唤醒的读线程可能抢先删掉，同一个会话
  同时算 `dead` 和 `reclaimed`。`[4/4]` 里的 `reclaimed=0` 就是这条的断言。

门还抓出一处我漏判的影响面：**T4 与 T6 直接按列表下标读会话表**（`app.sessions[0]`），表换成身份键的 dict
之后两门当场 `KeyError`。修法是给应用加一个读快照的 `App.live()`，两门改用它——门不该依赖容器的形状。

## T8 门的实测结果（2026-10-16）

```
[1/6] PASS  a connection registers a session       live=1
[2/6] PASS  bad JSON / unknown name / no event / raising handler: four refusals, one per frame
      refused +4 traceback=True session answered
[3/6] PASS  the producer refuses before the wire sees it: over the cap, duplicate row id
      cap=True duplicate_id=True
[4/6] PASS  a client that stopped reading sheds frames and holds nobody else
      shed=8 resync=0 other session answered=True
[5/6] PASS  an oversized frame is refused whole    rejected=0->1 tree 1935->1935
[6/6] PASS  an unreadable declared payload refuses the uplink instead of sending a hole
      rendered=True uplink.refused=1 sent=0 note=True
```

[1]–[4] 离线（真 socket + stdlib 客户端），[5]–[6] 真浏览器。[4] 里 `resync=0` 是这条检查的真实结果：真
socket 的内核缓冲把 8 帧都收下了，队列没停在排空状态，所以没触发重同步——那条路（丢帧 → 陈旧 → 排空后一帧
`create`）由 `tests/test_failure_modes.py` 用会阻塞的假 channel 确定性地测（断言 `stats["resync"] >= 1`），
门这一条证明的是**隔离**：慢的那个客户端没能按住别人的帧。

落地的形状：`reflux/app.py`（`Session.outbox` 入队时有界、丢中间帧标 `stale`、`_pump` 每会话一条写线程、
`flush_session` 排空后写一帧重同步、计数 shed/resync）、`reflux/channel.py`（`_take` 把 RST 归成
`ChannelClosed`）、`shell/js/events.js`（载荷声明的键在 locals 里取不到就拒发 + `onRefuse`）、
`shell/js/main.js`（`uplink.refused`）、`shell/js/validate.js`（一帧超过上限整帧拒收）、`reflux/ops.py`
（`draw` 上：上限与"一帧之内每个节点数组 id 唯一"）、`spec/components.json` 与生成物（`max_ops_per_frame:
1024`，一处定义两边用）、`tests/test_failure_modes.py`（5 例）、`tools/gate_t8.py`（6 条）。

这一轮改的设计，都是门顶出来的：

- **写线程改成每会话一条**。第一版是"一条共享 flusher 遍历所有会话"，门当场顶住：慢客户端把那条共享线程按在
  它自己的 `send` 里，别的会话的帧就卡住了——而"别的会话不受影响"正是这一条要保证的。写是唯一会被客户端拖住
  的一步，所以它必须是每会话自己的线程。
- **队列在入队时有界**，不是由写线程事后裁剪：写线程阻塞时它自己都不会再跑，事后裁剪等于没有上限。
- **上限进规格**（`max_ops_per_frame`）而不是两侧各写一个常量：壳与写入层读同一份，改一处两边同时动。
- **id 唯一性检查放在 `draw`**（帧级规则），不是每个建造器各查一遍：一支 op 还没成帧，谈不上"同一帧里唯一"。
- **RST 与正常关闭归成同一条账**：门第一次跑时，客户端 `close()` 让服务端读线程把 `ConnectionResetError`
  抛到了 socketserver，打出一大坨 traceback——突然消失是正常情况，不是异常；现在是 `ChannelClosed`，会话照常
  回收并计数。

## M1.1 门的实测结果（2026-10-19）

```
[1/5] PASS  the renderer mounts into #main         children=yes
[2/5] PASS  the socket lands on the host's path and codec urls=['ws://127.0.0.1:38233/ws?codec=json']
[3/5] PASS  the page-level handle reaches the producer frame={'event': 'probe', 'data': {'v': 1}}
[4/5] PASS  a call before the socket opened is not lost frame={'event': 'early', 'data': {'at': 'before-open'}}
[5/5] PASS  zero console errors                    none
```

驱动的形态：探针页（`#main` 带 `data-codec="json"`／`data-path="/ws"`，一段 module 脚本 await 完
`init()` 就调把手）与渲染器 dist 的三件资产在临时目录里拼起来，由 `App` 伺服（`/ws` 是它自己的通道），
`tools/cdp.py` 驱动 chromium。断言读的是**过 socket 的帧**（`app.log`）与 `Network.webSocketCreated`。

落地的形状：fluxen `crates/ui_leptos/src/lib.rs`（入口多读 `data-path`／`data-codec`；挂载后发布
`window.fluxen.send`，走 `Ctx::send`——与 canvas 的 `host.send` 同一条腿）；reflux `tools/gate_m1_1.py`。

门抓到的一件：**装配要留在 `mount_to` 的闭包里**。第一版把 transport 与 `Ctx::new` 提到 mount 之前
（外面只留 `ctx.clone()` 去发布把手），页面白屏、`#main` 空着，控制台一条
`spawn_local before a global executor was initialized`——`Ctx::new` 的读循环要 Leptos 的 executor。
修法是把装配搬回闭包，发布那行跟着进去。

M1.2 落地后这道门改了取材：探针页围绕**仓里钉住的**那份包拼（`www/static/vendor/fluxen/`，名字按
`versions.json`），不再读兄弟仓——渲染器升级把它弄丢了，这道门就会红。

## M1.2 门的实测结果（2026-10-19）

```
[1/7] PASS  the page boots under its prefix         #main children=1
[2/7] PASS  zero external requests                  7 requests, all same-origin
[3/7] PASS  the request set is exactly the pinned set extra=[] missing=[]
[4/7] PASS  every served byte matches its pinned sha256 4 assets
[5/7] PASS  the retiring shell still owns /        shell at /, page at /__next/
[6/7] PASS  a deep link under the prefix gets the page #main children=1
[7/7] PASS  zero console errors                    none
```

离线那一半：`python3 -m unittest tests.test_page`（13 例）——清单 ↔ 磁盘 ↔ 页面的三方对拍，加挂载规则
（前缀、深链、裸前缀 301、缺文件 404）。

落地的形状：`www/` 是页面树、`www/static/` 是资产树，挂载表 `/__next/` → `www/`、`/static/` → `www/static/`
（`reflux/server.py` 按前缀表匹配、最长前缀优先；只有基础挂载必须有 `index.html`）。`versions.json` 是资产
清单（rev + 逐文件 sha256／大小），页面从它读 js/wasm 的名字。门的请求清单、逐件哈希、离线测试对着同一份清单。

门抓到的两件：

- **相对路径在深链上必死**：第一版页面写 `./vendor/…`，`/__next/` 正常、`/__next/blog/a/post` 白屏——
  `fetch("./vendor/fluxen/versions.json")` 解析到 `/__next/blog/a/post/vendor/…`，服务端按「无扩展名 → 页面」
  回了 HTML，控制台是 `Unexpected token '<'`。修法是资源一律源站绝对路径（`/static/…`），顺带让 M1.7 只改挂载表。
- **资产挂载没有 `index.html`**：`make_server` 原来要求每个挂载都有页面，`/static/` 当场起不来。规则改成
  「只有基础挂载必须有页面」——资产前缀下的页面路径 404，这才是诚实答案。

计划里改了两处形态（判据）：页面树从 `reflux/page/` 挪到 `www/`、资产放 `www/static/`（页面与资产是两个挂载，
一棵树装不下两件事，两棵树又要给服务器加一条回退链）；「装配时填模板」改成「静态页 + `versions.json`」
（模板会造出只在伺服时存在的第二种页面形态，而清单让名字只有一个来源）。

体积：4 件资产 2 420 114 B（wasm 2 348 320 B）；当时一次开页 7 条请求（M1.3 把 runtime 加进来之后是 8 条，
见下一节）。

## M1.3 门的实测结果（2026-10-19）

```
[1/8] PASS  the path marker moves the address bar  location=/__next/a history=2->3
[2/8] PASS  the title marker writes document.title title='A'
[3/8] PASS  drawing the same path again adds no entry history=3->3
[4/8] PASS  a page turn pushes exactly one entry   location=/__next/b history=3->4
[5/8] PASS  back is one reflux:nav with the app path frame={'event': 'reflux:nav', 'data': {'path': '/a'}} location=/__next/a
[6/8] PASS  a deep link is one hello with the app path hello={'path': '/deep/link'} location=/__next/deep/link
[7/8] PASS  a page without markers changes nothing location=/__next/deep/link title='Deep'
[8/8] PASS  zero console errors                    none
```

落地的形状：`www/static/reflux.js`（约 90 行，零依赖）——`base` 从 `<base href>` 取，`toApp`／`toBrowser` 是
唯一的换算处；`mirror()` 读两个保留 id，路径不同才 `pushState`；`start()` 先 hello、再挂 `popstate`、再挂只读
MutationObserver（childList／characterData／subtree，`queueMicrotask` 合并）。页面的 bootstrap 在
`await init(...)` 之后 `import("/static/reflux.js")` 并 `start()`。

门自己的形态：**门当生产者**——`App()` 不设 page／routes（hello 不回帧），门等会话出现后用 `sdk.builders`
建页（标记 = `placeholder(b.text(…), id="reflux:path")`）、`dump()` 成线形状、手写一帧
`{"ev":"draw","sender":…,"content":[{"action":"create","event":"","data":…}]}`，收到 `reflux:nav` 再画下一页。
理由：当时出帧层还是退休形状（M1.4 才落地），而「绕过 SDK 手写帧的生产者」是设计明确承认的一类。

这一轮抓到的两件：

- **前缀要在某处换算，而唯一不撒谎的源是 `<base>`**：标记写应用路径，地址栏写挂载后的路径。第一版直接把
  `location.pathname` 当应用路径——在 `/__next/` 上 hello 送的是 `/__next/`，而标记写 `/` 又与地址栏不等，
  于是来回推。改成从 `document.baseURI` 取前缀、换算只在 `toApp`／`toBrowser` 两处；M1.7 只改 `<base>` 一行
  （`tests/test_page.py` 把两者钉在一起）。
- **不看 attributes**：MutationObserver 只观察 childList／characterData／subtree。加上 attributes 的话，输入框的
  class 每次变化都会触发一次镜像读——等于给每一次按键加一趟活。

## M1.4 门的实测结果（2026-10-19）

```
[1/12]  PASS  create draws the layout root           root present
[2/12]  PASS  tmpl expands {{label}} inside create   expanded
[3/12]  PASS  set replaces the node in a data slot   echo='set-value'
[4/12]  PASS  append lands at the tail               rows=['row-1', 'row-3']
[5/12]  PASS  append +1 lands before the last row    rows=['row-1', 'row-2', 'row-3']
[6/12]  PASS  remove drops the row by identity       rows=['row-1', 'row-3']
[7/12]  PASS  patch replace rewrites the pointed value echo='patched'
[8/12]  PASS  patch append extends a string          echo='patched!'
[9/12]  PASS  inject writes the vals plane           local-echo='injected'
[10/12] PASS  an out-of-range position is refused, not clamped rows=['row-1', 'row-3', 'row-4']
[11/12] PASS  empty decodes and changes nothing      rows=['row-1', 'row-3', 'row-4', 'row-5']
[12/12] PASS  zero console errors                    none
```

离线：`python3 -m unittest tests.test_wire`（20 例）——八种 action 的形状逐字对表，加四类拒收（不是指针的
路径、不是整数的 position、未知的 patch op、不是 accrete 的节点）。

落地的形状：`reflux/wire.py`（八个构造器 + `draw(sender, *ops)`；节点走 `parse` → `dump` 的边界；`position: 0`
不写；`created` 不写）。门 `tools/gate_t2_next.py` 自己当生产者：`wire` 组帧、`session.send` 发出，逐条读 DOM。

这一轮抓到的三件（都已改）：

- **生成器的 `list(None)`**：`b.rack(source="rows")` 的 `item` 缺省 `None`，生成的 `item=list(item) or None`
  当场 TypeError。生成器改成 `list(item) if item else None` 并重出（`builders.py` 两行变化）。
- **`text`／`case` 的 id 是 class 不是 DOM id**：`case` 把 id 塞进 class 列表，只有 `placeholder` 一类
  （`rack`／`pages`／`layer`／`fold`／`diagram`／`canvas`）才 `.id()`。门的读数因此按 class 取——这也是「标记
  必须是 `placeholder`」那条的同一个事实。
- **`inject` 落的是 Outflow 形状的包装**：vals 槽里是 `{event, data}`（与页面自己 emit 写入的完全同形），
  订阅方要 `bind.path = "/data"` 才拿到载荷本体。门里那个 local 绑定因此手写了 `path`。