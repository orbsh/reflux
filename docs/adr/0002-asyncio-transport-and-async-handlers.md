# 0002 — 服务端搬到 asyncio（aiohttp），处理器就是 `async def`

Status: **Accepted**（2026-11-25），**已落地**：P1–P5 全绿（§13 是五个阶段与各自的证明）。

## 1. 需求

处理器里要能查库、调外部 HTTP。而且这件事不该以"再养一个并发世界"为代价，也不该以"自己维护一份 HTTP 与 WebSocket"为代价。

## 2. 现状，先把事实摆清

传输是 `http.server.ThreadingHTTPServer`，每台设备两个线程：**读线程**（`App.handle`，`for raw in channel`）与**写线程**（`_pump` + `outbox` + `threading.Event` 唤醒 + `stale`/resync 修补），外加一个看门狗线程。`channel.py` 手写 WebSocket 帧（193 行，跑在 `rfile`/`wfile` 上），`server.py` 用 `SimpleHTTPRequestHandler` 供静态文件与 `GET /ws` 升级。一次投递在设备自己的读线程里从头跑到尾；异常只在 `dests._call` 一处被捕获。聊天页的流式回复是一个线程 + `time.sleep` 迭代 `ChatModel.reply() -> Iterator[str]`。

这套东西可用、也已经量过。它的问题只有一个，但是结构性的：**用户代码一旦要等 I/O，就没有体面的地方等**。

## 3. 决定

服务端搬到 asyncio，用 **aiohttp** 承载传输。

- 一条连接 = 一个 task；`/ws` 是一条 `web.get` 路由，升级后是 `WebSocketResponse`。
- 处理器写 `async def`，`await` 数据库与 HTTP 是原生的；同步处理器仍然合法，由框架用 `asyncio.to_thread` 兜住（§5）。两种写法都过 `reflux/settle.py` 的 `maybe()`：协程函数就 await，普通函数进线程；普通函数返回可等待物也照样 await。
- `ctx.emit` / `ctx.slot` / `ctx.device` **保持同步**：它们只是入队与读快照，不 await。await 只发生在处理器自己真的要等的时候，不扩散到写页面用的词表里。
- 取消与超时是原生的：设备 task 结束 → 它派生的子任务（流式回复）被取消；`App(handler_timeout=30.0)` 用 `asyncio.timeout` 包住一次投递。

顺序：一台设备一个 task，两次投递在同一 task 里串行，所以"同一设备不交错"是结构给的，不靠锁。

## 4. 传输怎么落：aiohttp，删代码而不是加代码

- **页面重画是一个排队项，不是一个 task**：`App.request_draw()` 往设备的 `outbox` 里放一个标记，writer 按序执行（`await _draw`）。画页要 await（页面处理器可能查库），而 task 会把它的帧排在调用者下一句 emit 之后——顺序会错。`_draw` 在没有 writer 的设备上（单测的假设备）把协程交回调用者，由它 await。
- **HTTP**：`web.Application` + 一条静态路由（`web.static`）+ 一条兜底路由出 `index.html`（深链与刷新靠它）。今天 `SimpleHTTPRequestHandler` 白给的东西——条件请求、`HEAD`、`Content-Type`、range、路径不逃逸——交给 aiohttp，本仓不再维护那一层。缓存策略仍由本仓决定：`Cache-Control: no-store`（重建的页面永不需要硬刷新）。
- **WebSocket**：`web.get("/ws")` → `WebSocketResponse`。`channel.py` 的帧编解码（掩码、分片、ping/pong、close code）**删掉**；`Channel` 退化成一层约 40 行的适配器（`recv`/`send` → `ws.receive_str`/`ws.send_str`），让 `Device`、门、测试夹具继续对着同一个接口说话。
- **写侧**：`outbox` 列表（有界）+ `asyncio.Event` + 一个 writer task，`await ws.send_str()` / `drain()`。丢弃语义逐条照旧（超容量丢中间、标 `stale`、空闲时用一帧 `create` 重画）。没用 `asyncio.Queue`：语义一样的容器换一个，只是把"丢中间"这条已有的规则重写一遍，不值。
- **出站**：一条 `aiohttp.ClientSession` 在 `@app.startup` 里建、`@app.shutdown` 里关，挂在 `app.http` 上给处理器用（聊天页的 SSE 腿就是它）。这是这两个钩子存在的具体理由，不是仪式。

## 5. 可等待的是什么

