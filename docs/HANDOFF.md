# Reflux — 交接（2026-11-27 快照）

给接手的会话：先读 `docs/DESIGN.md`（设计，含每次裁决的 Why Not）和 `docs/PLAN.md`（台账：什么真的落地了、
每件怎么复验）。这份文件只讲「现在站哪儿、下一步做什么、哪些坑已经替你踩过」，它会随日期过期，PLAN 不会。

## 一、现在在哪

- reflux：`main` 上 M1.7 已落地（一个页面、一套方言）。迁移七件全完：M1.1–M1.7 ✅。壳、规格、壳侧生成物、
  七道旧门都已删除——**这个仓里没有第二个渲染器了**。
- 一个页面：`www/` 是页面树，`/` 是它的根挂载，`/static/` 是它的资产树（`App.make_server` 自动挂，缺
  `static/` 就不挂）。深链与刷新都由根挂载的 `index.html` 接住，页面自己再向生产者要结构。
- 帧只有一个方言：`reflux/wire.py`（accrete 的八个 action，**一帧就是这份数组**——没有信封）。`ops`／`ui`／
  `node` 随壳删除，**没有翻译层**。
- fluxen：`main` @ 42f28d4（下行叫 `slot`、上行叫 `dest`；信封归宿主；字段在 wire 上没有 `sink`、类型在 `kind` 里；`color` 字段与折起的 `picker` 都在这一版）。`crates/ui_core/src/lib.rs` 的入口仍多读 `data-path`／`data-codec`，挂载后发布 `window.fluxen.send`。
- 渲染器包是 fluxen `42f28d4` 的发布件，落在 `www/static/vendor/fluxen/`——**这份包不入版本控制**（gitignore），仓里只有装它的 `tools/vendor.py`。装法一行：`python3 tools/vendor.py fetch`（取最新 release；离线用 `build --fluxen <path>`）。当前四个文件：`ui_leptos-581f7e2cb6910aa1.js`（100 548 B）、`ui_leptos-fda8196579f626d2_bg.wasm`（12 720 265 B）、`core.css`（53 298 B）、`custom.css`（6 295 B），共 12 880 406 B；本地树与 `versions.json` 逐字节一致（四个文件逐个比过 sha256 与大小）。
  `versions.json`（rev + 逐文件 sha256/大小）随包生成；trunk／rustc 版本不同字节就不同，所以以 release 那份为准。发布那边是 CI：`.github/workflows/renderer.yml` 每次推 main 都看 pin——该 tag 还没发就用那个 fluxen 修订构建，产出 `dist-release/fluxen-renderer-<rev>.tar.gz` + `SHA256SUMS` 挂到本仓的 release；已发则只装下来跑一遍测试。
- 第二个语言已落地（T10）：`sdks/rust/` 是从**同一份 schema 与 profile** 生成的 Rust SDK（`src/types.rs` 生成，`src/wire.rs` 手写），`gate_t10.py` 断言它建的八帧与 Python **逐字节相等**（9 条：八帧对拍 + 八帧互不相同）。词表只有一份模型（`tools/vocabulary.py`），两个 emitter 只做格式化——「规格是产品」这句现在有可跑的证明。
- 服务端是 asyncio（ADR 0002，2026-11-25）：aiohttp 承载 HTTP 与通道，一条 loop、一连接读/写两个 task；处理器可
  `async def`，页面、`shell`、`Auth.verify`、三种 announce 都能 await。并发模型写在 DESIGN「并发模型」。入口三个：
  `app.serve_forever(port, host)`（阻塞 + Ctrl-C，`tools/serve.py` 用的就是这一行）、`app.serve(...)`（后台线程 + 返回 server）、
  `app.start(...)` / `app.stop()`（嵌入与测试：自己拥有 server，可重复停）；`app.http` 是服务期的共享
  `ClientSession`，`@app.startup` / `@app.shutdown` 建与关。手写的 WebSocket 编解码（`accept_key`／`is_upgrade`／
  `upgrade`／`Channel`）随旧传输删除，`channel.py` 只剩 `WsChannel` 这个包装。
