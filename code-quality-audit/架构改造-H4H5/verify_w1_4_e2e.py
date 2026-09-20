# -*- coding: utf-8 -*-
"""W1-4 校验 · e2e 行为级 —— 真起 QApplication + 真 RalseiPet，逐条跑视频链路。

为什么必须有这个探针（**最贵的那条教训**）
------------------------------------------
W1-3 搬完游戏控制器后，G2（24 套件 / 1057 断言）**全绿**，但真机一起就
`RecursionError` 崩在**构造期** —— G2 对游戏/视频**零覆盖**。
「方法体逐字等价」≠「产品还能跑」：等价只保证"这段代码没被改坏"，
不保证"宿主 + 控制器的**转发链**接得上"（`__getattr__` 成环、挂载时机不对、
属性落到错的实例上…… 全是等价断言看不见的）。

所以本探针**自己建一个最小宿主**（不 import main.py，避免它 `sys.exit` /
建托盘 / 连单实例互斥），把 `VideoController` 挂上去，逐条跑真实方法：
  1. 构造期不递归、不炸；
  2. `check_video_apps` 的 3 个分支（有窗口 50% / 无窗口 30% / 什么都不做）；
  3. `start_watching_video`：状态写入宿主 + 定位 + 面向 + 起 5s 定时器；
  4. `_update_video_watching` 的 3 个分支（没在看不看 / 深夜关闭 / 随机反应）；
  5. `stop_watching_video`：结算时长 + 写历史 + 恢复移动 + 停表；
  6. `suggest_watching_video`：提议 + 打开浏览器 + 起表；
  7. 深夜分支里 `self.close_bilibili()` / `self.enter_sleep_mode()` 必须
     **经宿主回落**拿到（这是"未搬方法仍可用"的行为级证明）；
  8. `_log_()` 拿到的必须是**宿主模块的同一个 logger 对象**。

桩的口径：**跟着真实方法面走**（这是踩过 4 次的坑）—— 桩上只给方法体真的会碰的
东西，多给一个都会掩盖"回落链断了"。
"""
import ast
import io
import os
import sys
import types
import logging

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
sys.path.insert(0, os.path.join(ROOT, "ralsei_pet"))
sys.path.insert(0, os.path.join(ROOT, "ralsei_pet", "src"))

FAILS, PASSES = [], []


def check(name, cond, detail=""):
    if cond:
        PASSES.append(name); print("  PASS  %s" % name)
    else:
        FAILS.append((name, detail)); print("  FAIL  %s   %s" % (name, detail))


# 关掉 Qt 的离屏噪音（无字体 / 无显示器）
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMainWindow  # noqa: E402
from PyQt5.QtCore import QTimer, QRect  # noqa: E402

from modules.video_controller import VideoController  # noqa: E402


# ---------------------------------------------------------------------------
# 假 Qt 宿主 QMainWindow 太多重（要真 QApplication）→ 用真 QMainWindow 但最小化
# ---------------------------------------------------------------------------
class FakeDialogueUI(object):
    def __init__(self):
        self.lines = []
        self.shown = 0
        self.visible = True
        self.is_typing = False

    def add_dialogue(self, speaker, msg, face=None):
        self.lines.append((speaker, msg, face))

    def show_dialogue(self):
        self.shown += 1

    def isVisible(self):
        return self.visible


class FakeDesktop(object):
    def __init__(self, windows=None, bili=True):
        self.windows = windows if windows is not None else []
        self.bili = bili
        self.opened = []
        self.resized = 0
        self.closed = []

    def get_all_visible_windows(self):
        return list(self.windows)

    def open_browser(self, url, new_window=False):
        self.opened.append((url, new_window))

    def move_and_resize_bilibili_window(self):
        self.resized += 1

    def close_window(self, title):
        self.closed.append(title)


class FakeEmotion(object):
    def __init__(self):
        self.calls = []

    def add_emotion(self, e, v=0):
        self.calls.append((e, v))


class FakeAiDriver(object):
    def __init__(self):
        self.events = []

    def note_event(self, *a):
        self.events.append(a)


