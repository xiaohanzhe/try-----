# -*- coding: utf-8 -*-
u"""第169轮 · W 门「按分支补齐」回归锁。

## 本轮做了什么
第168轮用的是 `_room_graph.json` 里那 **98** 条 W 边 —— 那是**下界**。
`conn42b.csx` 每遇到一个 `Cmp` 就把 `srcRoom` 清成 -1，于是 ch2 有 97 条
W 边丢了源房间、进不了场景图。本轮改用**分支级解析**（`branch_x169.json`），
在 ch1/ch2 上多认出 113 条唯一边，落 **102** 条（其余 11 条逐条点名）。

## 判据分四段
- A 段：段位与分母（防空集恒真）
- B 段：独立重推 == 产品段（双向差集都空）
- C 段：落点自证（**真实对象名，大小写敏感**）
- D 段：守恒账与反回滚
"""
import io
import json
import os
import sys
import collections

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
#: ★ 环境变量口子只给 `mutate169.py` 用（同第168轮做法）：把产品表/证据换成副本，
#:   判据本身一行不改。没有这些口子，变异测试只能改真表，一崩就弄脏工作区。
PKG = os.environ.get('CQ_PKG169') or os.path.join(REPO, 'ralsei_pet')
SCENES = os.path.join(PKG, 'assets', 'scenes')
ROUTES_P = os.environ.get('CQ_ROUTES169') or os.path.join(SCENES, '_routes.json')
EV42 = os.environ.get('CQ_EV42') or os.path.join(
    REPO, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
EV = os.environ.get('CQ_EV169') or os.path.join(ROUND, '_evidence')
GRAPH_P = os.path.join(EV42, '_room_graph.json')
BX_P = os.path.join(EV, 'branch_x169.json')

for _p in (PKG, os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from modules import scene_system as SS       # noqa: E402

LETTER = 'W'
PRIO_BASE = 7088
BATCH = 169
KIND = 'delta_door_table'
W_VIA = ('obj_doorW', 'obj_doorw_musfade')
#: 落点对象名里允许出现的**真实**对象（大小写是产品事实：
#: 门叫 `obj_doorW`，W 的出生点却是**小写** `obj_markerw`）
MARK_OK = ('obj_markers', 'obj_markert', 'obj_markeru', 'obj_markerv',
           'obj_markerw', 'obj_markerX', 'obj_markerAny', 'obj_markerAny40px')
#: 钉死：应落 102 条、priority 7088~7189、全表 1,930 条
EXPECT_N = 102
EXPECT_ROUTES = 1961
EXPECT_SCENES = 2166
EXPECT_PRIO_END = 7189
#: 守恒账：176 条原始分支 = 60（第168轮已收）+ 116；116 = 2 未登记 + 8 已有别的门 + 4 重复 + 102
EXPECT_RAW = 176
EXPECT_IN_168 = 60
EXPECT_UNREG = 2
EXPECT_ALREADY = 8
EXPECT_DUP = 4
EXPECT_MARKER_NONE = 4
#: marker 分布（真实对象名 → 条数）
EXPECT_MARKERS = {'obj_markerw': 16, 'obj_markert': 18, 'obj_markerv': 11,
                  'obj_markeru': 12, 'obj_markerX': 23, 'obj_markers': 3,
                  'obj_markerAny': 15, None: 4}

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


def _jl(path):
    u"""读证据 JSON。★ 第42轮那批 `true/false` 是大写开头（非严格 JSON）。"""
    s = io.open(path, encoding='utf-8', newline='').read()
    return json.loads(s.replace(': True', ': true').replace(': False', ': false'))


# ===========================================================================
print('')
print('=' * 70)
print(u'A 段  段位与分母（防空集恒真）')
print('=' * 70)

RAW = json.loads(io.open(ROUTES_P, encoding='utf-8', newline='').read())
RL = RAW.get('routes') or []
IDX = SS.load_index(SCENES)
SCN = IDX.get('scenes') or {}
MINE = [r for r in RL if (r.get('_original') or {}).get('batch') == BATCH]
PAIRS = set((r.get('when_scene'), r.get('to')) for r in MINE)

check(u'A0 分母：`load_index()` ok=True、场景数 == %d、路由 == %d 条、本轮段非空'
      % (EXPECT_SCENES, EXPECT_ROUTES),
      IDX.get('ok') is True and len(SCN) == EXPECT_SCENES
      and len(RL) == EXPECT_ROUTES and len(MINE) > 0,
      u'scenes=%d routes=%d mine=%d ok=%r'
      % (len(SCN), len(RL), len(MINE), IDX.get('ok')))

_prios = sorted(r.get('priority') for r in MINE)
check(u'A1 ★★★ 本轮段 %d 条、priority %d~%d **连续无空洞**'
      % (EXPECT_N, PRIO_BASE, EXPECT_PRIO_END),
      len(MINE) == EXPECT_N
      and _prios == list(range(PRIO_BASE, EXPECT_PRIO_END + 1)),
      u'n=%d 首末=%r' % (len(MINE), (_prios[0], _prios[-1])))

#: ★ 顺序必须由 (章, 源房, 目标) 排序决定 —— 否则每次重建 priority 都会漂，
#:   `git diff` 看不出「到底改了哪几条」。这条专门抓「priority 对但顺序乱」。
_ordered = sorted(MINE, key=lambda r: r.get('priority'))
_key = [(r['_original']['chapter'], r['_original']['src_room_id'],
         r['_original']['dst_room_id'], r['_original']['table']) for r in _ordered]
check(u'A1b ★★ priority 升序 == (章, 源房, 目标, 门对象) 字典序（保证可复现）',
      _key == sorted(_key),
      u'首个逆序位=%r'
      % (next((i for i in range(1, len(_key)) if _key[i] < _key[i - 1]), None),))

_oobch = sorted(set(str(r.get('when_scene') or '').split('.')[0] for r in MINE)
                - set(('ch%d' % i) for i in range(1, 6)))
check(u'A2 本轮段只落 ch1~ch5（绝不碰 desktop / oneshot / ut / outertale / uty）',
      not _oobch, u'越界=%r' % (_oobch,))

_badseg = [r.get('to') for r in MINE
           if r.get('when_door') != LETTER
           or (r.get('_original') or {}).get('kind') != KIND
           or (r.get('_original') or {}).get('door_letter') != LETTER
           or (r.get('_original') or {}).get('via') not in W_VIA]
check(u'A3 本轮段 `when_door` / `door_letter` 全为 W、`kind` 全为 `%s`、'
      u'`via` 只有那两种门对象' % KIND,
      not _badseg, u'异常 %d: %r' % (len(_badseg), _badseg[:3]))

_mk = collections.Counter((r.get('_original') or {}).get('marker') for r in MINE)
_fake = [r.get('to') for r in MINE
         if (r.get('_original') or {}).get('marker') not in MARK_OK + (None,)]
check(u'A4 ★★★ `marker` 只用**真实**对象名；**大写 `obj_markerW` 一条都不许有**'
      u'（那是第125轮量错的那把尺）；`None` 只许 %d 条（落点不自证，按原作照收）'
      % EXPECT_MARKER_NONE,
      not _fake and dict(_mk) == EXPECT_MARKERS,
      u'实测 %r / 异常 %r' % (dict(_mk), _fake[:3]))

_dup = [k for k, v in collections.Counter(
    (r.get('when_scene'), r.get('to')) for r in MINE).items() if v > 1]
check(u'A5 本轮段 `(when_scene, to)` 无重复（同一扇门同一个目标只许一条）',
      not _dup, u'重复=%r' % (_dup[:3],))

_missing_sc = [r.get('when_scene') for r in MINE if r.get('when_scene') not in SCN]
_missing_to = [r.get('to') for r in MINE if r.get('to') not in SCN]
check(u'A6 ★ 两端场景**都在**场景索引里（写不进索引的边等于死边）',
      not _missing_sc and not _missing_to,
      u'源缺=%r 目标缺=%r' % (_missing_sc[:3], _missing_to[:3]))

#: ★★★ 门对象与反汇编代码名必须**互相推导得上**。
#:   变异 M4 就是钻这个空子：把 `table` 改成另一个门对象的 Alarm_2，
#:   `via` 不动 ⇒ A3/B2 全都绿，而"这条边到底是从哪段代码读出来的"已经错了。
_tab_bad = [(r.get('to'), (r.get('_original') or {}).get('via'),
             (r.get('_original') or {}).get('table')) for r in MINE
            if (r.get('_original') or {}).get('table')
            != 'gml_Object_%s_Alarm_2' % (r.get('_original') or {}).get('via')]
check(u'A7 ★★★ `table` 必须能由 `via` 推导（`gml_Object_<门对象>_Alarm_2`）',
      not _tab_bad, u'不符 %d: %r' % (len(_tab_bad), _tab_bad[:3]))

# ===========================================================================
print('')
print('=' * 70)
print(u'B 段  独立重推 == 产品段（双向差集都空）')
print('=' * 70)

BX = (_jl(BX_P) or {}).get('chapters') or {}
GRAPH = (_jl(GRAPH_P) or {}).get('chapters') or {}
CH = [('ch1', 'conn42b.json', 'inst42.json'),
      ('ch2', 'ch2_conn42b.json', 'ch2_inst42.json')]

RID2SID = collections.defaultdict(dict)
for _sid, _rec in SCN.items():
    if isinstance(_rec, dict) and isinstance(_rec.get('original_room_id'), int):
        RID2SID[_sid.split('.')[0]].setdefault(_rec['original_room_id'], _sid)

OTHER = set((r.get('when_scene'), r.get('to')) for r in RL
            if (r.get('_original') or {}).get('batch') != BATCH)
MRK = __import__('re').compile(r'^obj_marker(.*)$')
ANY = ('any', 'any40px')

acct = collections.Counter()
should = set()
should_rows = []
for _ch, _cf, _inf in CH:
    _conn = _jl(os.path.join(EV42, _cf))
    _inst = _jl(os.path.join(EV42, _inf))
    _rn = _conn['room_names']
    _N = len(_rn)
    _mkobj = {}
    for _r in _inst['rooms']:
        _d = {}
        for _o in _r['insts']:
            _mm = MRK.match(_o.get('obj') or '')
            if _mm:
                _d.setdefault((_mm.group(1) or '').lower(), _mm.group(0))
        _mkobj[_r['index']] = _d
    _g = set()
    for _e in ((GRAPH.get(_ch) or {}).get('edges') or []):
        if _e.get('door') in W_VIA:
            _g.add((_e['door'], _e['src'], _e['dst']))
    _seen = set()
    for _r in BX.get(_ch) or []:
        _via = 'obj_doorW' if _r['code'] == 'gml_Object_obj_doorW_Alarm_2' \
            else 'obj_doorw_musfade'
        acct['raw'] += 1
        if (_via, _r['src'], _r['dst']) in _g:
            acct['in_168'] += 1
            continue
        if not (0 <= _r['src'] < _N and 0 <= _r['dst'] < _N):
            acct['oob'] += 1
            continue
        _ss = RID2SID[_ch].get(_r['src'])
        _tt = RID2SID[_ch].get(_r['dst'])
        if not _ss or not _tt:
            acct['unreg'] += 1
            continue
        if (_ss, _tt) in OTHER:
            acct['already'] += 1
            continue
        if (_ss, _tt) in _seen:
            acct['dup'] += 1
            continue
        _seen.add((_ss, _tt))
        should.add((_ss, _tt))
        should_rows.append((_ch, _via, _r, _ss, _tt, _mkobj.get(_r['dst']) or {}))

check(u'B0 ★★ 守恒：%d 条原始分支 = %d（第168轮已收）+ %d（未登记）+ %d（已有别的门）'
      u' + %d（重复）+ %d（本轮）'
      % (EXPECT_RAW, EXPECT_IN_168, EXPECT_UNREG, EXPECT_ALREADY,
         EXPECT_DUP, EXPECT_N),
      acct['raw'] == EXPECT_RAW and acct['in_168'] == EXPECT_IN_168
      and acct['unreg'] == EXPECT_UNREG and acct['already'] == EXPECT_ALREADY
      and acct['dup'] == EXPECT_DUP and len(should) == EXPECT_N
      and acct['oob'] == 0,
      u'实测 %r / 重推唯一边 %d' % (dict(acct), len(should)))

check(u'B1 ★★★ **独立重推 == 产品本轮段**（双向差集都空）',
      should == PAIRS,
      u'重推 %d / 产品 %d / 多写 %r / 漏写 %r'
      % (len(should), len(PAIRS), sorted(should - PAIRS)[:3],
         sorted(PAIRS - should)[:3]))

#: ★ 每条规则都必须能回溯到**具体一条分支**（chapter/via/src/dst/entrance 四项对齐）。
#:   只比 (when_scene, to) 是不够的 —— 目标对得上、来源门搞错一样是错。
_byrow = {}
for _ch, _via, _r, _ss, _tt, _mkobj in should_rows:
    _byrow[(_ss, _tt)] = (_ch, _via, _r['code'], _r['src'], _r['dst'], _r['entrance'])
_trace_bad = []
for _r in MINE:
    _o = _r.get('_original') or {}
    _want = (_o.get('chapter'), _o.get('via'), _o.get('table'),
             _o.get('src_room_id'), _o.get('dst_room_id'), _o.get('entrance'))
    _got = _byrow.get((_r.get('when_scene'), _r.get('to')))
    if _got != _want:
        _trace_bad.append((_r.get('to'), _want, _got))
check(u'B2 ★★ 每条规则的 (章, 门对象, 代码名, 源房, 目标房, entrance) 都能回溯到具体一条分支',
      not _trace_bad, u'对不上 %d: %r' % (len(_trace_bad), _trace_bad[:2]))

# ===========================================================================
print('')
print('=' * 70)
print(u'C 段  落点自证（真实对象名，大小写敏感）')
print('=' * 70)

_c_bad = []
_c_cnt = collections.Counter()
for _ch, _via, _r, _ss, _tt, _mkobj in should_rows:
    _L = (_r.get('letter') or '').lower()
    if _L and _L in _mkobj:
        _c_cnt['letter'] += 1
    elif any(_a in _mkobj for _a in ANY):
        _c_cnt['any'] += 1
    elif not _mkobj:
        _c_cnt['nomarker'] += 1
    else:
        _c_cnt['mismatch'] += 1

check(u'C1 落点分桶：字母命中 %d + 通用 Any %d + 目标房零 marker %d + 字母不符 %d = %d'
      u'（零 marker 那 2 条因**目标房未登记成场景**已被 B0 的 unreg 挡掉，'
      u'所以本桶为 0 —— 不是"没查"）'
      % (_c_cnt['letter'], _c_cnt['any'], _c_cnt['nomarker'],
         _c_cnt['mismatch'], sum(_c_cnt.values())),
      sum(_c_cnt.values()) == EXPECT_N and _c_cnt['letter'] > 0
      and _c_cnt['any'] > 0 and _c_cnt['mismatch'] > 0,
      u'%r' % (dict(_c_cnt),))

#: ★★★ 最强的一条：每条规则的 `marker` 必须**真的出现在目标房的对象表里**
#:   （大小写敏感，不是拼字符串）。第125轮就是拼 `'obj_marker' + 'W'` 拼出了
#:   一个不存在的对象名，于是整类门被判"证据不足"。
_c2_bad = []
for _r in MINE:
    _o = _r.get('_original') or {}
    _m = _o.get('marker')
    if _m is None:
        continue
    _ch = _o.get('chapter')
    _inst = None
    for _c, _cf, _inf in CH:
        if _c == _ch:
            _inst = _jl(os.path.join(EV42, _inf))
    _objs = set()
    for _room in _inst['rooms']:
        if _room['index'] == _o.get('dst_room_id'):
            _objs = set(x.get('obj') for x in _room['insts'])
            break
    if _m not in _objs:
        _c2_bad.append((_r.get('to'), _m))
check(u'C2 ★★★ 每条规则的 `marker` **真的出现在目标房对象表里**（大小写敏感，不拼字符串）',
      not _c2_bad, u'对不上 %d: %r' % (len(_c2_bad), _c2_bad[:3]))

_wrong = [r.get('to') for r in MINE
          if (r.get('_original') or {}).get('marker') == 'obj_markerW']
check(u'C3 ★★ 负控制：大写 `obj_markerW` 条数 == 0（该对象名在游戏里**不存在**）',
      len(_wrong) == 0, u'实测 %d' % len(_wrong))

# ===========================================================================
print('')
print('=' * 70)
print(u'D 段  关联口径与反回滚')
print('=' * 70)

#: 一房多出口：产品侧 `route_for_door(sid, letter)` 每个 (场景, 门字母) 只返回
#: **一个**目标。本轮按"照原作"写入了同一场景的多条 W 边 ⇒ 该场景运行时只会
#: 生效其中一条。这是**产品侧限制**，不是数据错误 —— 本判据把它**点清数目**，
#: 免得将来有人以为"每条都会生效"。
_multi = [k for k, v in collections.Counter(
    r.get('when_scene') for r in MINE).items() if v > 1]
check(u'D1 一房多出口场景 %d 个（运行时每场景只生效一条；根治要"位置级落点"，本轮不做）'
      % len(_multi),
      len(_multi) == 37,
      u'实测 %d' % len(_multi))

#: 反回滚：本轮之后全表不许缩水
check(u'D2 ★★ 反回滚：全表 %d 条 ≥ %d；本轮段 %d 条 ≥ %d'
      % (EXPECT_ROUTES, EXPECT_ROUTES, EXPECT_N, EXPECT_N),
      len(RL) >= EXPECT_ROUTES and len(MINE) >= EXPECT_N,
      u'routes=%d mine=%d' % (len(RL), len(MINE)))

#: 与第168轮分账：那 88 条必须**一条不少、一条不改**
_old = [r for r in RL
        if (r.get('_original') or {}).get('via') in W_VIA
        and not (r.get('_original') or {}).get('batch')]
_old_p = sorted(r.get('priority') for r in _old)
check(u'D3 ★★★ 第168轮那 88 条**原样保留**（priority 7000~7087 连续、无 batch 标记）',
      len(_old) == 88 and _old_p == list(range(7000, 7088)),
      u'n=%d 首末=%r' % (len(_old),
                        (_old_p[0], _old_p[-1]) if _old_p else (None, None)))

print('')
print('=' * 70)
print(u'结果：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _bad:
    print(u'失败项：')
    for b in _bad:
        print(u'  - %s' % b)
print('=' * 70)
sys.exit(1 if _n['f'] else 0)
