# -*- coding: utf-8 -*-
u"""第168轮回归锁：Deltarune 五章的 **W 门** 不许再被整类拒收。

## 这一轮做了什么

第125轮以「证据不足」把 W 门**整类拒收**（产品里 W 一条都没有），理由是：

    obj_markerw 仅 60.2%、obj_markerX 84.3%，无一套到 100%

第126轮把门槛更正为「机制 + 在场 ≈ 90% 以上，且每一条不中都能逐条归因」，
并写明 W 不收的真因是「两套 marker 写法归不了因」。

本轮把"归不了因"查清了，结论是**当年两次都量错了对象**：

* 产品里 W 的出生点对象名是**小写** `obj_markerw`（sprite 却是专属的
  `spr_markerW`，与 A~F 同族）—— 拿 `'obj_marker' + 'W'` 去比 ⇒ 恒 0%；
* `obj_markerX` 是**字母 X 的**出生点（`spr_markerX`），**不是通用兜底**；
  真通用的是 `obj_markerAny`（`spr_markerAny`）—— 拿 X 比 ⇒ 84.3% 是个混账数。

机制侧同一次反汇编：`obj_doorW_Alarm_2` 的骨架与 A/B/C/D/X **逐句同形**
（先给 `entrance` 赋值 → `instance_create` → 一串 `if (room == N) room_goto(M)`）。

⇒ 本轮补收 **88** 条（priority 7000~7087，`kind=delta_door_table`）。

## ★★★ 一条必须记住的坑：`entrance` 不是"每类门一个常量"

    ch1  obj_doorW_Alarm_2            entrance = 23       ins =   58
    ch2  obj_doorW_Alarm_2            entrance = 24       ins = 1805
    ch2  obj_doorw_musfade_Alarm_2    entrance = 20       ins =  180

ch1 里它恰好等于字母序（W=23），**于是很容易得出"W ⇒ entrance=23"这个错结论**。
ch2 就把它推翻了：同一扇 `obj_doorW` 给 24，它的 musfade 变体给 20。
真语义是「**新房间里第 N 个字母的出生点**」，每个 `if (room == N)` 分支各自指定。
⇒ 可以说"W 与 A/B/C/D/X 同机制"，**不可以**把判据建在 `entrance` 的数值上。
本套件 `E6` / `E7` 就是钉这一条的。

## 本套件守什么（零 Qt / 零网络 / 零外部盘）

A 段位与分母 —— 88 条 · priority 7000~7087 连续 · 只落 ch1~ch5 · marker 只用实测名
B 独立重推   —— **另写一份推导**（不 import 生成器）⇒ 与产品段**集合相等**
C 逐条自洽   —— 两端下标 / 查表 / **目标房真有那个 marker** / 章前缀 / 声明序
D 拒收纪律   —— 7 条逐条留档：6 条"落点不是 W" + 1 条"目标房零 marker"，**成对**
E 证据自证   —— 直接读 `doors168.json`，把"A 段判据依据的事实"本身也锁住
F 自检       —— AST 查恒真 / 单一 harness / 判据名不带计数 / 格式 / 分母闸 / 零外部盘

## 纪律

`print('[PASS] %s')` 字面量；正/负控制成对；**断行为不断赋值**；负控制必须
**真的落进被测分支**（B5/B6 换一把尺重跑同一段推导；D3 改一个数据点重跑同一段推导）。
"""
import ast
import collections
import io
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.environ.get('CQ_PKG168') or os.path.join(REPO, 'ralsei_pet')
SCENES = os.path.join(PKG, 'assets', 'scenes')
#: ★ 四个口子只给 `mutate168.py` 用：把产品表 / 证据 / 包目录换成**副本**，
#:   判据本身一行不改。（没有这些口子，变异测试只能改真表 ⇒ 一崩就把工作区弄脏，
#:   还得靠 git 还原；而把判据副本放 temp 时，它按 `__file__` 推出的路径全是错的。）
ROUTES_P = os.environ.get('CQ_ROUTES168') or os.path.join(SCENES, '_routes.json')
EV42 = os.environ.get('CQ_EV42') or os.path.join(
    REPO, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
GRAPH_P = os.path.join(EV42, '_room_graph.json')
DOORS_P = os.environ.get('CQ_DOORS168') or os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')),
    '_evidence', 'doors168.json')
GEN_P = os.environ.get('CQ_GEN168') or os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')),
    '_tools', 'gen_routes168.py')

