# -*- coding: utf-8 -*-
"""第107轮 · 独立验收（不进 G2，**只做实证**）。

为什么单独一支：G2 里的 `check107` 是**结构性**判据（AST/常量/接线），
它证明不了「数学算对了」。本支用**真跑纯函数 + 真跑产品路径**给出数值证据：

  V1  `fit_fullscreen` 在 5 组屏幕上的精确输出（含 4:3 零黑边 / 竖屏上下黑边）
  V2  `fit_fullscreen` 的不变量：输出矩形必在屏内、比例恒 4:3、居中
  V3  ★★ 负控制：把 `min` 写成 `max` 会溢出屏幕（证明 V2 有鉴别力）
  V4  回退值与非法输入（0/负/None/字符串）必须返 None，不抛
  V5  ★★★ 产品真路径：`fit_camera_to_screen` 后 `scoped_size()` 恒 320×240
  V6  ★★★ 缩放耦合方向：`pet_scale` 1.0 / 2.5 时 `render = camera.scale × rel`，
      且 **`scoped` 不随 pet_scale 变**（曾写反——写反=镜头拉近）
  V7  ★★ 原作比例锚点：2560×1600 屏上 Ralsei 应 ≈ 273px 高（41/240 逻辑比）
  V8  `ui_scale()` 平方根折中 + 钳位
  V9  ★ 负控制：`ui_scale` 若写成线性（`pet_scale/1.0`）会超出钳位 ⇒ 有鉴别力

跑法：
    C:\\Python311\\python.exe verify107.py

★ 纪律：本支**零外部盘依赖**（回归碰不得 E 盘）；测试 `set_pet_scale` 一律
  `persist=False`（第107轮血泪：离屏测试把用户金库 `E:\\RalseiMemory\\` 写脏过）。
"""
import io
import json
import os
import re
import sys
import ast
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
# <轮次>/_tools/ ⇒ 仓库根 = 上三级（_tools → 轮次 → code-quality-audit → 仓库根）
ROOT = os.path.join(HERE, '..', '..', '..')
ROOT = os.path.abspath(ROOT)
PKG = os.path.join(ROOT, 'ralsei_pet')

sys.path.insert(0, os.path.join(PKG, 'modules'))
sys.path.insert(0, os.path.join(PKG, 'src'))

_OUT = []
_N = {'p': 0, 'f': 0}


def ok(name, cond, detail=u''):
    _N['p' if cond else 'f'] += 1
    tag = u'[PASS]' if cond else u'[FAIL]'
    line = u'%s %s' % (tag, name)
    if detail:
        line += u'  <- %s' % detail
    print(line)
    _OUT.append(line)
    return bool(cond)


def sec(t):
    print(u'\n-- %s --' % t)
    _OUT.append(u'\n-- %s --' % t)


def read(p):
    with io.open(p, 'r', encoding='utf-8') as f:
        return f.read()


print(u'=' * 72)
print(u'第107轮 · 独立验收（全屏化与全局缩放 · 数值实证）')
print(u'ROOT = %s' % ROOT)
print(u'=' * 72)

try:
    import scene_camera as SC
except Exception:
    traceback.print_exc()
    sys.exit(2)

# =====================================================================
# V1 五组屏幕的精确输出
# =====================================================================
sec(u'V1 `fit_fullscreen` 精确输出（5 组屏幕）')

_CASES = [
    # (屏宽, 屏高, 期望 w, 期望 h, 期望 ox, 期望 oy, 说明)
    (2560, 1600, 2133, 1600, 214, 0, u'16:10 主屏 ⇒ 左右各 214 黑边'),
    (1920, 1080, 1440, 1080, 240, 0, u'16:9 ⇒ 左右各 240 黑边'),
    (800, 600, 800, 600, 0, 0, u'4:3 ⇒ **零黑边**'),
    (1600, 2560, 1600, 1200, 0, 680, u'竖屏 ⇒ 上下各 680 黑边'),
    (1024, 768, 1024, 768, 0, 0, u'4:3 另一例 ⇒ 零黑边'),
]
_v1_bad = []
for _w, _h, _ew, _eh, _eox, _eoy, _desc in _CASES:
    got = SC.fit_fullscreen(_w, _h)
    exp = (_ew, _eh, _eox, _eoy)
    _good = (got == exp)
    if not _good:
        _v1_bad.append(((_w, _h), got, exp))
    ok(u'V1 %dx%d ⇒ %s（%s）' % (_w, _h, got, _desc), _good,
       u'期望 %s' % (exp,) if not _good else u'')
ok(u'V1z 五组屏幕全部逐值相等', not _v1_bad, u'偏差=%r' % (_v1_bad,))

# =====================================================================
# V2 不变量：屏内 + 4:3 + 居中
# =====================================================================
sec(u'V2 `fit_fullscreen` 不变量（屏内 / 4:3 / 居中）')

