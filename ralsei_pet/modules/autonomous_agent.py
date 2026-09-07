# -*- coding: utf-8 -*-
"""
自主代理模块 —— Ralsei 作为"第二个独立用户"与桌面交互。

状态机:
    IDLE → DECIDING → WALKING → FACING → ACTING → REACTING → IDLE

设计原则:
1. 不劫持用户鼠标：所有桌面操作通过 win32 API 后台执行（PostMessage /
   os.startfile / SHFileOperation / LVM_SETITEMPOSITION），绝不调用
   SetCursorPos / mouse_event / QCursor.setPos。
2. 运动与动作分离：主窗口的 update_movement 负责"走到哪里"，
   本模块负责"决定去哪里 + 走到后做什么"。两者通过 start_walk_to()
   回调 + on_arrived() 通知解耦。
3. 互斥锁：代理启动前检查 busy（拖拽/跟随/物理运动/手势追踪），
   冲突时排队等待，绝不与用户争抢鼠标控制权。
4. 视觉反馈：ACT 阶段触发宠物表情/对话/动画，让用户"看见"他在操作。
"""

import time
import math
import random
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Callable, Any, Dict


class AgentState(str, Enum):
    IDLE = "idle"
    DECIDING = "deciding"
    WALKING = "walking"
    FACING = "facing"
    ACTING = "acting"
    REACTING = "reacting"
    PAUSED = "paused"


class InteractionType(str, Enum):
    OPEN = "open"
    DRAG = "drag"
    DELETE = "delete"
    EXAMINE = "examine"
    OBSERVE = "observe"
    CLOSE_WINDOW = "close_window"
    RESIZE_WINDOW = "resize_window"
    MINIMIZE_WINDOW = "minimize_window"


@dataclass
class InteractionTarget:
    """代理选择的交互目标。"""
    kind: str                  # "file", "folder", "window", "desktop_icon"
    name: str                  # 显示名称
    path: Optional[str] = None # 文件/文件夹路径
    hwnd: Optional[int] = None # 窗口 HWND
    x: float = 0.0             # 目标中心 X (屏幕坐标)
    y: float = 0.0             # 目标中心 Y (屏幕坐标)
    width: float = 0.0
    height: float = 0.0

    def center(self):
        return (self.x + self.width / 2, self.y + self.height / 2)

    def nearest_edge(self, from_x: float, from_y: float):
        """返回从 (from_x, from_y) 到目标矩形上最近的边缘点。"""
        cx = min(max(from_x, self.x), self.x + self.width)
        cy = min(max(from_y, self.y), self.y + self.height)
        return (cx, cy)


@dataclass
class AutonomousTask:
    """完整的一次自主行动任务。"""
    target: InteractionTarget
    action: InteractionType
    # 用于 DRAG 的目标位置（屏幕坐标）
    drag_to: Optional[tuple] = None
    # 用于 RESIZE_WINDOW 的新尺寸
    new_width: Optional[int] = None
    new_height: Optional[int] = None
    # 内部计时
    facing_start: float = 0.0
    acting_start: float = 0.0
    reaction_start: float = 0.0


# 默认各阶段时长（秒）
DEFAULT_FACING_DURATION = 0.6
DEFAULT_ACTING_DURATION = 1.5
DEFAULT_REACTING_DURATION = 1.2

