# PLAN

方向与决定在 `docs/adr/`（一份决定一个文件），形状与不变量在 `docs/DESIGN.md`，测量数字与口径在 `docs/PERF.md`；本文件是索引——每一轮做了什么、门验的是什么、决定它的是哪份 ADR。

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

## 变更记录（2026-10-20 … 2026-11-26）

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
- [x] 渲染器钉到 `42f28d4`（2026-11-26）：颜色字段、`picker` 的折起、字段的 `kind` 都在这一版里；本地 vendor 树与 `versions.json` 的四个文件逐个比过 sha256 与大小，逐字节一致
- [x] CLI 退场：`reflux routes`／`reflux dests` 随 `hooks` 改成属性一起删除（`efe8627`），应用的声明改由 `@app.hooks.inspect("/v1/inspect")` 以 JSON 伺服；`tests/test_cli_events.py` 随之改名成 `test_cli_dests.py` 并只测表本身 — 2026-11-25
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

## 输入统一进 loom（ADR 0004，2026-11-24，已落地）

决定在 `docs/adr/0004-the-group-is-the-only-uplink.md`：组是唯一的出口，`tag` 是成员身份，载荷永远是 `{tag: value}` 的打包对象；清空与次数（`reset` / `sends`）归组。

- [x] `schema/accrete.schema.json` 同步（`LoomAttr` +`reset` +`sends`，新增 `$defs.ResetMode`），`tools/gen_sdk.py`、`tools/gen_rust.py` 重新生成 —— `h.loom(..., reset=…, sends=…)` 由此出现
- [x] 两棵树的独立输入进组：回声 → `h.loom(h.input(tag="name"), sink=echo, submit=["enter"])`，`echo` 读 `value["name"]`；步长 → 同形的组，`set_step` 读 `value["step"]`；两个处理器都只认打包对象
- [x] 聊天页的发送组 `reset="clear"`：发完输入框自己清空
- [x] 测试与夹具：`tests/test_sdk_generated.py`（带 `tag` 的字段；字段级 `sink` 被生成的模型拒绝）、`tests/types_fixture.py` 的 `input` 条目补 `tag`、`tests/test_counter.py` 的载荷是数字（`{"step": 5}`，空盒是 `None`）
- [x] 字段的 `sink` 从 wire 退场（fluxen 侧落地，本仓只跟着删）：`_check_uplinks` 与只被它用的 `FIELD_TYPES` 删除；`gate_t4` 的引言改成"字段在 wire 上没有 `sink` 这个属性，所以带不到页面上"，`tests/types_fixture.py` 的注释同改。手工构造的裸 dict 里再出现字段级 `sink` 现在是 `parse()` 的 `ValidationError`——终态由生成的模型挡在构造那一行
- [x] 字段的类型落在字段上：`kind`（`InputKind`）取代 `Bind.type`；`select` 换成 `picker`（自己的 `PickerKind`，`t3` 跟着读它）；`type` 不再是组的属性
- [x] 步长框改成 `kind="number"`：解析归渲染器（`42` → number，空盒 → null），`set_step` 只剩页面自己的 1–10 规则；`probe_counter` 从页面快照变成一条真检查（按一下得 1、输入 `3` 回车、再按得 4，否则非零退出）
- [x] 门：`gate_t4` 10/10（含"无 `tag` 的字段回车什么都不发、也不清空"、"包里是裸值，没有 `{data, payload}` 包装"）、`gate_t10` 9/9 逐字节、`gate_t3` 16/16（2026-11-27 复跑）

## 设置页（ADR 0001，2026-11-25/26，已落地；控件的最后一半仍在上游）

决定在 `docs/adr/0001-page-options-and-the-settings-page.md`（§2 值怎么走、§3–4 `TOKENS` 表与它的边界、§5 持久化、§8 整个令牌面、§9 颜色字段）。