for _p in (PKG, os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from modules import scene_system as SS       # noqa: E402

LETTER = 'W'
PRIO_BASE = 7000
KIND = 'delta_door_table'
#: W 门的两个门对象（UTMT 里的名字；`obj_doorw_musfade` 是小写 w）
W_VIA = ('obj_doorW', 'obj_doorw_musfade')
#: 出生点：**小写** `obj_markerw`（字母 W）与真通用 `obj_markerAny*`
MARK_LETTER = 'obj_markerw'
MARK_ANY = ('obj_markerAny', 'obj_markerAny40px')
#: ★ 钉死（证据侧）：`_room_graph.json` 里 W 边 98 条
EXPECT_EVID = 98
#: 98 = 91 可用（机制+落点+两端登记都过）+ 7 落点不自证
EXPECT_AVAIL = 91
EXPECT_REFUSED = 7
#: 91 可用 = 90 唯一边 + 1 重复实例（同一间房的门被第42轮数了两遍）
EXPECT_KEEP_DISTINCT = 90
#: 90 唯一边 = 88 收 + 2 已由别的门（A/B 位移门）提供同一目标
EXPECT_W = 88
EXPECT_ALREADY = 2
EXPECT_LETTER = 72
EXPECT_ANY = 16
EXPECT_ROUTES = 1930
EXPECT_SCENES = 2166

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
    u"""读证据 JSON。★ 第42轮那批文件里 `true/false` 是**大写开头**的（非严格 JSON）。"""
    s = io.open(path, encoding='utf-8', newline='').read()
    return json.loads(s.replace(': True', ': true').replace(': False', ': false'))


# ===========================================================================
print('')
print('=' * 66)
print(u'A 段  段位与分母（防空集恒真）')
print('=' * 66)

RAW = json.loads(io.open(ROUTES_P, encoding='utf-8', newline='').read())
RL = RAW.get('routes') or []
IDX = SS.load_index(SCENES)
SCN = IDX.get('scenes') or {}
W_RULES = [r for r in RL
           if (r.get('_original') or {}).get('via') in W_VIA
           #: ★★★ 第169轮分账：本轮又落了 102 条**分支级** W 边（带 `batch: 169`）。
           #:   它们是另一批证据（按分支解析，不是 `_room_graph` 的那 98 条），
           #:   由 `check169` 管。这里必须排除，否则本套件的 88 条历史结论会被冲掉
           #:   —— 「分账 ≠ 放宽」：过滤掉，但下方 A0 的分母要如实长到 1,930。
           and not (r.get('_original') or {}).get('batch')]
W_PAIRS = set((r.get('when_scene'), r.get('to')) for r in W_RULES)

check(u'A0 分母：`load_index()` ok=True、场景数 == %d、路由 == %d 条、W 段非空'
      % (EXPECT_SCENES, EXPECT_ROUTES),
      IDX.get('ok') is True and len(SCN) == EXPECT_SCENES
      and len(RL) == EXPECT_ROUTES and len(W_RULES) > 0,
      u'scenes=%d routes=%d w=%d ok=%r'
      % (len(SCN), len(RL), len(W_RULES), IDX.get('ok')))

_prios = sorted(r.get('priority') for r in W_RULES)
check(u'A1 ★★★ W 段 %d 条、priority %d~%d **连续无空洞**'
      % (EXPECT_W, PRIO_BASE, PRIO_BASE + EXPECT_W - 1),
      len(W_RULES) == EXPECT_W
      and _prios == list(range(PRIO_BASE, PRIO_BASE + EXPECT_W)),
      u'n=%d 首末=%r' % (len(W_RULES), (_prios[0], _prios[-1])))

_CH = set(('ch%d' % i) for i in range(1, 6))
_oob = sorted(set(str(r.get('when_scene') or '').split('.')[0] for r in W_RULES) - _CH)
check(u'A2 ★★★ W 段只落 ch1~ch5（绝不碰 desktop / oneshot / ut / outertale / uty）',
      not _oob, u'越界=%r' % (_oob,))

_badseg = [r.get('to') for r in W_RULES
           if r.get('when_door') != LETTER
           or (r.get('_original') or {}).get('kind') != KIND
           or (r.get('_original') or {}).get('door_letter') != LETTER
           or (r.get('_original') or {}).get('via') not in W_VIA]
check(u'A3 W 段 `when_door` / `door_letter` 全为 W、`kind` 全为 `%s`、'
      u'`via` 只有那两种门对象' % KIND,
      not _badseg, u'异常 %d: %r' % (len(_badseg), _badseg[:3]))

_mk = collections.Counter((r.get('_original') or {}).get('marker') for r in W_RULES)
_fake = [r.get('to') for r in W_RULES
         if (r.get('_original') or {}).get('marker') not in (MARK_LETTER,) + MARK_ANY]
check(u'A4 ★★★ `marker` 只用**实测**对象名（`%s` %d + `obj_markerAny` %d = %d）；'
      u'**大写 `obj_markerW` 一条都不许有**（那是第125轮量错的那把尺）'
      % (MARK_LETTER, EXPECT_LETTER, EXPECT_ANY, EXPECT_W),
      not _fake and _mk.get(MARK_LETTER) == EXPECT_LETTER
      and sum(_mk.get(a) or 0 for a in MARK_ANY) == EXPECT_ANY
      and (_mk.get('obj_markerW') or 0) == 0,
      u'实测 %r / 异常 %r' % (dict(_mk), _fake[:3]))

check(u'A5 W 段 `(when_scene, to)` 无重复（同一扇门同一个目标只许一条）',
      len(W_PAIRS) == len(W_RULES), u'条 %d / 唯一 %d' % (len(W_RULES), len(W_PAIRS)))

_tbl_bad = [r.get('to') for r in W_RULES
            if (r.get('_original') or {}).get('table')
            != 'gml_Object_%s_Alarm_2' % (r.get('_original') or {}).get('via')]
check(u'A6 `table` 逐条等于 `gml_Object_<via>_Alarm_2`（机制名与门对象不许对不上）',
      not _tbl_bad, u'异常 %d: %r' % (len(_tbl_bad), _tbl_bad[:3]))

# ===========================================================================
print('')
print('=' * 66)
print(u'B 段  独立重推（另一套实现：只从证据算，不 import 生成器）')
print('=' * 66)

GRAPH = (_jl(GRAPH_P) or {}).get('chapters') or {}
CHAPTERS = [('ch1', 'inst42.json', 'conn42b.json')] + [
    ('ch%d' % i, 'ch%d_inst42.json' % i, 'ch%d_conn42b.json' % i) for i in (2, 3, 4, 5)]

#: 章 → 房号 → 该房的对象名元组；章 → code 名 → {src: dst}；章 → 房名表
EVID = {}
for _cid, _inf, _cnf in CHAPTERS:
    _inst = _jl(os.path.join(EV42, _inf))
    _conn = _jl(os.path.join(EV42, _cnf))
    _obj = {}
    for _r in (_inst.get('rooms') or []):
        _obj[_r.get('index')] = tuple(_x.get('obj') for _x in (_r.get('insts') or []))
    _tab = collections.defaultdict(dict)
    for _it in (_conn.get('items') or []):
        if _it.get('op') == 'goto' and isinstance(_it.get('src'), int) and _it['src'] >= 0:
            _tab[_it.get('code')][_it['src']] = _it.get('dst')
    EVID[_cid] = {'obj': _obj, 'tab': dict(_tab), 'names': _conn.get('room_names') or []}

#: 原作房间下标 → scene_id（**按章分槽**；跨章共用下标是常态）
RID2SID = collections.defaultdict(dict)
for _sid, _rec in SCN.items():
    if not isinstance(_rec, dict):
        continue
    _rid = _rec.get('original_room_id')
    if isinstance(_rid, int):
        RID2SID[_sid.split('.')[0]].setdefault(_rid, _sid)


def _landing_ok(objs, rule='product'):
    u"""落点自证。`rule` 就是"用哪把尺" —— 三条，两条是错的（留着当负控制）。

    ★★★ `obj_markerw` 是**小写**：产品里对象名如此，sprite 才是 `spr_markerW`。
      所以 `product` 这把尺做**大小写不敏感**比对。
    """
    low = set(str(o).lower() for o in objs)
    if rule == 'product':
        return MARK_LETTER in low or any(a in objs for a in MARK_ANY)
    if rule == 'letter_x':
        # 第125轮那把错尺：把 X 的专属出生点当成"通用兜底"
        return 'obj_markerx' in low
    if rule == 'upper':
        # 大小写敏感地找大写 obj_markerW —— 产品里根本没有这个名字
        return 'obj_markerW' in objs
    raise ValueError(rule)


def _recompute(rule='product', ev_override=None):
    u"""从证据重推 W 边。返回 `(keep, refused, unreg)` 三个桶。

    与生成器分开写（**不 import `gen_routes168`**）：这里先建"房号 → 对象元组"
    和"code → 查表"，再逐个 `edge` 过三关（查表一致 / 落点自证 / 两端已登记）。

    `ev_override` 只给 D3 的负控制用：换掉某一章的证据再跑**同一段逻辑**，
    而不是另写一条判据 —— 否则"负控制"考的是新判据，不是被测那段。

    ★ 三个桶**各自点名**，不许"不 keep 就算了"：`unreg` 这条闸在第125轮那批
      缺口的复盘里就是"看不出漏在哪"的根源（落点不自证 vs 目标房没登记，
      两种缺口的处置完全不同）。
    """
    keep, refused, unreg = [], [], []
    for _cid, _inf, _cnf in CHAPTERS:
        _ev = (ev_override or {}).get(_cid) or EVID[_cid]
        for _e in ((GRAPH.get(_cid) or {}).get('edges') or []):
            if _e.get('door') not in W_VIA:
                continue
            _code = 'gml_Object_%s_Alarm_2' % _e.get('door')
            if _ev['tab'].get(_code, {}).get(_e.get('src')) != _e.get('dst'):
                continue
            if not _landing_ok(_ev['obj'].get(_e.get('dst'), ()), rule):
                refused.append((_cid, _e.get('src'), _e.get('dst')))
                continue
            _s = RID2SID[_cid].get(_e.get('src'))
            _t = RID2SID[_cid].get(_e.get('dst'))
            if _s and _t:
                keep.append((_s, _t))
            else:
                unreg.append((_cid, _e.get('src'), _e.get('dst'),
                              bool(_s), bool(_t)))
    return keep, refused, unreg


# ---- B0 证据侧分母 ----
_EV_EDGES = []
for _cid, _inf, _cnf in CHAPTERS:
    for _e in ((GRAPH.get(_cid) or {}).get('edges') or []):
        if _e.get('door') in W_VIA:
            _EV_EDGES.append((_cid, _e))
check(u'B0 分母：`_room_graph.json` 里 W 边 == %d 条（防空集恒真）' % EXPECT_EVID,
      len(_EV_EDGES) == EXPECT_EVID, u'实测 %d' % len(_EV_EDGES))

# ---- B1 机制自证：查表必须一致 ----
_mech_bad = []
for _cid, _e in _EV_EDGES:
    _code = 'gml_Object_%s_Alarm_2' % _e.get('door')
    if EVID[_cid]['tab'].get(_code, {}).get(_e.get('src')) != _e.get('dst'):
        _mech_bad.append((_cid, _e.get('src'), _e.get('dst')))
check(u'B1 机制自证：%d 条 W 边**全部**能在 `conn42b` 的 `{src: dst}` 里查到同一个目标'
      u'（这是"W 与 A/B/C/D/X 同机制"的数据面证明）' % EXPECT_EVID,
      not _mech_bad, u'不符 %d: %r' % (len(_mech_bad), _mech_bad[:3]))

# ---- B2 落点自证 ----
_KEEP, _REFUSED, _UNREG = _recompute('product')
_KEEP_SET = set(_KEEP)
check(u'B2 落点自证（同一把尺）：可用 %d 条 / 落点不自证 %d 条（%d + %d = %d，一条不少）'
      % (EXPECT_AVAIL, EXPECT_REFUSED, EXPECT_AVAIL, EXPECT_REFUSED, EXPECT_EVID),
      len(_KEEP) == EXPECT_AVAIL and len(_REFUSED) == EXPECT_REFUSED
      and len(_KEEP) + len(_REFUSED) + len(_UNREG) == EXPECT_EVID,
      u'可用 %d（唯一 %d）/ 拒收 %d / 未登记 %d'
      % (len(_KEEP), len(_KEEP_SET), len(_REFUSED), len(_UNREG)))

# ---- B3 ★★★ 独立重推 == 产品段 ----
_other_pairs = set((r.get('when_scene'), r.get('to')) for r in RL
                   if (r.get('_original') or {}).get('via') not in W_VIA)
_ALREADY = set(p for p in _KEEP_SET if p in _other_pairs)
_should = _KEEP_SET - _ALREADY
check(u'B3 ★★★ **独立重推 == 产品 W 段**（双向差集都空；重推 %d 唯一边 − 已由别的门提供的 %d = %d）'
      % (len(_KEEP_SET), len(_ALREADY), EXPECT_W),
      _should == W_PAIRS and len(_ALREADY) == EXPECT_ALREADY,
      u'重推 %d / 产品 %d / 多写 %r / 漏写 %r'
      % (len(_should), len(W_PAIRS), sorted(_should - W_PAIRS)[:3],
         sorted(W_PAIRS - _should)[:3]))

# ---- B4 守恒账 ----
check(u'B4 ★★ 守恒：%d 边可用 %d = 唯一边 %d + 重复实例 %d；唯一边 %d = 收录 %d + 已有同目标 %d'
      % (EXPECT_EVID, EXPECT_AVAIL, EXPECT_KEEP_DISTINCT,
         EXPECT_AVAIL - EXPECT_KEEP_DISTINCT, EXPECT_KEEP_DISTINCT,
         EXPECT_W, EXPECT_ALREADY),
      len(_KEEP) - len(_KEEP_SET) == EXPECT_AVAIL - EXPECT_KEEP_DISTINCT
      and len(_KEEP_SET) - len(_ALREADY) == EXPECT_W,
      u'重复 %d / 已有 %d' % (len(_KEEP) - len(_KEEP_SET), len(_ALREADY)))

# ---- B5 负控制 ①：第125轮那把错尺 ----
_X_KEEP, _X_REF, _X_UNREG = _recompute('letter_x')
_X_SET = set(_X_KEEP)
_over = _X_SET - _KEEP_SET          # 错尺**多认**的（产品明确拒收的那些）
_lost = _KEEP_SET - _X_SET          # 错尺**少认**的
check(u'B5 ★★★ 负控制：换成第125轮那把尺（只认 `obj_markerX`）⇒ 重推集合与产品**两边都不等**'
      u'（多认 %d / 少认 %d）—— 证明 B3 不是"随便怎么算都相等"' % (len(_over), len(_lost)),
      bool(_over) and bool(_lost),
      u'错尺 %d 唯一边 / 多认 %d / 少认 %d' % (len(_X_SET), len(_over), len(_lost)))

# ---- B6 负控制 ②：大小写敏感认大写 ----
_UP_KEEP, _UP_REF, _UP_UNREG = _recompute('upper')
check(u'B6 ★★★ 负控制：大小写敏感地找大写 `obj_markerW` ⇒ 重推 **0** 条、拒收 %d 条'
      u'（这正是第125轮报的那个 0%% —— 当年"量不出"不是没数据，是名字打错了大小写）'
      % EXPECT_EVID,
      len(_UP_KEEP) == 0 and len(_UP_REF) == EXPECT_EVID,
      u'实得 %d 条 / 拒收 %d' % (len(_UP_KEEP), len(_UP_REF)))

# ---- B7 正控制：product 这把尺两类落点都认得出 ----
_L_KEEP = [p for p in _KEEP]
_p_letter = sum(1 for r in W_RULES if (r.get('_original') or {}).get('marker') == MARK_LETTER)
_p_any = len(W_RULES) - _p_letter
check(u'B7 正控制：product 这把尺**两类落点都认**（同字母 %d + 通用 Any %d，两类都必须非空）'
      % (EXPECT_LETTER, EXPECT_ANY),
      _p_letter == EXPECT_LETTER and _p_any == EXPECT_ANY
      and len(_L_KEEP) > 0,
      u'实得 同字母 %d / 通用 %d' % (_p_letter, _p_any))

# ===========================================================================
print('')
print('=' * 66)
print(u'C 段  逐条自洽（产品侧独立查一遍证据）')
print('=' * 66)

_c1, _c2, _c3, _c4, _c5, _c6 = [], [], [], [], [], []
for _i, _r in enumerate(W_RULES):
    _o = _r.get('_original') or {}
    _s_rec = SCN.get(_r.get('when_scene')) or {}
    _d_rec = SCN.get(_r.get('to')) or {}
    if not (_s_rec.get('original_room_id') == _o.get('src_room_id')
            and _d_rec.get('original_room_id') == _o.get('dst_room_id')):
        _c1.append(_r.get('to'))
    _cid = _o.get('chapter')
    _ev = EVID.get(_cid) or {}
    # ★★ 用规则**自己声明的** `table`（它说"我读的是这段代码"），不是从 `via`
    #  重新拼一遍 —— 后者会让"报错了表"这件事查不出来（第168轮 M4 抓出来的缺口：
    #  第一版用 via 拼 code，把 table 换成 X 门那段后 C2 照样绿）。
    if (_ev.get('tab') or {}).get(_o.get('table'), {}).get(_o.get('src_room_id')) \
            != _o.get('dst_room_id'):
        _c2.append(_r.get('to'))
    if (_o.get('marker'),) not in [(_m,) for _m in (_ev.get('obj') or {}).get(_o.get('dst_room_id'), ())]:
        _c3.append(_r.get('to'))
    if str(_r.get('when_scene') or '').split('.')[0] != _cid:
        _c4.append(_r.get('to'))
    if _r.get('priority') != PRIO_BASE + _i:
        _c5.append(_r.get('to'))
    _why = str(_r.get('reason') or '')
    if (_o.get('marker') not in _why) or ('obj_markerW' in _why):
        _c6.append(_r.get('to'))

check(u'C1 每条 W 规则两端的 scene `original_room_id` 与 `_original` 逐条相等',
      not _c1, u'异常 %d: %r' % (len(_c1), _c1[:3]))
check(u'C2 每条 `(src_room_id, dst_room_id)` 真在**它自己声明的** `table` 查表里'
      u'（机制边不是编的，也不是"报错了表"）',
      not _c2, u'异常 %d: %r' % (len(_c2), _c2[:3]))
check(u'C3 ★★★ 每条的目标房**真的摆着** `_original.marker` 那个对象（在场，不是"应该会有"）',
      not _c3, u'异常 %d: %r' % (len(_c3), _c3[:3]))
check(u'C4 `_original.chapter` 与 `when_scene` 的章前缀一致（不许张冠李戴）',
      not _c4, u'异常 %d: %r' % (len(_c4), _c4[:3]))
check(u'C5 priority 按声明序 == %d + i（逐条升、无空洞）' % PRIO_BASE,
      not _c5, u'异常 %d: %r' % (len(_c5), _c5[:3]))
check(u'C6 `reason` 里写了**实测** marker 名，且没有那套假大写 `obj_markerW`（文案不许造假）',
      not _c6, u'异常 %d: %r' % (len(_c6), _c6[:3]))

# ===========================================================================
print('')
print('=' * 66)
print(u'D 段  拒收纪律：7 条逐条留档（成对，不靠"反正没收"）')
print('=' * 66)

check(u'D0 落点不自证**恰好 %d 条**（多一条少一条都要人工看）' % EXPECT_REFUSED,
      len(_REFUSED) == EXPECT_REFUSED, u'实测 %d' % len(_REFUSED))

_other_marker = []
_empty_room = []
for _cid, _srid, _drid in _REFUSED:
    _objs = EVID[_cid]['obj'].get(_drid, ())
    _low = set(str(o).lower() for o in _objs)
    if not _objs:
        _empty_room.append((_cid, _srid, _drid))
        continue
    # 目标房里有**别的** marker（A~V/X/cup…）—— 即"这房有出生点，但不是 W 的"
    if any(str(o).startswith('obj_marker') and str(o).lower() != MARK_LETTER
           and str(o) not in MARK_ANY for o in _objs) or 'obj_charmarker' in _low:
        _other_marker.append((_cid, _srid, _drid))

check(u'D1 其中 %d 条的目标房**有别的 marker**（`obj_markerX` / A/B/D/t/u 等）'
      u'⇒ 拒收理由不是"没落点"，是"落点不是 W"' % (EXPECT_REFUSED - 1),
      len(_other_marker) == EXPECT_REFUSED - 1,
      u'实测 %d 条' % len(_other_marker))
check(u'D2 其中 1 条的目标房**零 marker**（商店空壳 `room_shop_ch2_swatch`，连房都不像房）',
      len(_empty_room) == 1, u'实测 %r' % (_empty_room,))

# ---- D3 负控制：给那间空房补一个 obj_markerw ⇒ 它**不再**被判拒收 ----
_NEG_ROOM = _empty_room[0][2] if _empty_room else -1
_NEG_CID = _empty_room[0][0] if _empty_room else 'ch2'
_ev2 = dict(EVID[_NEG_CID])
_ev2['obj'] = dict(EVID[_NEG_CID]['obj'])
_ev2['obj'][_NEG_ROOM] = tuple(_ev2['obj'].get(_NEG_ROOM, ())) + (MARK_LETTER,)
_keep2, _ref2, _unreg2 = _recompute('product', {_NEG_CID: _ev2})
check(u'D3 ★★★ 负控制：给那间零 marker 的房**补一个** `%s` ⇒ 同一条边不再被判"落点不自证"'
      u'（拒收 %d → %d），而是**落到下一道闸**「目标房未登记」（未登记 %d → %d）'
      u'—— 两道缺口分工明确，拒收 %d 条里没有一条是"被误丢"'
      % (MARK_LETTER, len(_REFUSED), len(_ref2), len(_UNREG), len(_unreg2), EXPECT_REFUSED),
      len(_ref2) == len(_REFUSED) - 1 and len(_unreg2) == len(_UNREG) + 1
      and len(_keep2) == len(_KEEP),
      u'实得 拒收 %d / 未登记 %d / 可用 %d' % (len(_ref2), len(_unreg2), len(_keep2)))

check(u'D4 ★★ 那 7 条里**没有**"落点看着像 W、其实目标房没登记"的漏（未登记桶必须是空的）——'
      u'否则拒收数会被登记缺口顶替，账就假了',
      not _UNREG, u'未登记 %d: %r' % (len(_UNREG), _UNREG[:3]))

# ===========================================================================
print('')
print('=' * 66)
print(u'E 段  证据自证（A 段判据依据的**事实**本身也锁住）')
print('=' * 66)

DOORS = (_jl(DOORS_P) or {}).get('chapters') or {}
_D1 = (DOORS.get('ch1') or {}).get('marker_objects') or {}
_D2 = (DOORS.get('ch2') or {}).get('marker_objects') or {}
_E1 = (DOORS.get('ch1') or {}).get('door_entrance') or {}
_E2 = (DOORS.get('ch2') or {}).get('door_entrance') or {}

check(u'E1 ★★★ `obj_markerw` 的 sprite 是**专属** `spr_markerW`（ch1/ch2 一致）'
      u'—— 它是字母 W 的出生点，与 A~F 同族',
      _D1.get(MARK_LETTER) == 'spr_markerW' and _D2.get(MARK_LETTER) == 'spr_markerW',
      u'ch1=%r ch2=%r' % (_D1.get(MARK_LETTER), _D2.get(MARK_LETTER)))

check(u'E2 ★★★ `obj_markerX` 的 sprite 是 `spr_markerX` ⇒ 它是**字母 X 的**出生点，'
      u'**不是**通用兜底（第125轮拿它当兜底，于是 84.3% 成了混账数）',
      _D1.get('obj_markerX') == 'spr_markerX' and _D2.get('obj_markerX') == 'spr_markerX',
      u'ch1=%r ch2=%r' % (_D1.get('obj_markerX'), _D2.get('obj_markerX')))

check(u'E3 `obj_markerAny` 才是真通用（sprite `spr_markerAny`）；ch1 里没有这个对象'
      u'（如实记录 —— 所以 ch1 那 16 条通用落点全在 ch2 之后）',
      _D2.get('obj_markerAny') == 'spr_markerAny' and 'obj_markerAny' not in _D1,
      u'ch1 有=%r / ch2=%r' % ('obj_markerAny' in _D1, _D2.get('obj_markerAny')))

_shared_x = [k for k in ('obj_markerr', 'obj_markers', 'obj_markert', 'obj_markeru', 'obj_markerv')
             if _D1.get(k) == 'spr_markerX']
_own = [k for k in ('obj_markerr', 'obj_markers', 'obj_markert', 'obj_markeru', 'obj_markerv')
        if _D2.get(k) == 'spr_marker' + k[-1].upper()]
check(u'E4 ch1 的 r/s/t/u/v **共用** `spr_markerX`（%d 个），ch2 各自有专属 sprite（%d 个）'
      u'⇒ "ch1 共用 X" 只是那五张图当时没画，**不能**据此把 X 当占位符' % (5, 5),
      len(_shared_x) == 5 and len(_own) == 5,
      u'ch1 共用 %d / ch2 专属 %d' % (len(_shared_x), len(_own)))

_codes1 = (DOORS.get('ch1') or {}).get('door_codes') or []
_codes2 = (DOORS.get('ch2') or {}).get('door_codes') or []
_want = ['gml_Object_obj_doorW_Alarm_2', 'gml_Object_obj_doorw_musfade_Alarm_2']
check(u'E5 两章的 `door_codes` 里都有 `obj_doorW` 与 `obj_doorw_musfade` 的 `Alarm_2`'
      u'（机制取证真取到那两个对象，不是按名字猜的）',
      all(c in _codes1 for c in _want) and all(c in _codes2 for c in _want),
      u'ch1 缺=%r ch2 缺=%r'
      % ([c for c in _want if c not in _codes1], [c for c in _want if c not in _codes2]))

_w1 = (_E1.get('gml_Object_obj_doorW_Alarm_2') or {}).get('entrance')
_w2 = (_E2.get('gml_Object_obj_doorW_Alarm_2') or {}).get('entrance')
_w2m = (_E2.get('gml_Object_obj_doorw_musfade_Alarm_2') or {}).get('entrance')
check(u'E6 ★★★ `entrance` **不是字母常量**：ch1 的 W 门 %r、ch2 的 W 门 %r、'
      u'ch2 的 musfade 变体 %r —— 三处不一致 ⇒ 判据不许建在它的数值上'
      % (_w1, _w2, _w2m),
      isinstance(_w1, int) and isinstance(_w2, int) and isinstance(_w2m, int)
      and _w1 != _w2 and _w2 != _w2m,
      u'实得 %r / %r / %r' % (_w1, _w2, _w2m))

_i1 = (_E1.get('gml_Object_obj_doorW_Alarm_2') or {}).get('ins') or 0
_i2 = (_E2.get('gml_Object_obj_doorW_Alarm_2') or {}).get('ins') or 0
check(u'E7 ch2 的 W 门指令数 ≥ ch1 的 10 倍（%d vs %d）⇒ ch2 里那一长串 '
      u'`if (room == N)` 分支真实存在（第42轮只当它"一扇门一条边"，才漏了 W 门型）'
      % (_i2, _i1),
      _i1 > 0 and _i2 >= _i1 * 10, u'实测 %d / %d' % (_i1, _i2))

# ===========================================================================
print('')
print('=' * 66)
print(u'F 段  自检')
print('=' * 66)

_SELF_P = os.path.abspath(__file__)
_RAW = open(_SELF_P, 'rb').read()
_SELF_TXT = _RAW.decode('utf-8', 'replace')
check(u'F1 本套件无 BOM / 无 U+FFFD', not _RAW.startswith(b'\xef\xbb\xbf')
      and u'\ufffd' not in _SELF_TXT)

_TREE = ast.parse(_SELF_TXT)
_FUNCS = [n.name for n in _TREE.body if isinstance(n, ast.FunctionDef)]
_TRUES = []
for _node in ast.walk(_TREE):
    if isinstance(_node, ast.Call) and isinstance(_node.func, ast.Name) \
            and _node.func.id == 'check' and len(_node.args) >= 2:
        _a = _node.args[1]
        if isinstance(_a, ast.Constant) and _a.value is True:
            _TRUES.append(_node.lineno)
check(u'F2 本文件没有 `check(x, True)` 恒真判据（AST 判，不扫注释）',
      not _TRUES, u'命中 %r' % (_TRUES[:3],))

check(u'F3 本套件只用 `check()` 一套 harness（`ok()` 的判据不会被 F2 扫到，所以干脆不用）',
      ('check' in _FUNCS) and ('ok' not in _FUNCS), u'顶层函数 %s' % (_FUNCS,))

def _desc_of(node):
    u"""取出 `check(...)` 第一参里的**字面量部分**。

    ★★★ 第168轮踩过的坑：本套件绝大多数判据名是
      `u'A1 ★★★ W 段 %d 条…' % (EXPECT_W, …)` 这种 **BinOp**，不是裸 `ast.Constant`。
      只认 Constant 会数出 21 条（真实 39 条）⇒ 分母闸假红、名字扫描恒空
      （"判据恒真"的反面：**扫描器恒空**，看起来在守、其实没看）。
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp):
        return _desc_of(node.left)
    if isinstance(node, ast.JoinedStr) and node.values:
        return _desc_of(node.values[0])
    return ''


_NAMES = []
for _node in ast.walk(_TREE):
    if isinstance(_node, ast.Call) and isinstance(_node.func, ast.Name) \
            and _node.func.id == 'check' and _node.args:
        _s = _desc_of(_node.args[0])
        if _s:
            _NAMES.append(_s)
# ★ 口径收窄：查的是"共 N 条 / #1"这种**计数标记**，不是"共"这个字
#   —— E4 里合法的「共用」不能被误判（判据过窄=误报，第107/160轮同族）。
_badname = [s for s in _NAMES
            if re.search(r'#\s*\d', s) or re.search(u'共\\s*\\d', s)]
check(u'F4 判据名里不带计数标记（走 AST 取 desc，BinOp 也要拆到左侧字面量）',
      not _badname, u'命中 %r / 取到 %d 条' % (_badname[:3], len(_NAMES)))

check(u'F5 分母闸：判据条数 ≥ 30（防"判据被意外删空还全绿"）',
      len(_NAMES) >= 30, u'实得 %d 条' % len(_NAMES))

_DRV = re.findall(r"[A-Za-z]:[\\/]", _SELF_TXT)
check(u'F6 零外部盘：本文件不出现任何盘符路径（证据全在仓库内）',
      not _DRV, u'命中 %r' % (_DRV[:3],))

_R_BYTES = open(ROUTES_P, 'rb').read()
check(u'F7 `_routes.json` 无 BOM / 全 CRLF / **无尾换行**（第44轮定下的格式）',
      not _R_BYTES.startswith(b'\xef\xbb\xbf')
      and _R_BYTES.count(b'\n') == _R_BYTES.count(b'\r\n')
      and not _R_BYTES.endswith(b'\n'),
      u'crlf=%d bare_lf=%d tail=%r'
      % (_R_BYTES.count(b'\r\n'), _R_BYTES.count(b'\n') - _R_BYTES.count(b'\r\n'),
         _R_BYTES[-6:].decode('utf-8', 'replace').replace('\r', '/r').replace('\n', '/n')))

check(u'F8 生成器在盘（`gen_routes168.py` —— 本套件的重推是**另一份实现**，不 import 它）',
      os.path.isfile(GEN_P) and os.path.getsize(GEN_P) > 3000,
      u'bytes=%d' % (os.path.getsize(GEN_P) if os.path.isfile(GEN_P) else -1))

print('')
print('=' * 66)
print('PASS=%d  FAIL=%d' % (_n['p'], _n['f']))
if _n['f']:
    print(u'失败项：')
    for _x in _bad:
        print(u'  - %s' % _x)
    sys.exit(1)
print('[PASS] 第168轮 W 门补齐回归锁全部通过')
