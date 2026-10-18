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
#: 玩家会找不到路。留一丝幽灵般的可见度 —— 既满足"透明"的观感，
#: 又保住"这里有一扇门"的可发现性。
#:
#: ★★★ 第117轮**复核过，不改**（原本以为"门 D 在壁纸上几乎看不见"要抬下限，是**误判**）：
#:   上一版录屏报告里我写"门 C/D 渐显太淡 ⇒ 门 D 几乎看不见"，依据是
#:   `doors117_track_D.png`（8 帧拼成的**缩略竖条**）。第117轮补做了
#:   **1:1 带上下文的 A/B 对照**（`第117轮…/_tools/ab117_alpha.py` ⇒
#:   `_evidence/rec117/ab117_alpha_C/D.png`）：把真机一帧的背景反解出来，
#:   同一帧分别按 alpha 0.14 / 0.29 / 0.50 / 1.00 重新合成、**不缩放**并排看。
#:   结论：**0.14 时门 D 的金框、门 C 的门框轮廓都清楚可见** ——
#:   CIE76 ΔE 实测 **11.4（C）/ 13.5（D）**（ΔE≈2.3 即"刚能察觉"，10 已算"一眼看出"）。
#:   ⇒ 「看不见」是**缩略图判据的错觉**（门 D 的金框只占矩形 **17.5%**，缩小后被抹掉），
#:     不是产品缺陷。**下限保持 0.14**：用户第112轮要的是"从虚到实"，抬到 0.5 会
#:     把"虚"这一半砍掉、并让两扇大门常态变成 50% 遮挡（正是他说的"会影响使用"）。
#: ★ 以后要判"看不看得见"，**必须 1:1 带上下文**，别拿拼图缩略图下结论。
MIN_ALPHA = 0.14

#: 完全实体时的 alpha。
MAX_ALPHA = 1.0

# ---------------------------------------------------------------------------
#  ★★★ 第116轮：**屏幕像素口径**的阈值（另一套，别跟上面的房间逻辑像素混）
# ---------------------------------------------------------------------------
# 为什么必须再加一套口径（本轮真机逐帧 + 内省两条独立证据）
# ------------------------------------------------------------
# 用户逐字：「门在闪现，**黑底也没去干净**，并且对话框也是闪现，而且，
#           **你门的形式也没用对**」「你自己录屏然后逐帧分析去」
#
# 逐帧取证（`probe116_doors.py`，50Hz 内省 + 像素）测到两件事：
#  ① **渐显完全没生效**：把宠物窗口强制横扫全屏（与门的屏幕间距极差
#     **2382 px**），门 C 的 alpha 恒 `0.140`、门 D 恒 `1.000`，**极差 0.000**。
#     真因 = 宿主喂的"实体"是 `_camera_target_rect()`，而它**优先灵魂**
#     （第76轮 R4 口径）。桌面上的灵魂**恒停在 (2487,1500)**、从不移动
#     ⇒ alpha 是个**冻结值**。★ 功能是死的，不是"参数不好看"。
#  ② **触发矩形与门的真实位置脱节**：`apply_to_objects()` 吃的是
#     `desktop.json` 里的 `pos`（**房间逻辑坐标**，门还在房间图层时的几何）。
#     门 D 那条 = (140,42,320,197)，**占了 320×240 房间的右半张** ⇒
#     宠物站在房间右下角时矩形间距只有 **3 个逻辑单位** ⇒ 恒判"贴着门"
#     ⇒ 门 D **永远 100% 不透明**。真机像素：门 D 矩形内**纯黑比中位 0.820**
#     —— 这正是用户「黑底也没去干净」的像素证据。
#     而门 D 的**真实绘制位置**是屏幕右边缘 (2423,741,137,118)；按同一套
#     归一化映射回房间只有 ~17 逻辑像素宽 ⇒ **两套坐标早就不重合**。
#
# ⇒ 结论：门自第112轮续四起就**按屏幕坐标贴屏绘制**（`desk_doors`），
#   所以"接近程度"也必须在**屏幕坐标**里量 —— 实体与门在同一个坐标系，
#   且与门"实际画在哪"**永远一致**（同一个 `(x,y,w,h)`）。
#   用"占屏幕**短边**的比值"而非写死像素数 ⇒ 换分辨率/换显示器行为一致。
#
#: 开始渐显的距离（占屏幕**短边**的比值）。0.45 × 1600(短边) = 720 px。
#: 观感：宠物从屏幕中央走向某扇门，走过约 3/4 的路程才开始显形。
NEAR_FRAC = 0.45

