# -*- coding: utf-8 -*-
"""NPC 交互链 —— 原作「Z 键 → 射线检测 → 触发交互」的等价物（L1，零依赖）。

回答用户这条需求（第 88 轮，承接第 84 轮取证的第 84 轮清单缺口 I3 / I6 / I9）：
    「原作里该有的可以交互的东西也要有哦，也就是和原作内的效果一样」
    「把原作的世界搬到桌面上…桌面也是一个场景」
    「一切根据原作」

★ 本层只做三件事（第 84 轮清单里的三个缺口）
--------------------------------------------
1. **射线四段矩形（I6）** —— Z 键按下时，按主角当前朝向开一条矩形，
   找里面"最近的那个可交互物"。原作出处逐字（`obj_mainchara_Step_0`）：
   ```
   if (button1_p()) {
       d = global.darkzone + 1;
       if (global.facing == 1)  // 右
           collision_rectangle(x + sw/2, y + (6*d) + sh/2,
                               x + sw + (13*d), y + sh, obj_interactable, ...);
       if (global.facing == 3)  // 左
           collision_rectangle(x + sw/2, y + (6*d) + sh/2,
                               x - (13*d), y + sh, obj_interactable, ...);
       if (global.facing == 0)  // 下（★ 用 28d / 15d，不是 6d）
           collision_rectangle(x + (4*d), y + (28*d),
                               (x + sw) - (4*d), y + sh + (15*d), ...);
       if (global.facing == 2)  // 上（★ 用 5d）
           collision_rectangle(x + (3*d), y + sh - (5*d),
                               (x + sw) - (5*d), y + (5*d), ...);
   }
   ```
   ★ **四段形状各不相同**：左右是"细长横条（高度=角色高度）"，下是"下方一大块"、
   上是"上方一大块"。**没有一段是简单的"角色前方一个方块"** —— 所以本模块
   不做"朝向前方 N 像素"的简化，而是**逐段照抄**（四段各一个函数，可分别断言）。

2. **被交互者转向主角（I3）** —— 原作命中后：
   ```
   with (interactedobject) { facing = 3; }
   with (interactedobject) { scr_interact(); }
   ```
   ★ 注意原文里 `facing = 3` 是**硬编码左**（因为那一段就是"主角朝右、对象在右"的
   分支）。本项目不复刻这个硬编码 —— 而是让被交互者**真的看向主角**
   （用既有的 `_facing_between(dx, dy)`，它已按 45° 分档）。这是**等价实现**，
   不是改写：原作那四段各自 `facing=3/1/0/2` 合起来就是"看向主角"。

3. **NPC 待机朝向（I9）** —— 原作 `obj_npc_susiedark_Step_1`：
   ```
   if (myinteract == 0) { facing = dfacing; }
   ```
   即"没在对话时，回到自己的默认朝向"。本项目在 `Body` 上记初始朝向，
   对话结束（`myinteract == 0`）后回落。

**不做**：不碰 Qt、不播放音频、不做寻路、不做对话生成（对话走既有的
`main.npc_speak`，本模块只负责"找到人 + 转向 + 交回控制"）。

零依赖纪律（🔴 与 companion / npc_placement / scene_system 同源）
--------------------------------------------------------------
本模块**禁 import Qt、禁 import 任何项目内模块**（只准标准库）。
`main.py` 在 import 期就要建控制器；回头 import 项目内模块就会把
「初始化环」接上（本项目已踩 4 次，症状是 import 期直接崩、零输出）。
⇒ 本文件只准 `logging` / `math` / `collections`。

★ 与 `companion.Interactable` 的分工（**不许有第二套**）
------------------------------------------------------
· `companion.Interactable` = 「**交互协议**」（`myinteract` 三态 + 全局锁 + 防抖）；
· 本模块 = 「**怎么找到它**」（射线矩形 + 最近命中 + 转向）。
  ⇒ 本模块**只产出"该跟谁交互 + 他该朝哪"**，触发交给调用方
     `interactable.interact(actor)`。绝不自己实现对话/上锁 —— 那会让
     "对话时能不能点东西"出现两套互相不知道的锁（本项目最贵的坑）。

★ 三条设计律（都有正/负控制断言）
----------------------------------
1. **找不到就是没找到** —— 矩形内无人 ⇒ 返回 `None`，**绝不**回落到
   "最近的一个就算"（那会让"对空气按 Z"莫名其妙触发隔墙的人）。
2. **四段形状逐段照抄** —— 不许简化成"前方方块"（见上 #1 的注释）。
3. **数值全部有出处** —— 6 / 13 / 4 / 28 / 15 / 3 / 5 / 1 这些系数每个都在
   上面注释里能查到原作出处；本项目自创的（如 `ACTOR_HALF_W` 的取值口径）
   单独标注。
"""
import logging


