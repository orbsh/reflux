# 响应式信号（`reflux_signals`）—— 一层适配器，不改底层

想法，未实现，没有排期。收集原因：reflux 今天的写是**命令式**的——处理器改状态，然后自己把新节点写进槽；页面每多一个值，就多一处"什么时候写、写什么形状"的决定。这一层把"读时收集依赖、写时通知"搬到 Python 侧，页面只描述"这个位置显示什么"，剩下的交给追踪。它与 `app.view`（值 → 节点的静态声明）不重叠：view 管形状，这一层管依赖。

## 一、机制：它解决的四件事

| 机制 | 解决的核心痛点 | 实现原理 |
| --- | --- | --- |
| ContextVar 追踪栈 | 多用户高并发下，收集依赖不会"串台" | 利用 Python 原生协程/线程隔离变量，精准锁定当前正在执行的副作用函数。 |
| 作用域自然隔离 | 区分"单用户私有状态"与"多用户共享状态" | 写在页面函数内部即连接私有；写在模块全局即多用户实时广播。 |
| 连接生命周期托管 | 全局共享状态在用户关闭网页后发生内存泄漏 | 将连接创建的副作用函数挂载到当前连接上下文中，连接销毁时自动清空订阅引用。 |
| `batch()` 事务合并 | 一次点击修改多个状态导致连续发多次网络包 | 开启批处理上下文，暂存所有触发的更新函数，退出上下文时去重并一次性统一推送。 |

## 二、适配器（`reactive.py`）

原样收录，行内注释是提出时的说法：

```python
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Generic, Iterator, TypeVar

from reflux import Context
from reflux.sdk import h

T = TypeVar("T")

# 协程/线程安全的状态追踪上下文，确保多用户并发时依赖收集互不干扰
_current_effect: ContextVar[Callable[[], None] | None] = ContextVar("_current_effect", default=None)
_batch_depth: ContextVar[int] = ContextVar("_batch_depth", default=0)
_pending_effects: ContextVar[set[Callable[[], None]] | None] = ContextVar("_pending_effects", default=None)


@contextmanager
def batch() -> Iterator[None]:
    """批处理上下文：合并代码块内的多次 Signal 修改，结束时统一刷新一次 UI"""
    depth = _batch_depth.get()
    token_depth = _batch_depth.set(depth + 1)
    token_pending = None
    if depth == 0:
        token_pending = _pending_effects.set(set())
    try:
        yield
    finally:
        if depth == 0:
            pending = _pending_effects.get() or set()
            if token_pending is not None:
                _pending_effects.reset(token_pending)
            _batch_depth.reset(token_depth)
            for eff in pending:
                eff()
        else:
            _batch_depth.reset(token_depth)


class Signal(Generic[T]):
    """响应式状态容器：读取时收集依赖，修改时自动通知订阅者"""

    def __init__(self, initial: T) -> None:
        self._value = initial
        self._subscribers: set[Callable[[], None]] = set()

    @property
    def value(self) -> T:
        eff = _current_effect.get()
        if eff is not None:
            self._subscribers.add(eff)
        return self._value

    @value.setter
    def value(self, new_val: T) -> None:
        if self._value != new_val:
            self._value = new_val
            self._notify()

    def _notify(self) -> None:
        if _batch_depth.get() > 0:
            pending = _pending_effects.get()
            if pending is not None:
                pending.update(self._subscribers)
        else:
            for eff in list(self._subscribers):
                eff()

    def unsubscribe(self, eff: Callable[[], None]) -> None:
        self._subscribers.discard(eff)


class ReactiveUI:
    """绑定到单个用户连接（Context）的响应式 UI 渲染器"""

    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self._seq = 0
        self._cleanups: list[Callable[[], None]] = ctx.data.setdefault("_reactive_cleanups", [])

    def _next_slot(self):
        self._seq += 1
        return self.ctx.slot(f"_rx_{self._seq}")

    def effect(self, fn: Callable[[], None]) -> None:
        token = _current_effect.set(fn)
        try:
            fn()
        finally:
            _current_effect.reset(token)

    def bind_signal(self, sig: Signal[Any], fn: Callable[[], None]) -> None:
        self.effect(fn)
        self._cleanups.append(lambda: sig.unsubscribe(fn))

    def text(self, fn: Callable[[], str], **kwargs: Any) -> Any:
        slot = self._next_slot()
        self.effect(lambda: slot.set(h.text(fn(), **kwargs)))
        return h.text(source=slot)

    def list_tiles(self, items_sig: Signal[list[T]], render_item: Callable[[T], Any], **kwargs: Any) -> Any:
        slot = self._next_slot()
        rendered_ids: list[str] = []

        def sync_list() -> None:
            current_items = items_sig.value
            for old_id in rendered_ids:
                slot.remove(old_id)
            rendered_ids.clear()
            for idx, item in enumerate(current_items):
                item_id = f"rx-item-{self._seq}-{idx}"
                rendered_ids.append(item_id)
                slot.append(render_item(item))

        self.effect(sync_list)
        return h.tiles(source=slot, **kwargs)
```

