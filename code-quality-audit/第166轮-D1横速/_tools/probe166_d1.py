# -*- coding: utf-8 -*-
u"""第166轮 · 探针：D1 横速到底改了些什么（**先量再改**）。

## 为什么要这个

D1 的形态是 `handle_jump` 里这一行：

    vx = delta_x / self.jump_duration      # 目标一定，横向速度就被反推出来了

而 `_jump_reach_ok` 另有一套"他能跑多快才许跳多远"（`_max_run_px_s`）。
两套东西各自算 —— 本探针要回答的是：**把它们并成一套，会改变多少实际能跳的跨度。**

## 为什么用产品函数而不是我自己抄公式

项目纪律：观察量必须由产品代码判。所以这里 `import main`，把
`_max_run_px_s` / `_jump_reach_ok` / `_nominal_move_dt` 用 `types.MethodType`
绑到假 self 上跑 —— 算出来的就是产品算的。

## 三种 `_base` 口径怎么模拟

`_max_run_px_s()` 现在写的是 `_base = max_speed / dt`。方案要把"上限"从
**配置最大值**改成**当前真正能跑到的速度**。因为公式只有一份，模拟方式就是
给假 self 喂不同的 `max_speed`：

| 口径 | 喂进去的 `max_speed` | 含义 |
|---|---|---|
| old | 配置里的 `max_speed`（8.0） | 现状：按配置上限给门票 |
| new | 配置里的 `speed`（5.0） | 改法：按当前速度给门票 |

★ 全部数值从 `config.json` 读，**不硬编码** —— 硬编码过一次就错过一次
（第165轮 `_base` 用代码 fallback 15 当"真实值"，而配置是 8.0）。

⚠️ 本脚本**零网络、零外部盘、不构造 `RalseiPet()`**（31 秒那个），离屏即可。
真实窗口那一段（D）拿不到就**明说拿不到**，不伪造。
"""
import json
import io
import os
import sys
import types

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
CFG = os.path.join(PET, 'config.json')

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
for _p in (PET, os.path.join(PET, 'src'), os.path.join(PET, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from PyQt5.QtCore import QPoint  # noqa: E402

import main as M            # noqa: E402


def _hr(t):
    print('')
    print('=' * 72)
    print(t)
    print('=' * 72)


def _cfg():
    with io.open(CFG, 'r', encoding='utf-8') as fh:
        d = json.load(fh)
    mv = d.get('movement') or {}
    return (float(mv.get('speed', 5.0)),
            float(mv.get('min_speed', 3.0)),
            float(mv.get('max_speed', 8.0)))


class _Pet(object):
    u"""假 self：只放 `_max_run_px_s` / `_jump_reach_ok` 真正读的字段。"""

    def __init__(self, max_speed, speed):
        self.max_speed = float(max_speed)
        self.speed = float(speed)
        self._last_move_dt = 0.0
        self._runup_ready = False
        self._last_move_speed_px_s = 0.0
        self._runup_best_px_s = 0.0
        self.JUMP_SPEED_MAX = float(getattr(M.RalseiPet, 'JUMP_SPEED_MAX', 700.0))
        self.jump_duration = 1.0
        self.gravity = 500.0
        self._jump_reject = None
        self.jump_start_pos = None
        self.jump_target_pos = None
        # 第165轮的运动档案：ralsei 三项 1.0 ⇒ 倍率恒等，不影响本探针
        self._motion_exp = 0.0
        self._motion_eff_cache = None
        self._motion_profile_cache = None
        self._motion_progress_loaded = True
        self._motion_exp_map = {}
        self._motion_progress_path = None


def _bind(p):
    for name in ('_max_run_px_s', '_jump_reach_ok', '_nominal_move_dt',
                 '_motion_eff', '_motion_profile_of', '_motion_profile_table',
                 '_motion_progress_ensure'):
        fn = getattr(M.RalseiPet, name, None)
        if fn is not None:
            setattr(p, name, types.MethodType(fn, p))
    p._motion_progress_ensure = lambda: None      # 不真去读盘
    return p


def _vcap(max_speed, speed, ready=False, best=0.0, meas=0.0):
    p = _bind(_Pet(max_speed, speed))
    p._runup_ready = bool(ready)
    p._runup_best_px_s = float(best)
    p._last_move_speed_px_s = float(meas)
    return p._max_run_px_s()


def _gate(max_speed, speed, dx, ready=False, best=0.0, T=1.0):
    """产品闸门自己说这一跳能不能过。→ (放行?, 拒绝原因)"""
    p = _bind(_Pet(max_speed, speed))
    p._runup_ready = bool(ready)
    p._runup_best_px_s = float(best)
    p.jump_duration = float(T)
    p.jump_start_pos = QPoint(500, 900)
    # ★ 竖直固定 dy = −300（不是 −600）：`vy0 = dy − 0.5·g·T²` 在 T=1/g=500 下
    #   等于 dy−250 ⇒ dy=−600 会算出 vy0=−850，**超过 JUMP_SPEED_MAX(700)**
    #   ⇒ 每一跳都先被 too_high 拒掉，横速那一段根本没机会跑（探针会全表"拒"）。
    p.jump_target_pos = QPoint(int(500 + dx), 900 - 300)
    ok = p._jump_reach_ok()
    rj = p._jump_reject
    return bool(ok), (rj[0] if rj else '')


SPEED, MIN_SPEED, MAX_SPEED = _cfg()

_hr(u'A 配置真值（从 config.json 读，不硬编码）')
_dt = _bind(_Pet(MAX_SPEED, SPEED))._nominal_move_dt()
print(u'  movement: speed=%.1f  min=%.1f  max=%.1f   （px/帧）' % (SPEED, MIN_SPEED, MAX_SPEED))
print(u'  名义帧长 dt = %.4fs  ⇒  走路 %.1f px/s ／ 配置上限 %.1f px/s'
      % (_dt, SPEED / _dt, MAX_SPEED / _dt))
print(u'  RUNUP_SPEED_MAX = %.1f px/s   RUNUP_ACCEL = %.1f px/s²'
      % (float(getattr(M, 'RUNUP_SPEED_MAX', 320.0)),
         float(getattr(M, 'RUNUP_ACCEL', 600.0))))
print(u'  JUMP_SPEED_MAX  = %r' % (getattr(_Pet(MAX_SPEED, SPEED), 'JUMP_SPEED_MAX'),))

_hr(u'B 四种起跳情形下的门票上限（产品 `_max_run_px_s` 真跑）')
_CASES = [
    (u'① 未助跑（原地起跳）', dict(ready=False)),
    (u'② 助跑但只跑到走路速', dict(ready=True, best=SPEED / _dt)),
    (u'③ 助跑实测 250', dict(ready=True, best=250.0)),
    (u'④ 助跑实测 320（满）', dict(ready=True, best=320.0)),
]
_rows = []
for label, kw in _CASES:
    old = _vcap(MAX_SPEED, SPEED, **kw)
    new = _vcap(SPEED, SPEED, **kw)
    _rows.append((label, old, new))
    print(u'  %-22s old(按 max=%.0f)=%7.1f px/s   new(按 speed=%.0f)=%7.1f px/s'
          % (label, MAX_SPEED, old, SPEED, new))

_hr(u'C 同一跳在不同 dx 下的放行/落点（T=1.0s，竖直 dy=-300 固定）')
_DXS = [100, 150, 200, 242, 260, 300, 320, 400, 500, 600]
print(u'  说明：新口径的横向速度取 `sign(dx)×min(v_cap, |dx|/T)`；')
print(u'        落点差 = |dx − vx×T|；≤%d px 视为"吸附"（用户口径）' % 60)
for label, kw in _CASES:
    print('')
    print(u'  — %s —' % label)
    print(u'    %5s | %-22s | %-22s | %s'
          % ('dx', u'old：放行/落点差', u'new：放行/落点差', u'new 的处置'))
    for dx in _DXS:
        _ok_o, _w_o = _gate(MAX_SPEED, SPEED, dx, **kw)
        _ok_n, _w_n = _gate(SPEED, SPEED, dx, **kw)
        _vcap_n = _vcap(SPEED, SPEED, **kw)
        _vx = min(_vcap_n, float(dx))              # T=1.0 ⇒ |dx|/T = dx
        _err = abs(float(dx) - _vx)
        if not _ok_n:
            _disp = u'被拒（%s）' % _w_n
        elif _err <= 60.0:
            _disp = u'吸附（差 %.0fpx）' % _err
        else:
            _disp = u'如实落空（差 %.0fpx）' % _err
        _o = u'%s%s' % (u'放' if _ok_o else u'拒(%s)' % _w_o,
                        u'' if not _ok_o else (u' / 差%.0f' % abs(float(dx) - min(
                            _vcap(MAX_SPEED, SPEED, **kw), float(dx)))))
        _n = u'%s' % (u'放' if _ok_n else u'拒(%s)' % _w_n)
        print(u'    %5d | %-22s | %-22s | %s' % (dx, _o, _n, _disp))

_hr(u'D 真实桌面窗口的跨度（近似；拿不到就明说）')
_dx_real = []
try:
    import win32gui
    import win32api

    _vt = (win32api.GetSystemMetrics(76), win32api.GetSystemMetrics(77),
           win32api.GetSystemMetrics(78), win32api.GetSystemMetrics(79))
    print(u'  虚拟屏 = %s' % (_vt,))
    _vx0, _vy0, _vw, _vh = _vt
    _self_hwnd = set()

    def _cb(hwnd, acc):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return True
        try:
            l, t, r, b = win32gui.GetWindowRect(hwnd)
        except Exception:
            return True
        w, h = r - l, b - t
        if w < 200 or h < 120:
            return True
        if l <= _vx0 and t <= _vy0:            # 桌面/全屏壳
            return True
        acc.append((hwnd, title[:18], (l, t, r, b)))
        return True

    _wins = []
    win32gui.EnumWindows(_cb, _wins)
    print(u'  枚举到可见顶层窗口 %d 个（宽≥200 高≥120、有标题）' % len(_wins))
    if not _wins:
        print(u'  ⚠️ 本环境没有可用窗口 ⇒ D 段**无数据**（不伪造）')
    else:
        _ground_y = _vy0 + _vh - 80                      # 桌面站立点（近似）
        _start_x = _vx0 + _vw // 2
        for hwnd, title, (l, t, r, b) in _wins[:8]:
            _land_x = (l + r) // 2                       # 可见落点近似 = 底边中点
            _dx_real.append(abs(_land_x - _start_x))
            print(u'    %-18s rect=(%d,%d,%d,%d)  →  Δx≈%d px'
                  % (title, l, t, r, b, abs(_land_x - _start_x)))
        print(u'  Δx 最小 %d / 中位 %d / 最大 %d px'
              % (min(_dx_real), sorted(_dx_real)[len(_dx_real) // 2], max(_dx_real)))
except Exception as e:                                   # noqa: BLE001
    print(u'  ⚠️ 拿不到真实窗口（%s: %s）⇒ D 段**无数据**（不伪造）'
          % (type(e).__name__, e))

_hr(u'E 结论（自动算，不手填）')
_v_walk = _vcap(SPEED, SPEED, ready=False)
_v_max_new = _vcap(SPEED, SPEED, ready=True, best=9999.0)
print(u'  改后：未助跑最多跳 %.0f px ／ 助跑满最多跳 %.0f px（= v_cap × T，T=1.0s）'
      % (_v_walk, _v_max_new))
print(u'  改前：未助跑最多跳 %.0f px ／ 助跑满最多跳 %.0f px'
      % (_vcap(MAX_SPEED, SPEED, ready=False),
         _vcap(MAX_SPEED, SPEED, ready=True, best=9999.0)))
_need_runup = []
for dx in range(20, 700, 20):
    _o = _gate(MAX_SPEED, SPEED, dx, ready=False)[0]
    _n = _gate(SPEED, SPEED, dx, ready=False)[0]
    if _o and not _n:
        _need_runup.append(dx)
if _need_runup:
    print(u'  ★ 原本"原地起跳就能过"、改后必须助跑的 dx 区间：%d ~ %d px（共 %d 个取样）'
          % (_need_runup[0], _need_runup[-1], len(_need_runup)))
else:
    print(u'  ★ 没有"原地能过/改后必须助跑"的区间（改法对近距跳零影响）')
print(u'  ★ 改后水平速度上限 %.0f px/s ⇒ 单跳最远 %.0f px；超过这个跨度的窗口'
      u'  **必须靠分段跳到中途落脚板**（第164轮 R1 已落地的机制）' % (_v_max_new, _v_max_new))
print('')
print(u'（本探针只打印数据，不改任何文件、不联网、不构造 RalseiPet）')
