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
- [x] 按钮不再有出口（fluxen ADR 0039 §2a）：`Button` 去掉 `sink`，它就是它所在 `loom` 的确认键，按下提交那个组；SDK 的 `button()` 不再收 `sink`，闭包落点搬到持有出口的 `loom` 上（示例、测试、T10 的 Rust 帧、`types_fixture` 同步）— 2026-11-25
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

## 输入统一进 loom（2026-11-24，已落地）

fluxen `2ee6c13`「a send has a budget, and the fields have an aftermath」把这件事做成了两条，本仓跟着落地：

- **字段没有自己的出口了**（ADR 0032 §2 重写）：`tag` 是成员身份，没有 `tag` 的 `input`/`select` 不上行；字段的 `sink` 只表示**本地落点**（`scope: local`，值一变就写），`remote`/`both` 又没有 `tag` 的，渲染器记一条警告并丢掉。清空不再由字段做。
- **组多了两件事**：`attrs.reset`（`keep` 缺省 / `clear` / `default`，发完之后字段变成什么）与 `attrs.sends`（发几次：缺省或 `-1` 不限，`0` 从第一帧就锁住）。

因此本仓的决定（已定）：

- **组的载荷永远是打包对象**，没有裸值特例。单字段的组发 `{tag: value}`，处理器自己取值。
- **字段的 `tag` 拒绝，不生成**：一个带 `remote` sink 却没有 `tag` 的 `input`/`select` 是"没人收的值"，`parse()` 在构造那一行就 `ValueError`，消息里说清楚"给它一个 `tag`，把 `sink` 放到组上"。不自动从 `id` 推（那会把 UI 标识变成 wire 契约）。组自己的键仍按 `loom_key` 回退到 `id` —— 那是嵌套组的名字，性质不同。
- `type` 没有挪成字段属性：fluxen 保留 `Bind.type`（`sink.type` 或 `source.type`，两channel都读），所以本仓不动。

落地的清单：

- [x] `schema/accrete.schema.json` 同步到 fluxen 的导出（`tools/sync_schema.py --write`：`LoomAttr` +`reset` +`sends`，新增 `$defs.ResetMode`），`tools/gen_sdk.py`、`tools/gen_rust.py` 重新生成 —— `h.loom(..., reset=…, sends=…)` 由此出现。
- [x] `reflux/sdk/_parse.py`：`parse()` 先跑 `_check_uplinks`，拒绝"remote sink 且无 tag"的字段；本地落点（`scope: local`）仍合法，无线框的值也仍合法。
- [x] 两棵树的独立输入进组：`demo_app.py` 的回声输入 → `h.loom(h.input(tag="name"), sink=echo, submit=["enter"])`，`echo` 读 `value["name"]`；`demo_counter.py` 的步长输入 → 同样的组，`set_step` 读 `value["step"]`；两个处理器都只认打包对象（不认识的东西给空串/报错，不当裸值用）。
- [x] 聊天页的发送组加 `reset="clear"`：发完输入框自己清空，这是 fluxen 这次给的能力，也是那个页面本来该有的样子。
- [x] 测试与夹具：`tests/test_sdk_generated.py`（带 `tag` 的字段、拒绝无 `tag` 的 remote sink、本地落点仍合法）、`tests/types_fixture.py` 的 `input` 条目补 `tag`、`tests/test_counter.py` 的载荷改成 `{"step": "5"}`。
- [x] 门与文档：t0/t2/t3/t4/t6/t7/t9/t10/chat/demo 全绿（t4 改成断言"无 `tag` 的字段回车什么都不发、也不清空"，t10 的 Rust 夹具按新签名与新页面同步）；README 的 SDK 段、`docs/DESIGN.md` 的 ADR 0032 段落写了这条规则，`gen_sdk.py --check` 在同步态。
- [x] **字段上的 `sink` 已经不在 wire 上**（fluxen 侧落地，本仓只跟着删）：`Input`/`Select` 的 schema 现在只有 `source`（`tools/sync_schema.py --write` → in sync，`6b0211c8…`），本仓把为它写的守卫删了——`reflux/sdk/_parse.py` 的 `_check_uplinks` 与只被它用的 `FIELD_TYPES`，`tools/gate_t4.py` 的引言改成"字段在 wire 上没有 `sink` 这个属性，所以带不到页面上"，`tests/types_fixture.py` 的注释同改。`tests/test_auth.py::TheLoginSurface` 与各处 `Bind(type=…)` 借道早已随前几轮收敛（全仓 0 处）。手工构造的裸 dict 里再出现字段级 `sink` 不会报错了——那正是终态：渲染器记一条警告并丢掉（ADR 0032 §2）。

