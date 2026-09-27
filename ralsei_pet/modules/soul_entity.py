# -*- coding: utf-8 -*-
"""SOUL（灵魂）—— 可拖拽 / 可键盘操控 / 可自由出入各场景的互动实体（第55轮）。

用户口径（第55轮原话，逐字要点）
--------------------------------
* 「别换鼠标的样子了，改成可移动的那个灵魂图标，像是原作里那样，**鼠标可拖拽灵魂，
  键盘可操控移动**」
* 「原先和你说的**鼠标附身换成就是这个灵魂的功能**」
  ⇒ 旧行为"Ralsei 帮你移动系统光标"（`main.update_mouse_drag` 里的 `SetCursorPos`）
    **下线**，同一个"帮你移动"的动作改为驱动**灵魂**；
* 「**灵魂也可自由出入各个场景**，相当于这也是一个**有互动的实体**」

★★★ 原作依据（第55轮取证，全文见 `_evidence/original_soul/`）
--------------------------------------------------------------
源：`chapter1_windows\\data.win`，UTMT CLI v0.9.2.0 全量代码导出，蒸馏副本入库。

| 事实 | 出处（逐字） |
|---|---|
| **速度 = 4 像素/帧** | `gml_Object_obj_heart_Create_0.gml`：`global.sp = 4; wspeed = global.sp;` |
| **分轴独立、不归一化** | `Step_0`：`if press_r: px = wspeed` / `if press_u: py = -wspeed` ⇒ 对角线 √2 倍 |
| **常态定格第 0 帧** | `Create_0`：`image_speed = 0;` / `Step_0`：`image_speed = 0; image_index = 0;` |
| **只有受击才闪** | `Step_0`：`if global.inv > 0: image_speed = 0.25` |
| **四向钳制在视口内** | `Step_0`：`x ∈ [0, view+640−sprite_width]`、`y ∈ [0, view+320−sprite_height+boundaryup]` |
| **出生点 = 主角 + (10, 40)** | `gml_GlobalScript_scr_moveheart.gml`：`instance_create(obj_herokris.x + 10, obj_herokris.y + 40, obj_moveheart)` |
| **帧率 30** | `GeneralInfo`（第43轮已实证 `GMS2FPS = 30`） |
| 贴图 16×16 | `spr_heart`（ch1..ch5 md5 完全相同） |

⇒ 本模块把这些**逐条翻译**成产品常量，**不引入原作没有的物理**（没有加速度、没有摩擦、
   没有惯性 —— 原作的 SOUL 是"按键即满速、松键即停"的街机手感）。

三个**本项目取值**（原作没有对应物，必须标注，不许冒充原作）
------------------------------------------------------------
1. `DISPLAY_SCALE = 3` —— 原作 SOUL 在 640×480 视口里是 16×16；桌面上 16×16 太小，
   按项目既有口径（`scene_scale = 2.0`、角色 `scale_factor = 2.0`）取 3 倍 = **48×48 屏幕像素**。
2. `MAX_DT = 0.1` —— 掉帧/休眠唤醒时一帧 `dt` 可能很大，不钳会让灵魂"瞬移"。
   原作是定帧不变量，不面对这个输入 ⇒ 这是产品侧的必要防御。
3. `SoulBookmarks` —— 「自由出入各场景」的落地：**灵魂在每个场景各记一个位置**，
   回来时回到原处。原作没有跨房间的灵魂记忆（战斗结束就销毁），这是产品扩展。

零依赖纪律（与 `scene_camera` / `npc_system` 同源）
---------------------------------------------------
只允许模块顶部 `import logging / math`。**禁 import Qt、禁 import 任何项目内模块**
（`main.py` 在 import 期就会拉起本模块；回头 import 项目内模块会接上初始化环 ——
  本项目已踩过 4 次，见 `scene_system` 的模块 docstring）。
内部函数**不许**再 import（回归锁用 AST 强制）。
"""
import logging
import math

try:  # 项目内统一 logger；模块外独立导入时降级
    from logger_utils import get_logger
    _log = get_logger(__name__)
