"""The demo's content: what the page says and what the hosts draw, as data.

Ported from fluxen's `examples/walkthrough.py` and `examples/yaml/00.radar.yaml` (extracted
2026-11-24, fluxen `8f8fd84`). Those two files stay the origin of the story; this one is what reflux
can read without a YAML parser or a checkout of the other repo. A change there does not reach here —
re-run the extraction if the story itself moves.

Nothing in this module knows about slots, frames or the page: it is text, chart specs and a graph.
`page.py` is the player that puts them on screen.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "ANALYTICS",
    "BEATS",
    "DEPTS",
    "GRAPH_LINKS",
    "GRAPH_NODES",
    "GRAPH_REVEAL",
    "GRAPH_SEED",
    "PATCH",
    "PATCH_CODE",
    "RADARS",
    "REVIEW",
    "SAY_CAR",
    "SAY_GRAPH",
    "SAY_SHOE",
    "SUMMARY",
    "TAIL_DAYS",
    "TREND",
    "graph_payload",
]

# ---- 六段叙述：逐字来自 walkthrough.py ------------------------------------------
ANALYTICS = """先看一组模拟数据：11 个人、3 个部门，每人每天按各自的维度打分——研发部 5 项（出勤纪律、工作质量、工作量投入、协作沟通、学习成长），市场部 6 项（另加创新性），运营部 7 项（再加客户意识），0–5 分，连续 30 天。下面第一张图是三个部门的日均分走势，第二张把每个部门的每个人叠在同一个坐标系里比形状（三张雷达分别是 5 / 6 / 7 轴，轴数跟着数据走）；再附一张复核表，可以逐人改分并提交。"""
SUMMARY = """总结：近 30 天三个部门的平均分整体稳中有升；研发部波动最大（3.20–4.07），市场部次之，运营部最平稳且收在高位，末尾两天三个部门同步回落。"""
SAY_CAR = """先从体量大的看起。这台车不是网格模型——它没有面片、没有 UV、也没有贴图，而是几十万个高斯椭球按位置、尺度和朝向堆出来的（学术名字叫 3D Gaussian Splatting）。

可以把它想成一团"会发光的雾"：每个点自带颜色、透明度和方向，渲染时按视线方向排序，再把每个椭球投影到屏幕上混合成图像——不是先还原成三角形再算光照。好处很直接：它保留的是真实拍摄的观感。钣金的反射、车窗的厚度、边缘那圈高光，都会一次性带过来，不用人工建模、也不用猜材质参数。代价同样明确：文件大、要按视角排序、没法像网格那样随手改拓扑或者绑骨骼做动画。所以它现在的定位更像"把真实场景搬进浏览器"，而不是替代游戏里的网格资产。

这台车可以拖动围着转，滚轮拉近看细节。你注意到的远近层次是它自带的——这也是这类重建看起来比低模"实"的原因。"""
SAY_SHOE = """换一件小的。这两件东西的共同点是——都不是靠参数表说服人，而是靠"看起来、转起来是什么样"。所以文字我只给必要的部分，剩下的直接给你一个能转的三维模型。

这双鞋解决的问题不是"让你跑得更快"，而是"跑完之后脚还能要"。一双鞋的价值很少体现在某一次能多跑两秒，更多体现在明天你还愿不愿意出门。中底是上下两层的密度配方：上层软，负责落地那一下的缓冲；下层偏硬，负责把力还给你。踩下去先被吃掉大半冲击，再把你推回地面，所以它不像纯软底那样"踩得深、起不来"。系带做的是快拉式，一只手一次收紧，戴手套也操作得了；鞋面是一整片针织，没有拼接缝线，长距离之后不会在脚背和脚趾外侧磨出硬边。鞋楦偏中性，前掌留了大概一个拇指的余量，宽脚也塞得进去。

下面就是这个模型：左键拖动绕它转一圈，看侧墙的支撑结构和鞋底的纹路；右键拖动是平移，滚轮缩放。"""
PATCH = """最后一步换个方向：前面都在"看"，这一段是"改"。下面这块编辑器是 Monaco——VS Code 用的那个编辑器内核。代码不是嵌在页面里的：它和上面两件商品一样是随消息下来的一个参数，写进数据槽，编辑器订阅这个槽。

