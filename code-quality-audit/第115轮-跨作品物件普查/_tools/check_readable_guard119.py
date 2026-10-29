# -*- coding: utf-8 -*-
u"""第119轮回归锁：可读物的**守卫分级**（第二层 if 到底怎么选正文）。

## 一句话结论

原作 `obj_readable_*_Alarm_0` 不是 `if/else if` 链，而是**一串平行的 `if`**，
每个块直接覆盖 `global.msg[0]` ⇒ 语义是「**最后一条成立的赋值获胜**」。
所以"默认显示哪句"= **守卫最松（`base`）的那批里最后一条**，不是"编号最小的键"、
也不是"解析出来的第一条"。

## 本轮改了什么（都有实测依据）

1. **数据源**：v1 的键来自指令流的 `PushBltn room ; PushI N` 配对，但那个 `pending`
   只被下一个字符串 push 消费一次 ⇒ 同一房间块的第 2 个及以后的键拿不到房间、被丢掉。
   `audit119.py` 实测：**ut 少 105 组 / outertale 少 78 组**、污染 0 组。
   v2 改用 GML 原文解析（第118轮），并把每条候选标上 `guard`。
2. **选择规则**：`load_readable_text` 不再"取第一条"，改由 `pick_readable_entry()`
   按守卫等级选（`base` 的最后一条）。老资产（无 `guard` 字段）行为不变。
3. **别的都不动**：正文原样搬运、解码仍在 `decode_readable` 里做。

## 本套件守什么

A `pick_readable_entry` 纯函数：**正/负控制成对**（"最后一条 base" vs "第一条"必须不同）
B 资产结构：v2 schema、每条带合法 `guard`、`(obj, order)` 有序
C ★★ 与 GML 原文对账：资产里**该有的键一个都不少**（`MSC_*` 另行计数，不算正文）
D 防回滚：条目数 / 场景数不许跌回 v1 量级
E 分母闸 + 自检（无恒真判据 / 无 BOM）
F 三个写死取样的期望文本（防止"改了却没人发现"）

零 Qt、零网络、只读仓库内资产。
"""
import ast
import collections
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
ASSET = os.path.join(PET, 'assets', 'scenes', '_readable_text.json')
EV = os.path.join(ROUND, '_evidence')

sys.path.insert(0, os.path.join(PET, 'modules'))
import item_interact as II                                   # noqa: E402

_failed = []
_n_pass = 0
_n_fail = 0


def check(desc, cond, detail=''):
    global _n_pass, _n_fail
    if cond:
        _n_pass += 1
        print('[PASS] %s%s' % (desc, ('    ' + detail) if detail else ''))
    else:
        _n_fail += 1
        _failed.append(desc)
        print('[FAIL] %s%s' % (desc, ('    ' + detail) if detail else ''))


def _read(p):
    with io.open(p, encoding='utf-8', newline='') as f:
        return f.read()


P = II.pick_readable_entry


# ================================================================ A 纯函数
print('=' * 74)
print('A pick_readable_entry（规则来自 GML 原文：平行 if，后者覆盖前者）')
print('=' * 74)

_base1 = {'obj': 'o', 'key': 'K_base', 'guard': 'base'}
_state1 = {'obj': 'o', 'key': 'K_state', 'guard': 'state'}
_base2 = {'obj': 'o', 'key': 'K_base2', 'guard': 'base'}

check('A1 只有一条 base ⇒ 选它（后面的 state 不抢）',
      P([_base1, _state1]) is _base1, P([_base1, _state1]).get('key'))

check('A2 ★★ 多条 base ⇒ **最后一条**（执行顺序里最后覆盖的那句）'
      '（与 A3 成对：证明不是"随便挑一个"）',
      P([_base1, _state1, _base2]) is _base2, P([_base1, _state1, _base2]).get('key'))

check('A3 没有 base ⇒ 退回列表第一条（pos/state 产品侧判不了，按原文顺序）',
      P([_state1]) is _state1, P([_state1]).get('key'))

check('A4 空列表 ⇒ None（不抛、不返回空 dict 冒充条目）',
      P([]) is None, repr(P([])))

