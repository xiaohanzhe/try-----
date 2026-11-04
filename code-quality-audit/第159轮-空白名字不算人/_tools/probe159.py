# -*- coding: utf-8 -*-
u"""第159轮探针：**空白名字不该算一个人**。

用法：
    python probe159.py --before   # 改前基线（断言"进得去"）
    python probe159.py            # 改后（断言"拒掉了"）

## 量什么

| # | 输入 | 改前 | 改后 |
|---|---|---|---|
| P1 | `assign_errand('   ', …)` | 造出 1 条"看不见的人"的在办 | `None`，0 条 |
| P2 | `' ralsei '` 再 `'ralsei'` | **两个槽**（同一人两条在办） | 空格那个被拒 ⇒ 1 槽 |
| P3 | `assign_errand('ralsei', '   ', …)` | 进得去（会去压一个不存在的场景） | `None` |
| P4 | `what='   '` | 原样存 `'   '`（显示"办「   」"） | 归一成 `''`（= 走一趟），**仍派成** |
| P5 | 老档里有空白 id 的条目 | 读回 1 条（幽灵复活） | 丢弃那一条（**同档正常条目不受影响**） |
| P6 | 正常 `('ralsei', dest, '擦柜台')` | 成功（正控制） | 成功 |

★ 纪律：临时文件只落系统 temp（用完即删）；零网络 / 零 UI / 零显示器；
  时间基准一律用 `_time.time()`（从 0 起算会被 TTL 当陈年旧账，第156轮踩过）。
"""
import io
import json
import os
import shutil
import sys
import tempfile
import time as _time

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(ROOT, 'ralsei_pet')

