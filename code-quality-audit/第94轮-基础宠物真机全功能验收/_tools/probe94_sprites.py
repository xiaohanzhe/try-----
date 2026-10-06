# -*- coding: utf-8 -*-
"""第94轮 · 精灵容器体检：为什么 `idle` 的容器是 69x47（窗口 138x94）？

`_anim_container_size` = 该动画**所有帧**的最大 w/h；任何一帧异常大，
整组窗口就跟着变大（动画切换时 `setGeometry` 按中心重排 ⇒ 拖拽中"先窜后弹"）。
本探针把可疑动画的**逐帧尺寸**打出来，定位是哪一帧。
"""
import ctypes
import io
import os
import sys
import time

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
SRC = os.path.join(ROOT, 'ralsei_pet')
for _p in (os.path.join(SRC, 'src'), SRC, os.path.join(SRC, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

EVID = os.path.join(ROOT, 'code-quality-audit', '第94轮-基础宠物真机全功能验收', '_evidence')
OUT = os.path.join(EVID, 'probe94_sprites.txt')
_buf = []


def w(s=''):
    _buf.append(str(s))
    try:
        print(s, flush=True)
    except Exception:
        pass
    try:
        io.open(OUT, 'w', encoding='utf-8', newline='\n').write('\n'.join(_buf))
    except Exception:
        pass


from PyQt5.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)
import main as main_mod

p = main_mod.RalseiPet()
app.processEvents()

w('=== 第94轮 精灵容器体检 ===')
w('时间 = %s' % time.strftime('%Y-%m-%d %H:%M:%S'))
w('scale_factor = %r' % getattr(p, 'scale_factor', None))
w()

sprites = p.sprite_loader.sprites or {}
names = list(sprites.keys())
w('动画组总数 = %d' % len(names))
w()

FOCUS = ['idle', 'sleep', 'pose', 'cower', 'walk_right', 'walk_down', 'walk_left',
         'walk_up', 'run_right', 'jump_ball', 'fall', 'splat', 'land']
for nm in FOCUS:
    if nm not in sprites:
        w('%-14s <不存在>' % nm)
        continue
    frames = sprites[nm] or []
    sizes = []
    for f in frames:
        sizes.append('null' if (f is None or f.isNull()) else '%dx%d' % (f.width(), f.height()))
    cw = ch = 0
    for f in frames:
        if f is not None and not f.isNull():
            cw = max(cw, f.width())
            ch = max(ch, f.height())
    w('%-14s 帧数=%-3d 容器=%dx%d -> 窗口(×%s)=%dx%d' %
      (nm, len(frames), cw, ch, getattr(p, 'scale_factor', 1),
       int(cw * getattr(p, 'scale_factor', 1)), int(ch * getattr(p, 'scale_factor', 1))))
    w('    逐帧 = %r' % sizes)

# ---- 全局：哪些组的容器宽度远超最常见值（可疑离群）----
w()
w('--- 容器离群筛查（宽度 >= 60 或 高度 >= 60 的组）---')
for nm in sorted(names):
    frames = sprites[nm] or []
    cw = ch = 0
    argw = argh = None
    for f in frames:
        if f is not None and not f.isNull():
            if f.width() > cw:
                cw = f.width()
            if f.height() > ch:
                ch = f.height()
    if cw >= 60 or ch >= 60:
        w('  %-42s 容器=%3dx%-3d 帧数=%d' % (nm, cw, ch, len(frames)))
try:
    p.close()
except Exception:
    pass
os._exit(0)
