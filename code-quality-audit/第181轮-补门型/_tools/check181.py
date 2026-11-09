# -*- coding: utf-8 -*-
u"""第181轮 · 「按位移 / 按实例变量推门去向」回归锁。

## 本轮做了什么

补 63 条净增边（`batch=181`，`priority` 8200~8262），落点**只增不改**：
既有 2,768 条一个字段都不动（写前写后逐条比对过）。

取证两条独立路径：

    `probe181.ch{1..5}.txt`   UTMT 导出的**原始指令**（Push/Call）
    `probe181b.ch{1..5}.json` UTMT **反编译 GML**

逐门机制（五章一致，`gml_Object_<obj>_Alarm_2`）：

    obj_doorA / _musfade : room_goto_next()                          → +1
    obj_doorB / _musfade : room_goto_previous()                      → −1
    obj_doorC / _musfade : room_goto(room_next(room_next(room)))     → +2
    obj_doorD / _musfade : room_goto(room_previous(room_previous(room))) → −2
    obj_doorE            : room_next 三次                             → +3
    obj_doorF            : room_previous 三次                        → −3
    obj_climb_door       : 实例 PreCreate 写 `doorRoom`；`room_goto(doorRoom)`

## ★★★ 三条不能写错的口径

1. **`entrance` 数值不等于门名字母**（ch1 的 C=4 / D=5 / E=6 / F=7；ch2 起 C=3 / D=4）。
   `when_door` 取的是**名字字母**，所以本条判据**禁止**把 `entrance` 数值当常量断言；
   B5 反而要求 `when_door == 名字字母`，拿"用 entrance 填了字母"实现会直接红。
2. **判据不许写死会随轮次增长的绝对数**。路由总数只写 `>= 2831`；
   `batch=181` 的条数才写死 `== 63`（那是本轮的历史事实，不会变）。
3. **位移落在 `Data.Rooms` 下标上**（`_room_order.json` 的 meta 已写明），
   所以 B2 用下标算、B3 用名字核，两条互相交叉。

## 判据分段

- A 分母与批段（6）  · B 数据↔证据独立重推（10）  · C 老账不动（5）
- D 归因闭合（6）    · E 隐藏房登记（4）          · F 自检（5）

★ 环境变量口子（只给 `mutate181.py` 用，判据本身一行不改）
  `CQ_ROUTES_181` / `CQ_EV42_181` / `CQ_RAW_181` / `CQ_SCENES_181`
"""
import ast
import collections
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))