`@app.on`（含 `connect` / `location` / `disconnect` 的 announce）、闭包落点、`@app.page` / 单页、`shell`、`Auth.verify` 都可以 `async def`。`app.view` 登记的渲染器**不在其中**：它在 `Slot.set` 里面被调用，而 `Slot` 的写是同步的——让渲染器可 await 就等于让每一次 `ctx.slot(...).patch(...)` 变成 await，那是把整个写页面的词表推翻。渲染器是"值 → 节点"，不是 I/O。

## 6. 同步处理器：`to_thread`，与一条纪律

同步处理器是合法写法（参考应用里大多就是同步的），框架把它 `await asyncio.to_thread(handler, ctx, frame)`：它占一个线程池槽位，不会卡住 loop。

纪律写进文档：**在 loop 上不许阻塞**。同步 DB 驱动、`requests`、`time.sleep`、大块文件 I/O 只能出现在同步处理器里（由 `to_thread` 兜住），否则全部设备一起停。CPU 重的活自己丢线程池，框架不替部署决定。

## 7. 生命周期与入口

- `@app.startup` / `@app.shutdown`：可 async，跑在**服务的那个 loop** 上。`_boot` 在建 site 之前执行（先建 `app.http` 这个共享 `ClientSession`，再跑 startup），所以处理器可以假定它一定在场；`_halt` 在 `app.stop()` 之前执行，**后注册的先跑**，一节钩子抛异常只记一行、其余照跑，最后才关 session。
- `app.http`：服务期的共享出站客户端；不在服务中的 app 上是 `None`。
- `App.start(port, host)` 绑定并开始服务，返回 server；`App.stop()` 结束它拥有的东西（看门狗 + 这个 server），可重复调用；`App.serve()` 是 `start()` + 一个后台线程；`App.serve_forever()` 是 `start()` + 阻塞 + Ctrl-C + 收尾（`tools/serve.py` 现在就是这一行）。`app.loop` 公开，是服务所在的 loop。
- `Server.shutdown()` 的顺序：`_halt`（钩子 + session）→ `app.stop()`（看门狗）→ `runner.cleanup()` → 停 loop、join 线程、**关掉自己的 loop**（不关就漏一个 fd）。
- aiohttp 的 `web.run_app` 不用：它要独占 `asyncio.run`，而 `start()`/`stop()` 的测试形状需要一个可停的 runner。
- `web.Application` 的两个键用 `web.AppKey`（`APP_KEY` / `MOUNTS_KEY`）：字符串键每次运行都发一条 `NotAppKeyWarning`，而且拼错只会在请求时才炸。

## 8. 超时、取消、异常面

- `App(handler_timeout=30.0)`：`asyncio.timeout` 包住一次投递，超时 → 取消 → 记一条 → 设备存活。
- 设备 task 结束时取消它派生的子任务：一个已经不在的连接不值得继续等查询结果。
- `asyncio.CancelledError` **不吞**，继续向上。
- 异常面不变：`dests._call` 仍是唯一捕获点，`Exception` → 计数 + 日志 + 设备存活。

## 9. `ctx.turn()` 不变，代价照旧

缓冲挂在 `ctx` 上，跨 `await` 仍然有效：`with ctx.turn(): … await … …` 是一帧。代价是跨一次网络往返的 turn 一直握着那批操作，客户端在这段时间里看不到东西——"一个 turn 里只发一次网络请求"是使用纪律。

## 10. 谁要跟着改

- `pyproject.toml`：加 `aiohttp>=3.9`；删掉那句 "the rest of reflux stays stdlib-only"——它已经不真（`pydantic-core` 是编译的），而且本仓第一次为传输付依赖账，值得写明是为什么。
- `channel.py`：帧编解码删除；`accept_key` / `is_upgrade` 随 aiohttp 的握手一起删，只留 `Channel` 适配器。
- `server.py`：`SimpleHTTPRequestHandler` 与挂载表 → `web.Application` 的路由（静态 + index 兜底）；`serve_forever` 的位置由 `App.serve()` 接。
- `app.py`：`handle` → 一条连接 task；`_pump` / `flush_device` / `await_frames` / `outbox` → `asyncio.Queue` + `drain`；看门狗 → 一个 task；`Device.emit` 从"唤醒线程"变成"入队，必要时调度一次写"。
- `cli.py`：跑 `App.serve()`。这一项随后在 `efe8627`（hooks 改成属性）里随 CLI 一起退场——今天没有 `reflux` 子命令，起应用就是 `App.serve()`／`serve_forever()`（`tools/serve.py` 是那一行）。
- `examples/{zh,en}/chat_model.py`：`Iterator[str]` → `AsyncIterator[str]`；SSE 腿用 `app.http` 的 `ClientSession`（`urllib` 与它的阻塞读一起退场），同步读器与异步读器共用一条行判据。`demo_chat.py` 的流式线程 → task，`threading.Event`/`Lock` → `asyncio.Event`（一个 loop 上一次投递，`busy` 的翻转不需要锁）；设备走了，`disconnect` 的处理器 cancel 那条 task。
- 文档：`docs/DESIGN.md:70` 那句 "`channel.py`（HTTP 升级 + 文本帧编解码，stdlib）" 改写；`HANDOFF` 记 `serve()` 与 `start()` 的分工、`to_thread` 是唯一跨界点。
- 测试夹具：后台起服务的形状保留（`start()`/`stop()`），断言不变；门是端到端的，仍走真实端口。

