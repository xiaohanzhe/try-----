# -*- coding: utf-8 -*-
"""
宠物身体区域映射 + 手势追踪模块。

设计原则：
1. 纯逻辑模块，不依赖 RalseiPet 主窗口，通过 handle_* 接口接收事件，
   返回 PetEvent 或 None。主窗口据此触发情绪/反应。
2. 与拖拽、跟随鼠标等功能解耦：拖拽期间 is_dragging_mouse=True 时
   主窗口不会调用 handle_*；PetInteractionTracker 自身也有保护。
3. 动态区块：基于当前精灵帧的 alpha 遮罩 + 百分比坐标分区。
"""

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple, List, Deque

try:
    from PyQt5.QtGui import QPixmap, QImage
    from PyQt5.QtCore import QPoint
except ImportError:
    try:
        from PyQt6.QtGui import QPixmap, QImage
        from PyQt6.QtCore import QPoint
    except ImportError:
        QPixmap = None
        QImage = None
        QPoint = None


class BodyPart(str, Enum):
    HAIR = "hair"
    EAR = "ear"
    FACE = "face"
    SHOULDER = "shoulder"
    ARM = "arm"
    TORSO = "torso"
    #: ★ 肚子。与 `TORSO` **分开**是原作的划分（见 `_REGIONS_PERCENT` 的注释）：
    #  「拍肚子」和「轻点躯干」在原实现里是两套不同台词（`double_belly` vs
    #  `poke_body`），合并会让前者永不触发。
    BELLY = "belly"
    LEG = "leg"
    WHOLE_BODY = "whole_body"


class Gesture(str, Enum):
    STROKE = "stroke"           # 抚摸：3+ 次往返移动
    PUSH = "push"               # 轻推：单击
    PAT = "pat"                 # 拍拍：双击
    PINCH = "pinch"             # 捏：长按 ≥0.5s
    PULL = "pull"               # 拉住：长按 ≥0.5s 且伴随移动
    FLICK = "flick"             # 不楞不楞：3+ 连击


@dataclass
class PetEvent:
    body_part: BodyPart
    gesture: Gesture
    timestamp: float = field(default_factory=time.time)


# 百分比坐标 (min_x, min_y, max_x, max_y)，相对精灵尺寸
#
# ★★ 顺序即优先级：**先命中先返回**（`BodyRegionMapper.part_at` 是线性扫描，
#    取第一条命中）。所以子区域（belly 在 body 里）必须排在父区域之前，
#    否则整个肚子会被躯干吃掉，`double_belly` / `pat_belly` 永不触发。
#
# ★★ 这张表是 `main.py::get_ralsei_body_part`（第75轮 B3 迁移前的手写实现，
#    见 git 历史 `main.py` 的 `body_parts = [...]`）的**逐条等价搬迁**。
#    第75轮实测：先前的版本把百分比数值**重调过**（如 ear 30→28、hair 25→22），
#    还**整条漏掉了 `belly`** —— 这类"搬迁时手抖"不会报任何错，
#    只会让用户觉得"摸起来不准了"，属于本项目头号敌人「静默漂移」。
#    故此处数值一律回到原文，并在 `check76.py` 里加回归锁。
_REGIONS_PERCENT: List[Tuple[BodyPart, float, float, float, float]] = [
    # 耳朵区域
    (BodyPart.EAR,      0.0,  0.0,  30.0, 40.0),   # 左耳
    (BodyPart.EAR,     70.0,  0.0, 100.0, 40.0),   # 右耳
    # 头发区域
    (BodyPart.HAIR,    25.0, 10.0,  75.0, 50.0),
    # 面部区域
    (BodyPart.FACE,    30.0, 30.0,  70.0, 60.0),
    # 肚子区域（★ 必须在 TORSO 之前：它整个落在躯干范围内）
    (BodyPart.BELLY,   35.0, 60.0,  65.0, 80.0),
    # 躯干区域
    (BodyPart.TORSO,   20.0, 50.0,  80.0, 80.0),
    # 腿部区域
    (BodyPart.LEG,     30.0, 80.0,  70.0, 100.0),
    # 手臂区域
    (BodyPart.ARM,      0.0, 40.0,  30.0, 70.0),   # 左臂
    (BodyPart.ARM,     70.0, 40.0, 100.0, 70.0),   # 右臂
    # 肩膀区域
    (BodyPart.SHOULDER, 15.0, 45.0, 35.0, 60.0),   # 左肩
    (BodyPart.SHOULDER, 65.0, 45.0, 85.0, 60.0),   # 右肩
    # 全身区域（兜底：放在最后，前面都不命中时才会走到它）
    (BodyPart.WHOLE_BODY, 0.0, 0.0, 100.0, 100.0),
]