这意味着两件事。一是库的下载由载荷到达决定——编辑器这一段文字先到，Monaco 那四点几兆的库要等代码真的送上来才拉，所以"消息里有编辑器"不等于"首屏多下四兆"。二是上行同一条腿：改两笔、按 Ctrl/Cmd+S，整段代码连同语言 id 会沿复核表提交走的那条通道回给生产者，生产者据此回写文件或发起评审。

试着改一行——比如把 collect() 换成别的东西——然后按 Ctrl/Cmd+S，看 stage 控制台的 `<-` 块。"""
SAY_GRAPH = """最后看一眼左边那张图——它一直在这儿，只是你没注意到。这一页的布局从第一秒就是这个形态：左边一张常驻的关系图，右边一条流。没有菜单，没有标签页，也没有频道列表。原来的界面把"去哪儿"交给分类，而分类是写完就不改的一次性判断；这里把"去哪儿"交给关系，关系是当下的——"和这件事相连的还有谁"，树状菜单天然答不了。

图里是这套东西自己：圆点是 crate / 组件 / 外部模块，线是"谁渲染谁、谁挂载谁"，点越大、线越粗，表示它在链条上的位置越重。有两处值得看一眼。第一，它不是外包给某个 JS 图库的：渲染、力布局、相机、拾取全在这套 wasm 里，所以旋钮进的是 DSL 的类型化字段（节点尺寸、边的宽度、力参数），不是透传给别人的黑盒配置——也因此没有 three.js 那 1.4 MB。第二，图是长出来的：刚才送的那几份整份快照按节点 id 求差量，组件一批批加进来，已经站好的点不会重排；最后一下是一次距焦——相机飞向那几个节点，别的没消失，只是退到后面。搜索落地时就是这么动的。

