# -*- coding: utf-8 -*-
u"""probe96_walkup.py —— 抓 `walk_up` 是谁设进去的（调用栈现场）

背景（第96轮 10 分钟录制实测）：
    `frames.csv` 里出现 `anim=walk_up` 但位移角度 ≈ -141°（左上）⇒
    按现行 `-45/45/135` 分档应判 `left`。
    我在静态代码里找到**两处**可能的分档：
      · L7258 `update_movement` 自主移动分支：`-45/45/135`（对 -141° ⇒ left）
      · L7394 `_handle_mouse_follow` 鼠标跟随：`abs(dx) > abs(dy)`（对 |-844|>|-700| ⇒ left）
    两处**都该给 left**，可实测却是 walk_up ⇒ **说明还有第三处调用方**。

    这个探针不猜：直接在**产品进程内**包一层 `change_animation`，
    凡目标动画以 `walk_`/`run_` 开头者，把调用栈（3 层）与
    `current_speed`/`current_direction`/`is_moving` 现场一起落盘。

产物：`_evidence/probe96_walkup.txt`（每次切换一行 + 栈）
      `_evidence/probe96_walkup_frames.csv`（周期采样，便于交叉比对）
运行：C:/Python311/python.exe -X utf8 _tools/probe96_walkup.py
环境变量：PROBE96_SECS（默认 90）
"""
import io
import os
import sys
import csv
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
REPO = os.path.join(ROUND, '..', '..')
EV = os.path.join(ROUND, '_evidence')
if not os.path.isdir(EV):
    os.makedirs(EV)

OUT = os.path.join(EV, 'probe96_walkup.txt')
FCV = os.path.join(EV, 'probe96_walkup_frames.csv')

SECS = float(os.environ.get('PROBE96_SECS', '90'))

# ---------- 1) 复刻 main.py 的启动序列 ----------
# ★ 与 rec96.py 完全一致：先 chdir 到包目录、置前 sys.path，
#   再按 __main__ 顺序调 check_single_instance / install_crash_guard /
#   text_segmenter / data_store.migrate，最后才 QApplication + RalseiPet。
#   首版漏了这些且写错类名（`Ralsei` → 实为 `RalseiPet`）⇒ 直接 AttributeError。
PKG = os.path.join(REPO, 'ralsei_pet')
SRC = os.path.join(PKG, 'src')
os.chdir(PKG)
if SRC in sys.path:
    sys.path.remove(SRC)
sys.path.insert(0, SRC)

import main as M  # noqa: E402

M.check_single_instance()
M.install_crash_guard()
try:
    import text_segmenter
    text_segmenter.install()
except Exception as e:
    print('text_segmenter fail: %r' % (e,))
try:
    import data_store
    data_store.migrate_from_staging()
except Exception as e:
    print('data_store fail: %r' % (e,))


def _open_log():
    return io.open(OUT, 'w', encoding='utf-8', newline='')


class Probe(object):
    u"""包一层 change_animation。"""

    def __init__(self, log):
        self.log = log
        self.n = 0
        self.hits = 0
        self.orig = None

    def install(self):
        self.orig = M.RalseiPet.change_animation

        def wrapped(self_, new_animation, force=False):
            # 只在**走路/跑步方向动画**上取证
            name = u'%s' % (new_animation,)
            is_dir_anim = name.startswith(('walk_', 'run_'))
            if is_dir_anim:
                self.n += 1
                try:
                    spd = (getattr(self_, 'current_speed_x', 0.0),
                           getattr(self_, 'current_speed_y', 0.0))
                    cdir = getattr(self_, 'current_direction', None)
                    moving = getattr(self_, 'is_moving', None)
                    stage = getattr(self_, '_spell_stage', None)
                    tgt = getattr(self_, 'target_pos', None)
                    pos = self_.pos()
                except Exception as e:
                    self.log.write(u'[probe] 取现场失败 %r\n' % (e,))
                    spd, cdir, moving, stage, tgt, pos = None, None, None, None, None, None
                # 调用栈：跳过 probe 自己（前 2 帧），取 4 层
                st = traceback.extract_stack()[:-1]
                frames = []
                for fr in st[-5:]:
                    frames.append(u'%s:%d(%s)' % (
                        os.path.basename(fr.filename), fr.lineno, fr.name))
                self.log.write(
                    u'[%8.2f] anim=%-12s force=%-5s spd=(%7.3f,%7.3f) dir=%-5s moving=%-5s '
                    u'stage=%-8s pos=(%d,%d) tgt=%s\n'
                    % (time.time(), name, force, spd[0], spd[1], cdir, moving, stage,
                       pos.x() if pos else -1, pos.y() if pos else -1, tgt))
                for i, fr in enumerate(frames):
                    self.log.write(u'        %s> %s\n' % (u'  ' * i, fr))
                self.log.flush()
            return self.orig(self_, new_animation, force)

        M.RalseiPet.change_animation = wrapped
        self.hits = 0

    def uninstall(self):
        if self.orig is not None:
            M.RalseiPet.change_animation = self.orig


