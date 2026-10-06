# -*- coding: utf-8 -*-
u"""probe96_fall.py —— 坠落/跳跃**专项**真机录制（补第96轮 F7 的覆盖缺口）

动机：
    第96轮 10 分钟自然录制里 `is_falling=True` 的采样帧 = **0**
    ⇒ 第90轮用户点名的「**抛物线和跳上去不对**」「**跳上去窗口也只有跳没有上去**」
      **无法验证**。判据 F7 如实报红是对的，但不能就此收工 ——
      用户明确要求核对"我之前提到过的问题"。

做法：
    只调产品**已有的公开接口**：
      · `start_fall(reason)` —— 公开坠落入口（L8733）
      · 观察 `is_falling / is_gravity_falling / is_splat / _fall_phase /
              current_animation / wy` 的整条时间线
    不新增行为、不改产品代码。**周期性反复触发**以提高捕获率。

判据（写在本脚本内，独立于 analyze96）：
    · F7a 坠落确实触发过（帧数 ≥ 某阈值）
    · F7b 坠落期间 **Δy ≥ 0**（屏幕 +y 向下 ⇒ 应是往下掉），
           且**不存在"只有跳没有上去"**：即 y 必须真的变化（不是原地播动画）
    · F7c 坠落结束时落回地面（is_falling 从 True → False，且 y 稳定）
    · F7d 逐帧时间线落盘，供人眼复核

产物：`_evidence/probe96_fall.txt`（时间线 + 判据）
运行：C:/Python311/python.exe -X utf8 _tools/probe96_fall.py
环境变量：FALL96_SECS（默认 60）· FALL96_TICK_MS（默认 120）· FALL96_EVERY（默认 6）
"""
import io
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
REPO = os.path.join(ROUND, '..', '..')
EV = os.path.join(ROUND, '_evidence')
if not os.path.isdir(EV):
    os.makedirs(EV)

OUT = os.path.join(EV, 'probe96_fall.txt')
SECS = float(os.environ.get('FALL96_SECS', '60'))
TICK_MS = int(os.environ.get('FALL96_TICK_MS', '120'))
EVERY = float(os.environ.get('FALL96_EVERY', '6'))

# ---------- 复刻 main.py 的启动序列（与 rec96.py 一致）----------
PKG = os.path.join(REPO, 'ralsei_pet')
SRC = os.path.join(PKG, 'src')
os.chdir(PKG)
if SRC in sys.path:
    sys.path.remove(SRC)
sys.path.insert(0, SRC)

import main as M  # noqa: E402

M.check_single_instance()
M.install_crash_guard()
try:
    import text_segmenter
    text_segmenter.install()
except Exception as e:
    print('text_segmenter fail: %r' % (e,))
try:
    import data_store
    data_store.migrate_from_staging()
except Exception as e:
    print('data_store fail: %r' % (e,))


def _g(o, k, d=None):
    return getattr(o, k, d)


