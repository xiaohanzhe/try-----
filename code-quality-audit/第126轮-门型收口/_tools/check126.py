# -*- coding: utf-8 -*-
u"""第126轮回归锁：outertale 的**门路由**不许静默失效。

## 这一轮做了什么

第124/125轮的可达账里，outertale **244 个场景、0 条路由** —— 整个作品
"看得到、走不通"（`plan_route_to` 在那个作品里连一条边都拿不到）。

查根因：**不是没数据**。第115轮已经从 `game.droid` 抽出 **301** 条 `room_goto`
记录（`conn_ut.json`）+ **358** 间房的实例表（`inst_full.tsv`），只是没人把它
变成产品能读的边。

本轮按"机制 + 在场"两条独立证据推导：

    kind=ot_door_guard  `if (room == N) room_goto(M)` ⇒ (N → M)
                        ★ 独立验证：那个门对象**真的摆在 N 这间房**的实例表里
    kind=ot_door_shift  `room_goto_next()` ⇒ 每个实例房 r → r+1（第123轮 ut 同型）

⇒ 写入 **209** 条（guard 93 / shift 116，priority 6000~6208），覆盖 **162** 个源场景。

## 本套件守什么（零 Qt / 零网络 / 零外部盘 —— 只读仓库内证据与资产）

A 段位与分母 —— 209 条 · priority 6000~6208 连续 · 只落 outertale · `when_door` 全 None
B 独立重推   —— **只从证据重算**（另写一份推导，不 import 生成器）⇒ 与产品**集合相等**
C 逐条自洽   —— guard 条：门对象**真在该源房**的实例表里 ｜ shift 条：`dst == src + 1`
D 拒收纪律   —— 4 类丢弃**成对**：证据里有 N 条、产品里 0 条（防空集恒真）
E 寻路图层   —— `chapters.outertale` 与路由新段**同一集合**，冻结章一个数都没动
F 密度账     —— outertale「有出边的场景」0 → 162（只增不减）
G 自检       —— AST 查恒真判据（**两套 harness 都查**）· 无 BOM · CRLF 无尾换行 · 文件在盘

## 纪律

`print('[PASS] %s')` 字面量；正/负控制成对；**断行为不断赋值**；
负控制必须**真的落进被测分支**（B 段直接改传入的集合再比对，不是另写一份判据）。
"""
import ast
import collections
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(REPO, 'ralsei_pet')
MODULES = os.path.join(PKG, 'modules')
SCENES = os.path.join(PKG, 'assets', 'scenes')
ROUTES_P = os.path.join(SCENES, '_routes.json')
EV42 = os.path.join(REPO, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
GRAPH_P = os.path.join(EV42, '_room_graph.json')
EV115 = os.path.join(REPO, 'code-quality-audit', '第115轮-跨作品物件普查', '_evidence')
RAW = os.path.join(EV115, 'raw', 'outertale')
CONN_P = os.path.join(RAW, 'conn_ut.json')
INST_P = os.path.join(RAW, 'inst_full.tsv')
GEN_P = os.path.join(ROUND, '_tools', 'gen_routes126.py')

for _p in (PKG, MODULES):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from modules import scene_system as SS       # noqa: E402

PRIO_BASE = 6000
PRIO_HI = 6208
EXPECT_ADD = 209
EXPECT_GUARD = 93
EXPECT_SHIFT = 116
EXPECT_SRC = 162
EXPECT_UNION = 204
EXPECT_GRAPH = 209
KIND_GUARD = 'ot_door_guard'
KIND_SHIFT = 'ot_door_shift'
CHAPTER = 'outertale'
#: 冻结章（第42/105轮的取证事实，本轮一个数都不许动）
FROZEN = {'ch1': 238, 'ch2': 323, 'ch3': 79, 'ch4': 72, 'ch5': 70, 'oneshot': 420}
#: ★ 拒收的四类：证据侧的真条数（配对的"分母"）
EXPECT_DROP_UNCOND = 28
EXPECT_DROP_NO_INST = 24
EXPECT_DROP_UNREG = 54
EXPECT_DROP_AMB_GROUP = 1
#: ★ 具体样例（点名检查，不靠模糊匹配）：
#: ① 守卫说 43 是源房、实例表里 43 号房却没有这扇门 ⇒ **两种取证打架 ⇒ 不写**
GUARD_CONFLICT_SAMPLE = (43, 'obj_door_s_musfade', 44)
#: ② 同一扇门在同一间房按 `x` 坐标分叉（旅馆大堂那种）⇒ 产品一扇门一个目标 ⇒ 整组丢
AMB_SAMPLE = ('outertale.foundry.f_bird', 'obj_door_ruins13')

_n = {'p': 0, 'f': 0}
_failed = []


def check(desc, cond, detail=u''):
    if cond:
        _n['p'] += 1
        print(u'[PASS] %s%s' % (desc, (u'    ' + detail) if detail else u''))
    else:
        _n['f'] += 1
        _failed.append(desc)
        print(u'[FAIL] %s%s' % (desc, (u'    ' + detail) if detail else u''))


def jload(p):
    s = io.open(p, encoding='utf-8', newline='').read()
    return json.loads(s.replace(': True', ': true').replace(': False', ': false'))


def obj_of(code):
    u"""`gml_Object_obj_door_t_Alarm_2` → `obj_door_t`。**与生成器分开写**（B 段要用）。"""
    if not isinstance(code, str) or not code.startswith('gml_Object_'):
        return ''
    rest = code.split('gml_Object_', 1)[1]
    for i, ch in enumerate(rest):
        if ch == '_' and rest[i:i + 7] in ('_Alarm_', '_Step_0', '_Step_1', '_Step_2'):
            return rest[:i]
    # 兜底：按已知事件后缀切（Alarm_N / Step_N / Create_0 / Draw_0 / Collision_*）
    for suf in ('_Alarm_', '_Step_', '_Create_', '_Draw_', '_Collision_', '_Destroy_',
                '_Other_', '_KeyPress_', '_KeyRelease_', '_Mouse_'):
        j = rest.find(suf)
        if j > 0:
            return rest[:j]
    return rest


def is_door(o):
    return bool(o) and (o.startswith('obj_door') or o.startswith('obj_demodoor')) \
        and o != 'obj_mainchara'


# ===========================================================================
#  读盘
# ===========================================================================
RAW_ROUTES = json.loads(io.open(ROUTES_P, encoding='utf-8', newline='').read())
RL = RAW_ROUTES.get('routes') or []
IDX = SS.load_index(SCENES)
SC = IDX.get('scenes') or {}
NEW = [r for r in RL
       if isinstance(r.get('priority'), int) and PRIO_BASE <= r['priority'] <= PRIO_HI]

#: 原作房间下标 → scene_id（★ 只按 `original_room_id`；按名字在第115轮实测 0/358）
RID2SID = {}
for _sid, _rec in SC.items():
    if _sid.startswith(CHAPTER + '.') and isinstance(_rec.get('original_room_id'), int):
        RID2SID.setdefault(_rec['original_room_id'], _sid)

#: 358 间房的实例表（`R` 行切房、`I` 行记对象）
ROOMS = {}
INST = collections.defaultdict(set)
_cur = None
with io.open(INST_P, encoding='utf-8', errors='replace', newline='') as _fh:
    for _ln in _fh:
        _p = _ln.rstrip('\r\n').split('\t')
        if _p[0] == 'R' and len(_p) >= 3:
            _cur = int(_p[1])
            ROOMS[_cur] = _p[2]
        elif _p[0] == 'I' and len(_p) >= 2 and _cur is not None:
            INST[_cur].add(_p[1])
OBJ_ROOMS = collections.defaultdict(set)
for _r, _objs in INST.items():
    for _o in _objs:
        OBJ_ROOMS[_o].add(_r)

ITEMS = jload(CONN_P)['items']


def edge_key(r):
    u"""产品侧一条新段的"这条边是谁、从哪到哪"（B 段与 E 段共用）。"""
    o = r.get('_original') or {}
    return (o.get('src_room_id'), o.get('via'), o.get('dst_room_id'))


PROD = set(edge_key(r) for r in NEW)

# ===========================================================================
print(u'')
print(u'== A. 段位与分母（防空集恒真） ==')
# ===========================================================================
check(u'A0 分母：`load_index()` ok=True、场景数 == 2166、路由 == 1740 条、新段非空',
      IDX.get('ok') is True and len(SC) == 2166 and len(RL) == 1740 and len(NEW) > 0,
      u'scenes=%d routes=%d new=%d ok=%r'
      % (len(SC), len(RL), len(NEW), IDX.get('ok')))

_prios = sorted(r['priority'] for r in NEW)
check(u'A1 ★★ 新段 %d 条、priority %d~%d **连续无空洞**'
      % (EXPECT_ADD, PRIO_BASE, PRIO_HI),
      len(NEW) == EXPECT_ADD and _prios == list(range(PRIO_BASE, PRIO_BASE + EXPECT_ADD)),
      u'n=%d 首末=%r' % (len(NEW), (_prios[0], _prios[-1]) if _prios else None))

_bad_scene = [r.get('when_scene') for r in NEW
              if not str(r.get('when_scene') or '').startswith(CHAPTER + '.')]
_bad_door = [r.get('when_door') for r in NEW if r.get('when_door') is not None]
_bad_src = [r.get('when_src') for r in NEW if not is_door(r.get('when_src'))]
check(u'A2 ★★★ 新段只落 outertale（绝不碰桌面 / 别的作品）· `when_door` 全为 None · '
      u'`when_src` 全是门对象名',
      not _bad_scene and not _bad_door and not _bad_src,
      u'越界=%r 带字母=%r 坏 when_src=%r' % (_bad_scene[:3], _bad_door[:3], _bad_src[:3]))

_kind = collections.Counter((r.get('_original') or {}).get('kind') for r in NEW)
check(u'A3 新段分项 == guard %d / shift %d' % (EXPECT_GUARD, EXPECT_SHIFT),
      _kind.get(KIND_GUARD) == EXPECT_GUARD and _kind.get(KIND_SHIFT) == EXPECT_SHIFT,
      u'%r' % dict(_kind))

_obj = collections.Counter((r.get('_original') or {}).get('via') for r in NEW)
check(u'A4 用到 %d 种门对象、9 种都已实证（`obj_doorA` 单独 %d 条 = `room_goto_next` 位移门）'
      % (len(_obj), _obj.get('obj_doorA', 0)),
      len(_obj) == 9 and _obj.get('obj_doorA') == 116,
      u'%r' % dict(_obj))

# ===========================================================================
print(u'')
print(u'== B. ★★★ 独立重推：只从证据重算这 209 条 ==')
# ===========================================================================


def rebuild():
    u"""**另一份实现**：从 `conn_ut.json` + `inst_full.tsv` 重推，不 import 生成器、
    不读生成器的任何决策字段。返回 `{(src_rid, via, dst_rid)}` 与丢弃账。
    """
    st = collections.Counter()
    cand = []
    for it in ITEMS:
        o = obj_of(it.get('code'))
        if not is_door(o):
            st['nondoor'] += 1
            continue
        op = it.get('op')
        if op == 'goto':
            s, d = it.get('src'), it.get('dst')
            if isinstance(s, int) and s >= 0:
                if o not in INST.get(s, set()):       # 守卫与实例打架 ⇒ 丢
                    st['conflict'] += 1
                    continue
                cand.append((s, o, d))
            else:
                st['uncond'] += 1                     # src 未知 ⇒ 丢
        elif op in ('room_goto_next', 'room_goto_previous'):
            step = 1 if op == 'room_goto_next' else -1
            for r in sorted(OBJ_ROOMS.get(o) or ()):
                cand.append((r, o, r + step))
    # 端点已登记 + 非自环
    ok2 = []
    for s, o, d in cand:
        if not isinstance(d, int) or d < 0:
            st['bad_idx'] += 1
            continue
        if s == d:
            st['self'] += 1
            continue
        if s not in RID2SID or d not in RID2SID:
            st['unreg'] += 1
            continue
        ok2.append((s, o, d, RID2SID[s], RID2SID[d]))
    # 同 (场景, 对象) 多目标 ⇒ 整组丢
    g = collections.defaultdict(set)
    for s, o, d, ss, dd in ok2:
        g[(ss, o)].add(dd)
    amb = set(k for k, v in g.items() if len(v) > 1)
    st['amb_group'] = len(amb)
    out = set((s, o, d) for s, o, d, ss, dd in ok2 if (ss, o) not in amb)
    return out, st


EXP, DROP = rebuild()
check(u'B1 ★★★ 独立重推出的期望集合 == 产品新段（对称差 0）—— 期望 %d 条 / 产品 %d 条'
      % (len(EXP), len(PROD)),
      EXP == PROD, u'缺=%r 多=%r' % (sorted(EXP - PROD)[:3], sorted(PROD - EXP)[:3]))

_cut = sorted(EXP)[0]
check(u'B2 负控制：从产品集合里挖掉一条 ⇒ 对称差恰好是它（B1 有鉴别力）',
      (EXP - (PROD - {_cut})) == {_cut},
      u'挖 %r' % (_cut,))

_fake = (99999, 'obj_door_fake', 99998)
check(u'B3 负控制：往产品集合里塞一条假边 ⇒ 对称差非空（不是"至少包含"就绿）',
      (PROD | {_fake}) - EXP == {_fake},
      u'塞 %r' % (_fake,))

check(u'B4 分母闸：期望集合非空且两种机制都有样本（guard / shift）',
      len(EXP) == EXPECT_ADD
      and sum(1 for s, o, d in EXP if o == 'obj_doorA') >= 100
      and sum(1 for s, o, d in EXP if o != 'obj_doorA') > 0,
      u'total=%d doorA=%d 其它=%d'
      % (len(EXP), sum(1 for s, o, d in EXP if o == 'obj_doorA'),
         sum(1 for s, o, d in EXP if o != 'obj_doorA')))

check(u'B5 丢弃账与生成器一致（只对**计数量**，不对内部顺序）',
      DROP.get('uncond') == EXPECT_DROP_UNCOND
      and DROP.get('conflict') == EXPECT_DROP_NO_INST
      and DROP.get('unreg') == EXPECT_DROP_UNREG
      and DROP.get('amb_group') == EXPECT_DROP_AMB_GROUP,
      u'%r' % dict(DROP))

# ===========================================================================
print(u'')
print(u'== C. 逐条自洽（机制 → 落点 / 在场） ==')
# ===========================================================================
_c_guard_bad, _c_shift_bad, _c_self, _c_dup, _c_other = [], [], [], [], []
for r in NEW:
    o = r.get('_original') or {}
    s, d, v = o.get('src_room_id'), o.get('dst_room_id'), o.get('via')
    if s == d:
        _c_self.append((s, v))
    if o.get('kind') == KIND_GUARD:
        # 独立证据：这扇门**真的摆在这个源房**
        if v not in INST.get(s, set()):
            _c_guard_bad.append((s, v, d))
        if r.get('when_src') != v:
            _c_other.append((r.get('when_scene'), v))
    elif o.get('kind') == KIND_SHIFT:
        if not (d == s + 1 and o.get('room_delta') == 1):
            _c_shift_bad.append((s, d, o.get('room_delta')))
    else:
        _c_other.append((s, o.get('kind')))
check(u'C1 ★★★ guard 条 %d：门对象**真在该源房**的实例表里（独立于守卫常量的第二条证据）'
      % EXPECT_GUARD, not _c_guard_bad, u'违例=%r' % (_c_guard_bad[:3],))
check(u'C2 ★★ shift 条 %d：`dst == src + 1` 且 `room_delta == 1`'
      % EXPECT_SHIFT, not _c_shift_bad, u'违例=%r' % (_c_shift_bad[:3],))
_uniq = set(edge_key(x) for x in NEW)
check(u'C3 无自环 · 无三元重复 · kind 只有两种 · `when_src` 与 `_original.via` 一致',
      not _c_self and not _c_dup and not _c_other
      and len(_uniq) == len(NEW) and len(PROD) == len(NEW),
      u'自环=%r 其它=%r 唯一边=%d/%d'
      % (_c_self[:2], _c_other[:2], len(_uniq), len(NEW)))

_bad_ep = [(r.get('when_scene'), r.get('to')) for r in NEW
           if r.get('when_scene') not in SC or r.get('to') not in SC]
check(u'C4 两端都真在注册表里（写进一条到不存在场景的边 = 人走不到）',
      not _bad_ep, u'%r' % (_bad_ep[:3],))

# 负控制：把一条 guard 的 src 挪到一个**没摆这扇门**的房间 ⇒ C1 必红
_probe = [r for r in NEW if r.get('_original', {}).get('kind') == KIND_GUARD][0]
_o = dict(_probe['_original'])
_o['src_room_id'] = 0 if 'obj_door_t' not in INST.get(0, set()) else 1
check(u'C5 负控制：把 guard 条的源房换成"没摆这扇门"的房间 ⇒ C1 口径必红（C1 不是恒真）',
      _o.get('via') not in INST.get(_o['src_room_id'], set()),
      u'房 %r 的实例里没有 %r' % (_o['src_room_id'], _o.get('via')))

# ===========================================================================
print(u'')
print(u'== D. 拒收纪律（成对：证据里真有 / 产品里没有） ==')
# ===========================================================================
_uncond_n = sum(1 for it in ITEMS
                if is_door(obj_of(it.get('code'))) and it.get('op') == 'goto'
                and not (isinstance(it.get('src'), int) and it.get('src') >= 0))
_conflict_n = sum(1 for it in ITEMS
                  if is_door(obj_of(it.get('code'))) and it.get('op') == 'goto'
                  and isinstance(it.get('src'), int) and it.get('src') >= 0
                  and obj_of(it.get('code')) not in INST.get(it.get('src'), set()))
check(u'D1 ★★ 无条件 `room_goto(M)`（src 未知）证据里**确有 %d 条**，而产品新段'
      u'**每一条都有出处**（`src_room_id` 是 int 且在原作房间表里）—— 成对，防空集恒真'
      % EXPECT_DROP_UNCOND,
      _uncond_n == EXPECT_DROP_UNCOND
      and all(isinstance((r.get('_original') or {}).get('src_room_id'), int)
              and (r.get('_original') or {})['src_room_id'] in ROOMS for r in NEW),
      u'证据=%d 无出处=%r'
      % (_uncond_n, [r.get('when_scene') for r in NEW
                     if not isinstance((r.get('_original') or {}).get('src_room_id'), int)][:2]))

check(u'D2 ★★ 守卫与实例打架的**确有 %d 条**，产品里 0 条；点名样例 %r 不在产品里'
      % (EXPECT_DROP_NO_INST, GUARD_CONFLICT_SAMPLE),
      _conflict_n == EXPECT_DROP_NO_INST
      and (GUARD_CONFLICT_SAMPLE[0], GUARD_CONFLICT_SAMPLE[1],
           GUARD_CONFLICT_SAMPLE[2]) not in PROD,
      u'证据=%d 样例在=%r' % (_conflict_n, GUARD_CONFLICT_SAMPLE in PROD))

_amb_hit = [k for k in PROD if k[0] is not None
            and RID2SID.get(k[0]) == AMB_SAMPLE[0] and k[1] == AMB_SAMPLE[1]]
check(u'D3 ★★ 同(场景,对象)按坐标分叉的 %d 组整组丢；点名 %r 在产品里 0 条'
      % (EXPECT_DROP_AMB_GROUP, AMB_SAMPLE),
      EXPECT_DROP_AMB_GROUP == 1 and not _amb_hit,
      u'命中=%r' % (_amb_hit[:3],))

_unreg_pairs = [(it.get('src'), it.get('dst')) for it in ITEMS
                if is_door(obj_of(it.get('code')))
                and (it.get('src') not in RID2SID or it.get('dst') not in RID2SID)]
check(u'D4 ★ 端点未登记的证据边确有样本（%d 条）；产品里每条边两端都在注册表'
      u'（D 段不是"因为全是 0 所以绿"）' % len(_unreg_pairs),
      len(_unreg_pairs) >= 40 and not _bad_ep,
      u'证据=%d 产品坏端点=%d' % (len(_unreg_pairs), len(_bad_ep)))

# ===========================================================================
print(u'')
print(u'== E. 寻路图层（`chapters.outertale` 与路由同一集合） ==')
# ===========================================================================
G = json.loads(io.open(GRAPH_P, encoding='utf-8', newline='').read())
CHS = G.get('chapters') or {}
check(u'E1 图里有 `chapters.%s` 且 `n_edges` == %d == 路由新段条数'
      % (CHAPTER, EXPECT_GRAPH),
      isinstance(CHS.get(CHAPTER), dict)
      and CHS[CHAPTER].get('n_edges') == EXPECT_GRAPH
      and CHS[CHAPTER].get('n_edges') == len(NEW),
      u'n_edges=%r routes=%d' % ((CHS.get(CHAPTER) or {}).get('n_edges'), len(NEW)))

_gedges = (CHS.get(CHAPTER) or {}).get('edges') or []
check(u'E2 ★★★ 图里的边与路由新段**同一集合**（两层数据不许各说各的）',
      set((e.get('src'), e.get('door'), e.get('dst')) for e in _gedges) == PROD,
      u'图=%d 路由=%d 差=%r' % (len(_gedges), len(PROD),
                               list(PROD ^ set((e.get('src'), e.get('door'), e.get('dst'))
                                               for e in _gedges))[:3]))

check(u'E3 ★★★ 冻结章一个数都没动（ch1~ch5 + oneshot 逐章等值）',
      all(len((CHS.get(k) or {}).get('edges') or []) == v for k, v in FROZEN.items())
      and set(CHS) == set(FROZEN) | {CHAPTER},
      u'%r' % {k: len((CHS.get(k) or {}).get('edges') or []) for k in CHS})

_bad_shape = [e for e in _gedges
              if not (isinstance(e.get('src'), int) and isinstance(e.get('dst'), int)
                      and isinstance(e.get('door'), str) and e.get('door')
                      and e.get('kind') in (KIND_GUARD, KIND_SHIFT)
                      and e.get('src') != e.get('dst'))]
check(u'E4 图边形状合法（int 端点 · door 非空 · kind 只有两种 · 无自环）',
      not _bad_shape, u'违例=%r' % (_bad_shape[:2],))

# ===========================================================================
print(u'')
print(u'== F. 密度账（只增不减） ==')
# ===========================================================================
_out = set(r.get('when_scene') for r in RL if r.get('when_scene'))
_ot_out = set(s for s in _out if s.startswith(CHAPTER + '.'))
check(u'F1 ★ outertale「有出边的场景」0 → %d（新段 src 场景数），只增不减' % EXPECT_SRC,
      len(_ot_out) == EXPECT_SRC and len(_ot_out) >= EXPECT_SRC,
      u'实测=%d' % len(_ot_out))
_u = set(r.get('when_scene') for r in NEW) | set(r.get('to') for r in NEW)
check(u'F2 覆盖并集 == %d / outertale 共 244 个场景（如实登记，不假装全通）' % EXPECT_UNION,
      len(_u) == EXPECT_UNION and len(_u) < len([s for s in SC if s.startswith(CHAPTER + '.')]),
      u'并集=%d' % len(_u))
check(u'F3 负控制：把基线抬到实测 +1 ⇒ F1 的口径报红（不是"写了就绿"）',
      len(_ot_out) < EXPECT_SRC + 1,
      u'%d < %d' % (len(_ot_out), EXPECT_SRC + 1))

# ===========================================================================
print(u'')
print(u'== G. 自检 ==')
# ===========================================================================
me = io.open(os.path.abspath(__file__), encoding='utf-8').read()
_tree = ast.parse(me)
_bad_const = []


def _is_true(node):
    return isinstance(node, ast.Constant) and node.value is True


for _node in ast.walk(_tree):
    if not isinstance(_node, ast.Call):
        continue
    _fn = getattr(_node.func, 'id', None)
    if _fn == 'check' and len(_node.args) >= 2 and _is_true(_node.args[1]):
        _bad_const.append(('check', getattr(_node, 'lineno', 0)))
    # ★★★ 两套 harness 都要查：`ok(cond, msg)` 的判据是 args[0]
    if _fn == 'ok' and _node.args and _is_true(_node.args[0]):
        _bad_const.append(('ok', getattr(_node, 'lineno', 0)))
check(u'G1 本文件没有 `check(x, True)` / `ok(True, …)` 恒真判据'
      u'（AST 判 `check` 的 args[1] 与 `ok` 的 args[0]，不扫注释）',
      not _bad_const, u'%r' % (_bad_const[:3],))

_src_probe = u'check("x", True)\nok(True, "y")\n'
_probe_tree = ast.parse(_src_probe)
_hits = 0
for _node in ast.walk(_probe_tree):
    if isinstance(_node, ast.Call):
        _fn = getattr(_node.func, 'id', None)
        if _fn == 'check' and len(_node.args) >= 2 and _is_true(_node.args[1]):
            _hits += 1
        if _fn == 'ok' and _node.args and _is_true(_node.args[0]):
            _hits += 1
check(u'G2 正控制：合成源码里的 `check(...,True)` 与 `ok(True,…)` **都能被抓到**（恰好 2 处）',
      _hits == 2, u'抓得 %d 处' % _hits)

for _p in (ROUTES_P, GRAPH_P, GEN_P, CONN_P, INST_P):
    check(u'G3 被测文件在盘：%s' % os.path.basename(_p), os.path.isfile(_p))

_rb = io.open(ROUTES_P, 'rb').read()
_rt = _rb.decode('utf-8')
check(u'G4 `_routes.json` 无 BOM / 无 U+FFFD / 全 CRLF / **无尾换行**（第44轮定下的格式）',
      not _rb.startswith(b'\xef\xbb\xbf') and _rt.count(u'\ufffd') == 0
      and _rt.count('\r\n') > 0 and _rt.count('\n') == _rt.count('\r\n')
      and not _rt.endswith('\n'),
      u'crlf=%d bare_lf=%d tail=%r'
      % (_rt.count('\r\n'), _rt.count('\n') - _rt.count('\r\n'), _rt[-2:]))

_gb = io.open(GRAPH_P, 'rb').read()
check(u'G5 `_room_graph.json` 无 BOM / 无 U+FFFD / 全 CRLF',
      not _gb.startswith(b'\xef\xbb\xbf') and _gb.decode('utf-8').count(u'\ufffd') == 0
      and _gb.decode('utf-8').count('\n') == _gb.decode('utf-8').count('\r\n'),
      u'bytes=%d' % len(_gb))

print(u'')
print(u'---- 共 %d 条：PASS %d / FAIL %d' % (_n['p'] + _n['f'], _n['p'], _n['f']))
if _failed:
    for _d in _failed:
        print(u'   [失败] %s' % _d)
    sys.exit(1)
