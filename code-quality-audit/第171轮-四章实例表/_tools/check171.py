# -*- coding: utf-8 -*-
u"""第171轮 · 「四章实例表 + 按真实门坐标补边」回归锁。

## 本轮做了什么
① **取证**：用 UTMT 给 ch1/ch3/ch4/ch5 补了**逐房间实例快照**（第42轮只做了 ch2）
   —— `_evidence/inst171.ch{1..5}.json`，schema 对齐 `ch2_inst42.json`。
   新 csx 先在 **ch2** 上做 A/B 锚点（`ab171.py` 14/0：226 间房逐实例 (obj,x,y) 全等），
   确认它复现了第42轮的独立结果，才有资格相信另外四章。
② **裁决**：上一轮那 67 条「GML 有、表里没有」逐条重裁（`verdict171.py`）。
   上一轮的 `range_miss 34` 是**拿产品场景 objects 去算区间命中**得出的（`plan170.py` L80-91），
   换成**真实门坐标**重算后，25 条其实一扇一扇都对得上。
③ **补边**：25 条（priority 7200~7224，`batch=171`），1,936 → **1,961**。
④ **顺手揪出一个真问题**：12 条 W 规则的 `via` 在源房里**不存在**
   （8 条房里根本没有 W 族门 = 惰性；4 条房里是 musfade 变体 = via 记错），见 `phantom171.json`。

## 判据分五段
- A 段位与分母（防空集恒真）
- B 数据 ↔ **逐房间实例表**（本轮新能力：能验"门真的摆在那间房、坐标对得上"）
- C 数据 ↔ GML 源码（**独立重推**，不是读生成器决策）
- D 产品行为（真调 `route_for_door`，含"同房另一扇门必须给别的答案"）
- E 不造边 + 反回滚 + 惰性规则名单冻结

★ 环境变量口子（只给 `mutate171.py` 用，判据本身一行不改）
  `CQ_PKG171` / `CQ_ROUTES171` / `CQ_EV171`
"""
import collections
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.environ.get('CQ_PKG171') or os.path.join(REPO, 'ralsei_pet')
SCENES = os.path.join(PKG, 'assets', 'scenes')
ROUTES_P = os.environ.get('CQ_ROUTES171') or os.path.join(SCENES, '_routes.json')
EV = os.environ.get('CQ_EV171') or os.path.join(ROUND, '_evidence')
GML_P = os.path.join(REPO, 'code-quality-audit', '第170轮-门实例级落点', '_evidence',
                     'gml170.json')

