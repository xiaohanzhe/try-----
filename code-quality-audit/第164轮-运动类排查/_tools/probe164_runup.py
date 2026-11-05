# -*- coding: utf-8 -*-
"""第164轮 · 助跑验证（"要有助跑距离哦" —— 用户 2026-11-05）。

要守的四件事，缺一件这功能就等于没做：

  A. **闸门分层**：不助跑只到走路速度；助跑才到冲刺速度；
     而且冲刺速度必须是**实测**的 —— 标了旗但没跑起来，不许放行（假放行比拒绝更糟）。
  B. **两个量不许混**（用户原话：「这个预留点可别和助跑距离搞混了哦」）：
     起跳点 = 现在站的地方（预留空间是另一套，本函数不动）；
     起跑点 = 起跳点沿"远离落点"方向退 `v²/(2a)`。
  C. **冲刺必须压过距离减速**（头号陷阱）：`distance < 50` 那档会把目标速度压到
     `speed*(distance/50)`，而到达阈值 30px ⇒ 起跳前最后几步正好落进这一档
     ⇒ 实测速度掉到 1px/帧 ⇒ 闸门必拒 ⇒ "助跑永远不成功"，且**不报错**。
  D. **不许死锁**：助跑只试 `RUNUP_MAX_TRIES` 次；超时/被拖拽/跳起来都要清状态。

判据口径（见记忆：判据过窄=误报 / 恒真判据比不写还危险）：
  · 每条都带**正负控制**或 A/B 对照，不许只判"提到了某个名字"；
  · 观察量由**产品代码**产生（调真方法、读真字段），不自己算一个漂亮数字。
"""
import math
import os
import sys
import tempfile
import time

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['RALSEI_DATA_DIR'] = os.path.join(tempfile.gettempdir(), 'pet164_runup')
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

_fails = []
_passes = [0]


def ok(cond, msg):
    if cond:
        _passes[0] += 1
        print('  [PASS] %s' % msg)
    else:
        _fails.append(msg)
        print('  [FAIL] %s' % msg)


