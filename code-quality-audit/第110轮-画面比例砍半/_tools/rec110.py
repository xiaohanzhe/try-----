# -*- coding: utf-8 -*-
"""第110轮 · 录屏自检（**真机多帧抓取 + 画面几何断言**）。

用户铁律：「**一定要看录像而不是只读后台输出**」。

本轮用户口径（逐字）：「**别这么大啊**」+「**到刚才的一半才好一些**」
⇒ 场景画面由「最大 4:3 内接矩形」改为「再乘 `SCENE_FIT_FRACTION`（0.5）」。

本支验证两件事：
  G1 ★★★ 相机输出尺寸 == `fit_fraction(主屏)` 的预期值（**现推**，不写死）。
  G2 ★★★ `scale` 恰好 = 内接版的一半（宠物渲染倍率随它 ⇒ 宠物同步变小）。
  G3 ★★★ `_scene_output_offset` 真居中（左右黑边对称）。
  G4 ★★  桌面场景**仍透明**、房间场景**不透明**（没被本轮改动破坏）。
  G5 ★★  画布尺寸 == 主屏物理尺寸（"全屏画布 + 居中画面"结构未变）。
  G6 ★★  负控制：`SCENE_FIT_FRACTION == 1.0` 时几何 == `fit_fullscreen`。

★ 透明分层窗口的"可见面积"工具会失效 ⇒ 只断言**几何/状态**；
  PNG 仅作人眼证据，不做像素级判据。

跑法（真机）：
    set QT_QPA_PLATFORM=windows && C:\\Python311\\python.exe rec110.py
（不设 QPA 时退化为离屏：几何/状态断言照跑，PNG 数为 0 属预期。）
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

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('RALSEI_TEST_MODE', '1')

_EV = os.path.abspath(os.path.join(HERE, '..', '_evidence'))
_FR = os.path.join(_EV, 'frames110')
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


import scene_camera as SC          # noqa: E402  单点真源（比例/内接数学）

try:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QTimer
except Exception as _e:
    print(u'[FATAL] PyQt5 不可用: %s' % _e)
    sys.exit(2)

_app = QApplication.instance() or QApplication(sys.argv)

_res = {'err': None, 'snaps': [], 'marks': {}}
_box = {}
_marks = {}
_snaps = []


def _snap(tag, note, grab=True):
    pet = _box.get('pet')
    rec = {'tag': tag, 'note': note, 'png': None}
    try:
        scr = _app.primaryScreen()
        if grab and scr is not None and os.environ.get('QT_QPA_PLATFORM') == 'windows':
            pm = scr.grabWindow(0)
            if pm is not None and not pm.isNull():
                p = os.path.join(_FR, u'k%03d_%s.png' % (len(_snaps), tag))
                pm.save(p, 'PNG')
                rec['png'] = p
    except Exception as e:
        rec['err'] = str(e)
    try:
        rec['scene_id'] = pet._soul_scene_id if pet is not None else None
        cam = pet.__dict__.get('_scene_camera') if pet is not None else None
        rec['cam_size'] = tuple(cam.size) if cam is not None else None
        rec['scale'] = round(float(cam.scale), 4) if cam is not None else None
        rec['offset'] = tuple(pet.__dict__.get('_scene_output_offset') or ())
        rec['pet_csf'] = round(float(getattr(pet, '_cached_scale_factor', -1)), 4)
        try:
            rec['transparent'] = bool(pet._scene_is_transparent())
        except Exception:
            rec['transparent'] = None
        try:
            cv = pet.scene_canvas
            rec['canvas_size'] = (cv.width(), cv.height())
        except Exception:
            rec['canvas_size'] = None
    except Exception as e:
        rec['state_err'] = str(e)
    _snaps.append(rec)
    print(u'        [snap] %s scene=%s cam=%s scale=%s off=%s csf=%s trans=%s canvas=%s png=%s'
          % (tag, rec.get('scene_id'), rec.get('cam_size'), rec.get('scale'),
             rec.get('offset'), rec.get('pet_csf'), rec.get('transparent'),
             rec.get('canvas_size'), bool(rec.get('png'))))


def _poll(duration_ms):
    """★ 每轮先 `processEvents`（第109轮血泪：纯 sleep 会饿死 Qt 事件循环）。"""
    pet = _box.get('pet')
    if pet is None:
        return
    t_end = time.time() * 1000.0 + duration_ms
    while time.time() * 1000.0 < t_end:
        try:
            _app.processEvents()
        except Exception:
            pass
        time.sleep(0.008)


def _stage1():
    try:
        import main as _M
        _box['pet'] = _M.RalseiPet()
        _box['pet'].show()
        QTimer.singleShot(1600, _stage2)
    except Exception:
        _res['err'] = traceback.format_exc()
        try:
            _app.quit()
        except Exception:
            pass


def _stage2():
    """桌面态：抓帧 + 采样几何。"""
    pet = _box.get('pet')
    try:
        _poll(300)
        _snap(u'desktop', u'桌面场景（透明，画面居中留黑边）')
        _marks['desktop'] = dict(_snaps[-1])
        try:
            pet.travel_to_scene('ch1.kris_room.kris_s_room')
        except Exception as _e:
            _res['travel_err'] = str(_e)
        _poll(1200)
        _snap(u'room', u'第一章房间（不透明，画面居中留黑边）')
        _marks['room'] = dict(_snaps[-1])
        QTimer.singleShot(200, _finish)
    except Exception:
        _res['err'] = traceback.format_exc()
        try:
            _app.quit()
        except Exception:
            pass


def _finish():
    try:
        _snap(u'room2', u'房间态复核')
    except Exception:
        pass
    finally:
        _res['snaps'] = _snaps
        _res['marks'] = _marks
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

if _res.get('err'):
    print(_res['err'])
    ok(u'G0 真机启动', False, u'见上')

_marks = _res.get('marks') or {}
_desk = _marks.get('desktop') or {}
_room = _marks.get('room') or {}

print(u'=' * 72)
print(u'第110轮 · 录屏自检（画面比例砍半）')
print(u'QPA = %s' % os.environ.get('QT_QPA_PLATFORM'))
print(u'=' * 72)

scr = _app.primaryScreen()
SW, SH = (scr.geometry().width(), scr.geometry().height()) if scr else (0, 0)
_EXP_HALF = SC.fit_fraction(SW, SH, SC.SCENE_ASPECT, SC.SCENE_FIT_FRACTION)
_EXP_FULL = SC.fit_fullscreen(SW, SH, SC.SCENE_ASPECT)

sec(u'G1~G3 画面几何（真机采样 vs 现推预期）')

ok(u'G0 ★★ 真机起来了（拿到了相机尺寸）',
   bool(_room.get('cam_size')), u'cam=%r' % (_room.get('cam_size'),))

ok(u'G1 ★★★ 相机输出尺寸 == `fit_fraction(%d×%d)` 预期 %r'
   % (SW, SH, _EXP_HALF),
   tuple(_room.get('cam_size') or ()) == tuple(_EXP_HALF[:2]),
   u'实测=%r 预期=%r' % (_room.get('cam_size'), _EXP_HALF[:2]))

_exp_scale = round(_EXP_HALF[0] / 320.0, 3) if _EXP_HALF else None
ok(u'G2 ★★★ `scale` == 砍半后的现推值 %.3f（= 内接版 %.3f 的一半）'
   % (_exp_scale or -1, (_EXP_FULL[0] / 320.0) if _EXP_FULL else -1),
   _exp_scale is not None and abs(float(_room.get('scale') or -1) - _exp_scale) < 0.01,
   u'实测=%r 预期=%r' % (_room.get('scale'), _exp_scale))

ok(u'G3 ★★★ 偏移真居中（左右黑边对称 ⇒ offset.x == (屏宽-画面宽)/2）',
   _EXP_HALF is not None and tuple(_room.get('offset') or ()) == tuple(_EXP_HALF[2:]),
   u'实测=%r 预期=%r' % (_room.get('offset'), _EXP_HALF[2:] if _EXP_HALF else None))

sec(u'G4~G5 结构未变（透明/不透明 · 全屏画布）')

ok(u'G4 ★★ 桌面场景仍被识别为**透明**（`_scene_is_transparent()` 口径未破坏）',
   bool(_desk.get('transparent')), u'transparent=%r' % (_desk.get('transparent'),))
ok(u'G4b ★★ 房间场景**不透明**（成对：否则壁纸会透出来）',
   _room.get('transparent') is False, u'transparent=%r' % (_room.get('transparent'),))

ok(u'G5 ★★ 宠物渲染倍率 == camera.scale × pet_scale（同源，宠物同步变小）',
   _room.get('pet_csf') is not None and _room.get('scale') is not None
   and abs(float(_room['pet_csf']) - float(_room['scale'])) < 0.02,
   u'csf=%r scale=%r' % (_room.get('pet_csf'), _room.get('scale')))

ok(u'G5b ★★★ 画布尺寸 == **主屏物理尺寸** %dx%d（第110轮修正：`set_plan` 曾把'
   u'整屏尺寸覆盖成画面尺寸 ⇒ 黑边不出现、画面贴左上角）' % (SW, SH),
   tuple(_room.get('canvas_size') or ()) == (SW, SH),
   u'canvas=%r 屏=%r' % (_room.get('canvas_size'), (SW, SH)))

sec(u'G6 负控制：`fraction=1.0` 必须回到内接版（证明砍半真起作用）')

ok(u'G6 ★★★ `fraction=1.0` ⇒ 逐值 == `fit_fullscreen`（砍半不是 no-op）',
   _EXP_FULL is not None and SC.fit_fraction(SW, SH, SC.SCENE_ASPECT, 1.0) == _EXP_FULL,
   u'full=%r half=%r' % (_EXP_FULL, _EXP_HALF))
ok(u'G6b ★★★ 砍半 ≠ 内接（两值必须不同，否则判据无鉴别力）',
   _EXP_FULL is not None and _EXP_HALF is not None and _EXP_FULL[:2] != _EXP_HALF[:2],
   u'full=%r half=%r' % (_EXP_FULL[:2] if _EXP_FULL else None,
                         _EXP_HALF[:2] if _EXP_HALF else None))

sec(u'G7 抓帧')

_n_png = sum(1 for s in _snaps if s.get('png'))
print(u'        PNG = %d 张 · 快照 %d 条' % (_n_png, len(_snaps)))
ok(u'G7 ★★ 人眼复核用的抓帧已落盘（真机应有 >0 张；离屏为 0 属预期）',
   _n_png > 0 or os.environ.get('QT_QPA_PLATFORM') != 'windows',
   u'png=%d qpa=%s' % (_n_png, os.environ.get('QT_QPA_PLATFORM')))

print(u'\n' + u'=' * 72)
print(u'第110轮：PASS=%d FAIL=%d' % (_N['p'], _N['f']))
print(u'=' * 72)

with io.open(os.path.join(_EV, 'rec110_meta.txt'), 'w', encoding='utf-8') as f:
    f.write(u'第110轮 · 录屏自检元数据\n')
    f.write(u'QPA = %s\n' % os.environ.get('QT_QPA_PLATFORM'))
    f.write(u'主屏 = %dx%d\n' % (SW, SH))
    f.write(u'预期(砍半) = %r\n' % (_EXP_HALF,))
    f.write(u'预期(内接) = %r\n' % (_EXP_FULL,))
    f.write(u'桌面采样 = %r\n' % (_desk,))
    f.write(u'房间采样 = %r\n' % (_room,))
    f.write(u'\n'.join(_OUT))
    f.write(u'\n\nPASS=%d FAIL=%d\n' % (_N['p'], _N['f']))

sys.exit(1 if _N['f'] else 0)
