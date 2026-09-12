# -*- coding: utf-8 -*-
import sys, os, traceback
ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet"
os.chdir(ROOT)
for p in (os.path.join(ROOT,'src'), os.path.join(ROOT,'modules'), ROOT):
    if p not in sys.path: sys.path.insert(0, p)
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
app = QApplication(sys.argv)
OUT = []
def ck(label, cond, extra=""):
    OUT.append(("PASS " if cond else "FAIL ") + label + ("  " + str(extra) if extra else ""))

import main as M
# 1) 崩溃兜底
ck("install_crash_guard 存在", hasattr(M, "install_crash_guard"))
def boom(): raise RuntimeError("boom-test")
M.install_crash_guard()
sys.excepthook(RuntimeError, RuntimeError("x"), None)
ck("excepthook 已换为非默认", sys.excepthook is not sys.__excepthook__)

pet = M.RalseiPet()
# 2) 动画键
for k in ("fall_mad", "splat_mad", "splat", "fall"):
    ck(f"sprite_loader 有动画 {k}", k in pet.sprite_loader.sprites,
       pet.sprite_loader.frame_counts.get(k))
# 3) start_fall 分支选动画
pet.current_animation = "idle"
pet.is_falling = False
pet.start_fall("window_move")
ck("window_move 使用 fall_mad", pet.current_animation == "fall_mad", pet.current_animation)
ck("window_move 时长>=3s", pet.max_fall_duration >= 3.0, pet.max_fall_duration)
pet.is_falling = False
pet.start_fall("fall_from_window")
ck("fall_from_window 使用 fall_mad", pet.current_animation == "fall_mad", pet.current_animation)
ck("fall_from_window 时长>=5s", pet.max_fall_duration >= 5.0, pet.max_fall_duration)
pet.is_falling = False
pet.start_fall("fall_off")
ck("fall_off 仍用普通 fall", pet.current_animation == "fall", pet.current_animation)
# 4) 鼠标拖动定时器修复
ck("mouse_drag_timer 非 singleShot", pet.mouse_drag_timer.isSingleShot() is False)
ck("mouse_drag_timer 默认未启动", pet.mouse_drag_timer.isActive() is False)
pet.start_mouse_drag(pet.pos())
ck("start_mouse_drag 后定时器激活", pet.mouse_drag_timer.isActive() is True)
ck("定时器间隔为帧级(<=50ms)", pet.mouse_drag_timer.interval() <= 50, pet.mouse_drag_timer.interval())
pet.stop_mouse_drag()
ck("stop_mouse_drag 停止定时器", pet.mouse_drag_timer.isActive() is False)
# 5) update_mouse_drag 不再抛 NameError
pet.is_dragging_mouse = True
pet.drag_start_pos = pet.pos(); pet.drag_target_pos = pet.pos(); pet.drag_start_time = 0.0
pet.drag_duration = 999
try:
    pet.update_mouse_drag()
    ck("update_mouse_drag 不抛异常", True)
except Exception as e:
    ck("update_mouse_drag 不抛异常", False, repr(e))
pet.is_dragging_mouse = False

print("\n".join(OUT))
print("FAILED:", sum(1 for o in OUT if o.startswith("FAIL")))