def _pet_logger_name(_name):
    """把模块 `__name__` 映射到 `ralsei_pet.` 命名空间下的名字。

    ★ 与 `companion._pet_logger_name` 同源（第75轮实测：扁平导入的 logger
      在包形式加载下必然降级成裸 logger ⇒ INFO 全丢、故障查不到）。
      这里**独立复制**而不是 import —— 本模块的零依赖契约禁 import 项目内模块。
    """
    if not _name or _name == '__main__':
        return 'ralsei_pet.main'
    if _name.startswith('ralsei_pet.'):
        return _name
    if _name.startswith('modules.'):
        return 'ralsei_pet.' + _name
    return 'ralsei_pet.' + _name


_log = logging.getLogger(_pet_logger_name(__name__))

# ===========================================================================
#  朝向枚举（★ 与 npc_placement.FACINGS 同值域；此处独立定义避免 import）
# ===========================================================================

#: 原作朝向枚举：`0=下 / 1=右 / 2=上 / 3=左`（第84轮取证确证）。
FACE_DOWN = 'down'
FACE_RIGHT = 'right'
FACE_UP = 'up'
FACE_LEFT = 'left'
FACINGS = (FACE_DOWN, FACE_RIGHT, FACE_UP, FACE_LEFT)

#: 朝向 → 原点数（仅用于诊断打印；★ 不进任何判据）。
FACING_TO_GM = {FACE_DOWN: 0, FACE_RIGHT: 1, FACE_UP: 2, FACE_LEFT: 3}

#: 朝向 → 单位向量（本项目用逻辑坐标，`y` 向下为正 ⇒ 下是 `+1`）。
#: ★ 这张表是"朝向"的**单一真源**：射线、转向判定都从这里取，不各写一遍。
FACING_VECTORS = {
    FACE_DOWN: (0.0, 1.0),
    FACE_RIGHT: (1.0, 0.0),
    FACE_UP: (0.0, -1.0),
    FACE_LEFT: (-1.0, 0.0),
}

#: 反向朝向（被交互者看向主角 = 主角朝向的反向）。
OPPOSITE_FACING = {
    FACE_DOWN: FACE_UP,
    FACE_UP: FACE_DOWN,
    FACE_LEFT: FACE_RIGHT,
    FACE_RIGHT: FACE_LEFT,
}

# ===========================================================================
#  射线几何常量（★ 全部照抄 `obj_mainchara_Step_0`，出处见模块头注释）
# ===========================================================================

#: 主角碰撞盒（原作用 `sprite_width` / `sprite_height`）。
#: ★ 本项目没有逐角色的精灵尺寸表（渲染层尚未接 NPC 帧，见 main.py 3479 行注释）
#:   ⇒ 用一个**统一的、与原作 Ralsei/小体型角色同量级**的盒。这是**自创口径**，
#:   标注在此处，不与原作数值混写。单位 = 逻辑房间像素。
ACTOR_HALF_W = 12.0     #: 半分宽（原作 sw/2 的等价物）
ACTOR_HALF_H = 16.0     #: 半分高（原作 sh/2 的等价物）

#: 暗世界射线加长倍数（原作 `d = global.darkzone + 1`）：
#: 光世界 `darkzone=0 ⇒ d=1`，暗世界 `darkzone=1 ⇒ d=2`。
DARKZONE_LIGHT = 0
DARKZONE_DARK = 1

#: 距主角中心的**安全钳制**：矩形最小厚度（防止 `d` 异常时塌成零面积）。
MIN_RAY_THICK = 4.0