- 设置页已落地（ADR 0001）：`/settings` 导出 core.css 的 `@layer options`——十三个叶子（六个调色板名字、四个形式、三个字）——加 `sketch`，
  走页面选项槽 `__CONFIG__`——组的出口 `Sink(dest="__CONFIG__", scope="both", path="/")` 让改本地立刻生效、同时上行；
  `www/static/reflux.js` 的 `TOKENS` 表把渲染器镜像的 `data-*` 落到 `:root` 的 `--*`（名字加 `--` 即变量名，闭集 + 按种类校验，
  颜色成员存 `L C H`、由这里合成 `oklch()`；空值或非法值就撤掉那条属性）。页面上的六个颜色都是同一个颜色字段（`color`：一块方片加可复制的 `oklch()` 字面量，悬浮出 L/C/H 三根滑块），线型是一个折起来的 `picker`，字是字号（数字框）与字体栈（文本框）（ADR 0001 §9）；`tokens` 层的成对端点与派生逐条列在 `DERIVED` 里、不设（ADR 0001 §8）。服务端 `on_config` 做白名单与值域、节流原子落盘
  （`--settings <path>`，缺省 `./.demo-settings.json`，已入 `.gitignore`），每台设备第一次被画时把已存对象写进槽。
  `tools/gate_settings.py` 十四条真浏览器门（十四个控件）。
- **渲染器的引导契约（2026-11-25 换 rev 撞到的）**：`window.fluxen.send` 是渲染器**第一次渲染时**才发布的（`mount_to` 排队），
  所以 `www/index.html` 在 `mount()` 之后要等这个把手出现再 `start()` 客户端 runtime——不等就会抛
  「window.fluxen.send is missing」并且整页静默空白。渲染器本版还会在 bool 字段上打一条 `<svg> viewBox` 警告（Chromium），
  那是 fluxen 侧的事，门里按**逐字匹配**过滤掉它，别的错误照样失败。
- 示例是一棵参考应用写了两遍（`examples/zh` 与 `examples/en`，界面、注释、函数文档同语言），六个页面：`/`、`/about`、`/chat`（AI 对话）、`/counter`（信号与存储）、`/settings`（页面选项）、`/demo`（fluxen 的走查）。聊天页的六个后端行为（会话态／流式／停止／单飞／应用层两道门／模型失败变气泡）各有断言，`tools/gate_chat.py` 12 条（9 条走真 socket、3 条在真 Chromium）；走查页由 `tools/gate_demo.py` 19 条覆盖。

## 二、怎么跑（全绿才算数）

