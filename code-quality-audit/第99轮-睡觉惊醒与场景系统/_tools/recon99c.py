# -*- coding: utf-8 -*-
u"""recon99c.py —— 第99轮场景系统**进程内诊断**（只读，不改产品代码）。

recon99b 已证：进 `ch1.card_castle.card_castle_1f` 后
  · `canvas.last_drawn == 1`（`paint_on` 说"真落笔 1 条"）
  · 但**屏幕上只有壁纸**（converted 截图肉眼确认）
⇒ 与第89轮"`grab()` 看得见、屏幕看不见"**同型**。本脚本把中间每一个环节摊开：

  A. 绘制指令细节（每条 kind/name/rect，**逐条**打印）
  B. 素材缓存：`assets.get(name)` 是不是 null、真实像素尺寸多少
  C. `canvas.grab()` 的**离屏**位图（存 PNG）——「画布自己认为自己画了什么」
  D. 屏幕 `grabWindow(0)` 同位裁剪（存 PNG）——「合成后用户看到什么」
  E. 窗口位：`isVisible()` / `isExposed()` / `winId` / flags / z 序

★ A/B/C/D 对不上时，**哪一环断的**一目了然（这是判据侧最需要的那个"分界面"）。
"""
import ctypes
import io
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
SRC = os.path.join(PKG, 'src')
EV = os.environ.get('RECON99_EVDIR') or os.path.join(ROUND, '_evidence', 'recon')
OUT = os.path.join(EV, 'recon99c')
os.makedirs(OUT, exist_ok=True)

SCENE = os.environ.get('RECON99_SCENE', 'ch1.card_castle.card_castle_1f')
SECS = int(os.environ.get('RECON99_SECS', '18'))

os.chdir(PKG)
if SRC in sys.path:
    sys.path.remove(SRC)
sys.path.insert(0, SRC)

import main as M                                                  # noqa: E402
from PyQt5.QtWidgets import QApplication                           # noqa: E402
from PyQt5.QtCore import QTimer                                    # noqa: E402

M.check_single_instance()
M.install_crash_guard()
try:
    import text_segmenter
    text_segmenter.install()
except Exception:
    pass
try:
    import data_store
    data_store.migrate_from_staging()
except Exception:
    pass

app = QApplication(sys.argv)
window = M.RalseiPet()
window.show()
try:
    window.BEDTIME_ENABLED = False
except Exception:
    pass
try:
    M.RalseiPet.NPC_AUTONOMOUS_MOVE = False
except Exception:
    pass
try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

_scr = app.primaryScreen()
_log = io.open(os.path.join(OUT, 'recon99c_diag.txt'), 'w',
               encoding='utf-8', newline='\n')


def W(s):
    _log.write(s + u'\n')
    _log.flush()
    print(s.encode('utf-8', 'replace').decode('utf-8', 'replace'))
    sys.stdout.flush()


def _g(o, n, d=None):
    try:
        return getattr(o, n, d)
    except Exception:
        return d


_u32 = ctypes.windll.user32


def _zorder_map():
    order, h, i = {}, _u32.GetTopWindow(None), 0
    while h and i < 4000:
        order[int(h)] = i
        h = _u32.GetWindow(h, 2)      # GW_HWNDNEXT
        i += 1
    return order


def _cls(h):
    try:
        b = ctypes.create_unicode_buffer(256)
        _u32.GetClassNameW(int(h), b, 256)
        return b.value
    except Exception:
        return ''


def _save_pm(pm, path):
    try:
        ok = pm.save(path, 'PNG')
        W(u'    [saved %s ok=%r %s]'
          % (os.path.basename(path), ok,
             (u'%.1f KB' % (os.path.getsize(path) / 1024.0))
             if os.path.exists(path) else u''))
    except Exception as e:
        W(u'    [save FAIL %r]' % (e,))