# 动作文本模板
ACTION_DIALOGUES: Dict[InteractionType, Dict[str, List[str]]] = {
    InteractionType.OPEN: {
        "start":  ["我来看看 {name} 吧！", "让我打开 {name} 看看~", "{name}，我来啦！"],
        "done":   ["{name} 打开了哦~", "看看 {name} 里有什么...", "咦？{name} 打开了！"],
    },
    InteractionType.DRAG: {
        "start":  ["我来帮你把 {name} 挪个地方吧~", "{name} 放在这里好像不太对...", "让我把 {name} 移一下！"],
        "done":   ["好啦，{name} 挪完了~", "{name} 移好啦！", "嗯，{name} 现在位置不错！"],
    },
    InteractionType.DELETE: {
        "start":  ["{name} 看起来可以清掉呢...", "{name} 没用了吧？我来处理一下", "咦，{name} 好像不需要了？"],
        "done":   ["{name} 清理掉啦~", "好啦，{name} 已经处理了", "{name} 不见了！"],
    },
    InteractionType.EXAMINE: {
        "start":  ["让我看看 {name} 里有什么...", "{name} 里藏着什么秘密？", "我来研究一下 {name}"],
        "done":   ["嗯~ {name} 里是这样的啊", "原来 {name} 是这个！", "了解了 {name}~"],
    },
    InteractionType.OBSERVE: {
        "start":  ["让我观察一下 {name}", "{name} 看起来很有意思~", "{name}...嘿嘿..."],
        "done":   ["{name} 没什么特别的...", "{name} 就那样吧", "看完 {name} 了~"],
    },
    InteractionType.CLOSE_WINDOW: {
        "start":  ["{name} 好像不用了吧？", "{name}，我来关掉你哦~", "该让 {name} 休息了"],
        "done":   ["{name} 关掉啦~", "好啦，{name} 消失了", "{name} 已经关了"],
    },
    InteractionType.RESIZE_WINDOW: {
        "start":  ["{name} 窗口大小有点怪呢", "让我帮你调一下 {name} 的大小", "{name}，我来给你换个尺寸"],
        "done":   ["{name} 尺寸调好啦~", "嗯，{name} 现在看着舒服多了！"],
    },
    InteractionType.MINIMIZE_WINDOW: {
        "start":  ["先把 {name} 收起来吧", "{name} 先放一边~", "{name}，先最小化哦"],
        "done":   ["{name} 收起来了~", "{name} 在任务栏里等着呢"],
    },
}


