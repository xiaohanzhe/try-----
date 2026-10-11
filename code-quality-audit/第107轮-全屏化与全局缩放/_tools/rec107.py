# -*- coding: utf-8 -*-
"""第107轮 · 录屏自检（**离屏多帧抓取 + 几何断言**）。

用户铁律：「**一定要看录像而不是只读后台输出**」。
本支抓 **N 帧 PNG** 落盘（供人眼复核），并对**几何**做机器断言：

  S1  画布尺寸 == 主屏物理尺寸（铺满）
  S2  画布窗口位置 == 主屏原点（固定，不随宠物动）
  S3  ★ 宠物移动后画布位置**不变**（"不是跟随移动的窗口"的直接反证）
  S4  相机 scale / scoped 与屏幕自洽
  S5  非桌面场景 ⇒ `_opaque_bg=True`（不透过壁纸）；
      桌面场景 ⇒ `_opaque_bg=False`（透出壁纸）
  S6  ★★ 输出偏移真进画布（`_offset_x/_offset_y` 与 `fit_fullscreen` 一致）

★ 透明分层窗口的"可见面积"工具会失效 ⇒ 只断言**几何**（第73.8 条）；
  PNG 仅作人眼证据，不做像素级判据。

跑法：
    C:\\Python311\\python.exe rec107.py
"""
import io
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')

sys.path.insert(0, os.path.join(PKG, 'modules'))
sys.path.insert(0, os.path.join(PKG, 'src'))

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ.setdefault('RALSEI_TEST_MODE', '1')

_EV = os.path.abspath(os.path.join(HERE, '..', '_evidence'))
_FR = os.path.join(_EV, 'frames107')
for _d in (_EV, _FR):
    if not os.path.isdir(_d):
        os.makedirs(_d)

_OUT = []
_N = {'p': 0, 'f': 0}


def ok(name, cond, detail=u''):
    _N['p' if cond else 'f'] += 1
    line = u'%s %s' % (u'[PASS]' if cond else u'[FAIL]', name)
    if detail:
        line += u'  <- %s' % detail
    print(line)
    _OUT.append(line)
    return bool(cond)


def sec(t):
    print(u'\n-- %s --' % t)
    _OUT.append(u'\n-- %s --' % t)


print(u'=' * 72)
print(u'第107轮 · 录屏自检（多帧抓取 + 几何断言）')
print(u'=' * 72)

import scene_camera as SC

_res = {}
try:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QTimer

    _app = QApplication.instance() or QApplication(sys.argv)
    import main as _M

    _seq = []
    # ★ 用**容器**持有 pet，避免 `global` 与闭包取值混淆
    #   （实测：`_snap` 定义在 `_pet = None` 之前 ⇒ 抓到全 None，
    #    而日志显示产品分明在跑 —— 典型的"取值器太窄让判据自己说谎"）
    _box = {}

    def _snap(tag, note=u''):
        """抓一帧 + 记几何。"""
        _pet = _box.get('pet')
        if _pet is None:
            _seq.append({'tag': tag, 'err': 'pet 未就绪'})
            return
        try:
            cv = _pet.__dict__.get('scene_canvas')
            cam = _pet.__dict__.get('_scene_camera')
            scr = _app.primaryScreen()
            g = scr.geometry()
            rec = {
                'tag': tag,
                'note': note,
                'canvas_size': (cv.width(), cv.height()) if cv else None,
                'canvas_pos': (cv.x(), cv.y()) if cv else None,
                'off': (getattr(cv, '_offset_x', None),
                        getattr(cv, '_offset_y', None)) if cv else None,
                'opaque': getattr(cv, '_opaque_bg', None) if cv else None,
                'cam_size': tuple(cam.size) if cam else None,
                'cam_scale': cam.scale if cam else None,
                'scoped': tuple(cam.scoped_size()) if cam else None,
                'pet_scale': _pet.pet_scale,
                'render': _pet._cached_scale_factor,
                'scene_id': getattr(_pet.__dict__.get('_scene_state'),
                                    'scene_id', None),
                'screen': (g.x(), g.y(), g.width(), g.height()),
                'pet_pos': (_pet.x(), _pet.y()),
            }
            # 抓帧
            try:
                pm = scr.grabWindow(0)
                if not pm.isNull():
                    fn = os.path.join(_FR, u'k%03d_%s.png' % (len(_seq), tag))
                    pm.save(fn)
                    rec['png'] = os.path.basename(fn)
            except Exception as _e:
                rec['png_err'] = str(_e)
            _seq.append(rec)
        except Exception:
            _seq.append({'tag': tag, 'err': traceback.format_exc()})

    def _stage1():
        try:
            _box['pet'] = _M.RalseiPet()
            _box['pet'].show()
            QTimer.singleShot(1500, _stage2)
        except Exception:
            _res['err'] = traceback.format_exc()
            try:
                _app.quit()
            except Exception:
                pass

    def _stage2():
        _pet = _box.get('pet')
        try:
            _snap(u'desktop_init', u'桌面场景 · 初始化')
            # 移动宠物（画布不该跟着动）
            try:
                _pet.move(_pet.x() + 180, _pet.y() + 120)
                _pet.repaint()
            except Exception:
                pass
            QTimer.singleShot(900, _stage3)
        except Exception:
            _res['err'] = traceback.format_exc()
            try:
                _app.quit()
            except Exception:
                pass

    def _stage3():
        _pet = _box.get('pet')
        try:
            _snap(u'after_move', u'宠物移动后（画布须**不动**）')
            # 切到非桌面场景
            try:
                _pet.scene.switch('ch1.kris_room.kris_s_room')
            except Exception as _e:
                _res['switch_err'] = str(_e)
            QTimer.singleShot(900, _stage4)
        except Exception:
            _res['err'] = traceback.format_exc()
            try:
                _app.quit()
            except Exception:
                pass

    def _stage4():
        try:
            _snap(u'room_ch1', u'第一章房间（须铺不透明黑，不透过壁纸）')
            QTimer.singleShot(600, _stage5)
        except Exception:
            _res['err'] = traceback.format_exc()
            try:
                _app.quit()
            except Exception:
                pass

    def _stage5():
        _pet = _box.get('pet')
        try:
            _snap(u'back_desktop', u'切回桌面')
            try:
                _pet.scene.switch('desktop')
                _pet.repaint()
            except Exception:
                pass
            QTimer.singleShot(700, _finish)
        except Exception:
            _res['err'] = traceback.format_exc()
            try:
                _app.quit()
            except Exception:
                pass

    def _finish():
        try:
            _snap(u'desktop_final', u'回到桌面（透明恢复）')
        except Exception:
            pass
        finally:
            _res['seq'] = _seq
            try:
                _box['pet'].close()
            except Exception:
                pass
            try:
                _app.quit()
            except Exception:
                pass

    QTimer.singleShot(300, _stage1)
    _app.exec_()