## 三、用法：私有状态与全服共享

三条界线：写在 `register(app)` 或页面函数里的 `Signal` 属于这条连接（`ReactiveUI` 在 `ctx` 上建，`ctx.data` 天然按连接分）；写在模块顶层的 `Signal` 是全服共享，任何连接写它，所有订阅者都收到；`batch()` 里的多次改动只在退出时刷新一次。

```python
# 模块顶层：全服共享（进程内一份）
global_total = Signal(0)

def register(app: App) -> None:
    @app.page("/counter")                      # 反应式那条路：页面返回结构
    def counter(ctx: Context, match: Match):
        ui = ReactiveUI(ctx)
        # 页面内：这条连接私有
        count = Signal(int(ctx.data.get("count", 0)))
        step = Signal(1)
        history = Signal(list(ctx.data.get("history", [])))

        # 写：一次点击改三个状态，退出 batch 时只刷一轮
        def bump(delta: int) -> None:
            with batch():
                count.value = count.value + delta * step.value
                history.value = [f"{delta:+d} → {count.value}"] + history.value[:5]
                global_total.value = global_total.value + delta
            ctx.data["count"] = count.value

        return h.frame(
            ui.text(lambda: str(count.value), variant="heading-1"),
                ui.text(lambda: f"全服 {global_total.value}", variant="muted"),
                h.loom(h.button("+", sink=lambda _: bump(+1)), sink=lambda _: bump(+1), submit=["button"]),
                # 行 id 由适配器生成并交给渲染函数，`remove` 才命得中（提案原文的 `render_item(item)`
                # 拿不到 id，这是要改的一处签名）
            ui.list_tiles(history, lambda row, row_id: h.text(row, id=row_id)),
        )
```

## 四、落地注意事项

1. **断开连接时的资源回收**：用了全局信号就必须在连接关闭时摘掉订阅，否则每次关页面都留一个绑定在 `Signal._subscribers` 里的闭包。reflux 的宿主事件是 `connect` / `location` / `disconnect`，所以这条挂在 `@app.on("disconnect")` 上，遍历执行 `ctx.data["_reactive_cleanups"]`，然后清空这份列表。
2. **避免在 effect 里做阻塞 I/O**：赋值会同步触发更新函数，数据库或外部接口的调用留在事件处理器里，拿到结果再写 `Signal.value`。

## 五、按今天的 reflux 核过的地方

这些是对着代码确认过的，写在这里免得实现时再猜一遍：

- `ctx.slot(f"_rx_{n}")` 成立（`Slots.__call__`，`reflux/slots.py:180`）；`slot.set/append/move/patch/remove` 都在，`append` 的 `position=0` 是**尾插**（`wire.append`：`0` 是尾巴，`+n` 从尾数，`-n` 从头数）。
- `h.tiles(source=slot)` 成立（`tiles` 有 `source`）。
- `ctx.data` 是连接级：两个标签页各一份，与计数器页今天的写法一致。
- **没有 `ctx.on_close`**：清理要挂在 `@app.on("disconnect")`（`App.on` 接受框架自己的宿主事件名字符串）。
- **"一次点击发多个包"在 reflux 侧是可选的**：`with ctx.turn():` 会把块内所有写收成一帧（`reflux/app.py:337` `_Turn`），但处理器派发本身不自动开 turn，所以今天多次 `slot.set()` 确实是多帧。因此 `batch()` 的值在于**副作用去重**（同一 effect 一轮只跑一次），并且它的刷新阶段应当顺手套一层 `ctx.turn()`——那样一次批处理正好一帧，两件事合成一件。
- **`Signal.value` 的 `!=` 对节点与列表是结构比较**：列表每次都是新对象，`history.value = [...]` 必然通知；按 id 比较（或让调用方自己给 key）能省掉无效重绘。
- **`list_tiles` 的行 id 必须回传给渲染函数**：原文 `slot.append(render_item(item))` 里的 id 是适配器自己造的，而 `remove(old_id)` 也用它——渲染出来的节点却带着另一套 id，`remove` 就打空了。签名改成 `render_item(item, row_id)`，或者要求模型自带 id（后者更干净：行身份本来就不该由渲染位置决定）。
- **effect 每次写的都是新节点**：`ui.text` 每轮 `h.text(...)` 一个新节点、一次 `set`——这是 reflux 的模型本身（写即新帧），声明式只是把"谁来写"从处理器挪到了依赖追踪。