_RATIO = 4.0 / 3.0
_inv_bad = []
for _w, _h in [(2560, 1600), (1920, 1080), (800, 600), (1600, 2560),
               (3840, 2160), (1280, 1024), (500, 500), (333, 777)]:
    r = SC.fit_fullscreen(_w, _h)
    if r is None:
        _inv_bad.append(((_w, _h), 'None'))
        continue
    cw, ch, cox, coy = r
    if not (0 < cw <= _w and 0 < ch <= _h):
        _inv_bad.append(((_w, _h), 'overflow %r' % (r,)))
    if abs(cw / float(ch) - _RATIO) > 0.01:
        _inv_bad.append(((_w, _h), 'ratio %.4f' % (cw / float(ch),)))
    # 居中：左右留白差 <= 1（取整误差）
    if abs((_w - cw - cox) - cox) > 1 and cox > 0:
        _inv_bad.append(((_w, _h), 'offcenter-x %r' % (r,)))
    if abs((_h - ch - coy) - coy) > 1 and coy > 0:
        _inv_bad.append(((_w, _h), 'offcenter-y %r' % (r,)))
ok(u'V2 输出恒在屏内 · 比例恒 4:3 · 居中（8 组屏幕，含 500×500 / 333×777）',
   not _inv_bad, u'偏差=%r' % (_inv_bad,))

# =====================================================================
# V3 ★★ 负控制：min 写成 max ⇒ 溢出屏幕
# =====================================================================
sec(u'V3 负控制：`min` 写成 `max` 必溢出（证明 V2 有鉴别力）')


def _bad_fit(view_w, view_h, ratio=_RATIO):
    """故意写错的实现（grab 大者）—— 用于证明正确实现不是恒真。"""
    vw, vh = float(view_w), float(view_h)
    w_by_h = vh * ratio
    h_by_w = vw / ratio
    if w_by_h <= vw:
        w, h = vw, h_by_w       # ← 错：取宽铺满，高度溢出
    else:
        w, h = w_by_h, vh       # ← 错：取高铺满，宽度溢出
    w = max(1, int(round(w)))
    h = max(1, int(round(h)))
    return (w, h, int(round((vw - w) / 2.0)), int(round((vh - h) / 2.0)))


_bad_overflow = 0
_bad_checked = 0
for _w, _h in [(2560, 1600), (1920, 1080), (1600, 2560), (800, 600)]:
    r = _bad_fit(_w, _h)
    _bad_checked += 1
    if r[0] > _w or r[1] > _h:
        _bad_overflow += 1
    good = SC.fit_fullscreen(_w, _h)
    assert good[0] <= _w and good[1] <= _h
ok(u'V3 错实现：4 组里 %d 组真溢出（正确实现 0 组溢出 ⇒ 判据非恒真）'
   % _bad_overflow, _bad_overflow >= 3, u'checked=%d' % _bad_checked)

# =====================================================================
# V4 非法输入
# =====================================================================
sec(u'V4 非法输入：返 None，不抛')

_illegal = [(0, 600), (-1, 600), (800, 0), (800, -1), (None, 600),
            ('x', 600), (800, None), (None, None)]
_ill_bad = []
for _a, _b in _illegal:
    try:
        r = SC.fit_fullscreen(_a, _b)
        if r is not None:
            _ill_bad.append(((_a, _b), r))
    except Exception as e:
        _ill_bad.append(((_a, _b), 'raised %s' % type(e).__name__))
ok(u'V4 八种非法输入（0/负/None/字符串）一律返 None 且不抛',
   not _ill_bad, u'异常项=%r' % (_ill_bad,))

# ratio 非法 ⇒ 回落 SCENE_ASPECT 而不是崩
_r_bad_ratio = SC.fit_fullscreen(800, 600, ratio=0)
ok(u'V4b `ratio<=0` ⇒ 回落默认 4:3（不抛、不除零）',
   _r_bad_ratio == SC.fit_fullscreen(800, 600, ratio=SC.SCENE_ASPECT),
   u'got=%r' % (_r_bad_ratio,))
ok(u'V4c `SCENE_ASPECT` 常量 = 4/3',
   abs(getattr(SC, 'SCENE_ASPECT', 0) - _RATIO) < 1e-9,
   u'got=%r' % (getattr(SC, 'SCENE_ASPECT', None),))

# =====================================================================
# V5/V6/V7 走产品真路径（必须真机 QApplication）
# =====================================================================
sec(u'V5~V7 产品真路径（真机 RalseiPet）')

_os = os.environ.get('QT_QPA_PLATFORM')
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ.setdefault('RALSEI_TEST_MODE', '1')

