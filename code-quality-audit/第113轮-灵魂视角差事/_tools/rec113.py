# -*- coding: utf-8 -*-
"""第113轮 · 真机自检：差事闭环（§109.5「灵魂视角」的机制层）。

用户铁律：「**一定要看录像而不是只读后台输出**」「**记得录屏自检**」。

要证明的四件事（每件都必须**在真机起过的实例上**断言，不能只看纯函数单测）：
  A. **派出去的差事真的落进位置真源** —— `pet.npc_roam.resident_of(nid)` 变成目标场景。
     ★ 这就是"我（灵魂）中途进去能看到他"的**机制基础**：场景钩子按驻留表画人。
  B. **与显示解耦**（§109.5 要点 1/2）—— 整个"派出→在办→办完"过程里，
     **当前显示场景一字不变**（NPC 移动不该切我的画面）。
  C. **办完 ⇒ 撤覆盖 + 结果落进他的记忆**（要点 3「产生结果」）。
  D. **过程可观察** —— `working` 期间随时能查到"他在哪、在办什么"。

跑法（真机）：
    set QT_QPA_PLATFORM=windows && C:\\Python311\\python.exe rec113.py
（不设 QPA 时退化为离屏：状态断言照跑，PNG 数为 0 属预期。）
"""
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
_FR = os.path.join(_EV, 'frames113')
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
        b = getattr(pet, 'npc_errand', None)
        r = getattr(pet, 'npc_roam', None)
        rec['scene_id'] = pet._npc_scene_id()
        rec['board_len'] = len(b) if b is not None else None
        rec['resident_ralsei'] = (r.resident_of('ralsei') if r is not None else None)
        rec['soul_pos'] = [int(v) for v in getattr(pet, '_soul_scene_pos', ())] or None
    except Exception as e:
        rec['state_err'] = str(e)
    _SNAPS.append(rec)
    print(u'   [snap] %-22s scene=%s resident=%s board=%s png=%s'
          % (tag, rec.get('scene_id'), rec.get('resident_ralsei'),
             rec.get('board_len'), os.path.basename(rec['png']) if rec['png'] else u'(离屏无帧)'))
    return rec


# ===========================================================================
sec(u'A. 真机起实例')
try:
    import main as _M
    pet = _M.RalseiPet()
    _box['pet'] = pet
except Exception as e:
    import traceback
    traceback.print_exc()
    print(u'[FATAL] 起实例失败: %s' % e)
    sys.exit(3)

ok(u'A1 实例起来了', pet is not None)
board = getattr(pet, 'npc_errand', None)
roam = getattr(pet, 'npc_roam', None)
ok(u'A2 差事看板就位', board is not None)
ok(u'A3 驻留表就位（差事落地的地方）', roam is not None)
ok(u'A4 ★ 开局看板为空（没派过 ⇒ 零行为变化）',
   board is not None and len(board) == 0, u'len=%s' % (len(board) if board else None))
ok(u'A5 开关默认开', bool(_M.RalseiPet.NPC_ERRAND_ENABLED))

_snap(u'k000_boot', u'起实例后（未派差事）')

# ===========================================================================
sec(u'B. 派差事 ⇒ 位置真源真的变（A/C 两件）')
_NID = u'ralsei'
_DEST = u'oneshot.mainline.INIT'
_WHAT = u'去车厢取一封信'
_now = time.time()

_scene_before = pet._npc_scene_id()
ok(u'B0 记录"我的显示场景"（用于证明下面**不切显示**）', isinstance(_scene_before, str) or _scene_before is None,
   u'scene=%s' % (_scene_before,))

# ★★ 关键（本轮真机踩到）：`roam` 里**本来就可能**有他的驻留覆盖 —— 那是
#   `E:\RalseiMemory\npc_life.json` 读回的**自主挪窝结果**（NPC 独立于我看不看、
#   持续生活）。⇒ 断言"traveling 期 resident 必为 None"是**错误假设**，
#   会把既有的正确行为误判成 bug。正确判据 = **没被差事改写**。
_r_prior = roam.resident_of(_NID) if roam is not None else None
_e = pet.assign_errand(_NID, _DEST, _WHAT, travel=2.0, work=4.0, now=_now)
ok(u'B1 ★ assign_errand 派成功（任意角色都能被派）', _e is not None)
ok(u'B2 立刻 = traveling', _e is not None and _e.status == u'traveling')
ok(u'B3 ★★ traveling 期**位置真源没被差事改写**（"在路上" ≠ "已到达"）',
   roam is not None and roam.resident_of(_NID) == _r_prior,
   u'%s -> %s（目标 %s）' % (_r_prior, roam.resident_of(_NID) if roam else None, _DEST))
_snap(u'k001_traveling', u'刚派出（在路上）')