def diag(tag):
    W(u'')
    W(u'================ %s t=%.2f ================' % (tag, time.time() - _t0))
    canvas = _g(window, 'scene_canvas')
    scene = _g(window, 'scene')
    cam = window.__dict__.get('_scene_camera')
    try:
        W(u'scene=%r  default_scene=%r'
          % (_g(window, 'current_scene'), _g(scene, '_index', {})))
    except Exception:
        pass
    try:
        W(u'canvas.isVisible()=%r  isExposed=%r  winId=%r  cls=%r'
          % (canvas.isVisible(), _g(canvas, 'isExposed')(),
             int(canvas.winId()), _cls(int(canvas.winId()))))
    except Exception as e:
        W(u'canvas 窗口位读取失败 %r' % (e,))
    try:
        W(u'canvas.geometry=%r  view_size=%r  last_drawn=%r  scale=(%r,%r)'
          % (canvas.geometry().getRect(), canvas.view_size(),
             canvas.last_drawn, canvas._scale_x, canvas._scale_y))
    except Exception:
        pass
    try:
        zo = _zorder_map()
        W(u'z_canvas=%r z_pet=%r  画布类=%r'
          % (zo.get(int(canvas.winId())), zo.get(int(window.winId())),
             _cls(int(canvas.winId()))))
    except Exception:
        pass
    try:
        W(u'cam=%r' % ((cam.rect, cam.scale, cam.size) if cam else None,))
    except Exception:
        pass

    # ---- A. 绘制指令逐条 ----
    plan = None
    try:
        plan = canvas.plan()
    except Exception as e:
        W(u'plan() 失败 %r' % (e,))
    W(u'--- A. 画布当前 plan（%s 条）---' % (len(plan or [])))
    for i, it in enumerate(plan or []):
        W(u'   [%d] kind=%r name=%r rect=%r alpha=%r'
          % (i, it.get('kind'), it.get('name'), it.get('rect'), it.get('alpha')))

    # ---- A2. 现场重算一遍 plan_frame（看"每帧产物"是否一致）----
    try:
        live = scene.plan_frame(sprite_size=canvas.assets.sprite_size,
                                tick=int(time.time() * 1000), bubbles=None)
        W(u'--- A2. 现场 plan_frame = %d 条 ---' % len(live))
        for i, it in enumerate(live):
            W(u'   <live %d> kind=%r name=%r rect=%r'
              % (i, it.get('kind'), it.get('name'), it.get('rect')))
        W(u'    plan_viewport() = %r' % (scene.plan_viewport(),))
    except Exception:
        W(u'plan_frame 失败\n' + traceback.format_exc())

    # ---- B. 素材缓存 ----
    W(u'--- B. 素材缓存 ---')
    try:
        names = set()
        for it in (plan or []) + []:
            if it.get('name'):
                names.add(it.get('name'))
        for nm in sorted(names):
            pm = canvas.assets.get(nm)
            W(u'   get(%r) -> %s  null=%r  size=%r'
              % (nm, type(pm).__name__ if pm is not None else None,
                 (pm.isNull() if pm is not None else None),
                 ((pm.width(), pm.height()) if pm is not None else None)))
        W(u'   assets.base_dir=%r' % (getattr(canvas.assets, 'base_dir', '?'),))
        W(u'   缓存键=%r' % (sorted(list(getattr(canvas.assets, '_cache', {}) or {}))[:20],))
    except Exception:
        W(u'素材缓存读取失败\n' + traceback.format_exc())

    # ---- C. 画布离屏 grab ----
    W(u'--- C. canvas.grab()（画布自己认为画了什么）---')
    try:
        pm = canvas.grab()
        W(u'   grab 尺寸=%r' % ((pm.width(), pm.height()),))
        _save_pm(pm, os.path.join(OUT, 'canvas_grab_%s.png' % tag.replace(' ', '_')))
        img = pm.toImage()
        # 统计非全透明像素（判"画布上真有东西"）
        nz = 0
        for y in range(0, img.height(), 4):
            for x in range(0, img.width(), 4):
                if (img.pixel(x, y) >> 24) & 0xFF:
                    nz += 1
        W(u'   grab 非透明采样点=%d（每 4px 采一点，共 %d 点）'
          % (nz, ((img.width() // 4) + 1) * ((img.height() // 4) + 1)))
    except Exception:
        W(u'grab 失败\n' + traceback.format_exc())

    # ---- D. 屏幕同位裁剪 ----
    W(u'--- D. 屏幕 grabWindow(0) 画布位裁剪 ---')
    try:
        sp = _scr.grabWindow(0)
        g = canvas.geometry()
        crop = sp.copy(g)
        _save_pm(crop, os.path.join(OUT, 'screen_crop_%s.png' % tag.replace(' ', '_')))
        im2 = crop.toImage()
        nz2 = 0
        for y in range(0, im2.height(), 4):
            for x in range(0, im2.width(), 4):
                if im2.pixel(x, y) != 0xFF000000:
                    nz2 += 1
        W(u'   屏幕裁剪非黑采样点=%d' % nz2)
        # 参照：壁纸原始色（画布区正中）
        c = im2.pixel(im2.width() // 2, im2.height() // 2)
        W(u'   屏幕裁剪正中像素=%08x' % c)
    except Exception:
        W(u'屏幕裁剪失败\n' + traceback.format_exc())


_t0 = time.time()
diag('BEFORE-TRAVEL')


def _go():
    W(u'>>> travel_to_scene(%r)' % SCENE)
    try:
        W(u'    -> %r' % (window.travel_to_scene(SCENE),))
    except Exception:
        W(u'FAIL\n' + traceback.format_exc())

    def _after():
        diag('AFTER-TRAVEL')

    QTimer.singleShot(1500, _after)


QTimer.singleShot(5000, _go)


def _bye():
    app.quit()


QTimer.singleShot(SECS * 1000, _bye)

if __name__ == '__main__':
    rc = app.exec_()
    W(u'[recon99c] exit rc=%d' % rc)
    _log.close()
    sys.exit(rc)