def main():
    # ★ 启动序列已在模块级执行（复刻 __main__）；这里只补 `import` 引用。
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QTimer

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    log = _open_log()
    log.write(u'# probe96_walkup —— 抓 walk_*/run_* 的调用现场\n')
    log.write(u'# 时长 %ss\n' % SECS)
    log.write(u'# 说明：每次「方向类动画切换」记 1 组（现场 + 5 层调用栈）\n')
    log.write(u'=' * 78 + u'\n')
    log.flush()

    pet = M.RalseiPet()
    probe = Probe(log)
    probe.install()

    # ★★★ 主动驱动器：把目标**轮换**设到四个斜向角（含第95轮缺陷扇区的 -141°/左上 与 +39°/右下），
    #   否则又是"90s 里它没走到那个方向"⇒ 又一次"没测到"而不是"没问题"。
    #   只调产品**已有的**接口（`target_pos` + `is_moving`），不新增行为。
    from PyQt5.QtCore import QPoint
    corners = [
        (u'左上(-135°附近)', -0.72, -0.70),   # ★ 本轮实测缺陷角度 ≈ -141°
        (u'右下(+39°附近)', 0.78, 0.63),      # ★ 第95轮缺陷 B 的角度
        (u'左下(-141°附近)', -0.72, 0.70),
        (u'右上(+39°附近)', 0.78, -0.63),
    ]
    drv = {'i': -1}

    def drive():
        drv['i'] = (drv['i'] + 1) % len(corners)
        label, ux, uy = corners[drv['i']]
        try:
            g = pet._virtual_screen_rect()
            # 以屏幕中心为基准，沿 (ux,uy) 方向推到边（留 12% 余量）
            cx = (g.left() + g.right()) // 2
            cy = (g.top() + g.bottom()) // 2
            tx = int(cx + ux * (g.width() // 2 - 60))
            ty = int(cy + uy * (g.height() // 2 - 60))
            pet.target_pos = QPoint(tx, ty)
            pet.is_moving = True
            pet.is_sleeping = False
            log.write(u'[DRIVE] #%d %s ⇒ target=(%d,%d)  from=(%d,%d)\n'
                      % (drv['i'], label, tx, ty, pet.pos().x(), pet.pos().y()))
            log.flush()
        except Exception as e:
            log.write(u'[DRIVE] 失败 %r\n' % (e,))
            log.flush()

    drive_timer = QTimer()
    drive_timer.timeout.connect(drive)
    drive_timer.start(6000)          # 每 6s 换一个斜向目标
    QTimer.singleShot(300, drive)    # 立刻先给一个

    fcsv = io.open(FCV, 'w', encoding='utf-8', newline='')
    w = csv.writer(fcsv)
    w.writerow([u't', u'wx', u'wy', u'ww', u'wh', u'anim', u'dir', u'moving',
                u'falling', u'sleeping', u'spdx', u'spdy'])

    t0 = time.time()
    state = {'n': 0}

    def tick():
        el = time.time() - t0
        if el >= SECS:
            timer.stop()
            probe.uninstall()
            log.write(u'=' * 78 + u'\n')
            log.write(u'# 合计 方向类动画切换 = %d 次\n' % probe.n)
            log.flush()
            fcsv.close()
            app.quit()
            return
        state['n'] += 1
        try:
            pos = pet.pos()
            w.writerow([u'%.3f' % el, pos.x(), pos.y(), pet.width(), pet.height(),
                        getattr(pet, 'current_animation', None),
                        getattr(pet, 'current_direction', None),
                        getattr(pet, 'is_moving', None),
                        getattr(pet, 'is_falling', None),
                        getattr(pet, 'is_sleeping', None),
                        u'%.3f' % getattr(pet, 'current_speed_x', 0.0),
                        u'%.3f' % getattr(pet, 'current_speed_y', 0.0)])
            fcsv.flush()
        except Exception as e:
            log.write(u'[tick] %r\n' % (e,))

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(400)

    pet.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
