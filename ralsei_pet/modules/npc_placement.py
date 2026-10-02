# -*- coding: utf-8 -*-
"""NPC 站位 / 游荡 / 编队 / 结对（第56轮）。

用户口径（第56轮原话，逐字要点）
--------------------------------
* 「对于那些npc**参考原作**给他们设定的**初始在城堡镇里的位置**再加一些
  **自己游荡**的特性，就像是，**主角团会总凑在一起**，其他npc一部分也会有
  **相互经常互动**的情节，参考原作」
* 「其次，**只有主角团最多加个lancer能来电脑桌面，其余的不能**」

⇒ 本模块四件事，**互相独立、各自可单测**：

  1. `load_placement()` —— 读 `assets/npc/_placement.json`
     （站位 / 编队 / 结对 / 桌面白名单），并顺带读 `_room_geometry.json` 做钳制；
  2. `Body` —— 三个**行为模式**：`stand` / `patrol` / `pace`（口径见下节）；
  3. `PartyRig` + `Trail` —— 主角团编队（照抄原作 caterpillar 的"落后帧数"语义）；
  4. `BondPair` —— 结对：两人**同处一个场景时**才会凑近 / 对望。

★★ 什么"照抄"、什么只是"概括" —— 这条口径必须写清楚，否则日后无从判断
----------------------------------------------------------------------
| 项 | 与原作的关系 |
|---|---|
| `stand` | **照抄**。`obj_npc_room` 的 Create 里 `image_speed = 0` ⇒ 默认就是不动的。 |
| `patrol` | **照抄**。`ch4.obj_room_castle_lancer_Step_0.gml` 里 maus / poppup / tasque 三例： 到端点换目标 `target = (alt % 2) ? (xstart + N) : xstart`、**同时** `scr_flip("x")` 转身、每帧 `x = scr_movetowards(x, target, speed)`。原文实数：N=180/124/130，speed=2/1/1。**不受任何剧情 flag 门控** ⇒ 可逐条照写。 |
| `pace` | ★ **只是概括**。`ch2.obj_npc_king_Step_0.gml` 的右行分支被 `global.flag[20] == 3`（他喝酒的过场）门控；我们只借它的**形状**：区间 + 软起停（`hspeed` 逐步累加/递减）+ y 的 `±4` 起伏 + `x = min(x, clamp)` 硬钳制。**不声称逐帧一致。** |
| 编队 | **照抄**。`scr_makecaterpillar` 里 `target = 12 + slot * 12` = "落后主角多少帧"；`obj_caterpillarchara` 存 25 帧位置历史做延迟插值。 |
| 初始坐标 | ⚠️ **能取到原作硬坐标就用硬的**（`_placement.json` 每条带 `evidence`）；取不到的**如实标 `derived` / `authored`**，绝不假装是原作数据。 |

★★ 为什么队友"凑在一起"要靠"落后帧数"而不是各自寻路
------------------------------------------------------
原作的做法是**轨迹延迟采样**（走主角走过的路）。它天然带来三件事：
① 不会撞墙（主角能走的地方队友必然能走）；② 不会卡死（没有 A* 失败态）；
③ 队形在拐角处自然贴合（不是几何插值出来的斜线）。本项目第46轮已论证过这条
（`第46轮-原作代码通读/_evidence/原作系统取证46.md` §2.4），这里直接用。

零依赖纪律（与 `scene_camera` / `npc_system` / `npc_persona` / `soul_entity` 同源）
----------------------------------------------------------------------------------
只允许模块顶部 `import collections / json / logging / math / os`。
**禁 import Qt、禁 import 任何项目内模块**（含 `npc_system` —— "能不能进这个世界"
由调用方注入）。内部函数**不许**再 import（回归锁 `check56` 用 AST 强制）。
"""
import collections
import json
import logging


def _pet_logger_name(_name):
    """把模块 `__name__` 映射到 `ralsei_pet.` 命名空间下的名字。

    ★ 为什么需要它（第75轮实测）：一批模块历史上用**扁平导入**取日志器
      （`try: from logger_utils import get_logger / except ImportError: 降级`）。
      当 main.py 以**包形式**加载（`from modules.x import ...`）时，
      模块内 `from logger_utils import ...` 必然 ImportError ⇒ 静默走降级
      ⇒ 拿到**裸 logger**（`modules.xxx`）⇒ 两个后果：
        ① 不在 `ralsei_pet` 树下 ⇒ 挂在根上的**文件 handler 收不到**；
        ② 没有祖先 `setLevel(INFO)` ⇒ 有效级别退回 **30 (WARNING)** ⇒ INFO 全丢。
      表现就是"故障查不到"、"日志里零故障记录"。

    ★ 为什么用标准库字符串运算而不是 import `logger_utils`：
      `logging` 是**进程级全局注册表** —— 只要名字拼对，拿到的就是同一个对象。
      所以本函数**一行项目 import 都不需要**，从而不违反纯数据层的
      「零依赖 / 白名单」契约（`scene_render` 顶层 import ⊆ logging、
      `team_hp` 禁 `from modules`、`soul_overlay` 不拖业务模块 … 那几条闸）。
    """
    if not _name or _name == '__main__':
        return 'ralsei_pet.main'
    if _name.startswith('ralsei_pet.'):
        return _name
    if _name.startswith('modules.'):
        return 'ralsei_pet.' + _name
    return 'ralsei_pet.' + _name

import math
import os

try:  # 项目内统一 logger；模块外独立导入时降级
    from logger_utils import get_logger
    _log = logging.getLogger(_pet_logger_name(__name__))