- [x] 一页、一个组：`demo_settings.py` 按 `TOKENS` 表生成十个颜色、三个长度、一个线型，加 `sketch`；出口 `sink=Sink(dest="__CONFIG__", scope="both", path="/")`、`submit=["change"]`、`reset="keep"`；`demo_app.py` 注册 `/settings` 路由、第七个导航项与 `on_go` 的一行。槽里放"无形状"的 `frame`（`source.default` 是 fluxen 读成员的地方）
- [x] 上行与持久化：`on_config` → `Store.apply`（`flatten` 拆包、白名单、值域：颜色 `L C H`、长度 0–64、线型五个词、`sketch` 只收 bool）、`save_soon` 节流（`loop.call_later`）、`flush` 原子写（`.tmp` + `replace`）、`--settings <path>`（缺省 `./.demo-settings.json`，入 `.gitignore`）、启动 `load()`；外框每台设备第一次被画时写进槽（`seed`），新连接第一帧即生效
- [x] 上色：`www/static/reflux.js` 的 `TOKENS` 表（白名单 + 种类：颜色十、长度三、线型一），颜色存 `L C H` 由表合成 `oklch()`，长度补 `px`；空值撤掉那条自定义属性、交回样式表缺省（成对的 `light-dark` 也在里面）
- [x] 控件跟到上游：长度是 `kind="number"` 的输入框、`sketch` 是 `kind="bool"` 的勾选框、线型是折起来的 `picker`（`expand`，ADR 0049）；颜色是 `color` 字段（一块方片 + 可复制的 `oklch()` 字面量，悬浮展开 L/C/H 三根滑块），十个颜色令牌共用它（fluxen ADR 0052）— 2026-11-25/26
- [x] 门：`gate_settings` 13/13（真 Chromium：首帧带已存选项、`TOKENS` 落成 `:root` 属性、一次点击只动一个成员、`round` 10→18、越界回落缺省、折起的词表选中即收起、`--border` 跟着拼它的三样、`sketch` 镜像给渲染器、手绘模式下浮层是描出来的、上行合并、刷新仍是存下的值）；`tests/test_settings.py` 27 例
- [ ] 值的手势还剩上游一半：`picker` 的滑块与开关尚未画出（fluxen ADR 0050 的「还没做」）。本仓这一侧已经跟到位——`kind` 用上了、服务端也认数字与布尔两种形状；上游画出来之后，本页若出现数字/布尔选项再换控件

## 服务端搬到 asyncio（ADR 0002，2026-11-25，已落地）

决定、传输怎么落与五个阶段的证明在 `docs/adr/0002-asyncio-transport-and-async-handlers.md`（§3–§9，§13 阶段表）。硬约束是 `app.make_server(port)` 保持同形状，迁移当时的六个 harness 调用点一行不改——传输被换掉，门与探针的观测面不动。

- [x] P1 传换 —— `server.py` 换成 aiohttp（静态 + index 回退 + `no-store`、通道升级 → `WebSocketResponse`），`App.handle` 变协程、每设备一个 writer task，看门狗变 task，`make_server` 返回同形状的 `Server` 垫片；测试夹具迁到 async（`run_sync`），`settle()` 消失
- [x] P2 用户代码可 await —— `settle.maybe()` 是唯一入口（协程 await、普通函数 `to_thread`、返回可等待物也 await）；`App(handler_timeout=30.0)` 包住一次投递；页面重画是 outbox 里的排队项（`request_draw` + `_DRAW`），不是 task——否则它的帧会排到调用者下一句 emit 之后；`app.view` 的渲染器保持同步（ADR §5 记了理由）；`tests/test_async_handlers.py` 九例
- [x] P3 生命周期与入口 —— `@app.startup` / `@app.shutdown`、`app.http` 共享 `ClientSession`、`App.start/stop/serve/serve_forever`、`app.loop` 公开、`web.AppKey`；`Server.shutdown` 关掉自己的 loop；`tests/test_lifecycle.py` 十例
- [x] P4 聊天页 async 迭代 —— `Model.reply` → `AsyncIterator[str]`；`OpenAI` 走 `app.http`，`urllib` 与它的阻塞读退场；`parse_sse` / `parse_sse_async` 共用一条行判据；流式线程 → task（`launch()` 这一个测试缝），`threading.Event`/`Lock` → `asyncio.Event`，`time.sleep` → `asyncio.sleep`；断开时 cancel 那条 task
- [x] P5 删死代码 + 文档 —— `channel.py` 只剩 `WsChannel`，手写编解码与握手（连同 8 例字节级测试）删除；`ChannelClosed` 留下并统一翻译 aiohttp 的三种死法；`grep -rn threading reflux/` 只剩三处真线程；DESIGN 加「并发模型」，HANDOFF 记三个入口与 `app.http`

