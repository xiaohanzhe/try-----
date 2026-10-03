# -*- coding: utf-8 -*-
"""第82轮 R5 真机验证：**Z 键附身**（用户口径「交互键用 Z，达到原作操控的功能」）。

做法（不靠"看起来对"，靠数值）：
  1) 真机起 `RalseiPet()`（唯一可靠方式：PowerShell `&` + run_in_background）；
  2) **目标收集**：`_possession_targets` 必须真含 kris/os_niko/ut_frisk 三个
     （★ 这是本轮修掉的真 bug：模块只认 dict ⇒ 真机拿 NpcRegistry 对象 ⇒ 空表）；
  3) **A/B 锚点**（附身 = 换方向键消费方）：
       ① 未附身：按左 ⇒ 灵魂动、角色坐标不动（控制权在灵魂）
       ② 按 Z 附身 kris ⇒ 灵魂收起；再按左 ⇒ **角色坐标动、灵魂不动**
       ★ 必须 ①的Δ角色==0 且 ②的Δ角色!=0，否则"附身"没真的转移控制权。
  4) **解除**：再按 Z ⇒ 灵魂回来 + 角色停住（控制权归还）。
  5) kris 是 DIRECT（不征求）；os_niko 是 CONSENT ⇒ 必须进 ASKING（不直接附身）。

★ 判据纪律：先声明 DPI 感知；每段独立打印；退出码 0 = 全过。
★ 墙面事实：附身驱动靠 `_possession_tick(dt)`，本脚本**直接调它**喂 dt
  （不靠真键盘事件，避免焦点/时序问题）；Z 键本身走 `toggle_possession()`。
★ 真机里 `current_scene` 未必是 desktop ⇒ 目标 scene 可能对不上；
  本脚本**先把三者场景都对齐**再测（否则测的是"跨场景被拒"）。

用法（后台跑）：
  & C:\Python311\python.exe <本文件>
"""
import ctypes
import io
import os
import sys
import time

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
SRC = os.path.join(ROOT, 'ralsei_pet')
MODS = os.path.join(SRC, 'modules')
SRCDIR = os.path.join(SRC, 'src')
for p in (SRCDIR, SRC, MODS):
    if p not in sys.path:
        sys.path.insert(0, p)

_lines = []


def w(s=''):
    _lines.append(s)
    try:
        print(s, flush=True)
    except Exception:
        pass


def _dump(path):
    try:
        io.open(path, 'w', encoding='utf-8', newline='\n').write('\n'.join(_lines))
    except Exception:
        pass


EVID = os.path.join(ROOT, 'code-quality-audit', '第82轮-灵魂附身R5', '_evidence')
os.makedirs(EVID, exist_ok=True)
OUT = os.path.join(EVID, 'live_r5_82.txt')

DT = 1.0 / 30.0

w('=== 第82轮 R5 真机取证：Z 键附身 ===')
w('时间 = %s' % time.strftime('%Y-%m-%d %H:%M:%S'))
w('ROOT = %s' % ROOT)
w()

rc = 1
p = None
_fails = []


def chk(tag, cond):
    w('  [%s] %s' % ('PASS' if cond else 'FAIL', tag))
    if not cond:
        _fails.append(tag)


try:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import Qt  # noqa: F401
    app = QApplication.instance() or QApplication(sys.argv)

    import main as main_mod
    w('main.py 已导入：%s' % main_mod.__file__)

    p = main_mod.RalseiPet()
    w('RalseiPet() 构造成功')
    w('  POSSESSION_ENABLED = %r' % getattr(type(p), 'POSSESSION_ENABLED', None))
    app.processEvents()
    w()

    # ---- ① 目标收集（本轮修的真 bug：真机路径 NpcRegistry 对象） ----
    w('## ① 可附身目标收集')
    poss = getattr(p, 'possession', None)
    w('  possession = %r' % (type(poss).__name__ if poss else None))
    chk('附身系统已建起来', poss is not None)
    tgs = dict(getattr(p, '_possession_targets', {}) or {})
    w('  _possession_targets = %r' % sorted(tgs))
    chk('★ 目标含 kris / os_niko / ut_frisk（实得 %r）' % sorted(tgs),
        sorted(tgs) == ['kris', 'os_niko', 'ut_frisk'])
    if tgs.get('kris'):
        w('  kris.kind = %r  name = %r' % (tgs['kris'].kind, tgs['kris'].name))
        chk('kris 是 DIRECT 且名字来自登记表（%r）' % tgs['kris'].name,
            tgs['kris'].kind == 'direct' and tgs['kris'].name != 'kris')
    w()

    # ---- 场景对齐：把三个目标 scene 都设成 None（= 不校验），专测附身本身 ----
    for t in tgs.values():
        try:
            t.scene = None
        except Exception:
            pass

    # ---- ② A/B 锚点：控制权转移 ----
    w('## ② 控制权转移（A/B 锚点）')
    try:
        p.init_soul()
    except Exception as e:
        w('  init_soul: %r' % e)
    app.processEvents()
    soul = getattr(p, 'soul', None)
    chk('灵魂实体在', soul is not None)
    if soul is None:
        raise SystemExit(2)

    # 附身前：拿到角色可动坐标（kris 在桌面上的实体坐标走 poss.state.x/y）
    # 附身尚未开始 ⇒ 状态机内部坐标就是"接管后角色会从这里走"
    st = poss
    w('  附身前 poss.mode=%r x=%.2f y=%.2f' % (st.mode, st.x, st.y))

    soul_before = soul.state.center()
    # 未附身：按左 ⇒ 灵魂动、poss 坐标不动
    p._soul_press('left')
    for _ in range(10):
        try:
            soul.tick(DT)
        except Exception:
            break
    p._soul_release('left')
    app.processEvents()
    soul_after1 = soul.state.center()
    d_soul1 = soul_after1[0] - soul_before[0]
    d_char1 = st.x  # 未附身时不会动
    w('  未附身按左10帧：灵魂Δx=%.2f  poss.x=%.2f' % (d_soul1, d_char1))
    chk('① 未附身：灵魂真的动了（Δx≠0，实得 %.2f）' % d_soul1, abs(d_soul1) > 1e-6)
    chk('① 未附身：角色坐标**没动**（控制权不在角色，poss.x=%.2f）' % d_char1,
        abs(d_char1) < 1e-6)
    x0 = st.x
    w()

    # 附身：走 Z 键主入口（真产品路径）
    w('## ③ 按 Z 附身 kris')
    p.toggle_possession()
    app.processEvents()
    w('  附身后 mode=%r 目标=%r' % (st.mode, st.possessed_id))
    chk('★ 附身成立（mode=possessed，目标 kris）',
        st.mode == 'possessed' and st.possessed_id == 'kris')
    vis_now = bool(p._soul_visible())
    w('  灵魂可见 = %r（期望 False：操控权已转移）' % vis_now)
    chk('★ 附身后灵魂收起（_soul_visible()=False）', vis_now is False)

    # 附身后：按左 ⇒ 角色动、灵魂不动
    soul_before2 = soul.state.center()
    st.press('left')
    for _ in range(10):
        p._possession_tick(DT)        # ★ 真产品驱动路径
    st.release_key('left')
    app.processEvents()
    d_char2 = st.x - x0
    d_soul2 = soul.state.center()[0] - soul_before2[0]
    w('  附身后按左10帧：角色Δx=%.2f  灵魂Δx=%.2f' % (d_char2, d_soul2))
    chk('★ 附身：角色坐标真的动了（Δx≠0，实得 %.2f）' % d_char2, abs(d_char2) > 1e-6)
    chk('★ 附身：每帧约 3px（10帧≈-30，实得 %.2f）' % d_char2,
        abs(d_char2 + 30.0) < 1.0)
    chk('② 附身：灵魂坐标不动（Δx=%.2f）' % d_soul2, abs(d_soul2) < 1e-6)
    w()

    # ---- ④ 解除 ----
    w('## ④ 再按 Z 解除')
    p.toggle_possession()
    app.processEvents()
    w('  解除后 mode=%r' % st.mode)
    chk('★ 解除成立（mode=free）', st.mode == 'free')
    chk('★ 解除后灵魂回来（_soul_visible()=True）', bool(p._soul_visible()))
    x_after_release = st.x
    st.press('left')
    for _ in range(5):
        p._possession_tick(DT)
    st.release_key('left')
    app.processEvents()
    chk('★ 解除后角色不再被驱动（Δx=%.2f ≈ 0）' % (st.x - x_after_release),
        abs(st.x - x_after_release) < 1e-6)
    w()

    # ---- ⑤ os_niko 走征求同意（CONSENT） ----
    w('## ⑤ os_niko 必须征求意见（不能直接附身）')
    niko = tgs.get('os_niko')
    if niko is not None:
        niko.scene = None
        # 强制选 niko：临时把目标表缩小到只有 niko
        saved = dict(p._possession_targets)
        p._possession_targets = {'os_niko': niko}
        p.toggle_possession()
        app.processEvents()
        w('  按 Z 后 mode=%r  target=%r' % (
            st.mode, (st.target.npc_id if st.target else None)))
        # ★ 判据修正（本脚本首版写错）：`possessed_id` 在**非附身态**故意返回 None
        #   （"征求中"还没附身，语义正确）⇒ 该查 `st.target`，不是 `possessed_id`。
        #   这正是"判据本身也是被测物"——报红先怀疑判据，实测证实是判据错、产品对。
        chk('★ os_niko 按 Z ⇒ 进 ASKING（不直接附身）',
            st.mode == 'asking' and st.target is not None
            and st.target.npc_id == 'os_niko')
        # 同意后才附身
        st.grant()
        app.processEvents()
        w('  grant 后 mode=%r' % st.mode)
        chk('★ 同意后 ⇒ possessed', st.mode == 'possessed')
        p.toggle_possession()          # 收尾：解除
        p._possession_targets = saved
    app.processEvents()
    w()

    w('=== 结论 ===')
    w('  失败项 = %r' % (_fails,))
    w('  R5 真机判定 = %s' % ('PASS' if not _fails else 'FAIL'))
    rc = 0 if not _fails else 1

except SystemExit as e:
    rc = e.code or 0
except Exception:
    import traceback
    w('!! 真机验证异常：')
    w(traceback.format_exc())
    rc = 3
finally:
    _dump(OUT)
    print('written:', OUT, flush=True)
    try:
        if p is not None:
            p.close()
    except Exception:
        pass
    try:
        from PyQt5.QtWidgets import QApplication
        a = QApplication.instance()
        if a:
            a.quit()
    except Exception:
        pass
    os._exit(rc)