except ImportError:
    _log = logging.getLogger(_pet_logger_name(__name__))

SCHEMA_VERSION = 1

#: 站位表 / 房间几何（都在 `assets/npc/` 与 `assets/scenes/` 下）。
PLACEMENT_FILENAME = '_placement.json'
GEOMETRY_FILENAME = '_room_geometry.json'

# ---------------------------------------------------------------- 站立来源标签
#: 有原作脚本或原作房间名的**硬证据**。
SRC_ORIGINAL = 'original'
#: 房间有原作依据，房内坐标由本项目按同型房间布置。
SRC_DERIVED = 'derived'
#: 原作依据不足，本项目安排（**必须**在 `why` 里说清）。
SRC_AUTHORED = 'authored'
SOURCE_KINDS = (SRC_ORIGINAL, SRC_DERIVED, SRC_AUTHORED)

# ---------------------------------------------------------------- 行为模式
MODE_STAND = 'stand'
MODE_PATROL = 'patrol'
MODE_PACE = 'pace'
MODE_KINDS = (MODE_STAND, MODE_PATROL, MODE_PACE)

FACINGS = ('down', 'up', 'left', 'right')
FACE_DOWN = 'down'

# ---------------------------------------------------------------- 原作实数（锚点，便于核对）
#: 原作 `obj_room_castle_lancer_Step_0` 的三组 `(巡逻段长, 每帧速度)`：maus / poppup / tasque。
ORIGINAL_PATROLS = ((180, 2), (124, 1), (130, 1))
#: 原作 King 脚本里的硬钳制与右行端点（`x = min(x, 1455)` / `x < 1380`）。
ORIGINAL_PACE_CLAMP = 1455
ORIGINAL_PACE_END = 1380
#: 原作 King 的 y 起伏幅度（`ystart - 60`）。
ORIGINAL_PACE_RISE = 60.0
#: 原作 `scr_makecaterpillar`：`target = 12 + slot * 12`。
ORIGINAL_PARTY_LAG_BASE = 12
ORIGINAL_PARTY_LAG_STEP = 12
#: 原作 `obj_caterpillarchara` 的位置历史长度（`remx/remy` 数组长 25）。
ORIGINAL_TRAIL_LENGTH = 25
#: 原作 `GMS2FPS`。原作脚本里的速度是"**每帧**多少像素" ⇒ 换 px/s 要乘它。
GAME_FPS = 30.0

# ---------------------------------------------------------------- 本项目参数
#: 单帧 dt 上限（与 `soul_entity.MAX_DT` 同口径：卡顿一次不许把 NPC 甩出房间）。
MAX_DT = 0.1
#: 位置钳制时给房间四边留的空白（像素）。
WANDER_MARGIN = 24.0
#: `pace` 的加速度（px/s²）。**本项目取值**：照原作"每帧 ±1"的量级折算（1*30）。
PACE_ACCEL = 30.0
#: `pace` 的 y 起伏速度（px/s）。照原作"每帧 4"折算（4*30）。
PACE_Y_SPEED = 120.0
#: 编队各槽位的**错开量**（px）——**本项目微调**：只为了让"团长站着不动"时三人的
#: 显示像素不完全重叠（原作靠 `halign/valign` 也是几像素级的微调）。
#: ⚠️ 它加在 **y** 上（见 `PartyRig.place`），不是 x —— x 上的差值必须**纯粹**是
#:    `lag × 每帧位移`，否则那条量再也断不准（这正是第56轮修掉的坑）。
PARTY_LATERAL = (0.0, -6.0, 6.0)

BOND_KINDS = ('family', 'colleague', 'friend', 'classmate', 'rival')
MEET_APPROACH = 'approach'   # 走近到 gap 像素
MEET_FACE = 'face'           # 原地转向对望
MEET_KINDS = (MEET_APPROACH, MEET_FACE)
#: 结对默认间距（px）。**本项目取值**：照原作"并排两人 x 差 76"（Lancer/Mr. Elegance）
#: 与"两步之内的对话距离"折中。
DEFAULT_BOND_GAP = 72.0
#: 结对在别的场景时**不许隔空凑**（原作里跨房间的两人也不会互动）。
BOND_SAME_SCENE_ONLY = True
#: 结对 `approach` 的走近速度（px/秒）。
#: ★★ **自创值（`authored`），不是原作数据** —— 原作里**没有**"两个 NPC 主动
#:    凑到一起"的机制：`scr_makecaterpillar` 只做**队友跟主角**，方向是单向的。
#:    用户口径「其他npc一部分也会有相互经常互动的情节」把"经常互动"落成
#:    "会自己走近"，所以才需要一个走近速度。
#: 取 **40 px/s** = 低于原作实测的巡逻速度（maus 型 2px/帧 × 30fps = 60px/s）
#: ⇒ 观感上"凑过去"比"巡逻经过"慢一档，不抢戏，也不会在到达前抖动。
BOND_APPROACH_SPEED = 40.0


def _safe_dt(dt):
    """把 dt 钳进 `[0, MAX_DT]`（非数 ⇒ 0）。**与 `soul_entity` 同一套写法。**"""
    try:
        v = float(dt)
    except (TypeError, ValueError):
        return 0.0
    if v != v or v < 0.0:          # NaN / 负数
        return 0.0
    return v if v <= MAX_DT else MAX_DT