## 槽的值：信号与存储（ADR 0005，2026-11-26，已落地）

决定在 `docs/adr/0005-signals-are-the-subject.md`：信号是主语、槽只是地址；`.store(key)` 决定活多久；存储在 `reflux/stores.py`，后端是一个名字。读写口为什么是 `.value` 这个属性，单独在 `docs/adr/0003-value-is-an-attribute.md`。

- [x] `reflux/signals.py`：`Signal` / `Computed` / `Effect`，`batch()` 把一轮收在一起，`drawing()` 把首写推迟到绘制结束；`.bind` / `.view` / `.keyed` / `.store` 是声明链，槽上没有值
- [x] 身份：`.bind(slot)` 一个槽名一个信号（`ctx.data`），重画拿回同一个、首值只种一次；`.store(key)` 一个 key 一个信号——匿名连接存在这条连接的数据里，有用户的连接存在 `app.store`（按 user id），换连接/设备接着来
- [x] `reflux/stores.py`：`Store` 两个方法 `load(user, key)` / `save(user, key, value)`，值是 JSON（节点存不进去，当场报错）；`MemoryStore` 缺省、`SqliteStore`（SQL 的例子）、`KvStore`（任何有 `get`/`set` 的客户端）、`FjallStore`（`durable=True` 时每次 `sync_all`）；后端按名字挂（`app.set_store("sqlite", {"path"})`、`create_app(store=…)`），`redis`/`valkey` 收但排在最后（`reflux[redis]`，容忍不推荐）
- [x] 槽的值退场：`Slot.signal` / `.computed` / `.keyed` / `.value` 与 `signals.bound` / `into` / `own` / `mirror` / `keep` 删除；名字只由 `/` 拼、点号只到句柄自己的东西、点号子名与 `__getitem__` 一起删除
- [x] 两棵树的 `demo_counter`：`State` 类与 `state()` 缓存删除，五条声明放在页函数头部（三条 `.store`、两条上线 + `.keyed`），视图提成 `_count_node` / `_hint_node`
- [x] 测试：`tests/test_signals.py`、`tests/test_slots.py::TheValue` 改成新 API，新增 `tests/test_stores.py` 22 例（匿名/用户/sqlite 跨 app/四条拒绝/KV 客户端/后端按名字）；`probe_counter` 真 Chromium 一次点击 0→1

## 复核与门的现状（2026-11-27）

- [x] 全量 439 例、`tools/gen_sdk.py --check` 在同步态；十二道门全绿（t0 7／t2 12／t3 16／t4 10／t6 8／t7 4／t8 5／t10 9／ingest 12／chat 12／demo 19／settings 13）；`probe_counter` 通过
- [x] 渲染器钉在 `42f28d4`，本地 vendor 树与 `versions.json` 逐字节一致（见上节）
- [ ] `gate_t9` 15/17 里两项红（#11 退出不撤销、#14 后退的帧带着 `token`）：同一个因——渲染器在「已登录的 auth 子树换成登录面」那一帧 panic（`Tried to access a reactive value that has already been disposed`），DOM 冻在旧状态，空标记到不了浏览器，存下的 token 因此还在。已排除空文本标记、`request_draw`、重复写同一块登录面三种嫌疑。这是 fluxen 侧的账（它的 `dd1765d` 已写明「the panic T9 reports」仍在），本仓等那边修好后重取 vendor、回跑十三道门。