# -*- coding: utf-8 -*-
"""第163轮 · 动画/运动的运行时实测（离屏，只读产品代码）。

用户口径：「尤其是**运动类**和**动画类**那一部分」。

本支只做**事实收集**，不下结论。核心是三个对照实验：

  E1 实际帧率     —— 定时器每 `_anim_tick_ms` 调一次 `update_animation`，
                     它每调一次就 `current_frame += 1`。量真实 FPS。
  E2 帧延迟是否生效 —— 把 `animation_frame_delay` 从 167 改成 500（等价 2fps），
                     若 FPS 一点没变 ⇒ 配置项 `animation.frame_delay` 是死参数。
  E3 尺寸变化频次  —— 跨动画切换时窗口 resiz 的次数（第162轮已修锚点，
                     但"变尺寸"本身仍在；量它有多频繁）。

安全：`RALSEI_DATA_DIR` 指向 `D:\\_tmp`，并把 `memory_store.find_device_dir` /
`data_store.vault_root` 打桩成 None（第162轮教训：`MemorySystem.__init__` 自己找设备，
不桩会写用户真金库）。跑前备份 `config.json`，跑后还原。

跑法：`C:\\Python311\\python.exe probe163_fps.py`
"""
import io
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
DATA = os.path.join(__import__('tempfile').gettempdir(), 'pet163_data')
CFG = os.path.join(ROOT, 'ralsei_pet', 'config.json')
CFG_BAK = os.path.join(__import__('tempfile').gettempdir(), 'config163.bak')

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['RALSEI_DATA_DIR'] = DATA
os.makedirs(DATA, exist_ok=True)

sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'src'))

try:
    import memory_store as _ms
    _ms.find_device_dir = lambda create=True: None
except Exception as e:
    print('[WARN] 打桩 memory_store 失败: %s' % e)
try:
    import data_store as _ds
    _ds.vault_root = lambda create=True: None
except Exception as e:
    print('[WARN] 打桩 data_store 失败: %s' % e)

from PyQt5.QtWidgets import QApplication   # noqa: E402
from PyQt5.QtCore import QTimer            # noqa: E402

app = QApplication(sys.argv[:1])

FACTS = []


def fact(k, v):
    FACTS.append((k, v))
    print('[FACT] %-30s = %s' % (k, v), flush=True)


def measure(w, seconds=3.0, keep=None, label=''):
    """跑真实事件循环，采样 (t, current_frame, current_animation)。"""
    samples = []
    t0 = time.time()
    while True:
        now = time.time()
        if now - t0 >= seconds:
            break
        app.processEvents()
        if keep:
            keep(w)
        samples.append((now - t0, w.current_frame, w.current_animation))
        time.sleep(0.004)
    return samples


def analyse(samples, label):
    """从采样算：帧推进次数 / 时长 = 实际 FPS；以及帧序列的步长分布。"""
    if len(samples) < 3:
        fact(label + ' 采样', '不足 3 条')
        return None
    dur = samples[-1][0] - samples[0][0]
    adv = 0
    steps = []
    prev = None
    for t, fr, anim in samples:
        if prev is not None:
            if fr != prev[0] or anim != prev[1]:
                if anim == prev[1]:
                    d = (fr - prev[0]) % 1000
                    steps.append(d)
                adv += 1
        prev = (fr, anim)
    fps = adv / dur if dur > 0 else 0
    uniq_anim = sorted({a for _, _, a in samples})
    fact(label + ' 时长/采样数', '%.2fs / %d' % (dur, len(samples)))
    fact(label + ' 帧变化次数', adv)
    fact(label + ' **实际 FPS**', '%.2f' % fps)
    fact(label + ' 帧步长分布', dict((s, steps.count(s)) for s in sorted(set(steps))))
    fact(label + ' 出现过的动画', uniq_anim)
    return fps