class Host(QMainWindow):
    """最小宿主：与 main.py 的 RalseiPet 同构 —— 同款 __getattr__ 转发壳。"""

    _CONTROLLER_ATTRS = ('games', 'video')

    def __init__(self, windows=None):
        super().__init__()
        # 通用状态
        self.is_sleeping = False
        self.is_moving = False
        self.is_jumping = False
        self.is_falling = False
        self.idle_timer = 0
        self.max_idle_duration = 0
        self.current_direction = "down"
        self.current_window = None
        self.last_window_rect = None
        self.window_level = 0
        self.target_pos = None
        # 视频状态（**留在宿主**，与 main.py 一致）
        self.is_watching_video = False
        self.video_start_time = 0
        self.video_duration = 0
        self.current_video_url = ""
        self.video_platform = ""
        self.video_title = ""
        self.video_watch_history = []
        self.video_preferences = ["游戏", "动画", "音乐", "科普", "搞笑", "Deltarune", "Undertale"]
        # 预声明为 None —— **必须与 main.py 同构**：控制器的 __setattr__ 只把赋值转给
        # 宿主「已经拥有」的名字；不预声明 → 首次赋值会落在控制器上、状态被劈成两份。
        self.video_watching_timer = None
        # 协作对象
        self.dialogue_ui = FakeDialogueUI()
        self.desktop_interaction = FakeDesktop(windows)
        self.emotion_system = FakeEmotion()
        self.ai_driver = FakeAiDriver()
        self.anim_calls = []

        # 挂控制器（**必须在状态之后** —— 与 main.py 的时机一致）
        self.video = VideoController(self)

    # --- 宿主侧转发壳（与 main.py 的 __getattr__ 逐字同构） ---
    def __getattr__(self, name):
        for attr in Host._CONTROLLER_ATTRS:
            ctrl = self.__dict__.get(attr)
            if ctrl is None:
                continue
            impl = getattr(type(ctrl), name, None)
            if impl is not None:
                return getattr(ctrl, name)
        raise AttributeError(name)

    # --- 宿主能力（被控制器方法体引用） ---
    def move(self, x, y):
        self._pos = (x, y)

    def _clamp_pos_to_desktop(self, x, y):
        return (x, y)

    def change_animation(self, name, force=False):
        self.anim_calls.append((name, force))

    def randomize_movement_pattern(self):
        # 真实实现会写 max_idle_duration —— 桩照做，才能验"恢复移动"真的发生
        self.max_idle_duration = 1.234

    def enter_sleep_mode(self):
        # **未搬方法**：必须经宿主回落被调到
        self.is_sleeping = True
        self.is_watching_video = False
        self.max_idle_duration = 3600.0

    def close_bilibili(self):
        # **未搬方法**：同上
        for w in self.desktop_interaction.get_all_visible_windows():
            if any(k in w["title"] for k in ["哔哩哔哩", "B站", "bilibili"]):
                self.desktop_interaction.close_window(w["title"])
                break

    def width(self):
        return 128

    def height(self):
        return 128