## 六、`Computed`：派生信号

派生信号的处境与 `Signal` 不同：它不是存储，是**计算**。所以要三件事——缓存（别每次读都算）、失效（依赖变了让它变脏）、以及**截断**（算出来的结果与上次相同，就别再通知下游，否则一个 `list.filter(...)` 会在无关字段变化时把整张列表重画一遍）。

追踪栈要从"当前副作用"升级成"当前收集者"，因为一个 `Computed` 计算时也可能读别的 `Computed`，一层 ContextVar 放不下两层嵌套：栈顶是谁，读到的依赖就记在谁名下。

先说清与第二节相比改了什么：`_current_effect` 换成 `_tracking`（栈顶是"谁在读"，可以是一个副作用节点，也可以是一个 `Computed`）；`Signal` 的 `_subscribers` 因此变成 `_observers`（收集者对象，而不是裸函数）；副作用节点要有一个 `invalidate()`——它做的还是原来那件事，把函数跑一遍。

**还有一处第二节那种直连写法撑不住**：一次写要先把整张图标脏、把被叫醒的副作用排进队列，等标记走完再统一跑。原因是重算会在传播途中把已经访问过的节点重新标脏——`summed = a + doubled` 这种"一个信号被两条路径读到"的形状下，直连写法会把同一个效果叫醒两次（照第二节的写法实测输出是 `[9, 15, 15]`，第二轮多跑了一次）。所以下面这段把"标记"与"执行"分开，`batch()` 就是同一个传播轮，只是留得更久。

```python
_UNSET = object()

_tracking: ContextVar[Any] = ContextVar("_tracking", default=None)   # 谁在读
_depth: ContextVar[int] = ContextVar("_depth", default=0)            # 传播轮的嵌套深度
_queue: ContextVar[list[Any] | None] = ContextVar("_queue", default=None)   # 这一轮要跑的副作用


@contextmanager
def _pass():
    """一次传播：最外层的写者开轮，里层的写者搭顺风车。"""
    depth = _depth.get()
    outer = depth == 0
    token_depth = _depth.set(depth + 1)
    token_queue = _queue.set([]) if outer else None
    try:
        yield
    finally:
        if outer:
            queued = _queue.get() or []
            _depth.reset(token_depth)
            if token_queue is not None:
                _queue.reset(token_queue)
            for eff in queued:                 # 标记走完，才跑
                eff.run()
        else:
            _depth.reset(token_depth)


batch = _pass                                   # 批处理就是留得更久的传播轮


class Computed(Generic[T]):
    """派生信号：读时算、依赖变时变脏；值没变就不往下游传。"""

    def __init__(self, fn: Callable[[], T], *, equal: Callable[[T, T], bool] = operator.eq,
                 eager: bool = False) -> None:
        self._fn, self._equal, self._eager = fn, equal, eager
        self._value: Any = _UNSET
        self._dirty = True
        self._sources: set[Any] = set()        # 我依赖谁（动态：每次重算都可能变）
        self._observers: set[Any] = set()      # 谁依赖我

    def add_source(self, node: Any) -> None:
        """`_tracking` 指向我时，读到的信号/派生信号记在这里。"""
        self._sources.add(node)
        node._observers.add(self)

    @property
    def value(self) -> T:
        collector = _tracking.get()
        if collector is not None:
            collector.add_source(self)
        if self._dirty:
            self._recompute(notify=False)      # 谁在读，谁自己就在跑：不必再通知
        return self._value

    def invalidate(self) -> None:
        if self._dirty:
            return
        self._dirty = True
        if self._eager:
            self._recompute(notify=True)       # 立刻算，值真的变了才往下走
        else:
            for obs in list(self._observers):
                obs.invalidate()

    def _recompute(self, *, notify: bool) -> None:
        for src in self._sources:              # 先退掉旧依赖：依赖集合是动态的
            src._observers.discard(self)
        self._sources.clear()
        token = _tracking.set(self)
        try:
            value = self._fn()
        finally:
            _tracking.reset(token)
        changed = self._value is _UNSET or not self._equal(value, self._value)
        self._value, self._dirty = value, False
        if changed and notify:
            for obs in list(self._observers):
                obs.invalidate()


class Effect:
    """一个订阅：`invalidate()` 在一轮里只跑一次，`run()` 才是真的写槽。"""

    def add_source(self, node: Any) -> None:
        self._sources.add(node)
        node._observers.add(self)

    def invalidate(self) -> None:
        queue = _queue.get()
        if queue is not None:                  # 轮开着：等标记走完
            if self not in queue:
                queue.append(self)
            return
        self.run()

    def run(self) -> None:
        for src in self._sources:              # 每次跑之前重收依赖
            src._observers.discard(self)
        self._sources.clear()
        token = _tracking.set(self)
        try:
            self._fn()
        finally:
            _tracking.reset(token)


class Signal(Generic[T]):
    """第二节那个 `Signal`，只改一处：写的时候开一轮。"""

    @value.setter
    def value(self, new_val: T) -> None:
        if self._value == new_val:
            return
        self._value = new_val
        with _pass():
            for obs in list(self._observers):
                obs.invalidate()
```