except ImportError:
    _log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

# ---------------------------------------------------------------- 原作常量

#: 原作 `spr_heart` 的逻辑尺寸（16×16）。
LOGICAL_SIZE = (16, 16)

#: ★ 本项目取值（非原作）：桌面上把灵魂画成 3 倍大小 = 48×48 屏幕像素。
DISPLAY_SCALE = 3

#: 原作 `global.sp = 4`（像素/帧）。
SPEED_PX = 4.0

#: 原作 `GMS2FPS = 30`（第43轮实证）。
FRAME_HZ = 30

#: 原作 `Step_0` 的受击闪烁速度。
HIT_IMAGE_SPEED = 0.25

#: 原作常态：定格第 0 帧。
IDLE_IMAGE_INDEX = 0

#: 原作出生偏移 `scr_moveheart`：主角 + (10, 40)（**逻辑**像素）。
SPAWN_OFFSET = (10, 40)

#: ★ 本项目取值（非原作）：单帧 `dt` 上限（秒）。掉帧时不瞬移。
MAX_DT = 0.1

#: 键盘键名 → 方向。**只有方向键**。
#:
#: ⚠️ 为什么**不做** WASD：`S` 已经是道具菜单键（裸 S，见 `main.keyPressEvent`），
#:    `W`/`A`/`D` 将来也可能被占；"一个键两个意思"是本项目反复踩过的坑。
#:    方向键在本项目里**完全没人用**（全仓只有 `dialogue_ui` 的输入框），
#:    所以拿来做灵魂的操控键是零冲突的。
DIRECTION_KEYS = {
    'left': 'left', 'arrow_left': 'left', 'arrowleft': 'left',
    'right': 'right', 'arrow_right': 'right', 'arrowright': 'right',
    'up': 'up', 'arrow_up': 'up', 'arrowup': 'up',
    'down': 'down', 'arrow_down': 'down', 'arrowdown': 'down',
}

#: 方向 → 单位向量（**分轴独立**，不归一化 —— 原作就是分轴赋值）。
_DIR_VEC = {'left': (-1, 0), 'right': (1, 0), 'up': (0, -1), 'down': (0, 1)}


def normalize_key(name):
    """键名 → `'left' / 'right' / 'up' / 'down'`；认不出返回 `None`（**不猜**）。"""
    if not isinstance(name, str):
        return None
    return DIRECTION_KEYS.get(name.strip().lower())


class SoulGate(object):
    """灵魂的"能不能进这个世界"判定结果（形状与 `npc_system.GateResult` 对齐）。

    刻意**不 import** `npc_system`：本模块零依赖，而灵魂的答案恒为"能"
    —— 这正是与 NPC 门控的**结构性差别**（见 `soul_can_enter`）。
    """

    __slots__ = ('ok', 'reason', 'detail')

    def __init__(self, ok, reason='ok', detail=''):
        self.ok = bool(ok)
        self.reason = reason
        self.detail = detail

    def __bool__(self):
        return self.ok

    def __repr__(self):
        return '<SoulGate %s %s>' % ('OK' if self.ok else 'DENY', self.reason)


#: 灵魂门控的**唯一**原因码 —— 灵魂没有"不能去"的世界。
SOUL_REASON_FREE = 'soul_free'


def soul_can_enter(world, scene_id=None, chapters=None):
    """灵魂能否进入 `world`（`'light'` / `'dark'`）的 `scene_id`。

    ★★★ **恒为 True** —— 这就是用户要的「灵魂可自由出入各个场景」。

    为什么敢恒真（而不是"又一个没在守的判据"）：这条判据**不是**守护灵魂，
    它是**对照物**：`npc_system.world_gate` 会对同一个 (world, scene_id) 给出
    DENY（暗世界不属自己登记的章 / 光世界要球 …），而灵魂永远 OK。
    回归锁 `check55` 的 S 段用**同一组输入**同时喂两个函数，
    断言"NPC 被拒而灵魂被放行"（正/负控制成对）—— 若哪天有人给灵魂加了门控，
    这条立刻报红。

    :param world: `'light'` / `'dark'` / 其它（灵魂对未知世界也放行）。
    :param scene_id: 场景 id（灵魂不看它）。
    :param chapters: 兼容签名用的"登记章"（灵魂不看它）。
    """
    return SoulGate(True, SOUL_REASON_FREE, '灵魂不受场景门控（world=%r scene=%r）'
                     % (world, scene_id))


