# Reflux — 交接（2026-10-20 快照，示例应用后）

给接手的会话：先读 `docs/DESIGN.md`（设计，含每次裁决的 Why Not）和 `docs/PLAN.md`（台账：什么真的落地了、
每件怎么复验）。这份文件只讲「现在站哪儿、下一步做什么、哪些坑已经替你踩过」，它会随日期过期，PLAN 不会。

## 一、现在在哪

- reflux：`main` 上 M1.7 已落地（一个页面、一套方言）。迁移七件全完：M1.1–M1.7 ✅。壳、规格、壳侧生成物、
  七道旧门都已删除——**这个仓里没有第二个渲染器了**。
- 一个页面：`www/` 是页面树，`/` 是它的根挂载，`/static/` 是它的资产树（`App.make_server` 自动挂，缺
  `static/` 就不挂）。深链与刷新都由根挂载的 `index.html` 接住，页面自己再向生产者要结构。
- 帧只有一个方言：`reflux/wire.py`（accrete 的八个 action，**一帧就是这份数组**——没有信封）。`ops`／`ui`／
  `node` 随壳删除，**没有翻译层**。
- fluxen：`main` @ 460d867（2026-10-29 起线上只有动作列表，信封归宿主）。`crates/ui_core/src/lib.rs` 的入口仍
  多读 `data-path`／`data-codec`，挂载后发布 `window.fluxen.send`。
- 仓里钉着的渲染器包是 fluxen 460d867 的 **release** 构建（`examples/renderer`，`trunk build --release`）：
  `www/static/vendor/fluxen/`，4 件资产共 2 995 260 B（wasm 2 883 294 B；本机没有 `wasm-opt`，所以没有
  压缩后的数字），清单在 `versions.json`（rev + 逐文件 sha256/大小）。`rev` 现在写的是 `uncommitted`：
  这一版是从 fluxen 工作树（ADR 0022 + 0023（落点一律叫 `slot`） 之后）构建的，revision 随那次提交一起补。
- 第二个语言已落地（T10）：`sdks/rust/` 是从**同一份 schema 与 profile** 生成的 Rust SDK（`src/types.rs` 生成，
  `src/wire.rs` 手写），`gate_t10.py` 断言它建的七帧与 Python **逐字节相等**。词表只有一份模型
  （`tools/vocabulary.py`），两个 emitter 只做格式化——「规格是产品」这句现在有可跑的证明。
- 示例应用已落地：`examples/chat/`（AI 对话）——六个后端行为（会话态／流式／停止／单飞／应用层两道门／
  模型失败变气泡）各有断言，`tools/gate_chat.py` 12 条（9 条走真 socket、3 条在真 Chromium），
  `examples/chat/walkthrough.py` 是它的快速演示（借 fluxen `examples/walkthrough.py` 的形状）。

## 二、怎么跑（全绿才算数）

```
python3 tools/gen_sdk.py --check                 # schema + profile → reflux/sdk（唯一的词表门）
python3 -m unittest discover -s tests -t .       # 182 例
python3 tools/gate_ingest.py                     # 12 条：两道门、整帧拒收、计数（真 socket，无 chromium）
python3 tools/gate_t0.py                         # 7 条：请求集 == versions.json、逐件哈希、深链、缺模块 404
python3 tools/gate_t2.py                         # 12 条：八个 action 各一条 DOM 断言 + 拒收 + empty
python3 tools/gate_t3.py                         # 18 条：整树画词表 + 令牌的 computed style
python3 tools/gate_t4.py                         # 8 条：输入/表单上行、id 认领（真按键、真点击）
python3 tools/gate_t6.py                         # 8 条：runtime 镜像 / 历史 / 后退 / 深链 / 无标记
python3 tools/gate_t7.py                         # 4 条：会话（浏览器重载 + 离线判死，两套时钟）
python3 tools/gate_t8.py                         # 5 条：页面侧的坏帧后果
python3 tools/gate_t9.py                         # 10 条：参考应用（回声／列表／表单／两页导航／404）
python3 tools/gate_t10.py                        # 8 条：Rust SDK 的七帧与 Python 逐字节相等（要 cargo）
python3 tools/gate_chat.py                       # 12 条：示例应用的后端（9 条真 socket + 3 条真浏览器）
python3 -m examples.chat.app --port 8100  # 手工起示例应用（AI 对话）
python3 -m examples.chat.walkthrough --auto   # 示例的快速演示（自己起 app，六个行为各一步）
python3 -m reflux.cli routes reflux.demo_app       # 路由表（import 的副作用）
python3 -m reflux.cli uplinks reflux.demo_app:make_app  # 上行落点注册表（名字 / builtin|app / 来源）
python3 -m reflux.demo --port 0                  # 手工起页面（不动应用；用来对着 DOM 试帧）
python3 -m reflux.demo_app --port 0              # 起参考应用（回声／列表／表单／两条路由）
python3 tools/measure.py                         # 四段测量：帧字节 / DOM 变更 / 首屏 / 服务端 CPU（约一分钟）
python3 tools/measure.py --only bytes,cpu        #   只跑其中两段
```