# ---- 推进到"到达" ----
pet._npc_errand_tick(_now + 2.5)
ok(u'B4 ★★★ 到达 ⇒ 位置真源变成目标场景（"我进场能看到他"的机制基础）',
   roam is not None and roam.resident_of(_NID) == _DEST,
   u'resident=%s' % (roam.resident_of(_NID) if roam else None))
ok(u'B5 ★★ 与显示解耦：**我的当前场景一字不变**（NPC 移动不切我的画面）',
   pet._npc_scene_id() == _scene_before,
   u'%s -> %s' % (_scene_before, pet._npc_scene_id()))
ok(u'B6 ★ 过程可观察：working 期间查得到"他在哪、在办什么"',
   board is not None and (board.working_positions() == [(_NID, _DEST)])
   and (board.working_of(_NID) is not None)
   and (board.working_of(_NID).what == _WHAT),
   u'pos=%s' % (board.working_positions() if board else None))
_snap(u'k002_working', u'已到达、正在办事')

# ---- ★★★ 最直观的一条：**"我中途进去"到底能不能看到他？** ----
#   `_npc_seed_bodies(scene)` 按**驻留表**为指定场景重建 NPC 身体 —— 所以只要
#   在**目标场景**里 seed 一次，`ralsei` 出现在结果里，就等价于"我一进场就会
#   看到他在那办事"（场景钩子在真切换时做的就是这件事）。
_n_other = pet._npc_seed_bodies(_DEST)
_bodies = getattr(pet, 'npc_bodies', None) or {}
_in_other = (_NID in _bodies)
pet._npc_seed_bodies(_scene_before)   # ★ 复原：刚才把当前场景的身体表覆盖了
ok(u'B6b ★★★ 「我中途进去能看到过程」：按驻留表在**目标场景**重建身体 ⇒ 他在里面',
   _in_other, u'%s 场景 %d 个 NPC，含 %s=%s' % (_DEST, _n_other, _NID, _in_other))

# ---- 再推一拍（确认稳定，不抖） ----
pet._npc_errand_tick(_now + 3.0)
ok(u'B7 在办期间**重复推进不改变状态**（幂等；他在那儿待着）',
   roam is not None and roam.resident_of(_NID) == _DEST
   and board is not None and board.working_of(_NID) is not None)

# ===========================================================================
sec(u'C. 办完 ⇒ 撤覆盖 + 结果落记忆（要点 3）')
_before_hist = len(getattr(pet, 'npc_memory', None).history(_NID)) if getattr(pet, 'npc_memory', None) else 0
pet._npc_errand_tick(_now + 7.0)
ok(u'C1 ★★ 办完 ⇒ **撤覆盖**（回落静态归属 = 回家）',
   roam is not None and roam.resident_of(_NID) is None,
   u'resident=%s' % (roam.resident_of(_NID) if roam else None))
ok(u'C2 ★ 看板释放（不再占用）', board is not None and len(board) == 0)
ok(u'C3 ★★ 与显示解耦（办完也没切我的画面）', pet._npc_scene_id() == _scene_before)

mem = getattr(pet, 'npc_memory', None)
_hist = mem.history(_NID) if mem is not None else []
_after_hist = len(_hist)
_has_result = any((u'办完' in (it.get('text') or '')) for it in _hist if isinstance(it, dict))
ok(u'C4 ★★★ 结果**落进他的记忆**（"产生结果" + "我下次能观察到"）',
   mem is not None and _after_hist > _before_hist and _has_result,
   u'hist %d -> %d  命中结果=%s' % (_before_hist, _after_hist, _has_result))
_snap(u'k003_done', u'办完了（已撤覆盖 + 结果进记忆）')

# ===========================================================================
sec(u'D. 反例：**不派**就什么都不发生（零回归）')
_scene_d = pet._npc_scene_id()
_r_before = roam.resident_of(u'kris') if roam is not None else None
pet._npc_errand_tick(time.time() + 100.0)
ok(u'D1 ★ 没人被派 ⇒ 驻留表里的**他人**一字不动',
   roam is not None and roam.resident_of(u'kris') == _r_before)
ok(u'D2 ★ 没人被派 ⇒ 显示场景一字不动', pet._npc_scene_id() == _scene_d)

# ===========================================================================
sec(u'E. 收尾')
try:
    pet.close()
except Exception:
    pass

_report = {
    'round': 113, 'is_real': IS_REAL, 'pass': _N['p'], 'fail': _N['f'],
    'scene_before': _scene_before, 'dest': _DEST, 'npc': _NID,
    'snaps': _SNAPS, 'lines': _OUT,
}
_rp = os.path.join(_EV, 'rec113_report.json')
with open(_rp, 'w', encoding='utf-8') as fh:
    json.dump(_report, fh, ensure_ascii=False, indent=1)
print(u'\n---- rec113：%d PASS / %d FAIL  真机=%s  PNG=%d ----'
      % (_N['p'], _N['f'], IS_REAL, len([s for s in _SNAPS if s.get('png')])))
print(u'报告 = %s' % _rp)
sys.exit(1 if _N['f'] else 0)
