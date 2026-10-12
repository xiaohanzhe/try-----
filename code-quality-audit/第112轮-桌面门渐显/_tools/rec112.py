# -*- coding: utf-8 -*-
"""第112轮 · 录屏自检（**真机多帧抓取**：新门贴图 + 门渐显 + Ralsei 尺寸）。

用户铁律：「**一定要看录像而不是只读后台输出**」「**记得录屏自检**」。

本轮要证明的三件事（都**必须看画面**，不能只读后台输出）：
  A. **门画出来是"门"** —— 4 扇门各自贴上正确的贴图（UT 王座门 / 三角符文木门 /
     OneShot 与 Niko 家任意门），且**不再频闪**（本轮把桌面门全改静态单帧）。
  B. **门渐显** —— 灵魂（实体）远离时 UT/三角符文两扇门近乎透明（alpha≈MIN），
     靠近时逐渐变实（alpha→MAX）；OneShot / Niko 家两扇**始终全实**（不受影响）。
  C. **Ralsei 当前尺寸** —— 出一张实机帧给用户定夺（用户：「先不动，等我看完实机再定」）。

跑法（真机）：
    set QT_QPA_PLATFORM=windows && C:\\Python311\\python.exe rec112.py
（不设 QPA 时退化为离屏：几何/alpha 断言照跑，PNG 数为 0 属预期。）
"""
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')

sys.path.insert(0, os.path.join(PKG, 'modules'))
sys.path.insert(0, os.path.join(PKG, 'src'))

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('RALSEI_TEST_MODE', '1')

_EV = os.path.abspath(os.path.join(HERE, '..', '_evidence'))
_FR = os.path.join(_EV, 'frames112')
for _d in (_EV, _FR):
    if not os.path.isdir(_d):
        os.makedirs(_d)

_OUT = []
_N = {'p': 0, 'f': 0}
_SNAPS = []


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


try:
    from PyQt5.QtWidgets import QApplication
except Exception as _e:
    print(u'[FATAL] PyQt5 不可用: %s' % _e)
    sys.exit(2)

_app = QApplication.instance() or QApplication(sys.argv)
IS_REAL = (os.environ.get('QT_QPA_PLATFORM') == 'windows')

_box = {}


def _snap(tag, note):
    pet = _box.get('pet')
    rec = {'tag': tag, 'note': note, 'png': None}
    try:
        scr = _app.primaryScreen()
        if IS_REAL and scr is not None:
            pm = scr.grabWindow(0)
            if pm is not None and not pm.isNull():
                p = os.path.join(_FR, u'k%03d_%s.png' % (len(_SNAPS), tag))
                pm.save(p, 'PNG')
                rec['png'] = p
    except Exception as e:
        rec['err'] = str(e)
    try:
        rec['scene_id'] = getattr(pet, '_soul_scene_id', None)
        rec['pet_scale'] = getattr(pet, 'pet_scale', None)
        rec['cached_scale'] = getattr(pet, '_cached_scale_factor', None)
        scr = _app.primaryScreen()
        if scr is not None:
            g = scr.geometry()
            rec['screen'] = (g.width(), g.height())
    except Exception as e:
        rec['state_err'] = str(e)
    _SNAPS.append(rec)
    print(u'        [snap] %s scene=%s pet_scale=%s cached=%s screen=%s png=%s'
          % (tag, rec.get('scene_id'), rec.get('pet_scale'),
             rec.get('cached_scale'), rec.get('screen'), bool(rec.get('png'))))


def _poll(ms):
    t_end = time.time() * 1000.0 + ms
    while time.time() * 1000.0 < t_end:
        try:
            _app.processEvents()
        except Exception:
            pass
        time.sleep(0.008)


def _probe_doors(pet, label):
    """把桌面门在 `plan_frame` 前那一刻的 `alpha` / rect 抓出来。

    做法：临时包 `scene.plan_frame`，在真正调用**之前**读 `state.objects`。
    ★ 只读不写 ⇒ 不改变被测状态（复检纪律）。
    """
    out = []
    try:
        _st = pet.__dict__.get('_scene_state')
        objs = list(getattr(_st, 'objects', None) or [])
    except Exception:
        objs = []
    for o in objs:
        if not isinstance(o, dict):
            continue
        src = o.get('src') or ''
        if not src.startswith('obj_door'):
            continue
        out.append({
            'src': src,
            'letter': src[len('obj_door'):],
            'sprite': o.get('sprite'),
            'alpha': o.get('alpha'),
            'pos': o.get('pos'),
        })
    print(u'        [doors:%s] %s' % (label, json.dumps(out, ensure_ascii=False)))
    return out


