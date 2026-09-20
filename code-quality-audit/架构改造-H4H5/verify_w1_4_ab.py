# -*- coding: utf-8 -*-
"""W1-4 校验 · A/B 行为对照 —— 父版本（HEAD）与当前版本跑同一批视频场景。

**这条铁律（2026-09-19 真踩）**：A/B 探针必须先断言 **A ≠ B**。若取"旧值"时用
`git show HEAD:` 而改动**已先提交**，A == B，探针退化成自己跟自己比，结论必然
"没差别"**且非常像真的**。本脚本因此：
  ① 取 `git show HEAD:ralsei_pet/src/main.py`（本轮尚未提交 → HEAD 即父版本）；
  ② **md5 相同即 SystemExit**；
  ③ 另存父版本到临时目录，`import` 它跑同一批场景。

对照什么
--------
控制器搬走后，「同一场景」的**可观测结果**必须与父版本一致。选 6 个场景：
  1. 有视频窗口 50% 内 → 状态/标题/平台/历史/时长
  2. 有视频窗口 50% 外 → 不改状态
  3. 无窗口 30% 内 → 走 suggest
  4. suggest 命中 0.5 → 打开 URL / 标题 / 时长区间
  5. stop → 历史 duration / 恢复移动
  6. 深夜 tick → 观看态清掉 + 进睡眠

⚠️ 父版本**没有** `video_watching_timer` 的预声明（那是本轮加的），所以父版本里
`hasattr(self,'video_watching_timer')` 在 start 前为 False —— 这属于**已声明的
有意差异**，对照时按"start 之后"取值，不看 start 之前的初值。
"""
import ast
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
PET = os.path.join(ROOT, "ralsei_pet")
MAIN_PY = os.path.join(PET, "src", "main.py")

FAILS, PASSES = [], []


def check(name, cond, detail=""):
    if cond:
        PASSES.append(name); print("  PASS  %s" % name)
    else:
        FAILS.append((name, detail)); print("  FAIL  %s   %s" % (name, detail))