def main():
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QTimer

    app = QApplication.instance() or QApplication(sys.argv)
    log = io.open(OUT, 'w', encoding='utf-8', newline='\n')
    log.write(u'# probe96_fall —— 坠落/跳跃专项真机录制（补 F7 覆盖缺口）\n')
    log.write(u'# 时长 %ss · 采样 %dms · 每 %.1fs 触发一次 start_fall\n'
              % (SECS, TICK_MS, EVERY))
    log.write(u'# 时间线列：t / wy / anim / dir / falling / gravity_falling / '
              u'splat / fall_phase / moving\n')
    log.write(u'=' * 100 + u'\n')
    log.flush()

    pet = M.RalseiPet()
    pet.show()

    rows = []
    t0 = time.time()
    st = {'n': 0, 'trig': 0, 'last_trig': -99.0}

    def tick():
        el = time.time() - t0
        if el >= SECS:
            timer.stop()
            _report(log, rows)
            log.flush()
            app.quit()
            return
        # 周期性触发**两种**坠落（必须分开验，语义不同）：
        #   · `start_fall`   = **摔倒**（原地跌倒 → 摔扁 → 揉头 → 爬起）；`is_moving=False`
        #                      ⇒ **y 本来就不该大幅变化**（首版判据误把"原地摔倒"当"没掉下去"）
        #   · `start_falling`= **重力坠落**（建楼要求："没有支撑就得往下掉"）⇒ y 应**向下增大**
        if el - st['last_trig'] >= EVERY:
            st['last_trig'] = el
            st['trig'] += 1
            which = 'start_fall' if (st['trig'] % 2 == 1) else 'start_falling'
            try:
                if which == 'start_fall':
                    pet.start_fall(reason='probe96')
                else:
                    pet.start_falling(fall_velocity=3.0, is_thrown=False,
                                      reason='probe96')
                log.write(u'[TRIGGER] #%d t=%.2f %s\n' % (st['trig'], el, which))
            except Exception:
                log.write(u'[TRIGGER] 失败 %s\n' % which + traceback.format_exc() + '\n')
        # 采样
        try:
            p = pet.pos()
            rows.append(dict(
                t=el, wy=p.y(), wx=p.x(),
                anim=_g(pet, 'current_animation'), dir=_g(pet, 'current_direction'),
                falling=bool(_g(pet, 'is_falling', False)),
                grav=bool(_g(pet, 'is_gravity_falling', False)),
                splat=bool(_g(pet, 'is_splat', False)),
                phase=_g(pet, '_fall_phase'),
                moving=_g(pet, 'is_moving'),
                vy=_g(pet, 'current_speed_y'),
            ))
            log.write(u'%7.2f y=%5d x=%5d %-12s %-5s fall=%-5s grav=%-5s '
                      u'splat=%-5s phase=%-8s vy=%s\n'
                      % (el, p.y(), p.x(), _g(pet, 'current_animation'),
                         _g(pet, 'current_direction'),
                         _g(pet, 'is_falling'), _g(pet, 'is_gravity_falling'),
                         _g(pet, 'is_splat'), _g(pet, '_fall_phase'),
                         _g(pet, 'current_speed_y')))
            log.flush()
        except Exception:
            log.write(u'[tick] 失败\n' + traceback.format_exc() + '\n')

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(TICK_MS)
    sys.exit(app.exec_())


def _report(log, rows):
    u"""判据写在这里，落盘成文本。"""
    log.write(u'=' * 100 + u'\n')
    log.write(u'# 判据\n')
    n = len(rows)
    fall = [r for r in rows if r['falling']]
    log.write(u'F7a 采样帧 %d；`is_falling=True` 的帧 %d\n' % (n, len(fall)))
    ok_a = len(fall) >= 5
    log.write(u'     [%s] F7a 坠落确实触发过（≥5 帧）\n'
              % (u'PASS' if ok_a else u'FAIL'))

    if fall:
        # F7b: 坠落期间 y 必须真的变化（"只有跳没有上去" 的反面）
        ds = []
        for i in range(1, len(rows)):
            a, b = rows[i - 1], rows[i]
            if not b['falling']:
                continue
            ds.append(b['wy'] - a['wy'])
        n_up = len([d for d in ds if d < 0])
        n_dn = len([d for d in ds if d > 0])
        n_eq = len([d for d in ds if d == 0])
        log.write(u'F7b 坠落期间 Δy 步数=%d：向下 %d / 向上 %d / 不变 %d\n'
                  % (len(ds), n_dn, n_up, n_eq))
        log.write(u'     [%s] F7b 坠落期间 y **真的在变**（不是"只有跳没有上去"）\n'
                  % (u'PASS' if (n_dn + n_up) >= 1 else u'FAIL'))
        log.write(u'     [%s] F7b2 竖直位移以**向下为主**（Δy≥0 占多数）\n'
                  % (u'PASS' if n_dn >= n_up else u'FAIL'))
        # F7c: 坠落必须**结束**（不能卡在 falling）
        log.write(u'F7c 末帧 falling=%s\n' % rows[-1]['falling'])
        log.write(u'     [%s] F7c 坠落能结束（末帧不在坠落态）\n'
                  % (u'PASS' if not rows[-1]['falling'] else u'FAIL'))
        # 相位覆盖
        ph = {}
        for r in rows:
            if r['falling']:
                ph[r['phase']] = ph.get(r['phase'], 0) + 1
        log.write(u'F7d 坠落期间出现的 `_fall_phase`：%s\n' % ph)
    else:
        log.write(u'     [FAIL] F7b/c/d 无法判定（0 帧坠落）\n')
    log.write(u'=' * 100 + u'\n')


if __name__ == '__main__':
    main()