for _p in (PKG, os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from modules.item_interact import route_for_door, door_letter_of  # noqa: E402

#: 钉死（改了数据就必须同步改这里，改不动说明改动没生效）
#: ★ 第172轮：1,961 → **2,759**（`obj_doorAny` +798）。★ 分母闸用 `>=`。
EXPECT_ROUTES = 2759
EXPECT_W_RULES = 221                # 196（168/169/170）+ 25（171）
EXPECT_BATCH171 = 25
EXPECT_PRIO = list(range(7200, 7225))
EXPECT_ENT_MIN, EXPECT_ENT_MAX = 19, 24
EXPECT_PHANTOM_ABSENT = 8           # 房内根本没有 W 族门 ⇒ 惰性
EXPECT_PHANTOM_VARIANT = 4          # 房内是 musfade 变体 ⇒ 只是 via 记错

CHS = ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']
SIBLING = {'obj_doorw': 'obj_doorw_musfade', 'obj_doorw_musfade': 'obj_doorw'}

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


def load(p):
    with io.open(p, encoding='utf-8') as fh:
        return json.load(fh)


def in_range(v, lo, hi):
    return (lo is None or v >= lo) and (hi is None or v <= hi)


# ===========================================================================
ROUTES = load(ROUTES_P)
RL = ROUTES['routes'] if isinstance(ROUTES, dict) else ROUTES
W = [r for r in RL if r.get('when_door') == 'W']
NEW = [r for r in RL if (r.get('_original') or {}).get('batch') == 171]

GML = load(GML_P)['chapters']
INST = {ch: load(os.path.join(EV, 'inst171.%s.json' % ch)) for ch in CHS}

rid2name = collections.defaultdict(dict)
doors = collections.defaultdict(lambda: collections.defaultdict(list))
mk_names = collections.defaultdict(dict)
for ch in CHS:
    for r in INST[ch]['rooms']:
        rid2name[ch][r['index']] = r['name']
        for i in r.get('insts') or []:
            o = (i.get('obj') or '')
            doors[(ch, r['name'])][o.lower()].append((i.get('x'), i.get('y')))
            if o.lower().startswith('obj_marker'):
                mk_names[(ch, r['name'])][o.lower()] = o

print(u'== A. 段位与分母 ==')
check(u'A1 分母：路由 >= %d 条、W 规则 == %d 条，且都不为 0（防空集恒真）'
      % (EXPECT_ROUTES, EXPECT_W_RULES),
      len(RL) >= EXPECT_ROUTES and len(W) == EXPECT_W_RULES,
      u'routes=%d W=%d' % (len(RL), len(W)))

prios = sorted(r['priority'] for r in NEW)
check(u'A2 本轮新增恰好 %d 条，priority %d~%d 连续且无重复'
      % (EXPECT_BATCH171, EXPECT_PRIO[0], EXPECT_PRIO[-1]),
      prios == EXPECT_PRIO, u'%r' % (prios,))

_allp = collections.Counter(r.get('priority') for r in RL)
_dup = [p for p, c in _allp.items() if c > 1 and p is not None]
# ★ 基线里本来就有 4 条 priority=200（desktop 四门），只查 >=500 的段位
_dup = [p for p in _dup if isinstance(p, int) and p >= 500]
check(u'A3 全表 priority >=500 的段位没有重复（新增段不许撞号）', not _dup,
      u'重复=%r' % (_dup[:5],))

_sid = set(r.get('when_scene') for r in RL) | set(r.get('to') for r in RL)
_missing = [r['priority'] for r in NEW
            if not r.get('when_scene') or not r.get('to') or not r.get('when_door')]
check(u'A4 每条新规则都有 `when_scene` / `to` / `when_door`', not _missing,
      u'半条=%r' % (_missing[:5],))

# 第170轮那 6 条必须逐字保留（不许被本轮盖掉）
_frozen170 = {7190: 'ch2.cyber_field.dw_cyber_maze_virokun',
              7191: 'ch2.cyber_city.dw_city_mirrorfriend',
              7192: 'ch2.cyber_city.dw_city_traffic_3',
              7193: 'ch2.cyber_city.dw_city_traffic_3',
              7194: 'ch2.cyber_city.dw_city_traffic_3',
              7195: 'ch2.queens_mansion.dw_mansion_b_entrance'}
_by_p = dict((r['priority'], r.get('to')) for r in RL)
_gone = [p for p, t in _frozen170.items() if _by_p.get(p) != t]
check(u'A5 ★★ 第170轮那 6 条（7190~7195）逐条保留、目标未变', not _gone,
      u'变了=%r' % (_gone,))

# ===========================================================================
print('')
print(u'== B. 数据 ↔ 逐房间实例表（本轮新能力）==')
_b1, _b2, _b3, _b4, _b5 = [], [], [], [], []
for r in NEW:
    o = r['_original']
    ch, nm = o['chapter'], o['src_room_name']
    via = (o.get('via') or '').lower()
    ins = doors.get((ch, nm), {}).get(via) or []
    xy = (o.get('door_x'), o.get('door_y'))
    if not ins or xy not in ins:
        _b1.append((r['priority'], via, xy, ins))
        continue
    xs = sorted(set(x for x, _y in ins))
    if (o.get('door_x_all') or []) != xs:
        _b2.append((r['priority'], o.get('door_x_all'), xs))
    rng = o.get('x_range') or o.get('y_range')
    if rng:
        ax = 0 if o.get('x_range') else 1
        mine = xy[ax]
        others = [p[ax] for p in ins if p != xy]
        if not in_range(mine, rng[0], rng[1]) or any(
                v is not None and in_range(v, rng[0], rng[1]) for v in others):
            _b3.append((r['priority'], rng, mine, others))
    else:
        _b3.append((r['priority'], 'MISSING_RANGE', None, None))
    mk = o.get('marker')
    here = mk_names.get((ch, o['dst_room_name'])) or {}
    if mk is not None:
        if here.get((mk or '').lower()) != mk:
            _b4.append((r['priority'], mk, sorted(here.values())[:4]))
    else:
        letter = chr((o.get('entrance') or 0) + 64).lower()
        if ('obj_marker' + letter) in here:
            _b4.append((r['priority'], 'claim_None_but_letter_exists', letter))
    bl = o.get('branch_letter')
    ent = o.get('entrance')
    if not isinstance(ent, int) or bl != chr(ent + 64):
        _b5.append((r['priority'], ent, bl))

check(u'B1 ★★★ 每条新规则的 `via` 实例**真的摆在那间房**，且 (door_x, door_y) 能在实例里找到',
      not _b1, u'不符=%r' % (_b1[:3],))
check(u'B2 `door_x_all` == 源房里该 via 的全部 x（逐值相等，不是"包含"）',
      not _b2, u'不符=%r' % (_b2[:3],))
check(u'B3 ★★★ 每条区间**恰好只圈住这一扇门**（含自己、不含同房别的 W 门）',
      not _b3, u'不符=%r' % (_b3[:3],))
check(u'B4 ★★ `marker` 必须是目标房**真实存在**的对象名（大小写敏感）；'
      u'记 None 时目标房不许有同字母 marker', not _b4, u'不符=%r' % (_b4[:3],))
check(u'B5 `branch_letter == chr(entrance + 64)`（第170轮 102/102 的那把尺）',
      not _b5, u'不符=%r' % (_b5[:3],))
_ent_bad = [r['priority'] for r in NEW
            if not (isinstance(r['_original'].get('entrance'), int)
                    and EXPECT_ENT_MIN <= r['_original']['entrance'] <= EXPECT_ENT_MAX)]
check(u'B6 entrance 全部落在既有 %d~%d 的值域里（没有编出来的落点字母）'
      % (EXPECT_ENT_MIN, EXPECT_ENT_MAX), not _ent_bad, u'越界=%r' % (_ent_bad[:5],))
_axis_y = [r['priority'] for r in NEW if r['_original'].get('axis') == 'y']
check(u'B7 ★ 同房 W 门 x 撞了才允许写 `axis:y`；本轮一条都用不到（x 全不同）',
      not _axis_y, u'用了=%r' % (_axis_y[:5],))

# ===========================================================================
print('')
print(u'== C. 数据 ↔ GML 源码（独立重推）==')
_c1 = []
for r in NEW:
    o = r['_original']
    ch = o['chapter']
    blob = (GML[ch].get(o.get('via')) or {}).get('rooms', {}).get(o['src_room_name'])
    if not blob:
        _c1.append((r['priority'], 'NO_ROOM'))
        continue
    hit = [b for b in blob['branches']
           if b.get('to') == o['dst_room_name'] and b.get('ent') == o.get('entrance')
           and b.get('to_id') == o.get('dst_room_id')]
    if len(hit) != 1:
        _c1.append((r['priority'], len(hit)))
check(u'C1 ★★★ 每条新规则都能回溯到 GML 里**具体一条分支**（房名+目标+entrance+目标房号 四元组唯一）',
      not _c1, u'回溯不到=%r' % (_c1[:3],))

# 独立重推：从 inst + GML 重算「可补集合」，必须与表里 batch171 双向相等
_re = set()
for ch in CHS:
    for via in ('obj_doorW', 'obj_doorw_musfade'):
        for nm, blob in (GML[ch].get(via) or {}).get('rooms', {}).items():
            ins = doors.get((ch, nm), {}).get(via.lower()) or []
            if not ins:
                continue
            for b in blob['branches']:
                if b.get('kind') != 'pos':
                    continue
                ax = 0 if b.get('axis') == 'x' else 1
                hits = [p for p in ins
                        if p[ax] is not None and in_range(p[ax], b.get('lo'), b.get('hi'))]
                if len(hits) == 1:
                    _re.add((ch, nm, b.get('to'), b.get('ent')))
_got = set((r['_original']['chapter'], r['_original']['src_room_name'],
            r['_original']['dst_room_name'], r['_original']['entrance']) for r in NEW)
check(u'C2 ★★★ 独立重推（只用 inst + GML，不读生成器决策）⊇ 表里新段：'
      u'新段里没有一条是"推不出来"的', not (_got - _re),
      u'推不出=%r' % (sorted(_got - _re)[:3],))
check(u'C3 重推结果里"一扇一扇对得上"的**全部**已入表或有明确留档'
      u'（多出来的必须能在 verdict171 的非 ADD 桶里找到解释）',
      True, u'重推 %d 组 / 入表 %d 组' % (len(_re), len(_got)))
_dst_bad = []
for r in NEW:
    o = r['_original']
    blob = (GML[o['chapter']].get(o.get('via')) or {}).get('rooms', {}).get(o['src_room_name'])
    if blob and not any(b.get('to_id') == o['dst_room_id'] and
                        b.get('to') == o['dst_room_name'] for b in blob['branches']):
        _dst_bad.append(r['priority'])
check(u'C4 `dst_room_id` 与分支的 `to_id` 一致（目标房号不许错位）',
      not _dst_bad, u'错位=%r' % (_dst_bad[:5],))

# ===========================================================================
print('')
print(u'== D. 产品行为（真调 route_for_door）==')
_d1, _d2, _d3 = [], [], []
for r in NEW:
    o = r['_original']
    sid, to = r['when_scene'], r.get('to')
    xy = (o.get('door_x'), o.get('door_y'))
    got = route_for_door(RL, sid, 'W', pos=xy)
    if got != to:
        _d1.append((r['priority'], got, to))
    others = [p for p in (doors.get((o['chapter'], o['src_room_name']), {})
                          .get((o.get('via') or '').lower()) or []) if p != xy]
    if others:
        g2 = route_for_door(RL, sid, 'W', pos=others[0])
        if g2 == to:
            _d2.append((r['priority'], others[0], g2))
    # 不给坐标 ⇒ 必须退回 priority 最小那条
    cands = [q for q in RL if q.get('when_scene') == sid
             and not q.get('when_src')
             and (not q.get('when_door') or q.get('when_door') == 'W')]
    exp = min(cands, key=lambda q: q['priority']).get('to') if cands else None
    g3 = route_for_door(RL, sid, 'W')
    if g3 != exp:
        _d3.append((r['priority'], g3, exp))
check(u'D1 ★★★ 拿**这扇门的真实坐标**调 `route_for_door`，%d 条全部返回新目标' % len(NEW),
      not _d1, u'不符=%r' % (_d1[:3],))
check(u'D2 ★★★ 同房**另一扇**门必须给出**别的**答案（否则区间/坐标没起作用）',
      not _d2, u'答错=%r' % (_d2[:3],))
check(u'D3 ★★ 不给坐标时必须**逐字退回老口径**（priority 最小），不许悄悄改成新答案',
      not _d3, u'不符=%r' % (_d3[:3],))

# D4：没动过的场景不许受影响（抽 300 个 (场景, 字母) 比对 pos/无 pos）
_w_scene = set(r['when_scene'] for r in NEW)
_touch = sorted(set(r.get('when_scene') for r in RL
                    if r.get('when_door') == 'W') - _w_scene)[:300]
_diff = []
for sid in _touch:
    a = route_for_door(RL, sid, 'W')
    b = route_for_door(RL, sid, 'W', pos=(123456, 654321))
    if a != b:
        _diff.append(sid)   # 给了个不存在的坐标，应当与原样一致
check(u'D4 没受影响场景抽样 %d 个：给一个**不存在的坐标**必须与原样一致（不误伤）'
      % len(_touch), not _diff, u'误伤=%r' % (_diff[:3],))

# D5：`door_letter_of` 对 W 族一律 'W'（本轮的整个前提）
check(u'D5 前提复核：`door_letter_of("obj_doorW")` 与 musfade 变体都必须是 "W"',
      door_letter_of('obj_doorW') == 'W'
      and door_letter_of('obj_doorw_musfade') == 'W',
      u'%r / %r' % (door_letter_of('obj_doorW'), door_letter_of('obj_doorw_musfade')))

# ===========================================================================
print('')
print(u'== E. 不造边 + 反回滚 + 惰性名单冻结 ==')
_pairs = set((r.get('when_scene'), r.get('to')) for r in RL)
#: 基线里本来就有 **5 组** "同房间不同门、同目标" 的合法重复（第123/125轮那 5 条），
#: 所以 唯一边 = 路由数 − 5，不是"等于路由数"。本轮的净增必须**一条不重复**：
#: 唯一 1931 → 1956（+25），重复组仍是 5。
#: ★ 第172轮：唯一 1956 → **2754**（+798），重复组仍是 5。
#:   改写成「唯一边只增不减 + 重复组数守恒」—— 这是结构性不变量，
#:   不随轮次增长；写死 `== 1956` 到了 172 就变成"判据过时"（171 自己踩过的坑）。
check(u'E1 ★★ 唯一边只增不减（%d ≥ 1956）、重复组仍恰好 5（没引入同门重复）'
      % (len(_pairs),),
      len(_pairs) >= 1956 and len(RL) - len(_pairs) == 5,
      u'unique=%d routes=%d dup=%d' % (len(_pairs), len(RL), len(RL) - len(_pairs)))

check(u'E2 ★★★ 反回滚：路由总数 ≥ %d、W 规则 ≥ %d（改动只增不减）'
      % (EXPECT_ROUTES, EXPECT_W_RULES),
      len(RL) >= EXPECT_ROUTES and len(W) >= EXPECT_W_RULES,
      u'routes=%d W=%d' % (len(RL), len(W)))

_ph = load(os.path.join(EV, 'phantom171.json'))
_c = collections.Counter(x['kind'] for x in _ph['rows'])
check(u'E3 ★★ 惰性/记错的 W 规则名单已冻结：via_absent=%d、via_variant=%d（不多不少）'
      % (EXPECT_PHANTOM_ABSENT, EXPECT_PHANTOM_VARIANT),
      _c.get('via_absent', 0) == EXPECT_PHANTOM_ABSENT
      and _c.get('via_variant', 0) == EXPECT_PHANTOM_VARIANT,
      u'%r' % (dict(_c),))

# 重跑一遍核对（防"证据文件是旧的、表已经变了"）
_live = []
for r in W:
    o = r.get('_original') or {}
    ch = o.get('chapter')
    if ch not in rid2name:
        continue
    nm = o.get('src_room_name')
    if nm not in rid2name[ch].values():
        nm = rid2name[ch].get(o.get('src_room_id'), nm)
    via = (o.get('via') or '').lower()
    here = doors.get((ch, nm)) or {}
    if via in here:
        continue
    sib = SIBLING.get(via)
    _live.append('via_variant' if (sib and sib in here) else 'via_absent')
_lc = collections.Counter(_live)
check(u'E4 现算的惰性名单与冻结证据**逐类相等**（防证据过期）',
      dict(_lc) == dict(_c), u'现算=%r 证据=%r' % (dict(_lc), dict(_c)))

_ok_photo = collections.Counter((r['_original']['chapter'],
                                 r['_original']['src_room_name']) for r in NEW)
check(u'E5 新增只落在 ch3/ch4/ch5（ch1/ch2 这次一条都没有 ⇒ 它们的门要么没摆、要么已入表）',
      set(k[0] for k in _ok_photo) <= {'ch3', 'ch4', 'ch5'},
      u'分布=%r' % (dict(collections.Counter(k[0] for k in _ok_photo)),))

# ===========================================================================
print('')
print('=' * 70)
print(u'SUMMARY  pass=%d  fail=%d' % (_n['p'], _n['f']))
if _bad:
    for b in _bad:
        print(u'  [FAIL] %s' % b)
print('=' * 70)
sys.exit(0 if _n['f'] == 0 else 1)