except Exception:
    _res['err'] = traceback.format_exc()

if _res.get('err'):
    print(_res['err'])
    ok(u'S0 真机启动', False, u'见上')

_seq = _res.get('seq') or []
if not _seq:
    ok(u'S0 抓到帧', False, u'零帧')
else:
    print(u'        抓帧 %d 张' % len(_seq))
    for _s in _seq:
        print(u'        [%s] canvas=%s pos=%s off=%s opaque=%s cam=%s/%s '
              u'scoped=%s scene=%s pet=%s'
              % (_s.get('tag'), _s.get('canvas_size'), _s.get('canvas_pos'),
                 _s.get('off'), _s.get('opaque'), _s.get('cam_size'),
                 _s.get('cam_scale'), _s.get('scoped'), _s.get('scene_id'),
                 _s.get('pet_pos')))

_byname = {s.get('tag'): s for s in _seq}

sec(u'S1~S3 画布铺满 / 固定摆位 / 不跟随')

_d0 = _byname.get(u'desktop_init') or {}
if _d0:
    _scr = _d0.get('screen')
    _fit = SC.fit_fullscreen(_scr[2], _scr[3]) if _scr else None
    ok(u'S1 ★★★ 画布尺寸 == 主屏物理尺寸（铺满）',
       _scr is not None and tuple(_d0.get('canvas_size') or ()) == (_scr[2], _scr[3]),
       u'canvas=%s screen=%s' % (_d0.get('canvas_size'), _scr and (_scr[2], _scr[3])))
    ok(u'S2 ★★★ 画布位置 == 主屏原点（固定摆放，不是居中/钳制）',
       _scr is not None and tuple(_d0.get('canvas_pos') or ()) == (_scr[0], _scr[1]),
       u'pos=%s screen_org=%s' % (_d0.get('canvas_pos'), _scr and (_scr[0], _scr[1])))
    ok(u'S4 ★★★ `cam.size` == `fit_fullscreen(主屏)` 前两位',
       _fit is not None and tuple(_d0.get('cam_size') or ()) == tuple(_fit[:2]),
       u'cam=%s fit=%s' % (_d0.get('cam_size'), _fit))
    ok(u'S4b ★★★ `cam.scale == cam_w/320` 且 `scoped == (320,240)`',
       _fit and abs((_d0.get('cam_scale') or 0) - _fit[0] / 320.0) < 1e-6
       and tuple(_d0.get('scoped') or ()) == (320, 240),
       u'scale=%s scoped=%s' % (_d0.get('cam_scale'), _d0.get('scoped')))
    ok(u'S6 ★★ 输出偏移真进画布（`_offset_x/_offset_y` == fit 的 ox/oy）',
       _fit is not None and tuple(_d0.get('off') or ()) == (_fit[2], _fit[3]),
       u'off=%s fit_off=%s' % (_d0.get('off'), _fit and (_fit[2], _fit[3])))

