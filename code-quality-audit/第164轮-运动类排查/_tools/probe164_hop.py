# -*- coding: utf-8 -*-
"""第164轮 · 惊讶小跳的**行为级**验证（它到底有没有真的跳起来）。

背景
----
旧实现只写 `jump_height=20` / `jump_start_*`，**从不置 `is_jumping`**
⇒ `handle_jump` 一次都没跑过，`jump_count += 1` 是唯一"证据"（记账不等于跳）。
所以本探针不看记账，只看**坐标轨迹**：

  1. 站着（`is_moving=False`）被吓到 ⇒ 必须真的跳（旧实现走不到那段）
  2. 水平位移 **恒为 0**（目标点 = 当前位置 ⇒ 初速 0 ⇒ 只跳高）
  3. 竖直**先上后下**（真抛物线，不是单调上浮）
  4. 峰值 ≈ `vz0^2/(2g)`，其中 `vz0 = 0.5*g*T`、`T = 0.5s`
  5. 落地后 `is_jumping` / `_hop_mode` 都归位（不残留，否则下一次跨层跳跃
     会继承"跳过穿透判定"的标记）
"""
import os
import sys
import tempfile
import time

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['RALSEI_DATA_DIR'] = os.path.join(tempfile.gettempdir(), 'pet164_hop')
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
    w = RalseiPet()
    w.max_idle_duration = 1e9
    w.is_moving = False            # ★ 关键：站着（旧实现在这个状态下永远跳不了）
    w.show()
    app.processEvents()

    print('=' * 66)
    print('1 站着被吓到 ⇒ 必须真的起跳')
    print('=' * 66)
    jc0 = w.jump_count
    print('   触发前 is_moving=%s is_jumping=%s jump_count=%d'
          % (w.is_moving, w.is_jumping, jc0))
    w.trigger_surprise()
    ok(w.is_jumping is True,
       'trigger_surprise() 之后 is_jumping=True（旧实现恒 False）')
    ok(getattr(w, '_hop_mode', False) is True,
       '_hop_mode=True（让 handle_jump 跳过楼层穿透判定）')
    ok(w.jump_count == jc0 + 1, 'jump_count %d -> %d' % (jc0, w.jump_count))
    ok(w.jump_target_pos == w.pos(),
       '目标点 == 当前位置 (%d,%d) ⇒ 水平位移必须为 0'
       % (w.jump_target_pos.x(), w.jump_target_pos.y()))

    print()
    print('=' * 66)
    print('2 逐帧轨迹（真跑 handle_jump）')
    print('=' * 66)
    x0, y0 = w.pos().x(), w.pos().y()
    xs, ys = [], []
    t0 = time.time()
    for i in range(1, 21):                       # 20 帧 × 0.05s = 1.0s > T=0.5s
        now = t0 + i * 0.05
        try:
            w.handle_jump(0.05, now)
        except Exception as e:                   # noqa: BLE001
            print('   handle_jump 抛异常: %s: %s' % (type(e).__name__, e))
            break
        xs.append(w.pos().x() - x0)
        ys.append(w.pos().y() - y0)
        if not w.is_jumping:
            break
    print('   x 轨迹: %s' % xs)
    print('   y 轨迹: %s' % ys)

    ok(all(v == 0 for v in xs), '水平位移**恒为 0**（实得范围 [%d,%d]）'
       % (min(xs or [0]), max(xs or [0])))
    peak = min(ys) if ys else 0
    ok(peak < -8, '确实往上跳了（y 峰值 %d，向上为负）' % peak)
    if ys:
        _ip = ys.index(min(ys))
        ok(_ip > 0 and any(v > ys[_ip] for v in ys[_ip + 1:]),
           '先上后下（峰值在第 %d 帧，之后有回落）' % _ip)
    # 解析解：T=0.5 ⇒ vz0 = 0.5*g*T = 125 ⇒ h_max = 125^2/(2*500) = 15.6
    ok(abs(peak + 15.6) <= 4.0,
       '峰值与解析解 h_max=15.6 相符（实得 %d，容差 4px）' % peak)

    print()
    print('=' * 66)
    print('3 落地收尾（标记必须清干净，否则污染下一次跨层跳跃）')
    print('=' * 66)
    ok(w.is_jumping is False, 'is_jumping 已复位')
    ok(getattr(w, '_hop_mode', False) is False, '_hop_mode 已复位')
    ok(abs(w.pos().y() - y0) <= 1, '落回原高度（y 偏差 %d）' % (w.pos().y() - y0))

    print()
    print('=' * 66)
    print('4 负控制：已经在跳时不许叠加')
    print('=' * 66)
    w.is_jumping = True
    w._hop_mode = True
    _jc2 = w.jump_count
    w._start_surprised_hop()
    ok(w.jump_count == _jc2, '空中再触发 ⇒ jump_count 不变（%d）' % _jc2)
    w.is_jumping = False
    w._hop_mode = False

    print()
    print('=' * 66)
    print('通过 %d 项，失败 %d 项' % (_passes[0], len(_fails)))
    if _fails:
        for f in _fails:
            print('  ✗ %s' % f)
        return 1
    print('[PASS] 惊讶小跳行为验证全部通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
