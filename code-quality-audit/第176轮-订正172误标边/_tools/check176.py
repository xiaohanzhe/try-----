# -*- coding: utf-8 -*-
u"""第176轮判据：订正第172轮那 42 条**误标边**（删除，不升级标签）。

★★★ 本轮判据的重心在哪
---------------------
"删了 42 条边"这件事，光看条数（2,810 -> 2,768）是**证明不了对错**的：
  删少了、删错了、顺手删掉别的，都能凑出 -42。

所以本轮把重心压在三个**各自独立**的量上：

  ① **剩余部分逐条未变**（B5）：拿 `git show HEAD` 的改前副本（不是我自己存的）
     按留档的 42 个 priority 摘掉后，规范化 sha1 必须与**现在**的表逐条相同。
     ⇒ "删的正好是那 42 条，别的一条没动"。
  ② **删掉的是死边**（C1/C2）：3,047 个门物件的 `route_for_door` 结果，
     改前快照与现在**逐值相同**；且"把这 42 条加回去"也**不改变**任何一条。
     ⇒ 它们从来没被消费过。"冗余"不是我说了算，是快照说了算。
  ③ **可整段恢复**（D 段）：加回去 ⇒ 2,810 条、priority 连续无空洞、误标 42 条、
     全表路由同一份快照 ⇒ 留档是**无损**的。
     另外 A6/D3 用第174轮的 `precreate -> obj` 探针**反查**留档的真身（独立一侧），
     证明删的是"真身是变体却被标成 `obj_doorAny`"的边，不是随便 42 条。

★ 负控制（C2 后半）：把一条变体边的 `to` 改掉 ⇒ 快照**必须**变。
  否则 C1 的"逐值相同"就是恒真。

用法：python check176.py
"""
import ast
import collections
import hashlib
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
EV = os.path.join(ROUND, '_evidence')
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
ROUTES_P = os.path.join(SCENES, '_routes.json')
RM_P = os.path.join(EV, 'removed176.json')
SNAP_P = os.path.join(EV, 'snapshot176.json')
BEFORE_P = os.path.join(EV, 'before176.json')
E172 = os.path.join(REPO, 'code-quality-audit', u'第172轮-Any门接线', '_evidence')
SELF = os.path.abspath(__file__)

