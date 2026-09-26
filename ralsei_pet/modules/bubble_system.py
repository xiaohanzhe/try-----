# -*- coding: utf-8 -*-
"""第49轮 · 光世界「扭蛋球」容器（零依赖，P0~P1 骨架）。

用户口径（第49轮原话，逐字要点）
--------------------------------
* 「ralsei也不可以脱离暗世界，除非是用…第3章里出现过一很多扭蛋的那个球」
* 「做一个4个方向的旋转动画，然后在ralsei需要在光世界的时候让kris给他使用，
   然后就相当于把那个球套在了他身上」
* 「球本身不可见的地方需要能遮住ralsei，所以你要做一下代码」
* 「ralsei是在球里面，所以不要穿模，要时刻保持在光世界时候在球里面」
* 「即使是球可见度部分看到ralsei也要有那种透过塑料看人的感觉，也就是给他上一层滤镜」
* 「其他主角团的人和lancer也可以进去，要求和上述一样，
   只不过他们可以随时脱下来（除了lancer）」

★ 第50轮用户口径（逐字）
* 「16项要，但只有ralsei能自由在其他暗世界走，其他人无法通过球去其他世界，
   只能去光世界或是回原先他们的暗世界（这个不需要他们套上球）」
  ⇒ 球**只**给 Ralsei「出暗世界·去光世界」这一条能力；
    **不给**任何跨暗世界能力（见 `grants_foreign_dark()`，恒 `False`）。

原作依据（`_evidence/取证与设计49.md` §1，逐字取自
`ch3.obj_tenna_board4_gacha_Draw_0.gml` / `ch3.obj_ch3_GSC07_gacha_{Create,Draw}_0.gml`）
------------------------------------------------------------------------------------
「遮住角色」的原作做法**不是**额外 mask，而是**把球切成三层、角色夹在中间**：

    ① 球·下半后层(frame 2) → ② 角色 → ③ 球·下半前层(frame 3) → ④ 球·上罩(frame 1)

不透明像素自然遮挡，可见处自然透出 ⇒ `draw_plan()` 返回的就是这个顺序。

零依赖契约：模块顶部只允许 `import collections / json / logging / math / os`。
"""
import collections
import logging
import math
import os

try:
    from logger_utils import get_logger
    _log = get_logger(__name__)
except ImportError:
    _log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

# ---------------------------------------------------------------- 原作常量
#: 主球精灵（4 帧；0=整球、1=上罩、2=下半后层、3=下半前层）
SPRITE = 'spr_dw_tv_gachaball_transparent'
FRAME_FULL = 0
FRAME_TOP = 1
FRAME_BACK = 2
FRAME_FRONT = 3

SPRITE_W = 62
SPRITE_H = 62
ORIGIN_X = 31
ORIGIN_Y = 31

#: 绘制顺序（原作 Draw_0 逐字顺序）——元组元素是帧号
DRAW_ORDER = (FRAME_BACK, FRAME_FRONT, FRAME_TOP)
DRAW_ORDER_WITH_FULL = (FRAME_FULL,)

#: 缩放（原作 `_scale`；Susie 特例 2.02）
SCALE_DEFAULT = 1.55
SCALE_SUSIE = 2.02
CHAR_SCALE = 2.0

#: 角度（原作 `target_angle`）
ANGLE_DEFAULT = -150.0
ANGLE_MODE2 = -180.0
ANGLE_MODE34 = -100.0
ANGLE_TABLE = {0: ANGLE_DEFAULT, 1: ANGLE_DEFAULT, 2: ANGLE_MODE2,
               3: ANGLE_MODE34, 4: ANGLE_MODE34}

#: ★ 用户要的「4 个方向的旋转动画」——4 个朝向**均分整圈**（360°/4 = 90°）。
#: ⚠️ 不能写成 45°：那样 4 个朝向只覆盖 135°，转不满一圈，
#:    判据 G4 用「转 4 次必须回到原位」的行为断言把这一点钉死。
SPIN_DIRECTIONS = 4
SPIN_STEP_DEG = 360.0 / SPIN_DIRECTIONS