def W(title, x=100, y=100, w=800, h=600, z=5):
    return {"title": title, "x": x, "y": y, "width": w, "height": h, "z_order": z,
            "class_name": "Chrome_WidgetWin_1"}


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    print("=" * 72)
    print("W1-4 e2e · 1 构造期（转发生死线）")
    print("=" * 72)
    try:
        host = Host([W("哔哩哔哩 - 首页")])
        check("真构造函数不炸（无 RecursionError）", True)
    except RecursionError as e:
        check("真构造函数不炸（无 RecursionError）", False, str(e)[:120])
        return 1
    check("控制器已挂载", host.__dict__.get("video") is not None)

    print("-" * 72)
    print("W1-4 e2e · 2 宿主 → 控制器 转发（8 个方法名全部可达）")
    print("-" * 72)
    for n in ["check_video_apps", "identify_video_apps", "start_watching_video",
              "_start_video_watching_loop", "_update_video_watching", "_react_to_video",
              "stop_watching_video", "suggest_watching_video"]:
        check("host.%s 可达且绑定控制器" % n,
              callable(getattr(host, n)) and getattr(host, n).__self__ is host.__dict__["video"])

    print("-" * 72)
    print("W1-4 e2e · 3 identify_video_apps（关键词 / 类名两条分支）")
    print("-" * 72)
    h2 = Host([W("哔哩哔哩 - 首页"), W("记事本"), W("音乐", z=3)])
    apps = h2.identify_video_apps()
    check("按标题关键词命中 B站", [a["title"] for a in apps] == ["哔哩哔哩 - 首页"],
          "实际 %r" % ([a["title"] for a in apps],))
    h3 = Host([{"title": "Unknown", "x": 0, "y": 0, "width": 1, "height": 1,
                "z_order": 1, "class_name": "VLC media player"}])
    check("按 class_name 命中播放器", len(h3.identify_video_apps()) == 1,
          "实际 %r" % (h3.identify_video_apps(),))
    h4 = Host([W("记事本"), W("计算器")])
    check("非视频窗口 → 空列表", h4.identify_video_apps() == [])

    print("-" * 72)
    print("W1-4 e2e · 4 start_watching_video（状态 / 定位 / 面向 / 定时器）")
    print("-" * 72)
    h5 = Host([])
    app_rect = W("哔哩哔哩 - 影视", x=200, y=150, w=900, h=700, z=7)
    h5.start_watching_video(dict(app_rect))
    check("is_watching_video → True", h5.is_watching_video is True)
    check("video_start_time 已写", h5.video_start_time > 0)
    check("video_platform == 窗口标题", h5.video_platform == "哔哩哔哩 - 影视")
    check("video_title 非空", bool(h5.video_title))
    check("video_watch_history 追加 1 条", len(h5.video_watch_history) == 1)
    check("history 条目标题与 video_title 一致",
          h5.video_watch_history[0]["title"] == h5.video_title)
    check("current_window / last_window_rect / window_level 已更新",
          h5.current_window is not None and h5.last_window_rect is not None
          and h5.window_level == 7)
    check("is_moving 被暂停（专注观看）", h5.is_moving is False)
    check("max_idle_duration 落在 10~30", 10 <= h5.max_idle_duration <= 30,
          "实际 %s" % h5.max_idle_duration)
    check("change_animation 被调用", bool(h5.anim_calls))
    check("B站窗口触发 move_and_resize", h5.desktop_interaction.resized == 1)
    check("video_watching_timer 已建且 active（5s）",
          hasattr(h5, "video_watching_timer")
          and h5.video_watching_timer.isActive()
          and h5.video_watching_timer.interval() == 5000)
    check("定时器落在**宿主**实例字典上（状态不搬）",
          "video_watching_timer" in h5.__dict__)
    check("定时器连接到控制器的方法",
          h5.video_watching_timer.receivers(h5.video_watching_timer.timeout) > 0
          if hasattr(h5.video_watching_timer, "receivers") else True)

    print("-" * 72)
    print("W1-4 e2e · 5 历史条数上限 20 的裁剪")
    print("-" * 72)
    h6 = Host([])
    for i in range(25):
        h6.start_watching_video(dict(app_rect))
    check("video_watch_history 上限 20", len(h6.video_watch_history) == 20,
          "实际 %d" % len(h6.video_watch_history))

    print("-" * 72)
    print("W1-4 e2e · 6 _update_video_watching 的三个分支")
    print("-" * 72)
    # 6a：没在观看 → 停表返回
    h7 = Host([])
    h7.start_watching_video(dict(app_rect))
    h7.is_watching_video = False
    h7._update_video_watching()
    check("6a 未观看 → 定时器被停", not h7.video_watching_timer.isActive())

    # 6b：深夜 → 停止观看 + 关 B站 + 进睡眠（**两个未搬方法走宿主回落**）
    h8 = Host([W("哔哩哔哩 - 电影")])
    h8.start_watching_video(dict(W("哔哩哔哩 - 电影")))
    before_lines = len(h8.dialogue_ui.lines)
    import time as _t
    real_strftime = _t.strftime
    _t.strftime = lambda fmt, *a: "23" if fmt == "%H" else "30"
    try:
        h8._update_video_watching()
    finally:
        _t.strftime = real_strftime
    check("6b 深夜 → is_watching_video False", h8.is_watching_video is False)
    check("6b 深夜 → close_bilibili（宿主未搬方法）真的执行了",
          h8.desktop_interaction.closed == ["哔哩哔哩 - 电影"],
          "实际 %r" % (h8.desktop_interaction.closed,))
    check("6b 深夜 → enter_sleep_mode（宿主未搬方法）真的执行了",
          h8.is_sleeping is True and h8.max_idle_duration == 3600.0)
    check("6b 深夜 → 多了一条晚安台词", len(h8.dialogue_ui.lines) > before_lines)

    # 6c：白天 + 10% 概率命中 → _react_to_video（台词 + 情绪 + 上报 AI）
    h9 = Host([])
    h9.start_watching_video(dict(W("哔哩哔哩 - 动画")))
    import random as _r
    real_random = _r.random
    _r.random = lambda: 0.05      # < 0.1 → 必触发反应
    try:
        n0 = len(h9.dialogue_ui.lines)
        e0 = len(h9.emotion_system.calls)
        h9._update_video_watching()
    finally:
        _r.random = real_random
    check("6c 白天 + 命中 → _react_to_video 出了台词",
          len(h9.dialogue_ui.lines) == n0 + 1)
    check("6c 白天 + 命中 → emotion_system.add_emotion 被调",
          len(h9.emotion_system.calls) == e0 + 1)
    check("6c 上报 AI note_event",
          len(h9.ai_driver.events) == 1
          and h9.ai_driver.events[0][0] == "我正在陪主人一起看视频",
          "实际 %r" % (h9.ai_driver.events,))
    # 6c-：白天 + 没命中 → 什么都不做
    h10 = Host([])
    h10.start_watching_video(dict(W("哔哩哔哩 - 动画")))
    _r.random = lambda: 0.5
    try:
        n1 = len(h10.dialogue_ui.lines)
        h10._update_video_watching()
    finally:
        _r.random = real_random
    check("6c- 白天 + 未命中 → 无新台词", len(h10.dialogue_ui.lines) == n1)

    print("-" * 72)
    print("W1-4 e2e · 7 stop_watching_video（结算 / 恢复 / 停表）")
    print("-" * 72)
    h11 = Host([])
    h11.start_watching_video(dict(W("哔哩哔哩 - 剧集")))
    h11.video_start_time -= 42.0     # 假装看了 42 秒
    h11.stop_watching_video()
    check("7 is_watching_video → False", h11.is_watching_video is False)
    check("7 历史末条 duration 结算为 ~42s",
          abs(h11.video_watch_history[-1]["duration"] - 42.0) < 1.0,
          "实际 %s" % h11.video_watch_history[-1]["duration"])
    # ⚠️ 别断 `== 1.234`（桩里 randomize 写的那个值）：真实方法体**紧接着**自己又写了一次
    #    `self.max_idle_duration = random.uniform(0.5, 3.0)`，会覆盖桩的值。
    #    要断的是**区间**（方法体声明的语义），不是桩留下的痕迹 ——
    #    「断言断行为不断赋值/不断痕迹」。
    check("7 max_idle_duration 落在 0.5~3.0（方法体自己声明的恢复值）",
          0.5 <= h11.max_idle_duration <= 3.0, "实际 %s" % h11.max_idle_duration)
    check("7 is_moving → True（恢复移动）", h11.is_moving is True)
    check("7 定时器已停", not h11.video_watching_timer.isActive())
    check("7 出了一句结束台词", any("视频" in l[1] or "看完" in l[1] for l in h11.dialogue_ui.lines))
    # 7-：没在观看时调用 → 无副作用（不崩、不改历史）
    h12 = Host([])
    h12.stop_watching_video()
    check("7- 未观看时调用是安全的 no-op", h12.is_watching_video is False)

    print("-" * 72)
    print("W1-4 e2e · 8 suggest_watching_video（提议 + 打开 + 起表）")
    print("-" * 72)
    h13 = Host([])
    _r.random = lambda: 0.1     # <0.5 → 直接打开
    try:
        h13.suggest_watching_video()
    finally:
        _r.random = real_random
    check("8 打开 B站热门页（新窗口）",
          h13.desktop_interaction.opened == [("https://www.bilibili.com/v/popular/all", True)],
          "实际 %r" % (h13.desktop_interaction.opened,))
    check("8 move_and_resize 被调", h13.desktop_interaction.resized == 1)
    check("8 is_watching_video → True", h13.is_watching_video is True)
    check("8 video_title == 'B站热门视频'", h13.video_title == "B站热门视频")
    check("8 max_idle_duration 落在 30~90", 30 <= h13.max_idle_duration <= 90,
          "实际 %s" % h13.max_idle_duration)
    check("8 观看循环已启动", h13.video_watching_timer.isActive())
    # 8b：已有失效的表 → 走 elif 分支续跑（覆盖 hasattr/None 两条路径）
    h13.video_watching_timer.stop()
    _r.random = lambda: 0.1
    try:
        h13.suggest_watching_video()
    finally:
        _r.random = real_random
    check("8b 停掉的表被重新 start", h13.video_watching_timer.isActive())
    # 8c：没命中 0.5 → 只提议不开浏览器
    h14 = Host([])
    _r.random = lambda: 0.9
    try:
        h14.suggest_watching_video()
    finally:
        _r.random = real_random
    check("8c 未命中 → 不开浏览器", h14.desktop_interaction.opened == [])
    check("8c 未命中 → 仍有一句提议台词", len(h14.dialogue_ui.lines) == 1)

    print("-" * 72)
    print("W1-4 e2e · 9 check_video_apps（分发三分支）")
    print("-" * 72)
    h15 = Host([W("哔哩哔哩 - 首页")])
    _r.random = lambda: 0.1   # choice 不受影响；0.1<0.5 → 开始看
    try:
        h15.check_video_apps()
    finally:
        _r.random = real_random
    check("9 有窗口 + 命中 → start_watching_video 生效", h15.is_watching_video is True)
    h16 = Host([])
    calls = {"n": 0}
    # ⚠️ 桩必须打在**控制器实例**上，不能打在宿主上：宿主 `__getattr__` 只在常规查找
    #    miss 时才转发，而 `suggest_watching_video` 在宿主的常规查找里本来就找不到
    #    （它已被摘除）→ 会走到控制器。往宿主 `__dict__` 里塞同名函数 = 常规查找直接
    #    命中那个桩，**控制器那份根本不会被调** → 探针假绿（"桩必须跟着真实方法面走"）。
    def fake_suggest():
        calls["n"] += 1
    h16.__dict__["video"].__dict__["suggest_watching_video"] = fake_suggest
    _r.random = lambda: 0.1   # 0.1 < 0.3 → 走 suggest
    try:
        h16.check_video_apps()
    finally:
        _r.random = real_random
    check("9 无窗口 + 命中 → 调 suggest_watching_video（控制器那份）", calls["n"] == 1,
          "实际 %d" % calls["n"])
    # 9b：无窗口 + 未命中 0.3 → 什么都不做
    h17 = Host([])
    calls2 = {"n": 0}
    h17.__dict__["video"].__dict__["suggest_watching_video"] = lambda: calls2.__setitem__("n", calls2["n"] + 1)
    _r.random = lambda: 0.9   # 0.9 > 0.3 → 不进 suggest
    try:
        h17.check_video_apps()
    finally:
        _r.random = real_random
    check("9b 无窗口 + 未命中 → 不调 suggest", calls2["n"] == 0, "实际 %d" % calls2["n"])
    # 9c：有窗口 + 未命中 0.5 → 不开始观看
    h18 = Host([W("哔哩哔哩 - 首页")])
    _r.random = lambda: 0.9
    try:
        h18.check_video_apps()
    finally:
        _r.random = real_random
    check("9c 有窗口 + 未命中 → 不开始观看", h18.is_watching_video is False)

    print("-" * 72)
    print("W1-4 e2e · 10 _log_() 必须拿到宿主模块的同一个 logger")
    print("=" * 72)
    # 让 Host 类所属模块带一个 _log，模拟 main.py
    this_mod = sys.modules[__name__]
    sentinel = logging.getLogger("w14.sentinel")
    this_mod._log = sentinel
    ctrl = host.__dict__["video"]
    check("_log_() 返回宿主模块的 logger 对象", ctrl._log_() is sentinel,
          "实际 %r" % (ctrl._log_(),))
    # 宿主模块没有 _log 时 → 退回控制器自己的 logger（不许抛）
    del this_mod._log
    check("宿主模块无 _log 时退回自身 logger",
          ctrl._log_() is logging.getLogger("modules.video_controller"),
          "实际 %r" % (ctrl._log_(),))

    print()
    print("=" * 72)
    print("结果：PASS %d / FAIL %d" % (len(PASSES), len(FAILS)))
    for n, d in FAILS:
        print("  FAIL %s  %s" % (n, d))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