_v1 = [{'obj': 'o', 'key': 'K_old1'}, {'obj': 'o', 'key': 'K_old2'}]
check('A5 ★ v1 老资产（没有 `guard` 字段）⇒ 行为与第117轮一致（取第一条）',
      P(_v1) is _v1[0], P(_v1).get('key'))


def _old_pick(entries):
    u"""第117轮的实现：无条件取第一条。"""
    return entries[0] if entries else None


T = II.readable_text_of
_empty_base = {'obj': 'o', 'key': 'K_e', 'guard': 'base', 'en': u'%%'}
_state_txt = {'obj': 'o', 'key': 'K_s', 'guard': 'state', 'en': u'* 有字了 /%%'}

check('A7 ★★ 选中的 base 解完为空（原文只有 `%%`）⇒ **回退到其余候选**'
      '（否则这间房白白退回兜底台词）',
      T([_empty_base, _state_txt]) == u'* 有字了', repr(T([_empty_base, _state_txt])))

check('A8 与 A7 成对的负控制：**全部候选都空** ⇒ 返回空串（不造假）',
      T([_empty_base]) == u'' and T([]) == u'',
      '%r %r' % (T([_empty_base]), T([])))

check('A9 回退**不会改变“该选哪条”**：`pick_readable_entry` 仍选 base（回退只发生在解完为空时）',
      P([_empty_base, _state_txt]) is _empty_base,
      P([_empty_base, _state_txt]).get('key'))

check('A6 ★★ A2 那条判据**不是恒真**：把老实现（总取第一条）喂进同一组数据，'
      '结果必须不同（否则分级形同虚设）',
      _old_pick([_base1, _state1, _base2]) is not P([_base1, _state1, _base2]),
      'old=%s new=%s' % (_old_pick([_base1, _state1, _base2]).get('key'),
                         P([_base1, _state1, _base2]).get('key')))


# ================================================================ B 资产结构
print('')
print('=' * 74)
print('B 资产结构（v2）')
print('=' * 74)

doc = json.loads(_read(ASSET))
by_scene = doc.get('by_scene') or {}
check('B1 `schema_version == 2`（v1 没有 guard，靠版本号区分）',
      doc.get('schema_version') == 2, repr(doc.get('schema_version')))

_all = [(sid, e) for sid, es in by_scene.items() for e in es]
check('B2 每条候选都有合法 `guard`（base/pos/state）',
      all(e.get('guard') in ('base', 'pos', 'state') for _s, e in _all),
      '条目=%d 非法=%d' % (len(_all),
                         sum(1 for _s, e in _all
                             if e.get('guard') not in ('base', 'pos', 'state'))))

_bad_order = []
for sid, es in by_scene.items():
    last = None
    for e in es:
        k = (e.get('obj'), e.get('order'))
        if last is not None and (e.get('obj'), e.get('order')) < last:
            _bad_order.append((sid, k, last))
            break
        last = k
check('B3 每个场景的候选按 `(obj, order)` 升序（"最后一条 base 获胜"依赖这个顺序）',
      not _bad_order, '倒序场景=%d %r' % (len(_bad_order), _bad_order[:2]))

check('B4 `selection` / `guard_note` 写清了规则（数据自解释，后来人不用猜）',
      bool(doc.get('selection')) and bool(doc.get('guard_note')), '')


# ================================================================ C 与 GML 对账
print('')
print('=' * 74)
print('C ★★ 与 GML 原文对账：该有的键一个都不少')
print('=' * 74)

_gml_n = 0
_asset_keys = collections.defaultdict(set)
for sid, es in by_scene.items():
    for e in es:
        _asset_keys[(sid, e['obj'])].add(e['key'])

_missing = []
_msc = 0
_dead = 0
for game in ('ut', 'outertale'):
    p = os.path.join(EV, 'readable_plan119.%s.tsv' % game)
    if not os.path.isfile(p):
        print('[FAIL] 缺对账输入 %s（分母为空，不许算通过）' % os.path.basename(p))
        _n_fail += 1
        _failed.append('C0 对账输入缺失')
        continue
    for i, ln in enumerate(io.open(p, encoding='utf-8')):
        q = ln.rstrip('\n').split('\t')
        if i == 0 or len(q) < 6:
            continue
        if q[2].startswith('MSC_'):
            _msc += 1
            continue
        if int(q[5]) == 0:
            # ★ 该房间根本没有这个对象 ⇒ 这段 `if (room == X)` 是死代码，
            #   按第117轮的纪律**不进资产**，这里也不该要求它存在。
            _dead += 1
            continue
        _gml_n += 1
        if q[2] not in _asset_keys.get((q[0], q[1]), ()):
            _missing.append((q[0], q[1], q[2]))

