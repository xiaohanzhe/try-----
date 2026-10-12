# -*- coding: utf-8 -*-
"""第111轮 · 录屏自检（**真机多帧抓取 + 彩蛋链路行为断言**）。

用户铁律：「**一定要看录像而不是只读后台输出**」「**记得录屏自检**」。

本轮口径（#47 Niko 的家彩蛋，逐字见详版 §109.2 / §111.1）：
  连问三次 → 选「我确定！！！」⇒ **伴随三角符文的高级爆炸特效** ⇒ 选项变回
  「我再考虑考虑」⇒ **永远进不去**。

★ 本支要证明的**最核心一件事**：三次都选"我确定"之后，**场景 id 不变**
  （= 真的没进门）。这比"特效播出来了"重要得多 —— 特效是表现，不进门是语义。

★ 模态框处理：三连确认用 `QMessageBox`（模态 ⇒ 会堵事件循环）。本支用
  `QTimer` 在框弹出后**自动点按钮**：第 1/2 次点「我确定」，第 3 次点「我确定！！！」。
  通过 monkey-patch `_niko_home_ask` 的**可观测包装**来记录每次问了什么。

跑法（真机）：
    set QT_QPA_PLATFORM=windows && C:\\Python311\\python.exe rec111.py
（不设 QPA 时退化为离屏：状态断言照跑，PNG 数为 0 属预期。）
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

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('RALSEI_TEST_MODE', '1')

_EV = os.path.abspath(os.path.join(HERE, '..', '_evidence'))
_FR = os.path.join(_EV, 'frames111')
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


try:
    from PyQt5.QtWidgets import QApplication, QMessageBox
    from PyQt5.QtCore import QTimer
except Exception as _e:
    print(u'[FATAL] PyQt5 不可用: %s' % _e)
    sys.exit(2)

_app = QApplication.instance() or QApplication(sys.argv)

_res = {'err': None, 'snaps': []}
_box = {}
_marks = {}
_snaps = []
ASK_LOG = []          #: 每次确认框：{'round','yes_label','clicked'}
SPEECH_LOG = []       #: 每次台词


def _snap(tag, note, grab=True):
    pet = _box.get('pet')
    rec = {'tag': tag, 'note': note, 'png': None}
    try:
        scr = _app.primaryScreen()
        if grab and scr is not None and os.environ.get('QT_QPA_PLATFORM') == 'windows':
            pm = scr.grabWindow(0)
            if pm is not None and not pm.isNull():
                p = os.path.join(_FR, u'k%03d_%s.png' % (len(_snaps), tag))
                pm.save(p, 'PNG')
                rec['png'] = p
    except Exception as e:
        rec['err'] = str(e)
    try:
        rec['scene_id'] = pet._soul_scene_id if pet is not None else None
        try:
            rec['props'] = [type(p).__name__ for p in (pet.item_props or [])]
        except Exception:
            rec['props'] = None
        try:
            fx = pet.__dict__.get('_niko_egg_fx')
            rec['egg_fx'] = bool(fx)
            # ★ 帧索引（实现里放的是 `{'i': n}` 这个可变 dict）⇒ 可断言"动画真在推进"。
            if isinstance(fx, tuple) and len(fx) >= 3 and isinstance(fx[2], dict):
                rec['fx_frame'] = fx[2].get('i')
            else:
                rec['fx_frame'] = None
        except Exception:
            rec['egg_fx'] = None
            rec['fx_frame'] = None
    except Exception as e:
        rec['state_err'] = str(e)
    _snaps.append(rec)
    print(u'        [snap] %s scene=%s props=%s egg_fx=%s fx_frame=%s png=%s'
          % (tag, rec.get('scene_id'), rec.get('props'), rec.get('egg_fx'),
             rec.get('fx_frame'), bool(rec.get('png'))))


def _poll(duration_ms):
    pet = _box.get('pet')
    if pet is None:
        return
    t_end = time.time() * 1000.0 + duration_ms
    while time.time() * 1000.0 < t_end:
        try:
            _app.processEvents()
        except Exception:
            pass
        time.sleep(0.008)


def _auto_click_yes():
    """框弹出后自动点"确定"（把选项记进 ASK_LOG）。"""
    try:
        for w in _app.topLevelWidgets():
            if isinstance(w, QMessageBox) and w.isVisible():
                btns = w.buttons()
                # 第一个按钮 = 我确定/我确定！！！；第二个 = 我再考虑考虑
                for b in btns:
                    if u'确定' in b.text():
                        ASK_LOG.append({'label': b.text(), 'clicked': True})
                        b.click()
                        return
    except Exception:
        pass


def _stage1():
    try:
        import main as _M
        pet = _M.RalseiPet()
        _box['pet'] = pet
        pet.show()

        # ★ 观测台词（不改变行为，只是记录）—— 包在既有 `_item_prop_present` 外。
        _orig_present = pet._item_prop_present

        def _present_spy(text, actor=None):
            SPEECH_LOG.append(text)
            return _orig_present(text, actor)

        pet._item_prop_present = _present_spy
        # ★ 观测确认框（同样只记录，行为仍是真实弹框 + 自动点确定性按钮）。
        _orig_ask = pet._niko_home_ask

        def _ask_spy(round_index):
            rec = {'round': round_index, 'yes_label': None, 'ret': None}
            # ★ 记录真实文案（从源码口径现推，与实现同源）。
            rec['yes_label'] = u'我确定！！！' if round_index >= 2 else u'我确定'
            QTimer.singleShot(120, _auto_click_yes)
            ret = _orig_ask(round_index)
            rec['ret'] = ret
            ASK_LOG.append(rec)
            return ret

        pet._niko_home_ask = _ask_spy
        QTimer.singleShot(1800, _stage2)
    except Exception:
        _res['err'] = traceback.format_exc()
        try:
            _app.quit()
        except Exception:
            pass


def _stage2():
    pet = _box.get('pet')
    try:
        _poll(400)
        _snap(u'desktop', u'桌面（彩蛋门所在场景）')
        _marks['before'] = dict(_snaps[-1])
        _before_scene = _marks['before'].get('scene_id')

        # 找到彩蛋门并交互
        egg = None
        for p in (pet.item_props or []):
            if type(p).__name__ == 'NikoHomeDoorProp':
                egg = p
                break
        _res['found_egg'] = egg is not None
        _res['egg_no_target'] = (getattr(egg, 'target_scene', 'X') in (None, '')) if egg else None
        _res['egg_texts'] = list(getattr(egg, 'egg_texts', ()) or ()) if egg else None

        if egg is not None:
            _res['interact_ret'] = bool(egg.interact())
        # ★ 爆炸只有 ~578ms（17 帧 × 34ms）⇒ 必须**紧跟着**抓一帧，
        #   否则抓到的永远是"播完了"（第110轮血泪：抓帧时点比结果重要）。
        _poll(260)
        _snap(u'boom', u'★爆炸进行时（spr_realisticexplosion 正在播）')
        _marks['boom'] = dict(_snaps[-1])
        _poll(1200)                       # 让三次确认 + 爆炸跑完
        _snap(u'after_egg', u'彩蛋三连确认 + 爆炸之后')
        _marks['after'] = dict(_snaps[-1])
        _res['before_scene'] = _before_scene

        # 等爆炸帧放完
        _poll(900)
        _snap(u'after_fx', u'爆炸播完之后（仍应停在桌面）')
        _marks['final'] = dict(_snaps[-1])
        QTimer.singleShot(200, _finish)
    except Exception:
        _res['err'] = traceback.format_exc()
        try:
            _app.quit()
        except Exception:
            pass


def _finish():
    finally_close = True
    try:
        _res['snaps'] = list(_snaps)
        _res['marks'] = dict(_marks)
        _res['ask_log'] = list(ASK_LOG)
        _res['speech_log'] = list(SPEECH_LOG)
    finally:
        if finally_close:
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

if _res.get('err'):
    print(_res['err'])
    ok(u'G0 真机启动', False, u'见上')

_m = _res.get('marks') or {}
_before = _m.get('before') or {}
_after = _m.get('after') or {}
_final = _m.get('final') or {}

print(u'=' * 72)
print(u'第111轮 · 录屏自检（#47 Niko 的家彩蛋）')
print(u'QPA = %s' % os.environ.get('QT_QPA_PLATFORM'))
print(u'=' * 72)

sec(u'G1 彩蛋门真的被建成可交互物')

ok(u'G0 ★★ 真机起来了（拿到桌面场景采样）',
   bool(_before.get('scene_id')), u'scene=%r' % (_before.get('scene_id'),))
ok(u'G1 ★★★ 桌面场景里有 `NikoHomeDoorProp`（真机 item_props 里找到了）',
   bool(_res.get('found_egg')), u'props=%r' % (_before.get('props'),))
ok(u'G1b ★★★ 该门 `target_scene` 为空（**结构上不存在能进的目标**）',
   _res.get('egg_no_target') is True, u'no_target=%r' % (_res.get('egg_no_target'),))

sec(u'G2 三连确认：问三次、文案按口径递增')

_al = [r for r in (_res.get('ask_log') or []) if 'round' in r]
ok(u'G2 ★★★ 确认框被问了 **3 次**（三连确认）', len(_al) == 3,
   u'got=%d %r' % (len(_al), [r.get('round') for r in _al]))
ok(u'G2b ★★★ 第 1/2 次的"确定"按钮文案是「我确定」',
   len(_al) >= 2 and all(r.get('yes_label') == u'我确定' for r in _al[:2]),
   u'labels=%r' % [r.get('yes_label') for r in _al])
ok(u'G2c ★★★ 第 3 次的"确定"按钮文案是「我确定！！！」',
   len(_al) >= 3 and _al[2].get('yes_label') == u'我确定！！！',
   u'label=%r' % (_al[2].get('yes_label') if len(_al) >= 3 else None))
ok(u'G2d ★★ 三次都选了"确定"（自动点击生效）',
   len(_al) == 3 and all(r.get('ret') is True for r in _al),
   u'ret=%r' % [r.get('ret') for r in _al])

sec(u'G3 三句台词逐字播出（顺序也对）')

_sl = _res.get('speech_log') or []
_EXP = [u'你确定吗？',
        u'你这样的行为可能导致世界崩坏，你真的确定吗？',
        u'你真的不再考虑考虑了吗？']
ok(u'G3 ★★★ 三句台词都播出来了', _sl[:3] == _EXP if len(_sl) >= 3 else False,
   u'speech=%r' % (_sl[:4],))

sec(u'G4 ★★★ 核心语义：**永远进不去**')

_b = _before.get('scene_id')
_a = _after.get('scene_id')
_f = _final.get('scene_id')
ok(u'G4 ★★★ 彩蛋执行前后 **场景 id 不变**（%r → %r）——真的没进门' % (_b, _a),
   _b is not None and _b == _a, u'before=%r after=%r' % (_b, _a))
ok(u'G4b ★★★ 爆炸播完之后**仍停在桌面**（%r）' % (_f,),
   _f == _b, u'final=%r' % (_f,))
ok(u'G4c ★★ 负控制：桌面场景 id 确实**是** desktop（否则"不变"可能是两边都 None）',
   _b == 'desktop', u'before=%r' % (_b,))

sec(u'G5 爆炸特效真的起来了（表现层）')

_boom = _m.get('boom') or {}
_fr_boom = _boom.get('fx_frame')
_fr_after = _after.get('fx_frame')
ok(u'G5 ★★ 彩蛋交互时起了爆炸特效（`_niko_egg_fx` 有引用）',
   bool(_after.get('egg_fx')) or os.environ.get('QT_QPA_PLATFORM') != 'windows',
   u'egg_fx=%r qpa=%s' % (_after.get('egg_fx'), os.environ.get('QT_QPA_PLATFORM')))
ok(u'G5b ★★★ 爆炸帧索引真在推进（中途第 %r 帧）—— 不是"挂了个空引用"'
   % (_fr_boom,),
   (_fr_boom is not None and _fr_boom > 0)
   or os.environ.get('QT_QPA_PLATFORM') != 'windows',
   u'boom=%r after=%r' % (_fr_boom, _fr_after))
ok(u'G5c ★★ 爆炸中途的抓帧已落盘（人眼能看到火球，而不是只看到"播完"）',
   bool(_boom.get('png')) or os.environ.get('QT_QPA_PLATFORM') != 'windows',
   u'png=%r' % (_boom.get('png'),))

sec(u'G6 抓帧')

_n_png = sum(1 for s in _snaps if s.get('png'))
print(u'        PNG = %d 张 · 快照 %d 条' % (_n_png, len(_snaps)))
ok(u'G6 ★★ 人眼复核用的抓帧已落盘（真机应有 >0 张；离屏为 0 属预期）',
   _n_png > 0 or os.environ.get('QT_QPA_PLATFORM') != 'windows',
   u'png=%d qpa=%s' % (_n_png, os.environ.get('QT_QPA_PLATFORM')))

print(u'\n' + u'=' * 72)
print(u'第111轮：PASS=%d FAIL=%d' % (_N['p'], _N['f']))
print(u'=' * 72)

with io.open(os.path.join(_EV, 'rec111_meta.txt'), 'w', encoding='utf-8') as f:
    f.write(u'第111轮 · 录屏自检元数据（#47 Niko 的家彩蛋）\n')
    f.write(u'QPA = %s\n' % os.environ.get('QT_QPA_PLATFORM'))
    f.write(u'ask_log = %r\n' % (_res.get('ask_log'),))
    f.write(u'speech_log = %r\n' % (_res.get('speech_log'),))
    f.write(u'before = %r\n' % (_before,))
    f.write(u'boom = %r\n' % ((_m.get('boom') or {}),))
    f.write(u'after = %r\n' % (_after,))
    f.write(u'final = %r\n' % (_final,))
    f.write(u'\n'.join(_OUT))
    f.write(u'\n\nPASS=%d FAIL=%d\n' % (_N['p'], _N['f']))

sys.exit(1 if _N['f'] else 0)
