# Reflux — 交接（2026-10-20 快照，M1.6 后）

给接手的会话：先读 `docs/DESIGN.md`（设计，含每次裁决的 Why Not）和 `docs/PLAN.md`（台账：什么真的落地了、
每件怎么复验）。这份文件只讲「现在站哪儿、下一步做什么、哪些坑已经替你踩过」，它会随日期过期，PLAN 不会。

## 一、现在在哪

- reflux：`main` @ 9b4a92c（M1.5）。**M1.6 已落地、未提交**：新增 `tools/gate_t3_next.py`、`gate_t4_next.py`、
  `gate_t8_next.py`、`tests/types_fixture.py`、`tests/test_types_drawable.py`；改 `profile/profile.json`（令牌 +
  input/textarea/select 的落点收窄）、`tools/gen_sdk.py`、`reflux/sdk/builders.py`（重出）、`reflux/sdk/_parse.py`、
  `reflux/sdk/closed.py`、`www/static/reflux.css`、`tools/gate_m1_5.py`、三份 docs。
- fluxen：`main` @ 0bf166d，工作树干净。它的 `crates/ui_leptos/src/lib.rs` 是 M1.1 的唯一改动（入口多读
  `data-path`／`data-codec`，挂载后发布 `window.fluxen.send`）。
- 仓里钉着的渲染器包是 fluxen 0bf166d 的 **release** 构建：`www/static/vendor/fluxen/`，4 件资产共
  2 420 114 B（wasm 2 348 320 B），清单在 `versions.json`（rev + 逐文件 sha256/大小）。
- 迁移进度（M1 已拆成七件）：M1.1 ✅ · M1.2 ✅ · M1.3 ✅ · M1.4 ✅ · M1.5 ✅ · M1.6 ✅ · M1.7 ⏳（剩退场那一件）。
- 两个页面并存是刻意设计：壳仍在 `/`（旧门 T0–T8 对着它），新页在 `/__next/`，它的资产在 `/static/`。
  同一个 App 同时伺服这三处挂载。

## 二、怎么跑（全绿才算数）

```
python3 tools/gen.py --check                     # 旧规格 → 壳表/SDK 的漂移门（M1.7 退场）
python3 tools/gen_sdk.py --check                 # schema + profile → reflux/sdk（词表门）
python3 -m unittest discover -s tests -t .       # 178 例：规格、边界、路由、会话、wire、页面、入站、词表
python3 tools/gate_m1_5.py                       # 12 条：入站校验两道门（真 socket，无 chromium）
python3 tools/gate_t3_next.py                    # 18 条：整树画词表 + 令牌的 computed style
python3 tools/gate_t4_next.py                    # 8 条：输入/表单上行、id 认领（真按键、真点击）
python3 tools/gate_t8_next.py                    # 5 条：页面侧的坏帧后果
python3 tools/gate_m1_1.py                       # 5 条：入口把手（用仓里钉住的包）
python3 tools/gate_t0_next.py                    # 7 条：新页请求清单 == versions.json、逐件哈希、深链
python3 tools/gate_t6_next.py                    # 8 条：runtime 镜像 / 历史 / 后退 / 深链 / 无标记
python3 tools/gate_t2_next.py                    # 12 条：八个 action 一条 DOM 断言 + 拒收 + empty
python3 tools/gate_t0.py                         # 旧壳的门：t0 / t2 / t3 / t4 / t6 / t7 / t8
python3 tools/gate_t2.py                         #   （逐条跑，仍然必须全绿——它们 drive 的是壳，
python3 tools/gate_t3.py                         #     M1.7 才跟壳一起退场）
python3 tools/gate_t4.py
python3 tools/gate_t6.py
python3 tools/gate_t7.py
python3 tools/gate_t8.py
```

浏览器门共用 `tools/cdp.py`（stdlib CDP 夹具，真 chromium、真鼠标/按键）。旧门直接 drive
`window.reflux`（壳的内部）；新页的门都由**门自己当生产者**：等会话出现、用 `wire`/`sdk.builders` 组帧、
`session.send` 发出，再读 DOM。`gate_m1_5.py` 只要那条 socket（`cdp.Ws`），不需要浏览器。

## 三、下一件：M1.7 退场

这是迁移的最后一件，题目是「删」而不是「加」：

1. 删 `spec/`、`shell/*`（vendored SolidJS、壳 CSS、壳侧生成物 `components.generated.js`）、`tools/gen.py` 里生成
   壳分派表的那一半、对着规格与壳写的用例（`test_spec_sync`、`test_shell_assets`、`test_dsl` 里壳的部分）。
