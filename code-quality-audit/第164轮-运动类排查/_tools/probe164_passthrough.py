# -*- coding: utf-8 -*-
"""第164轮 · ①新增项：地面层「从窗口下方穿过去」是否成立（只读）。

2.5D 口径（2026-11-05 用户确认）：
  · 整张桌面 = 地面（Z=0 平面），屏幕底边只是"最近处"，不是地表；
  · 窗口 = **悬空的板**（有顶面可站、底下是空隙），不是立在地上的实心柱子；
  · 窗口之间、桌面与第一层窗口之间都有空隙 ⇒ 地面层能从下方穿过。

要验三件事：
  A. desktop_floor 的矩形是不是**整屏**（决定"整张桌面是地面"成不立）
  B. 站在窗口矩形的**正下方**（更靠近观察者一侧）时，`get_current_floor` 会不会误判成窗口
  C. 移动路径上有没有"撞窗口就停"的阻挡（有就与"能穿过"矛盾）
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

app = QApplication(sys.argv[:1])


def main():
    from main import RalseiPet
    w = RalseiPet()
    w.max_idle_duration = 1e9
    w.is_moving = False
    w.show()
    app.processEvents()

    fm = getattr(w, 'floor_manager', None) or getattr(w, 'floors', None)
    print('=' * 70)
    print('A 楼层清单 / 桌面口径')
    print('=' * 70)
    if fm is None:
        print('   没拿到 floor_manager，退出')
        return
    print('   floor_manager = %s' % type(fm).__name__)
    try:
        fm.update_floors()          # 正确入口（167 行）；不是 refresh
    except Exception as e:                            # noqa: BLE001
        print('   update_floors 抛异常: %s: %s' % (type(e).__name__, e))

    floors = list(getattr(fm, 'floors', []) or [])
    df = getattr(fm, 'desktop_floor', None)
    print('   窗口楼层数 = %d' % len(floors))
    if df is not None:
        r = df['rect']
        print('   desktop_floor rect = (%d,%d) %dx%d'
              % (r.left(), r.top(), r.width(), r.height()))
        sr = w._virtual_screen_rect()
        print('   _virtual_screen_rect = (%d,%d) %dx%d'
              % (sr.left(), sr.top(), sr.width(), sr.height()))
        print('   桌面矩形 == 虚拟屏 ⇒ %s（"整张桌面是地面"的直接依据）'
              % (r == sr))

    for i, f in enumerate(floors[:6]):
        r = f.get('rect')
        vr = f.get('visible_rects') or ()
        print('   [%d] type=%-8s rect=(%d,%d) %dx%d  visible_rects=%d  title=%s'
              % (i, f.get('type'), r.left(), r.top(), r.width(), r.height(),
                 len(vr), (f.get('title') or '')[:24]))

    print()
    print('=' * 70)
    print('B 站在窗口「正下方」时，应该归属桌面而不是窗口')
    print('=' * 70)
    if not floors:
        print('   没有窗口楼层（offscreen 下可能枚举不到）—— 本项改为源码判据')
    else:
        for i, f in enumerate(floors[:4]):
            r = f['rect']
            cx = r.left() + r.width() // 2
            pts = [
                ('窗口中心', QPoint(cx, r.top() + r.height() // 2)),
                ('窗口下缘外 +8', QPoint(cx, r.bottom() + 8)),
                ('窗口正下 +40', QPoint(cx, r.bottom() + 40)),
                ('窗口左外 -20', QPoint(r.left() - 20, r.top() + 4)),
            ]
            for tag, p in pts:
                cur = fm.get_current_floor(p)
                ctype = (cur or {}).get('type') if cur else None
                hit = fm.floor_visible_contains(f, p)
                print('   [%d] %-12s (%5d,%5d)  当前楼层=%-8s 命中该窗口=%s'
                      % (i, tag, p.x(), p.y(), ctype, hit))

    print()
    print('=' * 70)
    print('C 阻挡检查：移动/夹紧路径里有没有"撞窗口就停"')
    print('=' * 70)
    import inspect
    for name in ('_clamp_pos_to_desktop', '_is_blocked_by_floor',
                 '_can_stand_at', '_floor_blocks_move'):
        fn = getattr(w, name, None)
        if fn is None:
            print('   %-22s 不存在（无此阻挡逻辑）' % name)
            continue
        src = ''
        try:
            src = inspect.getsource(fn)
        except Exception:                             # noqa: BLE001
            pass
        has_win = ('floor' in src.lower()) or ('window' in src.lower())
        print('   %-22s 存在  源码提到 floor/window = %s  (%d 字符)'
              % (name, has_win, len(src)))

    try:
        w.cleanup_on_exit()
    except Exception:                                 # noqa: BLE001
        pass


if __name__ == '__main__':
    main()