三处容易写错，代码里都按"必须做对"处理：

- **旧依赖要退掉。** `_recompute` 先清 `_sources` 再算，否则依赖会只增不减——一个 `if flag: a else: b` 的分支切换后，`a` 变了还会把它叫醒。
- **`equal` 决定要不要往下传。** 这就是 memo 的全部价值；比较函数按类型给（列表比 id 序列，节点比 id）。
- **传播与执行必须分开。** 上面那个 `_pass` 不是讲究：直连写法在"一个信号两条下游路径"时会把同一个效果叫醒两次（实测 `[9, 15, 15]`），因为重算会把刚刚访问过的节点重新标脏。推论是 `batch()` 不需要自己一套机制——它就是同一个传播轮保持开启。

- **`eager` 是这笔买卖的开关。** 懒算省 CPU，但"值没变"这件事要到有人读才知道，于是下游那一轮已经被叫醒了；`eager=True` 在失效时立刻重算，`equal` 才真的能挡住下游。默认懒，因为 reflux 的写本来就是"一帧一次"，多算一轮的代价通常小于 eager 的长依赖链。

与其它两件的分界：`app.view` 是"值 → 节点"，`Computed` 是"值 → 值"，`Signal` 是"值 + 谁在看"。三者可以叠：`ui.text(lambda: f"{count.value} × {step.value} = {total.value}")` 里的 `total` 是 `Computed`，页面看不出区别。

**持久化只落基信号。** `Computed` 不需要存——它由基信号重算即可（这正是它与 `Signal` 的区别：可重算的不必存）。`durable-signals.md` 里那张 `SignalRow` 因此只收 `Signal`，恢复时先 load 基信号，再把页面上的 `Computed` 建起来即可。

六节的模型在九条断言上跑通过：嵌套派生（两层 `Computed`）、动态依赖（分支切换后旧依赖不再唤醒）、lazy 与 eager 两种截断、批处理合并，以及「一次写只跑一次效果」。第一个版本跑出 `[9, 15, 15]` 就是因为少了那个传播轮——这条不是推出来的，是跑出来的。

## 七、列表的增量更新（keyed diff）

### 渲染器已经做了这一半

`tiles` 的行在渲染器里是**按 id keyed** 的：`crates/ui_core/src/components/tiles.rs:598` 用 `tachys::view::keyed::keyed`，同一个文件里还有一条 `an_entry_is_keyed_by_its_own_id` 的测试。意思是：只要一行的 id 不变，`append`/`remove` 动别的行时它**不会重建**——焦点、动画、滚动都在。计数器页今天就是这么写的（`slots.history.append(h.text(..., id=ident))` 与 `slots.history.remove(id)`）。

### 适配器丢掉的正是这一半

