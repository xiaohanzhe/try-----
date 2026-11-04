# -*- coding: utf-8 -*-
u"""第158轮回归锁：**状态真变了就落盘** —— 别让"他说出去了"只在内存里。

## 为什么（第157轮 §9 第 1 条遗留）

差事状态的落盘只有三处：`_npc_errand_tick`（120 秒节流）、`cancel_errand`（同样走节流）、
退出时的 `_npc_plan_save(force=True)`（**只管生活档案，不管差事**）。
`assign_errand` 体内**一个落盘调用都没有**。改前实测（`probe158 --before`）：

| # | 场景 | 改前 |
|---|---|---|
| P1 | 连派三次（A→B→C）后什么都不做就重启 | 在办 **0 条** / 欠账 **0 件** |
| P2 | 派活 → 落过一次盘 → 30 秒内叫停 → 重启 | 在办 **1 条**（差事**复活**，人又出门） |
| P3 | 派 / 催 / 改派各一次，数落盘次数 | **0 次** |
| P5 | 派活 → 到岗（写过一次）→ 1.5 秒内办完 → 重启 | 在办 **1 条**、结果空（**又出门一次**） |

⇒ 用户口径「按照人类的逻辑来就好」：我说"让他去擦柜台"，这件事**当场就定下了**，
不该取决于我什么时候关窗口/什么时候崩。

## 改法（四处，都只是"换个时机写盘"）

| 位置 | 改成 | 为什么 |
|---|---|---|
| `assign_errand` 派成后 | `_npc_errand_save(force=True)` | 派活低频、语义必须落地；节流窗口里派的三次会整批消失 |
| `cancel_errand` | 原 `()` 改 `force=True` | 用户亲口叫停，盘上却还写着他在外面 ⇒ 重启"我说的话不算数" |
| `_npc_errand_tick` | `force=_structural` | **结构性**变化（被门控作废 / 办完）立刻写；**只压位置**保持节流 |
| 退出兜底 | 补 `_npc_errand_save(force=True)` | 原来只写生活档案，两本档一新一旧 |

## 本套件守什么

| 段 | 守什么 |
|---|---|
| A | **真跑往返**：派活当场落盘 · 欠账随档一起落 · **催一次都不写** · 门控拒 / 看板关**不写** · 叫停不复活 · 办完结果落盘 · **只压位置不强写** · 节流语义没被破坏 · 幂等 · 无路径降级不抛 · 内存与盘上欠账一致 |
| B | **AST 结构**：四处调用的**力**对不对（`True` / `_structural`）· 派活那处在 `return _prev` **之后**（催不写）· 被 `if _new is not None` 守卫 · `_structural` 只认 `dropped`/`finished`（**不含 `touched`**）· 退出兜底紧跟生活档案 · 全文件调用点**恰好 4 处** |
| C | 自检：分母闸 · 判据名非空字面量 · 只用 `check()` · 无 BOM 全 LF · 零外部盘 |

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

for _p in (PKG, os.path.join(PKG, 'src'), os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from main import RalseiPet                                  # noqa: E402
from main import _errand_given_up_of                        # noqa: E402
from modules import npc_errand as ER                        # noqa: E402
from modules import npc_system as NS                        # noqa: E402

with io.open(MAIN, 'r', encoding='utf-8', newline='') as _fh:
    SRC = _fh.read()
TREE = ast.parse(SRC)

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


def _kw(call, name):
    for k in call.keywords:
        if k.arg == name:
            return k.value
    return None


def _is_const(node, val):
    return isinstance(node, ast.Constant) and node.value is val


def _names_in(node):
    return set(n.id for n in ast.walk(node) if isinstance(n, ast.Name))


_DEST = 'oneshot.barrens.Blue'
_DEST2 = 'ut.rooms.room_area1'
_DEST3 = 'ch1.hometown.town_mid'
_WHAT = u'\u64e6\u67dc\u53f0'
_WHAT2 = u'\u6536\u676f\u5b50'
_WHAT3 = u'\u6253\u626b\u524d\u9662'

_T = _time.time()


class _Mem(object):
    def __init__(self):
        self.log = []

    def remember(self, nid, text, who=None, **kw):
        self.log.append((nid, text, who))

    def save(self, nid):
        pass


class _Pos(object):
    __slots__ = ('scene',)

    def __init__(self, scene):
        self.scene = scene


class _Roam(object):
    def __init__(self):
        self._t = {}

    def get(self, nid):
        return self._t.get(nid)

    def put(self, nid, scene, now, reason=None):
        self._t[nid] = _Pos(scene)

    def drop(self, nid):
        self._t.pop(nid, None)


class _Host(object):
    u"""轻宿主：挂产品函数（含 save/load/tick），并把每次落盘记进 `saves`。

    ★ `saves` 里存的是 `force`：`True` = 立刻写，`False` = 走节流那次（可能被挡掉）。
    """

    _npc_errand_note = RalseiPet._npc_errand_note
    assign_errand = RalseiPet.assign_errand
    cancel_errand = RalseiPet.cancel_errand
    _npc_errand_load = RalseiPet._npc_errand_load
    _npc_errand_tick = RalseiPet._npc_errand_tick
    _npc_errand_commit = RalseiPet._npc_errand_commit

    def __init__(self, path, gate_ok=True, enabled=True):
        self._path = path
        self._gate_ok = gate_ok
        self.npc_registry = NS.load_registry()
        self.npc_memory = _Mem()
        self.npc_roam = _Roam()
        self._npc_talking = 'ralsei'
        self._errand_given_up = {}
        self._npc_errand_last_save = 0.0
        self.saves = []
        # ★ 不能写 `load() or ErrandBoard()`：`__len__` 只数**在办**
        #   ⇒ "只剩已办"的档 len()==0 为假，会被换成空板（重启后结果全没）。
        #   产品侧是 `if _er is not None:`（`init_npc_systems`），照抄它。
        _er = self._npc_errand_load()
        self.npc_errand = _er if _er is not None else ER.ErrandBoard()
        self.npc_errand.enabled = bool(enabled)

    def _npc_errand_file(self):
        return self._path

    def _npc_errand_save(self, force=False):
        self.saves.append(bool(force))
        return RalseiPet._npc_errand_save(self, force)

    def _npc_errand_gate(self, npc_id, dest):
        if self._gate_ok:
            return (True, u'')
        return (False, u'\u4ed6\u8fdb\u4e0d\u53bb\u90a3\u4e2a\u4e16\u754c')

    def _npc_seed_bodies(self, scene_id=None):
        pass

    def _npc_scene_id(self):
        return 'ch1.hometown.town_mid'

    def _npc_plan_save(self, force=False):
        return True

    def _errand_report_ack(self, *a, **kw):
        # ★ 交差那句话要模型（第153轮另有套件）⇒ 这里不测，免得网络/线程把观察量淹掉。
        return None


class _NoPathHost(_Host):
    u"""路径取不到（`data_store` 不可用）⇒ 退内存态：**落盘返 `False` 且绝不抛**。"""

    def _npc_errand_file(self):
        return None


_CLS = _clsdef(TREE, 'RalseiPet')
_ASSIGN = _method(_CLS, 'assign_errand')
_CANCEL = _method(_CLS, 'cancel_errand')
_TICK = _method(_CLS, '_npc_errand_tick')

_tmp = tempfile.mkdtemp(prefix='check158_')
try:
    # ================================================ A 真跑往返
    mark(u'A 真跑：派活 / 催 / 门控 / 叫停 / 办完 / 压位置 各自落不落盘')

    _p1 = os.path.join(_tmp, 'a1.json')
    _h = _Host(_p1)
    # ★★ 前置：假装"上一拍刚写过盘"（真实会话里 tick 每 ≤120s 写一次 ⇒ 用户点"派活"
    #   时几乎总在节流窗口**里面**）。不预置这个值，`_npc_errand_last_save=0.0` 会让
    #   第一次派活"碰巧"写成功 ⇒ 判据咬不住"必须 force"这条（变异体 M1 实测）。
    _h._npc_errand_last_save = _T
    _h.assign_errand('ralsei', _DEST, _WHAT, now=_T)
    _h2 = _Host(_p1)
    _e2 = _h2.npc_errand.active_of('ralsei')
    check(u'A1 ★★★ 派活**当场**就落盘 ⇒ 新宿主读回 1 条在办（地点 / 事由 / 状态都在）',
          _e2 is not None and _e2.dest_scene == _DEST and _e2.what == _WHAT
          and getattr(_e2, 'status', u'') == 'traveling',
          u'在办=%d 地点=%s 状态=%s' % (len(_h2.npc_errand),
                                       getattr(_e2, 'dest_scene', u'?'),
                                       getattr(_e2, 'status', u'?')))

    _p2 = os.path.join(_tmp, 'a2.json')
    _h = _Host(_p2)
    _h._npc_errand_last_save = _T        # 同上：三次改派全落在节流窗口内
    _h.assign_errand('ralsei', _DEST, _WHAT, now=_T)
    _h.assign_errand('ralsei', _DEST2, _WHAT2, now=_T + 10)
    _h.assign_errand('ralsei', _DEST3, _WHAT3, now=_T + 20)
    _h2 = _Host(_p2)
    _gu = _errand_given_up_of(_h2, 'ralsei', now=_T + 30)
    check(u'A2 ★★ 改派留痕也随同一本档落盘 ⇒ 读回**两件欠账**、顺序老→新、事由一字不差',
          [d for d, w in _gu] == [_DEST, _DEST2] and [w for d, w in _gu] == [_WHAT, _WHAT2],
          u'欠账=%r' % ([d for d, w in _gu],))

    _p3 = os.path.join(_tmp, 'a3.json')
    _h = _Host(_p3)
    _e_a = _h.assign_errand('susie', _DEST, _WHAT, now=_T)
    _h.saves.clear()
    _e_b = _h.assign_errand('susie', _DEST, _WHAT, now=_T + 1)   # 同一件事再说一遍
    check(u'A3 ★★ 催（同一件事再说一遍）⇒ **一次都不写盘**，且返回的是**同一个对象**',
          len(_h.saves) == 0 and _e_a is _e_b and _e_a is not None,
          u'落盘=%d 同对象=%s' % (len(_h.saves), _e_a is _e_b))

    _p4 = os.path.join(_tmp, 'a4.json')
    _h = _Host(_p4, gate_ok=False)
    _e4 = _h.assign_errand('os_niko', _DEST, _WHAT, now=_T)
    check(u'A4 ★★ 门控拒 ⇒ 返 `None`、**不写盘**、盘上**没有这个档**（没派成不该留痕）',
          _e4 is None and len(_h.saves) == 0 and not os.path.isfile(_p4),
          u'返=%r 落盘=%d 有档=%s' % (_e4, len(_h.saves), os.path.isfile(_p4)))

    _p5 = os.path.join(_tmp, 'a5.json')
    _h = _Host(_p5, enabled=False)
    _e5 = _h.assign_errand('ralsei', _DEST, _WHAT, now=_T)
    check(u'A5 看板关（`enabled=False`）⇒ 同样 `None` 且不写盘（开关关着就别产生档）',
          _e5 is None and len(_h.saves) == 0 and not os.path.isfile(_p5),
          u'返=%r 落盘=%d' % (_e5, len(_h.saves)))

    _p6 = os.path.join(_tmp, 'a6.json')
    _h = _Host(_p6)
    _h.assign_errand('ralsei', _DEST, _WHAT, now=_T)
    _h.cancel_errand('ralsei')
    _h2 = _Host(_p6)
    check(u'A6 ★★★ 叫停**当场**落盘 ⇒ 重启后**不复活**（在办 0 / 已办 0）',
          len(_h2.npc_errand) == 0 and len(_h2.npc_errand.done) == 0,
          u'在办=%d 已办=%d' % (len(_h2.npc_errand), len(_h2.npc_errand.done)))

    _p7 = os.path.join(_tmp, 'a7.json')
    _h = _Host(_p7)
    _h.assign_errand('ralsei', _DEST, _WHAT, now=_T, travel=0.0, work=1.0)
    _h._npc_errand_tick(_T + 0.5)          # 到岗（这一拍落盘走节流，改后本就不必写）
    _h._npc_errand_tick(_T + 2.0)          # 办完 —— 距上次落盘 1.5 秒，仍在节流窗口内
    _h2 = _Host(_p7)
    _r7 = _h2.npc_errand.result_of('ralsei')
    check(u'A7 ★★★ 办完那一拍**结构性变化**⇒ 立刻落盘：重启后已办 1 条、结果一字不差、不再出门',
          len(_h2.npc_errand) == 0 and len(_h2.npc_errand.done) == 1 and bool(_r7)
          and _r7 == getattr(_h.npc_errand.done.get('ralsei'), 'result', None),
          u'在办=%d 已办=%d 结果=%r' % (len(_h2.npc_errand),
                                       len(_h2.npc_errand.done), _r7[:16]))

    _p8 = os.path.join(_tmp, 'a8.json')
    _h = _Host(_p8)
    _h.assign_errand('susie', _DEST, _WHAT, now=_T, travel=0.0, work=300.0)
    _h.saves.clear()
    _h._npc_errand_tick(_T + 1.0)          # 只把他**压在目的地**（无结构变化）
    _n8_force = _h.saves.count(True)
    check(u'A8 ★★ 只压位置（无结构变化）⇒ **不强写**（每拍写盘会拖垮主循环）',
          _n8_force == 0 and len(_h.saves) >= 1,
          u'强写=%d 总调用=%d' % (_n8_force, len(_h.saves)))

    _p9 = os.path.join(_tmp, 'a9.json')
    _h = _Host(_p9)
    _h.assign_errand('ralsei', _DEST, _WHAT, now=_T)
    _ok9 = _h._npc_errand_save()
    check(u'A9 ★ 节流语义**没被破坏**：刚强写过一次，紧接着的非力调用仍返 `False`',
          _ok9 is False, u'返=%s' % (_ok9 is True,))

    _p10 = os.path.join(_tmp, 'a10.json')
    _h = _Host(_p10)

    def _snap(path):
        # ★ 档不存在 ⇒ `None`（**不许在这里抛**：一抛后面的 B/C 段整段不跑，
        #   看到的"红"就变成崩溃点而不是守卫点 —— 第157轮 `A2` 的原坑）。
        if not os.path.isfile(path):
            return None
        with io.open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    _h.assign_errand('ralsei', _DEST, _WHAT, now=_T)
    _h.assign_errand('ralsei', _DEST2, _WHAT2, now=_T + 10)
    # ★ 先强写一次把盘**拉到当前状态**再取快照 —— 否则比的是"盘陈旧 vs 盘最新"，
    #   测出来的是"有没有漏写"（A1/A2 的事），不是幂等（变异体 M1 实测假红）。
    _h._npc_errand_save(force=True)
    _s1 = _snap(_p10)
    _h._npc_errand_save(force=True)
    _s2 = _snap(_p10)
    check(u'A10 ★ 幂等：同一状态连写两次，盘上内容**完全一致**（不会越写越少/越写越乱）',
          _s1 is not None and _s1 == _s2,
          u'键=%r' % (sorted(_s1.keys()) if _s1 else None,))

    _h11 = _NoPathHost(os.path.join(_tmp, 'never.json'))
    _ok11 = _h11._npc_errand_save(force=True)
    check(u'A11 ★ 路径取不到（`data_store` 不可用）⇒ 返 `False`，**绝不抛**（降级到内存态）',
          _ok11 is False, u'返=%s' % (_ok11 is True,))

    _p12 = os.path.join(_tmp, 'a12.json')
    _h = _Host(_p12)
    _h.assign_errand('ralsei', _DEST, _WHAT, now=_T)
    _h.assign_errand('ralsei', _DEST2, _WHAT2, now=_T + 10)
    _mem12 = [(d, w) for d, w in _errand_given_up_of(_h, 'ralsei', now=_T + 20)]
    _h2 = _Host(_p12)
    _dsk12 = [(d, w) for d, w in _errand_given_up_of(_h2, 'ralsei', now=_T + 20)]
    check(u'A12 ★★ 落盘**排在上痕之后**：同一时刻内存里的欠账与盘上的欠账**逐项相同**',
          bool(_mem12) and _mem12 == _dsk12,
          u'内存=%d 盘上=%d 相同=%s' % (len(_mem12), len(_dsk12), _mem12 == _dsk12))

    # ================================================ B AST
    mark(u'B AST：四处落盘的**力**与**位置**（挡住"改了但没用"和"每拍写盘"两种退化）')

    _save_a = _calls(_ASSIGN, '_npc_errand_save')
    check(u'B1 ★★★ `assign_errand` 里**恰好一处** `_npc_errand_save`，且 `force=True`',
          len(_save_a) == 1 and _is_const(_kw(_save_a[0], 'force'), True),
          u'处数=%d' % (len(_save_a),))

    _ret_prev = [n for n in ast.walk(_ASSIGN or ast.Module(body=[], type_ignores=[]))
                 if isinstance(n, ast.Return) and isinstance(n.value, ast.Name)
                 and n.value.id == '_prev']
    _ok_b2 = (len(_ret_prev) == 1 and len(_save_a) == 1
              and _save_a[0].lineno > _ret_prev[0].lineno)
    check(u'B2 ★★ 派活那处落盘排在 `return _prev` **之后**（"催"走不到它 ⇒ 没变化就不写盘）',
          _ok_b2, u'return _prev=%d 处' % (len(_ret_prev),))

    _ifs = []
    for n in ast.walk(_ASSIGN or ast.Module(body=[], type_ignores=[])):
        if isinstance(n, ast.If) and len(_save_a) == 1:
            for s in ast.walk(n):
                if s is _save_a[0]:
                    _ifs.append(n)
                    break
    _guard = _ifs[-1].test if _ifs else None
    _ok_b3 = (isinstance(_guard, ast.Compare)
              and isinstance(_guard.left, ast.Name) and _guard.left.id == '_new'
              and len(_guard.ops) == 1 and isinstance(_guard.ops[0], ast.IsNot)
              and isinstance(_guard.comparators[0], ast.Constant)
              and _guard.comparators[0].value is None)
    check(u'B3 ★★★ 派活落盘被 `if _new is not None:` 守卫（`assign` 返空 ⇒ **不写**）',
          _ok_b3, u'守卫=%s' % (ast.dump(_guard)[:60] if _guard is not None else '缺',))

    _save_c = _calls(_CANCEL, '_npc_errand_save')
    check(u'B4 ★★ `cancel_errand` 的落盘是 `force=True`（叫停不许被 120s 节流吃掉）',
          len(_save_c) == 1 and _is_const(_kw(_save_c[0], 'force'), True),
          u'处数=%d' % (len(_save_c),))

    _save_t = _calls(_TICK, '_npc_errand_save')
    _kw_t = _kw(_save_t[0], 'force') if len(_save_t) == 1 else None
    check(u'B5 ★★ `_npc_errand_tick` 的落盘力来自 `_structural`（不是常量、不是 `touched`）',
          len(_save_t) == 1 and isinstance(_kw_t, ast.Name)
          and _kw_t.id == '_structural',
          u'力=%s' % (getattr(_kw_t, 'id', repr(_kw_t)),))

    _asg_s = None
    for n in ast.walk(_TICK or ast.Module(body=[], type_ignores=[])):
        if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == '_structural' for t in n.targets):
            _asg_s = n.value
    _ok_b6 = (isinstance(_asg_s, ast.BoolOp) and isinstance(_asg_s.op, ast.Or)
              and len(_asg_s.values) == 2
              and 'dropped' in _names_in(_asg_s.values[0])
              and 'finished' in ast.dump(_asg_s.values[1])
              and 'touched' not in _names_in(_asg_s))
    check(u'B6 ★★★ `_structural` 只认 `dropped`（被拦下作废）与 `finished`（办完），**不含 `touched`**',
          _ok_b6, u'定义=%s' % (ast.dump(_asg_s)[:72] if _asg_s is not None else '缺',))

    _plan_force = []
    for n in ast.walk(TREE):
        if isinstance(n, ast.FunctionDef):
            for c in _calls(n, '_npc_plan_save'):
                if _is_const(_kw(c, 'force'), True):
                    _plan_force.append((n, c))
    _n_b7 = 0
    _ok_b7 = False
    if len(_plan_force) == 1:
        _fn, _pc = _plan_force[0]
        _ec = [c for c in _calls(_fn, '_npc_errand_save')
               if _is_const(_kw(c, 'force'), True) and c.lineno > _pc.lineno]
        _n_b7 = len(_ec)
        _ok_b7 = _n_b7 >= 1
    check(u'B7 ★★ 退出兜底：生活档案强写之后**紧跟差事档强写**（两本档不能一新一旧）',
          _ok_b7, u'生活档强写=%d 处 差事强写=%d 处'
          % (len(_plan_force), _n_b7))

    _all_save = []
    for n in ast.walk(TREE):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == '_npc_errand_save':
            _all_save.append(n)
    check(u'B8 ★★★ 全文件 `_npc_errand_save` 调用点**恰好 4 处**（多一处 = 又冒出"每拍写盘"的口子）',
          len(_all_save) == 4, u'处数=%d' % (len(_all_save),))

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
          not _bad_names and _n_check >= 24,
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
    print('check158：FAIL %d / PASS %d' % (_n_fail, _n_pass))
    for _d in _failed:
        print('  红：%s' % (_d,))
    sys.exit(1)
print('check158：%d 条全过' % (_n_pass,))
sys.exit(0)
