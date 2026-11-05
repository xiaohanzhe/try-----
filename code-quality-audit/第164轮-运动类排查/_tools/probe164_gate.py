# -*- coding: utf-8 -*-
"""第164轮 · 起跳闸门的验证（既测边界，也测"会不会误伤正常跳跃"）。

闸门要回答两件事（用户 2026-11-05 口径）：
  · 「窗口也是有层高的，所以**不可能跳无限高**」 ⇒ 太高必须拒绝
  · 「给他一个**水平初速度**他才能跳远」        ⇒ 太远必须拒绝

但闸门最怕的是**过度拦截**：把本来能跳的也拒了，宠物就"不会跳了"。
所以本探针同时给出：
  A. 边界用例（原地跳 / 正常远跳 / 刚好超限 / 明显超限）
  B. 真实候选（`get_jump_destinations` 给出的目标）逐条过闸门，看拦截率
  C. 关键参数实测值（别拿 15 当 px/s 用）
"""
import math
import os
import sys
import tempfile

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['RALSEI_DATA_DIR'] = os.path.join(tempfile.gettempdir(), 'pet164_gate')
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
    from main import RalseiPet
    from modules import motion2d as m2

    w = RalseiPet()
    w.max_idle_duration = 1e9
    w.is_moving = False
    w.show()
    app.processEvents()

    print('=' * 68)
    print('C 关键参数（单位陷阱：max_speed 是 px/帧，不是 px/s）')
    print('=' * 68)
    v_max = w._max_run_px_s()
    print('   max_speed = %s px/帧' % getattr(w, 'max_speed', None))
    print('   _last_move_dt = %s（兜底 0.033）'
          % getattr(w, '_last_move_dt', None))
    print('   ⇒ 最大水平速度 = %.1f px/s' % v_max)
    print('   gravity=%.1f  jump_duration=%.2f  JUMP_SPEED_MAX=%s'
          % (w.gravity, w.jump_duration,
             getattr(w, 'JUMP_SPEED_MAX', 700.0)))
    # ★ 第一版判据写 `300 < v_max < 900` 报红 —— 那是**我的预期错了**：
    #   本机配置 `movement.max_speed` 是 **8.0**（不是构造默认的 15）⇒ 8/0.033 = 242。
    #   要守的不是"具体多少"，而是"**换算过**"：只要不是把 8 直接当 8 px/s 就行。
    ok(30.0 < v_max < 900.0,
       '换算后的速度在合理量级（%.1f px/s，明显不是裸的 %.1f）'
       % (v_max, float(getattr(w, 'max_speed', 0) or 0)))
    ok(v_max > float(getattr(w, 'max_speed', 0) or 0) * 5.0,
       'A/B：换算值必须显著大于裸的 max_speed（证明乘了 1/dt）')

    print()
    print('=' * 68)
    print('A 边界用例：直接摆 jump_start_pos / jump_target_pos 过闸门')
    print('=' * 68)

    def probe(dx, dy, tag, dur=1.0):
        w.jump_duration = dur
        w.jump_start_pos = QPoint(500, 500)
        w.jump_target_pos = QPoint(500 + dx, 500 + dy)
        r = w._jump_reach_ok()
        rej = w._jump_reject
        print('   %-22s dx=%5d dy=%5d ⇒ %s  %s'
              % (tag, dx, dy, '放行' if r else '拒绝', rej or ''))
        return r, rej

    r0, _ = probe(0, 0, '原地跳（只跳高）')
    ok(r0 is True, '原地跳必须放行（否则连跳高都不行）')

    r1, _ = probe(200, 0, '正常横跳 200px')
    ok(r1 is True, '正常横跳 200px 必须放行')

    r2, rej2 = probe(0, -80, '正常跳高 80px')
    ok(r2 is True, '跳高 80px 必须放行')

    lim_far = v_max * 1.0
    r3, _ = probe(int(lim_far) - 5, 0, '刚好在跳远极限内')
    ok(r3 is True, '极限内 5px 必须放行（闭区间）')

    r4, rej4 = probe(int(lim_far) + 60, 0, '明显超跳远极限')
    ok(r4 is False, '超出跳远极限必须拒绝')
    ok(rej4 and rej4[0] == 'too_far',
       "拒绝原因 = 'too_far'（实得 %r）" % (rej4[0] if rej4 else None))

    # 高度：vy0 = (dy - 0.5*g*T^2)/T，T=1 ⇒ vy0 = dy - 250
    # 要 |vy0| > 700 ⇒ dy < -950 或 dy > 450
    r5, rej5 = probe(0, -1000, '明显超跳高极限')
    ok(r5 is False, '超出跳高极限必须拒绝')
    ok(rej5 and rej5[0] == 'too_high',
       "拒绝原因 = 'too_high'（实得 %r）" % (rej5[0] if rej5 else None))
    ok(rej4 and rej5 and rej4[0] != rej5[0],
       'A/B：两种拒绝原因必须不同（否则分不清该助跑还是该死心）')

    # 高度：T=1 ⇒ vy0 = dy - 0.5*g*T^2 = dy - 250
    # |vy0| <= 700 ⇒ -450 <= dy <= 950（dy 向下为正）
    # ★ 第一版把"刚好在内"写成 dy=-900 报红 —— 又是**我的预期错了**：
    #   -900 时 vy0=-1150，早就超了。真实边界是 **-450**（对应峰值 490px）。
    r6, _ = probe(0, -450, '刚好在跳高极限内（vy0=-700）')
    ok(r6 is True, 'dy=-450 必须放行（|vy0|=700 恰好等于上限）')
    r6b, rej6b = probe(0, -460, '刚超出跳高极限 10px')
    ok(r6b is False, 'dy=-460 必须拒绝（|vy0|=710）')
    ok(rej6b and rej6b[0] == 'too_high',
       "越界原因 = 'too_high'（实得 %r）" % (rej6b[0] if rej6b else None))
    print('   ⇒ 高度上限 ≈ %.0fpx（vy0=%.0f 时峰值 = vy0^2/(2g)）'
          % (700.0 * 700.0 / (2 * 500.0), 700.0))

    print()
    print('=' * 68)
    print('B 真实候选：现有楼层链路给出的目标，逐条过闸门（看会不会误伤）')
    print('=' * 68)
    fm = getattr(w, 'floor_manager', None)
    if fm is None:
        print('   没有 floor_manager，跳过本段')
    else:
        try:
            fm.update_floors()
        except Exception as e:                        # noqa: BLE001
            print('   update_floors 异常: %s' % e)
        cur = getattr(w, 'current_floor', None) or fm.desktop_floor
        w.current_floor = cur
        try:
            cands = fm.get_jump_destinations(cur, w.pos())
        except Exception as e:                        # noqa: BLE001
            cands = []
            print('   get_jump_destinations 异常: %s' % e)
        print('   候选数 = %d' % len(cands))
        allow = reject = 0
        for i, (f, pos) in enumerate(cands[:12]):
            if pos is None:
                continue
            dx = pos.x() - w.pos().x()
            dy = pos.y() - w.pos().y()
            w.jump_duration = 1.0
            w.jump_start_pos = w.pos()
            w.jump_target_pos = QPoint(pos.x(), pos.y())
            r = w._jump_reach_ok()
            if r:
                allow += 1
            else:
                reject += 1
            print('   [%d] 目标(%5d,%5d) dx=%5d dy=%5d ⇒ %s %s'
                  % (i, pos.x(), pos.y(), dx, dy,
                     '放行' if r else '拒绝', w._jump_reject or ''))
        if allow + reject:
            print('   放行 %d / 拒绝 %d' % (allow, reject))
            ok(allow > 0,
               '真实候选里至少有一条能跳（否则等于把跳跃功能关掉了）')

    print()
    print('=' * 68)
    print('通过 %d 项，失败 %d 项' % (_passes[0], len(_fails)))
    if _fails:
        for f in _fails:
            print('  ✗ %s' % f)
        return 1
    print('[PASS] 起跳闸门验证全部通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
