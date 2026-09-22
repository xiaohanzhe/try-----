# -*- coding: utf-8 -*-
"""第 35 轮 —— 真机状态直读（用户视角监测的第二条通道）。

背景：
    10 分钟窗口采样发现「宠物窗口几何 60+ 秒零变化」，需要区分两种情况：
      A. 本就该静止（例如处于 idle 站立、或甩飞后停在某处、或未到移动触发条件）
      B. 移动逻辑没跑起来（缺陷）

    光看窗口看不出来。必须**从宠物内部状态**判定：当前处于什么状态、目标点在
    哪、速度多少、定时器是否在跑。

做法（本项目「真机取证配方」）：
    独立进程 import main，构造 QApplication + RalseiPet，
    用 QTimer.singleShot 在构造后若干时刻读取属性并落盘，然后 quit。

⚠️ 注意：本脚本会**再起一个实例**，但项目有单实例锁 Global\\RalseiPetMutex。
    因此复用已在跑的那个进程是不可能的（跨进程读不了 Python 属性）。
    这里的处理：先探测锁 —— 若锁被占，说明真机在跑，此时**只读磁盘侧证据**，
    并如实标注"内部状态直读被单实例锁阻断"。若锁空闲，才真正实例化。
"""
import os
import sys
import json
import time

WS = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
SRC = os.path.join(WS, "ralsei_pet", "src")
EV = os.path.join(WS, "code-quality-audit", "第35轮-真机用户视角10分钟监测", "_evidence")
OUT = os.path.join(EV, "直读_宠物内部状态.txt")

sys.path.insert(0, SRC)
sys.path.insert(0, os.path.join(WS, "ralsei_pet"))


def probe_lock():
    """探测单实例锁是否被占（不创建，只 OpenExisting）。"""
    import win32event
    import win32api
    import winerror
    try:
        h = win32event.OpenMutex(win32event.SYNCHRONIZE, False, r"Global\RalseiPetMutex")
        win32api.CloseHandle(h)
        return False, "锁可打开（无实例占用）"
    except Exception as e:
        return True, f"锁被占用/探测异常: {e}"


def main():
    lines = []
    def w(s=""):
        lines.append(str(s))

    w("第35轮 真机状态直读（内部状态通道）")
    w("=" * 60)
    w("时间: " + time.strftime("%Y-%m-%d %H:%M:%S"))

    occupied, msg = probe_lock()
    w(f"单实例锁: occupied={occupied} | {msg}")
    w()

    if occupied:
        w("→ 真机进程正在运行，跨进程无法读 Python 属性。")
        w("  本通道降级为：只记录「无法直读」这一事实，判定依据改为窗口几何 + 日志。")
        w("  （这不是失败，是单实例设计的必然结果。）")
        with open(OUT, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print("LOCK_OCCUPIED -> wrote", OUT)
        return

    # 锁空闲 → 真机没在跑 → 自己起一个，读状态
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QTimer

    app = QApplication(sys.argv)
    import main as petmain

    pet = petmain.RalseiPet()
    w("RalseiPet 实例化成功")
    w(f"  尺寸: {pet.width()}x{pet.height()}  pos={pet.pos().x()},{pet.pos().y()}")
    w()

    def snap(tag):
        w(f"--- [{tag}] t+{round(time.time()-t0,1)}s ---")
        for attr in ("current_state", "state", "move_target", "target_pos",
                     "move_speed", "speed", "is_moving", "is_falling",
                     "is_jumping", "is_thrown", "current_floor",
                     "fall_velocity", "throw_velocity", "energy", "hunger"):
            if hasattr(pet, attr):
                try:
                    v = getattr(pet, attr)
                    if callable(v):
                        v = "<callable>"
                    w(f"  {attr} = {v!r}")
                except Exception as e:
                    w(f"  {attr} = <err {e}>")
        # 定时器状态
        for tn in ("movement_timer", "animation_timer", "idle_timer",
                   "autonomous_timer", "beat_timer", "gravity_timer"):
            t = getattr(pet, tn, None)
            if t is not None and hasattr(t, "isActive"):
                w(f"  {tn}.isActive() = {t.isActive()}  interval={t.interval()}")
        w()

    t0 = time.time()
    for i, delay in enumerate((1000, 5000, 15000, 30000)):
        QTimer.singleShot(delay, lambda i=i: snap(f"snap{i}"))

    QTimer.singleShot(35000, app.quit)
    app.exec_()

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("WROTE", OUT)


if __name__ == "__main__":
    main()