原稿的 `list_tiles` 每次都 `remove` 全部再 `append` 全部，行 id 还是 `rx-item-<seq>-<idx>`（下标在内）：删中间一行，后面每一行的 id 都变，于是全部重建；一屏十行就是二十次写、两次闪烁。

### 三条规则就够，不需要 LIS

当时 wire 没有 `move` 动作，`append` 的 `position` 只能表达到头/尾的距离（`0` 尾插，`+n` 从尾数，`-n` 从头数），所以"移动"只有一种说法：**删掉再插回**。这个天花板 2026-11-24 拆掉了：渲染器加了 `move`（fluxen ADR 0005），一条帧改行序、行节点复用、焦点不丢；下表第三行因此改写作一次 `move`。

| 变化 | 写法 | 代价 |
| --- | --- | --- |
| 尾部追加（日志、消息流） | 一次 `append` | 一行，零重建 |
| 中间删除 | 一次 `remove(id)` | 一行，其余行 keyed 不动 |
| 重排序 | 一次 `move(id, position)`（`wire.move` / `slot.move`） | 一行；节点 keyed 复用，焦点与光标由渲染器接住 |

```python
def list_tiles(self, items: Signal[list[T]], render_item: Callable[[T, str], Any], *,
               key: Callable[[T], str]) -> Any:
    """`key` 给出行的身份（数据自己的 id）；`render_item(item, row_id)` 必须用那个 id 起节点。"""
    slot = self._next_slot()
    shown: list[str] = []              # 现在屏幕上的行 id，按顺序

    def sync() -> None:
        want = [key(item) for item in items.value]
        if want == shown:              # 顺序没变：只处理增删
            added = set(want) - set(shown)
            kept = set(want) & set(shown)
            for old in shown:
                if old not in kept:
                    slot.remove(old)
            for item in items.value:
                if key(item) in added:
                    slot.append(render_item(item, key(item)))
        else:                          # 顺序变了（或首次绘制）：整表重建
            for old in shown:
                slot.remove(old)
            for item in items.value:
                slot.append(render_item(item, key(item)))
        shown[:] = want

    self.effect(sync)
    return h.tiles(source=slot)
```

三件顺带说清的：

- **id 必须来自数据**，不能来自下标或适配器的计数器——行身份本来就不该由渲染位置决定（这与 `list_tiles` 原文那个"适配器造 id 却让渲染函数自己再起一个"的 bug 是同一件事的两面）。
- **首次绘制用整表重建，之后只走增删**：第一帧没有"旧行"可比，逐行 `append` 与一次写完整列表效果相同，前者还多几个 op。
- **别对列表用 `!=` 判等**（`Signal.value` 的写法）：列表每次赋值都是新对象，判等必然成立、通知必然发出；判断该落在"id 序列"上，那正是 `key` 已经给出的东西。
## 八、原型（已落地 2026-11-25）：`reflux/signals.py`，计数器是第一个使用者

上面六、七两节是设计；落地的东西在 `reflux/signals.py`（`Signal` / `Computed` / `Effect` / `batch` / `effect`）加三个适配器（`bound` / `into` / `keyed`），`examples/{zh,en}/demo_counter.py` 是第一个使用者。与设计稿不同的四处，都是写的时候才看清的：

**1. 截断需要版本号，不只是"脏"标记。** 惰性 `Computed` 的读者如果是副作用本身，脏标记会**先**把它叫醒，等它去读的时候才知道值没变——那时效果已经跑过了。所以每个节点带一个 `_version`（真变才 +1），副作用记下它读到的版本；被"某个派生信号变脏"叫醒的效果排成**存疑**（maybe），到刷新时先拉一遍那些脏派生信号，版本没动就不跑。少了这一层，第七节那张表第三行的收益（"答案没变就不重画"）在直接读者身上完全不成立。

**2. 不要 `ReactiveUI`，也不要 `_rx_N` 私有槽。** 设计稿的 `ui.text(fn)` 每次绘制新建一个 `_rx_1`、`_rx_2`……槽，节点身份每次绘制都换，`app.view` 与页面里的 `source=` 也用不上。原型改成写**页面原有的具名槽**：`bound(ctx, "counter.count", 0)` 让一个信号拥有一个槽（写仍是 `ctx.slot(name).set`，视图照旧由 `app.view` 决定），`into(ctx, name, computed)` 把派生值镜像到槽上。页面一行没改，处理器不再写槽。