# ===========================================================================
#  射线：四段矩形（★ 逐段照抄，不简化）
# ===========================================================================
def ray_rect(x, y, facing, darkzone=DARKZONE_LIGHT,
             half_w=ACTOR_HALF_W, half_h=ACTOR_HALF_H):
    """返回主角 `(x, y)` 朝 `facing` 时那条射线的矩形 `(x1, y1, x2, y2)`。

    ★ 参数 `(x, y)` = 主角**中心**（原作里主角的 `x/y` 就是 sprite 左上角，
      但本项目 `Body.x/y` 用的是**中心**口径 —— 见 `npc_placement.Body`。
      所以这里做的是一次**口径换算**：把原作的 `x + sw/2` 之类改写成
      `cx ± half_w` 的形状。**换算口径写在每段注释里，逐段可核。**

    四段（照抄原作 `obj_mainchara_Step_0`）::

        右(1): x+sw/2, y+6d+sh/2,  x+sw+13d, y+sh
        左(3): x+sw/2, y+6d+sh/2,  x-13d,    y+sh
        下(0): x+4d,   y+28d,      x+sw-4d,  y+sh+15d
        上(2): x+3d,   y+sh-5d,    x+sw-5d,  y+5d

    返回 `None` 表示朝向非法（**不猜**，律 1）。
    """
    if facing not in FACINGS:
        return None
    try:
        cx = float(x)
        cy = float(y)
    except (TypeError, ValueError):
        return None
    # `darkzone` 非法（如传字符串）⇒ 按光世界处理，但**不抛**（射线是每帧调用）。
    try:
        dz = int(darkzone)
    except (TypeError, ValueError):
        dz = DARKZONE_LIGHT
    d = float(dz + 1)

    hw = float(half_w)
    hh = float(half_h)
    # 原作坐标口径：左 = `x`，右 = `x + sw`，上 = `y`，下 = `y + sh`
    # ★ 本项目传入的 `(cx, cy)` 是**中心**（`npc_placement.Body` 口径），
    #   而原作那些式子里的 `x` / `y` 是 **sprite 左上角** ⇒ 逐式换算是：
    #     原文 `x`      → `cx - hw`
    #     原文 `y`      → `cy - hh`
    #     原文 `x + sw` → `cx + hw`
    #     原文 `y + sh` → `cy + hh`
    #   ⚠️ 首版把"下/上"两段的 `y` 直接当 `cy` 用（漏了 `- hh`），
    #      实测 y1 偏 16px（= 一个半高）—— A/B 判据（`check88.C1`）就是这么抓到的。
    left = cx - hw
    right = cx + hw
    top = cy - hh                 #: 原作的 `y`
    bottom = cy + hh              #: 原作的 `y + sh`

    if facing == FACE_RIGHT:
        # 原文: x+sw/2, y+6d+sh/2, x+sw+13d, y+sh
        #   →  cx,     (cy-hh)+6d+hh,  cx+hw+13d,  cy+hh
        x1 = cx
        y1 = top + 6.0 * d + hh
        x2 = right + 13.0 * d
        y2 = bottom
    elif facing == FACE_LEFT:
        # 原文: x+sw/2, y+6d+sh/2, x-13d, y+sh
        x1 = left - 13.0 * d
        y1 = top + 6.0 * d + hh
        x2 = cx
        y2 = bottom
    elif facing == FACE_DOWN:
        # 原文: x+4d, y+28d, x+sw-4d, y+sh+15d
        #   →  (cx-hw)+4d, (cy-hh)+28d, (cx+hw)-4d, (cy+hh)+15d
        x1 = left + 4.0 * d
        y1 = top + 28.0 * d
        x2 = right - 4.0 * d
        y2 = bottom + 15.0 * d
    else:  # FACE_UP
        # 原文: x+3d, y+sh-5d, x+sw-5d, y+5d
        #   →  (cx-hw)+3d, (cy+hh)-5d, (cx+hw)-5d, (cy-hh)+5d
        x1 = left + 3.0 * d
        y1 = bottom - 5.0 * d
        x2 = right - 5.0 * d
        y2 = top + 5.0 * d

    # 归一化（x1<=x2 / y1<=y2）—— 原作的 left 段给的是 x1 > x2（从内往外），
    # `collision_rectangle` 内部会自己摆正；本模块显式归一，避免下游自己判。
    if x1 > x2:
        x1, x2 = x2, x1
    if y1 > y2:
        y1, y2 = y2, y1
    # 最小厚度钳制（防 `d` 异常 / 尺寸为 0 时塌成线）。
    if x2 - x1 < MIN_RAY_THICK:
        x2 = x1 + MIN_RAY_THICK
    if y2 - y1 < MIN_RAY_THICK:
        y2 = y1 + MIN_RAY_THICK
    return (x1, y1, x2, y2)


def rect_contains(rect, px, py):
    """点 `(px, py)` 是否落在 `rect`（含边界）。`rect` 非法 ⇒ `False`。"""
    if not rect or len(rect) != 4:
        return False
    try:
        x1, y1, x2, y2 = (float(v) for v in rect)
        px = float(px)
        py = float(py)
    except (TypeError, ValueError):
        return False
    return x1 <= px <= x2 and y1 <= py <= y2


def rect_intersects(rect, target):
    """两个矩形是否相交（含边贴边）。任一非法 ⇒ `False`。"""
    if not rect or not target or len(rect) != 4 or len(target) != 4:
        return False
    try:
        ax1, ay1, ax2, ay2 = (float(v) for v in rect)
        bx1, by1, bx2, by2 = (float(v) for v in target)
    except (TypeError, ValueError):
        return False
    return not (ax2 < bx1 or bx2 < ax1 or ay2 < by1 or by2 < ay1)