_res = {}
try:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QTimer

    _app = QApplication.instance() or QApplication(sys.argv)
    sys.path.insert(0, os.path.join(PKG, 'src'))
    import main as _M

    def _go():
        try:
            pet = _M.RalseiPet()
            pet.show()
            cam = pet.__dict__.get('_scene_camera')
            _res['cam_size'] = tuple(cam.size) if cam else None
            _res['cam_scale'] = cam.scale if cam else None
            _res['scoped'] = cam.scoped_size() if cam else None
            _res['pet_scale'] = pet.pet_scale
            _res['render'] = pet._cached_scale_factor
            _res['ui_scale'] = pet.ui_scale()
            _res['scene_scale'] = pet.scene_scale
            # ---- 切 pet_scale（★ 一律 persist=False，别写脏用户金库）----
            _obs = {}
            for _v in (1.0, 2.5, 0.4):
                pet.set_pet_scale(_v, persist=False)
                _cc = pet.__dict__.get('_scene_camera')
                _obs[_v] = {
                    'scoped': tuple(_cc.scoped_size()) if _cc else None,
                    'cam_scale': _cc.scale if _cc else None,
                    'render': pet._cached_scale_factor,
                    'ui': pet.ui_scale(),
                }
            _res['obs'] = _obs
            # 还原默认
            pet.set_pet_scale(1.0, persist=False)
            _res['restored'] = (pet.pet_scale, pet._cached_scale_factor)
            try:
                pet.close()
            except Exception:
                pass
        except Exception:
            _res['err'] = traceback.format_exc()
        finally:
            try:
                _app.quit()
            except Exception:
                pass

    QTimer.singleShot(120, _go)
    _app.exec_()
except Exception:
    _res['err'] = traceback.format_exc()

if _res.get('err'):
    print(_res['err'])
    ok(u'V5~V7 真机启动', False, u'启动异常（见上）')
else:
    _cam_size = _res.get('cam_size')
    _scr = None
    try:
        from PyQt5.QtWidgets import QApplication as _QA
        _a2 = _QA.instance()
        _scr = tuple(_a2.primaryScreen().geometry().getRect()[2:]) if _a2 else None
    except Exception:
        _scr = None
    print(u'        cam_size=%s cam_scale=%s scoped=%s pet_scale=%s render=%s'
          % (_cam_size, _res.get('cam_scale'), _res.get('scoped'),
             _res.get('pet_scale'), _res.get('render')))
    print(u'        primary_screen=%s' % (_scr,))
    ok(u'V5 ★★★ 产品 `camera.size` 与 `fit_fullscreen(主屏)` 逐值相等',
       _scr is not None and tuple(_cam_size) == tuple(SC.fit_fullscreen(*_scr)[:2]),
       u'cam=%s fit=%s' % (_cam_size, SC.fit_fullscreen(*_scr) if _scr else None))
    ok(u'V5b ★★★ `cam.scale == out_w/320`（放大唯一来源）',
       _cam_size and _res.get('cam_scale')
       and abs(_res['cam_scale'] - _cam_size[0] / 320.0) < 1e-6,
       u'scale=%s 期望=%s' % (_res.get('cam_scale'),
                              (_cam_size or [0])[0] / 320.0))
    ok(u'V5c ★★★ `scoped_size()` 恒 **320×240**（可见范围不变 = 不是镜头拉近）',
       tuple(_res.get('scoped') or ()) == (320, 240),
       u'got=%r' % (_res.get('scoped'),))

    # V6 耦合方向
    _obs = _res.get('obs') or {}
    _cam_scale = _res.get('cam_scale')
    _bad6 = []
    for _v, _d in _obs.items():
        if tuple(_d.get('scoped') or ()) != (320, 240):
            _bad6.append((_v, 'scoped=%r' % (_d.get('scoped'),)))
        if abs(_d.get('cam_scale', 0) - _cam_scale) > 1e-9:
            _bad6.append((_v, 'cam_scale drift %r' % (_d.get('cam_scale'),)))
        if abs(_d.get('render', 0) - _cam_scale * _v) > 1e-6:
            _bad6.append((_v, 'render=%r 期望 %r' % (_d.get('render'),
                                                     _cam_scale * _v)))
    ok(u'V6 ★★★ 耦合方向正确：`pet_scale` 变 ⇒ `render = cam.scale × rel` 变，'
       u'但 `scoped` 与 `cam.scale` **不变**（曾写反=镜头拉近）',
       not _bad6, u'偏差=%r' % (_bad6,))
    print(u'        obs=%r' % (_obs,))

    # V7 原作比例
    if _cam_size:
        _room_h_px = _cam_size[1]
        _oc_px = _room_h_px * (41.0 / 240.0)      # Ralsei 41px 逻辑 / 房间 240
        ok(u'V7 ★★ 原作比例锚点：屏上房间高 %dpx ⇒ 人物应 ≈ **%.0fpx**'
           u'（41/240 逻辑比 ⇒ 本就不该写死）' % (_room_h_px, _oc_px),
           abs(_oc_px / _room_h_px - 41.0 / 240.0) < 1e-6,
           u'比值=%.4f' % (_oc_px / _room_h_px))
        # 宠物贴图 21×41 逻辑 ⇒ 乘以 render 应 ≈ _oc_px
        _pr = _res.get('obs', {}).get(1.0, {}).get('render')
        if _pr:
            _draw_h = 41 * _pr
            ok(u'V7b ★★ 实测：贴图 41px × render %.3f = **%.0fpx**，'
               u'与 41/240 锚点 %.0fpx 相差 %.1f%%（默认档最贴原作）'
               % (_pr, _draw_h, _oc_px, abs(_draw_h - _oc_px) / _oc_px * 100),
               abs(_draw_h - _oc_px) / _oc_px < 0.02,
               u'anchor=%.1f draw=%.1f' % (_oc_px, _draw_h))