def _movetowards(cur, target, step):
    """`scr_movetowards` 的等价物：**一步之内能到就精确落到 target**。

    ⚠️ "精确落到" 这一条是**必须**的，不是优化：原作 patrol 的换向判据是
    `if (npc.x == target)` —— **浮点精确相等**。若我们停在 target±0.001，
    换向判据永远不成立，NPC 会卡在端点不动（而且不报错）。
    """
    d = target - cur
    if step <= 0.0 or abs(d) <= step:
        return target
    return cur + (step if d > 0 else -step)


def _clamp(v, lo, hi):
    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo
    if lo is not None and v < lo:
        return lo
    if hi is not None and v > hi:
        return hi
    return v


def _facing_for(dx):
    """**纯 x 位移** → 四向朝向（`scr_flip("x")` 在我们这套四向精灵里的等价物）。

    ⚠️ 只用于"沿一条线来回走"的 `patrol` / `pace`。要判"看着另一个人"请用
    `_facing_between(dx, dy)` —— 两人**竖直**相对时 `dx == 0`，本函数返回 `None`，
    调用方若退化成 `'down'`，就会出现"上下两人都朝下看"的错。
    """
    if dx > 0:
        return 'right'
    if dx < 0:
        return 'left'
    return None


def _facing_between(dx, dy):
    """`(dx, dy)` → 四向朝向（**取占优的那一轴**）。

    原作 GMS2 的 `image_angle` 是连续角，按 45° 分档；我们只有四向精灵，
    ⇒ 用"|dx| ≥ |dy| 就看左右，否则看上下"来分档，等价于 45° 分界。
    """
    if dx == 0.0 and dy == 0.0:
        return None
    if abs(dx) >= abs(dy):
        return 'right' if dx > 0 else 'left'
    return 'down' if dy > 0 else 'up'


# ================================================================ 站位
class Placement(object):
    """一个 NPC 的站位定义（静态，不含运行时状态）。"""

    __slots__ = ('npc_id', 'scene', 'x', 'y', 'facing', 'mode', 'patrol', 'pace',
                 'room_id', 'room_raw', 'source', 'evidence', 'why', 'extra')

    def __init__(self, npc_id, scene, x=0.0, y=0.0, facing=FACE_DOWN, mode=MODE_STAND,
                 patrol=None, pace=None, room_id=None, room_raw=None,
                 source=SRC_AUTHORED, evidence='', why='', extra=None):
        self.npc_id = npc_id
        self.scene = scene
        self.x = float(x or 0.0)
        self.y = float(y or 0.0)
        self.facing = facing if facing in FACINGS else FACE_DOWN
        self.mode = mode if mode in MODE_KINDS else MODE_STAND
        self.patrol = dict(patrol) if isinstance(patrol, dict) else None
        self.pace = dict(pace) if isinstance(pace, dict) else None
        self.room_id = room_id
        self.room_raw = room_raw
        self.source = source if source in SOURCE_KINDS else SRC_AUTHORED
        self.evidence = evidence or ''
        self.why = why or ''
        self.extra = dict(extra) if isinstance(extra, dict) else {}

    def to_dict(self):
        return collections.OrderedDict((
            ('id', self.npc_id), ('scene', self.scene), ('pos', [self.x, self.y]),
            ('facing', self.facing), ('mode', self.mode),
            ('patrol', self.patrol), ('pace', self.pace),
            ('room_id', self.room_id), ('room_raw', self.room_raw),
            ('source', self.source), ('evidence', self.evidence), ('why', self.why),
        ))

    def __repr__(self):
        return '<Placement %s %s %s %s>' % (self.npc_id, self.scene, self.mode, self.source)


def placement_from_dict(d):
    if not isinstance(d, dict) or not d.get('id'):
        raise ValueError('Placement 需要至少一个 id 字段')
    pos = d.get('pos') or (0, 0)
    if not isinstance(pos, (list, tuple)) or len(pos) < 2:
        pos = (0, 0)
    return Placement(
        npc_id=d['id'], scene=d.get('scene'), x=pos[0], y=pos[1],
        facing=d.get('facing', FACE_DOWN), mode=d.get('mode', MODE_STAND),
        patrol=d.get('patrol'), pace=d.get('pace'),
        room_id=d.get('room_id'), room_raw=d.get('room_raw'),
        source=d.get('source', SRC_AUTHORED),
        evidence=d.get('evidence', ''), why=d.get('why', ''),
    )


# ================================================================ 房间盒
class WanderBox(object):
    """NPC 能活动的那块矩形（房间四边各留 `margin`）。

    ⚠️ 拿不到房间几何时**不造假** —— `None` 表示"未知房间"，此时
    `Body` 不做钳制（沿用第44轮口径：缺项按"未知"退化，绝不伪造 640x480）。
    """

    __slots__ = ('x0', 'y0', 'x1', 'y1', 'w', 'h', 'name')

    def __init__(self, w, h, margin=WANDER_MARGIN, name=''):
        self.w = float(w)
        self.h = float(h)
        self.name = name or ''
        m = float(margin)
        self.x0 = min(m, self.w / 2.0)
        self.y0 = min(m, self.h / 2.0)
        self.x1 = max(self.x0, self.w - m)
        self.y1 = max(self.y0, self.h - m)

    def clamp(self, x, y):
        return (_clamp(x, self.x0, self.x1), _clamp(y, self.y0, self.y1))

    def contains(self, x, y):
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1

    def __repr__(self):
        return '<WanderBox %s %gx%g [%g..%g, %g..%g]>' % (
            self.name or '?', self.w, self.h, self.x0, self.x1, self.y0, self.y1)