# ===========================================================================
#  命中：在射线里找**最近**的那个可交互物
# ===========================================================================
def _box_of(item):
    """取一个候选项的矩形 `(x1, y1, x2, y2)`。

    ★ **形状约定（写死，不留歧义）**：
      · `(x, y)`                —— 点（退化盒，半宽半高 = 0）；
      · `(x1, y1, x2, y2)`      —— **矩形**（不是"中心+半宽"！见下踩坑）；
      · `{'rect': (x1,y1,x2,y2)}` —— 矩形；
      · `{'x':..,'y':..,'hw':..,'hh':..}` —— 中心 + 半宽半高。
      · 取不到 / 形状不认识 ⇒ `None`（该候选**不参与**命中，律 1）。

    ⚠️ 首版把 4 元组同时当"矩形"和"中心+半宽"用（docstring 写后者、代码做前者），
       `(130, 100, 10, 16)` 被当成 `x1=130 > x2=10` 的非法矩形 ⇒ 命中判据全假
       （一个"文档说 A、代码做 B"的典型）。现在只认一种语义：**4 元组 = 矩形**。
       想要"中心 + 半宽"就用字典 —— 名字里带 `hw`/`hh` 就不会认错。
    """
    if item is None:
        return None
    if isinstance(item, dict):
        if 'rect' in item:
            r = item.get('rect')
            if not (r and len(r) == 4):
                return None
            try:
                box = tuple(float(v) for v in r)
            except (TypeError, ValueError):
                return None
            return _normalize_box(box)
        try:
            x = float(item.get('x', 0.0))
            y = float(item.get('y', 0.0))
        except (TypeError, ValueError):
            return None
        try:
            hw = float(item.get('hw', item.get('half_w', 0.0)) or 0.0)
            hh = float(item.get('hh', item.get('half_h', 0.0)) or 0.0)
        except (TypeError, ValueError):
            return None
        return _normalize_box((x - hw, y - hh, x + hw, y + hh))
    if isinstance(item, (list, tuple)):
        try:
            vals = [float(v) for v in item]
        except (TypeError, ValueError):
            return None
        if len(vals) == 4:
            return _normalize_box((vals[0], vals[1], vals[2], vals[3]))
        if len(vals) == 2:
            return (vals[0], vals[1], vals[0], vals[1])
    return None


def _normalize_box(box):
    """矩形归一化（`x1<=x2` / `y1<=y2`）。非法 ⇒ `None`。"""
    if not box or len(box) != 4:
        return None
    try:
        x1, y1, x2, y2 = (float(v) for v in box)
    except (TypeError, ValueError):
        return None
    if x1 > x2:
        x1, x2 = x2, x1
    if y1 > y2:
        y1, y2 = y2, y1
    return (x1, y1, x2, y2)


def _distance2_to_box(cx, cy, box):
    """主角中心到矩形中心的平方距离（★ 不取 sqrt —— 只用来比大小）。"""
    bx = (box[0] + box[2]) * 0.5
    by = (box[1] + box[3]) * 0.5
    dx = bx - cx
    dy = by - cy
    return dx * dx + dy * dy


def pick_nearest(candidates, rect, cx, cy):
    """在所有**与 `rect` 相交**的候选里，挑**盒中心离 `(cx,cy)` 最近**的那个。

    返回 `(key, box)`；没有命中 ⇒ `(None, None)`。

    ★ `candidates` 的形状：`[(key, geom), ...]` 或 `{key: geom}`。
    ★ 平手时取 **key 的字典序最小** —— 保证**确定性**（否则同一帧两次调用
      可能给出不同的人，回归套件会随机红）。
    """
    if not rect:
        return (None, None)
    if isinstance(candidates, dict):
        items = list(candidates.items())
    else:
        items = list(candidates or [])
    best_key = None
    best_box = None
    best_d = None
    for key, geom in items:
        box = _box_of(geom)
        if box is None:
            continue
        if not rect_intersects(rect, box):
            continue
        dist = _distance2_to_box(cx, cy, box)
        if (best_d is None or dist < best_d
                or (dist == best_d and str(key) < str(best_key))):
            best_key = key
            best_box = box
            best_d = dist
    return (best_key, best_box)