#: 缓动参数（原作 `scr_lerpvar` 的步数）
ALPHA_LERP_STEPS = 5
POS_LERP_STEPS = 12
POS_LERP_PER_FRAME = 3
ANGLE_DELAY_FRAMES = 6
ANGLE_LERP_FRAMES = 15

#: 上下半的起始 y（原作 109 / 221）与 y 偏移（`y_offset = 28`）
TOP_START_Y = 109.0
BOTTOM_START_Y = 221.0
Y_OFFSET = 28.0

#: 帧率（原作 `GMS2FPS = 30`）
FPS = 30

# ---------------------------------------------------------------- 角色规则
CONTAINABLE = ('kris', 'susie', 'ralsei', 'lancer')

#: 「可以随时脱下来」= 其余主角团成员
ALWAYS_EJECTABLE = ('kris', 'susie')

#: 「除了 lancer」——永远脱不下来
NEVER_EJECTABLE = ('lancer',)

#: **必须靠球才能出暗世界（去光世界）**的角色（Ralsei）。
#: ★ 第50轮微调：别的角色去光世界**不需要球**（见 `npc_system.world_gate`），
#:   所以这条现在专指"必须靠球"的那一个特例，而不是"只有他能出暗世界"。
BUBBLE_ESCAPE = ('ralsei',)

#: 球的人名（进 prompt / 提示语用）
CHAR_CN = {'kris': 'Kris', 'susie': 'Susie', 'ralsei': 'Ralsei', 'lancer': 'Lancer'}

# 塑料滤镜默认参数（"透过塑料看人"）
FILTER_DEFAULT = collections.OrderedDict((
    ('tint', (222, 231, 238)),   # 轻微冷色偏（塑料反光）
    ('alpha', 0.88),             # 不是全透明——隔了一层壳
    ('rim', 0.18),               # 边缘高光强度
    ('saturate', 0.92),          # 略降饱和
))


def scale_for(char_id):
    """Susie 用原作的更大倍率（2.02），其余 1.55。"""
    return SCALE_SUSIE if char_id == 'susie' else SCALE_DEFAULT


def target_angle(mode=0):
    return ANGLE_TABLE.get(mode, ANGLE_DEFAULT)


def angle_for_direction(dir_index, mode=0):
    """★ 「4 个方向」：基准角 + dir_index × 45°。"""
    base = target_angle(mode)
    i = int(dir_index) % SPIN_DIRECTIONS
    return base + i * SPIN_STEP_DEG


def ejectable(char_id, world):
    """**能不能主动脱下球**。

    * Lancer：**永远不能**。
    * Ralsei：在**光世界不能**（脱了就违反「不可脱离暗世界」）；在暗世界不需要球，可脱。
    * 其余主角团（Kris / Susie）：随时可以。

    ⇒ 非 `CONTAINABLE` 的角色一律 False。
    """
    if char_id not in CONTAINABLE:
        return False
    if char_id in NEVER_EJECTABLE:
        return False
    if char_id == 'ralsei':
        return world != 'light'
    return char_id in ALWAYS_EJECTABLE


def must_stay_inside(char_id, world):
    """是否**必须留在球里**（用于「不要穿模」的强约束）。

    * Lancer：永远。
    * Ralsei：光世界必须（「时刻保持在光世界时候在球里面」）。
    """
    if char_id not in CONTAINABLE:
        return False
    if char_id in NEVER_EJECTABLE:
        return True
    if char_id == 'ralsei':
        return world == 'light'
    return False


def grants_foreign_dark(char_id=None):
    """球**能否**让人进入别的暗世界。

    ★ 第50轮口径：「其他人无法通过球去其他世界」⇒ **恒 `False`**。
    跨暗世界是 Ralsei **自身**的能力（`npc_system.free_dark_roam`），与球无关 ——
    把这条写成函数而不是"省略不写"，是为了让回归锁能**正面断言**它永远为假
    （否则"没实现"和"实现成永远拒绝"在测试上是同一件事）。
    """
    return False


