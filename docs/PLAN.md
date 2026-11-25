# PLAN

方向与设计在 `docs/DESIGN.md`，测量数字与口径在 `docs/PERF.md`；本文件是索引——每一轮做了什么、门验的是什么、决定它的是谁。

## 方向

- [x] 壳退休，reflux 转成集成 fluxen 的 web 框架（Next 之于 React 的分工）— 2026-10-16

## 门与迁移（2026-10-15 … 2026-10-20）

- [x] T0 — 真 chromium 起页面：零外部请求、零 console 错误、mount 探针 — 2026-10-15
- [x] T1 — 规格校验器加 16 个测试；写第一版规格时就抓出两处自相矛盾 — 2026-10-15
- [x] T2 — 10 条：`create` 的树与标题、事件回路 — 2026-10-15
- [x] T3 — 16 条：规格与实现逐项对齐，21 个组件无缺无多 — 2026-10-15
- [x] T4 — 13 条：hello 先于结构到达，深链落对页 — 2026-10-16
- [x] T5 — 路由表驱动 29 条，全套 77 条 — 2026-10-16
- [x] T6 — 12 条：冷启动带着深链，那一页被画出来 — 2026-10-16
- [x] T7 — 4 条：一个连接一个会话，刷新之后仍只有一个 — 2026-10-16
- [x] T8 — 6 条：坏 JSON、未知名字、缺事件、抛异常的处理器，四类拒绝各一帧 — 2026-10-16
- [x] M1.1 — 5 条：渲染器挂进 `#main`，socket 落宿主的路径与编解码 — 2026-10-19
- [x] M1.2 — 7 条：页面在自己的前缀下启动，零外部请求 — 2026-10-19
- [x] M1.3 — 8 条：`path` 标记改地址栏，`title` 标记写标题 — 2026-10-19
- [x] M1.4 — 12 条：`create` 画布局根，tmpl 展开，`set` 替换槽位 — 2026-10-19
- [x] M1.5 — 12 条：合法帧原样落地，未知节点类型被拒 — 2026-10-20
- [x] M1.6 — T3-NEXT 18/18：21 个角色的 class 逐个出现 — 2026-10-20
- [x] M1.7 — 退场：`spec/`、`shell/`、`tools/gen.py`、七道旧门全删 — 2026-10-20
- [x] T9 — 参考应用有门：SDK + App + runtime 合起来能不能写出一个应用 — 2026-10-20
- [x] T11 — 测量：四段数字进 `docs/PERF.md`；这一轮不改设计、不加缓存 — 2026-10-20
- [x] T10 — Rust SDK，第二个语言：五帧字节对拍 — 2026-10-20

## 变更记录（2026-10-20 … 2026-11-04）

- [x] 标记糖 `reflux:path` / `reflux:title` 有名字了：第二个消费者到齐才做 — 2026-10-20
- [x] `reflux events`——事件名注册表，目标写法 `module:attr` — 2026-10-20
- [x] `local` 落点与它的 `path` 随行键 — 2026-10-20
- [x] 示例应用 `examples/chat`：第二个使用者，重点在后端与会话态 — 2026-10-20
- [x] 信封退场，渲染器包升级（随 fluxen ADR 0021 决策 6）— 2026-10-29
- [x] 地址叫 `slot`，`event` 只留给名字 — fluxen ADR 0022 — 2026-10-29
- [x] 上行目标叫 `dest` — fluxen ADR 0023 — 2026-10-29
- [x] 渲染器包不入库：一个 pin、一个装它的工具、一条发布流水线 — 2026-10-30
- [x] 渲染器跟到 fluxen `92f0a7f`：`Sink{dest}`（ADR 0039）与 `kind` 都在包里了；`main.css` 改名 `core.css`（`vendor.py` 的清单、`www/index.html`、文档一起改）；`prune` 改成整棵 vendor 树扫一遍，改名留下的旧样式表不再躺在那儿被误读 — 2026-11-25
- [x] 按钮不再有出口（fluxen ADR 0039 §2a）：`Button` 去掉 `sink`，它就是它所在 `bundle` 的确认键，按下提交那个组；SDK 的 `button()` 不再收 `sink`，闭包落点搬到持有出口的 `bundle` 上（示例、测试、T10 的 Rust 帧、`types_fixture` 同步）— 2026-11-25
- [x] 渲染器钉到 `6882ce4`：`Button.sink` 删掉之后重打、发了 `renderer-6882ce4`，`tools/vendor.py fetch` 端到端跑通，本地 vendor 树与发布件逐字节一致 — 2026-11-25
- [x] `renderer-92f0a7f` 的 release 资产已发布，`tools/vendor.py fetch` 端到端跑通（装的是发布件，本地 vendor 树与它逐字节一致）— 2026-11-25
  同一 rev 两次构建不是逐字节可复现：js 相同（sha `fdc85bbe…`），wasm 差 8 KB（2,858,761 vs 2,867,046 B）。发布件为准——本地已换成发布件，十道门在它上面全绿