def main():
    import main as M
    w = M.RalseiPet()
    w.max_idle_duration = 1e9
    w.is_moving = False
    w.show()
    app.processEvents()

    V_WALK = w._max_run_px_s()
    print('=' * 68)
    print('0 环境量')
    print('=' * 68)
    print('   self.speed = %s px/帧   max_speed = %s px/帧'
          % (getattr(w, 'speed', None), getattr(w, 'max_speed', None)))
    print('   走路速度上限 = %.1f px/s；冲刺上限常量 = %.1f px/s'
          % (V_WALK, M.RUNUP_SPEED_MAX))
    ok(getattr(w, '_runup', 'missing') is None,
       '初始 `_runup` 为 None（不是没这个属性）')
    ok(w._runup_ready is False and w._runup_dashing is False,
       '初始 `_runup_ready` / `_runup_dashing` 都是 False')
    ok(M.RUNUP_MAX_TRIES >= 1, 'RUNUP_MAX_TRIES = %d（>=1，否则永不允许助跑）'
       % M.RUNUP_MAX_TRIES)

    # ------------------------------------------------------------------
    print()
    print('=' * 68)
    print('A 闸门分层：助跑才解锁冲刺速度；没真跑起来不许放行')
    print('=' * 68)

    def maxrun(ready, meas):
        w._runup_ready = ready
        w._last_move_speed_px_s = meas
        w._runup_best_px_s = 0.0
        v = w._max_run_px_s()
        w._runup_ready = False
        return v

    v_off = maxrun(False, 900.0)
    v_on_hi = maxrun(True, 320.0)
    v_on_lo = maxrun(True, 60.0)
    print('   不助跑(实测900) ⇒ %.1f | 助跑+实测320 ⇒ %.1f | 助跑+实测60 ⇒ %.1f'
          % (v_off, v_on_hi, v_on_lo))
    ok(abs(v_off - V_WALK) < 1e-6,
       '不助跑时上限 = 走路速度（实测值被**忽略**：900 进来也不许抬）')
    ok(v_on_hi > v_off * 1.15,
       'A/B：助跑+实测 320 ⇒ 上限显著抬高（%.1f > %.1f）' % (v_on_hi, v_off))
    ok(abs(v_on_hi - M.RUNUP_SPEED_MAX) < 1e-6,
       '助跑上限正好夹在 RUNUP_SPEED_MAX = %.0f' % M.RUNUP_SPEED_MAX)
    ok(abs(v_on_lo - v_off) < 1e-6,
       '★ 假放行防护：标了助跑但实测只有 60 ⇒ 退回走路速度（%.1f）' % v_on_lo)

    # 端到端：同一跳，助跑前被拒、助跑后放行
    def gate(dx, ready, meas):
        w.jump_duration = 1.0
        w.jump_start_pos = QPoint(500, 500)
        w.jump_target_pos = QPoint(500 + dx, 500)
        w._runup_ready = ready
        w._last_move_speed_px_s = meas
        r = w._jump_reach_ok()
        rej = w._jump_reject
        w._runup_ready = False
        w._last_move_speed_px_s = 0.0
        return r, rej

    dx_between = int(V_WALK + 30)          # 走路够不着、冲刺够得着
    r_no, rej_no = gate(dx_between, False, 0.0)
    r_yes, _ = gate(dx_between, True, M.RUNUP_SPEED_MAX)
    print('   同一跳 dx=%d：不助跑 ⇒ %s %s ；助跑 ⇒ %s'
          % (dx_between, '放行' if r_no else '拒绝', rej_no or '',
             '放行' if r_yes else '拒绝'))
    ok(r_no is False and rej_no and rej_no[0] == 'too_far',
       '不助跑时这一跳必须被拒且原因 = too_far')
    ok(r_yes is True, '助跑（真冲到冲刺速度）后同一跳必须放行')
    ok(dx_between < M.RUNUP_SPEED_MAX * 1.0,
       'A/B 前提成立：这个距离确实在"冲刺够得着"的区间里')

    # ------------------------------------------------------------------
    print()
    print('=' * 68)
    print('B 规划：起跳点 vs 起跑点（两个量不许混）')
    print('=' * 68)

    fm = getattr(w, 'floor_manager', None)
    ok(fm is not None, '有 floor_manager（否则起跑点没法校验同层）')
    if fm is not None:
        # ⚠️ 必须先刷一次：`desktop_floor['rect']` 在 `update_floors()` 之前是
        #    **空 QRect()** ⇒ `floor_visible_contains` 恒 False ⇒ `_try_runup`
        #    会一律判"起跑点站不住"而放弃助跑。第一版探针踩的就是这个
        #    （失败现象是"助跑永远不排"，与"产品没接线"长得一模一样）。
        try:
            fm.update_floors()
        except Exception as _e:                        # noqa: BLE001
            print('   update_floors 异常: %r' % (_e,))
        w.current_floor = getattr(w, 'current_floor', None) or fm.desktop_floor

    def reset_runup():
        w._runup = None
        w._runup_dashing = False
        w._runup_ready = False
        w._runup_tried = 0
        w.is_moving = False
        w._last_move_speed_px_s = 0.0

    # 让 pet 站到 (500,500)，落点在 +300（右）
    w.move(500, 500)
    app.processEvents()
    takeoff = w.pos()
    land = QPoint(takeoff.x() + 300, takeoff.y())

    reset_runup()
    print('   [diag] pos=%s  current_floor.type=%r  _runup_tried=%s'
          % ((w.pos().x(), w.pos().y()),
             ((getattr(w, 'current_floor', None) or {}).get('type')
              if getattr(w, 'current_floor', None) else None),
             getattr(w, '_runup_tried', None)))
    print('   [diag] desktop_rect=%r'
          % (fm.desktop_floor.get('rect') if getattr(fm, 'desktop_floor', None)
             else None,))
    _p0 = QPoint(w.pos().x() - 62, w.pos().y())
    try:
        _cf = getattr(w, 'current_floor', None) or fm.desktop_floor
        print('   [diag] floor_visible_contains((%d,%d)) = %r'
              % (_p0.x(), _p0.y(), fm.floor_visible_contains(_cf, _p0)))
    except Exception as _e:                            # noqa: BLE001
        print('   [diag] floor_visible_contains 异常: %r' % (_e,))
    ok(w._try_runup({'type': 'window', 'window': {}}, land, 'bottom',
                    V_WALK + 30) is True,
       '_try_runup 接下了这个请求（返回 True）')
    ru = w._runup or {}
    frm, to = ru.get('from'), ru.get('to')
    ok(ru.get('leg') == 'back', "第一腿 = 'back'（先退后，不是直接跳）")
    ok(to is not None and to.x() == takeoff.x() and to.y() == takeoff.y(),
       '★ 起跳点 = 宠物**现在站的位置** (%d,%d) —— 预留空间由落点选择负责，'
       '本函数不动它' % (takeoff.x(), takeoff.y()))
    ok(frm is not None and frm.x() < to.x(),
       '★ 起跑点在起跳点的**反方向**（远离落点）：from.x=%s < to.x=%s'
       % (frm.x() if frm else None, to.x() if to else None))

    L_got = math.hypot(frm.x() - to.x(), frm.y() - to.y()) if frm else -1
    L_want = M.motion2d.runup_distance(V_WALK + 30, 0.0, M.RUNUP_ACCEL)
    L_want = max(float(M.RUNUP_MIN_PX), min(float(M.RUNUP_MAX_PX), L_want))
    print('   助跑距离：实得 %.1fpx，解析 v²/(2a) = %.1fpx（夹在 [%d,%d]）'
          % (L_got, L_want, M.RUNUP_MIN_PX, M.RUNUP_MAX_PX))
    ok(abs(L_got - L_want) <= 1.5,
       '★ 起跑点距离 = v²/(2a)（%.1f ≈ %.1f）—— 助跑距离由**速度差**决定'
       % (L_got, L_want))
    ok(w.is_moving is True and w.target_pos.x() == frm.x(),
       '已经排上队：is_moving=True 且 target_pos 指向起跑点')
    ok(w._runup_tried == 1, '计数 +1（实得 %d）' % w._runup_tried)

    # 助跑只试一次
    reset_runup()
    w._runup_tried = M.RUNUP_MAX_TRIES
    ok(w._try_runup({'type': 'window'}, land, 'bottom', V_WALK + 30) is False,
       '★ 试满 RUNUP_MAX_TRIES 次后不再排助跑（防死循环）')

    # 垂直跳不助跑
    reset_runup()
    w.move(500, 500)
    app.processEvents()
    land_up = QPoint(w.pos().x(), w.pos().y() - 60)
    ok(w._try_runup({'type': 'window'}, land_up, 'top', V_WALK + 30) is False,
       '★ 近乎垂直的跳不排助跑（助跑买不到横向速度，纯浪费）')

    # 冲刺也够不着 ⇒ 不排助跑
    reset_runup()
    w.move(500, 500)
    app.processEvents()
    ok(w._try_runup({'type': 'window'}, QPoint(1400, 500), 'bottom',
                    M.RUNUP_SPEED_MAX + 200) is False,
       '需要速度超过 RUNUP_SPEED_MAX ⇒ 不排助跑（物理上做不到，交求助）')

    # ------------------------------------------------------------------
    print()
    print('=' * 68)
    print('C 冲刺压过距离减速（头号陷阱：到跟前就没速度了）')
    print('=' * 68)
    reset_runup()
    w.move(500, 500)
    app.processEvents()

    def run_a_bit(n=12, dashing=False, dist=140):
        """从 (500,500) 朝 +x 跑 n 帧；最后几帧会落进 <50px 的减速档。"""
        w._runup = {'from': QPoint(500, 500), 'to': QPoint(500 + dist, 500),
                    'args': (), 'leg': 'dash', 't0': time.time()}
        w._runup_dashing = dashing
        w.is_moving = True
        w.target_pos = QPoint(500 + dist, 500)
        w._last_move_speed_px_s = 0.0
        for _ in range(n):
            time.sleep(0.032)
            w.update_movement()
            app.processEvents()
        v = w._last_move_speed_px_s
        d = abs(w.pos().x() - (500 + dist))
        w._runup = None
        w._runup_dashing = False
        w.is_moving = False
        return v, d

    w.move(500, 500)
    app.processEvents()
    v_dash, d_dash = run_a_bit(14, dashing=True, dist=140)
    w.move(500, 500)
    app.processEvents()
    v_walk, d_walk = run_a_bit(14, dashing=False, dist=140)
    print('   冲刺腿：实测 %.0f px/s，离目标 %.0fpx' % (v_dash, d_dash))
    print('   负控制：不开冲刺：实测 %.0f px/s，离目标 %.0fpx' % (v_walk, d_walk))
    ok(v_dash > v_walk * 1.15,
       '★ 冲刺腿明显快于走路腿（%.0f > %.0f）—— 冲刺真的接上了'
       % (v_dash, v_walk))
    ok(v_dash >= M.RUNUP_SPEED_MAX * 0.8,
       '★ 逼近目标（<50px 减速档）时仍有冲刺速度（%.0f >= %.0f）—— '
       '这正是"助跑永远不成功"的那个陷阱'
       % (v_dash, M.RUNUP_SPEED_MAX * 0.8))
    # ★ 这条是**为我自己踩过的坑**加的回归闸：第一版用"当帧 dt"换算，
    #   某一帧 dt≈2ms 时实测值飙到 **2777 px/s**，闸门当场按 2777 放行 = 假放行。
    #   判据取 1.35 倍留余量（平滑上冲允许略微越过目标值，但不许出现数量级失真）。
    ok(v_dash <= M.RUNUP_SPEED_MAX * 1.35,
       '★ 实测值不许出现"帧率放大"的离谱数字（%.0f <= %.0f）—— '
       '这条守着 speed 是"像素/帧"那个单位陷阱'
       % (v_dash, M.RUNUP_SPEED_MAX * 1.35))
    ok(v_walk > 30.0,
       '负控制的走路速度本身是合理的（%.0f px/s，不是 0 也不是天文数字）' % v_walk)

    # ------------------------------------------------------------------
    print()
    print('=' * 68)
    print('D 状态机：不许提前起跳 / 不许死锁')
    print('=' * 68)
    reset_runup()
    w.move(500, 500)
    app.processEvents()

    fired = [0]
    _orig_sfj = w._start_floor_jump
    w._start_floor_jump = lambda *a, **k: (fired.__setitem__(0, fired[0] + 1) or True)

    # D1 dash 腿但还差 29px ⇒ 不许起跳
    w._runup = {'from': QPoint(500, 500), 'to': QPoint(529, 500),
                'args': ({}, 'bottom', QPoint(800, 500)), 'leg': 'dash',
                't0': time.time()}
    r = w._runup_on_arrive()
    ok(r is True, 'dash 腿没到 ⇒ 仍然接手（返回 True，不按"到达"收尾）')
    ok(fired[0] == 0,
       '★ 差 29px（> RUNUP_FIRE_PX=%d）**不许**起跳（否则 dx 凭空变大 29px，'
       '把助跑的速度吃光）' % M.RUNUP_FIRE_PX)
    ok(w._runup is not None and w.is_moving is True, '仍在冲刺中，没被中止')

    # D2 真到跟前 ⇒ 起跳一次
    w._runup = {'from': QPoint(500, 500), 'to': QPoint(504, 500),
                'args': ({}, 'bottom', QPoint(800, 500)), 'leg': 'dash',
                't0': time.time()}
    r = w._runup_on_arrive()
    ok(r is True and fired[0] == 1,
       '进了 RUNUP_FIRE_PX 才起跳，且只起跳一次（实得 %d 次）' % fired[0])
    ok(w._runup is None, '起跳后 `_runup` 已清（不留残状态）')

    # D3 'back' 腿到达 ⇒ 换 dash
    w._runup = {'from': QPoint(500, 500), 'to': QPoint(600, 500),
                'args': ({}, 'bottom', QPoint(900, 500)), 'leg': 'back',
                't0': time.time()}
    w._runup_on_arrive()
    ok(w._runup.get('leg') == 'dash' and w._runup_dashing is True,
       "'back' 腿走完 ⇒ 自动切 'dash' 并开冲刺")
    ok(fired[0] == 1, '这一拍**没有**起跳（还差得远）')

    # D4 超时清理
    w._runup = {'from': QPoint(500, 500), 'to': QPoint(600, 500),
                'args': (), 'leg': 'back',
                't0': time.time() - M.RUNUP_TIMEOUT_S - 1.0}
    w._runup_dashing = True
    w._runup_tick()
    ok(w._runup is None and w._runup_dashing is False,
       '超时（> %.0fs）⇒ 状态被清干净（否则这一层永远上不去）'
       % M.RUNUP_TIMEOUT_S)

    # D5 已经跳起来 ⇒ 清理
    w._runup = {'from': QPoint(500, 500), 'to': QPoint(600, 500),
                'args': (), 'leg': 'back', 't0': time.time()}
    w.is_jumping = True
    w._runup_tick()
    ok(w._runup is None, '已经跳起来了 ⇒ 助跑状态作废（别两套位移打架）')
    w.is_jumping = False

    w._start_floor_jump = _orig_sfj

    # ------------------------------------------------------------------
    print()
    print('=' * 68)
    print('E 拒绝分派：太远先助跑，太高直接求助，助跑过还不行才求助')
    print('=' * 68)
    spoken = [0]
    _orig_speech = w.start_autonomous_speech
    w.start_autonomous_speech = lambda *a, **k: spoken.__setitem__(0, spoken[0] + 1)

    def reject(reason, v_req, tried=0):
        spoken[0] = 0
        reset_runup()
        w._runup_tried = tried
        w.move(500, 500)
        app.processEvents()
        w._jump_reject = (reason, v_req, V_WALK)
        w._on_jump_rejected({'type': 'window'}, QPoint(w.pos().x() + 300,
                                                      w.pos().y()),
                            'bottom')
        return (w._runup is not None), spoken[0]

    scheduled, sp = reject('too_far', V_WALK + 40)
    ok(scheduled is True and sp == 0,
       'too_far ⇒ 排上助跑，且**不**先喊求助（实得 spawn=%s, 求助=%d）'
       % (scheduled, sp))

    scheduled, sp = reject('too_high', 0.0)
    ok(scheduled is False and sp == 1,
       'too_high ⇒ **不**排助跑（跑得再快也跳不高），直接求助一次')

    scheduled, sp = reject('too_far', V_WALK + 40, tried=M.RUNUP_MAX_TRIES)
    ok(scheduled is False and sp == 1,
       '★ 助跑已经试过还是 too_far ⇒ 不再排，转为求助（否则死循环）')

    w.start_autonomous_speech = _orig_speech

    # ------------------------------------------------------------------
    print()
    print('=' * 68)
    print('通过 %d 项，失败 %d 项' % (_passes[0], len(_fails)))
    if _fails:
        for f in _fails:
            print('  ✗ %s' % f)
        return 1
    print('[PASS] 助跑验证全部通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
