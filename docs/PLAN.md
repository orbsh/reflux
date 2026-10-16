# Reflux — 实施状态

任务清单与理由在 [`DESIGN.md`](DESIGN.md)（「实施计划」一节）。本文件只记**状态**与**复验命令**——
一条任务没跑过它的门槛命令，就不算完成。

| 任务 | 状态 | 复验 |
|------|------|------|
| T0 骨架与零工具链证明 | ✅ 2026-10-15 | `python3 tools/gate_t0.py` |
| T1 规格（规格 → 壳表 + SDK，无漂移） | ✅ 2026-10-15 | `python3 tools/gen.py --check` ＋ `python3 -m unittest discover -s tests -t .` |
| T2 壳的 store 与解释器（四个操作、路径寻址、槽订阅） | ✅ 2026-10-15 | `python3 tools/gate_t2.py` |
| T3 组件分派与本地态（21 个组件、规格↔实现相等、变更计数） | ✅ 2026-10-15 | `python3 tools/gate_t3.py` |
| T4 绑定与事件（source / event / payload / fire、委托监听、通道与上行帧、拒收） | ✅ 2026-10-16 | `python3 tools/gate_t4.py` |
| T5 路由（装饰器与注册器、发现、择优键、并列歧义、CLI 打印） | ✅ 2026-10-16 | `python3 -m unittest tests.test_routes` ＋ 全套 |
| T6 导航 | ⏳ | — |
| T7 会话与心跳 | ⏳ | — |
| T8 故障注入 | ⏳ | — |
| T9 Python SDK（demo 应用跑通四类交互） | ⏳ | — |
| T10 第二个语言的 SDK（最小） | ⏳ | — |
| T11 测量 | ⏳ | — |

## 已落地的形状

```
spec/components.json              单一来源：组件/属性白名单/取值域/绑定/上行时机/操作/保留前缀
tools/gen.py                      规格 → 三件产物；--check 做漂移门
tools/gate_t0.py                  T0 门：真起 chromium，经 CDP 断言（stdlib-only）
tools/gate_t2.py / t3.py / t4.py  各任务的门；共用 tools/cdp.py 的夹具（含真鼠标/真按键）
reflux/tables_generated.py        ← 生成：纯数据（壳与各 SDK 共用的词表，含 FIRE_EVENTS）
reflux/components_generated.py    ← 生成：各组件构造器（签名由规格派生）
reflux/node.py                    线上形状 + 校验边界 make()
reflux/ui.py                      写入层：规格词表寻址成一个模块（ui.stack(...)）
reflux/ops.py                     写入层：四个操作与 draw 的构造器（形状在边界校验）
reflux/server.py / demo.py        伺服壳（静态、无缓存、同源）＋ /ws 升级
reflux/channel.py                 WS 端点：升级 + 文本帧编解码（stdlib）
reflux/events.py                  事件名注册表：注册期报错、未注册拒收计数
reflux/app.py                     应用：壳 + /ws + 注册表；收到 hello 发首帧
reflux/demo_app.py                示例应用（T4 的门用它；T9 的种子）
reflux/routes.py                  路由表：声明（Route）、一次匹配（Match）、择优键、发现
reflux/cli.py                     `python3 -m reflux.cli routes <pkg>` 打印注册表
shell/index.html + js/main.js     静态壳：import map 加载 vendored SolidJS，无编译
shell/js/interp.js                壳的 store 与四个操作（T2）
shell/js/validate.js              节点与取值域校验：不合词表的帧整帧拒收（T3）
shell/js/render.js                组件分派表 + 本地态 + source 读槽（T3/T4）
shell/js/events.js                委托监听：认领规则、payload 收集、上行帧（T4）
shell/js/channel.js               壳的通道：连上即 hello，下行交解释器（T4）
shell/css/main.css                壳自己持有的设计语言：层序 theme/base/layout/element/custom/style
                                  （框架与 fluxen 的 ui-assets 样式一致），变体走 data 属性改指令牌
shell/vendor/solid-js/            钉版本的四个 ESM 文件（sha256 记在 shell/VERSIONS）
tests/                            规格漂移、两边词表一致、边界校验、签名形状、资产哈希、
                                  事件注册表、通道编解码、写入层、路由（含 route_fixture 样例包）
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