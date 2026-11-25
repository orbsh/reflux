# 持久化的 UI 状态（durable signals，落在 okm）

想法，未实现。它是 `reactive-signals.md` 的第二半：那一半让**值**驱动界面，这一半让**值**活过连接。收集原因同上——页面今天的写是"处理器里算完立刻写槽"，状态住在 `ctx.data`（连接级），刷新即归零、重启即清零。

## 一、它换来的六件事

1. **抗重启与零丢数。** 今天 `ctx.data` 是这条连接的，两个标签页各数各的，刷新即归零——`examples/zh/demo_counter.py` 的 docstring 自己写着"这个页面没有数据库，也不需要"。接上存储之后，断网重连、换设备登录、后端发版重启，都回到断开的最后一毫秒。
2. **时间旅行（撤销 / 重做 / 审计）。** 每次 `Signal` 变更都留下一条记录，多步撤销、操作审计、把某个时刻的界面快照分享给别人看，都不需要额外业务逻辑。**这一条不能照抄 Fjall 的 MVCC**：okm 的后端是可替换的（`fjall` / `redb` / `ephemeral` / remote），其中 `ephemeral` 那一档明确写着没有 journal、没有 compaction、没有 snapshot（`okm-core/src/engine.rs` 的模块文档，ADR-0072），而 fjall 的快照是引擎内部的，不通过 okm 的读接口暴露。所以历史要自己存——一份当前行 + 一条按 `seq` 递增的历史链，撤销就是回放。
3. **长耗时任务与在线状态解耦。** 十分钟的 agent 任务、转码、爬取：用户关掉网页走人，worker 继续把 `progress.value = 65` 写进存储；两小时后打开，界面挂到最新状态，直接看到 100%。
4. **多端同步与多人协同。** 状态一旦离开单个连接的 `ctx.data`，同一个 `owner` 的键就成了唯一数据源：手机点一下，电脑不刷新就跳变；多个用户绑同一个共享键（房间、看板），就是实时协同。okm 的 `subscribe`（`Event{op, epoch, key, document}` + `EventSink`）本身就是变更源，reflux 侧按 `owner` 找 `ctx.devices` 广播即可，不需要自己造轮子。
5. **突破单机内存上限。** 十万个历史用户的上下文全堆在 Python 内存里换来的就是 OOM。落到 okm 之后，冷数据在磁盘上，进程里只留活跃的那部分。**压缩这条不归这一层**：okm 不管压缩（它取决于底下选的后端），LZ4/Zstd 要自备，或者接受原样落盘。
6. **状态即数据库，排障跟着变。** 不再维护"前端临时状态 + 数据库表结构"两套模型，也就没有那层互相转换的代码。线上出问题，把某个 owner 的那几行捞出来，本地喂给同一个页面，现场就能复现。

一句话：不持久化的响应式 UI 只是一个交互演示器；状态落盘之后，它才是一个自带存储、能断线恢复、能多端协同、也能被复盘的完整应用。

## 二、键与形状（草案）

okm 的 schema 声明在 Rust 侧、由 Python 驱动（ADR-0022 嵌入模式，`import okm`），所以先有两张表，再有 Python 那层适配：

```rust
// 当前值：一个 owner 一条信号一行。owner 定宽在前，name 变宽在最末（okm 的索引定界规则）
#[derive(KeyEncode, Clone, PartialEq, Debug, Default)]
pub struct SignalKey { pub owner: u32, pub name: String }

#[derive(DocumentEncode, Clone, PartialEq, Debug)]
#[ok_ref(SignalKey)]
#[ok_ns(7)]
pub struct SignalRow {
    pub value: Vec<u8>,      // CBOR：信号值本身（数字、字符串、列表、节点）
    pub updated_ms: u64,
    pub version: u64,        // 每次写 +1，撤销/冲突检测都用它
}

// 历史：一条信号一行变更，seq 递增；撤销 = 往回翻，审计 = 顺序读
#[derive(KeyEncode, Clone, PartialEq, Debug, Default)]
pub struct SignalTurnKey { pub owner: u32, pub name: String, pub seq: u64 }
```

三处取舍写在前面：

- **`owner` 不是 `device`。** 按连接存等于刷新就换一份，第 1、4 条好处全丢；按 `user`（或匿名会话 id）存，多端才天然是同一个人。匿名态需要一个稳定 id（cookie 里的），这属框架该给的东西。
- **载荷是 bytes。** okm 的 schema 编译期定死，信号值的形状是页面的事，不该逼着每个页面改一次 Rust；形状交给 CBOR，代价是排障时少一层类型检查。
- **历史是第二张表，不是第二个引擎。** 撤销/审计要的是按 `(owner, name, seq)` 前缀范围扫（`scan_range`），正是 okm 的强项。

## 三、接线：谁在什么时候写