class BodyRegionMapper:
    """动态身体区域映射。

    支持两种模式：
    - alpha 遮罩模式：从 QPixmap 提取 alpha 通道作为有效像素，
      只将鼠标落在非透明区域的事件视为"在宠物身上"。
    - 百分比区域模式：将精灵按百分比坐标划分为 BodyPart。
    两者结合：先检查 alpha 遮罩命中，再用百分比坐标分类。
    """

    def __init__(self):
        self._pixmap: Optional[QPixmap] = None
        self._alpha_mask: Optional[List[List[bool]]] = None
        self._width: int = 0
        self._height: int = 0

    def set_sprite(self, pixmap: Optional[QPixmap]):
        """更新当前精灵帧，重建 alpha 遮罩。"""
        if pixmap is None or QPixmap is None:
            self._pixmap = None
            self._alpha_mask = None
            self._width = 0
            self._height = 0
            return
        self._pixmap = pixmap
        self._width = pixmap.width()
        self._height = pixmap.height()
        self._build_alpha_mask(pixmap)

    def _build_alpha_mask(self, pixmap: QPixmap):
        if QImage is None:
            self._alpha_mask = None
            return
        img = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
        w, h = img.width(), img.height()
        mask = []
        for y in range(h):
            row = []
            for x in range(w):
                alpha = (img.pixel(x, y) >> 24) & 0xFF
                row.append(alpha > 8)
            mask.append(row)
        self._alpha_mask = mask
        self._width = w
        self._height = h

    def is_on_pet(self, x: float, y: float) -> bool:
        """检查坐标 (像素，相对于精灵左上角) 是否落在宠物非透明区域。"""
        if self._alpha_mask is not None and self._width > 0 and self._height > 0:
            ix, iy = int(x), int(y)
            if 0 <= ix < self._width and 0 <= iy < self._height:
                return self._alpha_mask[iy][ix]
            return False
        return 0 <= x <= self._width and 0 <= y <= self._height

    def classify(self, x: float, y: float) -> BodyPart:
        """根据像素坐标返回对应的身体部位。"""
        if self._width <= 0 or self._height <= 0:
            return BodyPart.WHOLE_BODY
        rx = (x / self._width) * 100.0
        ry = (y / self._height) * 100.0
        for part, min_x, min_y, max_x, max_y in _REGIONS_PERCENT:
            if min_x <= rx <= max_x and min_y <= ry <= max_y:
                return part
        return BodyPart.WHOLE_BODY


