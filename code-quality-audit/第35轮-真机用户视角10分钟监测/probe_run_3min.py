# -*- coding: utf-8 -*-
"""第 35 轮 —— 真机内部状态探针（回答「为什么 89 秒零移动」）。

为什么要这个：
    窗口采样只能看到「没动」，看不到「为什么没动」。
    内部状态才能区分：
      · is_moving / idle_timer / max_idle_duration  → 是在走还是该休息
      · is_sleeping / last_interaction_time / max_sleep_idle_duration → 是否一启动就睡了
      · movement_timer.isActive()                   → 定时器到底有没有跑
      · _is_being_dragged / _special_anim_locked()  → 有没有被"关键过程"闸住
      · current_activity / current_animation        → 用户实际看到什么姿态

做法：
    直接在宠物进程内跑（同进程 QTimer 采样），每 2 秒把上述字段连同窗口几何
    写进 jsonl，跑 3 分钟。这份数据既是"用户视角监测"的第二通道，也是
    定位静默问题的证据。
"""
import os
import sys
import json
import time

WS = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
SRC = os.path.join(WS, "ralsei_pet", "src")
EV = os.path.join(WS, "code-quality-audit", "第35轮-真机用户视角10分钟监测", "_evidence")
OUT = os.path.join(EV, "3min_内部状态探针.jsonl")
ERR = os.path.join(EV, "3min_内部状态探针_错误.txt")

sys.path.insert(0, SRC)
sys.path.insert(0, os.path.join(WS, "ralsei_pet"))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

app = QApplication(sys.argv)
import main as petmain

fp = open(OUT, "w", encoding="utf-8")
t0 = time.time()
n = [0]
fatal = []


def snap():
    try:
        n[0] += 1
        p = app_pet
        d = {
            "elapsed": round(time.time() - t0, 1),
            "pos": [p.pos().x(), p.pos().y()],
            "size": [p.width(), p.height()],
            "is_moving": getattr(p, "is_moving", None),
            "is_sleeping": getattr(p, "is_sleeping", None),
            "is_jumping": getattr(p, "is_jumping", None),
            "is_falling": getattr(p, "is_falling", None),
            "is_gravity_falling": getattr(p, "is_gravity_falling", None),
            "is_recovering": getattr(p, "is_recovering", None),
            "is_dragging_mouse": getattr(p, "is_dragging_mouse", None),
            "is_following_mouse": getattr(p, "is_following_mouse", None),
            "_is_being_dragged": getattr(p, "_is_being_dragged", None),
            "current_activity": getattr(p, "current_activity", None),
            "current_animation": getattr(p, "current_animation", None),
            "current_direction": getattr(p, "current_direction", None),
            "idle_timer": round(getattr(p, "idle_timer", -1), 2),
            "max_idle_duration": round(getattr(p, "max_idle_duration", -1), 2),
            "moving_duration": round(getattr(p, "moving_duration", -1), 2),
            "max_moving_duration": round(getattr(p, "max_moving_duration", -1), 2),
            "target_pos": [p.target_pos.x(), p.target_pos.y()] if hasattr(p, "target_pos") else None,
            "speed": round(getattr(p, "speed", -1), 2),
            "last_interaction_age": round(time.time() - getattr(p, "last_interaction_time", 0), 1),
            "max_sleep_idle_duration": getattr(p, "max_sleep_idle_duration", None),
            "special_anim_locked": bool(p._special_anim_locked()) if hasattr(p, "_special_anim_locked") else None,
        }
        timers = {}
        for tn in ("movement_timer", "animation_timer", "idle_timer_qt", "autonomous_timer"):
            t = getattr(p, tn, None)
            if t is not None and hasattr(t, "isActive"):
                timers[tn] = {"active": t.isActive(), "interval": t.interval()}
        d["timers"] = timers
        aa = getattr(p, "autonomous_agent", None)
        if aa is not None:
            d["autonomous_agent"] = {
                "class": type(aa).__name__,
                "attrs": {k: str(v)[:60] for k, v in vars(aa).items()
                          if not k.startswith("__") and not callable(v)},
            }
        fp.write(json.dumps(d, ensure_ascii=False, default=str) + "\n")
        fp.flush()
    except Exception as e:
        import traceback
        fatal.append(traceback.format_exc())


app_pet = petmain.RalseiPet()
QTimer.singleShot(500, lambda: snap())
poll = QTimer()
poll.timeout.connect(snap)
poll.start(2000)
QTimer.singleShot(180000, app.quit)
app.exec_()
fp.close()
if fatal:
    open(ERR, "w", encoding="utf-8").write("\n".join(fatal))
print("PROBE_DONE samples=%d" % n[0])