## 设置页（ADR 0001，2026-11-25，进行中）

决定在 `docs/adr/0001-page-options-and-the-settings-page.md`：值走 `__CONFIG__` 一个槽（fluxen ADR 0038 §2），组的 `sink` 用 `scope: both`——本地立刻改、同时上行；浏览器侧由 `reflux.js` 的 `STYLE` 表把镜像的 `data-*` 落到 `:root` 的自定义属性；服务端是"新连接从哪开始"那份，落盘记住选择。

- [x] 设置页：`examples/{zh,en}/demo_settings.py` 一页，一个组装 `sketch`（`kind: bool`）、`accent`、`round`，`sink=Sink(dest="__CONFIG__", scope="both", path="/")`、`submit=["change"]`、`reset="keep"`；`demo_app.py` 注册 `/settings` 路由、第七个导航项与 `on_go` 的一行。**槽里放的是"无形状"的 `frame`**：fluxen 读的是这个节点的 `source.default`（`config_members`），所以 `Slot.set(dict)` 会被 `wire` 拒——与走查页 `payload()` 同一个写法。
- [x] 上行与持久化：`on_config` → `Store.apply`（`flatten` 拆渲染器那份 `{字段: {data: 值}}`、白名单 `sketch`/`accent`/`round`、值域 `#rrggbb` 与 0–24 整数、bool 不接受 `1`、合并后只收真变了的），`save_soon` 节流（`loop.call_later`，窗口内连续改动只写最后一次），`flush` 原子写（`.tmp` + `replace`）；`--settings <path>` 缺省 `./.demo-settings.json`（入 `.gitignore`），启动时 `load()`；外框每台设备第一次被画时把已存对象写进槽，新连接第一帧即生效（`seed`，带 `config_seeded` 一次性）。`tests/test_settings.py` 21 例。
- [x] 上色：`www/static/reflux.js` 的 `STYLE` 表（白名单 + 值域：`accent` 只收 `#rrggbb`、`round` 0–24 补 `px`），`paint()` 先读一次再挂 `MutationObserver`（只听这两个属性），值不合法就撤掉那条自定义属性、交回样式表缺省；DESIGN「客户端 runtime」与 `HANDOFF` 记了这条新契约。
- [x] 验证：`tools/gate_settings.py` 十条（真 Chromium）：第一帧带着已存选项、`TOKENS` 把镜像落成 `:root` 属性、一次改动**本地**就动（`data-accent` → `--accent`）、`round` 10→18 变 `18px`、表对 99.5 回落到样式表缺省、`sketch` 镜像给渲染器、上行到服务端并合并、刷新后仍是存下的值、控制台除渲染器那条 `<svg> viewBox` 警告外无错误。`tests/test_settings.py` 21 例 + 全量 390 例 + 十一门全绿。
- [x] 扩到 core 的整个令牌面（2026-11-25）：`TOKENS` 由三个成员变成一张表（颜色十、长度三、线型一），页面按表生成控件、`reflux.js` 按种类落到 `:root`（颜色存 `L C H`、合成 `oklch`），空值 = 不设、回到 `light-dark` 成对缺省；`tests/test_settings.py` 新增"表对着 core.css 的 `:root` 块一个不漏"与"浏览器表 == 服务端表"两例，`tools/gate_settings.py` 十一条（含清空即回缺省、`--border` 跟着拼它的三样）。
- [x] 颜色改成点出来的（2026-11-25）：fluxen 加了 `hue` 色相环（ADR 0048，字段而非新类别，值就是 `L C H` 三元组），有彩度的四个令牌用它、其余用中性格子，线型是五个词；`gate_settings` 十二条（环一次点击只动 `accent`、中性阶只动 `bg`、上行之后状态里只有这三样）。