class _StrokeDetector:
    """检测抚摸手势：3+ 次方向往返。"""

    def __init__(self):
        self._history: Deque[Tuple[float, float, float]] = deque(maxlen=30)
        self._last_dx_sign: Optional[int] = None
        self._direction_changes: int = 0
        self._last_trigger_time: float = 0.0
        self._min_move_px: float = 3.0
        self._max_move_px: float = 40.0
        self._cooldown: float = 1.5
        self._required_changes: int = 3

    def reset(self):
        self._history.clear()
        self._last_dx_sign = None
        self._direction_changes = 0

    def feed(self, dx: float, dy: float, part: BodyPart) -> Optional[BodyPart]:
        distance = (dx * dx + dy * dy) ** 0.5
        if distance < self._min_move_px or distance > self._max_move_px:
            return None

        if abs(dx) > abs(dy):
            sign = 1 if dx > 0 else -1
            if self._last_dx_sign is not None and sign != self._last_dx_sign:
                self._direction_changes += 1
            self._last_dx_sign = sign
        else:
            sign = 1 if dy > 0 else -1
            if self._last_dx_sign is not None and sign != self._last_dx_sign:
                self._direction_changes += 1
            self._last_dx_sign = sign

        self._history.append((dx, dy, distance))

        now = time.time()
        if self._direction_changes >= self._required_changes:
            if now - self._last_trigger_time > self._cooldown:
                self._last_trigger_time = now
                self.reset()
                return part
        return None


class GestureTracker:
    """统一的手势追踪器。

    状态：
    - press_start_time / press_pos：记录按下时刻和位置
    - press_part：按下时的身体部位
    - is_pressing：是否处于按下状态
    - press_has_moved：按下期间是否发生了显著位移
    - consecutive_clicks：同一部位的连续点击计数（用于 ear flick）
    - last_click_time / last_click_part：上一次点击的时间和部位
    - last_click_was_double：上一次点击是否已被识别为双击
    - stroke_detector：抚摸检测器
    """

    LONG_PRESS_THRESHOLD: float = 0.5
    DOUBLE_CLICK_GAP: float = 0.4
    CLICK_GAP_FOR_CONSECUTIVE: float = 0.6
    PULL_MOVE_THRESHOLD: float = 8.0
    FLICK_REQUIRED: int = 3

    def __init__(self):
        self.press_start_time: float = 0.0
        self.press_pos: Tuple[float, float] = (0.0, 0.0)
        self.press_part: BodyPart = BodyPart.WHOLE_BODY
        self.is_pressing: bool = False
        self.press_has_moved: bool = False

        self.consecutive_clicks: int = 0
        self.last_click_time: float = 0.0
        self.last_click_part: BodyPart = BodyPart.WHOLE_BODY
        self.last_click_was_double: bool = False

        self._last_pos: Optional[Tuple[float, float]] = None
        self._stroke = _StrokeDetector()

    def on_press(self, pos: Tuple[float, float], part: BodyPart):
        self.is_pressing = True
        self.press_start_time = time.time()
        self.press_pos = pos
        self.press_part = part
        self.press_has_moved = False
        self._last_pos = None
        self._stroke.reset()

    def on_release(self, pos: Tuple[float, float]) -> Optional[PetEvent]:
        if not self.is_pressing:
            return None
        self.is_pressing = False
        duration = time.time() - self.press_start_time
        part = self.press_part
        moved = self.press_has_moved
        self.press_has_moved = False

        if duration >= self.LONG_PRESS_THRESHOLD:
            if moved:
                return PetEvent(body_part=part, gesture=Gesture.PULL)
            else:
                return PetEvent(body_part=part, gesture=Gesture.PINCH)

        now = time.time()
        same_part = (part == self.last_click_part)
        gap = now - self.last_click_time

        # 点击计数（所有部位）
        if same_part and gap < self.CLICK_GAP_FOR_CONSECUTIVE:
            self.consecutive_clicks += 1
        else:
            self.consecutive_clicks = 1

        self.last_click_time = now
        self.last_click_part = part

        # 耳朵连击 → flick（优先于双击）
        if part == BodyPart.EAR and self.consecutive_clicks >= self.FLICK_REQUIRED:
            self.consecutive_clicks = 0
            self.last_click_was_double = False
            return PetEvent(body_part=part, gesture=Gesture.FLICK)

        # 双击（非耳朵部位）
        if same_part and gap < self.DOUBLE_CLICK_GAP and not self.last_click_was_double:
            if part != BodyPart.EAR:
                self.last_click_was_double = True
                self.last_click_time = 0.0
                self.consecutive_clicks = 0
                return PetEvent(body_part=part, gesture=Gesture.PAT)

        self.last_click_was_double = False

        # 普通单击 → push
        if part in (BodyPart.TORSO, BodyPart.SHOULDER, BodyPart.ARM):
            return PetEvent(body_part=part, gesture=Gesture.PUSH)

        return None

    def on_move(self, pos: Tuple[float, float], part: BodyPart,
                is_on_pet: bool) -> Optional[PetEvent]:
        if self.is_pressing:
            dx = pos[0] - self.press_pos[0]
            dy = pos[1] - self.press_pos[1]
            dist = (dx * dx + dy * dy) ** 0.5
            if dist > self.PULL_MOVE_THRESHOLD:
                self.press_has_moved = True
            return None

        if is_on_pet:
            if self._last_pos is not None:
                feed_dx = pos[0] - self._last_pos[0]
                feed_dy = pos[1] - self._last_pos[1]
            else:
                feed_dx, feed_dy = 0, 0
            self._last_pos = pos
            result = self._stroke.feed(feed_dx, feed_dy, part)
            if result is not None:
                return PetEvent(body_part=result, gesture=Gesture.STROKE)
        else:
            self._stroke.reset()
            self._last_pos = None

        return None


