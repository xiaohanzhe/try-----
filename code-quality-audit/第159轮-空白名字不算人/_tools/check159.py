# -*- coding: utf-8 -*-
u"""第159轮回归锁：**空白名字不算一个人**。

## 为什么（第150~153轮一路结转的那条「纯空格 `npc_id` 不拒」）

改前实测（`probe159 --before`，6/6 全过）：

| # | 输入 | 改前 |
|---|---|---|
| P1 | `assign_errand('   ', …)` | 造出 1 条"看不见的人"的在办（会写盘、会进 prompt、`working_positions()` 每拍压位置） |
| P2 | `' ralsei '` 再 `'ralsei'` | **两个槽**（同一人两条在办 · 名额虚耗 · 旧那条永远留在外面） |
| P3 | `assign_errand('ralsei', '   ', …)` | 进得去（会去压一个不存在的场景） |
| P4 | `what='   '` | 原样存 `'   '`（界面显示"办「   」"） |
| P5 | 老档里有空白 id 的条目 | 读回 1 条（**重启后那个"人"又出门了**） |

⇒ 用户口径「按照人类的逻辑来就好」：名字是空的不算一个人；**带空格的也不是他**。

## 本套件守什么

| 段 | 守什么 |
|---|---|
| A | **真跑**：四种脏输入各自被拒 · 门控**没被问**（参数不是人，连问路都不该问）· 不写记忆 · 不写欠账 · **不产档** · 老档幽灵条目丢弃而正常条目照读（正控制）· 机制层两道口子（`assign` / `from_dict`）都堵 · 空白事由归一成 `''` 但活照派 |
| B | **AST**：四处判据都含"首尾空白"这一半（只挡全空白会漏 `' ralsei '`）· 宿主层那条在 `_npc_errand_gate` **之前** · 全仓**没有** `npc_id = npc_id.strip()`（宁拒不改写）· `what` 归一分支在位 |
| C | 自检：分母闸 · 判据名字面量 · 只用 `check()` · 无 BOM 全 LF · 零外部盘 |

★ 判据纪律：`print('[PASS] %s')` 字面量；断行为不断赋值；正/负控制成对；
  零网络 / 零 UI / 零显示器 / 零外部盘（临时件落系统 temp，用完即删）。
"""
import ast
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
MAIN = os.path.join(PKG, 'src', 'main.py')
ERRAND_MOD = os.path.join(PKG, 'modules', 'npc_errand.py')

for _p in (PKG, os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from main import RalseiPet                                  # noqa: E402
from modules import npc_errand as ER                        # noqa: E402
from modules import npc_system as NS                        # noqa: E402

with io.open(MAIN, 'r', encoding='utf-8', newline='') as _fh:
    SRC = _fh.read()
TREE = ast.parse(SRC)
with io.open(ERRAND_MOD, 'r', encoding='utf-8', newline='') as _fh:
    MOD_SRC = _fh.read()
MOD_TREE = ast.parse(MOD_SRC)

_n_pass = 0
_n_fail = 0
_failed = []
_marks = 0


def check(desc, cond, detail=''):
    global _n_pass, _n_fail
    if cond:
        _n_pass += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _n_fail += 1
        _failed.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


def mark(title):
    global _marks
    _marks += 1
    print('---- [判据点 %d] %s ----' % (_marks, title))


def _clsdef(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef) and n.name == name:
            return n
    return None


def _method(cls, name):
    if cls is None:
        return None
    for n in cls.body:
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


def _calls(fn, attr):
    out = []
    if fn is None:
        return out
    for c in ast.walk(fn):
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) \
                and c.func.attr == attr:
            out.append(c)
    return out


_DEST = 'oneshot.barrens.Blue'
_WHAT = u'\u64e6\u67dc\u53f0'
_SPACE = u'   '
_PAD = u' ralsei '

_T = _time.time()


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
    u"""轻宿主：**门控放行**，但记住被问了几次（本轮要断言"脏输入不问路"）。"""

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
        self.gate_asked = []
        _er = self._npc_errand_load()
        self.npc_errand = _er if _er is not None else ER.ErrandBoard()

    def _npc_errand_file(self):
        return self._path

    def _npc_errand_save(self, force=False):
        self.saves.append(bool(force))
        return RalseiPet._npc_errand_save(self, force)

    def _npc_errand_gate(self, npc_id, dest):
        self.gate_asked.append((npc_id, dest))
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


