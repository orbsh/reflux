# 0005 — 槽的值：信号是主语、槽是去处，`.store(key)` 决定它活多久

Status: **Accepted**（2026-11-26），**已落地**：`reflux/signals.py` 与 `reflux/stores.py` 就是这个决定的结果。读写口为什么叫 `.value` 单独记在 ADR 0003；形状的当前描述在 `docs/DESIGN.md`「槽的值：信号」。

## 1. 需求

页面上的值要同时答四个问题：

1. **谁拥有它**：一处写，页面重画之后还是同一个值，首值不能被再种一遍。
2. **它怎么到页面上**：写页面的人不该在每个处理器里手写"把什么节点塞进哪条槽"；值变了，显示跟着变。
3. **它活多久**：有的值跟着这条连接，有的要跟着用户跨标签页、跨设备。
4. **不写信号的页面照旧能用**：这层是可选的，一页可以只用它管一个数字，其余手写。

## 2. 形状

声明写在页函数头部，一行一条，值在左、去处接在右边：

    step  = Signal(1).store("counter.step")
    count = Signal(0).bind(slots / "counter" / "count").view(_count_node)
    hint  = Computed(lambda: refusal.value or step_line(step.value)).bind(slots / "counter" / "hint").view(_hint_node)
    rows  = Signal([]).keyed(_row).bind(slots / "counter" / "history")

- **三种信号，一条规则**（读 = 订阅，写 = 通知，相等的写不算变）：`Signal` 是值；`Computed` 是派生（脏了才重算，答案相等就不再往下传）；`Effect` 是"读过这些东西的代码"（立刻跑一次，之后依赖变了再跑）。`with batch():` 把一轮传播收在一起——一次按下改两个值，页面只写一轮。
- **信号是主语，槽是它的去处**：`Signal(v).bind(slot)` 说这个值往哪条槽写；`.view(fn)` 说值怎么变成节点（登记在应用上，一个槽名一条）；`.keyed(render)` 让列表槽按 id 对齐（增 `append`、删 `remove`、换位 `move` 最少条）；`.store(key)` 说这个值要活过连接。槽本身只是地址加动词，值永远不在句柄上。
- **这层不写页面**：effect 与动词写的还是 `ctx.slot(name).set(...)`，所以"谁写"归信号、"写成什么样"归 `.view`。写路径没有被改道，这层因此是可选的。
- **一个名字一个信号，一条连接一份**：登记在 `ctx.data`（`signals.CELLS`）里，重画拿回同一个；`keyed` 的列表在声明时就把现有的行 append 上去，之后只跟着信号走。
- **首写等画完**（`signals.drawing`）：值声明在同一行，`.view` 却跟在后面，所以首次写推迟到这次绘制结束——视图都在了，帧才是节点。顺序因此不再由调用者记着"先 view 后值"。
- **不上线的状态也是信号**：计数器页的 `step`、`refusal` 没有槽，只有 `.store(key)`；它们和槽上的值走同一张登记表，不需要额外的 `State` 对象。
- **写槽先于通知读者**：`Signal.value` 的 setter 先跑写入链（`store` 的保存、`bind` 的 `slot.set`），再 `_notify`——页面不会比读到这个值的处理器晚一拍。

## 3. 存储：两个方法，值是 JSON，后端是一个名字

接口只有两次调用，因为一个值只需要这么多：

    store.load(user, key) -> value | None
    store.save(user, key, value) -> None

- **值是 JSON**：活过重连的东西必须是能写下来的东西。节点不是（`h.text(...)` 是页面的，不是关于用户的事实）——存那个数，让 view 去画。写不进去时当场报错（`stores._encode` 抛 `TypeError` 并点名是哪个 key）。
- **匿名连接不落盘**：值存在这条连接自己的 `ctx.data` 里（session）——重画还在，换连接就没了。这不是持久化，只是"别在重画时丢掉"。
- **有用户的连接跟着用户**：`ctx.user` 有值时存在 `app.store`，按 user id；换标签页、换设备接着来，别的用户看不到。
- **后端按名字挂**（`app.set_store(...)`、`create_app(store=...)`，也收一个 `Store` 对象）：`memory`（缺省，进程的生命周期）、`sqlite`（`path`，缺省 `:memory:`）、`kv`（`client` 任何有 `get`/`set` 的对象，加 `prefix`）、`fjall`（`path`，`durable=True` 时每次写 `sync_all`，`pip install reflux[fjall]`）、`redis`（`host`/`port`/`db`…，`pip install reflux[redis]`，`valkey` 同一条）。`stores.make_store` 是那张表，名字不认识时列出它会认的。
- **后端是 extras，不是依赖**：库本身是 `memory` 加标准库的 `sqlite`；没装的后端在第一次使用时给出"装哪个 extra"的消息，不是 import 错。
- **`redis` 排在最后，是容忍不是推荐**：它把一个本来就在这个进程里的数放到一次网络往返之后。部署有它，所以收；"值存在这里"不是它的好用途。