class PetInteractionTracker:
    """组合 BodyRegionMapper + GestureTracker，对外提供统一接口。"""

    def __init__(self):
        self.region = BodyRegionMapper()
        self.gesture = GestureTracker()
        self._drag_active = False
        self._follow_active = False

    def set_sprite(self, pixmap: Optional[QPixmap]):
        self.region.set_sprite(pixmap)

    def set_drag_active(self, active: bool):
        self._drag_active = active
        if active:
            self.gesture._stroke.reset()

    def set_follow_active(self, active: bool):
        self._follow_active = active

    def _resolve(self, window_pos) -> Tuple[bool, BodyPart, Tuple[float, float]]:
        if QPoint is not None and isinstance(window_pos, QPoint):
            px, py = float(window_pos.x()), float(window_pos.y())
        elif isinstance(window_pos, (tuple, list)) and len(window_pos) == 2:
            px, py = float(window_pos[0]), float(window_pos[1])
        else:
            return False, BodyPart.WHOLE_BODY, (0.0, 0.0)

        on_pet = self.region.is_on_pet(px, py)
        part = self.region.classify(px, py) if on_pet else BodyPart.WHOLE_BODY
        return on_pet, part, (px, py)

    def handle_press(self, window_pos) -> None:
        if self._drag_active or self._follow_active:
            return
        on_pet, part, rel = self._resolve(window_pos)
        if on_pet:
            self.gesture.on_press(rel, part)

    def handle_release(self, window_pos) -> Optional[PetEvent]:
        if self._drag_active:
            self.gesture.is_pressing = False
            return None
        on_pet, part, rel = self._resolve(window_pos)
        return self.gesture.on_release(rel)

    def handle_move(self, window_pos) -> Optional[PetEvent]:
        on_pet, part, rel = self._resolve(window_pos)

        if self.gesture.is_pressing and not self._drag_active:
            self.gesture.on_move(rel, part, on_pet)
            return None

        if not self._drag_active and not self._follow_active:
            return self.gesture.on_move(rel, part, on_pet)

        return None