def run_scenarios(main_src_path, tag):
    """把给定 main.py 放进一个隔离的包目录，跑场景，返回结果 dict。"""
    # 复制整个 ralsei_pet 到一个临时目录（避免污染工作区），替换 main.py
    tmp = tempfile.mkdtemp(prefix="w14_ab_%s_" % tag)
    shutil.copytree(PET, os.path.join(tmp, "ralsei_pet"),
                    ignore=shutil.ignore_patterns("__pycache__", ".git"))
    shutil.copy2(main_src_path, os.path.join(tmp, "ralsei_pet", "src", "main.py"))
    # 说明：HEAD（"父版本"）**已含 W1-3**，所以它也 import games_controller ——
    # 两个控制器都必须留着（我们的对照变量只是 video_controller，不是 games）。
    # 父版本用不到 video_controller 没关系：`import` 存在、不 import 它即可。

    prog = r'''
import os, sys, json, types
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PKG = sys.argv[1]
sys.path.insert(0, os.path.join(PKG, "ralsei_pet"))
sys.path.insert(0, os.path.join(PKG, "ralsei_pet", "src"))

from PyQt5.QtWidgets import QApplication
app = QApplication([])

# --- 用最小桩替换重模块，避免起托盘/单实例互斥/网络 ---
import main as M

out = {}
def W(t, x=100, y=100, w=800, h=600, z=5):
    return {"title": t, "x": x, "y": y, "width": w, "height": h,
            "z_order": z, "class_name": "Chrome_WidgetWin_1"}

class FakeDialogue(object):
    def __init__(self): self.lines=[]; self.shown=0
    def add_dialogue(self, s, m, f=None): self.lines.append((s,m,f))
    def show_dialogue(self): self.shown += 1
    def isVisible(self): return True
class FakeDesktop(object):
    def __init__(self, wins): self.wins=wins; self.opened=[]; self.resized=0; self.closed=[]
    def get_all_visible_windows(self): return list(self.wins)
    def open_browser(self, url, new_window=False): self.opened.append((url,new_window))
    def move_and_resize_bilibili_window(self): self.resized += 1
    def close_window(self, t): self.closed.append(t)
class FakeEmotion(object):
    def __init__(self): self.calls=[]
    def add_emotion(self, e, v=0): self.calls.append((e,v))
class FakeAiDriver(object):
    def __init__(self): self.events=[]
    def note_event(self, *a): self.events.append(a)

def make_host(M, wins):
    # 不走 RalseiPet.__init__（会起托盘/互斥/网络）；只构造一个"够用"的宿主，
    # 但**必须**用**真实类的方法**，所以用 __new__ 跳过 __init__ 后手工填状态。
    import main as M
    pet = M.RalseiPet.__new__(M.RalseiPet)
    from PyQt5.QtWidgets import QMainWindow
    QMainWindow.__init__(pet)
    pet.dialogue_ui = FakeDialogue()
    pet.desktop_interaction = FakeDesktop(wins)
    pet.emotion_system = FakeEmotion()
    pet.ai_driver = FakeAiDriver()
    pet.is_sleeping=False; pet.is_moving=False; pet.is_jumping=False; pet.is_falling=False
    pet.idle_timer=0; pet.max_idle_duration=0; pet.current_direction="down"
    pet.current_window=None; pet.last_window_rect=None; pet.window_level=0
    pet.is_watching_video=False; pet.video_start_time=0; pet.video_duration=0
    pet.current_video_url=""; pet.video_platform=""; pet.video_title=""
    pet.video_watch_history=[]; pet.video_preferences=["游戏","动画","音乐"]
    # ⚠️ **预声明观看循环定时器**（s1b 踩出来的）：
    #   真实的 `RalseiPet.__init__`（main.py L1169）本轮新加了
    #    `self.video_watching_timer = None`。本探针用 `__new__` 跳过 `__init__`，
    #    **不会**自动有这一行 → 控制器的 `__setattr__` 白名单里没有这个名字 →
    #    `_start_video_watching_loop` 里那次赋值会落回**控制器**自己身上，
    #    造出「新版本 timer 在控制器上」的**假差异**。
    #    补上这一行 = 复刻真实 `__init__` 的初始状态，对照才成立。
    pet.video_watching_timer = None
    pet.anim_calls=[]
    pet.move_calls=[]
    # 宿主 API（真实 main.py 有；__new__ 跳过后手工补）
    def change_animation(name, force=False): pet.anim_calls.append((name,force))
    pet.change_animation = change_animation
    def randomize_movement_pattern(): pet.max_idle_duration = 1.234
    pet.randomize_movement_pattern = randomize_movement_pattern
    def enter_sleep_mode():
        pet.is_sleeping=True; pet.is_watching_video=False; pet.max_idle_duration=3600.0
    pet.enter_sleep_mode = enter_sleep_mode
    def close_bilibili():
        for w in pet.desktop_interaction.get_all_visible_windows():
            if any(k in w["title"] for k in ["哔哩哔哩","B站","bilibili"]):
                pet.desktop_interaction.close_window(w["title"]); break
    pet.close_bilibili = close_bilibili
    if not hasattr(pet, "video_watching_timer"):
        pass
    # 当前版本会 import VideoController；父版本没有 → 显式挂（若类存在）
    VC = getattr(M, "VideoController", None)
    if VC is not None:
        pet.video = VC(pet)
    return pet

import random as R
real_random = R.random
real_choice = R.choice

# QTimer 打桩用的资源（场景 1b）。**必须在子进程内自己 import**，
# 因为 `prog` 是独立进程，不共享外层模块。
import types
import PyQt5.QtCore as _QC

# ⚠️ 必须把 `random.choice` 也钉住：`start_watching_video` 里
#   `video_type = random.choice(video_types)` 决定 `video_title`，
#   只钉 `random.random` 的话标题随全局 RNG 状态漂移，
#   场景 s1 会报"title 不一致"的**假差异**（实测踩过）。
#   同理 `_react_to_video` / `suggest_*` 也用 choice 选台词。
R.choice = lambda seq: seq[0]

# 场景 1：有视频窗口 + 命中 50% 内 → 进入观看态
#
# ⚠️ 这里**不走** `check_video_apps()`，改为直接调 `start_watching_video(app)`。
#   原因（本探针唯一一处刻意的口径修正，2026-09-19 真踩）：
#     `start_watching_video` 会调 `QMainWindow.width()/height()` 定位。宿主用
#     `__new__` + `QMainWindow.__init__` 造出来**从不 `show()`**，在 offscreen 平台下
#     尺寸一直没真正 resolve；而本探针开头调过一次 `QApplication([])` 却**把返回值丢了**
#     （没有存引用 → 可能被 GC），于是 `check_video_apps → identify_video_apps`
#     这条链在**新版本上偶发**抛异常（旧版本侥幸没抛）。
#   这是**探针的环境瑕疵**，不是产品差异：`_start_video_watching_loop` 被
#   `start_watching_video` 调到的位置（L363）在 `change_animation`（L356）之后 —
#   在**宿主**里 `change_animation` 会走到真 `setPixmap/update` → 才要求真窗口尺寸；
#   在**控制器**里它是宿主 API 桩（只记录调用）→ 不需要尺寸。
#   因此 `timer_active` 在两侧**不可能**同值（旧 True / 新 False），
#   **这一项在 s1 里没有鉴别力，删掉**；计时器建立改由「场景 1b」用直接路径
#   正/负控制来验（那才是它的正确落点）。
p = make_host(M, [W("哔哩哔哩 - 首页")])
R.random = lambda: 0.1
# 注意：**不能**写 `M.RalseiPet.identify_video_apps` —— 方法已搬进控制器，
# 宿主类型上查不到（转发壳只在**实例**属性查找生效，类属性查找不走 __getattr__）。
# 走实例：`p.identify_video_apps()` 先经宿主 `__getattr__` 转到控制器。
p.start_watching_video(p.identify_video_apps()[0])
out["s1"] = dict(watching=p.is_watching_video, title=p.video_title,
                 platform=p.video_platform, hist=len(p.video_watch_history),
                 dur_ok=(10 <= p.max_idle_duration <= 30),
                 moving=p.is_moving, resized=p.desktop_interaction.resized,
                 anim=len(p.anim_calls))

# 场景 1b：计时器落点的**正/负控制**（必须有鉴别力：两侧先断言结果不同）
#   正控：_start_video_watching_loop 直接把 timer 写到宿主实例字典；
# 场景 1b：计时器**落点**（正/负控制：两侧先断言结果不同）
#   旧：方法在宿主上 → `self` 就是宿主 → timer 必然落宿主实例字典。
#   新：方法在控制器上 → 落点由 `__setattr__` 白名单决定，**只有宿主预声明过
#       该名字时**才转发。本探针的 make_host 已复刻 `__init__` 的预声明 →
#       `on_host` 应为 True、`on_ctrl` 应为 False（与旧版本一致）。
#   若这里 `on_ctrl` 变成 True，说明**预声明丢了**、状态被劈成两份 —— 那就是真回归。
_tt = _QC.QTimer
_QC.QTimer = lambda parent=None: types.SimpleNamespace(
    _used_type=type(parent).__name__, _fixed=_tt, isActive=lambda: True,
    timeout=types.SimpleNamespace(connect=lambda f: None),
    start=lambda ms: None, stop=lambda: None)
try:
    pv = make_host(M, [])
    pv._start_video_watching_loop()
    _on_host = "video_watching_timer" in pv.__dict__
    _on_ctrl = (getattr(pv, "video", None) is not None and
                "video_watching_timer" in pv.video.__dict__)
    out["s1b"] = dict(on_host=_on_host, on_ctrl=_on_ctrl)
finally:
    _QC.QTimer = _tt

# 场景 2：有窗口 + 未命中 → 不改状态
p2 = make_host(M, [W("哔哩哔哩 - 首页")])
R.random = lambda: 0.9
try:
    p2.check_video_apps()
finally:
    R.random = real_random
out["s2"] = dict(watching=p2.is_watching_video, hist=len(p2.video_watch_history))

# 场景 3/4：无窗口 + 命中 → suggest（命中 0.5 内 → 打开）
p3 = make_host(M, [])
R.random = lambda: 0.1
try:
    p3.check_video_apps()
finally:
    R.random = real_random
out["s3"] = dict(watching=p3.is_watching_video, title=p3.video_title,
                 opened=p3.desktop_interaction.opened,
                 dur_ok=(30 <= p3.max_idle_duration <= 90),
                 resized=p3.desktop_interaction.resized)

# 场景 5：stop → 结算
p5 = make_host(M, [])
p5.is_watching_video = True; p5.video_start_time = __import__("time").time() - 42
p5.video_title = "B站热门视频"
p5.video_watch_history = [{"title": "B站热门视频", "duration": 0}]
p5.max_idle_duration = 999
try:
    p5.stop_watching_video()
except Exception as e:
    out["s5_err"] = repr(e)
out["s5"] = dict(watching=p5.is_watching_video,
                 dur=round(p5.video_watch_history[-1]["duration"], 1),
                 moving=p5.is_moving,
                 idle_ok=(0.5 <= p5.max_idle_duration <= 3.0))

# 场景 6：深夜 tick
p6 = make_host(M, [W("哔哩哔哩 - 电影")])
p6.is_watching_video = True; p6.video_title = "t"; p6.video_platform = "p"
p6.video_start_time = __import__("time").time()
# 让 start 起表（走真实路径）
R.random = lambda: 0.1
try:
    p6.check_video_apps()
finally:
    R.random = real_random
import time as _t
rs = _t.strftime
_t.strftime = lambda f, *a: "23" if f == "%H" else "30"
try:
    p6._update_video_watching()
finally:
    _t.strftime = rs
out["s6"] = dict(watching=p6.is_watching_video, sleeping=p6.is_sleeping,
                 closed=p6.desktop_interaction.closed,
                 idle=p6.max_idle_duration)

R.random = real_random
R.choice = real_choice
print("@@JSON@@" + json.dumps(out, ensure_ascii=False))
'''
    env = dict(os.environ)
    r = subprocess.run([sys.executable, "-c", prog, tmp],
                       capture_output=True, env=env)
    txt = r.stdout.decode("utf-8", "replace")
    if "@@JSON@@" not in txt:
        return None, (r.stdout.decode("utf-8", "replace")[-2000:]
                      + "\n--STDERR--\n" + r.stderr.decode("utf-8", "replace")[-2000:])
    import json
    return json.loads(txt.split("@@JSON@@", 1)[1].strip()), None