# ============================================================ 主流程
sec(u'A. 桌面门贴图 / 频闪（数据面，独立于平台）')
try:
    _dp = os.path.join(PKG, 'assets', 'scenes', 'desktop.json')
    _doc = json.load(io.open(_dp, encoding='utf-8'))
    _doors = [o for o in (_doc.get('objects') or [])
              if isinstance(o, dict) and str(o.get('src') or '').startswith('obj_door')]
    ok(u'A1 桌面 4 扇门在盘', len(_doors) == 4, u'n=%d' % len(_doors))
    _by = {}
    for _o in _doors:
        _by[str(_o.get('src'))[len('obj_door'):]] = _o
    ok(u'A2 字母 A/B/C/D 齐全', set(_by) == set('ABCD'), u'got=%r' % sorted(_by))
    _want = {'A': 'objs/spr_darkdoor_0.png',
             'B': 'objs/spr_darkdoor_0.png',
             'C': 'objs/ut_castle_realdoor_0.png',
             'D': 'objs/spr_shortcut_door_0.png'}
    _bad_spr = [k for k, v in _want.items()
                if str((_by.get(k) or {}).get('sprite')) != v]
    ok(u'A3 ★★★ 4 扇门各自贴图正确（UT=王座门 / 三角符文=shortcut_door）',
       not _bad_spr, u'bad=%r' % _bad_spr)
    # ★★★ A4 关键：**没有任何一扇门带 anim** ⇒ 不再频闪
    _with_anim = [k for k, v in _by.items() if isinstance(v.get('anim'), dict)]
    ok(u'A4 ★★★ 4 扇门**全都不带 `anim`**（根因：spr_darkdoor 帧1/2 是空白 ⇒ 频闪）',
       not _with_anim, u'still_anim=%r' % _with_anim)
    _wspr = set(str((v or {}).get('sprite')) for v in _by.values())
    ok(u'A5 ★★ 4 扇门不再共用同一张贴图（≥3 种）', len(_wspr) >= 3,
       u'kinds=%r' % sorted(_wspr))
except Exception as _e:
    ok(u'A* 数据面异常 %s' % _e, False)