def load_geometry(scene_dir=None):
    """读 `assets/scenes/_room_geometry.json` → `{'<章>:<room_id>': {w,h,name}}`。

    读不到 ⇒ 返回 `{}`（**不抛**：站位系统拿不到几何也应当能把人放出来，
    只是不钳制）。
    """
    path = geometry_path(scene_dir)
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            raw = json.load(fh)
        rooms = raw.get('rooms')
        return rooms if isinstance(rooms, dict) else {}
    except Exception as e:
        _log.warning('房间几何读取失败 %s（站位不钳制）: %s', path, e)
        return {}


def _default_root():
    # 本文件位于 ralsei_pet/modules/ ⇒ assets 在上一级
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def placement_path(root=None):
    return os.path.join(root or _default_root(), 'assets', 'npc', PLACEMENT_FILENAME)


def geometry_path(scene_dir=None):
    base = scene_dir or os.path.join(_default_root(), 'assets', 'scenes')
    return os.path.join(base, GEOMETRY_FILENAME)


def geometry_key(scene_id, room_id):
    """`('ch2.my_castle_town.dw_castle_castle', 71)` → `'ch2:71'`（与几何表键一致）。"""
    if not isinstance(scene_id, str) or room_id is None:
        return None
    ch = scene_id.split('.')[0]
    if not ch:
        return None
    return '%s:%s' % (ch, room_id)


# ================================================================ 运行时：身体
class Body(object):
    """一个 NPC 的运行时位置（三个模式：`stand` / `patrol` / `pace`）。

    ★ 速度单位：`speed` 存的是 **px/秒**；原作脚本里的速度是 **px/帧**（GMS2FPS=30），
      换算在 `from_placement()` 里一次做完（`speed_frames * GAME_FPS`）。
      ⚠️ 不换算的话 NPC 会慢 30 倍（而且"看着像没动"，不会报错）。
    """

    __slots__ = ('npc_id', 'scene', 'x', 'y', 'facing', 'mode',
                 'xstart', 'ystart', 'target', 'alt', 'speed', 'max_speed',
                 'cur_speed', 'accel', 'y_target', 'clamp_x', 'box', 'scale',
                 'offset', 'end')

    def __init__(self, npc_id, scene=None, x=0.0, y=0.0, facing=FACE_DOWN,
                 mode=MODE_STAND, speed=0.0, box=None, scale=1.0,
                 offset=None, end=None, clamp_x=None, accel=PACE_ACCEL):
        self.npc_id = npc_id
        self.scene = scene
        self.x = float(x)
        self.y = float(y)
        self.facing = facing if facing in FACINGS else FACE_DOWN
        self.mode = mode if mode in MODE_KINDS else MODE_STAND
        self.xstart = float(x)
        self.ystart = float(y)
        self.box = box
        self.scale = float(scale) if scale else 1.0
        self.speed = float(speed)            # px/s（patrol 用；pace 里是速度上限）
        self.max_speed = float(speed)
        self.cur_speed = 0.0                 # 仅 pace 用
        self.accel = float(accel)
        self.offset = float(offset) if offset is not None else None
        self.end = float(end) if end is not None else None
        self.clamp_x = float(clamp_x) if clamp_x is not None else None
        self.target = None
        self.y_target = None
        self.alt = 0
        if self.mode == MODE_PATROL and self.offset is None:
            # ⚠️ 直接构造（不走 `from_placement`）时没有 `offset` ⇒ 视作 0：
            #    巡逻退化成站立，**而不是**每帧在同一个点上翻来覆去（那会白刷 alt）。
            self.offset = 0.0
        if self.box is not None:
            self.x, self.y = self.box.clamp(self.x, self.y)
            self.xstart, self.ystart = self.x, self.y
        if self.mode == MODE_PATROL:
            self.target = self._patrol_target()
        elif self.mode == MODE_PACE:
            self.target = self.end if self.end is not None else self.xstart
            self.target = self._clamp_to_box_x(self.target)
            # ★ y 的落点必须与**去 / 回程**一致：去程（target 远离 xstart）上浮、
            #   回程落回出生高度。原写法在这里**恒取 `ystart`** ⇒ 第一趟不浮、
            #   从第二趟起才浮（与 `_step_pace` 端点处同一判据算出相反结论）。
            #   原作 `ch2.obj_npc_king_Step_0.gml` 的第一分支就是 `x < end ⇒ y -= 4`
            #   ⇒ **从第一帧起就上浮**才是原样。
            self.y_target = (self.ystart - ORIGINAL_PACE_RISE
                             if self.target != self.xstart else self.ystart)

    # -- 构造
    @classmethod
    def from_placement(cls, pl, box=None, scale=1.0):
        """按站位定义造一个身体（含"每帧 → 每秒"的速度换算）。"""
        mode = pl.mode
        speed = 0.0
        offset = end = clamp_x = None
        if mode == MODE_PATROL and pl.patrol:
            offset = pl.patrol.get('offset', 0)
            speed = float(pl.patrol.get('speed', 1)) * GAME_FPS
        elif mode == MODE_PACE and pl.pace:
            end = pl.pace.get('end')
            clamp_x = pl.pace.get('clamp')
            speed = float(pl.pace.get('speed', 1)) * GAME_FPS
        return cls(npc_id=pl.npc_id, scene=pl.scene, x=pl.x, y=pl.y, facing=pl.facing,
                   mode=mode, speed=speed, box=box, scale=scale,
                   offset=offset, end=end, clamp_x=clamp_x)

    # -- 内部
    def _clamp_to_box_x(self, x):
        if self.box is None:
            return x
        return _clamp(x, self.box.x0, self.box.x1)

    def _patrol_target(self):
        """原作巡逻的换向式：`(alt % 2) ? (xstart + offset) : xstart`。"""
        span = (self.xstart + self.offset) if (self.alt % 2) == 1 else self.xstart
        span = self._clamp_to_box_x(span)
        if self.clamp_x is not None:
            span = min(span, self.clamp_x)
        return span

    def _flip(self, new_target):
        f = _facing_for(new_target - self.x)
        if f is not None:
            self.facing = f

    # -- 推进
    def step(self, dt):
        """推进一帧。返回 `True` = 位置或朝向有变化。"""
        dt = _safe_dt(dt)
        if dt <= 0.0 or self.mode == MODE_STAND:
            return False
        if self.mode == MODE_PATROL:
            return self._step_patrol(dt)
        return self._step_pace(dt)

    def _step_patrol(self, dt):
        if self.target is None:
            self.target = self._patrol_target()
        # ★ 端点判据：原作是 `if (npc.x == npc_target)` 的**精确相等**。
        #   `_movetowards` 保证到达时精确落到 target ⇒ 这条判据成立。
        if self.x == self.target:
            self.alt += 1
            nxt = self._patrol_target()
            if nxt == self.target:
                # 段长 0（`offset == 0` 或钳制把端点压平了）⇒ 不退化成每帧空转。
                self.alt -= 1
                return False
            self.target = nxt
            self._flip(self.target)
        step = self.speed * dt * self.scale
        new_x = _movetowards(self.x, self.target, step)
        if new_x != self.x:
            f = _facing_for(new_x - self.x)
            if f is not None:
                self.facing = f
        self.x = new_x
        if self.box is not None:
            self.x, self.y = self.box.clamp(self.x, self.y)
        return True

    def _step_pace(self, dt):
        """概括自原作 King 的写法：区间 + 软起停 + y 起伏 + 硬钳制。"""
        if self.target is None:
            return False
        d = self.target - self.x
        if d == 0.0:
            # 到端点：换向 + 软刹一档（原作 `hspeed -= 1` 的形状）
            self.target = self.xstart if self.target != self.xstart else (
                self.end if self.end is not None else self.xstart)
            self.target = self._clamp_to_box_x(self.target)
            self.cur_speed = max(0.0, self.cur_speed - self.accel)
            self._flip(self.target)
            d = self.target - self.x
            # y 的落点：去程上浮、回程落回出生高度（原作 `ystart - 60` / `ystart`）
            self.y_target = (self.ystart - ORIGINAL_PACE_RISE
                             if self.target != self.xstart else self.ystart)
            if d == 0.0:
                # 段长 0（`end == xstart`，或钳制把两端压平）⇒ 本帧**没动**。
                # ⚠️ 原来这里 `return True`：会每帧都声称"动过"，让上层一直重绘，
                #    而位置一动不动 —— 与 `_step_patrol` 的零长度段同一种"白刷"，
                #    那边已改成 `return False`，这里对齐。
                return False
        self.cur_speed = min(self.max_speed, self.cur_speed + self.accel * dt * self.scale)
        if self.cur_speed <= 0.0:
            self.cur_speed = min(self.max_speed, self.accel * dt * self.scale)
        step = self.cur_speed * dt * self.scale
        new_x = _movetowards(self.x, self.target, step)
        if new_x != self.x:
            f = _facing_for(new_x - self.x)
            if f is not None:
                self.facing = f
        self.x = new_x
        if self.y_target is not None:
            self.y = _movetowards(self.y, self.y_target, PACE_Y_SPEED * dt * self.scale)
        if self.clamp_x is not None and self.x > self.clamp_x:
            self.x = self.clamp_x
        if self.box is not None:
            self.x, self.y = self.box.clamp(self.x, self.y)
        return True

    # -- 展示
    def pos(self):
        return (self.x, self.y)

    def describe(self):
        return ('%s@%s (%.1f,%.1f) face=%s mode=%s%s'
                % (self.npc_id, self.scene or '?', self.x, self.y, self.facing,
                   self.mode, ' target=%.1f' % self.target if self.target is not None else ''))

    def __repr__(self):
        return '<Body %s>' % self.describe()


