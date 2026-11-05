# -*- coding: utf-8 -*-
"""第164轮 · 段7「跟随鼠标」零变化的归因探针（只读，不改产品）。

疑点：`_handle_mouse_follow`（10618）读的是 `QCursor.pos()` = **真实光标**，
      阈值 `mouse_follow_distance = 50`（8363）。探针没控制光标 ⇒ 若真实光标
      恰好落在宠物中心 50px 内，走 else 分支只减速、不 move ⇒ 位置零变化。
      另一条可能：`_cached_screen_geom` 为 None（10662 的守卫）⇒ 算了速度但不 move。

本探针只做三件事：
  1) 打印真实光标 / 宠物中心 / 距离 / 阈值
  2) 打印 `_cached_screen_geom` 与阻力系数
  3) 打桩 `QCursor.pos` 到一个远点，再看会不会动（区分「夹具不保真」与「真缺陷」）
"""
import os
import sys
import tempfile

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['RALSEI_DATA_DIR'] = os.path.join(tempfile.gettempdir(), 'pet164_data')
os.makedirs(os.environ['RALSEI_DATA_DIR'], exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'src'))

import memory_store as _ms
_ms.find_device_dir = lambda create=True: None
_ms.default_memory_dir = lambda: (os.path.join(
    os.environ['RALSEI_DATA_DIR'], 'memory'), False, None)
import data_store as _ds
_ds.vault_root = lambda create=True: None

from PyQt5.QtWidgets import QApplication            # noqa: E402
from PyQt5.QtCore import QPoint                     # noqa: E402
from PyQt5.QtGui import QCursor                     # noqa: E402

app = QApplication(sys.argv[:1])


def main():
    from main import RalseiPet
    w = RalseiPet()
    w.max_idle_duration = 1e9
    w.is_moving = False
    w.show()
    app.processEvents()

    print('=' * 70)
    print('1 现场量：真实光标 / 宠物中心 / 阈值')
    print('=' * 70)
    cur = QCursor.pos()
    c = w.pos() + QPoint(w.width() // 2, w.height() // 2)
    dx, dy = cur.x() - c.x(), cur.y() - c.y()
    dist2 = dx * dx + dy * dy
    thr = getattr(w, 'mouse_follow_distance', None)
    print('   宠物 pos=%s size=%dx%d 中心=%s'
          % ((w.pos().x(), w.pos().y()), w.width(), w.height(), (c.x(), c.y())))
    print('   QCursor.pos() = %s' % ((cur.x(), cur.y()),))
    print('   dx=%d dy=%d 距离^2=%d  阈值=%s  距离^2 > 阈值^2 ⇒ %s'
          % (dx, dy, dist2, thr,
             (dist2 > (thr or 0) ** 2) if thr else 'n/a'))

    print()
    print('=' * 70)
    print('2 现场量：_cached_screen_geom / 阻力')
    print('=' * 70)
    sg = getattr(w, '_cached_screen_geom', None)
    print('   _cached_screen_geom = %s' % (
        None if sg is None else
        '(%d,%d) %dx%d' % (sg.left(), sg.top(), sg.width(), sg.height())))
    print('   friction=%s  air_resistance=%s  current_speed=(%.3f, %.3f)'
          % (getattr(w, 'friction', 'N/A'), getattr(w, 'air_resistance', 'N/A'),
             float(getattr(w, 'current_speed_x', 0) or 0),
             float(getattr(w, 'current_speed_y', 0) or 0)))

    print()
    print('=' * 70)
    print('3 打桩 QCursor.pos 到远点（正控制）：应当开始移动')
    print('=' * 70)
    far = QPoint(c.x() + 400, c.y() + 300)
    try:
        QCursor.pos = staticmethod(lambda: far)
        print('   打桩成功：QCursor.pos() -> (%d,%d)' % (far.x(), far.y()))
    except Exception as e:                            # noqa: BLE001
        print('   打桩失败（PyQt 类不可写）: %s: %s' % (type(e).__name__, e))
    w._cached_screen_geom = w._virtual_screen_rect()
    w.is_following_mouse = True
    before = w.pos()
    trail = []
    for i in range(1, 31):
        w._handle_mouse_follow(0.033)
        trail.append((w.pos().x() - before.x(), w.pos().y() - before.y()))
    moved = sum(1 for i in range(1, len(trail)) if trail[i] != trail[i - 1])
    print('   30 帧：位置变化次数=%d  起点=%s 终点=%s'
          % (moved, (before.x(), before.y()), (w.pos().x(), w.pos().y())))
    print('   轨迹（末 6 帧）: %s' % (trail[-6:],))
    if moved:
        # 方向对不对：应向 (+,+) 方向走
        okdir = trail[-1][0] > 0 and trail[-1][1] > 0
        print('   方向朝右下 = %s（期望 True）' % okdir)
    w.is_following_mouse = False

    print()
    print('=' * 70)
    print('4 负控制：光标放回中心（距离<50）应当停住')
    print('=' * 70)
    cc = w.pos() + QPoint(w.width() // 2, w.height() // 2)
    QCursor.pos = staticmethod(lambda: cc)
    w._cached_screen_geom = w._virtual_screen_rect()
    w.current_speed_x = 0.0
    w.current_speed_y = 0.0
    before = w.pos()
    for _ in range(10):
        w._handle_mouse_follow(0.033)
    print('   10 帧后位移 = (%d,%d)（期望 (0,0)）'
          % (w.pos().x() - before.x(), w.pos().y() - before.y()))

    try:
        w.cleanup_on_exit()
    except Exception:                                 # noqa: BLE001
        pass


if __name__ == '__main__':
    main()
