# -*- coding: utf-8 -*-
"""场景内行走 —— 「Ralsei 在房间里自然走过去，并且绕开障碍」的几何层。

回答用户这条需求（第 45 轮续）：
    「过去的路线别太死板，就比如直角拐弯，一直直线走这样的，自然点，
      还有，注意有些场景里是有障碍物的，别把那些障碍物的阻挡效果变没了，
      简而言之就是交互效果和原作一样」

★ 为什么本模块必须存在（与 scene_pathfind 的分工）
------------------------------------------------
`scene_pathfind` 解决的是**房间之间**怎么走（"教堂" → `ch1.town.town_church`，
吃原作 782 条门边、房间级 BFS）。
本模块解决的是**房间之内**怎么走：从当前像素坐标到目标像素坐标，绕开原作障碍物。
两者是**两个不同的图**，不能用同一套机制（前者节点=房间，后者节点=像素格）。

★ 原作障碍机制（第 45 轮反汇编取证，见 _evidence/碰撞机制取证45.md）
---------------------------------------------------------------
· 原作**不用** solid 属性（353 个对象 Solid=True 数为 0）；
· 阻挡 = `obj_mainchara_Step_0` 里对 `obj_solidblock` / `obj_interactablesolid`
  的 `place_meeting`（分轴判定 ⇒ 贴墙滑行是原作行为）；
· 障碍物 = **自由摆放的缩放矩形**（sprite 基准 20×20 × image_scale），
  **不是**瓦片网格 ⇒ 逐实例矩形，禁止网格近似（否则与原作不符）。
数据源：`assets/scenes/_obstacles.ch<章>.json`（逐房间 `[{x,y,w,h,o,r}]`）。

零依赖纪律（🔴 与 scene_routing / scene_pathfind 同源，违反会崩在 import 期）
---------------------------------------------------------------------------
本模块**禁 import Qt、禁 import 任何项目内模块**（只准标准库）。
`main.py` import 期就要建控制器，控制器再 import 本模块；回头 import 项目内模块
就会把「初始化环」接上（已踩 4 次）。

三条设计律（每条都有正/负控制断言）
----------------------------------
1. **走不到就如实说，不硬穿** —— `plan_walk()` 找不到路时返回
   `{'ok': False, 'path': [], 'reason': ...}`，**绝不**返回一条穿过墙的"直线"。
   静默降级是本项目头号敌人。
2. **障碍只增不减、宁可保守** —— 读不到障碍表时按"无障碍"处理（能力降级），
   但**绝不**因为"看起来路被堵死了"就删掉障碍。挡不住是 bug，穿模是事故。
3. **平滑不许把路推出可走区** —— 平滑后的每个采样点都必须重新过一遍
   可走性检测；被推出的点回退到平滑前的位置（宁可不平滑，不可穿墙）。

★ 为什么用 A* 而不是直线插值
--------------------------
原作障碍是**离散摆放**的矩形，房间多为"走廊 + 门框 + 家具"结构，
直线插值会**穿过家具角落**。A*（8 邻接 + 障碍膨胀）能绕开，
且天然给出"沿墙走"的路径 —— 这正是原作角色走位的观感。
"""
import json
import logging
import math
import os

_log = logging.getLogger(__name__)

#: 障碍表 schema 版本。读到不认识 → 拒绝加载（同 scene_system / scene_pathfind 纪律）。
OBSTACLES_SCHEMA_VERSION = 1

#: 障碍表文件名模板（`_` 前缀 = 框架文件，不会被当成场景定义加载）。
_OBSTACLES_TMPL = '_obstacles.ch%d.json'

#: ★★ 主角碰撞盒 —— 实测自原作 sprite 的 **bbox**，不是 sprite 全尺寸！
#:
#:   obj_mainchara.sprite = spr_krisd，sprite 19×38，
#:   但 `MarginLeft=0 MarginRight=18 MarginBottom=38 MarginTop=25`
#:   ⇒ **bbox = x[0,18] y[25,38]** —— 只有下半身（脚/腿）参与碰撞，
#:     头部（y 0~25）不挡路。
#:
#:   ⚠️ 这是第 45 轮的两个真教训：
#:   ① 第一版按"19×38 全高"实现，主角站在原作合法起点
#:      `room_krishallway (242,128)` 时被判撞墙 —— 因为 19×38 的盒子盖到
#:      y[128,166]，而原作只占 y[153,166)。
#:   ② 第二版取 `38-25=13` 作为**高度**（GML 的 bbox 是**半开区间**：
#:      `top=25, bottom=38` 表示像素行 25..37，即 13 行高）。
#:      ⇒ **几何语义（bbox 边界含否 / 原点）必须实测，不能按 sprite 尺寸想当然。**
#:
#:   原点：sprite `OriginX=0 OriginY=0` ⇒ 实例 `(x, y)` = sprite 左上角，
#:   故 bbox 实际范围 = `x[inst_x, inst_x+19) y[inst_y+25, inst_y+38)`。
PLAYER_BBOX_W = 19
PLAYER_BBOX_H = 13
#: sprite 左上到 bbox 左上 的偏移（x 向 0，y 向 25）。
PLAYER_BBOX_OFF_X = 0
PLAYER_BBOX_OFF_Y = 25

#: ★ 网格步长。原作障碍最小 20px（spr_solidsmall），主角宽 19px。
#:   取 10 ⇒ 每格半个最小障碍，精度足够且 A* 规模可控
#:   （room_dark2 640×480 ⇒ 64×48 = 3072 格）。
GRID_STEP = 10

#: ★★ 安全余量（px）：建 A* 格网时给主角 bbox 外扩这么多，
#:   保证"格中心可走"⇒"格间连线也可走"。取 3 ⇒ 覆盖
#:   `round(step/2)` 的舍入误差 + 简化/平滑的轻微外推。
#:   （实测触发值 0.6px，取 3 有 5 倍余量，且不至于把窄门堵死 ——
#:     原作最窄通路是 20px，主角 19px，留 3px 仍可通过 25px 的缝。）
SAFETY_PAD = 3

#: ★★ 允许的「弧长倒退」上限（px）。第 47 轮实测：平滑后路径会冒出
#: **往回走**的抖动（最坏 228px —— 近半间房的宽度，转角 174°~180°）——
#: 真人不会这么走，看着就是 bug。取**半个格步**：比这更小的前后微调
#: 肉眼看不见，允许；超过就必须当成"倒着走"消掉。
BACKTRACK_TOL = GRID_STEP / 2.0