# ================================================================ 编队
class Trail(object):
    """团长走过的位置（**新 → 旧**的环形缓冲）。

    照原作 `obj_caterpillarchara` 的 `remx/remy/facing` 三数组（长度 25）——
    队友不寻路，只是**延迟采样**这条路。
    """

    __slots__ = ('length', '_xs', '_ys')

    def __init__(self, length=ORIGINAL_TRAIL_LENGTH, x=0.0, y=0.0):
        self.length = max(1, int(length))
        self._xs = collections.deque([float(x)] * self.length, maxlen=self.length)
        self._ys = collections.deque([float(y)] * self.length, maxlen=self.length)

    def push(self, x, y):
        self._xs.appendleft(float(x))
        self._ys.appendleft(float(y))

    def reset(self, x, y):
        self._xs = collections.deque([float(x)] * self.length, maxlen=self.length)
        self._ys = collections.deque([float(y)] * self.length, maxlen=self.length)

    def sample(self, lag):
        """取 `lag` 帧前的位置（越界取最旧的一帧 —— 不"外推"，不发明位置）。"""
        try:
            i = int(lag)
        except (TypeError, ValueError):
            i = 0
        if i < 0:
            i = 0
        if i >= self.length:
            i = self.length - 1
        return (self._xs[i], self._ys[i])

    def head(self):
        """最新一帧（`sample(0)` 的等价物；用来判"这一帧是不是已经推进去过"）。"""
        return (self._xs[0], self._ys[0])

    def __len__(self):
        return self.length

    def __repr__(self):
        return '<Trail len=%d head=(%.0f,%.0f)>' % (self.length, self._xs[0], self._ys[0])