for _p in (PKG, os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from main import RalseiPet                                  # noqa: E402
from modules import npc_errand as ER                        # noqa: E402
from modules import npc_system as NS                        # noqa: E402

BEFORE = '--before' in sys.argv

_DEST = 'oneshot.barrens.Blue'
_WHAT = u'\u64e6\u67dc\u53f0'          # 擦柜台
_SPACE = u'   '

_n_pass = 0
_n_fail = 0


def ok(desc, cond, detail=''):
    global _n_pass, _n_fail
    if cond:
        _n_pass += 1
        print(u'[PASS] %s%s' % (desc, (u'    ' + detail) if detail else u''))
    else:
        _n_fail += 1
        print(u'[FAIL] %s%s' % (desc, (u'    ' + detail) if detail else u''))


class _Mem(object):
    def __init__(self):
        self.log = []

    def remember(self, nid, text, who=None, **kw):
        self.log.append((nid, text, who))

    def save(self, nid):
        pass


class _Roam(object):
    def get(self, nid):
        return None

    def put(self, *a, **k):
        pass

    def drop(self, *a, **k):
        pass


class _Host(object):
    u"""轻宿主：门控**故意放行**（本轮量的是参数校验，不是门控那条闸）。"""

    _npc_errand_note = RalseiPet._npc_errand_note
    assign_errand = RalseiPet.assign_errand
    _npc_errand_load = RalseiPet._npc_errand_load
    _npc_errand_tick = RalseiPet._npc_errand_tick
    _npc_errand_commit = RalseiPet._npc_errand_commit

    def __init__(self, path):
        self._path = path
        self.npc_registry = NS.load_registry()
        self.npc_memory = _Mem()
        self.npc_roam = _Roam()
        self._npc_talking = 'ralsei'
        self._errand_given_up = {}
        self._npc_errand_last_save = 0.0
        self.saves = []
        _er = self._npc_errand_load()
        self.npc_errand = _er if _er is not None else ER.ErrandBoard()

    def _npc_errand_file(self):
        return self._path

    def _npc_errand_save(self, force=False):
        self.saves.append(bool(force))
        return RalseiPet._npc_errand_save(self, force)

    def _npc_errand_gate(self, npc_id, dest):
        return (True, u'')

    def _npc_seed_bodies(self, scene_id=None):
        pass

    def _npc_scene_id(self):
        return 'ch1.hometown.town_mid'

    def _npc_plan_save(self, force=False):
        return True

    def _errand_report_ack(self, *a, **kw):
        return None

    def npc_label(self, npc_id):
        return (npc_id or u'').strip()


_tmp = tempfile.mkdtemp(prefix='probe159_')
_T = _time.time()

try:
    print(u'== 改前基线 ==' if BEFORE else u'== 改后 ==')

    # ------------------------------------------------ P1 纯空格 npc_id
    _h1 = _Host(os.path.join(_tmp, 'p1.json'))
    _e1 = _h1.assign_errand(_SPACE, _DEST, _WHAT, now=_T)
    _n1 = len(_h1.npc_errand)
    print(u'P1 assign_errand("   ") -> %r，在办 %d 条' % (_e1, _n1))
    if BEFORE:
        ok(u'P1 ★★★ 改前：纯空格也算一个人 ⇒ 造出"看不见的人"的在办条目',
           _e1 is not None and _n1 == 1, u'在办=%d' % (_n1,))
    else:
        ok(u'P1 ★★★ 纯空格名字**直接拒**（返 `None`，看板不动）',
           _e1 is None and _n1 == 0, u'在办=%d' % (_n1,))

    # ------------------------------------------------ P2 ' ralsei ' 与 'ralsei' 是不是同一个人
    _p2 = os.path.join(_tmp, 'p2.json')
    _h2 = _Host(_p2)
    _a2 = _h2.assign_errand(u' ralsei ', _DEST, _WHAT, now=_T)
    _b2 = _h2.assign_errand('ralsei', _DEST, u'\u6536\u676f\u5b50', now=_T + 1)
    _keys2 = list(_h2.npc_errand._active.keys())
    print(u'P2 " ralsei " 再 "ralsei" ⇒ 槽位 %r' % (_keys2,))
    if BEFORE:
        ok(u'P2 ★★★ 改前：**同一个人占两个槽**（名额虚耗 + 旧那条永远留在外面）',
           len(_keys2) == 2 and u' ralsei ' in _keys2, u'槽=%d' % (len(_keys2),))
    else:
        ok(u'P2 ★★★ 带前后空格的 id **同样拒** ⇒ 一个人只有一个槽',
           _a2 is None and _b2 is not None and _keys2 == ['ralsei'],
           u'槽=%r' % (_keys2,))

    # ------------------------------------------------ P3 空白 dest_scene
    _h3 = _Host(os.path.join(_tmp, 'p3.json'))
    _e3 = _h3.assign_errand('ralsei', _SPACE, _WHAT, now=_T)
    print(u'P3 assign_errand(dest="   ") -> %r' % (_e3,))
    if BEFORE:
        ok(u'P3 ★★ 改前：空白地点也进得去（会去压一个不存在的场景）',
           _e3 is not None, u'在办=%d' % (len(_h3.npc_errand),))
    else:
        ok(u'P3 ★★ 空白地点**直接拒**（返 `None`）',
           _e3 is None and len(_h3.npc_errand) == 0,
           u'在办=%d' % (len(_h3.npc_errand),))

    # ------------------------------------------------ P4 空白 what（设计上允许空 = 走一趟）
    _h4 = _Host(os.path.join(_tmp, 'p4.json'))
    _e4 = _h4.assign_errand('ralsei', _DEST, _SPACE, now=_T)
    _w4 = getattr(_e4, 'what', None)
    print(u'P4 assign_errand(what="   ") -> %r，what 存的是 %r' % (_e4, _w4))
    if BEFORE:
        ok(u'P4 ★ 改前：空白事由原样存下（界面上显示"办「   」"）',
           _e4 is not None and _w4 == _SPACE, u'what=%r' % (_w4,))
    else:
        ok(u'P4 ★ 空白事由**归一成空串**（= 走一趟），但活**照样派成**',
           _e4 is not None and _w4 == u'', u'what=%r' % (_w4,))

    # ------------------------------------------------ P5 老档里的幽灵条目
    _p5 = os.path.join(_tmp, 'p5.json')
    _seed = {
        'enabled': True,
        'active': [
            {'npc_id': _SPACE, 'dest_scene': _DEST, 'what': _WHAT,
             'start': _T, 'arrive_at': _T + 90, 'finish_at': _T + 390,
             'status': 'traveling', 'result': '', 'custom_result': ''},
            {'npc_id': 'ralsei', 'dest_scene': _DEST, 'what': _WHAT,
             'start': _T, 'arrive_at': _T + 90, 'finish_at': _T + 390,
             'status': 'traveling', 'result': '', 'custom_result': ''},
        ],
        'done': [],
    }
    with io.open(_p5, 'w', encoding='utf-8') as _f:
        _f.write(json.dumps(_seed, ensure_ascii=False))
    _h5 = _Host(_p5)
    _keys5 = list(_h5.npc_errand._active.keys())
    print(u'P5 老档（一条空白 + 一条正常）读回槽位 %r' % (_keys5,))
    if BEFORE:
        ok(u'P5 ★★ 改前：幽灵条目**照读不误**（重启后那个"人"又出门了）',
           _SPACE in _keys5 and len(_keys5) == 2, u'槽=%r' % (_keys5,))
    else:
        ok(u'P5 ★★ 老档里的幽灵条目被**丢掉**，同档的正常条目**照常读回**（正控制）',
           _keys5 == ['ralsei'], u'槽=%r' % (_keys5,))

    # ------------------------------------------------ P6 正控制：正常输入照常
    _h6 = _Host(os.path.join(_tmp, 'p6.json'))
    _e6 = _h6.assign_errand('ralsei', _DEST, _WHAT, now=_T)
    ok(u'P6 正控制：正常 `("ralsei", 场景, 事由)` 照常派成（不是"一刀切全拒"）',
       _e6 is not None and len(_h6.npc_errand) == 1,
       u'在办=%d' % (len(_h6.npc_errand),))
finally:
    try:
        shutil.rmtree(_tmp, ignore_errors=True)
    except Exception:
        pass

print(u'')
if _n_fail:
    print(u'probe159（%s）：FAIL %d / PASS %d'
          % (u'改前基线' if BEFORE else u'改后', _n_fail, _n_pass))
    sys.exit(1)
print(u'probe159（%s）：%d 项全过' % (u'改前基线' if BEFORE else u'改后', _n_pass))
sys.exit(0)