#: ★★ 去尖刺：只有转角 ≥ 这个值（度）的"拐一下又拐回来"才允许删。
#: 取 45° 是**刻意**的：真人走路的**缓弯**（每段转角 < 45°）必须保留 ——
#: 用户明确反对的另一种走法是"一直直线走"（第 45 轮原话），
#: 把缓弯也削掉就是把路拉直。
DESPIKE_MIN_TURN = 45.0

#: 去尖刺最多迭代几轮（删一个点会改变邻居的转角，要迭代到不动点；实测 1~2 轮收敛）。
#: ⚠️ 第51轮曾按"判据变严格后级联会变深"把它临时提到 40 —— **实测推翻了该假设**：
#:   538 组样本里残留的 82 个"可削"尖刺**全部**来自 `smooth_keep_walkable` 的
#:   `bailed` 兜底（那条路径根本没进 `_despike`），不是级联没走完。⇒ 已回退。
DESPIKE_PASSES = 6

#: 8 邻接（含对角）。对角代价 √2 ≈ 1.414。
_NEIGHBORS = (
    (1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
    (1, 1, 1.4142135), (1, -1, 1.4142135), (-1, 1, 1.4142135), (-1, -1, 1.4142135),
)


# ===========================================================================
#  路径
# ===========================================================================

def obstacles_path(chapter, scene_dir_path=None):
    """障碍表绝对路径。文件**不存在也照常返回**（调用方判存在）。"""
    if scene_dir_path is None:
        # 与 scene_system.scenes_dir() 同口径，但**不 import**（零依赖纪律）：
        # 本文件在 <repo>/ralsei_pet/modules/ → 上两级 = <repo>/ralsei_pet
        here = os.path.dirname(os.path.abspath(__file__))
        scene_dir_path = os.path.join(os.path.dirname(here), 'assets', 'scenes')
    return os.path.join(scene_dir_path, _OBSTACLES_TMPL % int(chapter))


# ===========================================================================
#  读取
# ===========================================================================

def load_obstacles(chapter, scene_dir_path=None):
    """读 `_obstacles.ch<章>.json` → `{'ok','rooms','error'}`。**永不抛**。

    `rooms` 形状：`{房间下标(int): {'name': str, 'items': [矩形...]}}`。
    `ok=False` 时 `rooms` 是空 dict —— 调用方按"该章没有障碍"处理（能力降级）。
    """
    result = {'ok': False, 'rooms': {}, 'error': None}
    path = obstacles_path(chapter, scene_dir_path)
    if not os.path.isfile(path):
        result['error'] = '%s 不存在' % os.path.basename(path)
        return result

    try:
        with open(path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
    except Exception as e:
        result['error'] = '读取失败: %s' % e
        return result

    if not isinstance(raw, dict):
        result['error'] = '不是合法 JSON 对象'
        return result

    if raw.get('schema_version') != OBSTACLES_SCHEMA_VERSION:
        result['error'] = 'schema_version 不匹配（期望 %s）' % OBSTACLES_SCHEMA_VERSION
        return result

    rooms_raw = raw.get('rooms')
    if not isinstance(rooms_raw, dict):
        result['error'] = 'rooms 字段缺失或不是对象'
        return result

    # 键是字符串（JSON 限制），转回 int；矩形做**严格校验**：
    # 只要有一个字段缺/非数/宽高<=0，就丢弃该矩形（宁少不坏）。
    rooms = {}
    for k, v in rooms_raw.items():
        try:
            idx = int(k)
        except (TypeError, ValueError):
            continue
        if not isinstance(v, dict):
            continue
        items = []
        for it in (v.get('items') or []):
            rect = _parse_rect(it)
            if rect is not None:
                items.append(rect)
        rooms[idx] = {'name': v.get('name') or '', 'items': items}

    result['ok'] = True
    result['rooms'] = rooms
    return result


def _parse_rect(it):
    """把一条 JSON 矩形转成 `(x, y, w, h, kind)`。**坏数据返回 None**（宁少不坏）。"""
    if not isinstance(it, dict):
        return None
    try:
        x = float(it['x'])
        y = float(it['y'])
        w = float(it['w'])
        h = float(it['h'])
    except (KeyError, TypeError, ValueError):
        return None
    if not (w > 0 and h > 0):
        return None
    raw_o = it.get('o') or ''
    kind = 'interactive' if 'interactable' in raw_o or 'pushable' in raw_o else 'solid'
    return (x, y, w, h, kind)


def room_obstacles(chapter, room_index, scene_dir_path=None):
    """取某一间房的障碍矩形列表。读不到 → `[]`（能力降级，不抛）。"""
    data = load_obstacles(chapter, scene_dir_path)
    if not data['ok']:
        if data['error']:
            _log.debug('障碍表不可用（按无障碍处理）: %s', data['error'])
        return []
    rec = data['rooms'].get(int(room_index))
    if not rec:
        return []
    return rec['items']


# ===========================================================================
#  可走性
# ===========================================================================

def _inflate(rect, pad):
    """把矩形四周外扩 `pad` 像素（用于把"主角体积"吸收进障碍）。"""
    x, y, w, h, kind = rect
    return (x - pad, y - pad, w + 2 * pad, h + 2 * pad, kind)


def blocks_at(obstacles, anchor_x, anchor_y,
              bbox_w=PLAYER_BBOX_W, bbox_h=PLAYER_BBOX_H,
              off_x=PLAYER_BBOX_OFF_X, off_y=PLAYER_BBOX_OFF_Y):
    """主角**锚点**（sprite 左上角，= 原作实例 `x,y`）在 `(anchor_x, anchor_y)`
    时，其碰撞盒是否与任一障碍重叠。

    ★ 坐标语义（避免歧义，这里是唯一权威）：
      · 障碍矩形 `(x, y, w, h)` = **左上角 + 宽高**（与 JSON 数据同义）；
      · 主角锚点 `(anchor_x, anchor_y)` = **sprite 左上角**（与实例 x,y 同义）；
      · 主角 bbox = 锚点 + 偏移 `(off_x, off_y)`，尺寸 `bbox_w × bbox_h`。
      ⇒ 二者**同一坐标系**，可直接比较，不需要做中心化换算
        （第一版搞混"中心 vs 左上"正是那次误判的根因）。
    """
    bx = anchor_x + off_x
    by = anchor_y + off_y
    for rect in obstacles:
        x, y, w, h, _kind = rect
        if (bx + bbox_w > x) and (bx < x + w) and (by + bbox_h > y) and (by < y + h):
            return True
    return False


def hit_obstacle(obstacles, anchor_x, anchor_y,
                 bbox_w=PLAYER_BBOX_W, bbox_h=PLAYER_BBOX_H,
                 off_x=PLAYER_BBOX_OFF_X, off_y=PLAYER_BBOX_OFF_Y):
    """返回第一个命中的障碍矩形（或 None）。给"撞到可交互障碍时做反应"用。

    坐标语义同 `blocks_at()`。
    """
    bx = anchor_x + off_x
    by = anchor_y + off_y
    for rect in obstacles:
        x, y, w, h, _kind = rect
        if (bx + bbox_w > x) and (bx < x + w) and (by + bbox_h > y) and (by < y + h):
            return rect
    return None


# ===========================================================================
#  A* 网格寻路
# ===========================================================================

def _build_grid(obstacles, x0, y0, x1, y1, step=GRID_STEP, pad=SAFETY_PAD):
    """建 `(w0, h0)` 布尔格网：`free[gy][gx] = True` 表示该格中心可站。

    `(x0,y0)-(x1,y1)` 是房间矩形（左上角 + 右下角）。

    ★ 为什么格子里要把主角 bbox **外扩 `pad`**（第 45 轮修的第二个真 bug）：
      A* 只保证**格中心**可走，而格到格的连线会经过格中心之间 ——
      当路径"贴"着障碍边缘（实测：`room_krishallway` 第 44 段锚点 x=503.4，
      障碍右边界 504.0，只差 0.6px）时，简化/平滑后就会越界穿模。
      ⇒ 建格时多留 `SAFETY_PAD` 像素安全余量，让 A* 自己就绕开边缘，
        后续平滑才有腾挪空间。这是「宁可绕远，不可穿墙」律的落点。
    """
    w0 = max(1, int(math.ceil((x1 - x0) / float(step))))
    h0 = max(1, int(math.ceil((y1 - y0) / float(step))))
    bw = PLAYER_BBOX_W + 2 * pad
    bh = PLAYER_BBOX_H + 2 * pad
    ox = PLAYER_BBOX_OFF_X - pad
    oy = PLAYER_BBOX_OFF_Y - pad
    free = []
    for gy in range(h0):
        row = []
        cy = y0 + (gy + 0.5) * step
        for gx in range(w0):
            cx = x0 + (gx + 0.5) * step
            row.append(not blocks_at(obstacles, cx, cy, bw, bh, ox, oy))
        free.append(row)
    return free, w0, h0


def _nearest_free(free, w0, h0, gx, gy, max_r=40):
    """从 `(gx,gy)` 向外螺旋找最近的可走格。找不到 → None。

    ★ 起点/终点可能正好落在障碍里（主角被拖到家具上、或目标点不可站），
    此时不能直接放弃 —— 先找最近可走格，再从那里规划。
    """
    def ok(gx, gy):
        return 0 <= gx < w0 and 0 <= gy < h0 and free[gy][gx]

    if ok(gx, gy):
        return (gx, gy)
    for r in range(1, max_r + 1):
        for d in range(-r, r + 1):
            for cand in ((gx + d, gy - r), (gx + d, gy + r), (gx - r, gy + d), (gx + r, gy + d)):
                if ok(cand[0], cand[1]):
                    return cand
    return None


def _nearest_free_visible(obstacles, free, w0, h0, x0, y0, step,
                          px, py, max_r=40):
    """从 `(px,py)` 螺旋找**最近的、既自身可走、又与 `(px,py)` 直连不穿墙**的格。

    找不到 → None（上层如实报"走不到"）。

    ★★ 这是第 45 轮的第六个真 bug（同样靠"五章全量扫描"暴露）：
      旧版 `_nearest_free()` 只按**欧氏距离**找"最近可走格"，
      **完全不管** `(px,py)` 与那个格之间有没有被障碍挡住。
      实测 `ch1 room_torielclass`：起点 `(140.6,45.7)` 本身可走，
      但"最近可走格"螺旋找到了 `(115,5)`，二者之间横着 `(84,48,142,20)` 那条桌子 ——
      于是路径首段 `(140.6,45.7) -> (115,5)` **直接穿桌**。

      ⇒ 判据必须是"**格可走 且 连线可走**"：
        第 1 项保证主角能站在格里，第 2 项保证"走到格里"这一步本身合法。
        两者缺一，产出的路径都会在**首尾**出现"从真实起终点直插障碍"的段。
    """
    g0 = _grid_of(px, py, x0, y0, step)

    def ok(cand_gx, cand_gy):
        if not (0 <= cand_gx < w0 and 0 <= cand_gy < h0):
            return False
        if not free[cand_gy][cand_gx]:
            return False
        cx, cy = _cell_center(cand_gx, cand_gy, x0, y0, step)
        return _segment_clear(obstacles, px, py, cx, cy,
                              PLAYER_BBOX_W, PLAYER_BBOX_H, step)

    if ok(g0[0], g0[1]):
        return (g0[0], g0[1])
    for r in range(1, max_r + 1):
        for d in range(-r, r + 1):
            for cand in ((g0[0] + d, g0[1] - r), (g0[0] + d, g0[1] + r),
                         (g0[0] - r, g0[1] + d), (g0[0] + r, g0[1] + d)):
                if ok(cand[0], cand[1]):
                    return cand
    return None


def astar(free, w0, h0, start, goal, max_expand=60000,
          obstacles=None, x0=0.0, y0=0.0, step=GRID_STEP,
          bbox_w=PLAYER_BBOX_W, bbox_h=PLAYER_BBOX_H):
    """8 邻接 A*。`start`/`goal` 是格坐标 `(gx,gy)`。

    返回格坐标列表 `[(gx,gy), ...]`（含起终点），找不到 → `None`。
    `max_expand` 是**保险丝**：房间再大也不该爆（超了就放弃，如实返回 None）。

    ★★ 第51轮新增参数（都可省略，省略时行为与旧版**逐字节一致**）
    ------------------------------------------------------------
    `obstacles` / `x0` / `y0` / `step` / `bbox_*` 用于对**对角步**做
    "盒扫掠"复检。为什么必须有（本轮巡行实测暴露的 4 例穿模）：

        "两侧正交格都可走" **不等于** "两个对角格心之间的连线可走"。
        反例（实测构造）：障碍 D 在 `x∈[cx+23,cx+25] y∈[cy+27,cy+30]`。
          · `(cx,cy)` 盒右边界 `cx+22 < cx+23` ⇒ 不撞 ⇒ 格可走；
          · `(cx+10,cy+10)` 盒上边界 `cy+32 > cy+30` ⇒ 不撞 ⇒ 格可走；
          · 但中点 `(cx+5,cy+5)` 盒 = `[cx+2,cx+27]×[cy+27,cy+46]` **完全盖住 D**
            ⇒ 连线穿模。
        ⇒ 只查格是不够的，**必须查"锚点从 A 格心扫到 B 格心"这条线段**。
          正交步不需要（沿轴平移时盒的一个维度不变，两端可走 ⇒ 全程可走），
          所以只在 `dx != 0 and dy != 0` 时做这一步，性能影响可忽略。
    """
    if start is None or goal is None:
        return None
    import heapq

    def h(n):
        return math.hypot(goal[0] - n[0], goal[1] - n[1])

    open_heap = [(h(start), 0.0, start)]
    came = {}
    gscore = {start: 0.0}
    closed = set()
    expanded = 0

    while open_heap:
        _f, g, cur = heapq.heappop(open_heap)
        if cur == goal:
            # 回溯
            path = [cur]
            while cur in came:
                cur = came[cur]
                path.append(cur)
            path.reverse()
            return path
        if cur in closed:
            continue
        closed.add(cur)
        expanded += 1
        if expanded > max_expand:
            _log.debug('A* 超出展开上限 %d，放弃（如实返回 None）', max_expand)
            return None

        cx, cy = cur
        for dx, dy, cost in _NEIGHBORS:
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < w0 and 0 <= ny < h0):
                continue
            if not free[ny][nx]:
                continue
            # ★ 对角不许"切角"：两侧正交格都得可走，否则会从两个障碍的
            #   斜缝里挤过去（视觉上明显穿模）。这是与原作一致的必要条件 ——
            #   原作 place_meeting 是**矩形**判定，切不进斜缝。
            if dx != 0 and dy != 0:
                if not free[cy][nx] or not free[ny][cx]:
                    continue
                # ★★ 格级通过还不够：再验"盒扫掠"（见 docstring 的反例）。
                if obstacles is not None:
                    px0, py0 = _cell_center(cx, cy, x0, y0, step)
                    px1, py1 = _cell_center(nx, ny, x0, y0, step)
                    if not _segment_clear(obstacles, px0, py0, px1, py1,
                                          bbox_w, bbox_h, step):
                        continue
            ng = g + cost
            if ng < gscore.get((nx, ny), 1e18):
                gscore[(nx, ny)] = ng
                came[(nx, ny)] = cur
                heapq.heappush(open_heap, (ng + h((nx, ny)), ng, (nx, ny)))
    return None


# ===========================================================================
#  平滑（去掉直角折线）
# ===========================================================================

def chaikin(points, iterations=3, closed=False):
    """Chaikin 角切平滑：反复把每条边切成 1/4 + 3/4 两点。

    ★ 为什么是 Chaikin 而不是贝塞尔：Chaikin **不需要选控制点**，
    且**保凸包**（结果点必在原折线包围盒内）—— 对"不许被推出可走区"
    这条律最友好。贝塞尔要猜控制点，容易过冲。
    """
    if len(points) < 3 or iterations <= 0:
        return list(points)
    pts = [tuple(p) for p in points]
    for _ in range(iterations):
        out = []
        n = len(pts)
        rng = n if closed else n - 1
        if not closed:
            out.append(pts[0])
        for i in range(rng):
            p0 = pts[i]
            p1 = pts[(i + 1) % n]
            out.append((p0[0] * 0.75 + p1[0] * 0.25, p0[1] * 0.75 + p1[1] * 0.25))
            out.append((p0[0] * 0.25 + p1[0] * 0.75, p0[1] * 0.25 + p1[1] * 0.75))
        if not closed:
            out.append(pts[-1])
        pts = out
    return pts


def simplify_collinear(points, align=1.0, obstacles=None,
                       bbox_w=PLAYER_BBOX_W, bbox_h=PLAYER_BBOX_H, step=GRID_STEP):
    """删掉共线中继点（转角 < `align` px 视为直线）。

    ★★ 传了 `obstacles` 时，**删点前必须校验新段可走**。
      这是第 45 轮的第五个真 bug，也是"五章全量扫描"才暴露出来的：

        旧版注释写着"只删真的在直线上的点，不改变路径形状 ⇒ 不影响可走性"。
        **这句话是错的。** A* 的格心折线在**绕障碍凸角**时呈**锯齿状**
        （格心沿障碍边缘一格格挪），其中继点恰恰近似共线；
        按"共线性"删掉后，`A→C` 直连就**切进了障碍**。

        实测（五章 2376 组起终点）：**17 例穿模全部出自这里**，
        其中 `ch1 room_flowershop_1f` 的末段 `(95,85)->(36.58,134.67)`
        直插 `(20,134,105.26,25.26)` 这个柜台。

      ⇒ 不传 `obstacles` 时保持旧的纯几何行为（E6/E7 判据仍成立）；
        传了就变成"**保行走简化**"：删点会让新段穿墙的，就不删。

    ★ 为什么不是"视线贪心简化"（LOS simplification）：那种做法删点最狠、
      路线最直，但会**丢弃"沿墙走"的原作观感**，且退化时（起点与近邻
      不可直连）仍会产出穿模段。保行走版改动最小、语义最接近原意。
    """
    if len(points) <= 2:
        return list(points)
    pts = [tuple(p) for p in points]
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        ax, ay = out[-1]
        bx, by = pts[i]
        cx, cy = pts[i + 1]
        cross = abs((bx - ax) * (cy - ay) - (by - ay) * (cx - ax))
        span = math.hypot(cx - ax, cy - ay) or 1.0
        keep = cross / span > align
        if not keep and obstacles is not None:
            # 本来"可删"，但删掉后 out[-1] -> pts[i+1] 若穿墙，就必须保留
            if not _segment_clear(obstacles, ax, ay, cx, cy, bbox_w, bbox_h, step):
                keep = True
        if keep:
            out.append(pts[i])
    # ★ 末段也要校验：`out[-1] -> pts[-1]` 同样是"删点产生的新段"
    if obstacles is not None and len(pts) >= 2:
        if not _segment_clear(obstacles, out[-1][0], out[-1][1],
                              pts[-1][0], pts[-1][1], bbox_w, bbox_h, step):
            # 把原折线的倒数第二个点补回来再试；仍不行则原样保留（由上层 repair 兜）
            out.append(pts[-2])
    out.append(pts[-1])
    return out


def smooth_keep_walkable(points, obstacles, iterations=3,
                         bbox_w=PLAYER_BBOX_W, bbox_h=PLAYER_BBOX_H,
                         step=GRID_STEP):
    """平滑，但**逐点 + 逐段回验可走性**；不合格就回退到原折线。

    ★ 这是「平滑不许穿墙」律的实现，也是第 45 轮修掉的一个真 bug：
      第一版只做**逐点**检测，结果相邻平滑点各自合法、**连线**却切过了障碍的窄角
      （实测：`room_krishallway` 平滑版第 44 段 `(502.8,82.8)->(504.1,109.8)`
       穿过 `(479,123,25,44.2)` 的左上角）。
      ⇒ 判据必须是「**点 + 它到下一个点的整段**」都不撞，与 D6/E11 的验收口径一致。

    返回：安全平滑后的点列。**任何一段修不干净就退回原折线** ——
    宁可不平滑（路线生硬），绝不穿墙（与原作不符且看着像 bug）。
    段级修法分三档（见下文 2) 节注释），优先保住"能平滑的部分"。
    """
    if len(points) < 3:
        return list(points)
    smoothed = chaikin(points, iterations=iterations)
    if len(smoothed) < 2:
        return list(points)

    # 1) 逐点：把被推进障碍的采样点，按"它在原折线上的等比例位置"回退
    n_in = len(points) - 1
    m = len(smoothed)
    kept = []
    for i, (sx, sy) in enumerate(smoothed):
        t = i / float(m - 1) if m > 1 else 0.0
        seg = min(n_in - 1, int(t * n_in)) if n_in > 0 else 0
        ax, ay = points[seg]
        bx, by = points[seg + 1] if seg + 1 < len(points) else points[-1]
        local = max(0.0, min(1.0, (t * n_in) - seg if n_in > 0 else 0.0))
        fx = ax + (bx - ax) * local
        fy = ay + (by - ay) * local
        if not blocks_at(obstacles, sx, sy, bbox_w, bbox_h):
            kept.append((sx, sy))
        elif not blocks_at(obstacles, fx, fy, bbox_w, bbox_h):
            kept.append((fx, fy))
        else:
            kept.append((ax, ay))

    # 2) ★ 逐段：任何一段的连线撞障碍 ⇒ 该段用原折线的对应子段替换
    #    ★ 三档回退（第 45 轮鉴别力体检催生的加固）：
    #      ① 弧长区间内的原折线顶点（`_backtrack_segment`）
    #      ② 端点各自最近的**单个**原折线顶点（处理"a、b 贴着同一个顶点"的
    #         亚像素偏移段 —— 例如 krishallway 第 44 段 `(502.8,82.8)->(504.1,109.8)`
    #         两端都紧贴顶点 `(505,85)`，弧长区间内没有任何顶点）
    #      ③ 仍不行 ⇒ 整条退回原折线（不穿墙优先；代价是这一段不平滑）
    #    ⚠️ 档③ 的复检口径必须是"**逐段查整条插入子路径**"，不能只查 a->b
    #       （第 45 轮踩过的第 4 个判据坑，注释见下）。
    out = [kept[0]]
    bailed = False
    for i in range(len(kept) - 1):
        a = out[-1]
        b = kept[i + 1]
        if _segment_clear(obstacles, a[0], a[1], b[0], b[1], bbox_w, bbox_h, step):
            out.append(b)
            continue

        # 档 ①：弧长子段
        back = _backtrack_segment(a, b, points)
        # 档 ②：弧长子段为空 ⇒ 补上两端各自最近的单个顶点
        if not back:
            va = _nearest_vertex(a, points)
            vb = _nearest_vertex(b, points)
            if va is not None and va != a:
                back.append(va)
            if vb is not None and vb != b and (not back or back[-1] != vb):
                back.append(vb)

        for p in back:
            if p != out[-1]:
                out.append(p)
        if out[-1] != b:
            out.append(b)

        # 档 ③：★ 逐段复检**刚插入的整条子路径** `a -> back... -> b`。
        #   ❗ 第 45 轮踩过的判据坑：第一版只查 `a -> out[-1]`（= a->b），
        #      **忽略了中间插入的顶点** ⇒ 明明 `a->(505,85)->b` 两段都干净，
        #      却因为直连 a->b 不干净而误判"回退失败"，整条退回原折线。
        chain = [a] + [p for p in back if p != a and p != b] + [b]
        bad_seg = False
        for k in range(len(chain) - 1):
            if not _segment_clear(obstacles, chain[k][0], chain[k][1],
                                  chain[k + 1][0], chain[k + 1][1],
                                  bbox_w, bbox_h, step):
                bad_seg = True
                break
        if bad_seg:
            _log.debug('平滑段回退失败，整条退回原折线（不穿墙优先）')
            bailed = True
            break
    if bailed or len(out) < 2:
        # ★★ 第51轮修正：`bailed` 只意味着"**平滑弧**在保行走的前提下修不动了"，
        #    **不代表不能去尖刺** —— `_despike()` 自带"删了会穿墙就不删"的校验，
        #    对**原折线**同样安全（删点前逐条 `_segment_clear`）。
        #    旧写法直接 `return list(points)` ⇒ 这条路径上的尖刺**永远没人削**。
        #    实测（538 组样本）：残留的 82 个"削了不穿墙却没削"的尖刺，
        #    **全部**落在这条 bailed 分支上（`smooth=False` 与默认 path 逐点相同
        #    即为铁证）—— 也就是说，旧写法让"修不动平滑"的房间顺带丢了"去尖刺"。
        #    `_despike` 不改点序、只删点，故不会把路径推出可走区。
        _log.debug('平滑弧回退（保行走优先）⇒ 仍执行去尖刺')
        return _despike(list(points), obstacles, bbox_w, bbox_h, step)
    # 3) ★★ 消掉"倒着走"（第 47 轮）—— 见 `_monotone_forward` 的注释。
    mono = _monotone_forward(out, points, obstacles, bbox_w, bbox_h, step,
                             BACKTRACK_TOL)
    # 4) ★★ 消掉"横向鼓包的尖刺"（第 47 轮）—— 见 `_despike` 的注释。
    return _despike(mono, obstacles, bbox_w, bbox_h, step)


def _monotone_forward(out, points, obstacles, bbox_w, bbox_h, step, tol):
    """按**原折线弧长**单调过滤 `out`，消掉"往回走"的抖动。**绝不制造穿墙**。

    ★ 这一层为什么必须有（第 47 轮实测，用户口径「别和机器人一样」）
    --------------------------------------------------------------
    上面阶段 1 在"平滑点本身被挡、它的等比例投影点也被挡"时，会退回
    **所在段的起点顶点** `(ax, ay)`。但 Chaikin 的点在**非均匀弧长**上分布
    （每条原边固定切出 8 个子点，长边短边一样多），而 `seg = int(t * n_in)`
    是按**点序号**而不是弧长映射的 ⇒ `(ax, ay)` 可能落在**身后几十像素**：

      实测 ch2 房 252：原折线 25 点 / 硬拐角 3 个，
      平滑后 204 点 / 硬拐角 **10** 个，其中
        `(883.0, 955.0) → (819.8, 951.9)`  = **往回倒 63.2px**（转角 177°）
        `(495.0, 816.3) → (500.2, 796.7)`  = 往回倒 19.6px（转角 174°）
      —— 这不是"不够顺"，是**画面上真的来回抽动**。

    五章 193 组配对里，**74 组**平滑后硬拐角比原折线还**多**（平滑在帮倒忙）。

    做法
    ----
    把 `out` 里"沿原折线弧长倒退超过 `tol`"的点**删掉**。删点会合并相邻线段，
    所以每删一个点前都要回验"上一个保留点 → 该点"这条新连线**不穿墙**。
    ⚠️ 删不动时**不能**整体放弃过滤（第一版就是那么写的，实测 74 对里只压掉 9 对）——
    正确做法是把刚跳过的点**接回来**（它们是原折线上的相邻点，段段本来就可走），
    再继续往后过滤。这样"删得动的地方"全都能删干净。
    """
    if len(out) < 3:
        return list(out)
    mono = [out[0]]
    s_last = _arc_pos(out[0], points)
    skipped = []                     # 自 mono[-1] 起"暂时删掉"的点（按原顺序）
    for i in range(1, len(out)):
        p = out[i]
        sp = _arc_pos(p, points)
        direct = _segment_clear(obstacles, mono[-1][0], mono[-1][1], p[0], p[1],
                                bbox_w, bbox_h, step)
        if sp - s_last < -tol and direct:
            skipped.append(p)        # 倒着走 且 删了安全 ⇒ 删
            continue
        if direct:
            mono.append(p)           # 直连安全 ⇒ 接上（顺带丢掉 skipped）
        else:
            if not skipped:
                # `out` 自身相邻段就不安全（不该发生）⇒ 原样返回，不冒险
                return list(out)
            for q in skipped:        # ★ 删不动 ⇒ 把跳过的点接回来
                if q != mono[-1]:
                    mono.append(q)
            mono.append(p)
        skipped = []
        s_last = _arc_pos(mono[-1], points)
    return mono if len(mono) >= 2 else list(out)


def _turn_deg(a, b, c):
    """折线在 `b` 处的转角（度）：0 = 直行，180 = 原路折返。"""
    v1 = (b[0] - a[0], b[1] - a[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n1 = math.hypot(v1[0], v1[1])
    n2 = math.hypot(v2[0], v2[1])
    if n1 < 1e-9 or n2 < 1e-9:
        return 0.0
    cosv = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    return math.degrees(math.acos(max(-1.0, min(1.0, cosv))))


def _despike(points, obstacles, bbox_w, bbox_h, step,
             min_turn=DESPIKE_MIN_TURN, passes=DESPIKE_PASSES):
    """删掉"拐一下又拐回来"的**尖刺**点（缓弯一律保留）。删点前回验不穿墙。

    ★ 为什么 `_monotone_forward` 之后还要这一层（第 47 轮第二次实测）
    --------------------------------------------------------------
    `_monotone_forward` 只治"沿原折线**倒着走**"，治不了**横向鼓包**：
    阶段 2 为了不穿墙会把原始顶点插进平滑弧里，路径就变成
    「弧 → 尖顶点 → 弧」，尖顶点**两侧各鼓出一个尖角**。

      实测（ch1/2/4/5、348 组真实配对）：平滑后可见硬拐角 180 个，
      其中 **30 组**比原折线**还多**；多出来的 44 个尖角里
      **20 个腿长 ≥15px、7 个 ≥30px**（最长 67.5px）——
      不是亚像素抖动，是画面上看得见的硬拐。

    ★ 为什么门槛是 45°（而不是"能删就删"）
    ------------------------------------
    用户反对的走法有**两种**：「直角拐弯」**和**「一直直线走」。
    所以不能一路抄近路把路拉直 —— 缓弯（每段转角 <45°）必须原样保留，
    只有"拐一下又拐回来"的尖刺才删。这样"人味"是加出来的，不是拿直线换的。

    ⚠️ 锚点必须是**上一个保留点**（`nxt[-1]`），不是 `cur[i-1]`：
       第 47 轮第一版写成后者 —— 删掉 `b` 之后仍拿 `b` 当前一个点，
       于是"抄近路会不会穿墙"验的是**早就被删掉的那一段**，
       实测凭空造出 **8 处穿模**。（又一次印证：实现写错时，报红的是产品。）
    """
    if len(points) < 3:
        return list(points)
    cur = list(points)
    for _ in range(passes):
        nxt = [cur[0]]
        changed = False
        i = 1
        while i < len(cur) - 1:
            a = nxt[-1]                      # ★ 上一个**保留**点（不是 cur[i-1]）
            b = cur[i]
            c = cur[i + 1]
            turn = _turn_deg(a, b, c)
            detour = (math.hypot(b[0] - a[0], b[1] - a[1])
                      + math.hypot(c[0] - b[0], c[1] - b[1])
                      - math.hypot(c[0] - a[0], c[1] - a[1]))
            if (turn >= min_turn and detour > 1.0
                    and _segment_clear(obstacles, a[0], a[1], c[0], c[1],
                                       bbox_w, bbox_h, step)):
                changed = True                # 尖刺 且 抄近路安全 ⇒ 删 b
                i += 1
                continue
            nxt.append(b)
            i += 1
        nxt.append(cur[-1])
        cur = nxt
        if not changed:
            break
    return cur


def _nearest_vertex(p, path):
    """`path` 上离 `p` 最近的顶点（或 None）。"""
    best, best_d = None, None
    for q in path:
        d = (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2
        if best_d is None or d < best_d:
            best, best_d = q, d
    return best


def _arc_pos(p, path):
    """把点 `p` 投影到折线 `path` 上，返回**累计弧长参数** `s`。

    ★ 用弧长（而不是"最近顶点下标"）做回退定位 —— 这是第 45 轮修的
      第三个真 bug 的一部分：顶点下标在**相邻**情形下无法区分
      "夹在同一段的两个顶点之间"，导致回退退化成原地不动。
      弧长是连续量，两点之间只要有内容就一定夹得住。
    """
    best_s, best_d, acc = 0.0, None, 0.0
    for i in range(len(path) - 1):
        ax, ay = path[i]
        bx, by = path[i + 1]
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        if seg2 <= 1e-12:
            t = 0.0
        else:
            t = ((p[0] - ax) * dx + (p[1] - ay) * dy) / seg2
            t = max(0.0, min(1.0, t))
        px, py = ax + dx * t, ay + dy * t
        d = (p[0] - px) ** 2 + (p[1] - py) ** 2
        if best_d is None or d < best_d:
            best_d = d
            best_s = acc + math.hypot(dx, dy) * t
        acc += math.hypot(dx, dy)
    return best_s


def _backtrack_segment(a, b, path):
    """段 `a->b` 撞墙时，返回**原折线 `path` 上严格夹在 a、b 之间的顶点序列**。

    ★ 第 45 轮修的第三个真 bug（鉴别力体检暴露）：
      第一版把子段**首尾强行替换**为 `a` / `b`（`sub[0]=a; sub[-1]=b`）。
      当两个端点的最近顶点**相邻**时，子段只有两个顶点，替换后 = `[a, b]` ——
      **和没回退一模一样**，"回退"静默失效（实测：尖角夹具仍有段穿模）。
      ⇒ 改为按**弧长参数**取子段：用 `_arc_pos()` 定位 a、b 在折线上的位置，
        返回该区间内的**真实顶点**（不含端点自身，由调用方衔接）。
        区间内无顶点时返回 `[]` —— 如实告知"这段没法用原折线修",
        由调用方按"退回整条原折线"兜底（见 `smooth_keep_walkable` 的段级兜底）。
    """
    if len(path) < 2:
        return []
    sa = _arc_pos(a, path)
    sb = _arc_pos(b, path)
    lo, hi = (sa, sb) if sa <= sb else (sb, sa)
    if hi - lo < 1e-9:
        return []
    # 累计弧长 → 顶点下标；只取**严格在 (lo, hi) 开区间**内的顶点
    mids, acc = [], 0.0
    for i in range(1, len(path) - 1):
        ax, ay = path[i - 1]
        bx, by = path[i]
        acc += math.hypot(bx - ax, by - ay)
        if lo + 1e-9 < acc < hi - 1e-9:
            mids.append(path[i])
    if sa > sb:
        mids.reverse()
    return mids


# ===========================================================================
#  门面
# ===========================================================================

def plan_walk(chapter, room_index, room_rect, start, goal,
              obstacles=None, scene_dir_path=None,
              step=GRID_STEP, smooth=True, bbox_w=PLAYER_BBOX_W, bbox_h=PLAYER_BBOX_H):
    """规划房间内从 `start` 到 `goal` 的自然行走路线。

    参数
    ----
    room_rect : `(x0, y0, x1, y1)` 房间矩形（左上 + 右下）
    start/goal : `(x, y)` 起点/终点（房间局部像素坐标）
    obstacles : 显式给障碍列表（测试用）；None 则从数据文件读

    返回
    ----
    `{'ok': bool, 'path': [(x,y), ...], 'reason': str|None,
      'smoothed': bool, 'steps': int}`

    ★ `ok=False` 时 `path` 是 `[]` —— **绝不返回一条穿墙的直线**。
    """
    out = {'ok': False, 'path': [], 'reason': None, 'smoothed': False, 'steps': 0}
    x0, y0, x1, y1 = room_rect
    if x1 <= x0 or y1 <= y0:
        out['reason'] = '房间矩形非法: %r' % (room_rect,)
        return out

    if obstacles is None:
        obstacles = room_obstacles(chapter, room_index, scene_dir_path)

    sx, sy = float(start[0]), float(start[1])
    gx, gy = float(goal[0]), float(goal[1])

    # 快路径：起点到终点直连且不撞任何障碍 ⇒ 直接两步（短距直线，无需 A*）
    if _segment_clear(obstacles, sx, sy, gx, gy, bbox_w, bbox_h, step):
        out['ok'] = True
        out['path'] = [(sx, sy), (gx, gy)]
        out['steps'] = 2
        # 两点不成线，平滑无意义 ⇒ smoothed 保持 False
        return out

    free, w0, h0 = _build_grid(obstacles, x0, y0, x1, y1, step)
    # ★ 用"可见性约束"版找格（见 `_nearest_free_visible`）：格可走 **且** 与真实
    #   起终点直连不穿墙。否则首尾会冒出"从起终点直插障碍"的段。
    s = _nearest_free_visible(obstacles, free, w0, h0, x0, y0, step, sx, sy)
    g = _nearest_free_visible(obstacles, free, w0, h0, x0, y0, step, gx, gy)
    if s is None or g is None:
        out['reason'] = '起点或终点附近找不到可走格（房间被障碍堵死？）'
        return out

    # ★ 第51轮：把障碍表/房间原点/步长一并交给 A*，让它对**对角步**做盒扫掠复检
    #   （理由见 `astar` 的 docstring —— 格级"不切角"挡不住盒级擦角）。
    cells = astar(free, w0, h0, s, g, obstacles=obstacles,
                  x0=x0, y0=y0, step=step, bbox_w=bbox_w, bbox_h=bbox_h)
    if cells is None:
        out['reason'] = 'A* 找不到通路（障碍把目标隔开了）'
        return out

    # 格中心 → 像素
    pts = [_cell_center(cx, cy, x0, y0, step) for (cx, cy) in cells]

    # ★★ 真实起终点用**插入**接在两端，**不是替换**首尾格心。
    #   这是第 45 轮的第七个真 bug（五章全量扫描暴露 9/2376）：
    #
    #   旧版写 `pts[0] = (sx, sy)` / `pts[-1] = (gx, gy)` —— **替换**。
    #   可 `_nearest_free_visible()` 刚验证过的正是
    #   「`(sx,sy)` → **s 格心**」这条短段；替换把它抹掉后，
    #   路径首段变成「`(sx,sy)` → **第二个**格心」，**跨过了障碍**。
    #
    #   实测 `ch1 room_torielclass`：s 格心 `(55,45)` 与起点直连
    #   `clean=True`，可替换后首段成了 `(140.6,45.7)->(55,35)`，
    #   直接穿过 `(84,48,142,20)` 那张桌子。
    #
    #   ⇒ 插入（而非替换）后，首段 = 起终点→s 格心（已验证可走），
    #     中间 = A* 格心折线，末段 = g 格心→终终点（已验证可走）。
    #     三条都干净，`simplify_collinear` 再按"保行走"删冗余点。
    pts = [(sx, sy)] + pts + [(gx, gy)]

    # ★ 保行走简化（传 obstacles ⇒ 删点前校验新段可走）。
    #   这是 17/2376 穿模的主因：绕角锯齿的中继点被"共线性"误删后直连切进障碍。
    pts = simplify_collinear(pts, align=step * 0.35, obstacles=obstacles,
                             bbox_w=bbox_w, bbox_h=bbox_h, step=step)

    if smooth and len(pts) >= 3:
        sm = smooth_keep_walkable(pts, obstacles, iterations=3,
                                  bbox_w=bbox_w, bbox_h=bbox_h)
        if len(sm) >= 2:
            pts = sm
            out['smoothed'] = True

    out['ok'] = True
    out['path'] = pts
    out['steps'] = len(pts)
    return out


def _grid_of(x, y, x0, y0, step):
    return (int((x - x0) // step), int((y - y0) // step))


def _cell_center(gx, gy, x0, y0, step):
    return (x0 + (gx + 0.5) * step, y0 + (gy + 0.5) * step)


def _seg_intersects_rect(x0, y0, x1, y1, rx, ry, rw, rh):
    """线段与轴对齐矩形是否**真正相交**（纯贴边/单点接触**不算**）。

    ★ 第51轮新增：替代"按 step 采样"。语义必须与 `blocks_at()` 的**开区间**
      判定一致 —— `blocks_at` 写的是
      `(bx + bw > ox) and (bx < ox + ow) and ...`，即**边贴着边不算撞**。
      所以这里也用严格区间 `t0 < t1`：接触点（`t0 == t1`）不算相交。

    算法 = Liang-Barsky 裁剪（参数化线段 + 四条边界收缩 t 区间）。
    复杂度 `O(1)`，**比采样更快也更准** —— 采样会漏掉"擦过障碍角、穿透宽度
    小于采样步长"的情形，正是本轮 75 处穿模的主因。
    """
    dx = x1 - x0
    dy = y1 - y0
    t0, t1 = 0.0, 1.0
    # ⚠️ 配对必须是标准 Liang-Barsky 的 `p = ∓d`、`q = 起点到该边界的距离`。
    #   第51轮第一次写成了 `(dx, x0 - rx)`（p 的符号反了），实测穿模
    #   75 → **907**（判据整体变松：本该死路绕行的点对被判成"直线可走"）。
    #   教训：**能用锚点自检的判据，必须先过锚点**（见 patrol51 的 D 段锚点）。
    for p, q in ((-dx, x0 - rx), (dx, rx + rw - x0),
                 (-dy, y0 - ry), (dy, ry + rh - y0)):
        if p == 0.0:
            if q < 0.0:
                return False        # 平行且在该边界外侧 ⇒ 不相交
            continue
        r = q / p
        if p < 0.0:
            if r > t1:
                return False
            if r > t0:
                t0 = r
        else:
            if r < t0:
                return False
            if r < t1:
                t1 = r
    if t0 >= t1:
        return False
    # ★ 零测度复检（第51轮，锚点自检抓出来的，勿删）：
    #   Liang-Barsky 用**闭**区间收缩 t，所以"线段正好沿着矩形某条边滑行"
    #   （例如 `dy=0` 且 `ry == y0`）会得到非空区间 `[t0,t1]` 而被判"相交"。
    #   但 `blocks_at()` 的判定是**开**区间（边贴边不算撞）⇒ 语义不一致。
    #   ⇒ 再取区间**中点**，验证它落在矩形**内部**：
    #     · 正测度穿透 ⇒ 中点必在内部 ⇒ True；
    #     · 沿边滑 / 只碰一点 ⇒ 中点在边界上 ⇒ False。
    tm = (t0 + t1) / 2.0
    mx = x0 + dx * tm
    my = y0 + dy * tm
    return (rx < mx < rx + rw) and (ry < my < ry + rh)


def _segment_clear(obstacles, x0, y0, x1, y1, bbox_w, bbox_h, step):
    """线段是否全程不撞障碍。

    ★★ 第51轮修正（重要，勿回退）：改为**解析判定**，不再按 `step * 0.5` 采样。

    旧实现的漏洞（本轮由巡行实测暴露：2244 成功 / **75 穿模**）：

        `n = int(dist / (step * 0.5))`、`step = GRID_STEP = 10` ⇒ 采样间隔 **5px**。
        角色碰撞盒 19×13，障碍最小 20×20。当路径**擦着障碍角**走时，
        "穿透"发生在 < 5px 的弧长区间内 ⇒ **采样点全部落在障碍外** ⇒
        判据说"可走"，而实际连线已经切进了障碍。

    ⇒ 换 Liang-Barsky：对每个障碍矩形做 `O(1)` 精确相交判定
      （`_seg_intersects_rect`）。**既修掉了漏判，又去掉了采样循环**。
      实测同一批 2784 组点对：穿模 75 → 见第51轮报告。

    坐标语义与 `blocks_at()` 完全一致：锚点 + `PLAYER_BBOX_OFF_*` = 盒左上角。
    `step` 参数**保留但不再使用**（签名兼容既有调用方/回归锁）。

    ⚠️⚠️ 第51轮第二次踩坑（务必理解，否则又会写错）：
        盒会**平移**，所以"锚点扫过的线段"必须撞**膨胀后的矩形** ——
        Minkowski 判定：盒 `[p,p+bw]×[q,q+bh]` 与矩形 `[rx,rx+rw]×[ry,ry+rh]`
        有正测度重叠 ⟺ **盒左上角** `(p,q)` 落在
        `(rx-bw, rx+rw) × (ry-bh, ry+rh)` 里。
        第一版直接把"左上角线段"去撞**原始矩形**（忘了 `-bw/-bh`）⇒ 判据变松，
        实测穿模 75 → **299**。两处（`_seg_intersects_rect` 的调用与本次）都是
        靠"巡行实测 + 锚点对拍"抓出来的。
    """
    ax0 = x0 + PLAYER_BBOX_OFF_X
    ay0 = y0 + PLAYER_BBOX_OFF_Y
    ax1 = x1 + PLAYER_BBOX_OFF_X
    ay1 = y1 + PLAYER_BBOX_OFF_Y
    for rect in obstacles or ():
        rx, ry, rw, rh = rect[0], rect[1], rect[2], rect[3]
        if _seg_intersects_rect(ax0, ay0, ax1, ay1,
                                rx - bbox_w, ry - bbox_h,
                                rw + bbox_w, rh + bbox_h):
            return False
    return True


def describe_walk(result):
    """把 `plan_walk()` 结果转成一句可读的话（给日志/调试用）。"""
    if not result:
        return '无行走计划'
    if not result.get('ok'):
        return '走不过去：%s' % (result.get('reason') or '未知原因')
    return '可行走，%d 个航点%s' % (
        result.get('steps', 0), '（已平滑）' if result.get('smoothed') else '')
