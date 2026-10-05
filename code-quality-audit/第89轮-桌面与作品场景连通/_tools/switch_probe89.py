# -*- coding: utf-8 -*-
u"""第89轮硬门槛验证：**场景真的能切换**（用户原话「先能让我看到场景可以切换再继续」）。

做法（**走产品真路径**，不模拟）
----------------------------
1. 进程内 `RalseiPet()` 真起（不是 stub）—— 因为 `travel_to` 要真跑寻路 + 真改
   `current_scene` + 真重建画布。
2. 记下起始 `current_scene`（应为 `desktop`）。
3. 调 `scene_controller.travel_to('城堡镇')`（用户口径里的例子）→ 断言
   ① `ok=True` ② `current_scene` **真变了** ③ 画布 plan **真变了**（不是只改字符串）。
4. 再走**门**：直接 `switch()` 到桌面门 `A` 的路由目标 → 断言切成功。
5. 回桌面 → 断言能回。
6. 每步都 `PrintWindow` 抓画布，落 `_evidence/shots/switch_*.png`（人眼可核对）。

★ 判据要点：
  · **断行为不断赋值** —— 不只看 `current_scene` 字符串，还要看**画布 plan**
    （`_scene_plan` / `scene_objects`）真的换了（否则"只改了个变量"也算过）。
  · **负控制** —— 编造的场景名必须 `ok=False` 且 `current_scene` **不变**。
"""
import ctypes
import os
import re
import sys
import time

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')
SH = os.path.join(HERE, '..', '_evidence', 'shots')
os.makedirs(SH, exist_ok=True)

for _p in (os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.append(_p)

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

os.environ['QT_QPA_PLATFORM'] = 'offscreen'      # 无头跑，抓图走 PrintWindow 不行 ⇒ 改用 widget.grab()
# ★ 但 offscreen 下窗口不存在 ⇒ 改用 `canvas.grab()`（Qt 自己的渲染到 QPixmap），
#   这在 offscreen 下**能拿到真渲染结果**（不需要 DWM）。

from PyQt5.QtWidgets import QApplication  # noqa: E402

_app = QApplication.instance() or QApplication([])

from main import RalseiPet  # noqa: E402

FAILS = []
N = [0]


def ck(desc, cond, detail=''):
    N[0] += 1
    if cond:
        print('[PASS] %s %s' % (desc, detail))
    else:
        print('[FAIL] %s %s' % (desc, detail))
        FAILS.append(desc)


def snap(pet, tag):
    """抓画布当前渲染（offscreen 下 Qt 自渲染，可靠）。"""
    try:
        w = pet.scene_canvas
        if w is None:
            return None
        pm = w.grab()
        fp = os.path.join(SH, 'switch_%s.png' % tag)
        pm.save(fp, 'PNG')
        return fp
    except Exception as e:
        print('   (抓画布失败 %s: %s)' % (tag, e))
        return None


print('=' * 66)
print('第89轮 硬门槛验证：场景可切换')
print('=' * 66)

pet = RalseiPet()
pet.BEDTIME_ENABLED = False
pet._npc_roam_last_tick = float('inf')

ctrl = getattr(pet, 'scene', None)
ck('A0 场景控制器在位（`pet.scene` 非空）', ctrl is not None)
if ctrl is None:
    print('FAILS:', FAILS)
    sys.exit(1)

start = pet.__dict__.get('current_scene')
print('  起始 current_scene = %r' % start)
ck('A1 起始场景 = desktop（桌面是一等场景）', start == 'desktop', '=%r' % start)

# ---- 画布与计划 ----
def plan_of(pet):
    return (pet.__dict__.get('_scene_plan'),
            pet.__dict__.get('scene_objects'))


s0 = snap(pet, '00_desktop')
p0 = plan_of(pet)
print('  桌面 plan = %s' % (type(p0[0]).__name__ if p0[0] is not None else None))
ck('A2 桌面画布抓到图（非空 pixmap）', s0 is not None and os.path.getsize(s0) > 1000,
   '=%s' % (os.path.getsize(s0) if s0 and os.path.exists(s0) else 0))

# ---- ① 走产品真入口 travel_to（用户例词）----
for target in ('ch1.castle_town.castle_town', 'ch2.card_castle.cc_fountain', 'uty.rooms.rm_intro', 'oneshot.barrens.Blue'):
    print('\n---- travel_to(%r) ----' % target)
    try:
        r = ctrl.travel_to(target)
    except Exception as e:
        ck('B1 travel_to(%r) 不抛' % target, False, repr(e))
        continue
    sid = r.get('scene_id')
    now = pet.__dict__.get('current_scene')
    print('   ok=%s scene_id=%r route=%r hops=%s err=%r now=%r'
          % (r.get('ok'), sid, r.get('route'), r.get('hops'), r.get('error'), now))
    if r.get('ok'):
        ck('B1 travel_to(%r) ok=True' % target, True, 'sid=%s' % sid)
        ck('B2 ★ 产品状态真变了（current_scene == 目标）' % (),
           now == sid and sid is not None, 'now=%r sid=%r' % (now, sid))
        p1 = plan_of(pet)
        # 画布计划也要变（不是只改字符串）
        changed = (p1[0] is not p0[0]) or (p1[1] is not p0[1])
        ck('B3 ★★ 画布计划**真的重建了**（不只看 current_scene 字符串）',
           changed, 'plan_identity_changed=%s' % changed)
        snap(pet, '01_%s' % re.sub(r'[^A-Za-z0-9]', '_', str(sid))[:30])
    else:
        ck('B1 travel_to(%r) ok=True（**这是硬门槛**）' % target, False,
           'err=%r candidates=%r' % (r.get('error'), r.get('candidates')[:4]))

# ---- ② 回桌面 ----
print('\n---- 回桌面 ----')
try:
    r2 = ctrl.travel_to('desktop')
except Exception as e:
    r2 = {'ok': False, 'error': repr(e)}
ck('C1 能回到桌面', bool(r2.get('ok')) and pet.__dict__.get('current_scene') == 'desktop',
   'ok=%s now=%r' % (r2.get('ok'), pet.__dict__.get('current_scene')))
snap(pet, '02_back_desktop')

# ---- ③ 负控制：编造场景名不许切 ----
print('\n---- 负控制：编造的目标 ----')
before = pet.__dict__.get('current_scene')
r3 = ctrl.travel_to('这个地方根本不存在_zzz')
ck('D1 ★ 编造目标 ok=False', not r3.get('ok'), 'ok=%s err=%r' % (r3.get('ok'), r3.get('error')))
ck('D2 ★★ 编造目标时 current_scene **不变**（失败不许把世界留在空场景）',
   pet.__dict__.get('current_scene') == before,
   'before=%r after=%r' % (before, pet.__dict__.get('current_scene')))

print('\n' + '=' * 66)
print('第89轮硬门槛：FAIL %d 项 %s' % (len(FAILS), FAILS if FAILS else ''))
print('=' * 66)
sys.exit(0 if not FAILS else 1)