```
python3 tools/vendor.py fetch                    # 先装渲染器包（不入库；离线用 build --fluxen <path>）
python3 tools/gen_sdk.py --check                 # schema + profile → reflux/sdk（唯一的词表门）
python3 -m unittest discover -s tests -t .       # 443 例
python3 tools/gate_ingest.py                     # 12 条：两道门、整帧拒收、计数（真 socket，无 chromium）
python3 tools/gate_t0.py                         # 7 条：请求集 == versions.json、逐件哈希、深链、缺模块 404
python3 tools/gate_t2.py                         # 12 条：八个 action 各一条 DOM 断言 + 拒收 + empty
python3 tools/gate_t3.py                         # 16 条：整树画词表 + 令牌的 computed style
python3 tools/gate_t4.py                         # 10 条：输入/loom 上行、落点与 id 认领（真按键、真点击）
python3 tools/gate_t6.py                         # 8 条：runtime 镜像 / 历史 / 后退 / 深链 / 无标记
python3 tools/gate_t7.py                         # 4 条：会话（浏览器重载 + 离线判死，两套时钟）
python3 tools/gate_t8.py                         # 5 条：页面侧的坏帧后果
python3 tools/gate_t9.py                         # 17 条：参考应用（回声／列表增删／拖拽归档／登录与 token／两页导航／404）
python3 tools/gate_t10.py                        # 9 条：Rust SDK 的八帧与 Python 逐字节相等（要 cargo）
python3 tools/gate_chat.py                       # 12 条：聊天页的后端（9 条真 socket + 3 条真浏览器）
python3 tools/gate_demo.py                       # 19 条：走查页（一域一槽、悬浮按钮四态、播放按连接）
python3 tools/gate_settings.py                   # 14 条：设置页（options 层、颜色字段、折起的词表、字体栈、持久化）
python3 tools/probe_counter.py                   # 计数器页的一次真实点击（按一下 1、步长 3、再按 4）
curl -s localhost:8000/v1/inspect | jq        # 应用自己声明的表（需要先注册 @app.hooks.inspect）
python3 tools/serve.py --port 0                  # 手工起页面（不动应用；用来对着 DOM 试帧）
python3 -m examples.zh.demo_app --port 0              # 起参考应用（`/`、`/about`、`/chat`、`/counter`、`/settings`、`/demo`）
python3 tools/measure.py                         # 四段测量：帧字节 / DOM 变更 / 首屏 / 服务端 CPU（约一分钟）
python3 tools/measure.py --only bytes,cpu        #   只跑其中两段
```

浏览器门共用 `tools/cdp.py`（stdlib CDP 夹具，真 chromium、真鼠标/按键、`open_page` 负责起服务与等启动）。
门都由**门自己当生产者**：等设备出现、用 `wire`/`sdk.builders` 组帧、`device.send` 发出，再读 DOM。
`gate_ingest.py` 只要那条 socket（`cdp.Ws`），不需要浏览器。

## 三、历史：聊天示例（2026-11-03/04，已并入参考应用）

T11 的数字在 `docs/PERF.md`，T10 的判据在 `tools/gate_t10.py`。那一轮补的是**使用者**：框架此前只有 `demo_app`（证明页面能怎么用），没有第二个应用证明**页面后面的后端**怎么做。独立的 `examples/chat` 已经不在了——对话页搬进参考应用成为 `/chat`（`examples/{zh,en}/demo_chat.py` + `chat_model.py`），`/status` 也进了 `demo_app`。

六件事各有用例与门：会话态挂在连接上、回话逐块流进槽（一句 126 字 = 42 帧）、停止时半句不进上下文、流未结束时再发被拒并说明、空/超长在应用层拒、模型出错变一条气泡。模型是一条缝（`Model.reply`，ADR 0002 P4 之后是 `AsyncIterator[str]`），默认 `Scripted` 离线确定性，`OpenAI` 走 SSE——**后者没有对真端点跑过**（本机没有 key）。

示例自身能继续长的地方（持久化、工具调用、token 计量）一直是它的「不做」，要做等于另开一轮；`canvas` 的真浏览器门仍是缺口（见第五节）。

## 四、硬约束（这些轮踩出来的，别再踩）

- **一个方言**：`reflux/wire.py` 是唯一的出帧层（accrete 的八个 action，帧就是数组）。没有第二个渲染器、
  没有翻译层、没有信封。M1.7 之前的 `ops` 方言已随壳删除——别照着旧文档或旧提交把它写回来。
- **入站只认动作数组**：对象（旧信封 `{ev, sender, content}`、壳的 `{op, …}`）整帧拒收，理由点名它看到的键
  （`ingest.check_frame`）。2026-10-29 起连「信封长什么样」都不在这一层判——线上没有信封。
- **闭集只有一份**：`reflux/sdk/closed.py` 从生成的模型算允许的键（取 alias，减 profile 的 `hidden_attrs`），
  构造期（`wire`）与边界（`ingest`）共用。别在 `ingest.py` 里再写一张类型/属性表。