class AutonomousAgent:
    """自主代理状态机。

    使用方式（在 RalseiPet 中）::

        def __init__(self):
            ...
            self.agent = AutonomousAgent(
                get_pos=lambda: self.pos(),
                set_target_pos=self._start_walk_to,
                change_animation=self.change_animation,
                play_once=self.play_animation_once,
                show_dialogue=lambda t, m, d: self.dialogue_ui.add_dialogue(...),
                add_emotion=lambda e, v: self.emotion_system.add_emotion(e, v),
                desktop=self.desktop_interaction,
                get_busy_flags=self._get_agent_busy_flags,
            )
            self.agent.start()

        def update_movement(self):
            ...  # 原有移动逻辑
            self.agent.tick(time.time())

        def _on_arrived(self):
            # 走到后调用
            self.agent.notify_arrived()

        def _get_agent_busy_flags(self):
            return {
                "dragging": self.is_dragging_mouse,
                "following": self.is_following_mouse,
                "physical": self.is_falling or self.is_recovering or ...,
            }
    """

    def __init__(
        self,
        get_pos: Callable[[], Any],
        set_target_pos: Callable[[float, float], None],
        change_animation: Callable[..., None],
        play_once: Callable[[str], None],
        show_dialogue: Callable[[str, str, str], None],
        add_emotion: Callable[[str, float], None],
        desktop: Any,
        get_busy_flags: Callable[[], Dict[str, bool]],
        decision_interval: float = 45.0,
        reach_threshold: float = 45.0,
        facing_duration: float = DEFAULT_FACING_DURATION,
        acting_duration: float = DEFAULT_ACTING_DURATION,
        reaction_duration: float = DEFAULT_REACTING_DURATION,
    ):
        self._get_pos = get_pos
        self._set_target_pos = set_target_pos
        self._change_anim = lambda a, force=False: change_animation(a, force)
        self._play_once = play_once
        self._show_dialogue = show_dialogue
        self._add_emotion = add_emotion
        self._desktop = desktop
        self._get_busy = get_busy_flags

        self._decision_interval = decision_interval
        self._reach_threshold = reach_threshold
        self._facing_duration = facing_duration
        self._acting_duration = acting_duration
        self._reaction_duration = reaction_duration

        self.state: AgentState = AgentState.IDLE
        self.current_task: Optional[AutonomousTask] = None
        self._last_decision_time: float = 0.0
        self._task_started_at: float = 0.0
        self._last_open_time: float = 0.0
        self._enabled: bool = False
        # 进阶 Skill 去抖时间戳
        self._last_organize_time: float = 0.0
        # 修复：记录暂停前的状态，冲突解除后恢复而不是直接变 IDLE（避免"暂停=取消"）
        self._pre_pause_state: AgentState = AgentState.IDLE
        # WALKING 暂停时记录目标坐标，恢复时重新发起移动
        self._pre_pause_walk_target: Optional[tuple] = None

    # ---- 公共 API ----

    def start(self):
        self._enabled = True
        self.state = AgentState.IDLE

    def stop(self):
        self._enabled = False
        self.state = AgentState.IDLE
        self.current_task = None

    def is_busy(self) -> bool:
        return self.state not in (AgentState.IDLE, AgentState.PAUSED)

    def tick(self, now: float):
        """每一帧（或每 100ms）调用一次。"""
        if not self._enabled:
            return

        # 只要存在冲突（施法中 / 游戏中 / 拖拽中 / 跳跃中 …）
        # 无论当前是 WALKING / FACING / ACTING / REACTING，都立刻暂停，
        # 避免在 spell casting 期间切 look_up / act 等动画打断施法。
        if self._has_conflict():
            if self.state in (AgentState.WALKING, AgentState.FACING,
                              AgentState.ACTING, AgentState.REACTING):
                # 修复：记录暂停前状态，以便恢复时继续而不是取消任务
                self._pre_pause_state = self.state
                # WALKING 时记录实际目标坐标（宠物可能被拖走，恢复时需要重新 walk_to）
                if self.state == AgentState.WALKING and self.current_task is not None:
                    try:
                        pos = self._get_pos()
                        # 从主移动系统获取当前目标（如果有），否则用任务目标
                        owner = getattr(self._desktop, 'parent', None)
                        if owner is not None and hasattr(owner, 'target_pos') and owner.target_pos:
                            self._pre_pause_walk_target = (owner.target_pos.x(), owner.target_pos.y())
                        else:
                            tx, ty = self.current_task.target.center()
                            self._pre_pause_walk_target = (tx, ty)
                    except Exception:
                        self._pre_pause_walk_target = None
                self.state = AgentState.PAUSED
            return

        if self.state == AgentState.IDLE:
            self._maybe_decide(now)
        elif self.state == AgentState.PAUSED:
            if not self._has_conflict():
                # 修复：从暂停恢复时回到之前的状态，而不是直接变 IDLE
                self._resume_from_pause(now)
        elif self.state == AgentState.WALKING:
            # 修复：WALKING 无超时兜底——自主代理的目标落点（target.center()+随机偏移）
            # 不做屏幕 clamp，而主移动系统会把宠物夹回主屏内，导致边缘/多屏目标
            # 永远走不到、notify_arrived 永不触发 → 永久卡 WALKING。任务从决策开始
            # 18 秒内未到达则放弃本轮，回到 IDLE 稍后再决策。
            if now - self._task_started_at > 18.0:
                print("[agent] WALKING 超时，放弃本轮任务")
                self._finish_task()
            else:
                self._check_arrived(now)
        elif self.state == AgentState.FACING:
            if now - self.current_task.facing_start >= self._facing_duration:
                self._enter_acting(now)
        elif self.state == AgentState.ACTING:
            if now - self.current_task.acting_start >= self._acting_duration:
                self._enter_reacting(now)
        elif self.state == AgentState.REACTING:
            if now - self.current_task.reaction_start >= self._reaction_duration:
                self._finish_task()

    def notify_arrived(self):
        """主窗口在到达 target_pos 后调用。"""
        if self.state == AgentState.WALKING:
            self._enter_facing(time.time())

    def notify_position_changed(self, new_x: float, new_y: float):
        """主窗口每次窗口位置更新后调用（可选）。"""
        if self.state == AgentState.WALKING and self.current_task is not None:
            # 位置变化意味着主窗口还在移动中，让 _check_arrived 来处理
            pass

    def suspend(self):
        """主窗口检测到冲突（用户拖拽等）时调用。"""
        if self.is_busy():
            self._pre_pause_state = self.state
            # WALKING 时记录目标坐标，恢复时需要重新发起移动
            if self.state == AgentState.WALKING and self.current_task is not None:
                try:
                    owner = getattr(self._desktop, 'parent', None)
                    if owner is not None and hasattr(owner, 'target_pos') and owner.target_pos:
                        self._pre_pause_walk_target = (owner.target_pos.x(), owner.target_pos.y())
                    else:
                        tx, ty = self.current_task.target.center()
                        self._pre_pause_walk_target = (tx, ty)
                except Exception:
                    self._pre_pause_walk_target = None
            self.state = AgentState.PAUSED
        elif self.state == AgentState.IDLE:
            self._pre_pause_state = AgentState.IDLE
            self.state = AgentState.PAUSED

    def resume(self):
        if self.state == AgentState.PAUSED and not self._has_conflict():
            self._resume_from_pause(time.time())

    # ---- 内部状态机 ----

    def _has_conflict(self) -> bool:
        flags = self._get_busy()
        return any(flags.values())

    def _maybe_decide(self, now: float):
        if self._has_conflict():
            return
        if now - self._last_decision_time < self._decision_interval:
            return
        self._last_decision_time = now

        # F: 桌面文件太多（>25 个）且距上次整理 > 30 分钟 → 主动整理
        # 注意：organize_desktop 现为安全实现（不自动移动用户文件，返回 (0,0)），
        # 因此不会真的整理；这里保持不打扰（moved==0 时不再说"整理好了"误导用户）。
        if now - self._last_organize_time > 1800:
            try:
                file_count = self._desktop.get_desktop_file_count()
                if file_count > 25:
                    self._last_organize_time = now
                    moved, skipped = self._desktop.organize_desktop()
                    if moved > 0:
                        self._show_dialogue(
                            "ralsei",
                            f"桌面有点乱呢~我整理了 {moved} 个文件！",
                            "happy")
                    # moved == 0：静默（不误导用户说"整理好了"）
                    return  # 整理完本轮不再选目标
            except Exception:
                pass

        target = self._pick_target()
        if target is None:
            return

        action = self._pick_action(target)
        # 修复：OPEN 动作冷却——避免自主代理频繁打开文件/文件夹（"打开太频繁"）。
        # 90 秒内只允许打开一次；冷却期内改选"只观察不打开"的动作。
        if action == InteractionType.OPEN:
            if now - getattr(self, '_last_open_time', 0.0) < 90.0:
                action = random.choice([InteractionType.EXAMINE, InteractionType.OBSERVE])
            else:
                self._last_open_time = now
        task = AutonomousTask(target=target, action=action)

        # 特定动作的额外参数
        if action == InteractionType.DRAG:
            task.drag_to = self._pick_destination()
        elif action == InteractionType.RESIZE_WINDOW:
            scale = random.choice([0.8, 0.9, 1.1, 1.2])
            task.new_width = int(target.width * scale)
            task.new_height = int(target.height * scale)

        self.current_task = task
        self._enter_walking(now)

    def _pick_target(self) -> Optional[InteractionTarget]:
        """从桌面/窗口中随机选一个目标。已过滤回收站（Ralsei 害怕它）。"""
        candidates: List[InteractionTarget] = []

        # 桌面图标
        try:
            elements = getattr(self._desktop, "desktop_elements", [])
            for el in elements[:30]:
                name = el.get("name", "未命名")
                path = el.get("path") or ""
                # E: 回避回收站（名称或路径匹配）
                if name in ("回收站", "Recycle Bin", "$RECYCLE.BIN"):
                    continue
                if "recycle" in path.lower() or "$recycle" in path.lower():
                    continue
                candidates.append(InteractionTarget(
                    kind=el.get("type", "file"),
                    name=name,
                    path=path,
                    x=el.get("x", 0),
                    y=el.get("y", 0),
                    width=el.get("width", 40),
                    height=el.get("height", 40),
                ))
        except Exception:
            pass

        # 可见窗口
        try:
            windows = self._desktop.get_all_visible_windows()
            for w in windows[:15]:
                # 注意：get_all_visible_windows 的 'rect' 是 tuple (left, top, right, bottom)，
                # 不能对 tuple 调 .get()（AttributeError 会被吞掉导致所有窗口目标失效）。
                # 窗口字典顶层已提供 x/y/width/height，直接使用。
                candidates.append(InteractionTarget(
                    kind="window",
                    name=w.get("title", "未命名窗口"),
                    hwnd=w.get("hwnd"),
                    x=w.get("x", 0),
                    y=w.get("y", 0),
                    width=w.get("width", 200),
                    height=w.get("height", 200),
                ))
        except Exception:
            pass

        if not candidates:
            return None

        # 优先选离宠物较近的目标
        my_pos = self._get_pos()
        my_x, my_y = float(my_pos.x()), float(my_pos.y())
        scored = []
        for c in candidates:
            cx, cy = c.center()
            dist = math.hypot(cx - my_x, cy - my_y)
            score = 1.0 / (dist + 100)
            # 文件比窗口更有趣
            if c.kind in ("file", "folder"):
                score *= 2.0
            scored.append((score + random.random() * 0.3, c))
        scored.sort(key=lambda x: -x[0])
        return scored[0][1]

    def _pick_action(self, target: InteractionTarget) -> InteractionType:
        """根据目标类型和宠物情绪选择动作。"""
        emotion = ""
        try:
            # 修复：desktop_interaction 没有 emotion_system 属性（在 RalseiPet 上），
            # 原代码 AttributeError 被吞 → emotion 恒为 "" → 害羞/平静的行为分支永不生效。
            # 通过 desktop_interaction.parent 访问主对象上的情绪系统。
            owner = getattr(self._desktop, 'parent', None)
            if owner is not None and hasattr(owner, 'emotion_system'):
                e, _ = owner.emotion_system.get_current_emotion()
                emotion = e
        except Exception:
            pass

        if target.kind == "window":
            # 修复：自主代理不再自动关闭/最小化/缩放用户窗口——随机选中的窗口可能
            # 是用户正在编辑/浏览的窗口，自动关掉会打断用户工作（每 ~45 秒 75% 概率
            # 触发过强）。窗口的破坏性操作只保留给用户明确指令（handle_window_operation）。
            # 自主代理对窗口只做"观察"（走过去看看 + 评论），不执行关闭/缩放。
            return InteractionType.OBSERVE
        elif target.kind == "folder":
            # 修复：移除 DRAG——后台"拖拽"到屏幕坐标没有目录语义，且安全实现不真移动，
            # 保留会变成"假装拖了"的假动作。自主代理对文件夹只做 观察/打开/查看。
            choices = [InteractionType.OPEN, InteractionType.OBSERVE, InteractionType.EXAMINE]
            if emotion in ("shy", "peaceful"):
                choices = [InteractionType.OBSERVE, InteractionType.OPEN]
            return random.choice(choices)
        else:  # file
            # 修复：移除 DELETE——需求要求"删除文件需要找用户确认"，
            # 自主代理不应自动删除用户文件（原代码会直接送回收站，仍可能误删）。
            # 移除 DRAG——同上，后台拖拽无目录语义且安全实现不真移动。
            choices = [InteractionType.OPEN, InteractionType.EXAMINE, InteractionType.OBSERVE]
            if emotion in ("shy", "peaceful"):
                choices = [InteractionType.EXAMINE, InteractionType.OPEN]
            return random.choice(choices)

    def _pick_destination(self) -> tuple:
        """随机选一个拖拽目标位置（屏幕内）。"""
        try:
            screen_w = self._desktop.screen_width or 1920
            screen_h = self._desktop.screen_height or 1080
        except Exception:
            screen_w, screen_h = 1920, 1080
        x = random.randint(100, screen_w - 200)
        y = random.randint(100, screen_h - 200)
        return (float(x), float(y))

    # ---- 状态转移 ----

    def _enter_walking(self, now: float):
        t = self.current_task
        self.state = AgentState.WALKING
        # 修复：记录任务开始时间，供 tick() 的 WALKING 超时兜底（now - _task_started_at > 18s）
        # 使用。此前该字段只在 __init__ 置 0.0、从不更新 → 程序运行 18 秒后每次进入
        # WALKING 都会被误判超时并立即 _finish_task()，导致 FACING/ACTING/动作执行不可达。
        self._task_started_at = now

        # 走到目标"近旁"而不是正中间（给 FACING 阶段留位置）
        # 选一个在目标右下角或左下/右上附近的点
        tx, ty = t.target.center()
        offsets = [(-80, 40), (80, 40), (-60, -60), (60, -60)]
        ox, oy = random.choice(offsets)
        self._walk_to(tx + ox, ty + oy)

        # 说话
        templates = ACTION_DIALOGUES[t.action]["start"]
        self._show_dialogue("ralsei", random.choice(templates).format(name=t.target.name),
                            self._mood_for_action(t.action))

        self._add_emotion("curious", 10)

    def _enter_facing(self, now: float):
        self.state = AgentState.FACING
        t = self.current_task
        t.facing_start = now

        # 面向目标方向（用 walk_<dir> 动画表示朝向）
        my_pos = self._get_pos()
        dx = t.target.x + t.target.width / 2 - my_pos.x()
        dy = t.target.y + t.target.height / 2 - my_pos.y()
        if abs(dx) > abs(dy):
            facing = "right" if dx > 0 else "left"
        else:
            facing = "down" if dy > 0 else "up"
        self._change_anim(f"walk_{facing}", force=True)

        self._play_once("look_up")

    def _enter_acting(self, now: float):
        self.state = AgentState.ACTING
        t = self.current_task
        t.acting_start = now

        # 播放交互动作帧
        if t.action in (InteractionType.OPEN, InteractionType.EXAMINE):
            self._play_once("act")
        elif t.action == InteractionType.DRAG:
            self._play_once("roll")
        elif t.action == InteractionType.DELETE:
            self._play_once("surprised")
        elif t.action in (InteractionType.CLOSE_WINDOW, InteractionType.MINIMIZE_WINDOW):
            self._play_once("look_up")
        elif t.action == InteractionType.RESIZE_WINDOW:
            self._play_once("pose")

        # 在后台执行实际操作（不碰鼠标）
        self._execute_action(t)

    def _enter_reacting(self, now: float):
        self.state = AgentState.REACTING
        t = self.current_task
        t.reaction_start = now

        templates = ACTION_DIALOGUES[t.action]["done"]
        self._show_dialogue("ralsei", random.choice(templates).format(name=t.target.name),
                            self._mood_for_action(t.action))
        self._add_emotion("happy", 10)

    def _finish_task(self):
        self.current_task = None
        self.state = AgentState.IDLE

    def _resume_from_pause(self, now: float):
        """从暂停恢复：回到暂停前的状态继续执行，而不是取消任务。"""
        prev = self._pre_pause_state
        if prev == AgentState.WALKING:
            # WALKING：宠物可能被拖到新位置，需要重新发起移动
            if self.current_task is not None and self._pre_pause_walk_target:
                tx, ty = self._pre_pause_walk_target
                self.state = AgentState.WALKING
                # 重置开始时间，避免刚恢复就触发超时（因为暂停期间计时仍在走）
                self._task_started_at = now
                try:
                    self._walk_to(tx, ty)
                except Exception:
                    # 移动失败就放弃本轮
                    self._finish_task()
            else:
                # 没有任务或目标，直接回 IDLE
                self.state = AgentState.IDLE
        elif prev in (AgentState.FACING, AgentState.ACTING, AgentState.REACTING):
            # 这些阶段是计时的，暂停期间时间仍在流逝 → 把起始时间往后推"暂停时长"
            # 简化处理：重置阶段起始时间为 now，给足完整的阶段时长
            t = self.current_task
            if t is not None:
                if prev == AgentState.FACING:
                    t.facing_start = now
                elif prev == AgentState.ACTING:
                    t.acting_start = now
                elif prev == AgentState.REACTING:
                    t.reaction_start = now
                self.state = prev
            else:
                self.state = AgentState.IDLE
        else:
            # 本来就是 IDLE 或异常状态，直接回 IDLE
            self.state = AgentState.IDLE

        self._pre_pause_walk_target = None
        self._pre_pause_state = AgentState.IDLE

    # ---- 动作执行（后台 API，零鼠标劫持）----

    def _execute_action(self, task: AutonomousTask):
        d = self._desktop
        t = task
        try:
            if t.action == InteractionType.OPEN:
                if t.target.kind == "folder":
                    d.open_folder(t.target.path)
                elif t.target.path:
                    d.open_file(t.target.path)

            elif t.action == InteractionType.DRAG:
                if t.target.kind in ("file", "folder") and t.target.path and t.drag_to:
                    d.drag_file_background(t.target.path, t.drag_to)

            elif t.action == InteractionType.DELETE:
                if t.target.path:
                    d.delete_file(t.target.path, confirm=False, send_to_recycle=True)

            elif t.action == InteractionType.CLOSE_WINDOW:
                if t.target.hwnd:
                    d.close_window_by_hwnd(t.target.hwnd)

            elif t.action == InteractionType.MINIMIZE_WINDOW:
                if t.target.hwnd:
                    d.minimize_window_by_hwnd(t.target.hwnd)

            elif t.action == InteractionType.RESIZE_WINDOW:
                if t.target.hwnd and t.new_width and t.new_height:
                    d.resize_window_by_hwnd(t.target.hwnd, t.new_width, t.new_height)

            elif t.action == InteractionType.EXAMINE:
                if t.target.path:
                    preview = d.get_file_content_preview(t.target.path, max_lines=3)
                    if preview:
                        self._show_dialogue("ralsei",
                                            f"让我看看{preview[:60]}...", "curious")

        except Exception as e:
            print(f"[AutonomousAgent] 动作执行失败: {e}")

    # ---- 辅助 ----

    def _walk_to(self, x: float, y: float):
        self._set_target_pos(int(x), int(y))

    def _check_arrived(self, now: float):
        """检查是否到达目标，同时跟踪目标变化（D: 追文件 skill）。"""
        task = self.current_task
        if task is None:
            return

        # D: 文件/文件夹目标 —— 检查是否还存在、是否被移动
        tgt = task.target
        if tgt.kind in ("file", "folder") and tgt.path:
            path_still_exists = os.path.exists(tgt.path)
            if not path_still_exists:
                # 目标被删除了 → 放弃这次行动，回到 IDLE
                self._show_dialogue(
                    "ralsei", f"诶？{tgt.name} 不见了...", "normal")
                self._finish_task()
                return
            # 文件还在，看看是否被移动了位置
            try:
                elements = getattr(self._desktop, "desktop_elements", [])
                for el in elements:
                    if el.get("path") == tgt.path:
                        new_x = el.get("x", tgt.x)
                        new_y = el.get("y", tgt.y)
                        if abs(new_x - tgt.x) > 30 or abs(new_y - tgt.y) > 30:
                            # 位置变了 → 更新目标坐标，继续追
                            tgt.x = new_x
                            tgt.y = new_y
                            tx, ty = tgt.center()
                            offsets = [(-80, 40), (80, 40), (-60, -60), (60, -60)]
                            ox, oy = random.choice(offsets)
                            self._walk_to(tx + ox, ty + oy)
                        break
            except Exception:
                pass

        my_pos = self._get_pos()
        tc = self.current_task.target.center()
        dx = my_pos.x() - tc[0]
        dy = my_pos.y() - tc[1]
        dist = math.hypot(dx, dy)
        if dist < self._reach_threshold:
            self._enter_facing(now)

    @staticmethod
    def _mood_for_action(action: InteractionType) -> str:
        mapping = {
            InteractionType.OPEN: "happy",
            InteractionType.DRAG: "playful",
            InteractionType.DELETE: "determined",
            InteractionType.EXAMINE: "curious",
            InteractionType.OBSERVE: "curious",
            InteractionType.CLOSE_WINDOW: "peaceful",
            InteractionType.RESIZE_WINDOW: "curious",
            InteractionType.MINIMIZE_WINDOW: "peaceful",
        }
        return mapping.get(action, "happy")
