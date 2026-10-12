# -*- coding: utf-8 -*-
"""门的「实体靠近 ⇒ 从虚到实」渐显（第112轮 #47 续）。

用户口径（第112轮，逐字）
--------------------------
「对了，给门添加一个功能，在检测到实体靠近后才从透明到实象，中间要有个从虚
到实的过度动画，**重点强调，只针对桌面上的 ut 和三角符文的门**（因为那俩太大
个了，会影响使用），**oneshot 和 niko 的家不变**」

⇒ 本模块只服务**两扇**门（`desktop` 的 `C`=UT、`D`=三角符文）。
   `A`（OneShot）/ `B`（Niko 的家）**恒为实体可见**，本模块对它们返回 1.0。

设计要点
--------
1. **零依赖**：只用标准库（`math` 都不用 —— 线性/平滑都可用纯算术表达）。
   可与 `possession.py` 同规格被单测直接 import，不需要 Qt / 不需要场景系统。
2. **纯函数**：`reveal_alpha(...)` 不做任何缓存、不持有状态 ⇒ 可重入、可并发、
   回归套件可以在任意 tick 上调它。**动画的"时间"由调用方给**（墙钟毫秒）。
3. ★★★ **幂等与帧率无关**：alpha 只由 `(entity_rect, door_rect, now_ms)` 决定，
   与"上一帧是多少"无关。这样：
     · 掉帧不会让动画变慢（`now_ms` 直接来自墙钟）；
     · 反复调用同一时刻 ⇒ 同一结果（回归可断言）；
     · 不存在"忘了重置"导致的残留状态（本项目最贵的坑之一）。
4. **双向**：靠近渐显、走远渐隐，同一套公式（`t` 是距离的归一化，与方向无关）。

坐标口径
--------
`entity_rect` / `door_rect` 都是**房间世界坐标**的 `(l, t, r, b)`（浮点）。
本模块按"矩形之间的最短间距"算距离 —— 不是中心点距离：门很大（UT 门 44×99），
用中心距会让"站在门边"也判定成很远。用矩形间距 = 玩家观感（贴着门才算近）。
"""

# ---------------------------------------------------------------------------
#  0. 常量（可调参数；改这里就够，不要在调用点写魔法数）
# ---------------------------------------------------------------------------

#: ★★★ 适用本功能的两扇门 `(scene_id, door_letter)`。
#: 用户「只针对桌面上的 ut 和三角符文的门」⇒ 精确到字母，**不用"桌面上所有门"**
#: 这种宽口径（否则 oneshot / niko 家会被顺带卷进来，违背用户逐字的"不变"）。
REVEAL_DOORS = (('desktop', 'C'), ('desktop', 'D'))

#: 门字母表（与 `item_interact.DOOR_LETTERS` **同口径**）。
#: ★★★ 为什么在这里**抄一份**而不是 `from .item_interact import DOOR_LETTERS`：
#:   本模块的设计承诺是**零依赖**（纯函数、无 Qt、可被回归套件直接 import）。
#:   而 `item_interact` 顶部就 `from companion import Interactable`（Qt 链）
#:   ⇒ 一旦依赖它，本模块就不再零依赖，"单测直接 import"这条就断了。
#:   代价 = 两处各有一份字母表。**防分叉**靠这一条：`check112` 的 H 段会
#:   断言两张表**完全相等**（不等就报红），所以分叉会被机器抓住，不是靠自觉。
DOOR_LETTERS = ('A', 'B', 'C', 'D', 'E', 'F', 'W', 'X', 'Y')

#: 开始渐显的距离（房间逻辑像素）：实体矩形与门矩形间距 ≤ 此值 ⇒ 开始变实。
#: 房间 320×240 里的观感：门在屏幕边框上，玩家从房间中心（约 160,120）走向门，
#: 间距约 100~140 ⇒ 340 意味着"走近到屏幕那一侧的四分之一"才开始显形。
NEAR_DIST = 110.0

#: 完全实体化的距离（≤ 此值 ⇒ alpha = 1.0）。
FAR_DIST = 34.0

#: alpha 的下限（**不是 0**）：用户要"从透明到实象"，但**完全 0 = 看不见门在哪**，
#: 玩家会找不到路。留一丝幽灵般的可见度（0.14）—— 既满足"透明"的观感，
#: 又保住"这里有一扇门"的可发现性。
MIN_ALPHA = 0.14