## 11. 代价

- **一个依赖与它的传递**：`aiohttp` 带 `multidict`/`yarl`/`frozenlist`/`aiosignal`/`attrs`。要在 NixOS 与 CI 里跟版本。
- **一次性重写**：`app.py` 的那几个方法 + `server.py` + `cli.py` + 聊天页 + 夹具；净效果是删掉约 350 行（帧编解码 + HTTP 特例），加上约 300 行改造。十道门与全量测试复跑。
- **阻塞传染**：asyncio 的真实代价，靠 §5 的规则与 `to_thread` 兜住。一个不守纪律的同步处理器现在会影响所有设备——在线程模型里它只影响自己。
- **调试形状变了**：traceback 在 `await` 链上，"任务从未被 await"一类警告要当错误处理。

## 12. 不做

- 不引 ASGI（`starlette`/`uvicorn`）：reflux 有自己的 CLI 与生命周期，aiohttp 一个包就给了 HTTP + WS + 出站客户端；将来若要跑在别人的应用服务器下再谈。
- 不引 ORM、模板引擎或别的框架：那些是应用的事。
- 不把 `ctx` 变成需要 await 的对象：词表对写页面的人保持同步。
- 不在框架里替同步处理器做并发扩张：`to_thread` 一次占一个池位，池的大小是部署的事。

## 13. 五个阶段，各自的证明

**一条硬约束**：`app.make_server(port)` 继续返回同形状的对象（`.server_address` / `.serve_forever()` / `.shutdown()` / `.close()`），内部是"后台线程跑 loop + `AppRunner`/`TCPSite`"。迁移当时的六个 harness 调用点（`tools/cdp.py`、`gate_t7`、`gate_demo`、`gate_ingest`、`tools/serve.py`、`tests/test_page.py`）一行不改——传输被换掉，门与探针的观测面不动，红了才分得清是谁的账。今天同一形状上的调用点是 `tools/cdp.py`、`gate_t7`、`gate_demo`、`gate_ingest`、`tools/measure.py`、`tests/test_page.py`；`tools/serve.py` 后来改成 `app.serve_forever()` 一行（§7）。

| 阶段 | 改什么 | 证明 |
|:--|:--|:--|
| P1 传换 | `server.py` → `web.Application`（每个 mount 一条 `web.static` + index 兜底 + `no-store`）；`/ws` → `WebSocketResponse`；`channel.py` 只留适配器；`App.handle` → `async`；`Device.emit` → `asyncio.Queue` + 每设备 writer task（`await ws.drain()`）；watchdog → task | 十门 + 全量测试；重点 `t7`、`demo`、`chat` |
| P2 可 await | `dests._call`/`_call_local` → `async`（`await maybe(...)`，同步走 `to_thread`）；`_draw`/`shell`/`view` 渲染器/`Auth.verify` 可 await；`App(handler_timeout=30.0)`；`CancelledError` 不吞 | 全门 + 6 条新例（async on/page/view/verify、超时、取消、同设备不交错） |
| P3 生命周期 | `@app.startup`/`@app.shutdown`、`app.http`、`App.serve()`、`start()`/`stop()`、`cli.py` | 门走老形状仍绿；CLI 起得来 |
| P4 聊天页 | `ChatModel.reply` → `AsyncIterator[str]`；流式线程 → task；SSE 腿用 `app.http` | `gate_chat` |
| P5 收尾 | 删 `_pump`/`_wake`/`await_frames`/`flush_device` 残留、`channel.py` 帧编解码、`accept_key`/`is_upgrade`、`threading`；DESIGN 加「并发模型」；HANDOFF 记 `serve()`/`start()` | 全绿 + `grep -rn threading reflux/` 收口 |

每个阶段一个 commit、全门绿才进下一个。P1 里先加一条守卫：处理器返回协程时抛 `TypeError`（P2 之前不支持），不许静默丢弃。P2 的真正工作量在夹具：`tests/fakes.py` 加 `run_sync(coro)`，17 处 `app._draw(...)` 与 5+ 处 `app.handle(channel)` 跟着改形状。