2. `/__next` 提到 `/`：`App.NEXT_PREFIX`、`www/index.html` 的 `<base href="/">`、挂载表（`tests/test_page.py` 把
   `<base>` 与 `App.NEXT_PREFIX` 钉在一起，两处必须同轮改）。
3. `App.draw_page`／`not_found` 切到 `wire`（壳没了，第二个方言一起退场——`ops.py`／`ui.py`／`node.py`／
   `components_generated.py` 随壳删除）；`reflux/demo_app.py` 要么迁到新页要么一并删。
4. 旧门 t0/t2/t3/t4/t6/t7/t8 全部退场（它们 drive 的是壳）；新门 t0′/t2′/t3′/t4′/t6′/t8′ 升格成唯一的门名。
5. `gen_sdk.py --check` 留作词表门；`gen.py --check` 与规格一起消失。

门槛（DESIGN 写的）：`rg 'spec/components.json|shell/js|SolidJS'` 零命中，全套绿（门会少一半，例数会掉）。

## 四、硬约束（这六轮踩出来的，别再踩）

- **方言分离**：`reflux/ops.py` 是**壳的方言**（`{"op":"create","root":…}`），`reflux/wire.py` 是新页的
  （accrete 的八个 + `{"ev":"draw","sender":…,"content":[…]}`）。同一个 socket 只一套帧，**永远不翻译**。
  M1.7 删 `ops`/`ui`/`node`/`components_generated` 时，`App.draw_page`／`not_found` 一并切到 `wire`。
- **入站认帧靠 `content`**：带 `content` 的帧归 accrete 那道校验，带 `ops` 的归壳自己的 `validate.js`
  （`ingest.check_frame` 第一句就是这条）。别在入站层给壳的四个操作再造一张表。
- **闭集只有一份**：`reflux/sdk/closed.py` 从生成的模型算允许的键（取 alias，减 profile 的 `hidden_attrs`），
  构造期（`wire`）与边界（`ingest`）共用。别在 `ingest.py` 里再写一张类型/属性表——那正是这套栈一直在付的税。
- **`profile.expose` 不是线封闭度**：它是构造器面。`template` 节点线上合法（`tmpl`/`inject` 展开的替换节点），
  只是没有建造器。
- **槽名在入站判不了**：「这个槽名声明过吗」要会话持着它发出去的树（影子状态），归 SDK 构造期。别为了它给
  session 加一份树。
- **拒收是整帧、会话存活、计数带身份**：`App.stats["refused"]` ＋ 日志里的会话／路径／第几条 op／原因。
  渲染器的降级只有 `warn`，我们这一侧每一个数字都要自己留。
- **令牌是唯一的 class 通路**：生产端只写 `variant=`（profile 的闭集合），SDK 低成 `attrs.class`；`closed.py`
  只在声明过变体的类型上放行 `class`，且每个元素必须是令牌。`selector` 一律隐藏。别给生产端开自由 class。
- **上行的时机是渲染器的，不是旧壳的**：`input`／`textarea` 在 **Enter**（全仓没有 blur），空值不上行；
  `field` 只被 `input` 读（回车提交进 form，form 的 submit 一次发出全部字段）；`id` = 发射节点自身，空 id 无键。
  写门之前先读 `ui_leptos`，别照旧壳的 `fire: change` 想当然。
- **每一轮落地，全套门同轮绿**。旧门不许先红着（所以有了两个页面并存的迁移期）。
- **两个标记必须是 `placeholder`**：`text`／`case` 把 id 塞进 class 列表，只有 `placeholder` 一类
  （`rack`/`pages`/`layer`/`fold`/`diagram`/`canvas`）才 `.id()`。gate 里读 DOM 也因此按 class 取。
- **挂载前缀的唯一来源是页面的 `<base href>`**（迁移期 `/__next/`）：标记写应用路径，地址栏写挂载后的路径，
  换算只在 `reflux.js` 的 `toApp`／`toBrowser`。M1.7 改 `<base>` + 挂载表，页面与 runtime 一行不动。