def main():
    shutil.copyfile(CFG, CFG_BAK)
    print('[i] 已备份 config.json -> %s' % CFG_BAK)
    try:
        from main import RalseiPet
        w = RalseiPet()

        fact('配置 animation.fps', w.config_manager.get('animation.fps', '(缺)'))
        fact('配置 animation.frame_delay', w.config_manager.get('animation.frame_delay', '(缺)'))
        fact('属性 animation_fps', getattr(w, 'animation_fps', '(缺)'))
        fact('属性 animation_frame_delay', getattr(w, 'animation_frame_delay', '(缺)'))
        fact('属性 _anim_tick_ms（实际定时器周期）', getattr(w, '_anim_tick_ms', '(缺)'))
        fact('定时器 interval()', w.animation_timer.interval())

        # 只留动画定时器，其它（移动/AI/统计）全停，隔离变量
        for t in w.findChildren(QTimer):
            try:
                t.stop()
            except Exception:
                pass
        w.animation_timer.start(getattr(w, '_anim_tick_ms', 83))

        # ---------------- E0：调用级诊断（每次 update_animation 的间隔与推帧结果）----------------
        _calls = []
        _orig_ua = w.update_animation

        def _ua_wrap(*a, **k):
            _before = w.current_frame
            _t = time.time()
            _r = _orig_ua(*a, **k)
            _calls.append((_t, _before, w.current_frame, bool(getattr(w, 'is_moving', False))))
            return _r

        w.update_animation = _ua_wrap
        _wired = False
        try:
            # 定时器的槽仍指向**旧的绑定方法**，要重新接一次才走 wrapper
            w.animation_timer.timeout.disconnect()
        except Exception:
            pass
        try:
            w.animation_timer.timeout.connect(w.update_animation)
            _wired = True
        except Exception as e:
            print('[WARN] 重接定时器失败: %s' % e, flush=True)

        # ---------------- E1：默认配置下，移动中的帧率 ----------------
        w.is_moving = True
        w.current_direction = 'left'
        w.change_animation('walk_left', force=True)
        s1 = measure(w, 3.0, keep=lambda x: setattr(x, 'is_moving', True), label='E1')
        fps1 = analyse(s1, 'E1 walk_left（默认配置）')

        # ---- E0 结论：调用次数 vs 推帧次数 ----
        if _calls:
            gaps = [(_calls[i][0] - _calls[i - 1][0]) * 1000.0 for i in range(1, len(_calls))]
            pushed = sum(1 for c in _calls if c[2] != c[1])
            dur0 = _calls[-1][0] - _calls[0][0]
            fact('E0 定时器重接成功', _wired)
            fact('E0 update_animation 调用次数', '%d（%.2fs）' % (len(_calls), dur0))
            fact('E0 调用间隔 ms（min/中位/max）',
                 '%.0f / %.0f / %.0f' % (min(gaps), sorted(gaps)[len(gaps) // 2], max(gaps)))
            fact('E0 其中真正推了帧的', '%d（%.1f%%）' % (pushed, 100.0 * pushed / max(1, len(_calls))))
            fact('E0 推帧率 fps', '%.2f' % (pushed / dur0 if dur0 > 0 else 0))
            fact('E0 调用时 is_moving 为真的比例',
                 '%.0f%%' % (100.0 * sum(1 for c in _calls if c[3]) / len(_calls)))
        else:
            fact('E0 update_animation 调用次数', '0（定时器没走 wrapper）')

        # ---------------- E2：把 frame_delay 改成 500，看 FPS 变不变 ----------------
        w.animation_frame_delay = 500
        fact('E2 已把 animation_frame_delay 改成', w.animation_frame_delay)
        w.change_animation('walk_left', force=True)
        s2 = measure(w, 3.0, keep=lambda x: setattr(x, 'is_moving', True), label='E2')
        fps2 = analyse(s2, 'E2 walk_left（frame_delay=500）')

        # ---------------- E2b：把定时器周期本身改成 167 ----------------
        _old_tick = getattr(w, '_anim_tick_ms', 83)
        w.animation_timer.start(167)
        w.change_animation('walk_left', force=True)
        s3 = measure(w, 3.0, keep=lambda x: setattr(x, 'is_moving', True), label='E2b')
        fps3 = analyse(s3, 'E2b walk_left（定时器 167ms）')
        w.animation_timer.start(_old_tick)

        fact('E2 判定：改 frame_delay 后 FPS 变化', '%.2f -> %.2f（差 %.2f）' % (fps1, fps2, fps2 - fps1))
        fact('E2b 判定：改定时器周期后 FPS 变化', '%.2f -> %.2f（差 %.2f）' % (fps1, fps3, fps3 - fps1))

        # ---------------- E3：跨动画切换的尺寸变化 ----------------
        w.is_moving = False
        seq = ['idle', 'walk_left', 'run_right', 'spell', 'act', 'dance', 'splat', 'fall', 'land']
        sizes = []
        for a in seq:
            if a not in w.sprite_loader.sprites:
                continue
            try:
                w.change_animation(a, force=True)
                w.is_moving = (a.startswith(('walk_', 'run_')))
                # ★ 必须清掉帧节流的时间戳：`update_animation` 开头有
                #   `if (now - _last_animation_time)*1000 + 1 < drag_delay: return`
                #   不清就会**整函数早退**，窗口尺寸保持上一次的残值
                #   —— 第一版 E3 九种动画全报 23x50，就是这个假象。
                w._last_animation_time = 0.0
                w.update_animation()
                sizes.append((a, w.current_animation, w.width(), w.height(),
                              getattr(w, '_cached_scale_factor', None),
                              getattr(w, '_anim_container_size', None),
                              getattr(w, '_anim_container_key', None)))
            except Exception as e:
                sizes.append((a, 'ERR:%s' % e, '', '', '', '', ''))
        print('\n[E3] 请求动画 -> 实得动画 / 窗口尺寸 / scale / 容器 / 容器键')
        for a, got, ww, hh, sc, ct, ck in sizes:
            print('      %-12s -> %-14s %-9s scale=%s container=%s key=%s'
                  % (a, got, '%sx%s' % (ww, hh), sc, ct, ck))
        if len(sizes) >= 2:
            ws = {s[2] for s in sizes if s[2] != ''}
            hs = {s[3] for s in sizes if s[3] != ''}
            fact('E3 不同窗口宽', sorted(ws))
            fact('E3 不同窗口高', sorted(hs))
            fact('E3 宽高种类数', '%d / %d' % (len(ws), len(hs)))

        # ---------------- E4：idle 是否真的静止 ----------------
        w.is_moving = False
        w._idle_loop_active = False
        w.change_animation('idle', force=True)
        s4 = measure(w, 2.0, keep=lambda x: setattr(x, 'is_moving', False), label='E4')
        analyse(s4, 'E4 idle（_idle_loop_active=False）')
        fact('E4 IDLE_LOOP_MIN_SECONDS', getattr(w, 'IDLE_LOOP_MIN_SECONDS', getattr(type(w), 'IDLE_LOOP_MIN_SECONDS', '(缺)')))

        w._idle_loop_active = True
        s5 = measure(w, 2.0, keep=lambda x: (setattr(x, 'is_moving', False),
                                             setattr(x, '_idle_loop_active', True)), label='E5')
        analyse(s5, 'E5 idle（_idle_loop_active=True）')

        try:
            w.cleanup_on_exit()
        except Exception as e:
            print('[WARN] cleanup_on_exit 抛错: %s' % e, flush=True)
    finally:
        try:
            shutil.copyfile(CFG_BAK, CFG)
            os.remove(CFG_BAK)
            print('[i] config.json 已还原')
        except Exception as e:
            print('[WARN] 还原 config.json 失败: %s' % e)

    print('\n[FACTS] 共 %d 条' % len(FACTS))


if __name__ == '__main__':
    main()