左键拖动转视角，滚轮缩放，点一个节点会往上回一条事件。"""

PATCH_CODE = """pub fn render(nodes: &[Node]) -> Frame {
    // 改两笔再按 Ctrl/Cmd+S：整段代码连同语言 id 会从同一条上行通道回上去
    nodes.iter().map(Node::draw).collect()
}
"""

# 折线比 summary 多的那 15 天（09-18 … 10-02），一天一帧追加进 `trend`；
# 三个数是三个部门的日均分，顺序同 `DEPTS`。
DEPTS = ('研发部', '市场部', '运营部')
TAIL_DAYS = [
    ('09-18', 3.53, 3.53, 3.53),
    ('09-19', 3.64, 3.42, 3.77),
    ('09-20', 3.45, 3.38, 3.9),
    ('09-21', 3.28, 3.37, 3.67),
    ('09-22', 3.36, 3.51, 3.7),
    ('09-23', 3.55, 3.41, 3.8),
    ('09-24', 3.6, 3.45, 3.78),
    ('09-25', 3.77, 3.68, 3.77),
    ('09-26', 3.85, 3.46, 3.87),
    ('09-27', 3.92, 3.7, 4.03),
    ('09-28', 3.81, 3.65, 4.11),
    ('09-29', 3.57, 3.63, 3.95),
    ('09-30', 3.38, 3.41, 4.08),
    ('10-01', 3.2, 3.28, 4.03),
    ('10-02', 3.39, 3.2, 4.0),
]

# 泼溅车那只相机：3DGS 场景自带一套坐标约定，这一组是 GaussianSplats3D 演示页
# （demo/truck.html）对这个场景用的那组 —— 换成查看器的默认值，场景是歪的。
TRUCK_CAMERA = {
    "up": [0, -1, -0.17],
    "position": [-5, -1, -1],
    "lookAt": [-1.72477, 0.05395, -0.00147],
}

# 折线 spec（前 15 天，09-03 … 09-17）：G2 自己的语法，数据与编码两样，不描述画法。
# `data` 之后由 TAIL_DAYS 逐日追加到 30 天 —— 整份 spec 重设一次，图就长一格。
TREND: dict[str, Any] = {
    'type': 'line',
    'data': [
        {'day': '09-03', 'avg': 4.07, 'dept': '研发部'},
        {'day': '09-03', 'avg': 3.95, 'dept': '市场部'},
        {'day': '09-03', 'avg': 4.18, 'dept': '运营部'},
        {'day': '09-04', 'avg': 3.86, 'dept': '研发部'},
        {'day': '09-04', 'avg': 3.97, 'dept': '市场部'},
        {'day': '09-04', 'avg': 4.11, 'dept': '运营部'},
        {'day': '09-05', 'avg': 3.64, 'dept': '研发部'},
        {'day': '09-05', 'avg': 3.97, 'dept': '市场部'},
        {'day': '09-05', 'avg': 3.88, 'dept': '运营部'},
        {'day': '09-06', 'avg': 3.61, 'dept': '研发部'},
        {'day': '09-06', 'avg': 3.75, 'dept': '市场部'},
        {'day': '09-06', 'avg': 3.67, 'dept': '运营部'},
        {'day': '09-07', 'avg': 3.57, 'dept': '研发部'},
        {'day': '09-07', 'avg': 3.92, 'dept': '市场部'},
        {'day': '09-07', 'avg': 3.48, 'dept': '运营部'},
        {'day': '09-08', 'avg': 3.43, 'dept': '研发部'},
        {'day': '09-08', 'avg': 3.98, 'dept': '市场部'},
        {'day': '09-08', 'avg': 3.71, 'dept': '运营部'},
        {'day': '09-09', 'avg': 3.47, 'dept': '研发部'},
        {'day': '09-09', 'avg': 3.93, 'dept': '市场部'},
        {'day': '09-09', 'avg': 3.95, 'dept': '运营部'},
        {'day': '09-10', 'avg': 3.24, 'dept': '研发部'},
        {'day': '09-10', 'avg': 4.11, 'dept': '市场部'},
        {'day': '09-10', 'avg': 3.84, 'dept': '运营部'},
        {'day': '09-11', 'avg': 3.2, 'dept': '研发部'},
        {'day': '09-11', 'avg': 3.92, 'dept': '市场部'},
        {'day': '09-11', 'avg': 3.75, 'dept': '运营部'},
        {'day': '09-12', 'avg': 3.36, 'dept': '研发部'},
        {'day': '09-12', 'avg': 3.76, 'dept': '市场部'},
        {'day': '09-12', 'avg': 3.79, 'dept': '运营部'},
        {'day': '09-13', 'avg': 3.43, 'dept': '研发部'},
        {'day': '09-13', 'avg': 3.69, 'dept': '市场部'},
        {'day': '09-13', 'avg': 3.81, 'dept': '运营部'},
        {'day': '09-14', 'avg': 3.21, 'dept': '研发部'},
        {'day': '09-14', 'avg': 3.47, 'dept': '市场部'},
        {'day': '09-14', 'avg': 3.66, 'dept': '运营部'},
        {'day': '09-15', 'avg': 3.3, 'dept': '研发部'},
        {'day': '09-15', 'avg': 3.44, 'dept': '市场部'},
        {'day': '09-15', 'avg': 3.57, 'dept': '运营部'},
        {'day': '09-16', 'avg': 3.34, 'dept': '研发部'},
        {'day': '09-16', 'avg': 3.41, 'dept': '市场部'},
        {'day': '09-16', 'avg': 3.47, 'dept': '运营部'},
        {'day': '09-17', 'avg': 3.49, 'dept': '研发部'},
        {'day': '09-17', 'avg': 3.51, 'dept': '市场部'},
        {'day': '09-17', 'avg': 3.34, 'dept': '运营部'},
    ],
    'encode': {'x': 'day', 'y': 'avg', 'color': 'dept', 'shape': 'smooth'},
    'style': {'lineWidth': 2},
    'scale': {'y': {'domain': [3.0, 5.0]}},
    'interaction': {'tooltip': {'crosshairs': True}},
}

# 三张雷达：部门内每人一条闭合多边形，轴数由数据的 `dim` 值决定（5 / 6 / 7），
# spec 里没有"维度数"这个旋钮；颜色 = 姓名。
RADARS: dict[str, Any] = {
    'radar_rd': {
        'type': 'view',
        'data': [
            {'dept': '研发部', 'name': '张伟', 'dim': '出勤纪律', 'value': 4.4},
            {'dept': '研发部', 'name': '张伟', 'dim': '工作质量', 'value': 4.1},
            {'dept': '研发部', 'name': '张伟', 'dim': '工作量投入', 'value': 3.6},
            {'dept': '研发部', 'name': '张伟', 'dim': '协作沟通', 'value': 4.7},
            {'dept': '研发部', 'name': '张伟', 'dim': '学习成长', 'value': 4.0},
            {'dept': '研发部', 'name': '李娜', 'dim': '出勤纪律', 'value': 3.9},
            {'dept': '研发部', 'name': '李娜', 'dim': '工作质量', 'value': 4.6},
            {'dept': '研发部', 'name': '李娜', 'dim': '工作量投入', 'value': 4.2},
            {'dept': '研发部', 'name': '李娜', 'dim': '协作沟通', 'value': 3.6},
            {'dept': '研发部', 'name': '李娜', 'dim': '学习成长', 'value': 4.4},
            {'dept': '研发部', 'name': '王强', 'dim': '出勤纪律', 'value': 4.6},
            {'dept': '研发部', 'name': '王强', 'dim': '工作质量', 'value': 4.9},
            {'dept': '研发部', 'name': '王强', 'dim': '工作量投入', 'value': 4.5},
            {'dept': '研发部', 'name': '王强', 'dim': '协作沟通', 'value': 3.2},
            {'dept': '研发部', 'name': '王强', 'dim': '学习成长', 'value': 3.6},
            {'dept': '研发部', 'name': '刘洋', 'dim': '出勤纪律', 'value': 3.6},
            {'dept': '研发部', 'name': '刘洋', 'dim': '工作质量', 'value': 3.8},
            {'dept': '研发部', 'name': '刘洋', 'dim': '工作量投入', 'value': 4.8},
            {'dept': '研发部', 'name': '刘洋', 'dim': '协作沟通', 'value': 4.0},
            {'dept': '研发部', 'name': '刘洋', 'dim': '学习成长', 'value': 4.6},
        ],
        'coordinate': {'type': 'polar'},
        'scale': {'x': {'padding': 0.5, 'align': 0}, 'y': {'domain': [0, 5], 'tickCount': 5}},
        'axis': {'x': {'grid': True, 'title': None}, 'y': False},
        'legend': {'color': {'layout': {'justContent': True}}},
        'children': [
            {
                'type': 'area',
                'encode': {'x': 'dim', 'y': 'value', 'color': 'name'},
                'style': {'fillOpacity': 0.15, 'lineWidth': 0},
            },
            {
                'type': 'line',
                'encode': {'x': 'dim', 'y': 'value', 'color': 'name'},
                'style': {'lineWidth': 2, 'join': 'round', 'cap': 'round'},
            },
        ],
        'interaction': {'tooltip': {}},
    },
    'radar_mkt': {
        'type': 'view',
        'data': [
            {'dept': '市场部', 'name': '陈静', 'dim': '出勤纪律', 'value': 4.2},
            {'dept': '市场部', 'name': '陈静', 'dim': '工作质量', 'value': 3.7},
            {'dept': '市场部', 'name': '陈静', 'dim': '工作量投入', 'value': 4.8},
            {'dept': '市场部', 'name': '陈静', 'dim': '协作沟通', 'value': 4.5},
            {'dept': '市场部', 'name': '陈静', 'dim': '学习成长', 'value': 3.4},
            {'dept': '市场部', 'name': '陈静', 'dim': '创新性', 'value': 3.9},
            {'dept': '市场部', 'name': '杨帆', 'dim': '出勤纪律', 'value': 4.6},
            {'dept': '市场部', 'name': '杨帆', 'dim': '工作质量', 'value': 4.2},
            {'dept': '市场部', 'name': '杨帆', 'dim': '工作量投入', 'value': 3.8},
            {'dept': '市场部', 'name': '杨帆', 'dim': '协作沟通', 'value': 4.1},
            {'dept': '市场部', 'name': '杨帆', 'dim': '学习成长', 'value': 4.5},
            {'dept': '市场部', 'name': '杨帆', 'dim': '创新性', 'value': 4.9},
            {'dept': '市场部', 'name': '赵磊', 'dim': '出勤纪律', 'value': 3.8},
            {'dept': '市场部', 'name': '赵磊', 'dim': '工作质量', 'value': 4.0},
            {'dept': '市场部', 'name': '赵磊', 'dim': '工作量投入', 'value': 4.2},
            {'dept': '市场部', 'name': '赵磊', 'dim': '协作沟通', 'value': 4.8},
            {'dept': '市场部', 'name': '赵磊', 'dim': '学习成长', 'value': 3.2},
            {'dept': '市场部', 'name': '赵磊', 'dim': '创新性', 'value': 3.6},
        ],
        'coordinate': {'type': 'polar'},
        'scale': {'x': {'padding': 0.5, 'align': 0}, 'y': {'domain': [0, 5], 'tickCount': 5}},
        'axis': {'x': {'grid': True, 'title': None}, 'y': False},
        'legend': {'color': {'layout': {'justContent': True}}},
        'children': [
            {
                'type': 'area',
                'encode': {'x': 'dim', 'y': 'value', 'color': 'name'},
                'style': {'fillOpacity': 0.15, 'lineWidth': 0},
            },
            {
                'type': 'line',
                'encode': {'x': 'dim', 'y': 'value', 'color': 'name'},
                'style': {'lineWidth': 2, 'join': 'round', 'cap': 'round'},
            },
        ],
        'interaction': {'tooltip': {}},
    },
    'radar_ops': {
        'type': 'view',
        'data': [
            {'dept': '运营部', 'name': '孙悦', 'dim': '出勤纪律', 'value': 4.8},
            {'dept': '运营部', 'name': '孙悦', 'dim': '工作质量', 'value': 4.1},
            {'dept': '运营部', 'name': '孙悦', 'dim': '工作量投入', 'value': 4.5},
            {'dept': '运营部', 'name': '孙悦', 'dim': '协作沟通', 'value': 4.3},
            {'dept': '运营部', 'name': '孙悦', 'dim': '学习成长', 'value': 3.5},
            {'dept': '运营部', 'name': '孙悦', 'dim': '创新性', 'value': 3.2},
            {'dept': '运营部', 'name': '孙悦', 'dim': '客户意识', 'value': 4.0},
            {'dept': '运营部', 'name': '周军', 'dim': '出勤纪律', 'value': 5.0},
            {'dept': '运营部', 'name': '周军', 'dim': '工作质量', 'value': 3.9},
            {'dept': '运营部', 'name': '周军', 'dim': '工作量投入', 'value': 4.4},
            {'dept': '运营部', 'name': '周军', 'dim': '协作沟通', 'value': 4.0},
            {'dept': '运营部', 'name': '周军', 'dim': '学习成长', 'value': 3.7},
            {'dept': '运营部', 'name': '周军', 'dim': '创新性', 'value': 3.4},
            {'dept': '运营部', 'name': '周军', 'dim': '客户意识', 'value': 3.8},
            {'dept': '运营部', 'name': '吴敏', 'dim': '出勤纪律', 'value': 4.1},
            {'dept': '运营部', 'name': '吴敏', 'dim': '工作质量', 'value': 4.3},
            {'dept': '运营部', 'name': '吴敏', 'dim': '工作量投入', 'value': 4.6},
            {'dept': '运营部', 'name': '吴敏', 'dim': '协作沟通', 'value': 4.9},
            {'dept': '运营部', 'name': '吴敏', 'dim': '学习成长', 'value': 4.0},
            {'dept': '运营部', 'name': '吴敏', 'dim': '创新性', 'value': 3.6},
            {'dept': '运营部', 'name': '吴敏', 'dim': '客户意识', 'value': 4.5},
            {'dept': '运营部', 'name': '郑华', 'dim': '出勤纪律', 'value': 4.5},
            {'dept': '运营部', 'name': '郑华', 'dim': '工作质量', 'value': 4.0},
            {'dept': '运营部', 'name': '郑华', 'dim': '工作量投入', 'value': 4.2},
            {'dept': '运营部', 'name': '郑华', 'dim': '协作沟通', 'value': 4.1},
            {'dept': '运营部', 'name': '郑华', 'dim': '学习成长', 'value': 3.8},
            {'dept': '运营部', 'name': '郑华', 'dim': '创新性', 'value': 3.5},
            {'dept': '运营部', 'name': '郑华', 'dim': '客户意识', 'value': 3.9},
        ],
        'coordinate': {'type': 'polar'},
        'scale': {'x': {'padding': 0.5, 'align': 0}, 'y': {'domain': [0, 5], 'tickCount': 5}},
        'axis': {'x': {'grid': True, 'title': None}, 'y': False},
        'legend': {'color': {'layout': {'justContent': True}}},
        'children': [
            {
                'type': 'area',
                'encode': {'x': 'dim', 'y': 'value', 'color': 'name'},
                'style': {'fillOpacity': 0.15, 'lineWidth': 0},
            },
            {
                'type': 'line',
                'encode': {'x': 'dim', 'y': 'value', 'color': 'name'},
                'style': {'lineWidth': 2, 'join': 'round', 'cap': 'round'},
            },
        ],
        'interaction': {'tooltip': {}},
    },
}

# 复核表三行：key / 字段类型 / 初值 / 姓名 / 部门 / 日均分 / 备注。三种字段各一
# （number / bool / text）——初值就是那一格显示的值，类型决定读者怎么改它。
REVIEW: tuple[tuple[str, str, Any, str, str, str, str], ...] = [
    ('zw', 'number', 4.13, '张伟', '研发部', '4.13', '后半月走低'),
    ('cj', 'bool', False, '陈静', '市场部', '4.24', '波动最大'),
    ('sy', 'text', '已复核', '孙悦', '运营部', '4.28', '收在高位'),
]

# 左边那张关系图：这套东西自己。圆点是 crate / 组件 / 外部模块，线是「谁渲染谁、谁挂载谁」，
# `weight` 定点的尺寸、`strength` 定边的粗细。33 点 / 42 线 —— 小图全都长成一团，
# 而这一页要的恰恰不是一团。
GRAPH_NODES = [
    {'id': 'accrete', 'name': 'accrete', 'kind': 'crate', 'weight': 9},
    {'id': 'ui_leptos', 'name': 'ui_leptos', 'kind': 'crate', 'weight': 8},
    {'id': 'stage', 'name': 'stage', 'kind': 'crate', 'weight': 6},
    {'id': 'content', 'name': 'content', 'kind': 'crate', 'weight': 7},
    {'id': 'transport', 'name': 'transport', 'kind': 'crate', 'weight': 5},
    {'id': 'transport_ws', 'name': 'transport_ws', 'kind': 'crate', 'weight': 4},
    {'id': 'forcegraph', 'name': 'forcegraph', 'kind': 'crate', 'weight': 7},
    {'id': 'ui_assets', 'name': 'ui_assets', 'kind': 'crate', 'weight': 4},
    {'id': 'accrete_macro', 'name': 'accrete_macro', 'kind': 'crate', 'weight': 3},
    {'id': 'ui_leptos_macro', 'name': 'ui_leptos_macro', 'kind': 'crate', 'weight': 3},
    {'id': 'fluxen', 'name': 'fluxen', 'kind': 'crate', 'weight': 6},
    {'id': 'frame', 'name': 'frame', 'kind': 'component', 'weight': 7},
    {'id': 'canvas', 'name': 'canvas', 'kind': 'component', 'weight': 7},
    {'id': 'rack', 'name': 'rack', 'kind': 'component', 'weight': 6},
    {'id': 'pages', 'name': 'pages', 'kind': 'component', 'weight': 5},
    {'id': 'form', 'name': 'form', 'kind': 'component', 'weight': 6},
    {'id': 'popup', 'name': 'popup', 'kind': 'component', 'weight': 4},
    {'id': 'layer', 'name': 'layer', 'kind': 'component', 'weight': 5},
    {'id': 'fold', 'name': 'fold', 'kind': 'component', 'weight': 4},
    {'id': 'svg', 'name': 'svg', 'kind': 'component', 'weight': 4},
    {'id': 'portal', 'name': 'portal', 'kind': 'component', 'weight': 3},
    {'id': '3dbrowser', 'name': '3dbrowser', 'kind': 'module', 'weight': 5},
    {'id': 'splatviewer', 'name': 'splatviewer', 'kind': 'module', 'weight': 5},
    {'id': 'g2chart', 'name': 'g2chart', 'kind': 'module', 'weight': 4},
    {'id': 'monaco', 'name': 'monaco', 'kind': 'module', 'weight': 6},
    {'id': 'mermaid', 'name': 'mermaid', 'kind': 'module', 'weight': 3},
    {'id': 'leptos', 'name': 'leptos', 'kind': 'lib', 'weight': 7},
    {'id': 'wasm_bindgen', 'name': 'wasm_bindgen', 'kind': 'lib', 'weight': 6},
    {'id': 'web_sys', 'name': 'web_sys', 'kind': 'lib', 'weight': 6},
    {'id': 'serde', 'name': 'serde', 'kind': 'lib', 'weight': 5},
    {'id': 'tokio', 'name': 'tokio', 'kind': 'lib', 'weight': 4},
    {'id': 'binaryen', 'name': 'binaryen', 'kind': 'tool', 'weight': 3},
    {'id': 'trunk', 'name': 'trunk', 'kind': 'tool', 'weight': 3},
]

GRAPH_LINKS = [
    {'source': 'ui_leptos', 'target': 'accrete', 'kind': 'renders', 'strength': 5},
    {'source': 'ui_leptos', 'target': 'ui_leptos_macro', 'kind': 'generates', 'strength': 3},
    {'source': 'accrete', 'target': 'accrete_macro', 'kind': 'generates', 'strength': 3},
    {'source': 'ui_leptos', 'target': 'ui_assets', 'kind': 'loads', 'strength': 3},
    {'source': 'ui_leptos', 'target': 'forcegraph', 'kind': 'mounts', 'strength': 4},
    {'source': 'forcegraph', 'target': 'accrete', 'kind': 'node', 'strength': 4},
    {'source': 'stage', 'target': 'content', 'kind': 'encodes', 'strength': 5},
    {'source': 'stage', 'target': 'ui_leptos', 'kind': 'serves', 'strength': 4},
    {'source': 'stage', 'target': 'transport', 'kind': 'bridges', 'strength': 3},
    {'source': 'transport', 'target': 'transport_ws', 'kind': 'extends', 'strength': 3},
    {'source': 'transport', 'target': 'content', 'kind': 'carries', 'strength': 3},
    {'source': 'content', 'target': 'serde', 'kind': 'derives', 'strength': 3},
    {'source': 'transport', 'target': 'serde', 'kind': 'derives', 'strength': 2},
    {'source': 'transport_ws', 'target': 'tokio', 'kind': 'runs-on', 'strength': 3},
    {'source': 'fluxen', 'target': 'stage', 'kind': 'starts', 'strength': 4},
    {'source': 'fluxen', 'target': 'transport_ws', 'kind': 'starts', 'strength': 3},
    {'source': 'frame', 'target': 'accrete', 'kind': 'node', 'strength': 5},
    {'source': 'frame', 'target': 'ui_leptos', 'kind': 'mounted-by', 'strength': 3},
    {'source': 'canvas', 'target': 'ui_leptos', 'kind': 'mounted-by', 'strength': 3},
    {'source': 'rack', 'target': 'ui_leptos', 'kind': 'mounted-by', 'strength': 3},
    {'source': 'rack', 'target': 'pages', 'kind': 'rows', 'strength': 3},
    {'source': 'pages', 'target': 'frame', 'kind': 'arranges', 'strength': 2},
    {'source': 'form', 'target': 'accrete', 'kind': 'node', 'strength': 3},
    {'source': 'form', 'target': 'ui_leptos', 'kind': 'mounted-by', 'strength': 2},
    {'source': 'popup', 'target': 'ui_leptos', 'kind': 'mounted-by', 'strength': 2},
    {'source': 'layer', 'target': 'ui_leptos', 'kind': 'mounted-by', 'strength': 2},
    {'source': 'fold', 'target': 'layer', 'kind': 'stacks-in', 'strength': 2},
    {'source': 'svg', 'target': 'ui_leptos', 'kind': 'mounted-by', 'strength': 2},
    {'source': 'portal', 'target': 'layer', 'kind': 'escapes-to', 'strength': 2},
    {'source': '3dbrowser', 'target': 'canvas', 'kind': 'mounts', 'strength': 4},
    {'source': 'splatviewer', 'target': 'canvas', 'kind': 'mounts', 'strength': 4},
    {'source': 'g2chart', 'target': 'canvas', 'kind': 'mounts', 'strength': 3},
    {'source': 'monaco', 'target': 'canvas', 'kind': 'mounts', 'strength': 5},
    {'source': 'mermaid', 'target': 'canvas', 'kind': 'mounts', 'strength': 3},
    {'source': 'leptos', 'target': 'wasm_bindgen', 'kind': 'compiles-to', 'strength': 4},
    {'source': 'web_sys', 'target': 'wasm_bindgen', 'kind': 'binds', 'strength': 4},
    {'source': 'ui_leptos', 'target': 'leptos', 'kind': 'built-with', 'strength': 5},
    {'source': 'forcegraph', 'target': 'web_sys', 'kind': 'draws-with', 'strength': 5},
    {'source': 'forcegraph', 'target': 'wasm_bindgen', 'kind': 'binds', 'strength': 3},
    {'source': 'trunk', 'target': 'ui_leptos', 'kind': 'builds', 'strength': 3},
    {'source': 'trunk', 'target': 'binaryen', 'kind': 'shrinks-with', 'strength': 2},
    {'source': 'binaryen', 'target': 'wasm_bindgen', 'kind': 'optimises', 'strength': 2},
]

# 第一帧就站着的那些（crate 层与渲染它的壳），其余跟着说出它的那一段到场：
# 一条边只在两端都在台上时才出现。
GRAPH_SEED = [
    'accrete',
    'accrete_macro',
    'canvas',
    'content',
    'fluxen',
    'forcegraph',
    'form',
    'frame',
    'layer',
    'leptos',
    'pages',
    'rack',
    'serde',
    'stage',
    'transport',
    'transport_ws',
    'ui_assets',
    'ui_leptos',
    'ui_leptos_macro',
    'wasm_bindgen',
    'web_sys',
]

# (段落的标签, 随它到场的节点 id) —— 标签就是 `BEATS` 里的那几行。
GRAPH_REVEAL = [
    ('分析引言', ('g2chart', 'fold')),
    ('图表落位', ('svg', 'mermaid')),
    ('复核表与表单', ('popup', 'portal')),
    ('泼溅车', ('3dbrowser', 'splatviewer')),
    ('鞋的网格模型', ('monaco',)),
    ('代码编辑器', ('trunk', 'binaryen', 'tokio')),
    ('关系图段落', ()),
]


def graph_payload(revealed: set[str] | frozenset[str]) -> dict[str, Any]:
    """Cumulative snapshot for the ids on screen: a link needs both of its ends.

    Cumulative, not a per-node patch, because one write is one physics push — the component diffs
    by node id, so re-sending what is already there is a no-op and an append never re-frames the
    camera.
    """
    nodes = [node for node in GRAPH_NODES if node["id"] in revealed]
    links = [link for link in GRAPH_LINKS if link["source"] in revealed and link["target"] in revealed]
    return {"nodes": nodes, "links": links, "focus": None}


# 播放的十一段：名字是给读者看的那一行状态，也是 `GRAPH_REVEAL` 的键。
BEATS: tuple[str, ...] = (
    "消息入场",
    "分析引言",
    "图表落位",
    "三十天",
    "摘要",
    "复核表与表单",
    "泼溅车",
    "鞋的网格模型",
    "代码编辑器",
    "关系图段落",
    "距焦",
)