class SoulState(object):
    """灵魂的运行时状态（无 Qt、无 IO，可单测）。

    坐标系：**屏幕像素**（左上角为窗口左上角，位置 = 窗口左上角的屏幕坐标）。
    速度按 `scale` 换算：`速度(px/s) = SPEED_PX × FRAME_HZ × scale`
    （`scale = 1` 时就是原作的 4 像素/帧 × 30 帧/秒 = 120 px/s）。
    """

    __slots__ = ('x', 'y', 'vx', 'vy', 'scale',
                 '_pressed', '_drag', '_drag_point', '_blink')

    def __init__(self, x=0.0, y=0.0, scale=DISPLAY_SCALE):
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        try:
            s = float(scale)
        except (TypeError, ValueError):
            s = DISPLAY_SCALE
        self.scale = s if s > 0 else 1.0
        self._pressed = set()
        self._drag = None          #: 拖拽中 = 抓取点相对灵魂左上角的偏移 (dx, dy)
        self._drag_point = None
        self._blink = 0.0          #: 受击闪烁剩余秒数

    # ------------------------------------------------------------ 几何
    @property
    def size(self):
        """灵魂的屏幕尺寸 `(w, h)`。"""
        return (int(round(LOGICAL_SIZE[0] * self.scale)),
                int(round(LOGICAL_SIZE[1] * self.scale)))

    @property
    def speed_per_sec(self):
        """满速（屏幕像素/秒）—— 原作的 4 px/帧 按 30fps 与显示倍率换算。"""
        return SPEED_PX * FRAME_HZ * self.scale

    def center(self):
        w, h = self.size
        return (self.x + w / 2.0, self.y + h / 2.0)

    def rect(self):
        w, h = self.size
        return (self.x, self.y, self.x + w, self.y + h)

    @property
    def is_dragging(self):
        return self._drag is not None

    @property
    def blinking(self):
        """是否正在"受击闪烁"（原作 `global.inv > 0`）。"""
        return self._blink > 0.0

    def image_index(self):
        """当前该画第几帧 —— 常态恒 0，闪烁期间在 0/1 之间按原作速度跳。"""
        if not self.blinking:
            return IDLE_IMAGE_INDEX
        # 累计相位 / 帧时长；HIT_IMAGE_SPEED = 0.25 帧/帧 ⇒ 每 4 帧换一次
        phase = self._blink * FRAME_HZ * HIT_IMAGE_SPEED
        return int(phase) % 2

    # ------------------------------------------------------------ 键盘
    def press(self, key):
        """按下方向键。返回 True 表示"这是一次新按下"（自动重复不算）。"""
        d = normalize_key(key)
        if d is None:
            return False
        if d in self._pressed:
            return False
        self._pressed.add(d)
        return True

    def release(self, key):
        """松开方向键。返回 True 表示"确实松掉了一个按住的键"。"""
        d = normalize_key(key)
        if d is None or d not in self._pressed:
            return False
        self._pressed.discard(d)
        return True

    def clear_keys(self):
        """清空按住的键（失焦/隐藏时必须调 —— 否则灵魂会一直朝一个方向飞）。"""
        n = len(self._pressed)
        self._pressed.clear()
        return n

    def pressed(self):
        return tuple(sorted(self._pressed))

    def direction(self):
        """当前方向 `(dx, dy)`（各取 -1/0/1；**分轴独立**，对角线不归一化）。"""
        dx = dy = 0
        if 'left' in self._pressed and 'right' not in self._pressed:
            dx = -1
        elif 'right' in self._pressed and 'left' not in self._pressed:
            dx = 1
        if 'up' in self._pressed and 'down' not in self._pressed:
            dy = -1
        elif 'down' in self._pressed and 'up' not in self._pressed:
            dy = 1
        return (dx, dy)

    # ------------------------------------------------------------ 推进
    def step(self, dt):
        """按 `dt` 秒推进。返回本次位移 `(dx, dy)`（屏幕像素）。

        三条与之一一对应的原作事实：
        1. **松键即停**（`px/py` 每帧都从 0 重新赋值）⇒ 这里没有任何残速；
        2. **按键即满速**（没有加速度曲线）；
        3. **分轴独立** ⇒ 对角线 √2 倍（`_DIR_VEC` + 不归一化）。
        """
        if self._drag is not None:
            # 拖拽中：位置由鼠标直接决定，速度归零（"抓住"就是抓住）。
            self.vx = self.vy = 0.0
            return (0.0, 0.0)
        dx, dy = self.direction()
        # —— 本项目防御（非原作）：dt 非法/过大 ⇒ 钳到 MAX_DT，避免瞬移。
        try:
            d = float(dt)
        except (TypeError, ValueError):
            d = 0.0
        if not math.isfinite(d) or d <= 0.0:
            self.vx = self.vy = 0.0
        else:
            d = min(d, MAX_DT)
        if dx == 0 and dy == 0:
            self.vx = self.vy = 0.0
            return (0.0, 0.0)
        v = self.speed_per_sec
        self.vx = dx * v
        self.vy = dy * v
        mx = self.vx * d
        my = self.vy * d
        self.x += mx
        self.y += my
        return (mx, my)

    # ------------------------------------------------------------ 拖拽
    def begin_drag(self, point_x, point_y):
        """开始拖拽：`point_*` = 鼠标的屏幕坐标。记录抓取偏移（鼠标抓住哪一点）。"""
        self._drag = (float(point_x) - self.x, float(point_y) - self.y)
        self._drag_point = (float(point_x), float(point_y))
        self.vx = self.vy = 0.0
        return True

    def drag_to(self, point_x, point_y):
        """拖到 `point_*`（屏幕坐标）—— 位移 = 鼠标位移（**不重算抓取点**，不抖）。"""
        if self._drag is None:
            return False
        ox, oy = self._drag
        self.x = float(point_x) - ox
        self.y = float(point_y) - oy
        self._drag_point = (float(point_x), float(point_y))
        return True

    def end_drag(self):
        """结束拖拽。返回"这次是点击还是拖拽"：`True` = 纯点击（没怎么动）。"""
        if self._drag is None:
            return False
        was_click = False
        if self._drag_point is not None:
            w, h = self.size
            dx = abs(self.x + self._drag[0] - self._drag_point[0])
            dy = abs(self.y + self._drag[1] - self._drag_point[1])
            was_click = (dx <= max(2, w * 0.15) and dy <= max(2, h * 0.15))
        self._drag = None
        self._drag_point = None
        return was_click

    # ------------------------------------------------------------ 钳制 / 闪烁
    def clamp_to(self, bounds):
        """把灵魂整体钳进 `bounds = (l, t, r, b)`（屏幕像素）。

        照抄原作 `Step_0` 的钳制形状：钳的是**左上角**，上界是
        `视口右下 − sprite 尺寸` ⇒ **整只灵魂永远在框内**（不会只露一半）。
        `bounds` 非法 / 比灵魂还小 ⇒ 钳到左上角（不抛、不返回 None）。
        """
        if not bounds or len(bounds) != 4:
            return (self.x, self.y)
        try:
            l, t, r, b = [float(v) for v in bounds]
        except (TypeError, ValueError):
            return (self.x, self.y)
        w, h = self.size
        hi_x = max(l, r - w)
        hi_y = max(t, b - h)
        self.x = min(max(self.x, l), hi_x)
        self.y = min(max(self.y, t), hi_y)
        return (self.x, self.y)

    def hit(self):
        """触发一次"受击闪烁"（原作 `global.inv > 0`）。"""
        self._blink = 1.0
        return True

    def tick_blink(self, dt):
        """推进闪烁计时。返回"本帧闪烁状态是否变了"。"""
        if self._blink <= 0:
            return False
        before = self.image_index()
        try:
            d = float(dt)
        except (TypeError, ValueError):
            d = 0.0
        if not math.isfinite(d) or d < 0:
            d = 0.0
        self._blink = max(0.0, self._blink - min(d, MAX_DT))
        return self.image_index() != before

    def needs_tick(self):
        """是否需要继续按帧推进（决定调用方要不要开 30fps 定时器）。"""
        return bool(self._pressed) or self.is_dragging or self.blinking

    def describe(self):
        """一行中文摘要（日志 / 自省用）。"""
        return ('灵魂 (%.0f, %.0f) %dx%d 速度上限 %.0fpx/s%s%s'
                % (self.x, self.y, self.size[0], self.size[1], self.speed_per_sec,
                   '，按键=%s' % (','.join(self.pressed()),) if self._pressed else '',
                   '，拖拽中' if self.is_dragging else ''))