class PartyRig(object):
    """主角团编队 —— 照抄原作 caterpillar 的"落后帧数"语义。

    * `members` / `leader` / `lag` 来自 `_placement.json`（`lag = 12 + slot*12`）；
    * `anchor` 是**当前主控角色**：原作恒为 `obj_mainchara`（Kris），
      桌面上主控是 Ralsei（宠物本体）⇒ 允许调用方换人，**不许写死**。
    * `trail` 必须是由调用方按 `anchor` 的真实位置推进的 `Trail`。
    """

    __slots__ = ('members', 'leader', 'lag', 'anchor', 'lateral', 'source')

    def __init__(self, members, leader=None, lag=None, anchor=None,
                 lateral=PARTY_LATERAL, source=SRC_ORIGINAL):
        self.members = tuple(members or ())
        if not self.members:
            raise ValueError('PartyRig 至少要有一个成员')
        self.leader = leader if leader in self.members else self.members[0]
        self.anchor = anchor or self.leader
        if anchor is not None and anchor not in self.members:
            # 锚必须是团员（否则"锚"与队形无关，那条轨迹没有意义）
            raise ValueError('anchor %r 不在成员 %r 里' % (anchor, self.members))
        if lag and len(lag) == len(self.members):
            self.lag = dict(zip(self.members, [int(v) for v in lag]))
        else:
            self.lag = dict((m, ORIGINAL_PARTY_LAG_BASE + i * ORIGINAL_PARTY_LAG_STEP)
                            for i, m in enumerate(self.members))
        self.lateral = tuple(lateral) if lateral else ()
        self.source = source

    def __len__(self):
        return len(self.members)

    def lag_of(self, npc_id):
        return self.lag.get(npc_id)

    def slot_of(self, npc_id):
        try:
            return self.members.index(npc_id)
        except ValueError:
            return -1

    def lateral_of(self, npc_id):
        i = self.slot_of(npc_id)
        if i < 0 or not self.lateral:
            return 0.0
        return self.lateral[i % len(self.lateral)]

    def order(self):
        """按落后帧数**升序**（跟在最前面的人排前面）。"""
        return sorted(self.members, key=lambda m: self.lag.get(m, 0))

    def place(self, trail, anchor_pos=None):
        """给出每个成员的落点 `{npc_id: (x, y)}`。

        `anchor_pos` 给了就保证"团长此刻的位置"在轨迹头上 —— 但**只在它还没进去时**
        才压一次。⚠️ 无条件 push 会**重复入队**：调用方本来就每帧 push 一次，
        再压一遍就等于把整条轨迹整体挪后一帧 ⇒ 队友的落后量**少一帧**
        （实测 lag=24 只落后 132px 而不是 144px，且"看不见"）。
        """
        if anchor_pos is not None:
            ap = (float(anchor_pos[0]), float(anchor_pos[1]))
            if trail.head() != ap:
                trail.push(ap[0], ap[1])
        out = collections.OrderedDict()
        for m in self.members:
            x, y = trail.sample(self.lag.get(m, 0))
            lat = self.lateral_of(m)
            if lat:
                # ★ 错开量加在 **y（垂直于"沿路排队"的那条轴）** 上，不是 x。
                #   为什么：y 上的落后量才是"队列间距"（`lag × 每帧位移`），
                #   把 lateral 也塞进 x 会**污染这条可测的量**（12 帧的落后会被
                #   ±6px 的错位搅成 78px，判据就再也断不准）。
                #   加在 y 上还顺带得到"一人靠里一人靠外"的纵深观感 ——
                #   原作靠 `halign/valign` 做的是同一件事（几像素级微调）。
                y += lat
            out[m] = (x, y)
        return out

    def describe(self):
        return 'party(%s) leader=%s anchor=%s lag=%s' % (
            '/'.join(self.members), self.leader, self.anchor,
            ','.join('%s:%d' % (m, self.lag[m]) for m in self.members))


