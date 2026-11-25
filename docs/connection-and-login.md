# 连接与登录：从握手到 ctx.user

一份写给**写应用的人**的说明，加一份写给**改框架的人**的对照。两半都要，因为这两件事在 reflux 里分属两侧：连接与握手是框架的，登录的"怎么证明"是应用的。

## 一、连接：谁先说，说了什么

页面加载后，客户端 runtime（`www/static/reflux.js`）做四件事，然后交班：

1. 等渲染器发布 `window.fluxen.send`（它由渲染器的第一次渲染给出，先于它调用会抛错、整页空白）；
2. `codec` 与 `token` 是**这一层自己的决定**，不是渲染器的：runtime 显式 `mount(el, {codec:"json", token})`，渲染器只负责拼进 WS 地址（fluxen ADR 0046 之后它连页面 URL 都不再读）；
3. `hooks.open` 里上行一帧 `reflux:hello`，载荷 `{path, query?, token?}`——**每一次连接**都发（重连是另一次握手，服务端那时是另一个人），不是"页面启动一次"——`path` 是**应用路径**（`<base>` 前缀已换算），`query` 只在有查询串时出现，`token` 只在浏览器存着凭证时出现；
3. 监听 `popstate`：后退/前进时上行 `reflux:nav`，同一种载荷；
4. 之后它只做镜像：读 DOM 上的 `reflux:path` / `reflux:title` / `reflux:token` 三个标记，写地址栏、标题、`localStorage`，并把页面选项的 `data-accent` / `data-round` 落成 `:root` 的 `--accent` / `--round`。

服务端 `_on_hello`（`reflux/app.py`）收到后，四步：

1. `location_of(frame)` 定下这个连接的 path 与 query；
2. `_adopt(device, token)`：认出的 token 把这个连接绑回同一个人，认不出就**保持匿名**——不是错误，是"过期的凭证什么也没换来"；
3. `request_draw(device)` 并 await：**第一帧就是这一页**；
4. 首次连接再 `announce("connect", …)`，交给应用自己的钩子。

刷新为什么还是同一个人：token 存在浏览器里，新连接带着它上来，第 2 步把身份接回去。所以"登录状态"在 reflux 里有两个位置——服务端的注册表（token→user）与浏览器的存储（token 本身），框架不信任任何别的东西。

## 二、登录：一个口子，一个元组

应用要认证，就写一个 `login` 口子：

```python
from reflux import App, Auth
from reflux.sdk import builders as h

app = App()

@app.hooks("login")                       # 第二个参数可改线上的事件名：@app.hooks("login", "登录事件")
def login(ctx, credentials, mode):        # mode 是 "login" 或 "signup"
    user = accounts.check(credentials)    # 你自己的验证：查库、问别的服务、绑 LDAP 都行
    if user is None:
        return (False, "用户名或密码不对")   # 失败：第二个元素是给人看的一句话
    return (True, user.id, {"nick": user.nick})   # 成功：账号 id + 应用自己的 info
```

返回值是**元组，第一个元素是成功标志**：

| 返回 | 框架做什么 |
|:--|:--|
| `(True, user_id, info)` | 绑这个连接、轮换凭证、重画页面；`info` 存进 `app.sessions[user_id]` |
| `(False, reason)` | 不绑定，把 `reason` 写在登录面上 |
| 别的东西 | 记日志，按失败处理，用框架自己的话说"形状不对" |

`user_id` 必须是字符串（框架的唯一事实）；`info` 是应用的自由形状，框架**从不读它的键**，只原样交回。

### 登录面

```python
@app.hooks("login.request")               # 自定义登录面；不写就用框架自带的两字段屏
def login_screen(ctx, state):             # state: "login" | "signup" | "refused"
    return h.frame(
        h.text("登录", variant="title"),
        h.input(tag="name", kind="text"),
        h.input(tag="password", kind="password"),
        h.button("登录", sink=h.Sink(dest="login", path="/")),
    )
```

登录面画在保留槽 `auth` 里——**不是整页**，因为 `create` 会替换整页。

### 门：哪些东西要人

```python
@app.page("/settings", auth=True)         # 没有登录时：页面照画，登录面同时打开
def settings(ctx):
    return h.text(f"你好，{ctx.session.get('nick') or ctx.user}")

@app.on(app.slot.go.secret, auth=True)    # 匿名发来的这个事件，处理器看不到它
def secret(ctx):
    ...
```

判定只问声明（`auth=True`），不看处理器内部。被拒的事件**在投递前**就被丢掉，应用永远不知道有人试过；框架自己打开登录面并记一行日志。`login` / `logout` 这些动词永远不被门拦——否则回到系统里的路自己堵死。

## 三、用户的登录信息在哪

| 你要的 | 拿法 | 说明 |
|:--|:--|:--|
| 是谁 | `ctx.user` | 字符串 id；匿名时 `None` |
| 应用自己的资料 | `ctx.session` | 就是 `(True, user_id, info)` 里的 `info`；匿名时 `{}` |
| 台账 | `app.sessions` | 按 user_id 索引，跨连接存活（重启即失，持久化是应用的事） |
| 别的设备 | `ctx.devices` / `ctx.device_of(id)` | 房间快照 |

`ctx.user` 是框架的、`ctx.session` 是应用的——这条线不要越，越了框架就得理解你的字段。

## 四、常见形状

```python
# 短写法：Auth(verify=…) 会被降级到同一个 login 口子，运行时只有一张表
app = App(auth=Auth(verify=async_check, view=my_screen, idle_window=3600))
```

- 不做认证：什么都不写。没有 `login` 口子就**没有门**（不是一把锁着的门），`login` 帧会被当未注册拒掉。
- 撤销：`logout` 帧丢掉这个连接上的 token；下次连接就是匿名。

## 五、改框架的人看这里

- `app.hooks(name, event=None)` 是唯一的扩展点注册表：`login` / `login.request` / `shell`。
- `_attempt()` 调 `login` 口子、`_verdict()` 读返回值、`_enable_auth()` 在注册口子时建 token 表并挂上三个动词。
- `_refuse_gated()` 在投递前拦人；`_draw()` 在页面带 `auth=True` 且连接匿名时打开登录面。
- 登录成功后：drop 旧 token → mint 新 token → `device.data["user"]` → `app.sessions[user] = info` → 重画。