class SoulBookmarks(object):
    """「灵魂进出各场景」的落地：**每个场景各记一个位置**（归一化比例）。

    为什么存**归一化比例**而不是像素：用户的桌面会换分辨率/插拔副屏；
    存像素会让"回到那个场景"落在屏外，存 `0~1` 的比例则永远落在同一相对位置。

    为什么不做成 `memory_store` 的一部分：那是 **Ralsei 的**记忆（对话/成长），
    灵魂的坐标是**界面状态**（跟窗口位置同级），混进去会污染"记忆"的语义，
    也会让记忆文件的写入频率被鼠标拖拽带着走。
    """

    def __init__(self, screen_w=None, screen_h=None):
        self._by_scene = {}
        self.screen_w = screen_w
        self.screen_h = screen_h

    def set_screen(self, screen_w, screen_h):
        """更新虚拟屏尺寸（每次存取前刷新，插拔屏不会算错）。"""
        self.screen_w = screen_w
        self.screen_h = screen_h

    def save(self, scene_id, x, y):
        """记下灵魂在 `scene_id` 里的位置。场景 id 非法 ⇒ 返回 False（不造键）。"""
        if not isinstance(scene_id, str) or not scene_id:
            return False
        sw, sh = self.screen_w, self.screen_h
        try:
            sw = float(sw)
            sh = float(sh)
        except (TypeError, ValueError):
            return False
        if sw <= 0 or sh <= 0:
            return False
        self._by_scene[scene_id] = (round(float(x) / sw, 4), round(float(y) / sh, 4))
        return True

    def get(self, scene_id):
        """取回 `scene_id` 里的归一化位置 `(nx, ny)`；没有则 `None`（**不猜**）。"""
        return self._by_scene.get(scene_id)

    def resolve(self, scene_id):
        """取回**屏幕像素**位置；没记过 / 屏尺寸未知 ⇒ `None`。"""
        rec = self._by_scene.get(scene_id)
        if rec is None or not self.screen_w or not self.screen_h:
            return None
        return (rec[0] * float(self.screen_w), rec[1] * float(self.screen_h))

    def scenes(self):
        return sorted(self._by_scene)

    def __len__(self):
        return len(self._by_scene)

    def as_dict(self):
        """可 JSON 化的快照（供 `getattr` / 落盘用）。"""
        return {'schema_version': SCHEMA_VERSION,
                'screen': [self.screen_w, self.screen_h],
                'scenes': dict(self._by_scene)}

    def load_dict(self, data):
        """从 `as_dict()` 的快照恢复。非法输入 ⇒ 清空并返回 False（不抛）。"""
        if not isinstance(data, dict):
            return False
        scenes = data.get('scenes')
        if not isinstance(scenes, dict):
            return False
        clean = {}
        for k, v in scenes.items():
            if (isinstance(k, str) and isinstance(v, (list, tuple)) and len(v) == 2
                    and all(isinstance(n, (int, float)) for n in v)):
                clean[k] = (float(v[0]), float(v[1]))
        self._by_scene = clean
        return True

    def describe(self):
        return '灵魂场景位置 %d 个：%s' % (len(self._by_scene),
                                          '、'.join(sorted(self._by_scene)[:4]))