_tmp = tempfile.mkdtemp(prefix='check159_')
try:
    # ================================================ A 真跑
    mark(u'A 真跑：四种脏输入各拒 · 不问路 · 不写记忆 · 不写欠账 · 不产档')

    _p1 = os.path.join(_tmp, 'a1.json')
    _h = _Host(_p1)
    _e1 = _h.assign_errand(_SPACE, _DEST, _WHAT, now=_T)
    check(u'A1 ★★★ 纯空格 `npc_id` ⇒ 返 `None`、看板不动、**不产档**',
          _e1 is None and len(_h.npc_errand) == 0 and not os.path.isfile(_p1),
          u'返=%r 在办=%d 有档=%s' % (_e1, len(_h.npc_errand), os.path.isfile(_p1)))

    _p2 = os.path.join(_tmp, 'a2.json')
    _h = _Host(_p2)
    _e2 = _h.assign_errand(_PAD, _DEST, _WHAT, now=_T)
    _e2b = _h.assign_errand('ralsei', _DEST, _WHAT, now=_T + 1)
    check(u'A2 ★★★ 首尾带空格的 `\' ralsei \'` 同样拒 ⇒ 一个人只剩**一个槽**',
          _e2 is None and _e2b is not None
          and list(_h.npc_errand._active.keys()) == ['ralsei'],
          u'槽=%r' % (list(_h.npc_errand._active.keys()),))

    _p3 = os.path.join(_tmp, 'a3.json')
    _h = _Host(_p3)
    _e3 = _h.assign_errand('ralsei', _SPACE, _WHAT, now=_T)
    check(u'A3 ★★ 空白目的地 ⇒ 拒（不会去压一个不存在的场景）',
          _e3 is None and len(_h.npc_errand) == 0,
          u'在办=%d' % (len(_h.npc_errand),))

    _p4 = os.path.join(_tmp, 'a4.json')
    _h = _Host(_p4)
    _e4 = _h.assign_errand('ralsei', _DEST, _SPACE, now=_T)
    check(u'A4 ★ 空白事由**归一成空串**（= 走一趟），但活照派（不是连活一起拒）',
          _e4 is not None and getattr(_e4, 'what', None) == u''
          and len(_h.npc_errand) == 1,
          u'what=%r 在办=%d' % (getattr(_e4, 'what', None), len(_h.npc_errand)))

    _p5 = os.path.join(_tmp, 'a5.json')
    _h = _Host(_p5)
    _h.assign_errand(_SPACE, _DEST, _WHAT, now=_T)
    check(u'A5 ★★★ 脏输入**不问路**（门控一次都没被调）：参数不是人，不配走门控那一步',
          _h.gate_asked == [], u'被问=%d 次' % (len(_h.gate_asked),))

    _p6 = os.path.join(_tmp, 'a6.json')
    _h = _Host(_p6)
    _h.assign_errand(_SPACE, _DEST, _WHAT, now=_T)
    check(u'A6 ★★ 脏输入**不写记忆**（不会留下"我本来要去 X"这种幽灵自述）',
          _h.npc_memory.log == [], u'记忆=%d 条' % (len(_h.npc_memory.log),))

    _p7 = os.path.join(_tmp, 'a7.json')
    _h = _Host(_p7)
    _h.assign_errand(_SPACE, _DEST, _WHAT, now=_T)
    check(u'A7 ★ 脏输入**不进欠账表**（否则欠账里多一个看不见的槽）',
          not _h._errand_given_up, u'欠账=%r' % (_h._errand_given_up,))

    _p8 = os.path.join(_tmp, 'a8.json')
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
    with io.open(_p8, 'w', encoding='utf-8') as _f:
        _f.write(json.dumps(_seed, ensure_ascii=False))
    _h = _Host(_p8)
    _keys8 = list(_h.npc_errand._active.keys())
    check(u'A8 ★★★ 老档里的幽灵条目被**丢掉**，同档的正常条目**照常读回**（正控制，防一刀切）',
          _keys8 == ['ralsei'], u'槽=%r' % (_keys8,))

    _b9 = ER.ErrandBoard()
    _e9 = _b9.assign(_T, _SPACE, _DEST, _WHAT)
    check(u'A9 ★★ 机制层 `ErrandBoard.assign` 自己也拒（不靠宿主兜）',
          _e9 is None and len(_b9) == 0, u'返=%r 在办=%d' % (_e9, len(_b9)))

    _e10 = ER.Errand.from_dict({'npc_id': _SPACE, 'dest_scene': _DEST,
                                'what': _WHAT, 'start': _T, 'arrive_at': _T,
                                'finish_at': _T, 'status': 'traveling'})
    _e10b = ER.Errand.from_dict({'npc_id': 'ralsei', 'dest_scene': _DEST,
                                 'what': _WHAT, 'start': _T, 'arrive_at': _T,
                                 'finish_at': _T, 'status': 'traveling'})
    check(u'A10 ★★ `Errand.from_dict` 同样拒幽灵、**正常条目照收**（正控制）',
          _e10 is None and _e10b is not None,
          u'幽灵=%r 正常=%r' % (_e10, _e10b))

    _p11 = os.path.join(_tmp, 'a11.json')
    _h = _Host(_p11)
    _e11 = _h.assign_errand('ralsei', _DEST, _WHAT, now=_T)
    _ok11 = _h._npc_errand_save(force=True)
    _h11b = _Host(_p11)
    check(u'A11 正控制：正常输入**照常落盘、照常读回**（收紧没把正常路也收掉）',
          _e11 is not None and _ok11 is True and len(_h11b.npc_errand) == 1,
          u'在办=%d' % (len(_h11b.npc_errand),))

    _e12 = ER.ErrandBoard().assign(_T, 'ralsei', _DEST, u'\u6536\u676f\u5b50')
    check(u'A12 正控制：机制层正常事由**一字不改**（只有纯空白才归一）',
          _e12 is not None and _e12.what == u'\u6536\u676f\u5b50',
          u'what=%r' % (getattr(_e12, 'what', None),))

    _b13 = ER.ErrandBoard()
    _e13 = _b13.assign(_T, _PAD, _DEST, _WHAT)
    check(u'A13 ★★★ 机制层对**首尾空白**也拒（只挡"全空白"会漏 `\' ralsei \'`，'
          u'宿主那一层挡不住直接调机制层的调用方）',
          _e13 is None and len(_b13) == 0,
          u'返=%r 在办=%d' % (_e13, len(_b13)))

    # ================================================ B AST
    mark(u'B AST：四处判据都含"首尾空白"这一半 · 不问路 · 不改写')

    _assign_mech = _method(_clsdef(MOD_TREE, 'ErrandBoard'), 'assign')
    _from_mech = _method(_clsdef(MOD_TREE, 'Errand'), 'from_dict')
    _assign_host = _method(_clsdef(TREE, 'RalseiPet'), 'assign_errand')

    def _has_strip_guard(fn, name):
        u"""判据里出现 `name != name.strip()`（或等价的比较）就算守住。"""
        for n in ast.walk(fn or ast.Module(body=[], type_ignores=[])):
            if isinstance(n, ast.Compare):
                side = [x for x in [n.left] + list(n.comparators)
                        if isinstance(x, ast.Call)
                        and isinstance(x.func, ast.Attribute)
                        and x.func.attr == 'strip']
                other = [x for x in [n.left] + list(n.comparators)
                         if isinstance(x, ast.Name) and x.id == name]
                if side and other:
                    return True
        return False

    check(u'B1 ★★★ 机制层 `assign` 的 `npc_id` 判据含**首尾空白**那一半',
          _has_strip_guard(_assign_mech, 'npc_id'))
    check(u'B2 ★★ 机制层 `assign` 的 `dest_scene` 判据同上',
          _has_strip_guard(_assign_mech, 'dest_scene'))
    check(u'B3 ★★ `Errand.from_dict` 的两条判据也含首尾空白（老档幽灵才挡得住）',
          _has_strip_guard(_from_mech, 'npc_id')
          and _has_strip_guard(_from_mech, 'dest_scene'))
    check(u'B4 ★★★ 宿主层 `assign_errand` 的两条判据同样含首尾空白',
          _has_strip_guard(_assign_host, 'npc_id')
          and _has_strip_guard(_assign_host, 'dest_scene'))

    _gate_calls = _calls(_assign_host, '_npc_errand_gate')
    _bad_checks = []
    for n in ast.walk(_assign_host or ast.Module(body=[], type_ignores=[])):
        if isinstance(n, ast.If):
            _t = ast.dump(n.test)
            if 'strip' in _t and _gate_calls and n.lineno < _gate_calls[0].lineno:
                _bad_checks.append(n.lineno)
    check(u'B5 ★★★ 宿主层那两道闸排在 `_npc_errand_gate` **之前**（脏参数不问路）',
          len(_bad_checks) == 2 and len(_gate_calls) == 1,
          u'前置判据=%d 门控调用=%d' % (len(_bad_checks), len(_gate_calls)))

    _rewrites = []
    for _tree in (TREE, MOD_TREE):
        for n in ast.walk(_tree):
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Name) and t.id in ('npc_id', 'dest_scene'):
                        if isinstance(n.value, ast.Call) \
                                and isinstance(n.value.func, ast.Attribute) \
                                and n.value.func.attr == 'strip':
                            _rewrites.append(n.lineno)
    check(u'B6 ★★ 全仓**没有** `npc_id = npc_id.strip()` 这种"静默改写"（宁拒不改写）',
          not _rewrites, u'命中=%d 处' % (len(_rewrites),))

    _what_norm = False
    for n in ast.walk(_assign_mech or ast.Module(body=[], type_ignores=[])):
        if isinstance(n, ast.If):
            _d = ast.dump(n.test)
            if 'what' in _d and 'strip' in _d:
                for s in ast.walk(n):
                    if isinstance(s, ast.Assign) \
                            and isinstance(s.value, ast.Constant) \
                            and s.value.value == '':
                        _what_norm = True
    check(u'B7 ★ 空白事由的**归一分支**在位（`what = \'\'`，不是原样存 `\'   \'`）',
          _what_norm)

    # ★★★ 第160轮补 B8：「两半都在」这条**不许绑写法**。
    #   第159轮只有 recheck 里查过"同一个 if 里两半"，而那种写法一拆段就假红
    #   （`probe160 --before` 实测）。补进回归锁，并把口径定成"同函数内两半都在"。
    def _has_not_guard(fn, name):
        u"""判据里出现 `not name`（挡空串那一半）就算守住 —— 不问它跟 strip 比较是不是同一个 if。"""
        for n in ast.walk(fn or ast.Module(body=[], type_ignores=[])):
            if isinstance(n, ast.If):
                for x in ast.walk(n.test):
                    if isinstance(x, ast.UnaryOp) and isinstance(x.op, ast.Not) \
                            and isinstance(x.operand, ast.Name) \
                            and x.operand.id == name:
                        return True
        return False

    _given_up = None
    for _n in TREE.body:
        if isinstance(_n, ast.FunctionDef) and _n.name == '_errand_given_up_add':
            _given_up = _n
    _pairs8 = ((_assign_host, 'npc_id'), (_assign_host, 'dest_scene'),
               (_assign_mech, 'npc_id'), (_assign_mech, 'dest_scene'),
               (_from_mech, 'npc_id'), (_from_mech, 'dest_scene'),
               (_given_up, 'npc_id'))
    _bad8 = [nm for fn, nm in _pairs8
             if not (_has_strip_guard(fn, nm) and _has_not_guard(fn, nm))]
    check(u'B8 ★★★ 七处判据**两半都在**（挡空串 + 挡首尾空白），且**不要求写在同一个 `if` 里**'
          u'（绑写法会把语义等价的改写判成破坏）',
          not _bad8, u'缺一半=%r 覆盖=%d 对' % (_bad8, len(_pairs8)))

    # ================================================ C 自检
    mark(u'C 自检：分母闸 · 字面量 · 只用 check() · 编码 · 零外部盘')

    with io.open(os.path.abspath(__file__), 'r', encoding='utf-8',
                 newline='') as _sf:
        SELF = _sf.read()
    SELF_TREE = ast.parse(SELF)

    _bad_names = []
    _n_check = 0
    for n in ast.walk(SELF_TREE):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                and n.func.id == 'check':
            _n_check += 1
            if not n.args or not isinstance(n.args[0], ast.Constant) \
                    or not isinstance(n.args[0].value, str) \
                    or not n.args[0].value.strip():
                _bad_names.append(getattr(n, 'lineno', -1))
    check(u'C0 分母闸：本文件里 `check(` 调用**非空**', _n_check > 0,
          u'处数=%d' % (_n_check,))
    check(u'C1 每条判据的说明都是**非空字面量**（不是变量、不是空串）',
          not _bad_names and _n_check >= 26,
          u'坏的=%d 条数=%d' % (len(_bad_names), _n_check))

    _n_ok = 0
    for n in ast.walk(SELF_TREE):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                and n.func.id == 'ok':
            _n_ok += 1
    check(u'C2 只用 `check()`，不用 `ok()`（两套 harness 混用 ⇒ 查恒真会漏一半）',
          _n_ok == 0, u'ok 调用=%d' % (_n_ok,))

    _crlf = SELF.count('\r\n')
    check(u'C3 无 BOM 且**全 LF**（与本目录其他套件同构）',
          not SELF.startswith(u'\ufeff') and _crlf == 0,
          u'BOM=%s CRLF=%d' % (SELF.startswith(u'\ufeff'), _crlf))

    _mark_a = u'D' + u':' + u'\\_tmp'
    _mark_b = u'E' + u':' + u'\\'
    _mark_c = u'C' + u':' + u'\\Users'
    _drive = [d for d in (_mark_a, _mark_b, _mark_c) if d in SELF]
    check(u'C4 零外部盘：判据本身不引用工作区外的路径（临时件落系统 temp）',
          not _drive, u'命中=%d 处' % (len(_drive),))
finally:
    try:
        shutil.rmtree(_tmp, ignore_errors=True)
    except Exception:
        pass

# ================================================ 汇总
print('')
if _n_fail:
    print('check159：FAIL %d / PASS %d' % (_n_fail, _n_pass))
    for _d in _failed:
        print('  红：%s' % (_d,))
    sys.exit(1)
print('check159：%d 条全过' % (_n_pass,))
sys.exit(0)