**3. `list_tiles` 换成 `keyed(ctx, name, rows, render)`**：`rows` 是 `Signal[[(id, item), ...]]`，行身份**由构造函数给**（不是"渲染函数要记得用回传的 id"），`keyed` 自己在闭包里记着屏幕上的 id —— 计数器原来那本 `State.ids` 因此消失。顺序变化也在这一层解决了：增删之后按"屏幕上已有的位置"求一条最长递增子序列，留在子序列里的行不动，其余逐行 `move` 到自己的位置 —— 要动的行数最少，顺序没变时一条 `move` 都不写。位移用 `move` 的位置词表（`0` = 末尾，`-n` = 从头数第 n 个之前，且在被拎出该行之后的表上计，fluxen ADR 0005）：目标第 i 位写 `-(i+1)`，只有最后一位得写 `0`（`-n` 的域比表长短一格，`-len` 是"最后一个之前"）。

顺带记一个只有真写了一遍才会发现的边界：`-(i+1)` 在 i = len-1 处是 `-len`，落到「最后一个之前」而不是末尾 —— 旋转（`[a,b,c,d]` → `[b,c,d,a]`）正好撞上它，位置写成 `-4` 会被渲染器**拒绝**（不是夹紧）。

**4. 连接清理不需要登记表。** 设计稿用 `ctx.data["_reactive_cleanups"]` 记退订；实际上页面里建的信号持有的是**那条连接**的 `Slot`，信号与连接同生共死，没人会来读一个死连接的信号。模块级信号（多连接共享）反过来是对的：它没有槽，只有读者。

顺带记一个踩到的坑：`bound` 在**构造时**就写第一个值，所以 `ctx.data.setdefault("counter", State(ctx))` 这种写法每次绘制都造一个 State 再扔掉——被扔掉的那个会把读者刚改好的数推回 0。已有测试 `test_the_value_is_seeded_once_not_per_draw` 当场抓到；`state()` 因此写成先 `get` 再建。

计数器前后的差别（这就是"能简化多少"的答案）：`slots.hint.set(...)` 从三处收成一处 `Computed`；`counter_seeded` 那个"只种一次"的守卫不需要了（`bound` 只在构造时写）；`State.ids` 那本账交给 `keyed`；处理器从"改值 + 写槽"变成"改值"。层数没有变多：页面仍然读 `h.text(source=slots.count)`，`app.view` 仍然决定值长什么样——`signals` 只决定**谁**去写。

## 九、第二个使用者：演示页的列表（每连接一张表）

参考应用的「列表 · 拖拽」那格原来是三套写法并存：处理器 `slots.rows.append(...)`、`remove(id)`、落点里 `remove(id)`，再加一个 `rows_seeded` 只种一次的守卫。现在列表是这条连接自己的 `Signal([(id, 文本)])`（`rows_of(ctx)` 按 `ctx.data` 取，页里用 `.keyed(row_node).bind(slots / "rows")` 声明，和计数器一页同一个形状），四种动作全是改这张表：加一行 `+ [row]`、✕ 与归档 `[... if id != ...]`、拖到另一行身上则重排 `rest.insert(index, moving)`；`rows_seeded` 随之消失（`bind` 按槽名记在 `ctx.data` 里，第二次画这页交回同一条信号，不再种）。

这一格同时说明了「作用域」那条：**信号在页函数里 = 这条连接的**。`rows_of` 把值挂在 `ctx.data` 上，所以 ✕／落点这两个按名字调用的处理器拿得到同一张表，而另一条连接看不见它 —— 共享列表的写法（`signals.keyed(rows, slot, render)`，模块级一张表、每条连接一份订阅）留在库里，参考应用不再需要它：一条连接的增删不该让另一条看见。

拖拽那半是 `move` 的第一个页面级使用者：行自己那个 `frame` 同时是 `draggable`（货物）和 `accept` + `sink=slots("row.move")`（落点），于是落点报上来的 `id` 说"落在哪一行"、`data.id` 说"哪一行被拖"，一次 drop 两样都有，处理器只重排列表，线上是一帧 `move`（67 B，不带节点）。`gate_t9` 的第 6 条就是这么验的：真浏览器里把最后一行拖到第一行身上，DOM 顺序变了，而这一轮里只多了一帧 `move`。