# ---------------------------------------------------------------- 纯函数

def spawn_point(anchor_x, anchor_y, scale=DISPLAY_SCALE):
    """出生点 = 锚点（通常是宠物窗口中心）+ 原作 `scr_moveheart` 的 (10, 40)。

    `(10, 40)` 是**逻辑**像素 ⇒ 乘 `scale` 换成屏幕像素（与灵魂缩放一致）。
    """
    try:
        s = float(scale)
    except (TypeError, ValueError):
        s = DISPLAY_SCALE
    if s <= 0:
        s = 1.0
    return (float(anchor_x) + SPAWN_OFFSET[0] * s,
            float(anchor_y) + SPAWN_OFFSET[1] * s)


def pick_nearest(point, targets, max_dist=None):
    """在 `targets` 里找离 `point` 最近的一个。

    :param point: `(x, y)`。
    :param targets: 可迭代，元素为 `(key, x, y)` 或 `{'key':..., 'x':..., 'y':...}`。
                    坐标非数的条目**跳过**（不猜、不当作 0）。
    :param max_dist: 超过它就算"够不着" ⇒ 返回 `(None, None)`（**不就近凑**）。
    :return: `(key, dist)`；`targets` 为空 / 全非法 ⇒ `(None, None)`。
    """
    if not point or len(point) < 2:
        return (None, None)
    try:
        px = float(point[0])
        py = float(point[1])
    except (TypeError, ValueError):
        return (None, None)
    best_key = None
    best_d2 = None
    for item in targets or ():
        try:
            if isinstance(item, dict):
                key, tx, ty = item.get('key'), item.get('x'), item.get('y')
            else:
                key, tx, ty = item[0], item[1], item[2]
            tx = float(tx)
            ty = float(ty)
        except (TypeError, ValueError, IndexError, KeyError):
            continue
        d2 = (tx - px) ** 2 + (ty - py) ** 2
        if best_d2 is None or d2 < best_d2:
            best_key, best_d2 = key, d2
    if best_key is None:
        return (None, None)
    dist = math.sqrt(best_d2)
    if max_dist is not None:
        try:
            if dist > float(max_dist):
                return (None, None)
        except (TypeError, ValueError):
            pass
    return (best_key, dist)


