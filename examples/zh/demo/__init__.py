"""走查页：fluxen 的演示故事，作为参考应用的一条路由。

参考应用（`examples/zh/demo_app.py`）故意写得小 —— 它演示的是"一个应用在这套 wire 上长什么样"。
这一页是内容：用的词表相同，但话多得多，它的文案、图表 spec 与关系图都在 `scene.py` 里。导入这个
包就是声明这一页的路由（框架的发现机制就是 import，见 `reflux/routes.py`），而 `page.register`
把它四条上行挂到要它的那个应用上。
"""

from . import page

__all__ = ["page", "scene"]