SCENES = os.environ.get('CQ_SCENES_181') or os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
EV42 = os.environ.get('CQ_EV42_181') or os.path.join(
    REPO, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
RAW = os.environ.get('CQ_RAW_181') or os.path.join(ROUND, '_evidence', 'raw')
EV = os.path.join(ROUND, '_evidence')
ROUTES = os.environ.get('CQ_ROUTES_181') or os.path.join(SCENES, '_routes.json')

BATCH = 181
PRIO_LO, PRIO_HI = 8200, 8262

_n = {'p': 0, 'f': 0}
_bad = []


def check(desc, cond, extra=u''):
    if cond:
        _n['p'] += 1
        print('[PASS] %s%s' % (desc, (u'    ' + extra) if extra else u''))
    else:
        _n['f'] += 1
        _bad.append(desc)
        print('[FAIL] %s%s' % (desc, (u'    ' + extra) if extra else u''))


def jload(p):
    return json.load(io.open(p, encoding='utf-8'))


# ---------------------------------------------------------------------------
#  0. 只读载入
# ---------------------------------------------------------------------------
CHAPTERS = [('ch1', 'inst42.json'), ('ch2', 'ch2_inst42.json'), ('ch3', 'ch3_inst42.json'),
            ('ch4', 'ch4_inst42.json'), ('ch5', 'ch5_inst42.json')]

_routes_raw = io.open(ROUTES, 'rb').read()
ROUTES_BYTES = len(_routes_raw)
_doc = json.loads(_routes_raw.decode('utf-8'))
ROUTES = _doc['routes']

_idx = jload(os.path.join(SCENES, '_index.json'))
BY_RID = {}
SID2NAME = {}
for _w, _wd in _idx['chapters'].items():
    for _a, _ad in _wd.get('areas', {}).items():
        for _sid, _sd in _ad.get('scenes', {}).items():
            SID2NAME[_sid] = _sd.get('name') or _sid
            _rid = _sd.get('original_room_id')
            if _rid is not None:
                BY_RID[(_w, _rid)] = _sid

_order = jload(os.path.join(EV42, '_room_order.json'))['chapters']
RID2NAME = {ch: {r['index']: r['name'] for r in cd['rooms']} for ch, cd in _order.items()}
NAME2SID = {}
for _ch in _order:
    for _r in _order[_ch]['rooms']:
        _s = BY_RID.get((_ch, _r['index']))
        if _s:
            NAME2SID[(_ch, _r['name'])] = _s

MINE = [r for r in ROUTES if (r.get('_original') or {}).get('batch') == BATCH]
LEGACY = [r for r in ROUTES if (r.get('_original') or {}).get('batch') != BATCH]

# ---------------------------------------------------------------------------
#  1. 从**原始指令**独立重推位移（不复用 apply181 的任何代码）
# ---------------------------------------------------------------------------
CODE_HDR = re.compile(r'^### CODE (\S+)\s+ins=(\d+)\s*$')
INS = re.compile(r'^\s*\d+\s+(\w+)\|([^|]*)\|(.*)$')
OBJ_EV = re.compile(r'^gml_Object_(.+?)_(Create_0|Alarm_\d+|Step_0|Other_\d+|Draw_0)$')


def parse_raw(path):
    out, cur, buf = {}, None, []
    for line in io.open(path, encoding='utf-8'):
        line = line.rstrip(u'\n')
        m = CODE_HDR.match(line)
        if m:
            if cur:
                out[cur] = buf
            cur, buf = m.group(1), []
            continue
        if line.startswith(u'=========='):
            if cur:
                out[cur] = buf
            cur, buf = None, []
            continue
        if cur is not None:
            mi = INS.match(line)
            if mi:
                buf.append((mi.group(1), mi.group(2), mi.group(3)))
    if cur:
        out[cur] = buf
    return out


def shift_of(body):
    u"""从 `Alarm_2` 指令序列里数出位移。

    · `room_goto_next`  ⇒ +1；`room_goto_previous` ⇒ −1
    · 连续 N 次 `room_next` ⇒ +N；连续 N 次 `room_previous` ⇒ −N
    · 一次都没命中 ⇒ None（这条门没有位移语义）
    """
    calls = []
    for k, ins in enumerate(body):
        if ins[0] != 'Call':
            continue
        v = ins[2]
        # ★ probe181.csx 写的格式是 `FN=room_goto_next`（等号），不是 `FN:`。
        #   第一版判据写成 `startswith('FN:')` ⇒ 恒空 ⇒ B2/D1/D4/D6 一起假红。
        if not v.startswith('FN='):
            continue
        calls.append(v[3:])
    if 'room_goto_next' in calls:
        return +1
    if 'room_goto_previous' in calls:
        return -1
    n_next = calls.count('room_next')
    n_prev = calls.count('room_previous')
    if n_next and not n_prev:
        return +n_next
    if n_prev and not n_next:
        return -n_prev
    return None


RAW_CODES = {}
for _n0 in (1, 2, 3, 4, 5):
    p = os.path.join(RAW, 'probe181.ch%d.txt' % _n0)
    if os.path.exists(p):
        RAW_CODES['ch%d' % _n0] = parse_raw(p)

#: {kind: {章: 位移}}
DERIVED_SHIFT = collections.defaultdict(dict)
for _ch, _codes in RAW_CODES.items():
    for _cn, _body in _codes.items():
        _m = OBJ_EV.match(_cn)
        if not _m or _m.group(2) != 'Alarm_2':
            continue
        _sh = shift_of(_body)
        if _sh is not None:
            DERIVED_SHIFT[_m.group(1)][_ch] = _sh

# ---------------------------------------------------------------------------
print('=' * 74)
print(u'第181轮 · 按位移/实例变量推门去向')
print('=' * 74)
print(u'')

# ---------------------------------------------------------------------------
#  A 分母与批段
# ---------------------------------------------------------------------------
check(u'A1 路由总数 >= 2831（本轮落在 2831；此数只增不减，故不写死）',
      len(ROUTES) >= 2831, u'实测 %d' % len(ROUTES))

check(u'A2 batch=181 的条数 == 63',
      len(MINE) == 63, u'实测 %d' % len(MINE))

_pri = sorted(r['priority'] for r in MINE)
check(u'A3 batch=181 的 priority 是 8200~8262 连续无洞',
      _pri == list(range(PRIO_LO, PRIO_LO + 63)),
      u'实测 %r ~ %r，条数 %d' % (_pri[:3], _pri[-3:], len(_pri)))

_mine_pairs = [(r['when_scene'], r['to']) for r in MINE]
check(u'A4 batch=181 内部 (when_scene, to) 唯一（不含重复边）',
      len(set(_mine_pairs)) == len(_mine_pairs), u'%d / %d' % (len(set(_mine_pairs)), len(_mine_pairs)))

_legacy_pairs = set((r['when_scene'], r['to']) for r in LEGACY)
_overlap = [k for k in _mine_pairs if k in _legacy_pairs]
check(u'A5 batch=181 与老账**零交集**（没造与既有同源的边）',
      not _overlap, u'交集 %d 条 %r' % (len(_overlap), _overlap[:3]))

_kinds = collections.Counter((r['_original'] or {}).get('via') for r in MINE)
check(u'A6 batch=181 覆盖 10 种门型，且每种都 >= 1 条',
      len(_kinds) == 10 and min(_kinds.values()) >= 1,
      u'%r' % dict(sorted(_kinds.items())))

# ---------------------------------------------------------------------------
#  B 数据 ↔ 证据（独立重推）
# ---------------------------------------------------------------------------
_probe_ch = [c for c in ('ch1', 'ch2', 'ch3', 'ch4', 'ch5') if c in RAW_CODES]
check(u'B1 五章原始指令证据齐全（probe181.ch1..ch5）',
      len(_probe_ch) == 5, u'实测 %r' % (_probe_ch,))

_exp_shift = {
    'obj_doorA': 1, 'obj_doorA_musfade': 1,
    'obj_doorB': -1, 'obj_doorB_musfade': -1,
    'obj_doorC': 2, 'obj_doorC_musfade': 2,
    'obj_doorD': -2, 'obj_doorD_musfade': -2,
    'obj_doorE': 3, 'obj_doorF': -3,
}
_sh_bad = []
for kind, want in _exp_shift.items():
    got = DERIVED_SHIFT.get(kind) or {}
    for ch in _probe_ch:
        if got.get(ch) != want:
            _sh_bad.append((kind, ch, got.get(ch), want))
check(u'B2 ★ 独立重推位移：10 种门型 × 5 章，逐条与 `_original.shift` 一致',
      not _sh_bad, u'不一致 %d 条 %r' % (len(_sh_bad), _sh_bad[:4]))

# 数据侧 shift 与证据侧 shift 对齐
_mismatch = []
for r in MINE:
    o = r.get('_original') or {}
    if o.get('kind') != 'delta_door_shift':
        continue
    ch, kind = o.get('chapter'), o.get('via')
    if (DERIVED_SHIFT.get(kind) or {}).get(ch) != o.get('shift'):
        _mismatch.append((ch, kind, o.get('shift')))
check(u'B3 每条 `delta_door_shift` 的 `_original.shift` 等于证据重推值',
      not _mismatch, u'不一致 %d 条 %r' % (len(_mismatch), _mismatch[:3]))

# 下标算术：src + shift == dst（覆盖项单列）
_arith = []
_ovr = [r for r in MINE if (r.get('_original') or {}).get('override')]
for r in MINE:
    o = r.get('_original') or {}
    if o.get('kind') != 'delta_door_shift':
        continue
    if o.get('override'):
        continue
    if o.get('src_room_id') + o.get('shift') != o.get('dst_room_id'):
        _arith.append((r['when_scene'], o.get('src_room_id'), o.get('shift'), o.get('dst_room_id')))
check(u'B4 下标算术闭合：src_room_id + shift == dst_room_id（覆盖项除外）',
      not _arith, u'不闭合 %d 条 %r' % (len(_arith), _arith[:3]))

_ovr_ok = all(
    (r['_original'].get('chapter'), r['_original'].get('src_room_id'),
     r['_original'].get('dst_room_id')) == ('ch3', 110, 28)
    for r in _ovr)
check(u'B5 ★ ch3 单点覆盖：唯一 override 是 `chapter==3 && room==110 → 28`',
      len(_ovr) == 1 and _ovr_ok,
      u'override 条数 %d，逐条 (章,源,目标)=%r'
      % (len(_ovr), [(r['_original'].get('chapter'), r['_original'].get('src_room_id'),
                      r['_original'].get('dst_room_id')) for r in _ovr]))

# 名字 ↔ 下标交叉核（用 _room_order，不依赖上面算出的任何东西）
_name_bad = []
for r in MINE:
    o = r.get('_original') or {}
    ch = o.get('chapter')
    if ch not in RID2NAME:
        _name_bad.append((ch, 'chapter?'))
        continue
    if o.get('kind') == 'delta_door_shift':
        if RID2NAME[ch].get(o.get('src_room_id')) != o.get('src_room_name'):
            _name_bad.append((ch, 'src', o.get('src_room_name')))
        if RID2NAME[ch].get(o.get('dst_room_id')) != o.get('dst_room_name'):
            _name_bad.append((ch, 'dst', o.get('dst_room_name')))
check(u'B6 房间名 ↔ 下标交叉核对（`_room_order.json` 独立查表）',
      not _name_bad, u'不一致 %d 条 %r' % (len(_name_bad), _name_bad[:3]))

# scene 映射交叉核
_map_bad = []
for r in MINE:
    o = r.get('_original') or {}
    ch = o.get('chapter')
    if o.get('kind') == 'delta_door_shift':
        if BY_RID.get((ch, o.get('src_room_id'))) != r['when_scene']:
            _map_bad.append(('src', r['when_scene']))
        if BY_RID.get((ch, o.get('dst_room_id'))) != r['to']:
            _map_bad.append(('dst', r['to']))
check(u'B7 `when_scene` / `to` 与 (章, 房下标) 的 scene 映射一致',
      not _map_bad, u'不一致 %d 条 %r' % (len(_map_bad), _map_bad[:3]))

# when_door 必须是**名字字母**，不是 entrance 数值
_letter_bad = []
for r in MINE:
    o = r.get('_original') or {}
    kind = o.get('via') or u''
    if o.get('kind') == 'delta_door_instance':
        if r.get('when_door') is not None:
            _letter_bad.append((kind, r.get('when_door'), u'应为 None'))
        continue
    want = None
    if kind.startswith('obj_door'):
        rest = kind[len('obj_door'):]
        if rest and rest[0].isalpha():
            want = rest[0].upper()
    if kind == 'obj_doorw_musfade':
        want = u'W'
    if r.get('when_door') != want:
        _letter_bad.append((kind, r.get('when_door'), want))
check(u'B8 ★ `when_door` 取门**名字字母**（不是 `entrance` 数值；实例门为 None）',
      not _letter_bad, u'不一致 %d 条 %r' % (len(_letter_bad), _letter_bad[:4]))

# climb_door：PreCreate 里的 doorRoom 必须与目标房名一致
# ★ 先一次性建表（B9 与 D1 的 climb 分母共用，避免两处各算一遍还算出两个数）
CLIMB_INSTS = []          # (章, 房下标, 源 scene, 目标 scene, doorRoom 房名)
CLIMB_BAD = []
for n in (1, 2, 3, 4, 5):
    p = os.path.join(RAW, 'probe181b.ch%d.json' % n)
    if not os.path.exists(p):
        CLIMB_BAD.append(('ch%d' % n, 'evidence-missing'))
        continue
    d = jload(p)
    for i in d['instances']:
        if i.get('obj') != 'obj_climb_door':
            continue
        g = i.get('creation_gml') or u''
        m = None
        for ln in g.split('\n'):
            ln = ln.strip()
            if ln.startswith('doorRoom'):
                m = ln.split('=', 1)[1].strip().rstrip(';').strip()
                break
        if not m:
            continue
        src = BY_RID.get(('ch%d' % n, i.get('room_index')))
        dst = NAME2SID.get(('ch%d' % n, m))
        CLIMB_INSTS.append(('ch%d' % n, i.get('room_index'), src, dst, m))
        if not src or not dst:
            continue
        # ★ 只要 (src,dst) **有路由**即可——6 条落点已被既有边覆盖，落边时按去重跳过，
        #   不能因此判红（第一版要求必须出现在 batch=181 里，属于判据过窄）。
        want = [r for r in ROUTES if r['when_scene'] == src and r['to'] == dst]
        if not want:
            CLIMB_BAD.append(('ch%d' % n, i.get('room_index'), '缺边'))
            continue
        o = want[0]['_original']
        if o.get('dst_room_name') and o.get('dst_room_name') != m:
            CLIMB_BAD.append(('ch%d' % n, i.get('room_index'), o.get('dst_room_name'), m))
_n_climb = len(CLIMB_INSTS)
check(u'B9 obj_climb_door：%d 个可解实例的 `doorRoom` 与落点逐条一致（含已被老账覆盖的）'
      % _n_climb,
      not CLIMB_BAD, u'不一致 %d 条 %r' % (len(CLIMB_BAD), CLIMB_BAD[:4]))

# 负控制：随手编一个 (场景, 目标) 必须查不到
_fake = ('ch1.card_castle.cc_4f', 'ch5.flower_castle.dw_fcastle_foyer')
check(u'B10 负控制：虚构的 (场景, 目标) 在 batch=181 里查不到（判据不是恒真）',
      _fake not in set(_mine_pairs), u'探针 %r' % (_fake,))

# ---------------------------------------------------------------------------
#  C 老账不动
# ---------------------------------------------------------------------------
check(u'C1 老账条数 >= 2768（只增不减）',
      len(LEGACY) >= 2768, u'实测 %d' % len(LEGACY))

# ★ `when_src` 本来就是**可选**字段（2,768 条里只有 1,408 条有），
#   第一版把它当必填 ⇒ 假红。正确口径 = 老账的键集合必须是**已知键的子集**，
#   不许出现本轮新增的键（那才说明我动了老账的结构）。
_LEGACY_ALLOWED = {'to', 'priority', 'reason', 'when_scene', 'when_door',
                   '_original', 'when_src', '_order', 'work'}
_kb = sorted(set().union(*[set(r) for r in LEGACY]) - _LEGACY_ALLOWED)
check(u'C2 老账没有出现已知集合以外的新键（`when_src` 是可选字段，不按必填算）',
      not _kb, u'越界键 %r' % (_kb,))

check(u'C3 顶层 `meta` / `_fallback` / `schema_version` 原样保留',
      isinstance(_doc.get('meta'), dict) and _doc.get('_fallback') is not None
      and _doc.get('schema_version') == 1)

_by_batch = collections.Counter((r.get('_original') or {}).get('batch') for r in ROUTES)
check(u'C4 批次分布：本轮只多了 batch=181 一格，其它批次条数不变',
      _by_batch.get(BATCH) == 63 and _by_batch.get(174) == 51 and _by_batch.get(172) == 756,
      u'%r' % dict(sorted(_by_batch.items(), key=lambda kv: (kv[0] is None, kv[0]))))

_to_missing = [r['to'] for r in ROUTES if r['to'] not in SID2NAME]
check(u'C5 全表 `to` 指向不存在的场景 == 0（本轮没往虚空里加边）',
      not _to_missing, u'%d 条 %r' % (len(_to_missing), _to_missing[:3]))

# ---------------------------------------------------------------------------
#  D 归因闭合：门型实例 = 落边实例 + 逐条归因
# ---------------------------------------------------------------------------
SHIFT_KINDS = set(_exp_shift)
_mine_set = set(_mine_pairs)

#: 逐实例五分类：本轮落边 / 老账已覆盖 / **目标未登记** / **源未映射** / **漏加**
#: ★ 第四类是第一版漏掉的：`room_school_unusedroom`（ch1~ch5 各一处，`obj_doorD`）
#:   从来没登记成 scene，所以源侧就没有 scene 可挂，边落不下去——但实例数照样要进分母。
_acc = collections.Counter()
_miss_rows = []
_ns_rows, _nsrc_rows = [], []
_kind_miss = collections.Counter()
_backed = set()           # 真正被原作用例复现出来的 batch=181 边
UNRESOLVED = []
for ch, f in CHAPTERS:
    p = os.path.join(EV42, f)
    if not os.path.exists(p):
        continue
    d = jload(p)
    for rm in d['rooms']:
        src = BY_RID.get((ch, rm['index']))
        for inst in rm['insts']:
            kind = inst['obj']
            if kind not in SHIFT_KINDS:
                continue
            sh = DERIVED_SHIFT.get(kind, {}).get(ch)
            if sh is None:
                continue
            _acc['tot'] += 1
            tgt = rm['index'] + sh
            if (ch, rm['index'], kind) == ('ch3', 110, 'obj_doorC'):
                tgt = 28
            dst = BY_RID.get((ch, tgt))
            if not dst:
                _acc['nos'] += 1
                _ns_rows.append((ch, rm['index'], kind, RID2NAME[ch].get(tgt)))
                UNRESOLVED.append((ch, rm['index'], kind, 'no_scene', RID2NAME[ch].get(tgt)))
                continue
            if not src:
                _acc['nosrc'] += 1
                _nsrc_rows.append((ch, rm['index'], kind, RID2NAME[ch].get(rm['index']), dst))
                UNRESOLVED.append((ch, rm['index'], kind, 'no_src', dst))
                continue
            if (src, dst) in _mine_set:
                _acc['mine'] += 1
                _backed.add((src, dst))
            elif (src, dst) in _legacy_pairs:
                _acc['leg'] += 1
                UNRESOLVED.append((ch, rm['index'], kind, 'dup_legacy', None))
            else:
                _acc['miss'] += 1
                _miss_rows.append((ch, rm['index'], kind, src, dst))
                _kind_miss[kind] += 1

#: climb 门同样逐实例入账（分母来自 probe181b，不是上面那 587 个位移门实例）
_c = collections.Counter()
for _ch, _ri, _src, _dst, _dr in CLIMB_INSTS:
    _c['tot'] += 1
    if not _src:
        _c['nosrc'] += 1
        UNRESOLVED.append((_ch, _ri, 'obj_climb_door', 'no_src', _dst or _dr))
    elif not _dst:
        _c['nos'] += 1
        UNRESOLVED.append((_ch, _ri, 'obj_climb_door', 'no_scene', _dr))
    elif (_src, _dst) in _mine_set:
        _c['mine'] += 1
        _backed.add((_src, _dst))
    elif (_src, _dst) in _legacy_pairs:
        _c['leg'] += 1
        UNRESOLVED.append((_ch, _ri, 'obj_climb_door', 'dup_legacy', None))
    else:
        _c['miss'] += 1
        _miss_rows.append((_ch, _ri, 'obj_climb_door', _src, _dst))
        _kind_miss['obj_climb_door'] += 1

_T = {k: _acc[k] + _c[k] for k in ('tot', 'mine', 'leg', 'nos', 'nosrc', 'miss')}
check(u'D1 ★ 逐实例差分闭合（位移门 %d + climb %d = %d）：实例 == 落边 + 老账覆盖 '
      u'+ 目标未登记 + 源未映射，且**漏加 0**'
      % (_acc['tot'], _c['tot'], _T['tot']),
      _T['tot'] == _T['mine'] + _T['leg'] + _T['nos'] + _T['nosrc'] and _T['miss'] == 0,
      u'实例 %d = 落边 %d + 老账覆盖 %d + 未登记 %d + 源未映射 %d；漏加 %d %r'
      u'｜位移门侧 %d = %d+%d+%d+%d｜climb 侧 %d = %d+%d+%d+%d'
      % (_T['tot'], _T['mine'], _T['leg'], _T['nos'], _T['nosrc'], _T['miss'],
         _miss_rows[:3],
         _acc['tot'], _acc['mine'], _acc['leg'], _acc['nos'], _acc['nosrc'],
         _c['tot'], _c['mine'], _c['leg'], _c['nos'], _c['nosrc']))

# ★ 落边**实例数**(64) 与**唯一边数**(63) 不相等是正常的：有一对 (源,目标) 被同房两扇
#   同型门共用。但反过来必须成立——63 条边**每一条**都得有实例背书，不许凭空多写。
_dup_pairs = collections.Counter()
for ch, f in CHAPTERS:
    p = os.path.join(EV42, f)
    if not os.path.exists(p):
        continue
    for rm in jload(p)['rooms']:
        src = BY_RID.get((ch, rm['index']))
        for inst in rm['insts']:
            kind = inst['obj']
            if kind not in SHIFT_KINDS:
                continue
            sh = DERIVED_SHIFT.get(kind, {}).get(ch)
            if sh is None or not src:
                continue
            tgt = 28 if (ch, rm['index'], kind) == ('ch3', 110, 'obj_doorC') else rm['index'] + sh
            dst = BY_RID.get((ch, tgt))
            if dst and (src, dst) in _mine_set:
                _dup_pairs[(src, dst)] += 1
_multi = sorted(k for k, v in _dup_pairs.items() if v > 1)
check(u'D2 ★ 无凭空边：63 条边每一条都被至少一个原作用例复现（`_backed == batch181`）',
      _backed == _mine_set,
      u'边 %d / 有背书 %d；差集 %r；被多实例共用的边 %d 条（故落边实例 64 > 唯一边 63）'
      % (len(_mine_set), len(_backed), sorted(_mine_set - _backed)[:3], len(_multi)))

check(u'D3 归因只允许三种理由（`no_scene` / `no_src` / `dup_legacy`），没有"其它"漏网',
      all(u[3] in ('no_scene', 'no_src', 'dup_legacy') for u in UNRESOLVED),
      u'实测理由集合 %r' % (sorted(set(u[3] for u in UNRESOLVED)),))

check(u'D4 `no_scene` 归因逐条带得出目标房名（不是空手说"未解"）',
      all(u[4] for u in UNRESOLVED if u[3] == 'no_scene'),
      u'%d 条，缺名 %d；涉及目标房 %r'
      % (sum(1 for u in UNRESOLVED if u[3] == 'no_scene'),
         sum(1 for u in UNRESOLVED if u[3] == 'no_scene' and not u[4]),
         sorted(set((u[0], u[4]) for u in UNRESOLVED if u[3] == 'no_scene'))[:4]))

check(u'D5 `no_src` 归因逐条带得出源房名与已知目标（源房没登记成 scene，不是"查不到"）',
      all(r[4] for r in _nsrc_rows) and len(_nsrc_rows) == sum(1 for u in UNRESOLVED if u[3] == 'no_src'),
      u'%d 条 %r' % (len(_nsrc_rows), _nsrc_rows[:3]))

# 未接线门型（Deltarune 侧）必须全部有交代
WIRED_KINDS = set()
for r in ROUTES:
    o = r.get('_original') or {}
    if (r['when_scene'] or '').split('.')[0] not in ('ch1', 'ch2', 'ch3', 'ch4', 'ch5'):
        continue
    for k in (o.get('via'), r.get('when_src')):
        if k:
            WIRED_KINDS.add(k)
ALL_DOOR_KINDS = collections.Counter()
for ch, f in CHAPTERS:
    p = os.path.join(EV42, f)
    if not os.path.exists(p):
        continue
    for rm in jload(p)['rooms']:
        for inst in rm['insts']:
            k = inst['obj'].lower()
            if 'door' not in k:
                continue
            if any(t in k for t in ('marker', 'doorframe', 'ambience', 'indicator')):
                continue
            ALL_DOOR_KINDS[inst['obj']] += 1

UNWIRED = {k: v for k, v in ALL_DOOR_KINDS.items() if k not in WIRED_KINDS}
_leaked = sorted(k for k in UNWIRED if k in SHIFT_KINDS and _kind_miss.get(k, 0) > 0)
check(u'D6 ★ 未接线门型里若出现位移门，必须"全部实例已被老账覆盖"，不许有漏加',
      not _leaked,
      u'未接线 %d 种 / %d 个实例；位移门漏加 %r；位移门但无新边（已被老账全覆盖）=%r'
      % (len(UNWIRED), sum(UNWIRED.values()), _leaked,
         sorted(k for k in UNWIRED if k in SHIFT_KINDS)))

# 每种未接线门型都得能"说出它为什么接不上"：要么自身无 room_goto，要么目标动态
_attrib = {}
for kind in UNWIRED:
    has_goto = False
    for ch, codes in RAW_CODES.items():
        for cn, body in codes.items():
            m = OBJ_EV.match(cn)
            if not m or m.group(1) != kind:
                continue
            for ins in body:
                if ins[0] == 'Call' and ins[2].startswith('FN=room_goto'):
                    has_goto = True
                    break
            if has_goto:
                break
        if has_goto:
            break
    _attrib[kind] = 'has_goto' if has_goto else 'no_goto'

check(u'D7 每个未接线门型都能归因：无 `room_goto` 的占多数，有 `room_goto` 的逐条另记',
      all(v in ('has_goto', 'no_goto') for v in _attrib.values()) and len(_attrib) == len(UNWIRED),
      u'无 door 代码或无 goto = %d 种；有 goto 但仍未接线 = %r'
      % (sum(1 for v in _attrib.values() if v == 'no_goto'),
         sorted(k for k, v in _attrib.items() if v == 'has_goto')))

# ★★★ 有 goto 却没接线的 5 种，逐条写死角色。第一版只写了 3 个（漏了后两个），
#     下面 D9 会把每条理由**再拿证据核一遍**，避免这张表退化成"随手抄输出"。
_HASGOTO_UNWIRED = {
    'obj_shortcut_door': 'dynamic_target',   # Create_0 里 door_destination = room（自己），真目标运行期才定
    'obj_darkdoor': 'story_state',           # Step_0 上千条指令，靠 global.con / plot 推进
    'obj_darkdoorevent': 'story_state',
    'obj_board_b2s_icedoor': 'story_state',  # ch3：con 12 段演出 + global.flag[1055] 冰钥匙，目标是常量
    'obj_doorC_musfade': 'dup_legacy',       # 位移门，但 7 个实例落点全被老账走过 ⇒ 净增 0
}
_got = set(k for k, v in _attrib.items() if v == 'has_goto')
check(u'D8 ★ 有 `room_goto` 却仍不接线的门型 == 5 个固定角色（动态目标 / 剧情状态机 / 已被老账全覆盖）',
      _got == set(_HASGOTO_UNWIRED),
      u'实测 %r；白名单 %r；多出 %r 缺失 %r'
      % (sorted(_got), sorted(_HASGOTO_UNWIRED),
         sorted(_got - set(_HASGOTO_UNWIRED)), sorted(set(_HASGOTO_UNWIRED) - _got)))

# D9：三类理由各自取证，不许"因为它在名单里所以它成立"
_ev_bad = []
for kind, why in sorted(_HASGOTO_UNWIRED.items()):
    if why == 'dynamic_target':
        c0 = u''
        for ch, codes in RAW_CODES.items():
            for cn, body in codes.items():
                m = OBJ_EV.match(cn)
                if m and m.group(1) == kind and m.group(2) == 'Create_0':
                    c0 += cn + u'\n'
        # ① Create_0 把 door_destination 指回自己
        selftgt = False
        for ch, codes in RAW_CODES.items():
            for cn, body in codes.items():
                m = OBJ_EV.match(cn)
                if not (m and m.group(1) == kind and m.group(2) == 'Create_0'):
                    continue
                txt = u'\n'.join(i[2] for i in body)
                if 'door_destination' in txt:
                    selftgt = True
        # ② 所有实例的 PreCreate 都没写 doorRoom / door_destination（⇒ 静态取不到真目标）
        n_cc = 0
        for n in (1, 2, 3, 4, 5):
            p = os.path.join(RAW, 'probe181b.ch%d.json' % n)
            if not os.path.exists(p):
                continue
            for i in jload(p)['instances']:
                if i.get('obj') != kind:
                    continue
                if (i.get('creation_gml') or u'').strip():
                    n_cc += 1
        if not (selftgt and n_cc == 0):
            _ev_bad.append((kind, why, selftgt, n_cc))
    elif why == 'story_state':
        best = 0
        hascon = False
        for ch, codes in RAW_CODES.items():
            for cn, body in codes.items():
                m = OBJ_EV.match(cn)
                if not m or m.group(1) != kind:
                    continue
                best = max(best, len(body))
                if any('VAR=con' in i[2] for i in body):
                    hascon = True
        # 剧情状态机 = 指令量足够大（>=100）且状态变量 con 在跑
        if not (best >= 100 and hascon):
            _ev_bad.append((kind, why, best, hascon))
    elif why == 'dup_legacy':
        leaked = _kind_miss.get(kind, 0)
        if not (leaked == 0 and ALL_DOOR_KINDS.get(kind, 0) > 0
                and kind in SHIFT_KINDS):
            _ev_bad.append((kind, why, leaked, ALL_DOOR_KINDS.get(kind, 0)))
    else:
        _ev_bad.append((kind, why, 'unknown_reason'))
check(u'D9 ★ D8 的白名单逐条可取证（动态目标=Create_0 指自己且实例无创建码；'
      u'剧情状态机=指令≥100 且 `con` 在跑；已全覆盖=漏加 0）',
      not _ev_bad, u'取证不成立 %d 条 %r' % (len(_ev_bad), _ev_bad[:4]))

# ---------------------------------------------------------------------------
#  E 隐藏房登记（只登记数据，不改行为）
# ---------------------------------------------------------------------------
HR = _doc.get('_hidden_rooms')
check(u'E1 `_hidden_rooms` 存在且是 4 条（ch1 未登记房 + ch2/ch3/ch4）',
      isinstance(HR, list) and len(HR) == 4,
      u'实测 %r' % (len(HR) if isinstance(HR, list) else type(HR).__name__,))

check(u'E2 每间都有 `status` 与 `evidence`，且状态取值在白名单内',
      isinstance(HR, list) and all(
          h.get('status') in ('data_only', 'target_not_registered', 'no_incoming_edge',
                              'gate_unresolved') and h.get('evidence')
          for h in HR),
      u'状态 %r' % ([h.get('status') for h in (HR or [])],))

_p02 = [h for h in (HR or []) if h.get('probability') == 0.02]
check(u'E3 概率 1/50 的两间（ch1/ch2）都记了 `probability=0.02` 与表达式',
      len(_p02) == 2 and all(h.get('probability_expr') for h in _p02),
      u'%r' % ([(h.get('scene'), h.get('probability')) for h in (HR or [])],))

check(u'E4 ★ 本轮**不声称已生效**：没有任何一条状态是 `enabled`（机制留到第182轮）',
      all(h.get('status') != 'enabled' for h in (HR or [])),
      u'有 enabled 的条数 %d' % sum(1 for h in (HR or []) if h.get('status') == 'enabled'))

# ---------------------------------------------------------------------------
#  F 自检
# ---------------------------------------------------------------------------
_src = io.open(os.path.abspath(__file__), encoding='utf-8').read()

_DRV = re.compile('[A-Za-z]' + ':' + r'[\\/]')
_ext = _DRV.findall(_src)
check(u'F1 零外部盘：本文件没有盘符开头的绝对路径字面量（找到 %d 处）' % len(_ext),
      not _ext, u'回归不许依赖外部盘/临时区')

_MAIN_IMP = 'import ' + 'main'
_TRUE_APP = 'Ralsei' + 'Pet('
check(u'F2 不构造真机 App：不 import `main`、不出现真机构造调用',
      _MAIN_IMP not in _src and _TRUE_APP not in _src)

_NET = ['import ' + m for m in ('requests', 'urllib', 'socket', 'http.client')]
_hit_net = [k for k in _NET if k in _src]
check(u'F3 零网络：不 import 网络库（命中 %r）' % (_hit_net,), not _hit_net)

# AST 查恒真：`check(x, True)` 这种写法必须为 0
_tree = ast.parse(_src)
_const_true = []
for _node in ast.walk(_tree):
    if not (isinstance(_node, ast.Call) and getattr(_node.func, 'id', None) == 'check'):
        continue
    if len(_node.args) >= 2 and isinstance(_node.args[1], ast.Constant) \
            and _node.args[1].value is True:
        _const_true.append(getattr(_node, 'lineno', -1))
check(u'F4 AST 无恒真判据（`check(desc, True)` 出现 0 次）',
      not _const_true, u'命中行号 %r' % (_const_true,))

# 判据条数固定（不随环境变）
# ★★★ 这里踩过一个坑：F5 在执行时 `_n` 里**还没有它自己** ⇒ 写 `== 36` 时实测永远 35，
#   判据自己把自己判红。正确写法是把自身 +1 算进去，改断言条数时必须同步改这个数字。
check(u'F5 判据条数不随环境变（本文件恒发 39 条断言，含本条自身）',
      _n['p'] + _n['f'] + 1 == 39, u'实测 %d（不含本条）+1 = %d' % (_n['p'] + _n['f'], _n['p'] + _n['f'] + 1))

# ---------------------------------------------------------------------------
print('')
print('=' * 74)
print(u'合计：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _bad:
    print(u'红项：')
    for _b in _bad:
        print(u'  - %s' % _b)
print('=' * 74)
sys.exit(1 if _n['f'] else 0)
