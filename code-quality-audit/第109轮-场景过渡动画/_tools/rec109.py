# -*- coding: utf-8 -*-
"""第109轮 · 录屏自检（**真机多帧抓取 + 过渡曲线断言**）。

用户铁律：「**一定要看录像而不是只读后台输出**」；本轮用户解锁：
「**你可以录屏了，我现在不用电脑**」⇒ 用 `QT_QPA_PLATFORM=windows` **真机**跑
（离屏平台 `grabWindow(0)` 必返 null，抓不到真帧）。

本支做的两件事：
  A. **抓帧**：真机驱动一次"带过渡的场景切换"，在过渡期间**高频密采**
     `scene_canvas._transition_alpha`，把整条 α(t) 曲线记下来；
     同时在若干个关键时刻抓 PNG 落盘（供人眼逐帧复核）。
  B. **断言**：把 α 曲线当**行为证据**判：
     T1 起点 α ≈ 0（正常态不遮屏）· T2 中间出现 α ≈ 1（换房那一拍全黑掩护）·
     T3 终点 α 回到 0（恢复）· T4 α **单调上升再单调下降**（不是跳变）·
     T5 淡出段时长 ≈ 267ms、淡入段 ≈ 417ms（与原作换算值同量级）·
     T6 换房真的发生了（scene_id 前后不同）· T7 负控制：不动它 ⇒ α 恒 0。

★ 透明分层窗口的"可见面积"工具会失效 ⇒ 只断言**几何/状态**（第73.8 条）；
  PNG 仅作人眼证据，不做像素级判据。

跑法（真机）：
    set QT_QPA_PLATFORM=windows && C:\\Python311\\python.exe rec109.py
（不设 QPA 时退化为离屏：只跑几何/状态断言，PNG 数为 0 属预期。）
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

# ★ 默认离屏（无人值守可跑）；显式 `QT_QPA_PLATFORM=windows` 时走真机抓帧。
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('RALSEI_TEST_MODE', '1')

_EV = os.path.abspath(os.path.join(HERE, '..', '_evidence'))
_FR = os.path.join(_EV, 'frames109')
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
print(u'第109轮 · 录屏自检（真机多帧抓取 + 过渡曲线断言）')
print(u'QPA = %s' % os.environ.get('QT_QPA_PLATFORM'))
print(u'=' * 72)

_res = {}
try:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QTimer

    _app = QApplication.instance() or QApplication(sys.argv)
    import main as _M

    _box = {}          # 持有 pet（避免闭包取值陷阱）
    _samples = []      # 过渡期间的 α 采样：(t_ms, alpha, scene_id)
    _snaps = []        # 关键时刻的几何/PNG 快照
    _marks = {}

    def _alpha_of(pet):
        cv = pet.__dict__.get('scene_canvas')
        if cv is None:
            return None
        try:
            return float(cv.transition_alpha())
        except Exception:
            return getattr(cv, '_transition_alpha', None)

    def _scene_of(pet):
        try:
            return getattr(pet.__dict__.get('_scene_state'), 'scene_id', None)
        except Exception:
            return None

    def _snap(tag, note=u'', grab=True):
        pet = _box.get('pet')
        if pet is None:
            return
        try:
            cv = pet.__dict__.get('scene_canvas')
            rec = {
                'tag': tag, 'note': note,
                'alpha': _alpha_of(pet),
                'scene_id': _scene_of(pet),
                'canvas_size': (cv.width(), cv.height()) if cv else None,
                'canvas_pos': (cv.x(), cv.y()) if cv else None,
                'trans_active': bool(pet.__dict__.get('_scene_trans_active')),
            }
            if grab and os.environ.get('QT_QPA_PLATFORM') != 'offscreen':
                try:
                    pm = _app.primaryScreen().grabWindow(0)
                    if not pm.isNull():
                        fn = os.path.join(
                            _FR, u'k%03d_%s.png' % (len(_snaps), tag))
                        pm.save(fn)
                        rec['png'] = os.path.basename(fn)
                except Exception as _e:
                    rec['png_err'] = str(_e)
            _snaps.append(rec)
        except Exception:
            traceback.print_exc()

    # ---- 采样器：真机下 `QTimer(16ms)` **不可靠**（窗口事件循环节流 ⇒ 实测
    #   真机 `_samples` 全是 0）。改用**阻塞轮询**（阶段性 sleep + 直接读 α）——
    #   过渡总时长仅 ~684ms，主线程短暂阻塞无害（这是测试支，不是产品）。
    #   ★ 抓帧（`grabWindow`）会阻塞数百 ms ⇒ **只在定点**做，不放进轮询循环。
    def _poll(duration_ms, grab_every=0):
        """在 `duration_ms` 内密集读 α 曲线（阻塞）。`grab_every>0` 时每 N 次抓帧。"""
        pet = _box.get('pet')
        if pet is None:
            return
        t_end = time.time() * 1000.0 + duration_ms
        n = 0
        while time.time() * 1000.0 < t_end:
            _samples.append((time.time() * 1000.0, _alpha_of(pet),
                             _scene_of(pet)))
            n += 1
            if grab_every and n % grab_every == 0:
                _snap(u'trans_f%03d' % len(_samples), u'过渡中', grab=True)
            time.sleep(0.012)

    # ---- 阶段 ----
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
        """基线：不动 ⇒ α 必须恒 0（T7 负控制）。"""
        pet = _box.get('pet')
        try:
            for _i in range(8):
                _samples.append((time.time() * 1000.0, _alpha_of(pet),
                                 _scene_of(pet)))
                time.sleep(0.02)
            _marks['idle_alpha_max'] = max(
                (a for (_t, a, _s) in _samples), default=None)
            _snap(u'idle', u'未切场景（α 应恒 0）')
            QTimer.singleShot(200, _stage3)
        except Exception:
            _res['err'] = traceback.format_exc()
            try:
                _app.quit()
            except Exception:
                pass

    def _stage3():
        """发起一次**带过渡**的场景切换，开始密采。"""
        pet = _box.get('pet')
        try:
            _marks['scene_before'] = _scene_of(pet)
            _samples.clear()          # 只留过渡期间的曲线
            _timer.start()
            _t_start = time.time() * 1000.0
            # 目标：第一章房间（已登记在案）
            _accepted = False
            try:
                _accepted = bool(pet.travel_to_scene(
                    'ch1.kris_room.kris_s_room'))
            except Exception as _e:
                _res['travel_err'] = str(_e)
            _marks['accepted'] = _accepted
            _marks['t_start'] = _t_start
            # 过渡总时长 ~684ms；等 1400ms 收尾
            QTimer.singleShot(1400, _stage4)
        except Exception:
            _res['err'] = traceback.format_exc()
            try:
                _app.quit()
            except Exception:
                pass

    def _stage4():
        pet = _box.get('pet')
        try:
            _marks['scene_after'] = _scene_of(pet)
            _marks['alpha_end'] = _alpha_of(pet)
            _snap(u'after_trans', u'过渡结束后（α 须回 0、场景已变）')
            # 再切回桌面（再来一次，确认可重复）
            _samples.clear()
            try:
                pet.travel_to_scene('desktop')
            except Exception:
                pass
            _marks['t_start2'] = time.time() * 1000.0
            QTimer.singleShot(1400, _finish)
        except Exception:
            _res['err'] = traceback.format_exc()
            try:
                _app.quit()
            except Exception:
                pass

    def _finish():
        pet = _box.get('pet')
        try:
            _marks['alpha_end2'] = _alpha_of(pet)
            _snap(u'back_desktop', u'切回桌面后（α 须回 0）')
        except Exception:
            pass
        finally:
            _timer.stop()
            _res['samples'] = _samples
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
except Exception:
    _res['err'] = traceback.format_exc()

if _res.get('err'):
    print(_res['err'])
    ok(u'T0 真机启动', False, u'见上')

_samples = _res.get('samples') or []
_snaps = _res.get('snaps') or []
_marks = _res.get('marks') or {}

print(u'        采样 %d 点 · 快照 %d 张' % (len(_samples), len(_snaps)))
for _s in _snaps:
    print(u'        [%s] alpha=%s scene=%s active=%s png=%s'
          % (_s.get('tag'), _s.get('alpha'), _s.get('scene_id'),
             _s.get('trans_active'), _s.get('png')))

# ---------------------------------------------------------------------
sec(u'T7 负控制：不动它 ⇒ 过渡期间无采样、α 恒 0')

ok(u'T7 ★★ 未发起过渡时 α 恒 0（`idle_alpha_max` 为空或 0）',
   (_marks.get('idle_alpha_max') or 0.0) == 0.0,
   u'idle_alpha_max=%r' % (_marks.get('idle_alpha_max'),))

sec(u'T1~T6 过渡曲线（真机行为证据）')

if not _samples:
    ok(u'T1 ★★★ 抓到过渡期间的 α 采样（零采样 ⇒ 过渡根本没跑 / 采集器失效）',
       False, u'samples=0')
else:
    _alphas = [a for (_t, a, _s) in _samples]
    _a0 = _alphas[0]
    _amax = max(_alphas)
    _alast = _alphas[-1]
    _t0 = _samples[0][0]
    _ts = [_t - _t0 for (_t, _a, _s) in _samples]
    # 找 α 首次达峰的时刻（换房那一拍）
    _ipk = _alphas.index(_amax)
    _t_pk = _ts[_ipk]

    ok(u'T1 ★★★ 过渡起点 α ≈ 0（正常态不遮屏）',
       _a0 <= 0.05, u'alpha0=%.3f' % _a0)
    ok(u'T2 ★★★ 过渡中 α 触达 ≈ 1（换房那一拍全黑掩护 —— 原作序）',
       _amax >= 0.9, u'alpha_max=%.3f @ %.0fms' % (_amax, _t_pk))
    ok(u'T3 ★★★ 过渡终点 α 回到 0（画面已恢复，不残留全黑）',
       _alast <= 0.05, u'alpha_end=%.3f' % _alast)
    # T4 单调上升（到峰前）再单调下降（峰后），允许 5% 噪声容差
    _up = _alphas[:_ipk + 1]
    _down = _alphas[_ipk:]
    _up_mono = all(_up[i + 1] >= _up[i] - 0.05 for i in range(len(_up) - 1))
    _down_mono = all(_down[i + 1] <= _down[i] + 0.05
                     for i in range(len(_down) - 1))
    ok(u'T4 ★★ α 曲线"先升后降"（不是瞬间跳变 —— 原作是逐帧 `image_alpha += fadespeed`）',
       _up_mono and _down_mono and _ipk > 0 and _ipk < len(_alphas) - 1,
       u'升=%r 降=%r 峰序=%d/%d' % (_up_mono, _down_mono, _ipk, len(_alphas)))
    # T5 淡出段 / 淡入段时长（与原作 267 / 417 ms 同量级，容差宽）
    # ★★ 判据修正（首轮 T5 假红，**先怀疑判据**）：初版把"淡入段"量成
    #   `_ts[-1] - _t_pk`（采样窗口末尾）⇒ 而采样器一直采到 1400ms 才停
    #   （过渡 684ms 就结束，其后 700ms 的 α≡0 全被算进淡入段 ⇒ 1114ms）
    #   ⇒ 这是**采集口径错**，不是产品错。正解：淡入段 = 峰值到"α 首次
    #   **回落到 0**"的那一点（这才是淡入真正结束的时刻）。
    _t_end_in = None
    for _i in range(_ipk, len(_alphas)):
        if _alphas[_i] <= 0.05:
            _t_end_in = _ts[_i]
            break
    _out_ms = _t_pk
    _in_ms = (_t_end_in - _t_pk) if _t_end_in is not None else -1.0
    ok(u'T5 ★★ 淡出段时长 ≈ 267ms、淡入段 ≈ 417ms（原作换算；容差 ±60%）',
       _out_ms > 0 and _in_ms > 0
       and 0.4 * 267 <= _out_ms <= 1.6 * 267
       and 0.4 * 417 <= _in_ms <= 1.6 * 417,
       u'out=%.0fms in=%.0fms（原作 267/417；淡入终点=α首次回0）'
       % (_out_ms, _in_ms))
    # T6 换房真的发生了
    ok(u'T6 ★★★ 过渡真的换了场景（scene_id 前后不同）',
       _marks.get('scene_before') is not None
       and _marks.get('scene_after') is not None
       and _marks.get('scene_before') != _marks.get('scene_after'),
       u'%s → %s（accepted=%r）'
       % (_marks.get('scene_before'), _marks.get('scene_after'),
          _marks.get('accepted')))
    ok(u'T6b ★★ 请求被接受（走的是过渡路径，不是同步回落）',
       _marks.get('accepted') is True,
       u'accepted=%r' % (_marks.get('accepted'),))
    ok(u'T6c ★★ 第二次切换（回桌面）后 α 也回到 0（可重复，不卡死）',
       (_marks.get('alpha_end2') or 0.0) <= 0.05,
       u'alpha_end2=%r' % (_marks.get('alpha_end2'),))

sec(u'T8 抓帧落盘')

_offscreen = os.environ.get('QT_QPA_PLATFORM') == 'offscreen'
_pngs = [s.get('png') for s in _snaps if s.get('png')]
# ★ 判据自身体检（沿用 rec107 的教训）：离屏平台 `grabWindow(0)` **必然 null**
#   ⇒ "抓到 PNG" 在离屏下不可能成立，属"夹具不保真" ⇒ 按平台分派。
if _offscreen:
    ok(u'T8 ★★ 离屏平台：状态采集成功 %d/%d 快照'
       u'（`grabWindow(0)` 在离屏下必然 null ⇒ 不拿"抓到 PNG"当判据）'
       % (len(_snaps), len(_snaps)),
       len(_snaps) >= 3, u'snaps=%d png=%d' % (len(_snaps), len(_pngs)))
    ok(u'T8c ★★ 离屏下 PNG 为 0 是**预期**（真机请用 `QT_QPA_PLATFORM=windows`）',
       len(_pngs) == 0, u'png=%d' % len(_pngs))
else:
    ok(u'T8 ★★ 真机抓到 ≥3 帧 PNG 落盘（供人眼逐帧复核）',
       len(_pngs) >= 3, u'n=%d %s' % (len(_pngs), _pngs))
ok(u'T8b 帧目录在盘', os.path.isdir(_FR), u'%s' % _FR)

# ---------------------------------------------------------------------
print(u'\n' + u'=' * 72)
print(u'第109轮录屏自检：PASS=%d FAIL=%d' % (_N['p'], _N['f']))
print(u'=' * 72)

_meta = os.path.join(_EV, 'rec109_meta.txt')
try:
    with io.open(_meta, 'w', encoding='utf-8') as f:
        f.write(u'\n'.join(_OUT) + u'\n\n---- CURVE ----\n')
        for (_t, _a, _s) in _samples:
            f.write(u'%.1fms\t%.4f\t%s\n' % (_t, _a, _s))
        f.write(u'\n---- SNAPS ----\n')
        for s in _snaps:
            f.write(u'%s\n' % (s,))
    print(u'证据已落盘：%s' % _meta)
except Exception as e:
    print(u'落盘失败：%s' % e)

sys.exit(1 if _N['f'] else 0)