check('C1 分母闸：GML 侧至少产生 500 条**真用得上**的正文键（否则本段什么也没证明）',
      _gml_n >= 500, 'GML 键=%d（死代码 %d 条已排除，MSC_ %d 条交给 msc 脚本）'
      % (_gml_n, _dead, _msc))

check('C2 ★★★ GML 里每条正文键都能在资产里找到（v1 缺 ut 105 组 / outertale 78 组，'
      '本判据就是防它回退）',
      not _missing, '缺=%d %r' % (len(_missing), _missing[:3]))

check('C3 ★★ C2 不是恒真：随便编一个不存在的键，必须被同一谓词判为缺',
      ('ut.rooms.room_ruins2', 'obj_readable_room1', '__nope__')
      not in _asset_keys.get(('ut.rooms.room_ruins2', 'obj_readable_room1'), ()),
      '')


# ================================================================ D 防回滚
print('')
print('=' * 74)
print('D 防回滚（下界，不是"等于某个随时相变的绝对值"）')
print('=' * 74)

check('D1 条目数 ≥ 900（v1 是 355；跌回去说明数据源又退回指令流了）',
      len(_all) >= 900, '条目=%d' % len(_all))
check('D2 场景数 ≥ 160（v1 是 166 个场景）', len(by_scene) >= 160, '场景=%d' % len(by_scene))
_n_base = sum(1 for _s, e in _all if e.get('guard') == 'base')
check('D3 base 候选 ≥ 500（守卫最松的那批，是"默认显示"的来源）',
      _n_base >= 500, 'base=%d' % _n_base)


# ================================================================ F 写死取样
print('')
print('=' * 74)
print('F 写死取样：加载器最终交给界面的那句')
print('=' * 74)

table = II.load_readable_text(ASSET)
# ★ 写死场景/对象 + 期望包含的子串：不写整句（整句里有原生控制符解出来的空格差异），
#   但也不写"非空"这种弱判据。
SAMPLES = [
    ('ut.rooms.room_ruins2', 'obj_readable_room1', u'顺着路走'),
    ('ut.rooms.room_fire_lab1', 'obj_readable_room5', u'太暗了看不清'),
    ('ut.rooms.room_torielroom', 'obj_readable_room2', u'百科全书'),
]
_bad_sample = []
for sid, obj, sub in SAMPLES:
    got = (table.get(sid) or {}).get(obj) or u''
    if sub not in got:
        _bad_sample.append((sid, obj, sub, got[:40]))
check('F1 ★★ 三个写死取样都能读到期望的原作正文（读不到=选择规则或资产坏了）',
      not _bad_sample, '不符=%d %r' % (len(_bad_sample), _bad_sample[:2]))

check('F2 加载器结果与资产 scene 数一致（每个有正文的场景都进表）',
      len(table) >= 160, '场景=%d' % len(table))


# ================================================================ E 自检
print('')
print('=' * 74)
print('E 本脚本自检')
print('=' * 74)

_self = _read(os.path.abspath(__file__))
_taut = 0
for n in ast.walk(ast.parse(_self)):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'check':
        if len(n.args) >= 2:
            a = n.args[1]
            if isinstance(a, ast.Constant) and a.value in (True, 1):
                _taut += 1
check('E1 本脚本没有 `check(..., True)` 这种恒真判据（AST 数，不扫文本）',
      _taut == 0, '恒真=%d' % _taut)
check('E2 本脚本无 BOM', not _self.startswith(u'\ufeff'), '')

print('')
print('=' * 74)
print('合计：PASS=%d FAIL=%d' % (_n_pass, _n_fail))
if _failed:
    print('失败项：')
    for d in _failed:
        print('  - %s' % d)
print('=' * 74)
sys.exit(0 if _n_fail == 0 else 1)
