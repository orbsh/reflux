# 0004 — 上行只有一个出口：组是发送者，字段的 `tag` 是它的身份

Status: **Accepted**（2026-11-24），**已落地**；终态按 2026-11-26 的 wire 收敛（字段上连 `sink` 这个键都没有了）。上游的形状在 fluxen ADR 0032 §2，本文件只记本仓这一侧怎么跟。

## 1. 需求

一次表单要一起送出几个值：一个聊天框带一个发送键、一个回声输入框的口令、一页设置项。此前的形状是**每个字段自己带一个 `sink`**：回车就由字段自己上行，上行之后自己清空。三件事散在每个控件里，而且每一件都只有控件说了算：

- 送不送：字段的 `sink` 与组的 `sink` 是两套入口，答同一个问题；
- 这个字段叫什么：字段的 `sink.slot` 既是"值落在哪条槽"，又是"它在包里叫什么"，一个地址两个意思；
- 送完变成什么、还能送几次：没有地方写，清空是控件的硬编码。

## 2. 上游给的形状（fluxen ADR 0032 §2，2026-11-24 修订）

- **`tag` 是成员身份**：组把带 `tag` 的字段打包成一个对象送出；没有 `tag` 的字段不上行。
- **字段没有 `sink`**：`Input` / `Picker` 的 wire 上没有这个键（`schema/accrete.schema.json`，由 `tools/sync_schema.py` 同步）。清空不再由字段做。
- **组多了两件事**：`attrs.reset`（`keep` 缺省 / `clear` / `default`，发完之后字段变成什么）与 `attrs.sends`（发几次：缺省或 `-1` 不限、`0` 从第一帧就锁住）。
- **字段的类型在字段上**：`kind`（`InputKind` 六个词，`Picker` 另有 `PickerKind`）；`Bind` 不再带 `type`，读与写都没有第二个说法。

## 3. 决定

- **组的载荷永远是打包对象**，没有裸值特例。单字段的组发 `{tag: value}`，处理器自己取值（`value["name"]`）。`tools/gate_t4.py` 第 6 条钉的就是这个形状：包里是裸值，没有 `{data, payload}` 那层包装。
- **`tag` 只由写页面的人给，绝不从 `id` 推**。`id` 是节点身份（列表行的键、`patch`/`remove` 的地址、一次提交的实例标记），`tag` 是 wire 上的成员名。从 `id` 推等于把 UI 标识升成协议契约：改一次 `id` 就改一次线上形状。
- **字段不设"有 `sink` 没 `tag`"的守卫**。那种"没人收的值"的守卫（`_parse.py` 的 `_check_uplinks` 与它用的 `FIELD_TYPES`）只在上游还留着字段级 `sink` 时才有意义；wire 上那个键没了之后，没有 `tag` 的字段就是"不上行"，不是一种可拒绝的畸形。守卫随 2026-11-25 那次 schema 同步删除，手工构造的裸 dict 里再出现字段级 `sink` 由生成的模型拒绝（`parse()` 抛 `ValidationError`）。
- **清空与次数归组**：`reset` 与 `sends` 挂在 `loom` 上（`h.loom(..., reset=…, sends=…)`），字段没有这两个词。聊天页的发送组是 `reset="clear"`（发完输入框自己清空），设置页是 `reset="keep"`（设置项不是提交一次就作废的东西）。
- **`kind` 不再挪成组属性**：它已经是字段的类型，组只管打包。

## 4. 落地

- `schema/accrete.schema.json` 同步到 fluxen 的导出（`LoomAttr` 有 `reset` 与 `sends`，新增 `$defs.ResetMode`），`tools/gen_sdk.py`、`tools/gen_rust.py` 重新生成——`h.loom(..., reset=…, sends=…)` 由此出现。
- 两棵树的独立输入进组：`demo_app.py` 的回声输入 → `h.loom(h.input(tag="name"), sink=echo, submit=["enter"])`，`echo` 读 `value["name"]`；`demo_counter.py` 的步长输入 → 同样的组，`set_step` 读 `value["step"]`。
- 聊天页的发送组加 `reset="clear"`。
- 测试与夹具：`tests/test_sdk_generated.py`（带 `tag` 的字段、字段级 `sink` 被模型拒绝）、`tests/types_fixture.py` 的 `input` 条目补 `tag`、`tests/test_counter.py` 的载荷是数字（`{"step": 5}`，空盒是 `None`）。
- 门：`gate_t4` 改成断言"无 `tag` 的字段回车什么都不发、也不清空"，`gate_t10` 的 Rust 夹具按新签名与新页面同步（逐字节相等）。
- 收口：字段的 `sink` 从 wire 退场之后，`_check_uplinks` 与 `FIELD_TYPES` 删除，`gate_t4` 的引言、`tests/types_fixture.py` 的注释同改。

## 5. 代价

- **一个字段要上行就包一层组**：即使只有一个输入框也付一个 `loom` 节点的钱。买到的是一次发送只有一个地方定义（时机、清空、次数都在那里）。
- **处理器拿到的是对象**：每一处取值多一层（`value["tag"]`），"单值组"没有语法糖——有糖就有第二个形状，而这一轮的整件事是取消第二个形状。
- **忘了 `tag` 不再报错**：字段只是不进包、不上行，页面在处理器那侧才看得出少了一项。写页面的地方没有编译器，渲染器也没有可拒绝的形状。
- **组里的回车不等于发送**：字段的回车只提交进组（`gate_t4` 第 4 条：一帧都不发），发不发由 `attrs.submit` 与组的按钮决定。旧写法里"回车即上行"的直觉要改。

## 6. 不做

- 不从 `id` 派生 `tag`，也不给 `id` 加一个"顺便当名字"的模式。
- 不把字段级 `sink` 以"本地落点"的名义留下：本地落点是**组的**（`sink` 的 `scope: local` 加 `submit: ["change"]`，上游 ADR 0032 §2 的同一个形状），一个节点不答两个问题。
- 不在 SDK 里替没有 `tag` 的字段补一个名字（`field-1` 之类）：那是把"忘了写名字"变成"有一个你没写过的名字"。
- 不把 `reset` / `sends` 做成字段属性：它们是一次提交之后的事，提交的出口在组上。