# ===========================================================================
#  手势 → 事件名（kind）映射 + 响应规格表（第75轮 B3）
# ===========================================================================
# ★ 这一层是**纯数据 + 纯函数**：不碰 Qt、不碰情绪系统、不碰台词池实现。
#   主窗口拿 `kind` 去查 `RESPONSE_SPEC` 执行，查不到就什么都不做。
#
# ⚠️ 为什么 `kind` 的名字必须是 `event_speech.EVENT_TIERS` 里**已登记**的那些：
#   未登记的 kind 会被 `tier_of()` 判成 `TIER_INSTANT`（不联网、走内置台词），
#   于是"迁移到 AI"的这批事件会**静默退回罐头** —— 这正是第75轮在别处踩过的坑。
#   ⇒ `_KIND_*` 三张表里的每个字符串都能在 `EVENT_TIERS` 里找到（check75d 守）。

#: `BodyPart` → `event_speech.PET_PARTS` 用的部位名。
#  ★★ 必须做这层映射，不能直接用 `part.value`：
#    `BodyPart.TORSO` 的值是 `"torso"`，而 `PET_PARTS` 里是 `"body"`
#    （HEAD 的手写实现用的是 `clicked_part == "body"`）；
#    `LEG` / `WHOLE_BODY` 在 `PET_PARTS` 里**根本没有** ⇒ 归 `other`。
#    不做映射的话，摸肚子会得到 `pet_torso`（未登记）⇒ 静默退回罐头。
_PART_TO_PET = {
    BodyPart.HAIR: 'hair',
    BodyPart.EAR: 'ear',
    BodyPart.FACE: 'face',
    BodyPart.SHOULDER: 'shoulder',
    BodyPart.ARM: 'arm',
    BodyPart.TORSO: 'body',
    # ★ `BELLY` 没有对应的 `pet_belly`：`PET_PARTS` 里只有 body。
    #   抚摸肚子按原作也算 body（HEAD 的抚摸链路只按 body/… 分池）。
    #   但**双击/连点**肚子另有专属事件 `double_belly`，见 `kind_for`。
    BodyPart.BELLY: 'body',
}

#: 长按类手势 → 每部位对应的事件名。
#
# ★★★ 出处：HEAD `main.py::mouseReleaseEvent` 的**长按链**（`press_duration >= 0.5`），
#     原文是**一条 if/elif 链、六个分支**，全部搬迁到这张表：
#       `"ear"`      → `pinch_ear`      （轻轻捏耳朵）
#       `"arm"`      → `pull_arm`       （拉住手臂）
#       `"body"`     → `press_body`     （按住躯干）
#       `"belly"`    → `pat_belly`      （拍肚子）
#       `"face"`     → `pinch_face`     （轻轻捏脸）
#       `"shoulder"` → `pull_shoulder`  （拉住肩膀）
#
#     ⚠️ 第75轮第二版判定"捏/拉只对 ear/face/arm/shoulder 有反应"是**漏读**：
#        原文里 `body` 和 `belly` 各有独立台词（`press_body` / `pat_belly`），
#        只是命名不像 `pinch_*`/`pull_*` 那样好认。删掉它们 = 按住肚子变成没反应，
#        而 `pat_belly` / `press_body` 这两个已登记 kind 变成**永不触发的死项**。
#        ⇒ `check76.py` A6 段（"手势事件名恰好 22 个且与改造前集合相等"）抓到。
#
#     没列的部位（`hair`/`leg`/`whole_body`）**确实没有**长按台词 ⇒ 返回 `None`
#     如实沉默（铁律：走不到就是走不到，**不就近凑**）。
_PRESS_KINDS = {
    Gesture.PINCH: {
        BodyPart.EAR: 'pinch_ear',
        BodyPart.FACE: 'pinch_face',
        #  ★ `body` / `belly` 的 kind 名字里没有 "pinch" 字样，容易漏 —— 见上注。
        BodyPart.TORSO: 'press_body',
        BodyPart.BELLY: 'pat_belly',
    },
    Gesture.PULL: {
        BodyPart.ARM: 'pull_arm',
        BodyPart.SHOULDER: 'pull_shoulder',
    },
}