浏览器门共用 `tools/cdp.py`（stdlib CDP 夹具，真 chromium、真鼠标/按键、`open_page` 负责起服务与等启动）。
门都由**门自己当生产者**：等会话出现、用 `wire`/`sdk.builders` 组帧、`session.send` 发出，再读 DOM。
`gate_ingest.py` 只要那条 socket（`cdp.Ws`），不需要浏览器。

## 三、这一轮：示例应用（`examples/chat`）

T11 的数字在 `docs/PERF.md`，T10 的判据在 `tools/gate_t10.py`——都落了。这一轮补的是**使用者**：框架此前只有
`demo_app`（证明页面能怎么用），没有第二个应用证明**页面后面的后端**怎么做。

示例是一页对话应用，六件事各有用例与门：会话态挂在连接上、回话逐块流进槽（一句 126 字 = 42 帧）、停止时半句不进
上下文、流未结束时再发被拒并说明、空/超长在应用层拒、模型出错变一条气泡。模型是一条缝（`Model.reply`），默认
`Scripted` 离线确定性，`OpenAI` 走 SSE——**后者没有对真端点跑过**。

下一件没有排定的条目。可选的两条：给 `canvas`／`chart`／`editor`／`diagram` 补真浏览器门（要先决定部署件从哪来），
或者按 DESIGN「开放问题」里没结的几条做一次裁决。示例自身能继续长的地方（持久化、工具调用、token 计量）是它
README 里明说的「不做」，要做等于另开一轮。

## 四、硬约束（这些轮踩出来的，别再踩）

- **一个方言**：`reflux/wire.py` 是唯一的出帧层（accrete 的八个 action，帧就是数组）。没有第二个渲染器、
  没有翻译层、没有信封。M1.7 之前的 `ops` 方言已随壳删除——别照着旧文档或旧提交把它写回来。
- **入站只认动作数组**：对象（旧信封 `{ev, sender, content}`、壳的 `{op, …}`）整帧拒收，理由点名它看到的键
  （`ingest.check_frame`）。2026-10-29 起连「信封长什么样」都不在这一层判——线上没有信封。
- **闭集只有一份**：`reflux/sdk/closed.py` 从生成的模型算允许的键（取 alias，减 profile 的 `hidden_attrs`），
  构造期（`wire`）与边界（`ingest`）共用。别在 `ingest.py` 里再写一张类型/属性表。
- **`profile.expose` 不是线封闭度**：它是构造器面。`template` 节点线上合法（`tmpl`/`inject` 展开的替换节点），
  只是没有建造器。
- **槽名在入站判不了**：「这个槽名声明过吗」要会话持着它发出去的树（影子状态），归 SDK 构造期。别为了它给
  session 加一份树。
- **拒收是整帧、会话存活、计数带身份**：`App.stats["refused"]` ＋ 日志里的会话／路径／第几条 op／原因。
  渲染器的降级只有 `warn`，我们这一侧每一个数字都要自己留。
- **令牌是唯一的 class 通路**：生产端只写 `variant=`（profile 的闭集合），SDK 低成 `attrs.class`；`closed.py`
  只在声明过变体的类型上放行 `class`，且每个元素必须是令牌。`selector` 一律隐藏。别给生产端开自由 class。
- **生产者侧两条规则在 `wire`**：一帧超过 `MAX_OPS_PER_FRAME` 拒建、一棵树里同一个 id 出现两次拒建
  （`reflux/protocol.py` 是那两个协议数字的唯一来源）。服务端那道门独立复核，两条都要留。
