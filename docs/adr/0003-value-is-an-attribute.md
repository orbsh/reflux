# 0003 — 值的读写口是 `.value` 这个属性，不换 SolidJS 的 `()`／`set()`

Status: **Accepted**（2026-11-26）。只定名字与形状，不改代码：今天的 `reflux/signals.py` 已经是这个决定的结果。

## 1. 需求

页面上的一个值需要一个读写口，而写的人希望它同时满足三件事：

1. **读到表达式里**：`f"…{step.value:+d}"`、`min(max(wanted, 1), 10)`、`refusal.value or step_line(step.value)`。
2. **写是一行赋值**：`count.value += by * step.value` —— 自增、读-改-写、批量里连写几个值，都不该拆成两句。
3. **两种写法不能并存**：同一件事有两套拼写，读代码的人要先判断"这是哪种信号"，那这层就不该存在。

## 2. 事实：`.value` 不是我加的新语法，主语换过三次

| 版本 | 值存在哪 | 页面怎么写 |
|---|---|---|
| `28d7187^`（信号之前） | 不存在"值"，槽只装节点；计数是页面自己的普通字段 | `self.value += by * current.step` 之后手动 `slots.count.set(current.value)` |
| `2db356e`（槽带值） | 槽自己长了个细胞（`.signal(0)`） | `slot.value` |
| `1bf0004` 起（信号是主语） | 值在 `Signal` 上，槽只是地址 | `signal.value` |

第一阶段的原文还在历史里：`slots.count.set(current.value)` —— 值与节点是两份，忘记写槽就与页面脱节，`id`／`variant` 也在每个 `set` 处重写。信号层引入的正是"值"这个东西；**一旦有了值，就必须有人拥有它**。

而"必须定义一个属性"是 Python 的约束，不是选型：给裸名字赋值（`count = 3`）只能落成局部变量，语言层面没有钩子。要拦截写入只剩三条路——属性、`__setattr__`、描述符。描述符（`__set_name__`）只能在类体里声明，而这一层已经把声明放在页函数头部（`docs/DESIGN.md:153`「槽的值：信号」），所以它出局。剩属性，名字取 `value`：它是 Vue `ref` 一带的老约定，而且从第二阶段沿用到第三阶段时拼写不用改。

## 3. 决定

- `Signal.value` 是**同一个对象上的读写口**：`@property` 读（同时登记依赖），`@value.setter` 写（相等就提前返回，否则写槽、再通知读者）。
- `Computed.value` 同名同义（派生值的读口）。
- `.store()` / `.bind()` / `.view()` / `.keyed()` 是**声明链**，`.value` 与槽无关：一个没绑槽的信号（`refusal = Signal("").store("counter.refusal")`）照样 `.value` 读写，只是没人直接画它。
- 不提供 `__call__`，不提供 `.set()`／`.update()`：一个读的口、一个写的口，都在 `.value` 上。

## 4. 备选一：SolidJS 的元组（读函数 + 写函数）—— 不可行

```js
const [count, setCount] = createSignal(0);
count();  setCount(1);  setCount(c => c + 1);
```

直译到 Python 是"声明返回一对"：

```python
count, set_count = signals.Signal(0).bind(slots / "counter" / "count").view(...)
```

这条在我们的声明链上不成立：链的产物是**信号**，而一对得由最外层给出。要么 `.bind()`／`.view()`／`.keyed()`／`.store()` 全都返回一对（读口上再挂 `.view` 是什么？），要么链路断成两句：

```python
count = signals.Signal(0)
count.bind(slots / "counter" / "count").view(...)   # 读的名字与写入口分成两个对象
```

Solid 能这么写，是因为它的声明就是一次解构，之后没有链；我们的声明是链，元组与链天然打架。

## 5. 备选二：`()` 读 + `.set()`／`.update()` 写 —— 可行，但净收益为负

同一个对象，读靠调用，写靠方法。`examples/zh/demo_counter.py` 这一段会变成：

```python
def record(label: str) -> None:
    seq.update(lambda n: n + 1)
    row = (f"log-{seq()}", f"{label} → {count()}")
    history.update(lambda rows: (rows + [row])[-HISTORY:])

def change(by: int) -> None:
    with signals.batch():
        count.update(lambda c: c + by * step())
        record(f"{by * step():+d}")
```

逐条比：

| 轴 | `.value` | `()` + `.set/.update` |
|---|---|---|
| 读 | `count.value` | `count()`（更短） |
| 自增 | `count.value += 1` | `count.update(lambda c: c + 1)`，或 `count.set(count() + 1)`（两次调用，中间可被重入） |
| 表达式里 | `f"{count.value} → {step.value}"` | `f"{count()} → {step()}"`（更短） |
| 订阅 | 读即登记依赖，只在 Computed／绘制里生效 | 调用即登记，规则相同 |
| 存函数值 | 无歧义（`signal.value = fn` 就是存一个函数） | Solid 的 `setCount(fn)` 把函数当更新器，存函数必须包一层；`set`／`update` 分开可避开 |
| 名字数量 | 一个对象一个名字 | 一个对象一个名字（`.set` 形态），或两个（元组形态） |

读的拼写确实短了五个字符；代价是**每一个读-改-写都要拆成"取-算-放"**，`+=` 和"读一次用三处"（`f"{by * step.value:+d}"` 里读两次）都没有了。这一页会从 10 处 `.value`（全仓 `examples/` 32 处）变成等量的 `()` 加若干 `update(lambda …)` —— 行数不减，表达式变长。净收益为负。

## 6. 代价与已知缺陷

- **同一个拼写，两种命运**：绑了槽的写会画到页面（`count`），没绑槽的写只通知读者（`refusal` → `hint`）。区别由 `.bind()` 那一处声明承担，读代码要往上看几行。这不是 `.value` 造成的，但 `.value` 让它看起来一样。
- **没有只读视图**：`signal.value = …` 在任何持有者手里都能写。Solid 的元组在这里有真实优势（只读组件拿不到 setter）—— 但那是**语义**差异，正确的补法是将来给一个只读句柄（`signal.readonly()` 之类），不是在拼写上做文章。
- **写相同的值不会通知**（setter 提前返回），所以重复同一句拒绝是空操作；`refusal.value = ""` 在已经是空串时也一样。
- **处理器里的读不是订阅**：`step.value` 出现在 f-string 里只是取值；订阅只发生在 Computed／绘制里执行的时候。这一点两种形状相同。

## 7. 不做

- 不加 `__call__`：两个读的口比一个更糟（"到底该用哪个"是每次读都要做的决定）。
- 不加 `.set()`／`.update()` 作为 `.value` 的别名：同上，而且 `update` 的更新函数形态正是 Solid 那个函数值歧义的来源。
- 不把信号做成描述符：与"声明写在页函数头部"的裁决冲突（`docs/DESIGN.md:153`）。
- 不为"只读"另造一个类型：等真有页面需要把值往下传而不许改时再谈，那时是一个 `readonly()` 视图，不是第二个 Signal。