# ================================================================ 结对
class Bond(object):
    """一对"经常互动"的 NPC。

    `meet='approach'` ⇒ 两人互相走近，直到距离 ≤ `gap`；
    `meet='face'` ⇒ **不移动**，只把朝向转成看着对方。
    ★ `BOND_SAME_SCENE_ONLY`：两人不在同一场景时**一律不生效**（不隔空凑）。
    """

    __slots__ = ('a', 'b', 'kind', 'meet', 'gap', 'source', 'evidence', 'note')

    def __init__(self, a, b, kind='friend', meet=MEET_FACE, gap=DEFAULT_BOND_GAP,
                 source=SRC_AUTHORED, evidence='', note=''):
        self.a = a
        self.b = b
        self.kind = kind if kind in BOND_KINDS else 'friend'
        self.meet = meet if meet in MEET_KINDS else MEET_FACE
        self.gap = float(gap)
        self.source = source if source in SOURCE_KINDS else SRC_AUTHORED
        self.evidence = evidence or ''
        self.note = note or ''

    def pair(self):
        return (self.a, self.b)

    def involves(self, npc_id):
        return npc_id in (self.a, self.b)

    def other(self, npc_id):
        if npc_id == self.a:
            return self.b
        if npc_id == self.b:
            return self.a
        return None

    def target_point(self, mover, other):
        """`approach` 时 mover 该往哪走（保持 gap 距离，从 other 那边看过来）。"""
        dx = mover[0] - other[0]
        dy = mover[1] - other[1]
        d = math.hypot(dx, dy)
        if d <= 0.0 or d <= self.gap:
            return (float(mover[0]), float(mover[1]))
        k = self.gap / d
        return (other[0] + dx * k, other[1] + dy * k)

    def resolve(self, pos_a, pos_b, dt, speed=0.0, box=None, scale=1.0):
        """推进一次结对动作。

        返回 `{'a': (x,y), 'b': (x,y), 'facing_a': ..., 'facing_b': ..., 'moved': bool}`。
        `meet='face'` 时位置原样返回（只给朝向）；`approach` 时两人各走一半。
        """
        ax, ay = float(pos_a[0]), float(pos_a[1])
        bx, by = float(pos_b[0]), float(pos_b[1])
        facing_a = facing_b = None
        moved = False
        if self.meet == MEET_APPROACH:
            dt = _safe_dt(dt)
            step = float(speed) * dt * float(scale or 1.0)
            if step > 0.0:
                ta = self.target_point((ax, ay), (bx, by))
                tb = self.target_point((bx, by), (ax, ay))
                # `rem` = 距离目标还差多少（= 当前间距 − gap）；两边对称相同。
                rem = math.hypot(ta[0] - ax, ta[1] - ay)
                if rem > 0.0:
                    # ★ 每人只走**超出量的一半**。原写法两人都按"整份超出量"迈步
                    #   ⇒ 一帧就把间距压到 gap 以下、下一帧又互相推开 ⇒ 在 gap 附近
                    #   **永久抖动**（实测 200 帧后停在 68.00 而不是 72）。
                    #   取一半之后，`rem ≤ 2×step` 那一帧会**精确**落到 gap 并停住。
                    half = min(step, rem * 0.5)
                    ax2 = ax + (ta[0] - ax) / rem * half
                    ay2 = ay + (ta[1] - ay) / rem * half
                    bx2 = bx + (tb[0] - bx) / rem * half
                    by2 = by + (tb[1] - by) / rem * half
                    moved = (ax2, ay2, bx2, by2) != (ax, ay, bx, by)
                    ax, ay, bx, by = ax2, ay2, bx2, by2
        # 朝向：看着对方（两种 meet 都做）
        facing_a = _facing_between(bx - ax, by - ay) or 'down'
        facing_b = _facing_between(ax - bx, ay - by) or 'down'
        if box is not None:
            ax, ay = box.clamp(ax, ay)
            bx, by = box.clamp(bx, by)
        return {'a': (ax, ay), 'b': (bx, by),
                'facing_a': facing_a, 'facing_b': facing_b, 'moved': moved}

    def describe(self):
        return '%s<->%s %s/%s gap=%g' % (self.a, self.b, self.kind, self.meet, self.gap)

    def __repr__(self):
        return '<Bond %s>' % self.describe()


def bonds_from_dicts(items, group_members=None):
    """把 `_placement.json` 的 bonds 列表转成 `Bond`，并**去掉重复登记**。

    ★ 一对 `(a,b)` 只允许一条（`a/b` 互换视为同一对）：运行时"凑到一起"的动作
      只有一种，两条 bond 会给出两个 `gap`，听谁的没有答案（第45轮"多解闸"教训）。
      这里**保留先出现的那条**并记 warning（生成器那边是硬失败，这里只兜底）。
    """
    out = []
    seen = {}
    for d in (items or ()):
        if not isinstance(d, dict):
            continue
        a, b = d.get('a'), d.get('b')
        if not a or not b or a == b:
            _log.warning('跳过非法结对 %r', d)
            continue
        key = tuple(sorted((a, b)))
        if key in seen:
            _log.warning('结对 %s 重复登记（已有 kind=%s，本次 kind=%s）⇒ 忽略后者',
                         key, seen[key], d.get('kind'))
            continue
        seen[key] = d.get('kind')
        out.append(Bond(a=a, b=b, kind=d.get('kind', 'friend'),
                        meet=d.get('meet', MEET_FACE),
                        gap=d.get('gap', DEFAULT_BOND_GAP),
                        source=d.get('source', SRC_AUTHORED),
                        evidence=d.get('evidence', ''), note=d.get('note', '')))
    return out


