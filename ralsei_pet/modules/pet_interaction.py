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
# 顺序：先特殊区域（耳、发），再通用区域（躯干、四肢）
_REGIONS_PERCENT: List[Tuple[BodyPart, float, float, float, float]] = [
    (BodyPart.EAR,      0.0,  0.0, 28.0, 38.0),
    (BodyPart.EAR,     72.0,  0.0, 100.0, 38.0),
    (BodyPart.HAIR,    22.0,  5.0, 78.0, 42.0),
    (BodyPart.FACE,    28.0, 30.0, 72.0, 60.0),
    (BodyPart.SHOULDER, 12.0, 42.0, 38.0, 62.0),
    (BodyPart.SHOULDER, 62.0, 42.0, 88.0, 62.0),
    (BodyPart.ARM,      0.0, 38.0, 25.0, 72.0),
    (BodyPart.ARM,     75.0, 38.0, 100.0, 72.0),
    (BodyPart.TORSO,   25.0, 58.0, 75.0, 85.0),
    (BodyPart.LEG,     28.0, 80.0, 72.0, 100.0),
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