def filter_params(char_id=None):
    """「透过塑料看人」的滤镜参数（返回副本，调用方可改）。"""
    p = collections.OrderedDict(FILTER_DEFAULT)
    p['tint'] = tuple(p['tint'])
    return p


# ---------------------------------------------------------------- 几何

def ball_radius(scale=SCALE_DEFAULT):
    """球的绘制半径（像素）——由原作精灵尺寸 × 缩放推出。"""
    return (SPRITE_W * scale) / 2.0


def clamp_inside(cx, cy, bx, by, radius):
    """把角色中心 (cx,cy) **钳制在**球心 (bx,by)、半径 radius 的圆内。

    ⇒ 「ralsei是在球里面，不要穿模」的落实点：每帧调用，越界即拉回边界。
    返回 `(x, y, moved, dist)`；`moved` 表示这一帧是否发生过钳制。
    """
    dx = cx - bx
    dy = cy - by
    d = math.hypot(dx, dy)
    if radius <= 0:
        return (bx, by, True, d)
    if d <= radius:
        return (cx, cy, False, d)
    k = radius / d if d else 0.0
    return (bx + dx * k, by + dy * k, True, d)


def draw_plan(bx, by, char_xy, scale=SCALE_DEFAULT, angle=ANGLE_DEFAULT,
              alpha=1.0, char_sprite=None, char_frame=0):
    """返回**逐帧绘制指令**（有序列表）。顺序 = 原作 `Draw_0`。

    每项：`{'role', 'sprite', 'frame', 'x', 'y', 'scale', 'angle', 'alpha'}`
    `role` ∈ `{'ball_back', 'character', 'ball_front', 'ball_top'}`。
    """
    r = ball_radius(scale)
    plan = [
        {'role': 'ball_back', 'sprite': SPRITE, 'frame': FRAME_BACK,
         'x': bx, 'y': by, 'scale': scale, 'angle': angle, 'alpha': alpha},
        {'role': 'character', 'sprite': char_sprite, 'frame': char_frame,
         'x': char_xy[0], 'y': char_xy[1], 'scale': CHAR_SCALE, 'angle': 0.0, 'alpha': 1.0},
        {'role': 'ball_front', 'sprite': SPRITE, 'frame': FRAME_FRONT,
         'x': bx, 'y': by, 'scale': scale, 'angle': angle, 'alpha': alpha},
        {'role': 'ball_top', 'sprite': SPRITE, 'frame': FRAME_TOP,
         'x': bx, 'y': by, 'scale': scale, 'angle': angle, 'alpha': alpha},
    ]
    del r  # 半径只用于 clamp_inside；此处保持签名稳定
    return plan


# ---------------------------------------------------------------- 运行时