- **资源一律源站绝对路径**（`/static/…`）：相对路径会被深链解析到深链目录底下（实测白屏 + `Unexpected token '<'`）。
- **`inject` 落的是 Outflow 形状的包装**：vals 槽里是 `{event, data}`，订阅方要 `bind.path = "/data"`。
- **`position` 的域外只有渲染器判得了**（它要知道列表多长）；我们只校验「是整数」，域外拒收是渲染器的 `warn`，
  门的断言是「那一行没落地」。我们**能**判的是同一帧里同一个列表槽的行 id 只出现一次——那条已在入站整帧拒收。
- **fluxen 的装配必须在 `mount_to` 的闭包里**：`Ctx::new` 用 Leptos 的 executor，提前会 panic（白屏 + 一条
  `spawn_local before a global executor was initialized`）。
- **不碰 fluxen 的 `Message`**：宿主 API 只有 `#main` 的 `data-path`/`data-codec` 与 `window.fluxen.send`
  两处；要第二类下行帧就得改那个信封，已否决（Why Not）。
- **写文档的纪律**：代码落地同轮改 DESIGN（形状 + Why Not）与 PLAN（状态 + 实测行）；裁决要把文档里被它推翻
  的旧话一起扫掉（用户会逐句读）。提交只在明确说「提交」时发生，一条提交一个主题。

## 五、明确没做的（别当成已存在）

- 内置 404（`not_found`）还是壳的旧形状 → 新页上画不出来；T6′ 因此**没有**「未知路径 → 404」那条。
- `App.draw_page` 还在用 `ops`（旧方言）→ **路由应用还不能给新页供页**；目前只有门里的生产者能画。
- 旧门 t2／t3／t4／t8 仍在跑壳（M1.7 与壳一起退场）。
- `canvas`／`chart`／`editor`／`diagram` 四个类型没有一条真浏览器门（要外部部署件，见 DESIGN 的属性落空清单）。
- SDK 还没有标记糖（`reflux:path`／`reflux:title` 目前靠手写 `placeholder`，见 `tools/gate_t6_next.py`）。
- `bind` 的 `local` 落点只有 `fold`／`pages` 的构造器暴露（`text` 没有）；门与 `gate_t2_next` 的 fixture 手写了这一处。
- `reflux events` CLI、`demo_app` 迁到新页、T9–T11 重对：都没做。

## 六、文件地图（这几轮新增/改动的）

```
reflux/wire.py                 出帧层：八个 action + draw 信封（新页的方言）
reflux/ingest.py               入站校验：Session.send 的出帧门 + App.handle 的入站门，整帧拒收＋计数
reflux/sdk/closed.py           闭集：从生成的模型算允许的键（取 alias），减 profile 的 hidden_attrs
reflux/app.py                  Session.send 过入站校验；handle 派发前校上行；stats 增 refused
reflux/sdk/_parse.py           dump 补 by_alias（线上是 class，不是 class_）
www/index.html                 页面：静态；`#main` 钉通道与编码；<base> 是挂载前缀
www/static/reflux.js           客户端 runtime：标记镜像、hello、popstate（只读 DOM，不持 socket）
www/static/reflux.css          只藏两个保留标记
www/static/vendor/fluxen/      钉住的渲染器包 + versions.json（升版只改这里）
tools/gate_m1_5.py  gate_m1_1.py  t0_next.py  t6_next.py  t2_next.py    五道新门
tools/gate_t3_next.py  gate_t4_next.py  gate_t8_next.py                T3′ / T4′ / T8′
tests/types_fixture.py         29 个暴露类型的唯一一份最小节点（T3′ 与离线测试共用）
tests/test_types_drawable.py   词表完整性：夹具 == profile 暴露集，逐节点过闭集与域
www/static/reflux.css          @layer reflux 的七条令牌规则（heading-1/2/3、code、muted、danger、card）
tests/test_ingest.py           入站校验：拒收表 + 两道门（22 例）
tests/test_wire.py             八种形状对表 + 四类拒收 + 构造期闭集与 alias
tests/test_page.py             清单 ↔ 磁盘 ↔ 页面三方对拍；挂载规则
```

## 七、下一步怎么开头

```
1. 跑一遍第二节的全套，确认基线（178 例 + 十五道门：8 道新的 + 7 道旧的，全绿）
2. 读 DESIGN 的「M1.7——退场」与「已落地的形状」，以及 PLAN 的 M1.7 行
3. 出 M1.7 的计划：删哪些文件／用例、`/__next` 提到 `/` 的两处同改、`draw_page`／`not_found` 切 `wire` 的形状、
   哪些门升格成唯一的门名 —— 等「开」
4. 落地、跑全套、报实测行与改动文件；不提交
```