# ================================================================ 整本站位簿
class PlacementBook(object):
    """站位 / 编队 / 结对 / 桌面白名单的只读视图。"""

    def __init__(self, placements=(), groups=(), bonds=(), unplaced=None,
                 desktop_allowed=(), hubs=None, rules=None, geometry=None):
        self._by_id = collections.OrderedDict()
        for p in placements:
            self._by_id[p.npc_id] = p
        self.unplaced = dict(unplaced or {})
        self.groups = list(groups or ())
        self.bonds = list(bonds or ())
        self.desktop_allowed_ids = tuple(desktop_allowed or ())
        self.hubs = dict(hubs or {})
        self.rules = dict(rules or {})
        self.geometry = geometry if isinstance(geometry, dict) else {}

    # -- 查询
    def __len__(self):
        return len(self._by_id)

    def __contains__(self, npc_id):
        return npc_id in self._by_id

    def ids(self):
        return list(self._by_id.keys())

    def all(self):
        return list(self._by_id.values())

    def get(self, npc_id):
        return self._by_id.get(npc_id)

    def scene_of(self, npc_id):
        p = self.get(npc_id)
        return p.scene if p is not None else None

    def hub_of(self, chapter):
        return self.hubs.get(chapter)

    def group_of(self, npc_id):
        for g in self.groups:
            if npc_id in (g.members if hasattr(g, 'members') else g.get('members', ())):
                return g
        return None

    def bonds_of(self, npc_id):
        return [b for b in self.bonds if b.involves(npc_id)]

    def same_scene(self, a, b):
        sa, sb = self.scene_of(a), self.scene_of(b)
        return bool(sa) and sa == sb

    def desktop_allowed(self, npc_id):
        return npc_id in self.desktop_allowed_ids

    # -- 几何
    def room_wh(self, npc_id):
        p = self.get(npc_id)
        if p is None:
            return None
        key = geometry_key(p.scene, p.room_id)
        g = self.geometry.get(key) if key else None
        if not isinstance(g, dict):
            return None
        w, h = g.get('w'), g.get('h')
        if not isinstance(w, (int, float)) or not isinstance(h, (int, float)):
            return None
        if w <= 0 or h <= 0:
            return None
        return (float(w), float(h), g.get('name') or '')

    def box_of(self, npc_id, margin=None):
        """`npc_id` 的活动盒；**拿不到几何 ⇒ `None`**（不伪造尺寸）。"""
        wh = self.room_wh(npc_id)
        if wh is None:
            return None
        m = WANDER_MARGIN if margin is None else margin
        return WanderBox(wh[0], wh[1], margin=m, name=wh[2])

    # -- 构造运行时
    def body_of(self, npc_id, scale=1.0, margin=None):
        p = self.get(npc_id)
        if p is None:
            return None
        return Body.from_placement(p, box=self.box_of(npc_id, margin), scale=scale)

    def initial_bodies(self, ids=None, scale=1.0, margin=None):
        """建出全部（或指定）NPC 的身体，`{npc_id: Body}`。"""
        want = list(ids) if ids else self.ids()
        out = collections.OrderedDict()
        for nid in want:
            b = self.body_of(nid, scale=scale, margin=margin)
            if b is not None:
                out[nid] = b
        return out

    def rig(self, group_id='party', anchor=None):
        """按编队 id 造 `PartyRig`（找不到 ⇒ `None`）。"""
        for g in self.groups:
            members = g.members if hasattr(g, 'members') else g.get('members')
            if not members:
                continue
            gid = g.id if hasattr(g, 'id') else g.get('id')
            if group_id is not None and gid != group_id:
                continue
            leader = g.leader if hasattr(g, 'leader') else g.get('leader')
            lag = g.lag if hasattr(g, 'lag') else g.get('lag')
            return PartyRig(members, leader=leader, lag=lag, anchor=anchor)
        return None

    # -- 展示
    def by_source(self):
        c = collections.Counter(p.source for p in self._by_id.values())
        return dict(c)

    def describe(self):
        return ('PlacementBook %d 人（%s）；未安置 %d；编队 %d；结对 %d；桌面白名单 %s'
                % (len(self._by_id), self.by_source(), len(self.unplaced),
                   len(self.groups), len(self.bonds),
                   '/'.join(self.desktop_allowed_ids) or '（无）'))


def load_placement(root=None, scene_dir=None, with_geometry=True):
    """读 `assets/npc/_placement.json`（+ 房间几何）。

    **读不到 / 解析失败一律返回空簿**，绝不让调用方起不来
    （与 `npc_system.load_registry` / `sprite_loader` 同口径）。
    """
    path = placement_path(root)
    placements, groups, bonds = [], [], []
    unplaced, allowed, hubs, rules = {}, (), {}, {}
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            raw = json.load(fh)
        for d in (raw.get('placement') or []):
            try:
                placements.append(placement_from_dict(d))
            except Exception as e:
                _log.warning('跳过非法站位记录 %r: %s', d, e)
        groups = [g for g in (raw.get('groups') or []) if isinstance(g, dict)]
        bonds = bonds_from_dicts(raw.get('bonds'))
        unplaced = raw.get('unplaced') if isinstance(raw.get('unplaced'), dict) else {}
        desktop = raw.get('desktop') if isinstance(raw.get('desktop'), dict) else {}
        allowed = tuple(desktop.get('allowed') or ())
        hubs = raw.get('hubs') if isinstance(raw.get('hubs'), dict) else {}
        rules = raw.get('rules') if isinstance(raw.get('rules'), dict) else {}
    except Exception as e:
        _log.warning('站位表读取失败 %s（NPC 无站位，功能降级）: %s', path, e)
        return PlacementBook()

    geo = load_geometry(scene_dir) if with_geometry else {}
    return PlacementBook(placements=placements, groups=groups, bonds=bonds,
                         unplaced=unplaced, desktop_allowed=allowed,
                         hubs=hubs, rules=rules, geometry=geo)


# ================================================================ 便捷
def desktop_allowed_ids(book=None):
    """桌面白名单（数据侧镜像；★ 代码侧的单一真源在 `npc_system.DESKTOP_ALLOWED_IDS`）。

    两边必须逐字一致 —— 由 `check56` 断言。
    """
    if book is None:
        book = load_placement()
    return tuple(book.desktop_allowed_ids)


def step_bodies(bodies, dt):
    """一次推进一批身体，返回**真正动过**的 id 列表（给调用方决定要不要重绘）。"""
    moved = []
    for nid, b in (bodies or {}).items():
        try:
            if b.step(dt):
                moved.append(nid)
        except Exception as e:
            _log.debug('NPC %s 游荡推进异常（本帧跳过）: %s', nid, e)
    return moved


#: 空簿（调用方拿它当"没有站位数据"的单例兜底，省得处处置 None 判断）。
EMPTY_BOOK = PlacementBook()