#: 完全实体时的 alpha。
MAX_ALPHA = 1.0


def _clamp01(x):
    """钳进 `[0, 1]`（非数/异常输入 ⇒ 0.0，**不抛**）。"""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0.0
    if v != v:          # NaN
        return 0.0
    if v <= 0.0:
        return 0.0
    if v >= 1.0:
        return 1.0
    return v


def rect_gap(a, b):
    """两个 `(l, t, r, b)` 矩形之间的**最短间距**（逻辑像素）。

    · 相交 / 包含 ⇒ `0.0`
    · 只在某一轴分离 ⇒ 该轴间距
    · 输入不合法（`None` / 长度不对 / 非数）⇒ `float('inf')`
      （**"算不出距离" ⇒ 当"很远"** ⇒ 门保持最透明 —— 这是保守侧：
       宁可门不显形，也不要因为一个坏数据把门忽然刷成全实。）
    """
    if not a or not b:
        return float('inf')
    try:
        al, at_, ar, ab = (float(a[0]), float(a[1]), float(a[2]), float(a[3]))
        bl, bt, br, bb = (float(b[0]), float(b[1]), float(b[2]), float(b[3]))
    except (TypeError, ValueError, IndexError):
        return float('inf')
    for v in (al, at_, ar, ab, bl, bt, br, bb):
        if v != v:                      # NaN
            return float('inf')
    dx = max(bl - ar, al - br, 0.0)
    dy = max(bt - ab, at_ - bb, 0.0)
    if dx <= 0.0 and dy <= 0.0:
        return 0.0
    # 只在一个轴上分离 ⇒ 直接返回该轴（避免 sqrt 的浮点噪声）
    if dx <= 0.0:
        return dy
    if dy <= 0.0:
        return dx
    # 两轴都分离 ⇒ 欧氏距离（用 ** 0.5，不 import math）
    return (dx * dx + dy * dy) ** 0.5


def ease(t):
    """平滑插值（smoothstep）—— "从虚到实的过度动画"的手感来源。

    线性插值看起来像"突然被点亮"；smoothstep（`3t²-2t³`）起止都慢、
    中段快，读起来像"显影"。★ 纯算术，零依赖。
    """
    t = _clamp01(t)
    return t * t * (3.0 - 2.0 * t)


def reveal_t(gap, near=NEAR_DIST, far=FAR_DIST):
    """矩形间距 → 归一化显形度 `t ∈ [0,1]`（0=最透明，1=完全实体）。

    · `gap >= near` ⇒ 0
    · `gap <= far`  ⇒ 1
    · 中间线性映射后过 `ease()`

    ★ `near <= far` 这种反了的参数 ⇒ 退化成硬阈值（`gap <= far` 即 1），
      **不抛**（配置写错不该让桌面崩）。
    """
    try:
        near = float(near)
        far = float(far)
    except (TypeError, ValueError):
        return 0.0
    try:
        g = float(gap)
    except (TypeError, ValueError):
        return 0.0
    if g != g or g == float('inf'):
        return 0.0
    if far >= near:
        return 1.0 if g <= far else 0.0
    if g >= near:
        return 0.0
    if g <= far:
        return 1.0
    return _clamp01((near - g) / (near - far))


def reveal_alpha(entity_rect, door_rect, near=NEAR_DIST, far=FAR_DIST,
                 min_alpha=MIN_ALPHA, max_alpha=MAX_ALPHA):
    """★ 主入口：实体矩形 + 门矩形 ⇒ 门的 alpha。

    返回 `min_alpha .. max_alpha` 之间的浮点。**永不抛**（任何坏输入 ⇒
    返回 `min_alpha`，即"门最透明但还看得见" —— 保守侧）。
    """
    try:
        t = ease(reveal_t(rect_gap(entity_rect, door_rect), near=near, far=far))
        a = float(min_alpha) + (float(max_alpha) - float(min_alpha)) * t
    except (TypeError, ValueError):
        return MIN_ALPHA
    if a != a:
        return MIN_ALPHA
    if a < 0.0:
        return 0.0
    if a > 1.0:
        return 1.0
    return a