- **上行的时机是渲染器的**：`input`／`textarea` 在 **Enter**（全仓没有 blur），空值不上行；`field` 只被 `input`
  读（回车提交进 form，form 的 submit 一次发出全部字段）；帧的 `id` = 发射节点自身，空 id 无键。写门之前先读
  `ui_leptos`。
- **`button` 只在 `form` 里渲染**，且一次点击就是一帧 form submit——所以「点一下做事」的组件一律包一层 form，
  行身份靠 form 自己的 id 上行（`demo_app.row_node`）。
- **两个标记必须是 `placeholder`**：`text`／`case` 把 id 塞进 class 列表，只有 `placeholder` 一类
  （`rack`/`pages`/`layer`/`fold`/`diagram`/`canvas`）才 `.id()`。gate 里读 DOM 也因此按 class 取。
- **挂载前缀的唯一来源是页面的 `<base href>`**（现在是 `/`）：标记写应用路径，地址栏写挂载后的路径，换算只在
  `reflux.js` 的 `toApp`／`toBrowser`。换前缀＝改 `<base>` + 挂载表，页面与 runtime 不动。
- **资源一律源站绝对路径**（`/static/…`）：相对路径会被深链解析到深链目录底下（实测白屏 + `Unexpected token '<'`）。
  页面的 `<img>` 也一样——`tests/types_fixture.py` 那个 `image` 节点指向 `www/static/logo.svg` 是有原因的
  （它原指 `/favicon.svg`，那是壳的挂载根里的文件，M1.7 之后 404）。
- **`inject` 落的是 Outflow 形状的包装**：vals 槽里是 `{slot, data}`，订阅方要 `bind.path = "/data"`。
- **`position` 的域外只有渲染器判得了**（它要知道列表多长）；我们只校验「是整数」。同一帧里同一个列表槽的行 id
  出现两次才是我们能判的——那条在入站整帧拒收。
- **槽里的种子是一次性的**：`create` 换树，数据平面（槽）不换，所以「页面每次重画都 append 一遍种子行」会把行
  翻倍。`demo_app.frame_for` 用 `session.rows_seeded` 只种一次——生产者计数，这就是 DESIGN「操作」里认下的代价。
- **fluxen 的装配必须在 `mount_to` 的闭包里**：`Ctx::new` 用 Leptos 的 executor，提前会 panic（白屏 + 一条
  `spawn_local before a global executor was initialized`）。
- **不碰 fluxen 的帧形状**：宿主 API 只有 `#main` 的 `data-path`/`data-codec` 与 `window.fluxen.send`
  两处；渲染器那条 socket 只解动作列表（信封已归宿主，ADR 0021 决策 6），要给框架一类自己的下行帧
  就是另一条腿，已否决（Why Not）。
- **写文档的纪律**：代码落地同轮改 DESIGN（形状 + Why Not）与 PLAN（状态 + 实测行）；裁决要把文档里被它推翻
  的旧话一起扫掉（用户会逐句读）。提交只在明确说「提交」时发生，一条提交一个主题。

## 五、明确没做的（别当成已存在）

- `canvas`／`chart`／`editor`／`diagram` 四个类型没有一条真浏览器门（要外部部署件，见 DESIGN 的属性落空清单）。
- 这三件是**已落地**的，列在这里是为了说明它们不在「未做」里：标记糖（`reflux.sdk.markers` + `sdks/rust/src/markers.rs`
  手写同一份约定，不进 vocabulary）、`reflux uplinks` CLI（显式 `module:attr` 目标，不猜 `make_app`；没有 Rust 对应物，
  注册表属于宿主）、`text` 的 `local` 落点与它的 `path` 随行键（`gate_t2` 的 vals 平面检查已从手写 dict 换成构造器）。
- 示例应用不持久化、不做账号与刷新后的历史（会话挂在连接上，刷新即新对话）；没有工具调用与检索；没有 token 计量与
  限流。`model.OpenAI` 的 SSE 读器用本地 stub 测过，**没有对真端点跑过**（本机没有 key）——别把它当已验收。
- 里程碑层面：T0–T11 与 M1.1–M1.7 全部落地，DESIGN 的「实施计划」里**没有剩下的条目**——余下的是上面那一条门缺口与
  「开放问题」里还没结的裁决。