def kind_for(part, gesture):
    """`(身体部位, 手势)` → 事件名（kind）。取不到对应条目 ⇒ `None`（**不猜**）。

    主窗口据此查 `RESPONSE_SPEC`：`None` = 这个手势在这里没有回应，
    **保持沉默**，而不是随便挑一个响应出来（"静默降级是本项目头号敌人"
    的反面：这里"沉默"是**有意的**，因为反应表就是没这一项）。

    ★ 与 `event_speech.pet_kind()` 的分工：那个函数只做"部位 → pet_*"，
      喂给抚摸链路；本函数覆盖**全部 6 种手势**，是主窗口的唯一入口。

    :param part: `BodyPart`；传字符串也接受（按 `.value` 宽松比对）。
    :param gesture: `Gesture`；同上。
    :return: kind 字符串 或 `None`。
    """
    g = gesture.value if isinstance(gesture, Gesture) else str(gesture or '')
    p = part if isinstance(part, BodyPart) else None
    if p is None:
        # 宽松：允许传字符串（如 "hair" / "torso"）
        for bp in BodyPart:
            if bp.value == str(part or ''):
                p = bp
                break

    if g == Gesture.PUSH.value:
        # 单击：只有躯干/肩膀有专门台词，其余走通用（与 HEAD 手写实现逐字一致）
        if p == BodyPart.TORSO or p == BodyPart.BELLY:
            return 'poke_body'
        if p == BodyPart.SHOULDER:
            return 'poke_shoulder'
        return 'poke_default'

    if g == Gesture.PAT.value:
        # 双击：HEAD 有 double_hair / double_belly / double_face / double_shoulder
        # + `double_other` 五项。
        if p == BodyPart.HAIR:
            return 'double_hair'
        if p == BodyPart.BELLY:
            return 'double_belly'
        if p == BodyPart.TORSO:
            # ★ 躯干双击在原实现里走**通用**项（`double_belly` 专属肚子）。
            #   第75轮第一版把 TORSO 直接映射到 `double_belly`，导致
            #   `belly` 独立出来的意义归零 ⇒ 这里回到 `double_other`。
            return 'double_other'
        if p == BodyPart.FACE:
            return 'double_face'
        if p == BodyPart.SHOULDER:
            return 'double_shoulder'
        return 'double_other'

    if g == Gesture.STROKE.value:
        # 抚摸：台词池按部位分（见 STROKE_POOL），kind 统一 `pet_<部位>`
        name = _PART_TO_PET.get(p)
        return ('pet_%s' % name) if name else 'pet_other'

    if g in (Gesture.PINCH.value, Gesture.PULL.value):
        # ★★ 合并查两张表，**不分** PINCH / PULL。
        #    理由：HEAD 原文只有**一条**"长按 ≥0.5s"的 if/elif 链，分支只看
        #    `clicked_part`，**完全不看长按期间有没有移动**。
        #    而本模块的 `GestureTracker` 会把"长按且移动"判成 `PULL`、
        #    "长按不动"判成 `PINCH` —— 如果只在各自表里查，用户**捏住耳朵
        #    稍微拖一下**就会从 `pinch_ear` 掉进"PULL 表里没有 ear ⇒ None"，
        #    表现为"捏耳朵有时有反应有时没有"（间歇性、极难复现）。
        #    ⇒ 合并表 = 贴合原文（长按就是长按），也消除了这个间歇缺陷。
        for _t in _PRESS_KINDS.values():
            if p in _t:
                return _t[p]
        return None

    if g == Gesture.FLICK.value:
        # 3+ 连击：HEAD 只有耳朵那个机关（`ear_ruffle`，且**有意**保持 INSTANT）
        if p == BodyPart.EAR:
            return 'ear_ruffle'
        return None

    return None