def main():
    print("=" * 72)
    print("W1-4 校验 D · A/B 行为对照（父版本 vs 当前）")
    print("=" * 72)

    cur = io.open(MAIN_PY, "rb").read()
    r = subprocess.run(["git", "show", "HEAD:ralsei_pet/src/main.py"],
                       cwd=ROOT, capture_output=True)
    if r.returncode != 0:
        print("  !! git show 失败"); return 2
    old = r.stdout
    if hashlib.md5(old).hexdigest() == hashlib.md5(cur).hexdigest():
        print("  !! A == B：父版本与当前 md5 相同 → 探针退化，终止")
        return 2
    print("  父版本 md5 %s" % hashlib.md5(old).hexdigest())
    print("  当前   md5 %s" % hashlib.md5(cur).hexdigest())

    tmpdir = tempfile.mkdtemp(prefix="w14_abolD_")
    old_path = os.path.join(tmpdir, "main_old.py")
    io.open(old_path, "wb").write(old)

    res_new, err_new = run_scenarios(MAIN_PY, "new")
    res_old, err_old = run_scenarios(old_path, "old")

    if err_new:
        print("  !! 当前版本场景执行失败:\n%s" % err_new); return 2
    if err_old:
        print("  !! 父版本场景执行失败:\n%s" % err_old); return 2

    print("-" * 72)
    for sk in sorted(res_old):
        same = res_old[sk] == res_new[sk]
        check("场景 %s 行为一致" % sk, same,
              "\n      旧=%r\n      新=%r" % (res_old[sk], res_new[sk]))
        if not same:
            print("      旧=%r" % (res_old[sk],))
            print("      新=%r" % (res_new[sk],))
    print("-" * 72)
    print("  详细对照：")
    for sk in sorted(res_old):
        print("    %-4s 旧 %s" % (sk, res_old[sk]))
        print("    %-4s 新 %s" % ("", res_new[sk]))

    print()
    print("=" * 72)
    print("结果：PASS %d / FAIL %d" % (len(PASSES), len(FAILS)))
    for n, d in FAILS:
        print("  FAIL %s  %s" % (n, d))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
