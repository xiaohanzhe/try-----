# -*- coding: utf-8 -*-
"""第四轮审查：端到端运行时演练（离屏）。
构造真实 RalseiPet，跑事件循环，模拟核心用户路径，全程收集异常。"""
import os, sys, time, tempfile, shutil

PROJECT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
PET = os.path.join(PROJECT, "ralsei_pet")
sys.path.insert(0, PET)
sys.path.insert(0, os.path.join(PET, "modules"))
sys.path.insert(0, os.path.join(PET, "src"))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# 数据文件隔离（安全版）：只复制到备份目录，绝不移动原文件。
# 即使进程被中途终止，原始数据也始终在原位，不会丢失。
_BACKUP = tempfile.mkdtemp(prefix="ralsei_backup_")
DATA_FILES = ("memory.json", "growth_data.json", "entertainment_data.json",
              "config.json", "customization_config.json")
_originals = {}
for _f in DATA_FILES:
    _p = os.path.join(PET, _f)
    if os.path.exists(_p):
        _originals[_f] = shutil.copy2(_p, _BACKUP)  # 原文件保持原位


def _restore_data_files():
    for _f, _bp in _originals.items():
        _p = os.path.join(PET, _f)
        try:
            if os.path.exists(_p):
                os.remove(_p)
            shutil.copy2(_bp, _p)
        except Exception as _e:
            print("恢复数据文件失败 %s: %s" % (_f, _e), flush=True)

errors = []
def hook(t, v, tb):
    import traceback
    errors.append("".join(traceback.format_exception(t, v, tb)))
sys.excepthook = hook

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, Qt, QPoint
from PyQt5.QtTest import QTest

app = QApplication(sys.argv)

try:
    from main import RalseiPet
    w = RalseiPet()
    w.show()
    print("[1] 构造成功", flush=True)

    # 跑 3 秒事件循环（定时器真实运转：update_movement/update_animation/ai_timer）
    QTimer.singleShot(3000, app.quit)
    app.exec_()
    print("[2] 事件循环 3 秒无崩溃，current_animation=%s pos=%s" % (w.current_animation, w.pos()), flush=True)

    # 模拟用户点击（身体部位）
    from PyQt5.QtGui import QMouseEvent
    center = w.rect().center()
    # 直接调事件处理
    try:
        w.mousePressEvent(QMouseEvent(QMouseEvent.MouseButtonPress, center, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
        w.mouseReleaseEvent(QMouseEvent(QMouseEvent.MouseButtonRelease, center, Qt.LeftButton, Qt.NoButton, Qt.NoModifier))
        print("[3] 点击事件 OK", flush=True)
    except Exception as e:
        print("[3] 点击事件异常:", e, flush=True)

    # 菜单动作（模态 exec_ 会阻塞离屏，直接触发菜单项对应功能）
    try:
        w.feed_ralsei()
        w.pet_ralsei()
        w.change_animation_randomly()
        print("[4] 菜单动作 OK", flush=True)
    except Exception as e:
        print("[4] 菜单动作异常:", e, flush=True)

    # 猜数字游戏全程
    try:
        r = w.start_guess_number()
        print("[5] 猜数字开始 OK, is_playing=%s" % w.game_state['is_playing'], flush=True)
        w.play_guess_number("50")
        w.play_guess_number("25")
        w.play_guess_number("abc")  # 非法输入
        w.play_guess_number("999")  # 越界
        # 直接猜中
        w.guess_number_game["target_number"] = 42
        w.play_guess_number("42")
        print("[6] 猜数字流程 OK, is_playing=%s" % w.game_state['is_playing'], flush=True)
    except Exception as e:
        print("[6] 猜数字异常:", e, flush=True)

    # 石头剪刀布
    try:
        w.start_rock_paper_scissors()
        w.play_rock_paper_scissors("石头")
        w.play_rock_paper_scissors("剪刀")
        print("[7] 石头剪刀布 OK, is_playing=%s" % w.game_state['is_playing'], flush=True)
    except Exception as e:
        print("[7] 石头剪刀布异常:", e, flush=True)

    # 对话系统
    try:
        r = w.dialogue_system.generate_response("你今天过得怎么样？", w.emotion_system)
        print("[8] 对话生成 OK:", str(r)[:40], flush=True)
        r2 = w.dialogue_system.generate_response("帮我看看我的文件", w.emotion_system)
        print("[8b] 对话生成2 OK:", str(r2)[:40], flush=True)
    except Exception as e:
        print("[8] 对话异常:", e, flush=True)

    # 喂食/抚摸
    try:
        w.feed_ralsei()
        w.pet_ralsei()
        print("[9] 喂食/抚摸 OK", flush=True)
    except Exception as e:
        print("[9] 喂食/抚摸异常:", e, flush=True)

    # 动画切换
    try:
        ok = w.change_animation("walk_left")
        w.change_animation("laugh", force=True)
        print("[10] 动画切换 OK (walk_left=%s)" % ok, flush=True)
    except Exception as e:
        print("[10] 动画异常:", e, flush=True)

    # 系统托盘隐藏/恢复
    try:
        w._hide_ralsei()
        w._show_from_tray()
        print("[11] 托盘隐藏/恢复 OK", flush=True)
    except Exception as e:
        print("[11] 托盘异常:", e, flush=True)

    # 清理（走正式退出路径）
    w.cleanup_on_exit()
    print("[12] 退出清理 OK", flush=True)

    # 恢复数据文件
    _restore_data_files()
    print("[13] 数据文件恢复 OK", flush=True)

    print("========== 异常统计 ==========", flush=True)
    if errors:
        print("捕获 %d 个异常：" % len(errors), flush=True)
        for e in errors[:10]:
            print(e[:2000], flush=True)
    else:
        print("0 个未捕获异常", flush=True)

    # 数据零改动检查
    dirty = []
    for f in ("memory.json", "growth_data.json", "entertainment_data.json", "config.json"):
        p = os.path.join(PET, f)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            dirty.append(f)
    print("运行时数据文件（应无残留）: %s" % (dirty or "干净"), flush=True)

except Exception as e:
    import traceback
    traceback.print_exc()
    print("顶层异常:", e, flush=True)
finally:
    _restore_data_files()
    shutil.rmtree(_BACKUP, ignore_errors=True)
