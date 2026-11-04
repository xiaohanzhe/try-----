# -*- coding: utf-8 -*-
u"""第157轮回归锁：**欠账要落盘** —— 重启之后，"我还欠着两件事"得还在。

## 为什么（第156轮 §9 第 1 条遗留）

第156轮把欠账挂进了 prompt 尾部（治好了"记忆窗口裁掉"），但它**只存内存**。
改前实测（`probe157 --before`）：

| 量 | 改前 |
|---|---|
| 派三次 → 落盘 → **新宿主**读回：在办差事 | 1 条（活了） |
| 同一时刻：欠账 | **0 件（死了）** |
| 存档顶层键 | `['active', 'done', 'enabled']` —— 欠账从未进档 |
| 靠记忆兜底？ | **不成立**：重启后聊 12 句，两件都出窗 |

⇒ 用户口径「按照人类的逻辑来就好」：人会记得"我手上还欠着两件事"。

## 改法（机制层零改动）

`_ErrandDoc(board, 欠账dump)` 把 `ErrandBoard.to_dict()` 的形状原样拿过来、
**多补一个 `given_up` 键**，再交给 `npc_plan_store.save()`（原子写照旧复用）。
`ErrandBoard.from_dict` 本来就**忽略**它不认识的键 ⇒ 新旧档**双向兼容**。

## 本套件守什么

| 段 | 守什么 |
|---|---|
| A | **真跑往返**：跨"重启"两件都回来（顺序老→新）· ★★★ **类型还原**（盘上是 `list`、内存里必须是 `tuple`，否则 `_errand_given_up_of` 静默全丢）· 空账写 `{}` · TTL 过期不落盘 · 上限截断 · **老档兼容**（无 `given_up` 键）· 坏一条丢一条 · 非 dict 不炸 · 两次往返幂等 · 按人分槽 · 看板本身不受影响 |
| B | **存档形状**：四个键都在 · `given_up` 是可 JSON 序列化的 `{npc_id: [[ts, dest, what]]}` · 原子写产物读得回来 · ★ `ErrandBoard.to_dict()` 仍是**三个键**（机制层形状没被污染） |
| C | **AST/边界**：写仍走 `npc_plan_store_mod.save` · 读仍走 `from_dict` 且**不碰** `npc_plan_store_mod.load` · 机制层仍不出现 `given_up` · dump/restore 是**模块级** · restore 里那步 `tuple` 转换在位 · save 传的是 `_ErrandDoc` · dump/restore 体内**不自己写盘** |
| D | 自检：判据名非空字面量 · 只用 `check()` · 无 BOM 全 LF · 零外部盘 |

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
from main import (                                          # noqa: E402
    _ErrandDoc, _errand_given_up_dump, _errand_given_up_restore,
    _errand_given_up_of, ERRAND_GIVEN_UP_MAX, ERRAND_GIVEN_UP_TTL)
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


_TOP = [n.name for n in TREE.body if isinstance(n, ast.FunctionDef)]
_TOPOBJ = dict((n.name, n) for n in TREE.body if isinstance(n, ast.FunctionDef))

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


class _Host(object):
    u"""轻宿主：**只挂产品函数**（`assign_errand` / `_npc_errand_save` / `_npc_errand_load`）。

    ★ 与 `check150._DiskHost` 同一套顺序：先 `_npc_errand_load()`（它顺手定路径），
      读不到只是返 `None`。这是产品的真实顺序，不是捷径。
    """

    _npc_errand_note = RalseiPet._npc_errand_note
    _errand_note = RalseiPet._npc_errand_note
    assign_errand = RalseiPet.assign_errand
    _npc_errand_save = RalseiPet._npc_errand_save
    _npc_errand_load = RalseiPet._npc_errand_load

    def __init__(self, path):
        self._path = path
        self.npc_registry = NS.load_registry()
        self.npc_memory = _Mem()
        self._npc_talking = 'ralsei'
        self._errand_given_up = {}
        self._npc_errand_last_save = 0.0
        self.npc_errand = self._npc_errand_load() or ER.ErrandBoard()

    def _npc_errand_file(self):
        return self._path

    def _npc_errand_gate(self, npc_id, dest):
        return (True, u'')


def _dump_json(path):
    with io.open(path, encoding='utf-8') as fh:
        return json.load(fh)


_tmp = tempfile.mkdtemp(prefix='check157_')
_P1 = os.path.join(_tmp, 'a.json')
_P2 = os.path.join(_tmp, 'b.json')
_P3 = os.path.join(_tmp, 'c.json')

try:
    # ================================================ A 真跑往返
    mark(u'A 真跑往返：跨"重启"两件都回来 / 类型还原 / 空账 / TTL / 上限 / '
         u'老档兼容 / 坏一条丢一条 / 幂等 / 按人分槽')

    check(u'A0 分母闸：`_ErrandDoc` / `_errand_given_up_dump` / `_errand_given_up_restore` '
          u'都在（缺一个后面全是空断言）',
          isinstance(_ErrandDoc, type)
          and '_errand_given_up_dump' in _TOP
          and '_errand_given_up_restore' in _TOP,
          u'类=%s dump=%s restore=%s'
          % (isinstance(_ErrandDoc, type),
             '_errand_given_up_dump' in _TOP,
             '_errand_given_up_restore' in _TOP))

    _h1 = _Host(_P1)
    _h1.assign_errand('ralsei', _DEST, _WHAT, now=_T)
    _h1.assign_errand('ralsei', _DEST2, _WHAT2, now=_T + 10)
    _h1.assign_errand('ralsei', _DEST3, _WHAT3, now=_T + 20)
    _ok_save = _h1._npc_errand_save(force=True)
    _raw1 = _dump_json(_P1)
    _h2 = _Host(_P1)
    _back = _errand_given_up_of(_h2, 'ralsei', now=_T + 30)

    check(u'A1 ★★★ 重启（新宿主 + 读盘）之后，两件欠账**都回来了**，顺序仍是"老 → 新"',
          _ok_save is True
          and [d for d, _w in _back] == [_DEST, _DEST2],
          u'件数=%d 顺序对=%s' % (len(_back),
                                 [d for d, _w in _back] == [_DEST, _DEST2]))

    # ★★★ 盘上是 list（JSON 没有 tuple），内存里必须是 tuple —— 不转就静默全丢。
    # ★ 这里一律 `.get(...) or []`：破坏（比如"save 又退回裸 board"）会让 `given_up`
    #   整个键都不在 ⇒ 直接下标取会 **KeyError 把套件炸掉**，后面 20 多条判据根本没跑，
    #   看上去"只红一条"（实测踩过：那轮的"只红 A1"其实是崩溃点，不是守卫点）。
    _gu_rows = (_raw1.get('given_up') or {}).get('ralsei') or []
    _mem_rows = (getattr(_h2, '_errand_given_up', None) or {}).get('ralsei') or []
    _disk_elem = type(_gu_rows[0]) if _gu_rows else None
    _mem_elem = type(_mem_rows[0]) if _mem_rows else None
    check(u'A2 ★★★ **类型还原**：盘上元素是 `list`、读回内存必须转成 `tuple`'
          u'（`_errand_given_up_of` 只认 tuple ⇒ 不转就是"盘上有、界面上没有"）',
          _disk_elem is list and _mem_elem is tuple and len(_back) == 2,
          u'盘上=%s 内存=%s 可用=%d'
          % (getattr(_disk_elem, '__name__', u'缺'), 
             getattr(_mem_elem, '__name__', u'缺'), len(_back)))

    check(u'A3 地点与事由**一字不差**地带回来（不是只回一个地点表）',
          [w for _d, w in _back] == [_WHAT, _WHAT2]
          and bool(_back) and _back[0][0] == _DEST,
          u'事由对=%s' % ([w for _d, w in _back] == [_WHAT, _WHAT2],))

    check(u'A4 **看板本身不受影响**（正控制：差事照旧跨重启）',
          len(_h2.npc_errand) == 1 and _h2.npc_errand.active_of('ralsei') is not None,
          u'在办=%d' % (len(_h2.npc_errand),))

    # ---- A5 空账：写 {}，不写 null，也不造假条目 ----
    _h0 = _Host(_P2)
    _h0.assign_errand('ralsei', _DEST, _WHAT, now=_T)
    _h0._npc_errand_save(force=True)
    _raw2 = _dump_json(_P2)
    _h0b = _Host(_P2)
    check(u'A5 **没欠账时写 `{}`**（不是 `null`、也不是空壳条目），读回仍是空',
          _raw2.get('given_up') == {}
          and _errand_given_up_of(_h0b, 'ralsei', now=_T + 1) == [],
          u'盘上=%r' % (_raw2.get('given_up'),))

    # ---- A6 TTL：过期账**不落盘**（文件不随时间膨胀）----
    _h6 = _Host(_P3)
    _h6._errand_given_up = {'ralsei': [(_T - 90000.0, _DEST, _WHAT),
                                       (_T - 60.0, _DEST2, _WHAT2)]}
    _d6 = _errand_given_up_dump(_h6, now=_T)
    check(u'A6 超过 TTL 的旧账**不写进档**（只剩一天内那件 —— 否则档会越攒越长）',
          list(_d6.get('ralsei') or []) and len(_d6['ralsei']) == 1
          and _d6['ralsei'][0][1] == _DEST2,
          u'落盘件数=%d' % (len(_d6.get('ralsei') or []),))

    # ---- A6b 恢复侧也按 TTL 过滤（看的是**内存表长度**，不是查询结果）----
    _h6b = _Host(_P3)
    _n6b = _errand_given_up_restore(_h6b, {'ralsei': [
        [_T - 90000.0, _DEST, _WHAT],        # 25 小时前
        [_T - 60.0, _DEST2, _WHAT2],
    ]}, now=_T)
    _tbl6b = _h6b._errand_given_up.get('ralsei') or []
    check(u'A6b 恢复侧**也按 TTL 过滤**：陈年旧账连内存表都不进'
          u'（查询侧还会再滤一次 ⇒ 只看"返几件"是恒真的，这里看**表长度**）',
          _n6b == 1 and len(_tbl6b) == 1,
          u'恢复=%d 表内=%d' % (_n6b, len(_tbl6b)))

    # ---- A7 上限：连改 12 次只写 MAX 件 ----
    _h7 = _Host(_P3)
    _h7._errand_given_up = {'ralsei': [(_T - i, '%s#%d' % (_DEST2, i),
                                       u'\u7b2c%d\u4ef6' % (i,))
                                      for i in range(12)]}
    _d7 = _errand_given_up_dump(_h7, now=_T)
    check(u'A7 欠账超过上限 ⇒ 落盘**只留最近那几件**'
          u'（与第156轮的内存上限同一条口径）',
          len(_d7.get('ralsei') or []) == ERRAND_GIVEN_UP_MAX,
          u'落盘件数=%d 上限=%d' % (len(_d7.get('ralsei') or []), ERRAND_GIVEN_UP_MAX))

    # ---- A7b 恢复侧也截断（防手改档 / 老档塞进来一长串）----
    _h7b = _Host(_P3)
    _n7b = _errand_given_up_restore(_h7b, {'ralsei': [
        [_T - i, '%s#%d' % (_DEST2, i), u'\u7b2c%d\u4ef6' % (i,)]
        for i in range(12)]}, now=_T)
    _tbl7b = _h7b._errand_given_up.get('ralsei') or []
    check(u'A7b 恢复侧**也按上限截断**：手改/老档塞 12 条 ⇒ 内存表只留上限那几件',
          _n7b == ERRAND_GIVEN_UP_MAX and len(_tbl7b) == ERRAND_GIVEN_UP_MAX,
          u'恢复=%d 表内=%d' % (_n7b, len(_tbl7b)))

    # ---- A8 老档兼容：只有 enabled/active/done 的旧档 ----
    with io.open(_P2, 'w', encoding='utf-8', newline='\n') as _fh:
        json.dump({'enabled': True, 'active': [], 'done': []}, _fh)
    _h8 = None
    _err8 = u''
    try:
        _h8 = _Host(_P2)
    except Exception as e:
        _err8 = u'%s' % (e,)
    check(u'A8 ★ **老档兼容**：只有 `enabled/active/done` 的旧档 ⇒ 不炸、空账、看板照建',
          _h8 is not None and _errand_given_up_of(_h8, 'ralsei', now=_T) == []
          and len(_h8.npc_errand) == 0,
          _err8 or u'建起来了')

    # ---- A9 坏一条丢一条（单元级）----
    _h9 = _Host(_P3)
    _n9 = _errand_given_up_restore(_h9, {'ralsei': [
        [_T - 10, _DEST, _WHAT],
        ['not-a-number', _DEST2, _WHAT2],     # ← 坏的
        [_T - 5, _DEST3, _WHAT3],
    ]}, now=_T)
    check(u'A9 **坏一条丢一条**（不是"有一条坏就整表作废"）：3 条里坏 1 条 ⇒ 恢复 2 条',
          _n9 == 2 and len(_errand_given_up_of(_h9, 'ralsei', now=_T)) == 2,
          u'恢复=%d' % (_n9,))

    # ---- A10 非 dict 的 given_up：不炸、返 0 ----
    _h10 = _Host(_P3)
    _n10 = None
    _err10 = u''
    try:
        _n10 = (_errand_given_up_restore(_h10, u'oops', now=_T),
                _errand_given_up_restore(_h10, [], now=_T),
                _errand_given_up_restore(_h10, None, now=_T))
    except Exception as e:
        _err10 = u'%s' % (e,)
    check(u'A10 非 dict 的 `given_up`（字符串 / 列表 / None）⇒ **返 0、不抛**'
          u'（旧档被手改坏也不该让桌宠起不来）',
          _n10 == (0, 0, 0), _err10 or u'三态都返 0')

    # ---- A11 两次往返幂等 ----
    _h11 = _Host(_P1)
    _i1 = _errand_given_up_of(_h11, 'ralsei', now=_T + 30)
    _h11._npc_errand_save(force=True)
    _h11b = _Host(_P1)
    _i2 = _errand_given_up_of(_h11b, 'ralsei', now=_T + 30)
    check(u'A11 再存再读**幂等**：件数不翻倍、顺序不乱（存档不会"越读越多"）',
          _i1 == _i2 and len(_i2) == 2, u'第一轮=%d 第二轮=%d' % (len(_i1), len(_i2)))

    # ---- A12 按人分槽 ----
    _h12 = _Host(_P3)
    _h12._errand_given_up = {'ralsei': [(_T - 10, _DEST, _WHAT)],
                             'susie': [(_T - 20, _DEST2, _WHAT2)]}
    _h12._npc_errand_save(force=True)
    _h12b = _Host(_P3)
    _r12 = _errand_given_up_of(_h12b, 'ralsei', now=_T)
    _s12 = _errand_given_up_of(_h12b, 'susie', now=_T)
    check(u'A12 欠账**按人分槽**：两人的各回各的，不串味',
          _r12 == [(_DEST, _WHAT)] and _s12 == [(_DEST2, _WHAT2)],
          u'ralsei=%d susie=%d' % (len(_r12), len(_s12)))

    # ================================================ B 存档形状
    mark(u'B 存档形状：四个键都在 / given_up 可 JSON 序列化 / 原子写产物可读 / '
         u'机制层形状没被污染')

    _keys = set(_raw1.keys())
    check(u'B1 顶层**四个键都在**（`enabled`/`active`/`done` 一个没少，外加 `given_up`）',
          {'enabled', 'active', 'done', 'given_up'} <= _keys,
          u'键=%d 个' % (len(_keys),))

    _gu = _raw1.get('given_up') or {}
    _shape_ok = isinstance(_gu, dict) and all(
        isinstance(k, str) and isinstance(v, list)
        and all(isinstance(it, list) and len(it) == 3
                and isinstance(it[0], float) and isinstance(it[1], str)
                and isinstance(it[2], str) for it in v)
        for k, v in _gu.items())
    check(u'B2 `given_up` 形状是 `{npc_id: [[ts(float), dest(str), what(str)], ...]}`'
          u'（**全部 JSON 原生类型**，没有 tuple 混进去）',
          _shape_ok, u'形状对=%s' % (_shape_ok,))

    check(u'B3 原子写产物**读得回来**（`.tmp` + `os.replace` 没留半截文件）',
          _dump_json(_P1) == _raw1 and not os.path.exists(_P1 + '.tmp'),
          u'一致=%s 残留tmp=%s'
          % (_dump_json(_P1) == _raw1, os.path.exists(_P1 + '.tmp')))

    check(u'B4 ★ `ErrandBoard.to_dict()` 仍然只有**三个键**（机制层形状没被欠账污染）',
          sorted(ER.ErrandBoard().to_dict().keys())
          == ['active', 'done', 'enabled'],
          u'键=%r' % (sorted(ER.ErrandBoard().to_dict().keys()),))

    # ================================================ C AST
    mark(u'C AST/边界：写仍走 npc_plan_store.save / 读不碰 load / 机制层干净 / '
         u'模块级 / tuple 转换在位 / 传的是 _ErrandDoc / 不自己写盘')

    _CLS = _clsdef(TREE, 'RalseiPet')
    _SAVE = _method(_CLS, '_npc_errand_save')
    _LOAD = _method(_CLS, '_npc_errand_load')


    def _mod_calls(fn, mod_name, attr):
        out = []
        if fn is None:
            return out
        for c in ast.walk(fn):
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) \
                    and c.func.attr == attr \
                    and isinstance(c.func.value, ast.Name) \
                    and c.func.value.id == mod_name:
                out.append(c)
        return out


    check(u'C1 写仍**复用** `npc_plan_store_mod.save()`（第150轮 G3 的契约没被绕开）',
          bool(_mod_calls(_SAVE, 'npc_plan_store_mod', 'save')),
          u'处数=%d' % (len(_mod_calls(_SAVE, 'npc_plan_store_mod', 'save')),))
    check(u'C2 读仍走 `from_dict`、且**不碰** `npc_plan_store_mod.load`'
          u'（那条路只认 `schema_version==1`，会把差事档判成版本不符）',
          bool(_calls(_LOAD, 'from_dict'))
          and not _mod_calls(_LOAD, 'npc_plan_store_mod', 'load'),
          u'from_dict=%d load=%d'
          % (len(_calls(_LOAD, 'from_dict')),
             len(_mod_calls(_LOAD, 'npc_plan_store_mod', 'load'))))

    _mod_src = io.open(ERRAND_MOD, 'r', encoding='utf-8').read()
    check(u'C3 机制层 `npc_errand.py` 里**仍不出现** `given_up`'
          u'（第156轮定的边界：机制层不认识"欠账"这种人类叙事）',
          'given_up' not in _mod_src and 'GIVEN_UP' not in _mod_src,
          u'命中=%d' % (_mod_src.count('given_up'),))

    check(u'C4 dump / restore 是**模块级**函数（写成方法 ⇒ 轻宿主当场 `AttributeError`，'
          u'第156轮同款第 4 次的教训）',
          '_errand_given_up_dump' in _TOP and '_errand_given_up_restore' in _TOP,
          u'模块级=%s' % (('_errand_given_up_dump' in _TOP
                          and '_errand_given_up_restore' in _TOP),))

    _rst = _TOPOBJ.get('_errand_given_up_restore')
    _tuple_ok = False
    for n in ast.walk(_rst) if _rst is not None else []:
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == 'append' and n.args:
            if isinstance(n.args[0], ast.Tuple) and len(n.args[0].elts) == 3:
                _tuple_ok = True
    check(u'C5 ★ restore 里那步**转回 tuple** 在位（`rows.append((ts, dest, what))`）'
          u'—— 这是 A2 的结构性对照',
          _tuple_ok, u'tuple 追加=%s' % (_tuple_ok,))

    _doc_args = []
    for c in _calls(_SAVE, 'save'):
        for a in c.args:
            if isinstance(a, ast.Call) and isinstance(a.func, ast.Name) \
                    and a.func.id == '_ErrandDoc':
                _doc_args.append(a.func.id)
    check(u'C6 save 传的是 **`_ErrandDoc(...)`**（不是裸 board ⇒ 欠账才有地方写）',
          _doc_args == ['_ErrandDoc'], u'实参=%r' % (_doc_args,))

    _io_hit = []
    for _fn_name in ('_errand_given_up_dump', '_errand_given_up_restore'):
        for n in ast.walk(_TOPOBJ.get(_fn_name) or ast.Module(body=[], type_ignores=[])):
            if isinstance(n, ast.Call):
                _nm = getattr(n.func, 'id', '') or ''
                if _nm in ('open', 'makedirs', 'replace', 'remove'):
                    _io_hit.append((_fn_name, _nm))
    check(u'C7 dump / restore **自己不写盘**（纯数据变换；写盘只有 `npc_plan_store.save` 一个口子）',
          not _io_hit, u'命中=%d 处' % (len(_io_hit),))

    # ================================================ D 自检
    mark(u'D 自检：判据名非空字面量 · 只用 check() · 无 BOM 全 LF · 零外部盘')

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
    check(u'D0 分母闸：本文件里 `check(` 调用**非空**', _n_check > 0,
          u'处数=%d' % (_n_check,))
    check(u'D1 每条判据的说明都是**非空字面量**（不是变量、不是空串）',
          not _bad_names and _n_check >= 26,
          u'坏的=%d 条数=%d' % (len(_bad_names), _n_check))

    _n_ok = 0
    for n in ast.walk(SELF_TREE):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                and n.func.id == 'ok':
            _n_ok += 1
    check(u'D2 只用 `check()`，不用 `ok()`（两套 harness 混用 ⇒ 查恒真会漏一半）',
          _n_ok == 0, u'ok 调用=%d' % (_n_ok,))

    _crlf = SELF.count('\r\n')
    check(u'D3 无 BOM 且**全 LF**（与本目录其他套件同构）',
          not SELF.startswith(u'\ufeff') and _crlf == 0,
          u'BOM=%s CRLF=%d' % (SELF.startswith(u'\ufeff'), _crlf))

    _mark_a = u'D' + u':' + u'\\_tmp'
    _mark_b = u'E' + u':' + u'\\'
    _mark_c = u'C' + u':' + u'\\Users'
    _drive = [d for d in (_mark_a, _mark_b, _mark_c) if d in SELF]
    check(u'D4 零外部盘：判据本身不引用工作区外的路径（临时件落系统 temp）',
          not _drive, u'命中=%d 处' % (len(_drive),))
finally:
    try:
        shutil.rmtree(_tmp, ignore_errors=True)
    except Exception:
        pass

# ================================================ 汇总
print('')
if _n_fail:
    print('check157：FAIL %d / PASS %d' % (_n_fail, _n_pass))
    for _d in _failed:
        print('  红：%s' % (_d,))
    sys.exit(1)
print('check157：%d 条全过' % (_n_pass,))
sys.exit(0)