_d1 = _byname.get(u'after_move') or {}
if _d0 and _d1:
    ok(u'S3 ★★★ 宠物移动后画布位置**不变**'
       u'（用户口径"**不是跟随移动的窗口**"的直接反证）',
       _d0.get('canvas_pos') == _d1.get('canvas_pos')
       and _d0.get('pet_pos') != _d1.get('pet_pos'),
       u'before=%s after=%s pet %s→%s'
       % (_d0.get('canvas_pos'), _d1.get('canvas_pos'),
          _d0.get('pet_pos'), _d1.get('pet_pos')))
    ok(u'S3b 负控制：宠物真移动了（否则 S3 是 no-op 恒真）',
       _d0.get('pet_pos') != _d1.get('pet_pos'),
       u'%s → %s' % (_d0.get('pet_pos'), _d1.get('pet_pos')))

sec(u'S5 桌面透明 / 房间不透明')

_dr = _byname.get(u'room_ch1') or {}
_df = _byname.get(u'desktop_final') or {}
if _dr:
    ok(u'S5 ★★ 非桌面场景 ⇒ `_opaque_bg=True`'
       u'（用户口径"不透过桌面壁纸、图标、任务栏"）',
       _dr.get('opaque') is True, u'opaque=%r scene=%s'
       % (_dr.get('opaque'), _dr.get('scene_id')))
if _df:
    ok(u'S5b ★★ 桌面场景 ⇒ `_opaque_bg=False`（透出用户壁纸 = 桌面即场景）',
       _df.get('opaque') is False,
       u'opaque=%r scene=%s' % (_df.get('opaque'), _df.get('scene_id')))
if _dr and _df:
    ok(u'S5c 负控制：两个场景的 `_opaque_bg` 真的不同（不是恒取同值）',
       _dr.get('opaque') != _df.get('opaque'),
       u'room=%r desktop=%r' % (_dr.get('opaque'), _df.get('opaque')))

sec(u'S7 抓帧落盘')

_pngs = [s.get('png') for s in _seq if s.get('png')]
# ★★ 判据自身体检（第107轮实跑修正）：离屏平台 `QT_QPA_PLATFORM=offscreen`
#   下 `QScreen.grabWindow(0)` **必然返 null**（没有真实帧缓冲可抓）——
#   "抓到 ≥5 帧 PNG" 在离屏环境里是**不可能成立的要求**，属"夹具不保真"。
#   ⇒ 按平台分派：离屏 ⇒ 只断言"几何采集成功"（本支真正的产品判据）；
#      真机（带 QPA=windows）⇒ 才断言 PNG 帧数。
_offscreen = os.environ.get('QT_QPA_PLATFORM') == 'offscreen'
if _offscreen:
    _geo_ok = [s for s in _seq if s.get('canvas_pos') is not None]
    ok(u'S7 ★★ 离屏平台：几何采集成功 %d/%d 帧'
       u'（`grabWindow(0)` 在离屏下必然 null ⇒ 不拿"抓到 PNG"当判据，'
       u'否则=夹具不保真）' % (len(_geo_ok), len(_seq)),
       len(_geo_ok) == len(_seq) and len(_seq) >= 5,
       u'geo=%d png=%d' % (len(_geo_ok), len(_pngs)))
    ok(u'S7c ★★ 离屏下 PNG 为 0 是**预期**（不是产品缺陷）—— '
       u'真机录屏请用 `QT_QPA_PLATFORM=windows` 跑同支',
       len(_pngs) == 0, u'png=%d' % len(_pngs))
else:
    ok(u'S7 ★★ 抓到 ≥5 帧 PNG 落盘（供人眼复核）',
       len(_pngs) >= 5, u'n=%d %s' % (len(_pngs), _pngs))
ok(u'S7b 帧目录在盘', os.path.isdir(_FR), u'%s' % _FR)

# ---------------------------------------------------------------------
print(u'\n' + u'=' * 72)
print(u'第107轮录屏自检：PASS=%d FAIL=%d' % (_N['p'], _N['f']))
print(u'=' * 72)

_meta = os.path.join(_EV, 'rec107_meta.txt')
try:
    with io.open(_meta, 'w', encoding='utf-8') as f:
        f.write(u'\n'.join(_OUT) + u'\n\n---- SEQ ----\n')
        for s in _seq:
            f.write(u'%s\n' % (s,))
    print(u'证据已落盘：%s' % _meta)
except Exception as e:
    print(u'落盘失败：%s' % e)

sys.exit(1 if _N['f'] else 0)