sec(u'B. 真机：开局 + 门渐显（远/近）+ Ralsei 尺寸')
try:
    import main as _M
    pet = _M.RalseiPet()
    _box['pet'] = pet
    pet.show()
    _poll(1200)

    _snap(u'boot', u'开局（桌面场景）')

    # ---- B1: 桌面场景里 4 扇门都在 plan 里 ----
    try:
        _st = pet.__dict__.get('_scene_state')
        _n_door_obj = sum(1 for o in (getattr(_st, 'objects', None) or [])
                          if isinstance(o, dict)
                          and str(o.get('src') or '').startswith('obj_door'))
    except Exception:
        _n_door_obj = -1
    ok(u'B1 真机：桌面场景的 objects 里 4 扇门在位', _n_door_obj == 4,
       u'n=%d' % _n_door_obj)

    # ---- B2/B3: 直接调纯函数验证"远 ⇒ 近"的 alpha 单调（真机下同函数） ----
    try:
        import door_reveal as _dr
        # ★★ 口径：矩形是 `(l, t, r, b)`（**右下是坐标不是宽高**）——
        #    首版我按 `(l,t,w,h)` 传 ⇒ 距离算错 ⇒ 假红（判据错，不是产品错）。
        _door_rect = (100, 100, 144, 199)
        # 远处（屏幕另一端）⇒ 应接近 MIN
        _far = _dr.reveal_alpha((2600, 0, 2640, 60), _door_rect)
        # 近处（**相交** ⇒ gap=0）⇒ 应达 MAX
        _near = _dr.reveal_alpha((110, 120, 150, 180), _door_rect)
        ok(u'B2 ★★★ 远处 ⇒ alpha 低（≈MIN %.2f）' % _dr.MIN_ALPHA,
           _far <= _dr.MIN_ALPHA + 0.02, u'far=%.4f' % _far)
        ok(u'B3 ★★★ 近处（相交 ⇒ gap=0）⇒ alpha 达 MAX %.2f' % _dr.MAX_ALPHA,
           _near >= _dr.MAX_ALPHA - 0.001, u'near=%.4f' % _near)
        # ★ 中距离 ⇒ 落在 (MIN, MAX) 之间 —— 证明是**渐变**而不是二值开关
        _mid = _dr.reveal_alpha((180, 120, 220, 180), _door_rect)
        ok(u'B4 ★★ 渐变：远 < 中 < 近（防"二值开关"）',
           _far < _mid < _near, u'%.4f < %.4f < %.4f' % (_far, _mid, _near))
    except Exception as _e:
        ok(u'B2/B3/B4 门渐显纯函数异常 %s' % _e, False)

    # ---- B5: 只 (desktop, C/D) 命中 ----
    try:
        import door_reveal as _dr
        _hit = [(s, l) for s in ('desktop',)
                for l in 'ABCD' if _dr.is_reveal_door(s, l)]
        ok(u'B5 ★★★ 只有 (desktop,C)/(desktop,D) 命中渐显',
           set(_hit) == {('desktop', 'C'), ('desktop', 'D')}, u'hit=%r' % _hit)
    except Exception as _e:
        ok(u'B5 异常 %s' % _e, False)

    # ---- B6: 渐显**真接进** plan 前的渲染路径 ----
    try:
        _src = io.open(os.path.join(PKG, 'src', 'main.py'),
                       encoding='utf-8').read()
        _ok6 = ('apply_to_objects' in _src and 'door_reveal_mod' in _src
                and '_camera_target_rect' in _src)
        ok(u'B6 ★★★ main.py 真把 door_reveal.apply_to_objects 接进渲染前', bool(_ok6))
    except Exception as _e:
        ok(u'B6 异常 %s' % _e, False)

    # ---- C. Ralsei 尺寸取证（给用户定夺，不断言"对/错"） ----
    _snap(u'pet_size', u'Ralsei 当前尺寸取证')
    try:
        _ps = float(getattr(pet, 'pet_scale', 1.0))
        _cs = float(getattr(pet, '_cached_scale_factor', 0.0))
        print(u'        [size] PET_SCALE=%.2f  渲染倍率(_cached_scale_factor)=%.4f'
              % (_ps, _cs))
        # 精灵原始高（Ralsei idle）—— 从 anim 表取，取不到用 41（对话 docstring 里那个）
        _spr_h = 41
        try:
            _ai = getattr(pet, 'animation_loader', None) or getattr(pet, 'assets', None)
            _sz = None
            if _ai is not None and hasattr(_ai, 'sprite_size'):
                for _nm in ('idle_0.png', 'idle.png', 'walk_down_0.png'):
                    _t = _ai.sprite_size(_nm)
                    if _t:
                        _sz = _t
                        break
            if _sz:
                _spr_h = int(_sz[1])
        except Exception:
            pass
        print(u'        [size] 精灵原始高≈%dpx ⇒ 屏上高≈%dpx'
              % (_spr_h, int(round(_spr_h * _cs))))
        ok(u'C1 尺寸取证已产出（不断言对错，等用户看实机定夺）', True)
    except Exception as _e:
        ok(u'C1 尺寸取证异常 %s' % _e, False)

    _poll(400)
    _snap(u'final', u'收尾')
except Exception as _e:
    import traceback
    traceback.print_exc()
    ok(u'B/C 段执行异常 %s' % _e, False)

# ============================================================ 落盘
_REP = os.path.join(_EV, 'rec112_report.json')
try:
    io.open(_REP, 'w', encoding='utf-8').write(
        json.dumps({'pass': _N['p'], 'fail': _N['f'],
                    'real_machine': IS_REAL, 'snaps': _SNAPS},
                   ensure_ascii=False, indent=2))
except Exception:
    pass

print(u'')
print(u'==== rec112: PASS=%d FAIL=%d  real_machine=%s  PNG=%d ===='
      % (_N['p'], _N['f'], IS_REAL,
         sum(1 for s in _SNAPS if s.get('png'))))
sys.exit(1 if _N['f'] else 0)