#: 抚摸的**共用情绪**（所有部位一样）—— 照抄 HEAD 手写实现的两行。
#  ⚠️ 为什么是模块常量而不是塞进 `RESPONSE_SPEC`：`main._dispatch_pet_event`
#    对 STROKE 走的是**独立分支**（先加这组情绪，再按部位取台词池），
#    与其它手势"查 RESPONSE_SPEC"的路径不同。两份表分开 = 各自可独立回归。
STROKE_EMOTIONS = (("happy", 30), ("shy", 15))

#: 抚摸的**按部位台词池**（HEAD 原文台词汇总；`pet_other` 是兜底池）。
#  ★ 这些台词是 **AI 不可用时的兜底**（`speak_event(kind, pool, face)`
#    的 `pool` 语义：有 pool = AI 判退就说出兜底句；`pool=None` = 宁可沉默）。
#    所以这里保留 HEAD 的原句 —— 它们是用户已见过的文案，不是新编的。
STROKE_POOL = {
    'hair': ["嘿嘿~ 摸我的头发好舒服呀！", "谢谢你的抚摸！",
             "真的好舒服呀~", "我的头发很软吧？"],
    'ear': ["哎呀~ 别摸我的耳朵！好痒呀！", "嘿嘿~ 耳朵好敏感呀！",
            "别摸啦！耳朵会变红的！"],
    'face': ["哎呀~ 别摸我的脸！", "脸好烫呀~",
             "嘿嘿~ 摸脸的感觉好特别！"],
    'body': ["嘿嘿~ 好舒服呀！", "谢谢你的抚摸！",
             "真的好舒服呀~", "你的手好温暖！"],
    'arm': ["哎呀~ 别摸我的手臂！", "嘿嘿~ 手臂也会痒的！",
            "你的抚摸让我好开心！"],
    'shoulder': ["谢谢你抚摸我的肩膀！", "嘿嘿~ 肩膀也很舒服！",
                 "你的手好温柔！"],
}

#: 抚摸通用兜底池（部位不在 `STROKE_POOL` 里时用）。
STROKE_POOL_OTHER = ["嘿嘿~ 好舒服呀！", "谢谢你的抚摸！", "真的好舒服呀~"]


def _spec(emotions, anim, face, pool):
    return (emotions, anim, face, pool)