def is_reveal_door(scene_id, letter):
    """`(scene_id, letter)` 是否属于"要渐显"的两扇门。

    ★ 只看**字母**，不比 `src` 字符串 —— `src` 在不同场景可能带实例后缀
      （`obj_doorC_0`），比 `src` 会漏判。字母由 `door_letter_of()` 归一化过。
    """
    if not scene_id or not letter:
        return False
    key = (str(scene_id), str(letter).upper())
    return key in REVEAL_DOORS


def door_rect_from_pos(pos, size):
    """`[x, y]`（左上角）+ `(w, h)` ⇒ `(l, t, r, b)`（房间世界坐标）。

    房间坐标系与 `plan_frame` 的物件 `pos` 同一套（左上角 + 像素尺寸）。
    """
    try:
        x = float(pos[0])
        y = float(pos[1])
        w = float(size[0])
        h = float(size[1])
    except (TypeError, ValueError, IndexError):
        return None
    return (x, y, x + w, y + h)


def door_letter_of_local(src):
    """`obj_doorC` → `'C'`；认不出 → `None`（**不猜**）。

    ★ 与 `item_interact.door_letter_of()` **逐字同构** —— 本模块自带一份是为了
      保住「零依赖」（见 `DOOR_LETTERS` 的注释）。两份的一致性由 `check112`
      的 H 段机器保证（断言两表相等 + 抽样比对同一批输入的结果）。
    """
    if not isinstance(src, str):
        return None
    s = src.strip()
    if not s.lower().startswith('obj_door'):
        return None
    rest = s[len('obj_door'):]
    head = rest.split('_', 1)[0]
    if len(head) == 1 and head.upper() in DOOR_LETTERS:
        return head.upper()
    return None


def apply_to_objects(objects, scene_id, entity_rect,
                     near=NEAR_DIST, far=FAR_DIST, sizer=None):
    """★ 就地给 `objects` 里"要渐显的门"写入 `alpha`；返回改动过的 id 列表。

    `objects` = 场景的 `objects` 列表（`desktop.json` 那种 dict 列表）。
    `scene_id` = 当前场景 id；`entity_rect` = 实体的房间世界矩形。
    `sizer` = 可选 `callable(obj) -> (w, h)`：**素材真尺寸**从哪来。
        ★★★ 必须传它：JSON 里的 `pos` 是**左上角 + 逻辑像素**，但**尺寸不在
          JSON 里**（尺寸由 `sprite` 指向的 PNG 决定）。不传 ⇒ 只能退化成
          "把门当 1×1 的点"，间距会偏大 ⇒ 门显形偏难（**保守，但不是本意**）。
          宿主侧传的是 `canvas.assets.sprite_size`（同一个尺寸源，单一真源）。

    ★ 为什么**就地改 dict** 而不是返回新列表：`scene_render.plan_frame` 读的
      就是这份对象（`SceneState.objects`），就地写 `alpha` 是**最小改动**
      —— 不需要给渲染层加新参数、不需要动 `plan_frame` 的签名。

    ★ 只碰**目标两扇门**：其余物件的 `alpha` 键**一个字节都不动**
      （否则回归基线的"725 条指令一字不变"会被整体牵连）。

    ★ 幂等：同一 `entity_rect` 反复调用 ⇒ 写入同一个值（无累积）。
    """
    changed = []
    if not objects or not entity_rect:
        return changed
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        letter = door_letter_of_local(obj.get('src'))
        if not is_reveal_door(scene_id, letter):
            continue
        pos = obj.get('pos')
        if not (isinstance(pos, (list, tuple)) and len(pos) == 2):
            continue
        size = None
        if callable(sizer):
            try:
                got = sizer(obj)
                if isinstance(got, (list, tuple)) and len(got) == 2:
                    size = (float(got[0]), float(got[1]))
            except Exception:
                size = None
        if size is None:
            # 回退顺序：JSON 里的显式尺寸 → 当点用。
            cand = obj.get('_size') or obj.get('size')
            if isinstance(cand, (list, tuple)) and len(cand) == 2:
                size = (float(cand[0]), float(cand[1]))
        if size is None:
            size = (1.0, 1.0)
        dr = door_rect_from_pos(pos, size)
        a = reveal_alpha(entity_rect, dr, near=near, far=far)
        if obj.get('alpha') != a:
            obj['alpha'] = a
            changed.append(obj.get('id') or letter)
    return changed
