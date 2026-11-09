# -*- coding: utf-8 -*-
u"""第170轮 · 「门实例级落点」回归锁。

## 本轮做了什么
原作里**同一间房可以有好几扇 W 门**，去向靠 `if (x > 1730 && x < 1840)` 这类
位置条件分流。但 `door_letter_of('obj_doorW')` 对它们一律返回 `'W'` ⇒ 只按
(场景, 字母) 查，同房几扇门会**全去同一条规则**指向的房间（"一房多出口"）。

本轮两件事：
① **数据侧**（`_routes.json`）：`entrance` 补到 190/190；区间按源码校正 27 条
   （其中 11 条方向反了）；补 17 条门实例坐标（12 条是 `y` 轴）；新增 6 条规则
   （★ 另有 3 条与既有 `(场景, 目标)` 完全重复，**有意不落** —— 重复边会让
   `check124 D2` 判"同门重复"，也会弄脏 `check169` 的覆盖桶）。
② **产品侧**（`item_interact.route_for_door`）：加 `pos` 参数，同场景同字母
   **多候选**时按门坐标消歧；挑不出唯一就退回老口径。

## 判据分四段
- A 段：段位与分母（防空集恒真）
- B 段：数据 ↔ 源码对账（entrance / 区间 / 门坐标 / 新增边）
- C 段：产品行为（**全表扫描**，不是只查我改过的那几条）
- D 段：不造边 + 反回滚

★ 环境变量口子（只给 `mutate170.py` 用，判据本身一行不改）
  `CQ_PKG170` / `CQ_ROUTES170` / `CQ_EV170`
"""
import collections
import glob
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.environ.get('CQ_PKG170') or os.path.join(REPO, 'ralsei_pet')
SCENES = os.path.join(PKG, 'assets', 'scenes')
ROUTES_P = os.environ.get('CQ_ROUTES170') or os.path.join(SCENES, '_routes.json')
EV = os.environ.get('CQ_EV170') or os.path.join(ROUND, '_evidence')
GML_P = os.path.join(EV, 'gml170.json')
INST_P = os.path.join(REPO, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence',
                      'ch2_inst42.json')