- [x] 地址带查询串、内置 `connect`/`disconnect`、后端可加的 location 事件、`routes` 槽 — 2026-11-03
- [x] 一个连接是一台设备，而通道是一条路由 — 2026-11-03
- [x] 示例照框架文档的样子写：一个 app，一串装饰器 — 2026-11-03
- [x] 一个应用，一个页面一个文件：概览 + 对话 — 2026-11-03
- [x] 重画归设备：`device.draw()` 与 `device.go(url)` — 2026-11-04
- [x] 示例里挂一个自己的 HTTP 接口（`/status`）— 2026-11-04
- [x] 事件驱动这一侧不返回：处理器拿 `ctx` — 2026-11-04
- [x] 走查页进了参考应用：`examples/zh/demo_app.py` 声明外框与三页，`/demo` 播 fluxen 的 walkthrough（一域一槽、悬浮按钮四态、播放按连接），首页重排成卡片；`token_attrs` 的 `class` 键位按 schema 归位，Rust 夹具随之对齐（`gate_t10` 逐字节相等）— 2026-11-24
- [x] 示例应用收成一个：`examples/app` 删除，对话页搬进参考应用成为 `/chat`（`examples/zh/demo_chat.py` + `examples/zh/chat_model.py`），`/status` 一并进 `demo_app`；`gate_chat`、`test_chat_example`、`test_example_status` 改指新页，`gate_dashboard` 删除（图表/3D 由 `gate_demo` 覆盖）— 2026-11-24
- [x] 示例分成中英两棵树：`examples/zh` 与 `examples/en` 是同一个参考应用写了两遍（界面、注释、函数文档同语言），各有自己的 `Routes()` 因而能同时起服务；页面改由 `register(app)` 以调用式声明路由（避免 `-m` 下的循环 import），`reflux.cli routes` 先找模块里的 `app`；新增 `tests/test_two_trees.py` 六例（结构逐节点相同、两树语言互斥）— 2026-11-24
- [x] 闭包落点：`sink=fn` / `sink=gated(fn)` 在绘制时被命名（`<路径>.<函数名>`，按函数身份去重），登记在设备上，换页换表；`@app.on` 保留给名字须先于绘制存在的情形（多来源、行的身份、框架动词、跨页事件）。参考应用首页的回声/加行/私密改成闭包，✕/落点/导航仍是名字，并在页面文案里点明界线；`tests/test_landings.py` 十例钉机制 — 2026-11-24
- [x] 词表构造器改名 `h`（`reflux/sdk/h.py`，`from reflux.sdk import h`）：属性式 `h.frame(...)` 是人写页面的写法，`h.node(('frame', props, children))` 是数据式（元组/列表进、节点出，props 仍走构造器签名）；示例与测试 464 处调用点改名，走查页的 pin chip 改用数据式演示，`tests/test_h.py` 八例 — 2026-11-24
- [x] 计数器页 + 槽视图：`examples/{zh,en}/demo_counter.py`（装饰器写在 `register(app)` 里、闭包落点、列表槽、状态挂 `ctx.data`、步长输入带解析）；`app.view(name, render)` 让槽写入收值（节点原样通过），`reflux/slots.py` 的 `frame()` 读这条规则；`tests/test_counter.py` 十四例 + 浏览器探针 `tools/probe_counter.py` 验一次真实点击 — 2026-11-24

## 输入统一进 bundle（2026-11-24，已落地）

fluxen `2ee6c13`「a send has a budget, and the fields have an aftermath」把这件事做成了两条，本仓跟着落地：