PKG = os.path.join(REPO, 'ralsei_pet')
for _p in (PKG, os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from modules.item_interact import door_letter_of, route_for_door   # noqa: E402

VAR_SRC = ('obj_doorAnyHorz', 'obj_doorAnyVert')
VIA = 'obj_doorAny'
BATCH = 172
PRIO_BASE = 7300

#: 分母常量（写死 + 判据里独立重算，两边必须相等才会绿）
EXPECT_RM = 42            # 留档条数
EXPECT_BEFORE = 2810      # 改前条数（第174轮之后）
EXPECT_AFTER = 2768       # 改后条数 = 2810 - 42
EXPECT_VIA_BEFORE = 798   # 改前 `via=obj_doorAny` 条数
EXPECT_VIA_AFTER = 756    # 改后 = 798 - 42
EXPECT_VAR = 51           # 第174轮的变体边（42 Horz + 9 Vert），本轮一条不许动
EXPECT_VAR_HORZ = 42
EXPECT_VAR_VERT = 9
EXPECT_HORZ_OF_RM = 36    # 留档里真身是 Horz 的条数
#: ★★★ 第181轮：本轮的判据全部在"**减去 batch=181 那 63 条**"的表上做。
#:   check176 守的是「第176轮删掉那 42 条**没动别的东西**」—— 那是**第181轮之前**的事实。
#:   第181轮按位移 / 实例变量机制又落了 63 条（另一条独立推导线，归 `check181` 守），
#:   混进来会把"其余逐条相同"判成假红。⇒ 判据口径改成"现行表 − 181 段"，
#:   并且**不把 2768 调成 2831**：改的是"拿哪张表去比"，不是把历史数改大。
EXPECT_181 = 63           # 第181轮的净增（只做减法口径的锚点，不并入本条的任何分母）
EXPECT_VERT_OF_RM = 6     # 留档里真身是 Vert 的条数
EXPECT_SNAP_N = 3047      # 全表门物件数（快照键数）
EXPECT_SNAP_HIT = 2898    # 其中解出目标的门物件数
CHECK_FLOOR = 30

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


def jl(p):
    return json.loads(io.open(p, encoding='utf-8', errors='replace',
                              newline='').read())


def canon(rows):
    u"""规范化指纹：与缩进/排版/key 顺序无关，只反映"内容"。"""
    return hashlib.sha1(
        json.dumps(rows, ensure_ascii=False, sort_keys=True,
                   separators=(',', ':')).encode('utf-8')).hexdigest()


def load_objs():
    u"""scene_id -> objects（独立文件 + 区域分片两条来源都读）。"""
    out = {}
    for f in sorted(os.listdir(SCENES)):
        if f.endswith('.json') and not f.startswith('_'):
            d = jl(os.path.join(SCENES, f))
            if isinstance(d, dict) and d.get('scene_id'):
                out[d['scene_id']] = d.get('objects') or []
    for f in sorted(os.listdir(SCENES)):
        if not f.startswith('_zone.'):
            continue
        d = jl(os.path.join(SCENES, f))
        for sid, sc in ((d or {}).get('scenes') or {}).items():
            out[sid] = (sc or {}).get('objects') or []
    return out


def snapshot(RL, OBJS):
    u"""全表路由快照：每个**门类**物件的 `route_for_door` 结果（键含列表下标）。"""
    out = {}
    for sid in sorted(OBJS):
        for i, o in enumerate(OBJS[sid] or []):
            if not isinstance(o, dict):
                continue
            src = o.get('src')
            if not isinstance(src, str) or not src.lower().startswith('obj_door'):
                continue
            pos = o.get('pos')
            out['%s#%d|%s|%s' % (sid, i, src, pos)] = route_for_door(
                RL, sid, door_letter_of(src), src, pos)
    return out


RAW = jl(ROUTES_P)
RL = RAW['routes'] if isinstance(RAW, dict) else RAW
RL = RL or []
RM = jl(RM_P)
REMOVED = RM['items']
SNAP_EV = jl(SNAP_P)
BEFORE = jl(BEFORE_P)

RM_PRIOS = set(r.get('priority') for r in REMOVED)
RM_PAIRS = set((r.get('when_scene'), r.get('to')) for r in REMOVED)
RM_KEYS = set((r.get('when_scene'), r.get('to'),
               (r.get('_original') or {}).get('door_x'),
               (r.get('_original') or {}).get('door_y')) for r in REMOVED)

MINE = [r for r in RL if (r.get('_original') or {}).get('batch') == BATCH]
#: ★★★ 第181轮的两张视图（见 `EXPECT_181` 的注释）
RL_181 = [r for r in RL if (r.get('_original') or {}).get('batch') == 181]
RL_BASE = [r for r in RL if (r.get('_original') or {}).get('batch') != 181]
VIA_ROWS = [r for r in RL if r.get('when_src') == VIA]
VAR_ROWS = [r for r in RL if r.get('when_src') in VAR_SRC]

#: 第174轮的 `precreate -> 真实 obj` 探针（独立一侧，不看产品表）
PC2OBJ = {}
for _ch in ('ch1', 'ch2', 'ch3', 'ch4', 'ch5'):
    _p = os.path.join(E172, 'probe_any172.%s.json' % _ch)
    if not os.path.isfile(_p):
        continue
    for _i in (jl(_p).get('instances') or []):
        if _i.get('creation_code'):
            PC2OBJ[(_ch, _i['creation_code'])] = _i['obj']

print('=' * 70)
print(u'第176轮判据 · 订正第172轮 42 条误标边（删除 + 可恢复）')
print('=' * 70)

# ---------------------------------------------------------------------------
# A 段：留档自洽（"这 42 条到底是什么"）
# ---------------------------------------------------------------------------
print('')
print('=' * 70)
print(u'A 段  留档自洽')
print('=' * 70)

check(u'A0 留档结构：`note` 非空、`count` == 条数 == %d' % EXPECT_RM,
      bool(RM.get('note')) and RM.get('count') == len(REMOVED) == EXPECT_RM,
      u'count=%r len=%d' % (RM.get('count'), len(REMOVED)))

check(u'A1 留档 42 个 priority 两两不同，且全落在 172 段区间 %d~%d 内、无重复'
      % (PRIO_BASE, PRIO_BASE + EXPECT_VIA_BEFORE - 1),
      len(RM_PRIOS) == EXPECT_RM
      and all(isinstance(p, int) and PRIO_BASE <= p <= PRIO_BASE + EXPECT_VIA_BEFORE - 1
              for p in RM_PRIOS),
      u'唯一=%d 范围=%r' % (len(RM_PRIOS),
                            (min(RM_PRIOS), max(RM_PRIOS)) if RM_PRIOS else None))

check(u'A2 留档 42 个 `(场景, 目标)` 对两两不同；`(场景,目标,门坐标)` 也两两不同'
      u'（否则"删 42 条"其实只影响 <42 个去处）',
      len(RM_PAIRS) == EXPECT_RM and len(RM_KEYS) == EXPECT_RM,
      u'pairs=%d keys=%d' % (len(RM_PAIRS), len(RM_KEYS)))

_bad_tag = [r.get('priority') for r in REMOVED
            if r.get('when_src') != VIA
            or (r.get('_original') or {}).get('via') != VIA
            or (r.get('_original') or {}).get('batch') != BATCH
            or (r.get('_original') or {}).get('kind') != 'delta_door_any']
check(u'A3 ★ 留档每条的 `when_src` / `_original.via` 都是 `%s`、`batch` 都是 %d、'
      u'`kind` 都是 `delta_door_any` ⇒ 删的确实是"第172轮那批"里的'
      % (VIA, BATCH),
      not _bad_tag, u'不合 %d 条: %r' % (len(_bad_tag), _bad_tag[:5]))

_need = ('chapter', 'kind', 'table', 'via', 'precreate', 'src_room_name',
         'dst_room_name', 'src_room_id', 'door_x', 'door_y', 'batch')
_bad_f = [(r.get('priority'),
           [k for k in _need if (r.get('_original') or {}).get(k) is None])
          for r in REMOVED]
_bad_f = [x for x in _bad_f if x[1]]
check(u'A4 ★ 留档 `_original` 必备字段齐全（%s）、门坐标是 int'
      % u' / '.join(_need),
      not _bad_f
      and all(isinstance((r.get('_original') or {}).get('door_x'), int)
              and isinstance((r.get('_original') or {}).get('door_y'), int)
              for r in REMOVED),
      u'缺字段 %d 条: %r' % (len(_bad_f), _bad_f[:3]))

#: 探针反查（独立一侧）：留档每条的 `precreate` 在第174轮取证里真身是什么
_rm_obj = [PC2OBJ.get(((r['_original']).get('chapter'),
                       (r['_original']).get('precreate'))) for r in REMOVED]
_rm_unknown = [i for i, o in enumerate(_rm_obj) if o is None]
_rm_horz = sum(1 for o in _rm_obj if o == VAR_SRC[0])
_rm_vert = sum(1 for o in _rm_obj if o == VAR_SRC[1])
check(u'A5 ★★★ 留档真身（用第174轮 `precreate -> obj` 探针反查，**不看产品表**）：'
      u'Horz %d + Vert %d == %d，且**没有一条查不到**'
      % (_rm_horz, _rm_vert, EXPECT_RM),
      not _rm_unknown and _rm_horz == EXPECT_HORZ_OF_RM
      and _rm_vert == EXPECT_VERT_OF_RM
      and _rm_horz + _rm_vert == EXPECT_RM,
      u'Horz=%d Vert=%d 查不到=%d' % (_rm_horz, _rm_vert, len(_rm_unknown)))

check(u'A6 证据自洽：留档 `removed176.json` 与改前副本 `before176.json` 对得上'
      u'（改前 %d 条 - 留档 %d == 剩下 %d）'
      % (BEFORE['before_routes'], EXPECT_RM, BEFORE['rest_n']),
      BEFORE['before_routes'] == EXPECT_BEFORE
      and BEFORE['removed'] == EXPECT_RM
      and BEFORE['rest_n'] == EXPECT_AFTER == EXPECT_BEFORE - EXPECT_RM,
      u'before=%r rest_n=%r' % (BEFORE['before_routes'], BEFORE['rest_n']))

# ---------------------------------------------------------------------------
# B 段：删除确实生效 + 除这 42 条外一字未改
# ---------------------------------------------------------------------------
print('')
print('=' * 70)
print(u'B 段  删除生效 + 其余逐条未变')
print('=' * 70)

_cur_prios = set(r.get('priority') for r in RL)
check(u'B1 ★★ 留档那 %d 个 priority 在现存表里**一个都不在了**' % EXPECT_RM,
      not (RM_PRIOS & _cur_prios),
      u'还在 %d 个: %r' % (len(RM_PRIOS & _cur_prios),
                          sorted(RM_PRIOS & _cur_prios)[:5]))

_cur_prio_172 = set(r.get('priority') for r in MINE)
_holed = sorted(set(range(PRIO_BASE, PRIO_BASE + EXPECT_VIA_BEFORE)) - _cur_prio_172)
check(u'B2 ★★ 172 段 priority 的空洞**恰好**是留档那 42 个（不多不少）'
      u'—— 洞多一个=误删，少一个=没删干净',
      set(_holed) == RM_PRIOS and len(_holed) == EXPECT_RM,
      u'空洞=%d 洞==留档?%r 多出=%r'
      % (len(_holed), set(_holed) == RM_PRIOS,
         sorted(set(_holed) - RM_PRIOS)[:5]))

check(u'B3 条数两套账：现存 %d − 第181轮 %d == 改前 %d - %d；`via=%s` %d == %d - %d'
      % (len(RL), len(RL_181), EXPECT_BEFORE, EXPECT_RM, VIA, len(VIA_ROWS),
         EXPECT_VIA_BEFORE, EXPECT_RM),
      len(RL_BASE) == EXPECT_AFTER and len(RL_181) == EXPECT_181
      and len(VIA_ROWS) == EXPECT_VIA_AFTER
      and len(MINE) == EXPECT_VIA_AFTER,
      u'routes=%d（= %d + 181段 %d）via=%d mine=%d'
      % (len(RL), len(RL_BASE), len(RL_181), len(VIA_ROWS), len(MINE)))

_c_h = sum(1 for r in VAR_ROWS if r.get('when_src') == VAR_SRC[0])
_c_v = sum(1 for r in VAR_ROWS if r.get('when_src') == VAR_SRC[1])
check(u'B4 ★★ 第174轮的变体边**一条没少**：%d 条（Horz %d + Vert %d）'
      % (len(VAR_ROWS), _c_h, _c_v),
      len(VAR_ROWS) == EXPECT_VAR and _c_h == EXPECT_VAR_HORZ
      and _c_v == EXPECT_VAR_VERT,
      u'合计=%d Horz=%d Vert=%d' % (len(VAR_ROWS), _c_h, _c_v))

#: ★★★ B5：拿 `git HEAD` 的改前副本，按留档 priority 摘掉 42 条，剩下的规范化
#:   指纹必须与**现在磁盘上的表**逐条相同。这是"别的一条没动"的硬证明 ——
#:   不是拿我自己的快照跟自己比，改前副本来自 git。
check(u'B5 ★★★ 除这 %d 条外**其余逐条相同**：现状**减去第181轮那 %d 条**后的规范化 '
      u'sha1 == 改前副本摘掉留档后的 sha1' % (EXPECT_RM, len(RL_181)),
      canon(RL_BASE) == BEFORE['rest_sha1'] and len(RL_BASE) == BEFORE['rest_n'],
      u'现状−181段=%s 期望=%s n=%d/%d'
      % (canon(RL_BASE)[:12], BEFORE['rest_sha1'][:12], len(RL_BASE), BEFORE['rest_n']))

#: 负控制：随便改一条现存边的 `to`，B5 的指纹**必须**变（否则 B5 恒真）
if RL:
    _probe = json.loads(json.dumps(RL))
    _probe[0]['to'] = u'__nope__.x.y'
    check(u'B6 负控制：把任意一条现存边的 `to` 改掉 ⇒ 规范化指纹**必须**变'
          u'（证明 B5 有鉴别力，不是"算了个啥都相等"）',
          canon(_probe) != canon(RL),
          u'原=%s 改后=%s' % (canon(RL)[:12], canon(_probe)[:12]))

#: ★★ 这条第一版写成"四元组在现存表里一个都没有"，一跑就红 42 —— **判据的键选错了**：
#:   那 42 条的 `(场景,目标,门坐标)` 与第174轮的变体边**本来就完全重合**（这正是
#:   "纯冗余"的定义），所以四元组必然还在。真正的区分字段是 `when_src`。
#:   改成两句一起说：① 四元组**全部由变体边承接**；② 仍标成 `obj_doorAny` 的一条不剩。
def _has(key, srcs):
    return [r for r in RL if r.get('when_src') in srcs
            and (r.get('when_scene'), r.get('to'),
                 (r.get('_original') or {}).get('door_x'),
                 (r.get('_original') or {}).get('door_y')) == key]


_rm_left = [k for k in RM_KEYS if _has(k, (VIA,))]
_rm_cover = [k for k in RM_KEYS if _has(k, VAR_SRC)]
check(u'B7 ★★★ 内容级交叉验证：那 %d 个 `(场景,目标,门坐标)` 四元组，'
      u'仍标成 `%s` 的 **0 个**，而由变体边承接的 **%d 个**'
      u'（B1/B2 按 priority 查、这条按内容查，三条互不相同的键）'
      % (EXPECT_RM, VIA, EXPECT_RM),
      not _rm_left and len(_rm_cover) == EXPECT_RM,
      u'还标成 any=%d 变体承接=%d/%d'
      % (len(_rm_left), len(_rm_cover), EXPECT_RM))

# ---------------------------------------------------------------------------
# C 段：产品行为零变化（删掉的是死边）
# ---------------------------------------------------------------------------
print('')
print('=' * 70)
print(u'C 段  产品行为零变化（全表扫描）')
print('=' * 70)

OBJS = load_objs()
snap_now = snapshot(RL, OBJS)
#: ★★★ 第181轮：**改前快照是在"第181轮那 63 条还不存在"时录的**，
#:   所以比较必须站在同一张表上 ⇒ 用 `RL_BASE`（现行表 − 181段）重算一次。
#:   否则 48 个门物件会因为"第181轮让它们终于有路可走"而报差异 ——
#:   那是**修好了**，不是"删那 42 条动坏了"。
snap_base = snapshot(RL_BASE, OBJS)
_snap_ev = SNAP_EV['snap']
_diff = [(k, _snap_ev.get(k), snap_base.get(k))
         for k in set(_snap_ev) | set(snap_base)
         if _snap_ev.get(k) != snap_base.get(k)]
check(u'C1 ★★★ 全表路由快照：%d 个门物件（其中 %d 个解出目标）的 `route_for_door`'
      u'结果与改前快照**逐值相同**（在"现行表 − 第181轮 %d 条"上比）'
      % (len(snap_base), sum(1 for v in snap_base.values() if v), len(RL_181)),
      len(snap_base) == EXPECT_SNAP_N and len(_snap_ev) == EXPECT_SNAP_N
      and sum(1 for v in snap_base.values() if v) == EXPECT_SNAP_HIT
      and not _diff,
      u'键=%d/%d 解出=%d 差异=%d（含 181 段的现行表解出 %d）'
      % (len(snap_base), len(_snap_ev), sum(1 for v in snap_base.values() if v),
         len(_diff), sum(1 for v in snap_now.values() if v)))

#: ★★ "纯冗余"的直接证据：把 42 条**加回去**，快照一点不变 ⇒ 它们从来没被消费
snap_back = snapshot(list(RL) + list(REMOVED), OBJS)
_diff_back = [k for k in set(snap_now) | set(snap_back)
              if snap_now.get(k) != snap_back.get(k)]
check(u'C2 ★★★ 把这 42 条**加回去**再跑一遍全表快照 ⇒ 与现在**逐值相同**'
      u'（这就是"死边"的证明：它们在的时候也不改变任何一扇门的结果）',
      not _diff_back and len(snap_back) == len(snap_now),
      u'差异=%d' % len(_diff_back))

#: 负控制：改掉一条变体边的目标 ⇒ 快照必须变，否则 C1/C2 是恒真
if VAR_ROWS:
    _r2 = json.loads(json.dumps(RL))
    for _x in _r2:
        if _x.get('when_src') in VAR_SRC:
            _x['to'] = u'__nope__.x.y'
            break
    snap_bad = snapshot(_r2, OBJS)
    _n_bad = sum(1 for k in snap_bad
                 if snap_bad.get(k) != snap_now.get(k))
    check(u'C3 负控制：把一条变体边的 `to` 改掉 ⇒ 快照**必须**出现差异'
          u'（证明 C1/C2 的比较有鉴别力）',
          _n_bad > 0, u'差异键=%d' % _n_bad)
else:
    check(u'C3 负控制：把一条变体边的 `to` 改掉 ⇒ 快照必须出现差异', False,
          u'表里没有变体边（分母为 0，无法做负控制）')

_pairs_now = set((r.get('when_scene'), r.get('to')) for r in RL)
_lost = sorted(RM_PAIRS - _pairs_now)
check(u'C4 ★★★ 可达图**逐对不变**：留档那 42 个 `(场景,目标)` 对在现存表里'
      u'**全都还在**（由第174轮的变体边承担）⇒ 删的是冗余，不是通路',
      not _lost, u'丢了对 %d: %r' % (len(_lost), _lost[:3]))

_c5_bad = []
for r in REMOVED:
    o = r.get('_original') or {}
    true_src = PC2OBJ.get((o.get('chapter'), o.get('precreate')))
    got = route_for_door(RAW, r.get('when_scene'), None, src=true_src,
                         pos=[o.get('door_x'), o.get('door_y')])
    if got != r.get('to') or true_src not in VAR_SRC:
        _c5_bad.append((r.get('priority'), true_src, got, r.get('to')))
check(u'C5 ★★ 拿这 42 扇门的**真实坐标**、按**探针反查出来的真身 src**（变体名）'
      u'调 `route_for_door` ⇒ 返回的目标与留档里的一致（第174轮的边接得住）'
      u'〔口径边界：其中 33 扇所在同-src 组只有 1 条候选，坐标其实无关，'
      u'真正在验消歧的是下面的 C5b〕',
      not _c5_bad, u'不符 %d 条: %r' % (len(_c5_bad), _c5_bad[:3]))

#: ★★ C5b：**只挑"坐标真在起作用"的那几扇**。判据是两条前提同时成立：
#:   ① 该 `(场景, src)` 组里候选 >= 2（`_pick_by_pos` 才会启动）；
#:   ② 组里 priority 最小的那条目标 **不等于** 本门目标（否则"退回落选"与
#:      "按坐标挑中"给同一个答案，这次比较就没有鉴别力）。
#:   对这种门，把坐标挪到一个不存在的点 ⇒ 必须退回**别人**的目标。
_VAR_G = collections.defaultdict(list)
for _x in RL:
    _s = _x.get('when_src')
    if isinstance(_s, str) and _s in VAR_SRC:
        _VAR_G[(_x.get('when_scene'), _s)].append(_x)
_c5b_sharp = 0
_c5b_bad = []
for r in REMOVED:
    o = r.get('_original') or {}
    true_src = PC2OBJ.get((o.get('chapter'), o.get('precreate')))
    cands = _VAR_G.get((r.get('when_scene'), true_src)) or []
    if len(cands) < 2:
        continue
    if min(cands, key=lambda x: x.get('priority')).get('to') == r.get('to'):
        continue
    _c5b_sharp += 1
    got = route_for_door(RAW, r.get('when_scene'), None, src=true_src,
                         pos=[o.get('door_x') - 99999, o.get('door_y') - 99999])
    if got == r.get('to'):
        _c5b_bad.append((r.get('priority'), true_src, got))
check(u'C5b ★★★ 坐标**真的在参与消歧**的那 %d 扇门：换成不存在的坐标 ⇒ 必须退回'
      u'（同组 priority 最小那条的）**别人**的目标，不能还返回本门目标'
      % _c5b_sharp,
      _c5b_sharp >= 9 and not _c5b_bad,
      u'有鉴别力 %d 扇、错坐标仍返回本门 %d 条: %r'
      % (_c5b_sharp, len(_c5b_bad), _c5b_bad[:3]))

#: 死边的另一面：改用（错的）`src=obj_doorAny` + 这扇门的坐标去查，
#: 凡是"该场景已没有别的 obj_doorAny 边"的，都必须**查不到** ——
#: 因为对象级匹配是 `when_src == src` 精确相等，这批边标错了 src 就永远命不中。
_via_keys = set((r.get('when_scene'),
                 (r.get('_original') or {}).get('door_x'),
                 (r.get('_original') or {}).get('door_y'))
                for r in RL if r.get('when_src') == VIA)
_dead_miss = [r.get('priority') for r in REMOVED
              if (r.get('when_scene'),
                  (r.get('_original') or {}).get('door_x'),
                  (r.get('_original') or {}).get('door_y')) not in _via_keys]
check(u'C6 ★★★ 死边的另一面：42 扇门里有 %d 扇，用（错的）`src=%s` + 自己的坐标'
      u'去查**已经查不到**任何目标 —— 这就是"删掉它们不影响行为"的机制性理由'
      % (len(_dead_miss), VIA),
      len(_dead_miss) == EXPECT_RM,
      u'仍能命中 %d 扇: %r' % (EXPECT_RM - len(_dead_miss), _dead_miss[:3]))

# ---------------------------------------------------------------------------
# D 段：留档可整段恢复
# ---------------------------------------------------------------------------
print('')
print('=' * 70)
print(u'D 段  留档可整段恢复（无损）')
print('=' * 70)

RESTORED = list(RL_BASE) + list(REMOVED)
check(u'D1 加回 42 条 ⇒ %d 条 == 改前 %d 条（用"现行表 − 第181轮 %d 条"作底）'
      % (len(RESTORED), EXPECT_BEFORE, len(RL_181)),
      len(RESTORED) == EXPECT_BEFORE, u'实得=%d' % len(RESTORED))

_rp = sorted(r.get('priority') for r in RESTORED
             if (r.get('_original') or {}).get('batch') == BATCH)
check(u'D2 加回后 172 段 priority 恢复成 %d~%d **连续无空洞**、且无重复'
      % (PRIO_BASE, PRIO_BASE + EXPECT_VIA_BEFORE - 1),
      _rp == list(range(PRIO_BASE, PRIO_BASE + EXPECT_VIA_BEFORE)),
      u'n=%d 首末=%r 唯一=%d'
      % (len(_rp), (_rp[0], _rp[-1]) if _rp else None, len(set(_rp))))

_rvia = [r for r in RESTORED if r.get('when_src') == VIA]
check(u'D3 加回后 `via=%s` 恢复成 %d 条' % (VIA, EXPECT_VIA_BEFORE),
      len(_rvia) == EXPECT_VIA_BEFORE, u'实得=%d' % len(_rvia))

snap_rest = snapshot(RESTORED, OBJS)
_diff_r = [k for k in set(snap_base) | set(snap_rest)
           if snap_base.get(k) != snap_rest.get(k)]
check(u'D4 ★★ 加回后的全表路由快照也 == "现行表 − 181段"的快照 ⇒ 恢复是**无损**的'
      u'（不只是条数对上，行为也对上）',
      not _diff_r, u'差异=%d' % len(_diff_r))

_mis_rest = [r for r in _rvia
             if PC2OBJ.get(((r.get('_original') or {}).get('chapter'),
                            (r.get('_original') or {}).get('precreate'))) in VAR_SRC]
check(u'D5 ★★ 加回后"误标边"回到 %d 条（= 第174轮 B7 的原始口径）'
      u'⇒ 这一轮确实只是把账**挪出去**，没有篡改历史' % EXPECT_RM,
      len(_mis_rest) == EXPECT_RM, u'实得=%d' % len(_mis_rest))

# ---------------------------------------------------------------------------
# E 段：文件格式 + 自检
# ---------------------------------------------------------------------------
print('')
print('=' * 70)
print(u'E 段  文件格式 + 自检（判据也是被测物）')
print('=' * 70)

_b = io.open(ROUTES_P, 'rb').read()
_txt = _b.decode('utf-8')
check(u'E1 文件格式：无 BOM、全 CRLF（无裸 LF）、JSON 可解析、条数 == 列表长度',
      not _b.startswith(b'\xef\xbb\xbf')
      and _txt.count(u'\r\n') == _txt.count(u'\n') > 0
      and len(RL) == len(RAW.get('routes') or []),
      u'bom=%r crlf=%d lf=%d'
      % (_b.startswith(b'\xef\xbb\xbf'), _txt.count(u'\r\n'), _txt.count(u'\n')))

_canon = json.dumps(RAW, ensure_ascii=False, indent=2).replace(u'\n', u'\r\n')
check(u'E2 无损往返：`json.dumps(indent=2)` + CRLF 生成的文本 == 磁盘上的文本'
      u'（⇒ 落盘没有顺带改排版，diff 里只有那 42 条）',
      _canon == _txt, u'长度 %d vs %d' % (len(_canon), len(_txt)))

_src = io.open(SELF, encoding='utf-8').read()
_tree = ast.parse(_src)
_checks = [n for n in ast.walk(_tree)
           if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
           and n.func.id == 'check']
_const_true = [getattr(c, 'lineno', -1) for c in _checks
               if isinstance(c.args[1] if len(c.args) > 1 else None, ast.Constant)
               and bool(c.args[1].value)]
check(u'E3 ★★★ 全部 %d 条 `check(...)` 的第二参**都不是**常量真'
      u'（恒真判据比不写还危险）' % len(_checks),
      len(_checks) > 0 and not _const_true, u'恒真行号=%r' % (_const_true[:5],))

_ok_defs = [n for n in ast.walk(_tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name == 'ok']
_ok_calls = [n for n in ast.walk(_tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == 'ok']
check(u'E4 单一 harness：本文件只定义 `check(desc, cond, extra)`，'
      u'没有第二套 `ok(...)`（两套并存时只查一处必漏）',
      not _ok_defs and not _ok_calls)

check(u'E5 判据条数下限：AST 数出 >= %d 条（防有人整段删掉）' % CHECK_FLOOR,
      len(_checks) >= CHECK_FLOOR, u'实测 %d' % len(_checks))

_pat = [('E' + ':' + '\\'), ('h' + 'ttp' + '://'), ('h' + 'ttps' + '://'),
        ('url' + 'open' + '(')]
_hit = [p for p in _pat if p in _src]
check(u'E6 零外部盘 / 零网络：源码里不出现 E 盘路径或 URL'
      u'（★ 令牌用拼接构造，避免扫描器扫到自己）',
      not _hit, u'命中=%r' % (_hit,))

# ---------------------------------------------------------------------------
print('')
print('=' * 70)
print(u'合计：PASS=%d FAIL=%d' % (_n['p'], _n['f']))
if _bad:
    print(u'失败项：')
    for b in _bad:
        print(u'  - %s' % b)
print('=' * 70)
sys.exit(1 if _n['f'] else 0)
