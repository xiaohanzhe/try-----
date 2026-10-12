# -*- coding: utf-8 -*-
"""第112轮 · **门渐显动图/视频**（用户铁律「一定要看录像」）。

用户要看的是「**实体靠近 ⇒ 门从虚到实**」这个**过程**，静态帧给不了。
但真机 `grabWindow(0)` 抓不到我们的分层窗口（见 `EVIDENCE.md` 一）⇒
改为**把画布抓帧 + 壁纸合成**，逐帧产出，再用 ffmpeg 编码成 mp4/gif。

做法（不改产品状态，只读 + 驱动真实 tick）：
  1. 起真机 App，进桌面场景
  2. 把**灵魂**沿一条路径从"远离 UT 门"移动到"贴着 UT 门"（真机驱动灵魂状态）
  3. 每帧 `canvas.grab()` ⇒ 与壁纸合成 ⇒ 落 PNG
  4. 最后用 ffmpeg 把 PNG 序列编成 mp4（有 ffmpeg 时）+ 拼一张"时间轴长图"

跑法：
    set QT_QPA_PLATFORM=windows && C:\\Python311\\python.exe anim112.py
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, os.path.join(PKG, 'modules'))
sys.path.insert(0, os.path.join(PKG, 'src'))

os.environ.setdefault('RALSEI_TEST_MODE', '1')

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QImage, QPainter, QColor

_app = QApplication.instance() or QApplication(sys.argv)
IS_REAL = (os.environ.get('QT_QPA_PLATFORM') == 'windows')

OUT = os.path.abspath(os.path.join(HERE, '..', '_evidence', 'anim112'))
FRAMES = os.path.join(OUT, 'frames')
for _d in (OUT, FRAMES):
    if not os.path.isdir(_d):
        os.makedirs(_d)

print(u'==== anim112  platform=%s real=%s ====' % (os.environ.get('QT_QPA_PLATFORM'), IS_REAL))

import main as _M
pet = _M.RalseiPet()
pet.show()


def poll(ms):
    t_end = time.time() * 1000.0 + ms
    while time.time() * 1000.0 < t_end:
        try:
            _app.processEvents()
        except Exception:
            pass
        time.sleep(0.008)


poll(2000)

scr = _app.primaryScreen()
sc = pet.__dict__.get('scene_canvas')
if sc is None:
    print(u'[FATAL] 没有 scene_canvas')
    sys.exit(1)

# 壁纸（一次）
wall = None
if IS_REAL:
    pm = scr.grabWindow(0)
    if pm is not None and not pm.isNull():
        wall = pm.toImage().convertToFormat(QImage.Format_ARGB32)

soul = pet.__dict__.get('soul')
print(u'  soul = %r' % (type(soul).__name__ if soul else None))

# 灵魂走位：从"远离 UT 门（右下）"走到"贴着 UT 门（左侧中点）"
# ★ 用**屏幕像素**喂给灵魂（灵魂状态用屏幕坐标），屏 2560x1600。
#   UT 门在画面左缘，画面 x747 ⇒ 门屏幕 x≈747~810、y≈400+70*3.33≈633~963。
path = []
x0, y0 = 2200.0, 1300.0     # 起点：右下（远离 UT 门）
x1, y1 = 800.0, 800.0       # 终点：贴着 UT 门
STEPS = 30
for i in range(STEPS + 1):
    t = i / float(STEPS)
    path.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))

saved_center = None
try:
    saved_center = soul.state.center()
except Exception:
    pass

composed = []
for idx, (mx, my) in enumerate(path):
    try:
        soul.state.move_to(mx, my) if hasattr(soul.state, 'move_to') else None
    except Exception:
        pass
    try:
        st = soul.state
        if hasattr(st, 'x'):
            st.x = mx
        if hasattr(st, 'y'):
            st.y = my
    except Exception:
        pass
    poll(60)
    img = sc.grab().toImage()
    base = QImage(img.size(), QImage.Format_ARGB32)
    if wall is not None and wall.size() == img.size():
        base = wall.copy()
    else:
        base.fill(QColor(24, 26, 34))
    p = QPainter(base)
    p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    p.drawImage(0, 0, img)
    p.end()
    fp = os.path.join(FRAMES, u'f%03d.png' % idx)
    base.save(fp, 'PNG')
    composed.append(fp)

print(u'  帧数 = %d' % len(composed))

# 还原灵魂
try:
    if saved_center is not None and hasattr(soul.state, 'move_to'):
        soul.state.move_to(saved_center[0], saved_center[1])
except Exception:
    pass

# ---- 拼时间轴长图（取 6 帧等距） ----
try:
    picks = [composed[i] for i in
             (0, len(composed) // 5, 2 * len(composed) // 5,
              3 * len(composed) // 5, 4 * len(composed) // 5, len(composed) - 1)]
    imgs = [QImage(p) for p in picks]
    tw = 480
    th = int(imgs[0].height() * tw / float(imgs[0].width()))
    scaled = []
    for i in imgs:
        scaled.append(i.scaled(tw, th))
    cols, rows = 3, 2
    sheet = QImage(tw * cols, th * rows, QImage.Format_ARGB32)
    sheet.fill(QColor(16, 18, 24))
    qp = QPainter(sheet)
    for n, i in enumerate(scaled):
        qp.drawImage((n % cols) * tw, (n // cols) * th, i)
    qp.end()
    p_sheet = os.path.join(OUT, 'reveal_timeline.png')
    sheet.save(p_sheet, 'PNG')
    print(u'  时间轴长图 -> %s' % os.path.basename(p_sheet))
except Exception as e:
    print(u'  拼图失败: %s' % e)

# ---- ffmpeg 编码（有就编） ----
mp4 = os.path.join(OUT, 'reveal112.mp4')
try:
    r = subprocess.run(
        ['ffmpeg', '-y', '-framerate', '12', '-i', os.path.join(FRAMES, 'f%03d.png'),
         '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-vf',
         'scale=trunc(iw/2)*2:trunc(ih/2)*2', mp4],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
    if os.path.isfile(mp4):
        print(u'  mp4 -> %s (%.1f KB)' % (os.path.basename(mp4),
                                        os.path.getsize(mp4) / 1024.0))
    else:
        print(u'  ffmpeg 未产出 mp4（rc=%s）' % r.returncode)
except Exception as e:
    print(u'  ffmpeg 不可用: %s' % e)

print(u'\n==== anim112 完成 ====')