- **字段没有自己的出口了**（ADR 0032 §2 重写）：`tag` 是成员身份，没有 `tag` 的 `input`/`select` 不上行；字段的 `sink` 只表示**本地落点**（`scope: local`，值一变就写），`remote`/`both` 又没有 `tag` 的，渲染器记一条警告并丢掉。清空不再由字段做。
- **组多了两件事**：`attrs.reset`（`keep` 缺省 / `clear` / `default`，发完之后字段变成什么）与 `attrs.sends`（发几次：缺省或 `-1` 不限，`0` 从第一帧就锁住）。

因此本仓的决定（已定）：

- **组的载荷永远是打包对象**，没有裸值特例。单字段的组发 `{tag: value}`，处理器自己取值。
- **字段的 `tag` 拒绝，不生成**：一个带 `remote` sink 却没有 `tag` 的 `input`/`select` 是"没人收的值"，`parse()` 在构造那一行就 `ValueError`，消息里说清楚"给它一个 `tag`，把 `sink` 放到组上"。不自动从 `id` 推（那会把 UI 标识变成 wire 契约）。组自己的键仍按 `bundle_key` 回退到 `id` —— 那是嵌套组的名字，性质不同。
- `type` 没有挪成字段属性：fluxen 保留 `Bind.type`（`sink.type` 或 `source.type`，两channel都读），所以本仓不动。

落地的清单：

- [x] `schema/accrete.schema.json` 同步到 fluxen 的导出（`tools/sync_schema.py --write`：`BundleAttr` +`reset` +`sends`，新增 `$defs.ResetMode`），`tools/gen_sdk.py`、`tools/gen_rust.py` 重新生成 —— `h.bundle(..., reset=…, sends=…)` 由此出现。
- [x] `reflux/sdk/_parse.py`：`parse()` 先跑 `_check_uplinks`，拒绝"remote sink 且无 tag"的字段；本地落点（`scope: local`）仍合法，无线框的值也仍合法。
- [x] 两棵树的独立输入进组：`demo_app.py` 的回声输入 → `h.bundle(h.input(tag="name"), sink=echo, submit=["enter"])`，`echo` 读 `value["name"]`；`demo_counter.py` 的步长输入 → 同样的组，`set_step` 读 `value["step"]`；两个处理器都只认打包对象（不认识的东西给空串/报错，不当裸值用）。
- [x] 聊天页的发送组加 `reset="clear"`：发完输入框自己清空，这是 fluxen 这次给的能力，也是那个页面本来该有的样子。
- [x] 测试与夹具：`tests/test_sdk_generated.py`（带 `tag` 的字段、拒绝无 `tag` 的 remote sink、本地落点仍合法）、`tests/types_fixture.py` 的 `input` 条目补 `tag`、`tests/test_counter.py` 的载荷改成 `{"step": "5"}`。
- [x] 门与文档：t0/t2/t3/t4/t6/t7/t9/t10/chat/demo 全绿（t4 改成断言"无 `tag` 的字段回车什么都不发、也不清空"，t10 的 Rust 夹具按新签名与新页面同步）；README 的 SDK 段、`docs/DESIGN.md` 的 ADR 0032 段落写了这条规则，`gen_sdk.py --check` 在同步态。
- [ ] **字段上的 `sink` 要删**（决定已落，实施在 fluxen）：`Input`/`Select` 仍带 `sink`，而 ADR 0032 §2 让它只剩两种借道用途——`type`（`widgets/input.rs` 的 `sink.type`，读侧 `source.type` 亦可）与"不进组字段的本地落点"（开关点击、过滤框击键）。决定与理由写在 fluxen `docs/decisions/0032-a-bundle-packs-fields.md` §2 末段（"The field's `sink` itself is going, too"，2026-11-24），工单 scratch **#470**。本仓随之要做的只有删除：`reflux/sdk/_parse.py` 的 `_check_uplinks` 与 `tests/test_sdk_generated.py` 里那条拒绝用例、`tests/test_auth.py::TheLoginSurface`（密码框不再需要 `source=Bind(type=…)` 借道），以及各处 `h.input(tag=…, source=Bind(type=…))` 收敛成字段属性——等 fluxen 的 schema 到位再动。