- **`profile.expose` 不是线封闭度**：它是构造器面。`stamp` 节点线上合法（`tmpl` 展开的替换节点），只是没有建造器。
- **槽名在入站判不了**：「这个槽名声明过吗」要会话持着它发出去的树（影子状态），归 SDK 构造期。别为了它给
  session 加一份树。
- **拒收是整帧、会话存活、计数带身份**：`App.stats["refused"]` ＋ 日志里的会话／路径／第几条 op／原因。
  渲染器的降级只有 `warn`，我们这一侧每一个数字都要自己留。
- **令牌是唯一的 class 通路**：生产端只写 `variant=`（profile 的闭集合），SDK 低成 `attrs.class`；`closed.py`
  只在声明过变体的类型上放行 `class`，且每个元素必须是令牌。`selector` 一律隐藏。别给生产端开自由 class。
- **生产者侧两条规则在 `wire`**：一帧超过 `MAX_OPS_PER_FRAME` 拒建、一棵树里同一个 id 出现两次拒建
  （`reflux/protocol.py` 是那两个协议数字的唯一来源）。服务端那道门独立复核，两条都要留。
- **上行的时机是渲染器的**：`input`（含 `multiline`）在 **Enter**（全仓没有 blur），空值不上行；`tag` 被 `input`／`picker`（与嵌套的 `loom`）读（回车提交进 loom，loom 的 `submit` 一次发出全部字段）；帧的 `id` = 发射节点自身，空 id 无键。写门之前先读 `ui_leptos`。
- **`button` 只在 `loom` 里渲染**，且一次点击就是一帧 loom submit——所以「点一下做事」的组件一律包一层 loom，
  行身份靠 loom 自己的 id 上行（`demo_app.row_node`）。
- **两个标记必须是 `frame`**：`text` 只把 id 塞进 class 列表，`frame` 还把它落到 DOM 的 `id` 属性上
  （`placeholder` 并进来时带过来的行为，ADR 0027）；`tiles`/`panel`/`canvas` 虽然也 `.id()`，
  但各自带语义，标记不该借用。gate 里按 id-as-class 取节点的那几处（`text`）照旧。
- **挂载前缀的唯一来源是页面的 `<base href>`**（现在是 `/`）：标记写应用路径，地址栏写挂载后的路径，换算只在
  `reflux.js` 的 `toApp`／`toBrowser`。换前缀＝改 `<base>` + 挂载表，页面与 runtime 不动。
- **资源一律源站绝对路径**（`/static/…`）：相对路径会被深链解析到深链目录底下（实测白屏 + `Unexpected token '<'`）。
  页面的 `<img>` 也一样——`tests/types_fixture.py` 那个 `image` 节点指向 `www/static/logo.svg` 是有原因的
  （它原指 `/favicon.svg`，那是壳的挂载根里的文件，M1.7 之后 404）。
- **本地落点归组，读侧仍要进一层**：`inject` 已随 fluxen ADR 0038 §1 删除；`scope: local` 的写现在是**组的**（`sink` 的 `scope: local` 加 `submit: ["change"]`），字段在 wire 上没有 `sink`。客户端槽里装的仍是 Outflow 形状的包装，所以要显示载荷本身，读侧写 `source=Source(slot=…, scope="local", path="/data")`。
- **`position` 的域外只有渲染器判得了**（它要知道列表多长）；我们只校验「是整数」。同一帧里同一个列表槽的行 id
  出现两次才是我们能判的——那条在入站整帧拒收。
- **槽里的种子是一次性的**：`create` 换树，数据平面（槽）不换，所以「页面每次重画都 append 一遍种子行」会把行
  翻倍。这条现在归信号层：`Signal(v).keyed(fn).bind(slot)` 的首写是它的行、之后的绘制 `bind` 交回同一条信号
  （按槽名记在 `ctx.data` 里），页面自己不必记一个「种过没有」的标记。