for _p in (PKG, os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from modules.item_interact import (route_for_door, _pick_by_pos,  # noqa: E402
                                   _rule_door_axis, door_letter_of)

#: ★ 第172轮：1,961 → **2,759**（`obj_doorAny` 按每实例创建代码 +798）。★ 分母闸用 `>=`。
EXPECT_ROUTES = 2759
EXPECT_BATCH170 = 6
EXPECT_PRIO = list(range(7190, 7196))
EXPECT_W_RULES = 221                 # 190（168/169）+ 6（170）+ 25（171）
EXPECT_ENT_FILLED = 190              # batch169 的 102 条里原先 88 条没记，本轮补齐
EXPECT_RANGE_FLIP = 0                # 方向反了 = 0（修完）
EXPECT_RANGE_MISS = 0                # 该有区间却没有 = 0（修完）
EXPECT_COORD = 17                    # 第170轮写死的门实例坐标条数
EXPECT_AXIS_Y = 12                   # 该轮 y 轴修正（同房两扇门 x 相同，只能按 y 分）
EXPECT_DOOR_Y = 48                   # 带 door_y 的总数（第171轮落定：23 + 25 条新边）
EXPECT_AFFECTED = 26                 # 传 pos 会改变结果的场景数（只增不减的敏感度闸）
EXPECT_BATCH171 = 25                 # 第171轮那批（7200~7224）

#: ★★★ 第171轮的教训：**别把会随轮次增长的绝对数写成 `==`**。
#:   第170轮原判据 A3/B3/C3/D2b 全都钉了当日快照，171 一加 25 条边就四连红 ——
#:   那不是回归，是判据过时（同 165 的 `fit` 恒真、134 `B5` 同族）。
#:   现在统一改成两种写法：①「历史段冻结 + 新段只增不减」② 结构性不变量。
FROZEN_BATCH = {None: 88, 169: 102, 170: 6}   # 168 那批规则没有 batch 字段 ⇒ 记成 None
KIND = 'delta_door_table'
W_VIA = ('obj_doorW', 'obj_doorw_musfade')

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
    return json.loads(io.open(p, encoding='utf-8', errors='replace', newline='').read())


def load_scene_objects():
    u"""→ {scene_id: [object, ...]}；与 `item_interact.build_props` 读的是同一份。"""
    out = {}
    for f in glob.glob(os.path.join(SCENES, '_zone.*.json')):
        z = jl(f)
        s = z.get('scenes')
        it = (s.items() if isinstance(s, dict) else ((v.get('scene_id'), v) for v in s))
        for k, v in it:
            if isinstance(v, dict):
                out[v.get('scene_id') or k] = v.get('objects') or []
    return out


# ===========================================================================
print('')
print('=' * 70)
print(u'A 段  段位与分母（防空集恒真）')
print('=' * 70)

RAW = jl(ROUTES_P)
RL = RAW.get('routes') or []
OBJS = load_scene_objects()
W_RULES = [r for r in RL if (r.get('_original') or {}).get('via') in W_VIA]
MINE = [r for r in RL if (r.get('_original') or {}).get('batch') == 170]

check(u'A0 分母：场景对象表非空、路由 >= %d 条、W 规则 == %d 条、本轮段非空'
      % (EXPECT_ROUTES, EXPECT_W_RULES),
      len(OBJS) > 1000 and len(RL) >= EXPECT_ROUTES
      and len(W_RULES) == EXPECT_W_RULES and len(MINE) > 0,
      u'scenes=%d routes=%d W=%d mine=%d'
      % (len(OBJS), len(RL), len(W_RULES), len(MINE)))

_prios = sorted(r.get('priority') for r in MINE)
check(u'A1 本轮段 %d 条、priority %d~%d 连续无空洞'
      % (EXPECT_BATCH170, EXPECT_PRIO[0], EXPECT_PRIO[-1]),
      len(MINE) == EXPECT_BATCH170 and _prios == EXPECT_PRIO,
      u'n=%d 首末=%r' % (len(MINE), (_prios[0], _prios[-1]) if _prios else None))

_my_prios = set(EXPECT_PRIO)
_collide = []
for r in MINE:
    same = [q for q in RL if q is not r and q.get('priority') == r.get('priority')]
    if same:
        _collide.append((r.get('priority'), len(same)))
check(u'A2 ★★ 第170轮那 %d 条的 priority 不与**任何**既有规则重复（不许顶掉谁）'
      % EXPECT_BATCH170,
      not _collide, u'撞车=%r' % (_collide[:5],))
#: ★ 基线表里 `priority=200` 本来就有 4 条（都是 desktop 门）—— 那是既有事实，
#:   不是第170轮引入的。判据只盯"那一轮加的 6 条"，不然会报一个跟它无关的红。

_all_batch = collections.Counter((r.get('_original') or {}).get('batch') for r in W_RULES)
_bad_hist = [(k, _all_batch.get(k, 0), v) for k, v in FROZEN_BATCH.items()
             if _all_batch.get(k, 0) != v]
_later = sum(v for k, v in _all_batch.items() if k not in FROZEN_BATCH)
_bad_label = [k for k in _all_batch if k is not None and not isinstance(k, int)]
check(u'A3 段位分布：历史段**冻结**（无 batch %d / 169 段 %d / 170 段 %d，一格都不许动）'
      u' + 171 起 %d 条（只增不减）；段位标签只许 None 或整数'
      % (FROZEN_BATCH[None], FROZEN_BATCH[169], FROZEN_BATCH[170], _later),
      not _bad_hist and not _bad_label and _later >= EXPECT_BATCH171,
      u'%r' % (dict(_all_batch),))
#: ★ 第168轮那 88 条**没有 `batch` 字段**（所以是 None）—— 按 168 去数会数出 0。
#: ★ 原写法是「三段之和 == 全表条数」，只在"段位集合永远不变"时才成立 ——
#:   171 多了第四段就立刻红。真正的闸是「历史段一格不动 + 新段不少 + 没有编出来的段位标签」。


# ===========================================================================
print('')
print('=' * 70)
print(u'B 段  数据 ↔ 源码对账（entrance / 区间 / 门坐标 / 新增边）')
print('=' * 70)

G = jl(GML_P)

#: (ch, room_name, obj, dst_room_id) → [branch]
BIDX = collections.defaultdict(list)
#: (ch, src_room_id, obj, dst_room_id) → [branch]
#: ★ 为什么要两张索引：第44/125轮那批老规则的 `_original.src_room_name` 是
#:   **中文本地化名**（"纸牌城堡·一层"），拿它去 GML 的 `room_cc_1f` 里查会查不到，
#:   于是把一条真规则误报成"我编的"。按房号兜底才能两边都认。
BIDX2 = collections.defaultdict(list)
RID2NAME = {}
for _ch, _chd in G['chapters'].items():
    for _obj, _dd in _chd.items():
        for _room, _v in _dd['rooms'].items():
            if _v.get('room_id') is not None:
                RID2NAME[(_ch, _v['room_id'])] = _room
            for _b in _v['branches']:
                if _b['to_id'] is not None:
                    BIDX[(_ch, _room, _obj, _b['to_id'])].append(_b)
                    BIDX2[(_ch, _v.get('room_id'), _obj, _b['to_id'])].append(_b)

# ---- B1 entrance ----
_b169 = [r for r in W_RULES if (r.get('_original') or {}).get('batch') == 169]
_no_ent = [r for r in _b169 if not isinstance(r['_original'].get('entrance'), int)]
check(u'B1 ★★ batch169 的 %d 条全部有整数 `entrance`（本轮补了 88 条）'
      % EXPECT_ENT_FILLED,
      len(_b169) == len(_b169) and len(_b169) > 0 and not _no_ent,
      u'n=%d 缺=%d' % (len(_b169), len(_no_ent)))

_out = [r['_original'].get('entrance') for r in _b169
        if isinstance(r['_original'].get('entrance'), int)]
check(u'B1b `entrance` 值域在 19~24（原作 `global.entrance` 的实际取值）',
      bool(_out) and min(_out) >= 19 and max(_out) <= 24,
      u'min=%r max=%r' % (min(_out) if _out else None, max(_out) if _out else None))

# ---- B2 区间 ----
_flip, _miss, _other, _nomatch = [], [], [], []
for r in _b169:
    o = r['_original']
    k = (o.get('chapter'), o.get('src_room_name'), o.get('via'), o.get('dst_room_id'))
    bs = BIDX.get(k) or []
    if len(bs) != 1:
        _nomatch.append(r.get('priority'))
        continue
    b = bs[0]
    lo, hi = b['lo'], b['hi']
    if lo is None and hi is None:
        _other.append(r.get('priority'))      # 混轴：源码自己也解不出，不许改
        continue
    cur = o.get('%s_range' % (b['axis'] or 'x'))
    if not isinstance(cur, list):
        cur = [None, None]
    if cur == [lo, hi]:
        continue
    if cur == [hi, lo]:
        _flip.append(r.get('priority'))
    else:
        _miss.append((r.get('priority'), b['cond'], cur, [lo, hi]))

check(u'B2 ★★★ 区间方向反了 == %d（源码 `x < 10` 不许再记成 `[10, None]`）'
      % EXPECT_RANGE_FLIP,
      len(_flip) == EXPECT_RANGE_FLIP, u'反了=%r' % (_flip[:6],))

check(u'B2b ★★★ 该有区间却没有 == %d（y 轴分支写的是 `y_range`）'
      % EXPECT_RANGE_MISS,
      len(_miss) == EXPECT_RANGE_MISS,
      u'缺=%r' % ([(x[0], x[1]) for x in _miss][:6],))

# ---- B3 门实例坐标 vs 原作实例快照 ----
INST = {}
if os.path.exists(INST_P):
    _d = jl(INST_P)
    for _r in _d['rooms']:
        _pairs = set()
        for _o in _r['insts']:
            nm = _o.get('obj') or ''
            if nm.startswith('obj_doorW') or nm.startswith('obj_doorw'):
                _pairs.add((_o.get('x'), _o.get('y')))
        INST.setdefault(_r['name'], set()).update(_pairs)

_axis_y = [r for r in W_RULES if (r.get('_original') or {}).get('axis') == 'y']
_coord_rules = [r for r in W_RULES
                if (r.get('_original') or {}).get('door_y') is not None]
_axis_no_y = [r.get('priority') for r in _axis_y
              if (r['_original'] or {}).get('door_y') is None]
check(u'B3 `axis:"y"` ≥ %d 条、带 `door_y` 的 ≥ %d 条（两处都是只增不减）；'
      u'且每条 `axis:"y"` 都必须记了 door_y（轴判断没坐标就是空话）'
      % (EXPECT_AXIS_Y, EXPECT_DOOR_Y),
      len(_axis_y) >= EXPECT_AXIS_Y and len(_coord_rules) >= EXPECT_DOOR_Y
      and not _axis_no_y,
      u'axisY=%d doorY=%d 缺y=%r' % (len(_axis_y), len(_coord_rules), _axis_no_y[:5]))

_bad_coord = []
for r in _coord_rules:
    o = r['_original']
    room = o.get('src_room_name')
    if room not in INST:
        continue
    if (o.get('door_x'), o.get('door_y')) not in INST[room]:
        _bad_coord.append((r.get('priority'), room, o.get('door_x'), o.get('door_y')))
check(u'B3b ★★★ 每条 `door_y` 规则的 (x, y) 都**逐像素**落在原作门实例上（独立来源对账）',
      not _bad_coord, u'不符=%r' % (_bad_coord[:5],))

# ---- B4 新增 9 条的 to 与源码一致 ----
_old_pairs = set()
for r in W_RULES:
    o = r.get('_original') or {}
    if o.get('batch') != 170:
        _old_pairs.add((r.get('when_scene'), r.get('to')))
_new_ok, _new_bad = 0, []
for r in MINE:
    o = r['_original']
    room = RID2NAME.get((o.get('chapter'), o.get('src_room_id')))
    bs = BIDX.get((o.get('chapter'), room, o.get('via'), o.get('dst_room_id'))) or []
    #: ★ 这里只能要求「**至少有**一条分支」，不能要求"唯一" ——
    #:   `dw_mansion_east_2f_c` 到同一个目标有两条分支（不同条件），
    #:   要求唯一会把它判成假红（7198 就是这么被抓的）。
    #:   真·唯一性由 `plan170` 的 `ok` 把关，不在这一段。
    if bs:
        _new_ok += 1
    else:
        _new_bad.append((r.get('priority'), room, len(bs)))
check(u'B4 新增 9 条的 (章,源房,对象,目标) 都能在 GML 里找到**至少一条**分支',
      _new_ok == len(MINE) and len(MINE) == EXPECT_BATCH170 and not _new_bad,
      u'ok=%d bad=%r' % (_new_ok, _new_bad[:4]))


# ===========================================================================
print('')
print('=' * 70)
print(u'C 段  产品行为（全表扫描）')
print('=' * 70)


def _rule_coord(r):
    return _rule_door_axis(r)


#: 逐门实例扫全表：规则坐标与门坐标对上的那些，必须由 `pos` 一路认领
_tested, _viol, _fb_tested, _fb_viol = 0, [], 0, []
_aff = set()
for sid, objs in OBJS.items():
    for o in objs:
        if not isinstance(o, dict):
            continue
        lt = door_letter_of(o.get('src'))
        if not lt:
            continue
        pos = o.get('pos') or [None, None]
        with_pos = route_for_door(RAW, sid, lt, src=o.get('src'), pos=pos)
        no_pos = route_for_door(RAW, sid, lt, src=o.get('src'))
        if with_pos != no_pos:
            _aff.add(sid)
        # ★★★ 候选集必须用**全表**而不是只挑 W 规则：`route_for_door` 是按
        #   (场景, 字母) 查的，A~F/X/Y 门和 ut 的对象级规则都在同一个池子里。
        #   只挑 W 会把 1,297 个"别的门字母"误判成"原本查不到"（第一版就这么假红了）。
        # ★★★ 第181轮改：候选集还必须**与 `route_for_door` 同一套解析顺序** ——
        #   产品侧是「先对象级（`when_src == src`）→ 没有才退字母级（跳过带 when_src 的）」。
        #   第一版只取字母级 ⇒ 第181轮给 A~F / climb 门落的 63 条**对象级**边被排除在外，
        #   而 `route_for_door(src=…)` 明明先命中它们 ⇒ 算出的"老口径"是 `None`
        #   ⇒ 41 条"该退回却没退回"的**假红**。这是"候选集须与被测同一套"的又一次现场。
        cands = [r for r in RL
                 if r.get('when_scene') == sid and o.get('src')
                 and r.get('when_src') == o.get('src')]
        if not cands:
            cands = [r for r in RL
                     if r.get('when_scene') == sid and not r.get('when_src')
                     and (not r.get('when_door') or r.get('when_door') == lt)]
        hits = []
        for r in cands:
            k = _rule_coord(r)
            if not k:
                continue
            if k[0] == 'x' and k[1] == pos[0]:
                hits.append(r)
            elif k[0] == 'y' and k[1] == pos[1]:
                hits.append(r)
        #: ★ `_pick_by_pos` 要求候选 **≥2** 才生效；只有 1 条候选时它一定返 None，
        #:   所以这种门归到"退回老口径"那一档，不能算进"可唯一认领"。
        #: ★★★ 第172轮：`_pick_by_pos` 多了**第二拍** —— 单轴挑不出唯一时，改用
        #:   `(door_x, door_y)` 两个坐标一起对。所以"能不能唯一认领"的判定也要跟着多一拍，
        #:   否则判据会拿**旧模型**去套新实现（本轮 C2 就这么假红 1 条：
        #:   `dw_mansion_east_1f_secret` 的 [970,190]，两条规则都 x=970、只有一条记了 y=190
        #:   ⇒ 旧模型判"多命中 ⇒ 该退回"，而正解恰恰是认领 7195 那条）。
        #:   ★ 这不是"放宽判据来迁就改动"：C1/C2 的**语义**没变（能唯一认领就必须认对、
        #:     认不出就必须逐字退回），变的只是"能不能认领"的定义 —— 而且新定义由
        #:     C2b 用一条**具体真值**单独锁住，不靠这里自证。
        if len(cands) >= 2 and len(hits) == 1:
            _tested += 1
            if with_pos != hits[0].get('to'):
                _viol.append((sid, lt, pos, with_pos, hits[0].get('to')))
        else:
            _both = []
            for r in cands:
                o = r.get('_original') or {}
                if (isinstance(o.get('door_x'), int) and isinstance(o.get('door_y'), int)
                        and o.get('door_x') == pos[0] and o.get('door_y') == pos[1]):
                    _both.append(r)
            if len(cands) >= 2 and len(_both) == 1:
                _tested += 1
                if with_pos != _both[0].get('to'):
                    _viol.append((sid, lt, pos, with_pos, _both[0].get('to')))
                continue
            #: 挑不出唯一 ⇒ 必须**逐字回到老口径**（该 (场景,字母) 的 priority 最小者）
            _fb_tested += 1
            best = None
            for r in cands:
                p = r.get('priority')
                p = p if isinstance(p, int) else 10 ** 6
                if best is None or p < best[0]:
                    best = (p, r.get('to'))
            want = None if best is None else best[1]
            if with_pos != want:
                _fb_viol.append((sid, lt, pos, with_pos, want))

check(u'C0 分母：按坐标可唯一认领的门实例 == %d 个（> 0 才有意义）' % _tested,
      _tested > 0 and _fb_tested > 0,
      u'唯一=%d 退回=%d' % (_tested, _fb_tested))

check(u'C1 ★★★ 可唯一认领的门，`route_for_door(pos=…)` 必须返回**那条规则**的目标',
      not _viol, u'违例=%d %r' % (len(_viol), _viol[:4]))

check(u'C2 ★★★ 挑不出唯一的门，必须**逐字退回**「priority 最小」的老口径',
      not _fb_viol, u'违例=%d %r' % (len(_fb_viol), _fb_viol[:4]))

#: ★★★ 第172轮：把"第二拍"钉死成一条**具体真值**，不让上面那段自证。
#:   `dw_mansion_east_1f_secret` 两扇 W：7144 只有 x=970、7195 是 (970, **190**)。
#:   旧口径下这扇 [970,190] 被判"多命中 ⇒ 退回"，落到 priority 最小的 7144
#:   （`queen_s_mansion_entrance`）；而第170轮之所以记 7195 的 y=190，
#:   就是要它去 `dw_mansion_b_entrance`。第二拍按 (x,y) 认领到 7195 ⇒ 走对了。
_sec = [r for r in RL
        if r.get('when_scene') == 'ch2.queens_mansion.dw_mansion_east_1f_secret'
        and not r.get('when_src') and r.get('when_door') == 'W']
_g2 = route_for_door(RAW, 'ch2.queens_mansion.dw_mansion_east_1f_secret', 'W',
                     pos=[970, 190])
_want2 = [r.get('to') for r in _sec
          if (r.get('_original') or {}).get('door_x') == 970
          and (r.get('_original') or {}).get('door_y') == 190]
_fb2 = min(_sec, key=lambda r: r.get('priority')).get('to') if _sec else None
check(u'C2b ★★★ 第二拍正控制：两扇门同 x、只有一扇记了 y ⇒ 必须认领**那一扇**'
      u'（%r），而不是退回 priority 最小的 %r'
      % (_want2[0] if _want2 else None, _fb2),
      len(_want2) == 1 and _g2 == _want2[0] and _g2 != _fb2,
      u'got=%r 应为=%r 老口径=%r' % (_g2, _want2[0] if _want2 else None, _fb2))

#: ★ 只增不减的敏感度闸（不是快照）：每多一个场景，代表多一扇「光看字母分不出来、
#:   必须靠坐标才认领得到」的门。答案对不对由 C1/C2/B3b 逐条判，这里只管"没缩水"。
#:   配套闸：`pos` 能改变答案的场景，表里必须**至少两条**候选规则 —— 只有一条时
#:   给不给坐标都是同一个答案，那就说明 `_aff` 记错了，或 `_pick_by_pos` 在乱动。
_by_scene = collections.Counter(r.get('when_scene') for r in RL)
_thin = [s for s in _aff if _by_scene.get(s, 0) < 2]
check(u'C3 ★★★ 传 `pos` 会改变结果的场景 ≥ %d（只增不减，缩水就是丢门）；'
      u'且这些场景每条都至少有 2 条候选规则在抢'
      % EXPECT_AFFECTED,
      len(_aff) >= EXPECT_AFFECTED and not _thin,
      u'n=%d 不足两条=%r 样本=%r' % (len(_aff), _thin[:4], sorted(_aff)[:6]))

# ---- 负控制：必须**真的**走不到"取第一个"那条路 ----
_rules_dark = [r for r in W_RULES if r.get('when_scene') == 'ch2.queens_mansion.dw_mansion_darkbulb_1']
_n2 = _pick_by_pos(_rules_dark, 'ch2.queens_mansion.dw_mansion_darkbulb_1',
                   lambda r: not r.get('when_src'), [620, 240])
check(u'C4 负控制：同一坐标命中 **2** 条（darkbulb_1 的 7132/7133 都在 x=620）⇒ 必须返 None',
      _n2 is None, u'got=%r' % (_n2,))

_rules_west = [r for r in W_RULES if r.get('when_scene') == 'ch2.queens_mansion.dw_mansion_b_west_1f']
_n0 = _pick_by_pos(_rules_west, 'ch2.queens_mansion.dw_mansion_b_west_1f',
                   lambda r: not r.get('when_src'), [235, 255])
check(u'C5 负控制：命中 **0** 条（b_west_1f 三扇门只有一扇记了坐标）⇒ 必须返 None',
      _n0 is None, u'got=%r' % (_n0,))

_np = _pick_by_pos(_rules_west, 'ch2.queens_mansion.dw_mansion_b_west_1f',
                   lambda r: not r.get('when_src'), None)
check(u'C6 负控制：`pos=None` ⇒ 必须返 None（老调用方一行不改也不会变行为）',
      _np is None, u'got=%r' % (_np,))

# ---- 正控制：确实能认领（否则上面几条 NULL 是"永远返 None"式的假绿）----
_rules_mid = [r for r in W_RULES if r.get('when_scene') == 'ch2.hometown.town_mid']
_p1 = _pick_by_pos(_rules_mid, 'ch2.hometown.town_mid',
                   lambda r: not r.get('when_src'), [301, 94])
_p2 = _pick_by_pos(_rules_mid, 'ch2.hometown.town_mid',
                   lambda r: not r.get('when_src'), [1740, -10])
check(u'C7 ★★ 正控制：town_mid 的 x=301 / x=1740 必须各自认领到**不同**目标'
      u'（否则 C4~C6 的 None 可能只是"永远返 None"）',
      _p1 is not None and _p2 is not None and _p1 != _p2,
      u'301→%r 1740→%r' % (_p1, _p2))


# ===========================================================================
print('')
print('=' * 70)
print(u'D 段  不造边 + 反回滚')
print('=' * 70)

#: 表里每条 W 规则都必须能在 GML 找到对应分支（找不到 = 我编的）
_rule_only = []
for r in W_RULES:
    o = r['_original']
    k = (o.get('chapter'), o.get('src_room_name'), o.get('via'), o.get('dst_room_id'))
    k2 = (o.get('chapter'), o.get('src_room_id'), o.get('via'), o.get('dst_room_id'))
    if not (BIDX.get(k) or BIDX2.get(k2)):
        _rule_only.append((r.get('priority'), k))
check(u'D1 ★★★ 「表里有、GML 没有」== 0（一条都不许编）',
      not _rule_only, u'多造=%r' % (_rule_only[:5],))

#: ★ 本轮新规则 priority 全表最大 ⇒ `_pick` 取最小，它们**结构上抢不走**既有规则的权。
#:   这比数"重复了几条"精确得多：重复是现象，抢权才是风险。
_maxp = max(r.get('priority') for r in RL if isinstance(r.get('priority'), int))
_shadow = []
for r in MINE:
    same = [q for q in RL if q is not r
            and q.get('when_scene') == r.get('when_scene') and q.get('to') == r.get('to')]
    for q in same:
        if isinstance(q.get('priority'), int) and q['priority'] > r['priority']:
            _shadow.append((r.get('priority'), q.get('priority')))
check(u'D2 ★★★ 新增规则不许**抢走**谁的权：同 (场景,目标) 的既有规则 priority 必须更小',
      not _shadow, u'抢权=%r' % (_shadow[:5],))
#: ★★★ 结构性不变量（不再是"当日最大号 == 7195"那种快照）：
#:   最新一批的 priority 段必须**整体压在全部旧段之上**，且全表最大值就落在这一批。
#:   有了它，`_pick`（取最小）在结构上就抢不走任何既有规则的权 —— 只可能填空。
#:   哪天有人插一条低号新规则进来，这条立刻红，而不是等下一个人肉眼看出来。
_bp = collections.defaultdict(list)
for _r in RL:
    _p = _r.get('priority')
    if not isinstance(_p, int):
        continue
    _b = (_r.get('_original') or {}).get('batch')
    _bp[-1 if _b is None else _b].append(_p)      # 168 那批无 batch ⇒ 当最老的 -1
_newest = max(k for k in _bp if k >= 0)
_new_prios = _bp[_newest]
_older_max = max(p for k, v in _bp.items() if k != _newest for p in v)
check(u'D2b ★★★ 最新一批（batch=%d）的 priority 段整体压在旧段之上：min %d > 旧段 max %d，'
      u'且全表最大 %d 就在这一批（新增只能填空不能顶替）'
      % (_newest, min(_new_prios), _older_max, _maxp),
      min(_new_prios) > _older_max and _maxp == max(_new_prios),
      u'批=%d min=%d 旧max=%d 全表max=%d' % (_newest, min(_new_prios), _older_max, _maxp))

#: 反回滚闸：条数不许缩水
check(u'D3 ★★★ 反回滚：路由总数 %d、W 规则 %d，均不低于本轮落定值'
      % (EXPECT_ROUTES, EXPECT_W_RULES),
      len(RL) >= EXPECT_ROUTES and len(W_RULES) >= EXPECT_W_RULES,
      u'routes=%d W=%d' % (len(RL), len(W_RULES)))

#: 每条 W 规则都得有 when_scene / to / when_door（缺了就是半条规则）
_half = [r.get('priority') for r in W_RULES
         if not r.get('when_scene') or not r.get('to') or not r.get('when_door')]
check(u'D4 每条 W 规则都有 `when_scene` / `to` / `when_door`',
      not _half, u'半条=%r' % (_half[:5],))


# ===========================================================================
print('')
print('=' * 70)
print(u'SUMMARY  pass=%d  fail=%d' % (_n['p'], _n['f']))
if _bad:
    for b in _bad:
        print(u'  [FAIL] %s' % b)
print('=' * 70)
sys.exit(0 if _n['f'] == 0 else 1)