# ===========================================================================
#  转向（I3 / I9）
# ===========================================================================
def facing_toward(ax, ay, bx, by):
    """从 `(ax, ay)` 看 `(bx, by)` 应该是哪个朝向（取占优轴，45° 分档）。

    ★ 与 `npc_placement._facing_between` 同算法 —— 但那是在 `npc_placement`
      内部（本模块零依赖，不能 import）⇒ 此处独立实现。
      **同一份规则两处算 = 最贵的坑** ⇒ 配套一条 A/B 判据：把两边喂同样输入，
      结果必须逐项相等（`check88` 的 `D1`）。任一改动破坏等价 ⇒ 立刻报红。

    ★★ 退化判定**必须与 `_facing_between` 逐位一致**（`dx == 0.0 and dy == 0.0`）。
      首版写的是 `abs(dx) < 1e-9`（自认为"更稳健"），结果在 `(1e-12, 0)` 上两边
      分道扬镳：这边返 `None`、那边返 `'right'` ⇒ A/B 判据当场报红。
      教训：**等价性判据守的是"算法"，不是"阈值"** —— 只要叫"等价"，
      就不能留一条只有本侧知道的宽容带。
    """
    try:
        dx = float(bx) - float(ax)
        dy = float(by) - float(ay)
    except (TypeError, ValueError):
        return None
    if dx == 0.0 and dy == 0.0:
        return None
    if abs(dx) >= abs(dy):
        return FACE_RIGHT if dx > 0 else FACE_LEFT
    return FACE_DOWN if dy > 0 else FACE_UP


def face_actor(ax, ay, bx, by):
    """被交互者 `(bx, by)` 看向主角 `(ax, ay)` 的朝向（I3 的落地）。

    等价于 `facing_toward(bx, by, ax, ay)`。单独一个函数名是为了
    **判据可读**（"谁看谁"这件事在名字里，不靠读参数顺序）。
    """
    return facing_toward(bx, by, ax, ay)


# ===========================================================================
#  一步到位：解一条"该跟谁交互 + 他朝哪"
# ===========================================================================
def resolve(actor_xy, facing, candidates, darkzone=DARKZONE_LIGHT,
            half_w=ACTOR_HALF_W, half_h=ACTOR_HALF_H):
    """解出这一帧按 Z 应该交互谁。返回 dict（**恒有值，不返回 None**）。

    字段::

        {
          'rect':    (x1,y1,x2,y2) 射线矩形（诊断 / 判据用）,
          'target':  key 或 None   命中的人,
          'box':     (x1,y1,x2,y2) 他的盒 或 None,
          'face':    朝向 或 None  他该转向哪（I3）,
          'reason':  'hit' / 'no_facing' / 'no_target' / 'bad_actor_xy',
        }

    ★ `actor_xy` 非法 / `facing` 非法 ⇒ `target=None` 且 `reason` 写明成因
      （诊断要能看出"是没人"还是"输入坏了"）。
    """
    out = {'rect': None, 'target': None, 'box': None, 'face': None,
           'reason': 'bad_actor_xy'}
    if not actor_xy or len(actor_xy) != 2:
        return out
    try:
        ax = float(actor_xy[0])
        ay = float(actor_xy[1])
    except (TypeError, ValueError):
        return out
    if facing not in FACINGS:
        out['reason'] = 'no_facing'
        return out

    rect = ray_rect(ax, ay, facing, darkzone=darkzone,
                    half_w=half_w, half_h=half_h)
    out['rect'] = rect
    if rect is None:
        out['reason'] = 'no_facing'
        return out

    key, box = pick_nearest(candidates, rect, ax, ay)
    if key is None:
        out['reason'] = 'no_target'
        return out

    out['target'] = key
    out['box'] = box
    out['face'] = face_actor(ax, ay,
                             (box[0] + box[2]) * 0.5,
                             (box[1] + box[3]) * 0.5)
    out['reason'] = 'hit'
    return out


# ===========================================================================
#  自检 / 描述
# ===========================================================================
def describe(rect):
    """一行诊断串（日志用）。"""
    if not rect:
        return '射线=(无)'
    return '射线=(%.1f,%.1f)-(%.1f,%.1f)' % (
        rect[0], rect[1], rect[2], rect[3])


WIRING = {
    'module': 'npc_interact',
    'round': 88,
    'purpose': 'Z 键 → 射线检测 → 触发 NPC 交互（原作 I3/I6/I9 的等价物）',
    'depends_on': [],
    'used_by': ['main.py'],
    'not_yet': [
        'NPC 逐角色精灵尺寸表（现用统一 ACTOR_HALF_W/H 自创口径）',
        'obj_interactable / obj_interactablesolid 的**两层分类**（原作用于区分'
        '"普通/实心"两种交互优先级；本项目目前只有一层）',
    ],
}