- **fluxen 的装配必须在 `mount_to` 的闭包里**：`Ctx::new` 用 Leptos 的 executor，提前会 panic（白屏 + 一条
  `spawn_local before a global executor was initialized`）。
- **不碰 fluxen 的帧形状**：宿主 API 只有 `#main` 的 `data-path`/`data-codec` 与 `window.fluxen.send`
  两处；渲染器那条 socket 只解动作列表（信封已归宿主，ADR 0021 决策 6），要给框架一类自己的下行帧
  就是另一条腿，已否决（Why Not）。
- **写文档的纪律**：代码落地同轮改 DESIGN（形状 + Why Not）与 PLAN（状态 + 实测行）；裁决要把文档里被它推翻
  的旧话一起扫掉（用户会逐句读）。提交只在明确说「提交」时发生，一条提交一个主题。

## 五、明确没做的（别当成已存在）

- `canvas` 没有一条真浏览器门（要外部部署件，见 DESIGN 的属性落空清单；`chart`／`editor`／`diagram` 已是它的实例，一并归在这里）。
- 这三件是**已落地**的，列在这里是为了说明它们不在「未做」里：标记糖（`reflux.sdk.markers` + `sdks/rust/src/markers.rs` 手写同一份约定，不进 vocabulary）、`@app.hooks.inspect("/v1/inspect")`（应用的声明以 JSON 发出；CLI 的 `routes`／`dests` 已在 efe8627 退场，表由这条钩子伺服，没有 Rust 对应物——注册表属于宿主）、`text` 的 `local` 落点与它的 `path` 随行键（`gate_t2` 的 vals 平面检查已从手写 dict 换成构造器）。
- 示例应用不持久化、不做账号与刷新后的历史（会话挂在连接上，刷新即新对话）；没有工具调用与检索；没有 token 计量与
  限流。`model.OpenAI` 的 SSE 读器用本地 stub 测过，**没有对真端点跑过**（本机没有 key）——别把它当已验收。
- 里程碑层面：T0–T11 与 M1.1–M1.7 全部落地，DESIGN 的「实施计划」里**没有剩下的条目**——余下的是上面那一条门缺口与
  「开放问题」里还没结的裁决。

## 六、文件地图（T10 之后）