## 服务端搬到 asyncio（ADR 0002，2026-11-25，已落地）

决定在 `docs/adr/0002-asyncio-transport-and-async-handlers.md`：传输换成 **aiohttp**，一条 loop、一条连接一个 task；处理器写 `async def`，同步的由框架 `to_thread` 兜住；`ctx` 与 `Slot` 保持同步；`asyncio.timeout` 管一次投递的预算；`@app.startup`/`@app.shutdown` 给 `ClientSession`、连接池与后台 task。

**一条硬约束**：`app.make_server(port)` 继续返回同形状的对象（`.server_address` / `.serve_forever()` / `.shutdown()` / `.close()`），内部是"后台线程跑 loop + `AppRunner`/`TCPSite`"。六个 harness 调用点（`tools/cdp.py`、`gate_t7`、`gate_demo`、`gate_ingest`、`tools/serve.py`、`tests/test_page.py`）一行不改——传输被换掉，门与探针的观测面不动，红了才分得清是谁的账。

| 阶段 | 改什么 | 证明 |
|:--|:--|:--|
| P1 传换 | `server.py` → `web.Application`（每个 mount 一条 `web.static` + index 兜底 + `no-store`）；`/ws` → `WebSocketResponse`；`channel.py` 只留适配器；`App.handle` → `async`；`Device.emit` → `asyncio.Queue` + 每设备 writer task（`await ws.drain()`）；watchdog → task | 十门 + 全量测试；重点 `t7`、`demo`、`chat` |
| P2 可 await | `dests._call`/`_call_local` → `async`（`await maybe(...)`，同步走 `to_thread`）；`_draw`/`shell`/`view` 渲染器/`Auth.verify` 可 await；`App(handler_timeout=30.0)`；`CancelledError` 不吞 | 全门 + 6 条新例（async on/page/view/verify、超时、取消、同设备不交错） |
| P3 生命周期 | `@app.startup`/`@app.shutdown`、`app.http`、`App.serve()`、`start()`/`stop()`、`cli.py` | 门走老形状仍绿；CLI 起得来 |
| P4 聊天页 | `ChatModel.reply` → `AsyncIterator[str]`；流式线程 → task；SSE 腿用 `app.http` | `gate_chat` |
| P5 收尾 | 删 `_pump`/`_wake`/`await_frames`/`flush_device` 残留、`channel.py` 帧编解码、`accept_key`/`is_upgrade`、`threading`；DESIGN 加「并发模型」；HANDOFF 记 `serve()`/`start()` | 全绿 + `grep -rn threading reflux/` 收口 |

每个阶段一个 commit、全门绿才进下一阶段。P1 里先加一条守卫：处理器返回协程时抛 `TypeError`（P2 之前不支持），不许静默丢弃。P2 的真正工作量在夹具：`tests/fakes.py` 加 `run_sync(coro)`，17 处 `app._draw(...)` 与 5+ 处 `app.handle(channel)` 跟着改形状。