## 六、文件地图（T10 之后）

```
reflux/protocol.py             协议自己的两个数字：MAX_OPS_PER_FRAME、RESERVED_PREFIX
reflux/wire.py                 出帧层：八个 action（帧就是数组）；生产者侧两条规则（上限、树内 id 唯一）
reflux/ingest.py               入站校验：Session.send 的出帧门 + App.handle 的入站门，整帧拒收＋计数
reflux/sdk/closed.py           闭集：从生成的模型算允许的键（取 alias），减 profile 的 hidden_attrs
reflux/sdk/_parse.py           手写：parse／dump 边界（dump 补 by_alias）与 bind 条目组装
reflux/sdk/markers.py          手写：两个保留 id 与 page()（`reflux:path`／`reflux:title`），不进词表
reflux/app.py                  根挂载 + /static/ + /ws + 注册表 + 一页钩子；draw_page 走 wire
reflux/server.py               伺服：挂载表（前缀 → 目录）、无缓存、深链交 index.html、/ws 升级
reflux/demo_app.py             参考应用：回声／列表增删／表单一次提交／两条路由（T9 的种子）
reflux/demo.py                 只伺服 www/，不声明页面
examples/chat/app.py           示例应用：一页对话 + 流式 worker + 单飞/停止/应用层两道门
examples/chat/model.py         模型缝：Scripted（离线确定性）／OpenAI（SSE，未对真端点验证）
examples/chat/client.py        通用 WS 客户端（walkthrough 与 gate_chat 都用它）
examples/chat/walkthrough.py   示例的快速演示（Enter 分步 / --auto / --delay / --attach）
examples/chat/README.md        示例的自述：跑法、六个行为、模型缝、明确不做的
www/index.html                 页面：静态；`#main` 钉通道与编码；<base href="/">
www/static/reflux.js           客户端 runtime：标记镜像、hello、popstate（只读 DOM，不持 socket）
www/static/reflux.css          @layer reflux 的七条令牌规则 + 藏两个保留标记
www/static/logo.svg            页面自己的图片资产（fixture 与示例都用它）
www/static/vendor/fluxen/      钉住的渲染器包 + versions.json（升版只改这里）
tools/cdp.py                   CDP 夹具：open_page（起服务、等启动、注入 error hook）、真鼠标/按键、Ws 客户端
tools/gate_ingest.py           入站门（真 socket，无 chromium）
tools/measure.py               T11 的测量（帧字节 / DOM 变更 / 首屏 / 服务端 CPU）；数字落 docs/PERF.md
tools/vocabulary.py            词表模型：schema + profile + 类型层的字段序，两个 emitter 共用
tools/gen_rust.py              Rust emitter：词表 → sdks/rust/src/types.rs
tools/gate_t10.py              T10 的门：六帧字节对拍（要 cargo；首次 build 需 crates.io）
sdks/rust/                     第二语言的 SDK：生成的 src/types.rs + 手写的 src/{wire,markers}.rs 与 src/bin/frames.rs
tools/gate_t0.py … gate_t10.py   十道门（t2/t3/t4/t6/t9/t10 用浏览器或 cargo，t7 真浏览器 + 离线，t8 页面侧，ingest 真 socket）
tests/types_fixture.py         29 个暴露类型的唯一一份最小节点（gate_t3 与离线测试共用）
tests/test_page.py             清单 ↔ 磁盘 ↔ 页面三方对拍；根挂载与 /static/ 的规则
tests/test_cli_events.py       `reflux uplinks` 的表、目标解析的四种拒绝、以及「页面能发的意图都有处理器」
tests/test_app.py              路由解析、内置 404、demo 的种子与导航提交
tests/test_chat_example.py     示例后端 19 例：窗口、两道门、流式、停止、失败、SSE（本地 stub）
tools/gate_chat.py             示例的门：真 socket 的九条 + 真浏览器的三条
```

## 七、下一步怎么开头

```
1. 跑一遍第二节的全套，确认基线（182 例 + 十一道门，全绿；gate_t10 需要 cargo，gate_chat 需要 chromium）
2. 读 DESIGN 的「开放问题」里还没结的几条，以及第五节列的四条小缺口
3. 出下一轮的计划（补小缺口，或按开放问题做一个裁决）—— 等「开」
4. 落地、跑全套、报实测行与改动文件
```