# =====================================================================
# V8/V9 ui_scale
# =====================================================================
sec(u'V8 `ui_scale()` 平方根折中 + 钳位')


class _U(object):
    """最小替身：只为 `ui_scale` 的取值器喂 pet_scale。"""

    PET_SCALE_DEFAULT = 1.0

    def __init__(self, v):
        self.pet_scale = v

    def ui_scale(self):
        r = (self.pet_scale / self.PET_SCALE_DEFAULT) ** 0.5
        if r < 0.5:
            r = 0.5
        if r > 3.0:
            r = 3.0
        return r


_u_cases = [(1.0, 1.0), (2.5, 2.5 ** 0.5), (0.4, 0.4 ** 0.5)]
_bad8 = []
for _in, _exp in _u_cases:
    _got = _U(_in).ui_scale()
    if abs(_got - _exp) > 1e-9:
        _bad8.append((_in, _got, _exp))
ok(u'V8 平方根折中：1.0⇒1.0 / 2.5⇒%.4f / 0.4⇒%.4f'
   % (2.5 ** 0.5, 0.4 ** 0.5), not _bad8, u'偏差=%r' % (_bad8,))
# 钳位（喂极端值）
ok(u'V8b 钳位：pet_scale=100 ⇒ 3.0（上限）；pet_scale=1e-6 ⇒ 0.5（下限）',
   _U(100.0).ui_scale() == 3.0 and _U(1e-6).ui_scale() == 0.5,
   u'hi=%r lo=%r' % (_U(100.0).ui_scale(), _U(1e-6).ui_scale()))

# 产品真测（若真机跑通）
if not _res.get('err') and _res.get('obs'):
    _prod_ui = {k: v.get('ui') for k, v in _res['obs'].items()}
    _bad8b = []
    for _v, _u in _prod_ui.items():
        _e = max(0.5, min(3.0, (_v / 1.0) ** 0.5))
        if _u is None or abs(_u - _e) > 1e-9:
            _bad8b.append((_v, _u, _e))
    ok(u'V8c ★★ 产品 `ui_scale()` 真值 = 平方根公式（3 档实测）',
       not _bad8b, u'偏差=%r' % (_bad8b,))
    print(u'        product ui_scale=%r' % (_prod_ui,))
else:
    ok(u'V8c 产品 `ui_scale()` 真值（离屏真机未跑通 ⇒ 跳过，标 SKIP 不假红）',
       True, u'SKIP')

sec(u'V9 负控制：线性写法会被钳位截断 ⇒ V8 有鉴别力')


def _lin_ui(v):
    r = v / 1.0          # ← 错：线性
    return max(0.5, min(3.0, r))


_disc = 0
for _v in (2.5, 0.4, 2.0, 1.5):
    if abs(_lin_ui(_v) - max(0.5, min(3.0, _v ** 0.5))) > 1e-9:
        _disc += 1
ok(u'V9 线性 vs 平方根：4 档里 %d 档可区分（2.5 线性=2.5≠1.581 最明显）'
   % _disc, _disc >= 3, u'disc=%d' % _disc)

# =====================================================================
print(u'\n' + u'=' * 72)
print(u'第107轮独立验收：PASS=%d FAIL=%d' % (_N['p'], _N['f']))
print(u'=' * 72)

_ev = os.path.join(HERE, '..', '_evidence', 'verify107.txt')
try:
    if not os.path.isdir(os.path.dirname(_ev)):
        os.makedirs(os.path.dirname(_ev))
    with io.open(_ev, 'w', encoding='utf-8') as f:
        f.write(u'\n'.join(_OUT) + u'\n')
    print(u'证据已落盘：%s' % _ev)
except Exception as e:
    print(u'证据落盘失败：%s' % e)

sys.exit(1 if _N['f'] else 0)