## 4. 否掉的形状

| 形状 | 它的问题 |
|---|---|
| 处理器手写 `slot.set(node)`（信号之前） | 值与节点是两份：忘记写槽，页面就与状态脱节；`id` / `variant` 在每个 `set` 处重写 |
| **槽带值**（`2db356e`：`Slot.signal(0)` / `.computed` / `.keyed`） | 首值是槽的一次写，所以声明顺序成了规则（先 `view` 后 `signal`，反过来 `ValueError`）；而**不上线的值**没有槽可挂，于是页面另有自己的一套（计数器页的 `State` 类与 `state()` 缓存）——一个想法两个主语 |
| **适配器动词**（`signals.bound` / `into` / `own` / `mirror` / `keep`） | 同样的三个机制（值、派生、列表）在槽的构造器与自由函数上各有一套名字；调用者要先判断手上是槽还是信号 |
| `docs/ideas/reactive-signals.md` 的表面（`reactive.py` 的适配层） | 机制留下来了（ContextVar 追踪、`batch`、computed），被否的是表面：声明留在槽上、再包一层适配器，等于给同一件事起两个名字 |

三种信号这一层是**显式声明**：依赖由"读到哪些值"在运行时收集，但**哪里放值、往哪条槽写、活多久**都写在页函数头部的那几行里。读代码的人不必追一次执行的影子栈才知道这页有什么。

## 5. 规矩与它们的理由

- **`.store(key)` 必须在 `.bind(slot)` 之前**：存下的值是这条连接**首写**要带的那个值；先绑槽再读存储，首帧就种了错的值。反过来写是 `RuntimeError`，消息说清楚"store 决定首写"。
- **`.store(key)` 需要一次投递**（写在页面的绘制里，或先绑槽）：没有投递就没有连接、没有用户，值无处安放。不做"模块级 store 猜一个用户"。
- **一个槽名一个值**：同一个槽名第二次 `.bind` 交回第一次那个信号；先登记的是别的东西时是 `RuntimeError`（"one value per name"）。一页一条槽只画一个值，需要两个就是两条槽。
- **`.view` 登记在应用上**：`slot.set(值)` 过 view，`slot.set(节点)` 原样通过——节点就是节点，不做第二次转换。
- **模块级信号是共享的**：声明写在页函数里就属于这条连接（它握着这条连接的槽或 `ctx.data`），写在模块级就是每个连接都读它。一条共享列表配每条连接一条槽的用法是 `signals.keyed(rows, slot, render)`：订阅按连接建，建一次（页面把它记在 `ctx.data` 里，重画不重订）。
- **`keyed` 与 `bind` 的先后**：文档写法是 `.keyed(render).bind(slot)`；反过来也成立，因为 bind 的首写种子在绘制结束才决定，那时已经知道它是 keyed 列表——keyed 列表的首写是它的行，不是列表本身。

## 6. 代价

- **声明有顺序**：`.store` 在 `.bind` 之前、`.view` 在 `.bind` 之后（后一条由延迟首写兜住，前一条是硬规则）。读一页的头几行要按这个顺序读。
- **值跟着声明的地方活**：写在页函数里就死在这条连接上；要共享得挪到模块级，而模块级的值是进程的（重启就没了）。
- **存储只存 JSON**：想存"这个页面长什么样"会当场报错——这是有意的；页面状态归渲染器，用户的事实才进存储。
- **匿名会话不是持久化**：不用登录就活过重连的东西，这个框架不提供；那需要一个身份。
- **一个槽名一个值**：同一份数据要两种画法是 `.view` 的事，不是第二个信号。

## 7. 不做

- 不给所有信号自动持久化：`.store(key)` 是显式声明，一个值要不要活过连接是页面的事。
- 不加只读句柄：`signal.value = …` 在任何持有者手里都能写；Solid 那套元组在这一点上有真优势，但补法是将来一个 `readonly()` 视图，不是在声明链上做文章（ADR 0003 §6）。
- 不做名字常量表或 `Literal` 联合：名字就地写 `slots / "chat" / "send"`，拼错靠 `AttributeError` 与 `/status`（2026-11-26 定）。
- 不给 `Store` 加列举 / 删除 / 遍历：两个方法就是全部；一个值不需要知道还有谁。
- 不让 `App` 自己打开存储：谁开、什么时候关是部署的事，`app.set_store` 只收一个名字或一个对象。