- [x] P1 传换 —— 2026-11-25：`server.py` 换成 aiohttp（静态 + index 回退 + `no-cache`、通道升级 → `WebSocketResponse`），`App.handle` 变协程、每设备一个 writer task（保留 `outbox` 列表 + `asyncio.Event`，shed / `stale` / resync 语义逐条照旧），看门狗变 task，`make_server` 返回同形状的 `Server` 垫片（`server_address` / `serve_forever` / `server_close`），六个 harness 调用点零改动；`Device.wake()` 管跨线程 emit；测试夹具迁到 async（`run_sync` + async channel），`settle()` 消失（`handle` 返回即写完）。350 例 + 十道门全绿。顺手补 `frames.rs` 跟着 `emit` 窗口的第 9 个参数
- [x] P2 用户代码可 await —— 2026-11-25：`reflux/settle.py` 的 `maybe()` 是唯一入口（协程函数 await，普通函数 `to_thread`，返回可等待物也 await）；`dests.dispatch` / `announce` / `_call` / `_call_local`、`App._draw` / `shell`、`@app.page` / 单页、`Auth.verify`、`connect` / `location` / `disconnect` 都可 await；`App(handler_timeout=30.0)` 用 `asyncio.timeout` 包住一次投递，超时取消 + 记一条 + 设备存活，`CancelledError` 不吞；**页面重画是 outbox 里的排队项**（`App.request_draw` + `_DRAW` 标记），不是 task——否则它的帧会排到调用者下一句 emit 之后；`evict` 的摘表仍是同步的（调用者的答案），关帧与 disconnect 通告在 loop 上跟进。`app.view` 的渲染器保持同步（它在 `Slot.set` 里，让写槽变成 await 等于推翻整个词表），ADR §5 记了理由。`tests/test_async_handlers.py` 九例：async 处理器 / 闭包落点 / 页面 / shell / 验证器、线程外跑、预算取消、同设备不交错、慢的不拖快的。362 例 + 十道门全绿
- [x] P3 生命周期与入口 —— 2026-11-25：`@app.startup` / `@app.shutdown`（可 async，在服务的 loop 上；`_boot` 建 site 前跑 startup 并先建 `app.http`，`_halt` 在 `app.stop()` 前跑、后注册的先跑、单节抛异常只记一行）；`app.http` 共享 `ClientSession`；`App.start(port, host)` 拥有 server、`App.stop()` 结束它（可重复），`serve()` = start + 后台线程，`serve_forever()` = start + 阻塞 + Ctrl-C（`tools/serve.py` 现在就是这一行）；`app.loop` 公开；`Server.shutdown` 关掉自己的 loop（原来漏 fd）；`web.Application` 改用 `web.AppKey`（消掉 `NotAppKeyWarning`）。`tests/test_lifecycle.py` 十例。372 例 + 十道门全绿
- [x] P4 聊天页 async 迭代 —— 2026-11-25：`Model.reply` → `AsyncIterator[str]`（`Scripted` 包着同步的 `scripted_reply`）；`OpenAI` 走 `app.http`，`urllib` 与其阻塞读退场，`parse_sse` / `parse_sse_async` 共用一条 `sse_piece` 行判据（`END` 哨兵把 `[DONE]` 与"这行没有增量"分开）；`demo_chat.share_http` 在 `@app.startup` 把共享会话交给模型、`@app.shutdown` 收回；流式线程 → task（`launch()` 这一个测试缝），`threading.Event`/`Lock` → `asyncio.Event`（一次投递在 loop 上，`busy` 翻转不需要锁），`time.sleep` → `asyncio.sleep`；`disconnect` 的处理器 cancel 那条 task（否则 gate 退出时留下一个 pending task）。两面树同步。377 例（聊天 25 例，含异步读器对齐、缺会话的具名报错、启动钩子交会话、断开取消）+ 十道门全绿
- [x] P5 删死代码 + 文档 —— 2026-11-25：`channel.py` 只剩 `WsChannel` 这个包装——手写编解码（`Channel` 的 `_take`/`recv`/`_send`/`send`/`ping`/`close`/`abort`/`__iter__`）与握手（`accept_key`／`is_upgrade`／`upgrade`）连同 `tests/test_channel.py` 的 8 例字节级测试一起删除（-8 例）；`ChannelClosed` 留下并成为 `WsChannel.send` 对 aiohttp 三种死法的统一翻译；`handle` 里那条读侧 `except ChannelClosed` 删掉（读侧现在以 `StopAsyncIteration` 结束）；看门狗的 `threading.Event` 删掉（task 可取消，不需要第二个停止信号）。`grep -rn threading reflux/` 只剩三处真线程：`Server` 的 loop 线程、`serve()` 的后台线程、`Server._stopped`。DESIGN 加「并发模型」一节，HANDOFF 记三个入口与 `app.http`。369 例 + 十道门全绿
- 服务端搬到 asyncio：P1–P5 全部落地（ADR 0002）。