```
连接建立     →  load(owner)：scan_range 拉这个 owner 的全部信号 → 建 Signal
Signal 变脏   →  记进 dirty 集合（不立刻写盘）
batch() 退出 →  一次 flush：dirty 的每一条 put(SignalRow) + 追加一条 SignalTurnKey
断开连接     →  只摘订阅（ReactiveUI 的 cleanups），不删状态
```

要点是**写盘只有两个时机**：`batch()` 退出，和页面的一次投递结束（没有 `batch()` 时）。这跟 `reactive-signals.md` 里那个 `batch()` 是一件事——它的刷新阶段顺手把脏集合交给存储，于是"一次点击 = 一帧网络包 + 一次存储写"。

```python
from okm import SignalStore  # 概念示意：okm-python 目前按声明的 schema 驱动

class Durable:
    def __init__(self, store, owner: int) -> None:
        self.store, self.owner = store, owner
        self.dirty: set[str] = set()

    def load(self, ui: ReactiveUI) -> None:
        for name, row in self.store.scan_range(owner=self.owner):
            sig = Signal(decode(row.value))
            sig.version = row.version
            ui.bind_signal(sig, lambda: self.mark(name))
            ui.signals[name] = sig

    def mark(self, name: str) -> None:
        self.dirty.add(name)

    def flush(self, ui: ReactiveUI) -> None:
        for name in self.dirty:
            sig = ui.signals[name]
            sig.version += 1
            self.store.put(self.owner, name, encode(sig.value), version=sig.version)
        self.dirty.clear()
```

## 四、状态分层：哪些该落盘

这是这套东西真正容易做坏的地方。三档，判据是**"换个连接还算不算它"**：

| 档 | 例子 | 去处 | 寿命 |
| --- | --- | --- | --- |
| 瞬时 | 焦点、hover、弹窗开关、滚动位置 | 只在渲染器里，连 `ctx.data` 都不必 | 一次交互 |
| 会话 | 草稿、筛选条件、当前步骤、AI 对话上下文 | `ctx.data` + okm（按 owner 落盘，带 TTL） | 天/周 |
| 事实 | 任务、订单、账号 | 业务表（本来就该有的那张表），**不是信号表** | 永久 |

判据落在"事实"这一档上最容易出错：把订单塞进信号表，等于用 UI 的写法做业务数据的存储，撤销/审计会变成"用户点了撤销，订单没了"。信号层该存的是**界面认为用户正在看到的那个东西**，不是业务真相。

## 五、按 okm 核过的地方（与照抄 Fjall 会错的地方）

- **一次写一次提交，一批写 N 次提交。** `Collection::put` 把主键、每个访问面的索引项、嵌入子文档、旧文档的引用释放与 reduce RMW 全拼进一个 batch 一次提交，所以**一次语义写 = 一次引擎提交 = 一个崩溃边界**（`okm-core/src/model/document.rs` 的模块文档原话）；跨 ns 的原子性是 store 实例的边界，不是 Collection 的。所以单条信号的写是原子的，而"一批信号一起落"是 N 次提交——半批的风险还在，可选做法是写一条意图行再写值，或者 load 时按 `version` 校验后整批丢弃。
- **没有内建历史，也没有统一的快照读。** 后端可替换（`fjall` feature / `redb` / `ephemeral` / remote 发送器，都实现同一个 `VirtualStorage`），`ephemeral` 自述没有 journal、compaction、snapshot（ADR-0072）；fjall 的 MVCC 属于引擎内部，okm 的读接口给的仍是当前行。时间旅行因此要显式留历史键，不能指望"翻到某个快照"。
- **压缩不归它管。** 取决于选的后端；载荷压缩自备。
- **schema 编译期定死。** 这正是 okm 的取舍（闭集查询），代价是信号形状若要走 schema 就得改 Rust 再编译；把值压成 bytes 是绕开它的办法，换来排障时少一层类型。
- **变更源是现成的。** `okm-core/src/subscribe.rs` 的 `Event{op, epoch, key, document}` 与 `SinkCell::register`，第 4 条（多端/协同）应该接在这里，而不是在 reflux 里自己比对。
- **okm 是嵌入式的。** `bindings/okm-python`（ADR-0022 嵌入模式）意味着它与 reflux 同进程，没有网络往返、没有连接池——这一条比任何远端 KV 都强，也是在 Python 里做这件事的前提。

## 六、两个没有答案的问题

1. **TTL 与膨胀**：`(owner, name, seq)` 的历史会无限长。简单做法是每个 owner 只留最近 N 条（写时顺手删第 N+1 条之前的那条），复杂做法是按时间分桶、冷桶整体丢掉。okm 没有内建 TTL，这一步得自己做。
2. **匿名用户的生命周期**：匿名 owner 的键什么时候过期？没人登录、也没人回来，键就永远在。要么给匿名 owner 一个 TTL，要么登录时把匿名 owner 的行合并到真实 owner（后者要处理名字冲突与 version 单调性）。