#: `kind` → `(情绪表, 播一次动画, 表情, 台词池)`。
#
# ★★★ 本表是对 HEAD `main.py` 手写实现的**逐字等价搬迁**，不是新设计。
#     每条都写清出处行（HEAD 的 `mousePressEvent` / `mouseReleaseEvent` /
#     `mouseDoubleClickEvent`），改动时**回原文核对**，别凭手感调数值。
#
#     ⚠️ 第75轮第二版曾按"看着合理"重写过一遍数值（如 `pinch_ear` 写成
#        surprised 20/shy 15、台词换成「别、别捏啦……」），**全部偏离原文**。
#        这类偏差不会报错、不会被用户立刻发现，只会让"摸耳朵"和"捏耳朵"
#        的反应慢慢不像原来那只 Ralsei —— 属于本项目头号敌人「静默漂移」。
#        故第三版起：**数值与台词一律回原文**，并由 `check76.py` F4/F5 段逐条钉住。
#
#     出处对照（全部来自 HEAD `main.py`）：
#       · `poke_body`      ← mousePressEvent  `clicked_part == "body"`
#       · `poke_shoulder`  ← mousePressEvent  `clicked_part == "shoulder"`
#       · `poke_default`   ← mousePressEvent  else 分支（无情绪、无动画）
#       · `double_hair`    ← mouseDoubleClickEvent `"hair"`（摸头杀）
#       · `double_belly`   ← mouseDoubleClickEvent `"belly"`
#       · `double_face`    ← mouseDoubleClickEvent `"face"`
#       · `double_shoulder`← mouseDoubleClickEvent `"shoulder"`
#       · `double_other`   ← mouseDoubleClickEvent else 分支
#       · `pinch_ear`      ← mouseReleaseEvent 长按 `"ear"`
#       · `pull_arm`       ← mouseReleaseEvent 长按 `"arm"`
#       · `press_body`     ← mouseReleaseEvent 长按 `"body"`（按住躯干）
#       · `pat_belly`      ← mouseReleaseEvent 长按 `"belly"`（拍肚子）
#       · `pinch_face`     ← mouseReleaseEvent 长按 `"face"`
#       · `pull_shoulder`  ← mouseReleaseEvent 长按 `"shoulder"`
#       · `ear_ruffle`     ← HEAD 的连点机关（登记为 INSTANT，不联网）
#
#  ⚠️ `pool=None` 的项 = **不给内置台词**（说不了就沉默）——
#     这是用户「聊天系统全权由 7B 接管」的口径；目前全部保留 HEAD 文案
#     （因为它们已在用户面前出现过），后续要迁 AI 时把 pool 改成 None 即可。
RESPONSE_SPEC = {
    # ---- 单击（PUSH）----
    'poke_body': _spec((("happy", 15), ("curious", 10)), 'look_up', 'curious',
                       ["嗯？怎么啦？", "诶？有什么事吗？", "嘿嘿~ 你戳我啦"]),
    'poke_shoulder': _spec((("happy", 20), ("curious", 10)), 'look_up', 'curious',
                           ["嗯？有什么事吗？"]),
    'poke_default': _spec((), None, 'happy',
                          ["嘿嘿！", "你好呀！", "很高兴见到你！", "要一起玩吗？"]),
    # ---- 双击（PAT）----
    'double_hair': _spec((("happy", 50), ("shy", 35)), 'pose', 'happy',
                         ["嘿嘿~ 摸头杀好舒服！"]),
    'double_belly': _spec((("happy", 45), ("excited", 25)), 'laugh', 'laughing',
                          ["哈哈！别用力拍我的肚子啦！"]),
    'double_face': _spec((("happy", 40), ("shy", 40)), 'surprised', 'surprised',
                         ["哎呀！别捏我的脸！"]),
    'double_shoulder': _spec((("happy", 35), ("caring", 20)), 'wave', 'happy',
                             ["谢谢你拍拍我的肩膀！"]),
    'double_other': _spec((("happy", 20), ("shy", 10)), 'happy', 'happy',
                          ["嘿嘿~ 你对我真好！"]),
    # ---- 连击（FLICK）—— 登记为 INSTANT（不联网），保留原机关台词 ----
    #  出处：HEAD `mousePressEvent` 的"点耳朵 3 次"机关（0.5s 内累计）：
    #        happy 40 + excited 20 / `play_animation_once("laugh")` / face=`surprised`
    #        / `speak_event(..., instant=True)`
    'ear_ruffle': _spec((("happy", 40), ("excited", 20)), 'laugh', 'surprised',
                        ["哎呀！别不楞我的耳朵啦！"]),
    # ---- 长按（PINCH / PULL）—— 全部来自 mouseReleaseEvent 的长按链 ----
    'pinch_ear': _spec((("happy", 35), ("shy", 25)), 'surprised', 'surprised',
                       ["哎呀！别捏我的耳朵！好痒呀！"]),
    'pull_arm': _spec((("happy", 30),), 'wave', 'happy',
                      ["嘿嘿~ 别拉我的手臂啦！"]),
    'press_body': _spec((("happy", 25), ("shy", 20)), 'happy', 'happy',
                        ["嗯~ 好舒服！"]),
    'pat_belly': _spec((("happy", 40), ("excited", 20)), 'laugh', 'happy',
                       ["嘿嘿~ 我的肚子很软哦！"]),
    'pinch_face': _spec((("happy", 30), ("shy", 30)), 'surprised', 'shy',
                        ["哎呀~ 别捏我的脸！"]),
    'pull_shoulder': _spec((("happy", 25), ("shy", 15)), 'pose', 'happy',
                           ["谢谢你拉我的肩膀！"]),
}