#: 完全实体化的距离（占屏幕短边的比值）。0.08 × 1600 = 128 px。
FAR_FRAC = 0.08


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


def pixel_near_far(screen_w, screen_h, near_frac=NEAR_FRAC, far_frac=FAR_FRAC):
    """屏幕尺寸 ⇒ **屏幕像素**口径的 `(near, far)`。

    :return: `(近阈值, 全实阈值)`，单位 = 像素；非法输入 ⇒ `(0.0, 0.0)`
        （调用方据此判"算不出 ⇒ 不做渐显"，见 `screen_reveal_alpha`）。

    ★ 为什么按**短边**而不是宽/高各算：门贴在四条边的**中点**上，横向门与
      纵向门到屏幕中心的距离本来就不同（2560 宽 vs 1600 高）；按短边统一
      取一个尺度，四条边的手感才一致。
    """
    try:
        sw = float(screen_w)
        sh = float(screen_h)
        nf = float(near_frac)
        ff = float(far_frac)
    except (TypeError, ValueError):
        return (0.0, 0.0)
    if sw <= 0.0 or sh <= 0.0:
        return (0.0, 0.0)
    if nf != nf or ff != ff:            # NaN
        return (0.0, 0.0)
    short = sw if sw < sh else sh
    return (short * nf, short * ff)


def screen_reveal_alpha(scene_id, letter, entity_rect, door_rect,
                        screen_w, screen_h,
                        near_frac=NEAR_FRAC, far_frac=FAR_FRAC):
    """★★★ 第116轮主入口：**屏幕像素**口径的门 alpha。

    :param scene_id: 当前场景 id（只有 `('desktop','C')` / `('desktop','D')` 命中）。
    :param letter: 门字母（`'A'..'Y'`）。
    :param entity_rect: 实体（宠物）的**屏幕像素**矩形 `(l, t, r, b)`。
    :param door_rect: 这扇门的**屏幕像素**矩形 —— 必须与
        `desk_doors.plan_screen_doors()` 输出的那个**逐字同一个**矩形，
        即"门实际画在哪"。★ 这是本函数存在的全部理由：门画在屏幕坐标上，
        距离就必须在屏幕坐标里量。
    :param screen_w, screen_h: 屏幕（画布）尺寸 ⇒ 由 `pixel_near_far` 折成阈值。
    :return: `MIN_ALPHA .. MAX_ALPHA`；非目标门 ⇒ **恒 `MAX_ALPHA`**。

    ★ A/B 恒 `MAX_ALPHA`：用户逐字「**oneshot 和 niko 的家不变**」。
      判据走 `is_reveal_door()`（字母白名单），不是"桌面上所有门"。
    ★ 算不出阈值（屏幕尺寸非法）⇒ 返回 `MAX_ALPHA`（**不动渐显**）。
      与 `rect_gap()` 的"坏数据 ⇒ 当很远"**刻意相反**，理由：那两扇门是
      **通往别的世界的唯一入口**，让它变成近乎不可见是**功能性损失**；
      而"没渐显"只是外观退回到第112轮之前的样子。**保守侧在这里 = 保可见。**
    """
    if not is_reveal_door(scene_id, letter):
        return MAX_ALPHA
    near, far = pixel_near_far(screen_w, screen_h, near_frac, far_frac)
    if near <= 0.0 or far <= 0.0:
        return MAX_ALPHA
    return reveal_alpha(entity_rect, door_rect, near=near, far=far)


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