class Bubble(object):
    """**一个**角色身上的球（穿/脱/旋转/滤镜/钳制）。"""

    APPEAR = 'appear'
    HOLD = 'hold'
    GONE = 'gone'

    def __init__(self, char_id, world='dark', mode=0):
        self.char_id = char_id
        self.world = world
        self.mode = mode
        self.scale = scale_for(char_id)
        self.angle = angle_for_direction(0, mode)
        self.dir_index = 0
        self.alpha = 0.0
        self.state = self.APPEAR
        self.frames_alive = 0

    # -- 旋转
    def spin_to(self, dir_index):
        """切到第 N 个方向（0~3）→ 目标角 = 基准角 + N×45°。"""
        self.dir_index = int(dir_index) % SPIN_DIRECTIONS
        return angle_for_direction(self.dir_index, self.mode)

    def spin_step(self, dt_frames=1):
        """朝目标角缓动（原作是延迟 6 帧、历时 15 帧的 lerp）。"""
        tgt = angle_for_direction(self.dir_index, self.mode)
        k = min(1.0, max(0.0, float(dt_frames) / ANGLE_LERP_FRAMES))
        self.angle += (tgt - self.angle) * k
        return self.angle

    # -- 显隐
    def tick(self, dt_frames=1):
        self.frames_alive += dt_frames
        step = float(dt_frames) / max(1, ALPHA_LERP_STEPS)
        if self.state == self.APPEAR:
            self.alpha = min(1.0, self.alpha + step)
            if self.alpha >= 1.0:
                self.state = self.HOLD
        elif self.state == self.GONE:
            self.alpha = max(0.0, self.alpha - step)
        self.spin_step(dt_frames)
        return self.alpha

    # -- 钳制
    def keep_inside(self, char_xy, ball_xy):
        """把角色拉回球内（「不要穿模」）。返回 `(x, y, moved)`。"""
        r = ball_radius(self.scale) * 0.72   # 留壳厚，角色不贴边
        x, y, moved, _d = clamp_inside(char_xy[0], char_xy[1], ball_xy[0], ball_xy[1], r)
        return (x, y, moved)

    def plan(self, ball_xy, char_xy, char_sprite=None, char_frame=0):
        return draw_plan(ball_xy[0], ball_xy[1], char_xy, scale=self.scale,
                         angle=self.angle, alpha=self.alpha,
                         char_sprite=char_sprite, char_frame=char_frame)

    def filters(self):
        return filter_params(self.char_id)

    def can_eject(self):
        return ejectable(self.char_id, self.world)


class BubbleField(object):
    """当前场景里所有球（一般最多 1 个在主控角色身上）。"""

    def __init__(self):
        self._by_char = collections.OrderedDict()

    # -- 查询
    def __contains__(self, cid):
        return cid in self._by_char

    def __len__(self):
        return len(self._by_char)

    def get(self, cid):
        return self._by_char.get(cid)

    def holders(self):
        return list(self._by_char.keys())

    # -- 动作
    def equip(self, cid, by='kris', world='dark', mode=0):
        """给 `cid` 套上球。**只有主角团成员**能给（`by` 必须是主角团）。

        * 不在 `CONTAINABLE` ⇒ 返回 `None`
        * 已经在球里 ⇒ 直接返回既有球（幂等）
        * Ralsei 在光世界**必须**靠球 ⇒ 这是唯一合法途径
        """
        if cid not in CONTAINABLE:
            return None
        if by not in CONTAINABLE:
            return None
        b = self._by_char.get(cid)
        if b is not None:
            b.world = world
            return b
        b = Bubble(cid, world=world, mode=mode)
        self._by_char[cid] = b
        return b

    def unequip(self, cid, world=None):
        """脱下球。**不可脱的会拒绝**（返回 `False`）。"""
        b = self._by_char.get(cid)
        if b is None:
            return False
        w = b.world if world is None else world
        if not ejectable(cid, w):
            return False
        del self._by_char[cid]
        return True

    def transfer_world(self, world):
        """整体切世界后的自动处理（**回暗世界自动脱**，符合"效果不带出章节"的同类口径）。"""
        dropped = []
        for cid in list(self._by_char.keys()):
            b = self._by_char[cid]
            if b.world == 'light' and world == 'dark' and ejectable(cid, 'dark'):
                del self._by_char[cid]
                dropped.append(cid)
            else:
                b.world = world
        return dropped

    def tick_all(self, dt_frames=1):
        for b in self._by_char.values():
            b.tick(dt_frames)

    def keep_inside_all(self, char_positions, ball_position):
        """对每个球把被装角色钳回球内，返回 {cid: (x, y)}。"""
        out = {}
        for cid, b in self._by_char.items():
            xy = char_positions.get(cid)
            if xy is None:
                continue
            x, y, _moved = b.keep_inside(xy, ball_position)
            out[cid] = (x, y)
        return out