def screen_to_room(screen_x, screen_y, room_rect, screen_size):
    """屏幕坐标 → **房间世界坐标**（`main._pet_target_rect` 的取反）。

    `main._pet_target_rect` 把「窗口中心 / 虚拟屏」按比例压进房间矩形；
    这里就是那条映射的逆：`世界 x = rl + rw × (屏幕 x / 屏宽)`。

    任一输入非法 ⇒ 返回 `None`（**不伪装成 (0,0)** —— 那会让"灵魂旁边的物件"
    变成"房间左上角的物件"，是最难查的那种假结果）。
    """
    if not room_rect or len(room_rect) != 4 or not screen_size or len(screen_size) != 2:
        return None
    try:
        rl, rt, rr, rb = [float(v) for v in room_rect]
        sw, sh = [float(v) for v in screen_size]
        sx, sy = float(screen_x), float(screen_y)
    except (TypeError, ValueError):
        return None
    if sw <= 0 or sh <= 0:
        return None
    rw = max(1.0, rr - rl)
    rh = max(1.0, rb - rt)
    fx = min(1.0, max(0.0, sx / sw))
    fy = min(1.0, max(0.0, sy / sh))
    return (rl + rw * fx, rt + rh * fy)


def describe_gate(gate):
    """一行中文摘要（自省/日志用）。"""
    if not isinstance(gate, SoulGate):
        return '非灵魂门控结果：%r' % (gate,)
    return '灵魂门控 %s（%s）%s' % ('放行' if gate.ok else '拒绝',
                                   gate.reason, gate.detail)