```
reflux/protocol.py             协议自己的两个数字：MAX_OPS_PER_FRAME、RESERVED_PREFIX
reflux/wire.py                 出帧层：八个 action（帧就是数组）；生产者侧两条规则（上限、树内 id 唯一）
reflux/ingest.py               入站校验：Device.send 的出帧门 + App.handle 的入站门，整帧拒收＋计数
reflux/sdk/closed.py           闭集：从生成的模型算允许的键（取 alias），减 profile 的 hidden_attrs
reflux/sdk/_parse.py           手写：parse／dump 边界（dump 补 by_alias）与 Source／Sink 组装
reflux/sdk/markers.py          手写：两个保留 id 与 page()（`reflux:path`／`reflux:title`），不进词表
reflux/application.py          App：挂载表 + /ws + 注册表 + 页面钩子 + 设备表 + 存储指针
reflux/server.py               aiohttp 伺服：静态 + index 回退、无缓存、/ws 升级；`make_server` 的同形状垫片
reflux/signals.py              信号层：Signal／Computed／Effect、batch、drawing（值 → 槽）
reflux/stores.py               存储接口与后端：memory／sqlite／kv／fjall（redis 只容忍）
reflux/slots.py                槽句柄：名字 + set／append／patch／remove／move，写值过 view
reflux/settle.py               maybe()：协程 await、普通函数 to_thread 的唯一入口
reflux/routes.py               路由表与 Match（`{name}` ／ `{name:path}` 的捕获、择优键）
reflux/dests.py                上行落点注册表
reflux/site.py                 部署的那个 app
reflux/auth.py                 认证：verify／token／gated
examples/zh/demo_app.py        参考应用：外框 + `/`、`/about`、`/chat`、`/counter`、`/settings`、`/demo`
examples/zh/demo_chat.py       对话页与后端：流式、停止、单飞、两道应用门
examples/zh/chat_model.py      模型缝：Scripted（离线确定性）／OpenAI（SSE，未对真端点验证）
examples/en/…                  同一份应用的英文树
examples/pacing.py             走查共用的节奏（编号步骤、一次 Enter）
tools/serve.py                 只伺服 www/，不声明页面；起法与停法是 `app.serve_forever()` 一行
www/index.html                 页面：静态；`#main` 钉通道与编码；<base href="/">
www/static/reflux.js           客户端 runtime：标记镜像、hello、popstate、TOKENS 上色（只读 DOM，不持 socket）
www/static/reflux.css          @layer reflux 的令牌规则 + 藏两个保留标记
www/static/logo.svg            页面自己的图片资产（fixture 与示例都用它）
www/static/vendor/fluxen/      装出来的渲染器包 + versions.json（gitignore，不入仓库；`tools/vendor.py fetch` 取最新 release）
tools/cdp.py                   CDP 夹具：open_page（起服务、等启动、注入 error hook）、真鼠标/按键、Ws 客户端
tools/vendor.py                装渲染器包：fetch（release）/ build（trunk 构建）/ install（已有 dist）
tools/gate_ingest.py           入站门（真 socket，无 chromium）
tools/probe_counter.py         计数器页的一次真实点击
tools/measure.py               T11 的测量（帧字节 / DOM 变更 / 首屏 / 服务端 CPU）；数字落 docs/PERF.md
tools/vocabulary.py            词表模型：schema + profile + 类型层的字段序，两个 emitter 共用
tools/gen_rust.py              Rust emitter：词表 → sdks/rust/src/types.rs
tools/gate_t10.py              T10 的门：八帧字节对拍（要 cargo；首次 build 需 crates.io）
sdks/rust/                     第二语言的 SDK：生成的 src/types.rs + 手写的 src/{wire,markers,landings}.rs 与 src/bin/frames.rs
tools/gate_*.py                十三道门：t0/t2/t3/t4/t6/t7/t8/t9/t10（浏览器或 cargo）、ingest（真 socket）、chat／demo／settings（真浏览器）
tests/types_fixture.py         15 个暴露类型的唯一一份最小节点（gate_t3 与离线测试共用）
tests/test_page.py             清单 ↔ 磁盘 ↔ 页面三方对拍；根挂载与 /static/ 的规则
tests/test_cli_dests.py        `reflux` 的落点表与目标解析（inspect 的那份声明里能看到的）
tests/test_app.py              路由解析、内置 404、demo 的种子与导航提交
tests/test_chat_example.py     聊天页后端 27 例：窗口、两道门、流式、停止、失败、SSE（本地 stub）
tests/test_settings.py         设置页 29 例：白名单与值域、节流、原子写、首帧 seed
tests/test_signals.py          信号与声明链 17 例
tests/test_stores.py           存储 22 例：匿名／用户／sqlite 跨 app／拒绝／KV／按名字
tools/gate_chat.py             聊天页的门：真 socket 的九条 + 真浏览器的三条
```

## 七、下一步怎么开头

```
1. 跑一遍第二节的全套，确认基线（443 例 + 十三道门全绿；唯一一条红是 `tests/test_packaging.py` 的本地包 `-dirty` rev，发布件不会有这个后缀；`gate_t10` 需要 cargo，浏览器门需要 chromium）
2. 读 DESIGN 的「开放问题」里还没结的几条，以及第五节那条门缺口
3. 出下一轮的计划（补小缺口，或按开放问题做一个裁决）—— 等「开」
4. 落地、跑全套、报实测行与改动文件
```