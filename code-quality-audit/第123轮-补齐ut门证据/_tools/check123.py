# -*- coding: utf-8 -*-
u"""第123轮回归锁：ut 的**位移门**（`room_goto(room_prev/next(...))`）不许静默失效。

## 本套件守什么（零 Qt、零网络、零外部盘 —— 只读仓库内资产）

A 规模与形状 —— ut 段 525 条（122 的 243 + 本轮 282）· priority 4000~4524 **连续无洞** ·
  两端已登记 · 无自环 · **同场景同字母唯一**（`verify_routes_order44` 的硬闸）
B ★★★ **独立重算**（本套件最硬的一条）—— 从 `door_codes123.json`（UTMT 反编译原文）
  + `door_objects123.json`（父链）+ `inst_full.tsv`（实例）**自己再推一遍**
  `(场景, 门) → 目标`，与产品逐条比；缺 / 多 / 目标不同 三项必须全 0。
  ★ **故意不复用生成器的正则**：这里用手工括号匹配解析 `room_goto(...)`，
    两种实现都算出同一张表才算"证据成立"（同一实现自证等于没验）。
C 覆盖与账 —— `objects` 里的门组 == 路由表组（点不动 0 / 幽灵 0）；
  覆盖实例 **1,233 / 1,299 = 94.9%**；剩下 66 个必须逐类有出处（不是"忘了"）
D 产品接线（行为级）—— 真跑 `build_props`：`obj_doorB` 建出的门去 `房间号 −1`；
  `obj_doorAmusicfade`（无字母）走 `when_src`；两路互不串台
E 防回滚 —— ut 段 ≥ 525 · shift 条 ≥ 282 · 覆盖实例 ≥ 1,233
F 自检 —— AST 数恒真判据（不扫注释）+ 无 BOM
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
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
MODULES = os.path.join(REPO, 'ralsei_pet', 'modules')
RAW = os.path.join(ROUND, '_evidence', 'raw', 'ut')
RAW115 = os.path.join(os.path.dirname(ROUND), '第115轮-跨作品物件普查', '_evidence', 'raw', 'ut')
FACT122 = os.path.join(os.path.dirname(ROUND), '第122轮-ut门与房间连接', '_evidence',
                       'ut_doors122.json')

sys.path.insert(0, MODULES)
import item_interact as II       # noqa: E402

EXPECT_UT = 525
EXPECT_NEW = 282
EXPECT_110_133 = (110, 133)
EXPECT_COVERED = 1233
EXPECT_DOOR_INST = 1299
EXPECT_OBJ_ENTRIES = 1655
EXPECT_OBJ_SCENES = 274
PRIO_BASE = 4000

_n = {'p': 0, 'f': 0}
_failed = []


def check(desc, cond, detail=''):
    if cond:
        _n['p'] += 1
        print(u'[PASS] %s%s' % (desc, (u'    ' + detail) if detail else u''))
    else:
        _n['f'] += 1
        _failed.append(desc)
        print(u'[FAIL] %s%s' % (desc, (u'    ' + detail) if detail else u''))


def _json(p):
    with io.open(p, encoding='utf-8', newline='') as f:
        return json.load(f)


def _rows(p):
    for ln in io.open(p, encoding='utf-8', newline='').read().split('\n'):
        if ln:
            yield ln.split('\t')


# ---------- 载入 ----------
ZONE = _json(os.path.join(SCENES, '_zone.ut.rooms.json'))['scenes']
ROUTES = _json(os.path.join(SCENES, '_routes.json'))
RL = ROUTES.get('routes') or []
UT = [r for r in RL if str((r or {}).get('when_scene') or '').startswith('ut.')]
SHIFT = [r for r in UT if (r.get('_original') or {}).get('kind') == 'ut_door_shift']

CODES = _json(os.path.join(RAW, 'door_codes123.json'))['codes']
OBJS_RAW = _json(os.path.join(RAW, 'door_objects123.json'))['objects']
OBJS = set(r[1] for r in _rows(os.path.join(RAW115, 'objmap_ut.txt'))
           if len(r) >= 5 and r[0] != 'GameObjects')

INSTS = collections.Counter()
_cur = None
for _r in _rows(os.path.join(RAW115, 'inst_full.tsv')):
    if _r[0] == 'R':
        _cur = _r[2]
    elif _r[0] == 'I' and _cur is not None:
        INSTS[(_cur, _r[1])] += 1

NAME2SID, RID2SID = {}, {}
for _sid, _sc in ZONE.items():
    if not isinstance(_sc, dict):
        continue
    NAME2SID[_sc.get('name')] = _sid
    if isinstance(_sc.get('original_room_id'), int):
        RID2SID[_sc['original_room_id']] = _sid

DOOR_KINDS = set(o for o in OBJS if (II.classify(o) or {}).get('kind') == 'door')
N_DOOR_INST = sum(n for (rn, o), n in INSTS.items() if o in DOOR_KINDS)


# ===========================================================================
# B 用的**独立解析器**：手工括号匹配，不用生成器那套正则
# ===========================================================================
def _calls(src, fname):
    u"""取出 `fname(...)` 的所有调用实参文本（**括号配对**，不靠正则贪婪）。"""
    out = []
    i = 0
    while True:
        j = src.find(fname + '(', i)
        if j < 0:
            break
        # 左边必须是词边界（否则 `room_next(` 会误命中 `xxx_room_next(`）
        if j > 0 and (src[j - 1].isalnum() or src[j - 1] == '_'):
            i = j + 1
            continue
        k = j + len(fname) + 1
        depth, start = 1, k
        while k < len(src) and depth:
            if src[k] == '(':
                depth += 1
            elif src[k] == ')':
                depth -= 1
            k += 1
        if depth == 0:
            out.append(src[start:k - 1])
        i = k
    return out


def _shift_from_src(src):
    u"""`room_goto(<expr>)` → 位移。

    `<expr>` 只认这几种（其余返 None，不猜）：
      `room_next(room)` / `room_previous(room)` / `room_next(room_next(room))` /
      `room_previous(room_previous(room))` / 单独的 `room_goto_next()` / `room_goto_previous()`
    """
    offs = set()
    for arg in _calls(src, 'room_goto'):
        a = u''.join(arg.split())
        if a == 'room_next(room)':
            offs.add(1)
        elif a == 'room_previous(room)':
            offs.add(-1)
        elif a == 'room_next(room_next(room))':
            offs.add(2)
        elif a == 'room_previous(room_previous(room))':
            offs.add(-2)
    for arg in _calls(src, 'room_goto_next'):
        if not arg.strip():
            offs.add(1)
    for arg in _calls(src, 'room_goto_previous'):
        if not arg.strip():
            offs.add(-1)
    if len(offs) != 1:
        return None
    return next(iter(offs))


def _cond_rooms(src):
    u"""`if (<条件>)` 里点名的房间 —— 手工配对取条件文本，不在整段里乱扫。"""
    out = set()
    i = 0
    while True:
        j = src.find('if', i)
        if j < 0:
            break
        if j > 0 and (src[j - 1].isalnum() or src[j - 1] == '_'):
            i = j + 2
            continue
        k = src.find('(', j)
        if k < 0:
            break
        depth, p = 1, k + 1
        while p < len(src) and depth:
            if src[p] == '(':
                depth += 1
            elif src[p] == ')':
                depth -= 1
            p += 1
        cond = src[k + 1:p - 1]
        if 'room' in cond:
            # 条件里的 room_xxx（`room` 本身不算）
            buf, cur = [], ''
            for ch in cond:
                if ch.isalnum() or ch == '_':
                    cur += ch
                else:
                    if cur:
                        buf.append(cur)
                    cur = ''
            if cur:
                buf.append(cur)
            for tok in buf:
                if tok.startswith('room_') and tok != 'room_next' and tok != 'room_previous':
                    out.add(tok[len('room_'):])
        i = p
    return out


def _mechanism():
    u"""{对象: (off 或 None, 真源对象, cond_rooms)} —— 沿父链解析 `Alarm_2`。"""
    names = set(o['name'] for o in OBJS_RAW)
    parent = {o['name']: (o.get('parent') or '') for o in OBJS_RAW}
    src_of, code_of = {}, {}
    for it in CODES:
        nm = it['name']
        if not nm.startswith('gml_Object_'):
            continue
        tail = nm[len('gml_Object_'):]
        best = None
        for o in names:
            if (tail == o or tail.startswith(o + '_')) and (best is None or len(o) > len(best)):
                best = o
        if not best:
            continue
        ev = tail[len(best) + 1:] if tail != best else ''
        src_of[(best, ev)] = it['src']
        code_of[(best, ev)] = nm
    out = {}
    for o in sorted(names):
        cur, seen, found = o, set(), None
        while cur and cur not in seen:
            seen.add(cur)
            if (cur, 'Alarm_2') in src_of:
                found = cur
                break
            cur = parent.get(cur, '')
        if found is None:
            out[o] = (None, None, [])
            continue
        s = src_of[(found, 'Alarm_2')]
        out[o] = (_shift_from_src(s), found, sorted(_cond_rooms(s)))
    return out


MECH = _mechanism()


def _recount():
    u"""独立重推 shift 批：`(when_scene, when_src, when_door) -> to`。

    ★ 与生成器同一套**语义**（这点必须一致，否则验的不是同一件事），
      但实现是分开写的：这里用 `_calls`/`_cond_rooms` 手工解析，生成器用正则。
    ★ 也要做同样的去重：
      · 第122轮已经写过的 (房间, 字母) / (房间, 对象) 不重复写（本轮不覆盖 122）
      · 同场景同字母/同对象若出现两个目标 ⇒ 整键丢弃（不猜）
    """
    old_L, old_S = set(), set()
    for r in UT:
        k = (r.get('_original') or {}).get('kind')
        if k not in ('ut_door_src', 'ut_door_next'):
            continue
        rn = (r.get('_original') or {}).get('src_room_name')
        if r.get('when_src'):
            old_S.add((rn, r['when_src']))
        else:
            old_L.add((rn, r.get('when_door')))

    cand = {}
    for (rn, o), _n_inst in sorted(INSTS.items()):
        if o not in DOOR_KINDS:
            continue
        if (rn, o) in old_S:
            continue
        off, src_obj, conds = MECH.get(o, (None, None, []))
        if off is None:
            continue
        sid = NAME2SID.get(rn)
        rid = ZONE.get(sid, {}).get('original_room_id') if sid else None
        if not isinstance(rid, int):
            continue
        if rn in conds:
            continue
        dst = RID2SID.get(rid + off)
        if not dst or dst == sid:
            continue
        letter = II.door_letter_of(o)
        key = ('L', sid, letter) if letter else ('S', sid, o)
        if key[0] == 'L' and (rn, letter) in old_L:
            continue
        if key in cand and cand[key] != dst:
            cand[key] = None
            continue
        cand[key] = dst if key not in cand else cand[key]
    return dict((k, v) for k, v in cand.items() if v)


print(u'== A. 规模与形状 ==')
_kind = collections.Counter((r.get('_original') or {}).get('kind') for r in UT)
check(u'A0 ut 段 %d 条 = src %d + next %d + shift %d'
      % (len(UT), _kind['ut_door_src'], _kind['ut_door_next'], _kind['ut_door_shift']),
      len(UT) == EXPECT_UT and _kind['ut_door_shift'] == EXPECT_NEW
      and (_kind['ut_door_src'], _kind['ut_door_next']) == EXPECT_110_133
      and sum(_kind.values()) == len(UT),
      repr(dict(_kind)))

_pr = sorted(r['priority'] for r in UT)
check(u'A1 priority 独立段 %d~%d **连续无洞**（%d 个值）'
      % (PRIO_BASE, PRIO_BASE + len(UT) - 1, len(set(_pr))),
      _pr == list(range(PRIO_BASE, PRIO_BASE + len(UT))),
      u'实测 %s~%s / 去重 %d' % (_pr[0] if _pr else None, _pr[-1] if _pr else None, len(set(_pr))))

_bad_ref = [r for r in UT if r.get('when_scene') not in ZONE or r.get('to') not in ZONE]
_self = [r for r in UT if r.get('when_scene') == r.get('to')]
check(u'A2 两端都已登记（坏 %d）/ 无自环（%d）' % (len(_bad_ref), len(_self)),
      not _bad_ref and not _self,
      repr((_bad_ref[:2], _self[:2])))

# 同场景同字母唯一（这是 verify_routes_order44 的硬闸，段长大以后更要守）
_dup = collections.Counter((r['when_scene'], r.get('when_door')) for r in UT
                           if r.get('when_door'))
_dup = {k: v for k, v in _dup.items() if v > 1}
check(u'A3 ★ 同场景同字母唯一（重复 %d 组）' % len(_dup), not _dup, repr(list(_dup)[:3]))

_bad_src = [r for r in UT if r.get('when_src') and r['when_src'] not in OBJS]
_bad_door = [r for r in UT if not r.get('when_src')
             and r.get('when_door') not in II.DOOR_LETTERS]
check(u'A4 `when_src` 都在 ut objmap（坏 %d）／字母都合法（坏 %d）'
      % (len(_bad_src), len(_bad_door)),
      not _bad_src and not _bad_door, repr((_bad_src[:2], _bad_door[:2])))

_shift_off = collections.Counter((r.get('_original') or {}).get('off') for r in SHIFT)
_shift_via = collections.Counter((r.get('_original') or {}).get('via') for r in SHIFT)
check(u'A5 shift 批只含已实证的位移 %s；对象只在 %s'
      % (sorted(_shift_off), sorted(_shift_via)),
      set(_shift_off) == {-2, -1, 1, 2} and set(_shift_via) == {
          'obj_doorA', 'obj_doorAmusicfade', 'obj_papdoor', 'obj_doorB', 'obj_doorBmusicfade',
          'obj_doorC', 'obj_doorCmusicfade', 'obj_doorD', 'obj_doorDmusicfade'},
      repr((dict(_shift_off), dict(_shift_via))))

print(u'')
print(u'== B. 独立重算（手工括号解析，不复用生成器正则）==')
EXPECT = _recount()
HAVE = {}
for r in SHIFT:
    o = r.get('when_src')
    key = ('L' if r.get('when_door') else 'S', r['when_scene'],
           r.get('when_door') or o)
    HAVE[key] = r['to']
_KEY = lambda k: (k[0], k[1], k[2] or '')
_missing = sorted(set(EXPECT) - set(HAVE), key=_KEY)
_extra = sorted(set(HAVE) - set(EXPECT), key=_KEY)
_diff = sorted((k for k in (set(EXPECT) & set(HAVE)) if EXPECT[k] != HAVE[k]), key=_KEY)
check(u'B1 重推 %d 条（字母级 %d / 对象级 %d）；缺 %d / 多 %d / 目标不同 %d'
      % (len(EXPECT), sum(1 for k in EXPECT if k[0] == 'L'),
         sum(1 for k in EXPECT if k[0] == 'S'),
         len(_missing), len(_extra), len(_diff)),
      not _missing and not _extra and not _diff and len(EXPECT) == EXPECT_NEW,
      repr((_missing[:2], _extra[:2], _diff[:2])))

# B2 负控制：改掉一条目标 ⇒ 必须报红
if HAVE:
    _k0 = sorted(HAVE, key=_KEY)[0]
    _mut = dict(HAVE)
    _mut[_k0] = '__WRONG__'
    _m_missing = [k for k in EXPECT if k not in _mut or _mut[k] != EXPECT[k]]
    check(u'B2 负控制：改掉一条目标后重算必报红（%d 处不一致）' % len(_m_missing),
          bool(_m_missing), repr(_k0))
# B3 正控制：目标一字不改 ⇒ 完全一致（证明 B1 不是恒假）
check(u'B3 正控制：产品条目与重推结果**逐条相等**', HAVE == EXPECT,
      u'%d vs %d' % (len(HAVE), len(EXPECT)))
# B4 分母闸：重推不许退化成空
check(u'B4 重推结果非空且两类都有（字母 %d / 对象 %d）'
      % (sum(1 for k in EXPECT if k[0] == 'L'), sum(1 for k in EXPECT if k[0] == 'S')),
      len(EXPECT) == EXPECT_NEW and any(k[0] == 'L' for k in EXPECT)
      and any(k[0] == 'S' for k in EXPECT))
# B5 机制表自证：继承链真的解析到父对象（不是"全都无机制"）
_inh = {o: m[1] for o, m in MECH.items() if m[0] is not None and m[1] != o}
check(u'B5 ★机制表里 %d 个对象是**继承**来的（%s）—— 父链解析真的生效'
      % (len(_inh), sorted(_inh)),
      set(_inh) >= {'obj_doorAmusicfade', 'obj_doorBmusicfade'}, repr(dict(_inh)))
_cond = {o: m[2] for o, m in MECH.items() if m[0] is not None and m[2]}
check(u'B6 ★条件分支房间被识别：%s' % sorted(_cond),
      'obj_doorA' in _cond and 'castle_prebarrier' in _cond['obj_doorA'], repr(_cond))

print(u'')
print(u'== C. 覆盖与账 ==')
_have_doors = set()
for _sid, _sc in ZONE.items():
    if not isinstance(_sc, dict):
        continue
    for _e in (_sc.get('objects') or []):
        if (II.classify((_e or {}).get('src')) or {}).get('kind') == 'door':
            _have_doors.add((_sc.get('name'), _e['src']))
_routed = set()
for r in UT:
    o = r.get('when_src') or (r.get('_original') or {}).get('via') or 'obj_doorA'
    _routed.add(((r.get('_original') or {}).get('src_room_name'), o))
check(u'C1 `objects` 里的门 %d 组 == 路由表 %d 组（点不动 %d / 幽灵 %d）'
      % (len(_have_doors), len(_routed), len(_have_doors - _routed),
         len(_routed - _have_doors)),
      _have_doors == _routed and len(_have_doors) == EXPECT_UT,
      repr((sorted(_have_doors - _routed)[:3], sorted(_routed - _have_doors)[:3])))

_n_obj = sum(len((s or {}).get('objects') or []) for s in ZONE.values() if isinstance(s, dict))
_n_sc = sum(1 for s in ZONE.values() if isinstance(s, dict) and s.get('objects'))
_n_door_obj = sum(1 for s in ZONE.values() if isinstance(s, dict)
                  for e in (s.get('objects') or [])
                  if (II.classify((e or {}).get('src')) or {}).get('kind') == 'door')
check(u'C2 `_zone.ut.rooms.json` %d 条 / %d 场景（门 %d + 物 %d）'
      % (_n_obj, _n_sc, _n_door_obj, _n_obj - _n_door_obj),
      _n_obj == EXPECT_OBJ_ENTRIES and _n_sc == EXPECT_OBJ_SCENES
      and _n_door_obj == EXPECT_COVERED,
      u'%d / %d / %d' % (_n_obj, _n_sc, _n_door_obj))

_cov_inst = sum(n for k, n in INSTS.items() if k in _routed)
check(u'C3 覆盖门实例 %d / %d = %.1f%%（下界 %d）'
      % (_cov_inst, N_DOOR_INST, 100.0 * _cov_inst / max(1, N_DOOR_INST), EXPECT_COVERED),
      N_DOOR_INST == EXPECT_DOOR_INST and _cov_inst == EXPECT_COVERED,
      u'%d / %d' % (_cov_inst, N_DOOR_INST))

# C4 剩下的 66 个必须**逐类有出处**（不是"忘了"）：只允许 无机制 / 条件分支 / 越界 三种
_left = collections.Counter()
for (rn, o), n in INSTS.items():
    if o not in DOOR_KINDS or (rn, o) in _routed:
        continue
    _left[o] += n
_left_bad = [o for o in _left if MECH.get(o, (None,))[0] is not None]
check(u'C4 ★未覆盖的 %d 个实例**全部**来自"没有位移写法"的门（另有机制的混进来 %d 个）'
      % (sum(_left.values()), len(_left_bad)),
      sum(_left.values()) == EXPECT_DOOR_INST - EXPECT_COVERED and not _left_bad,
      repr((dict(_left), _left_bad[:3])))

print(u'')
print(u'== D. 产品接线（行为级）==')


def _mk_scene(rn):
    sid = NAME2SID[rn]
    sc = dict(ZONE[sid])
    sc['scene_id'] = sid
    return sc


# D1 字母级：obj_doorB 的门必须去「房间号 −1」
_byr = collections.defaultdict(list)
for r in RL:
    _byr[r.get('when_scene')].append(r)
_probe = None
for r in SHIFT:
    if (r.get('_original') or {}).get('via') == 'obj_doorB' and r.get('when_door') == 'B' \
            and r.get('when_src') is None:
        _probe = r
        break
_got = None
if _probe:
    rn = _probe['_original']['src_room_name']
    sc = _mk_scene(rn)
    props = II.build_props(sc, 'ut', 'light', routes=RL)
    want = [p for p in props if getattr(p, 'src', None) == 'obj_doorB']
    _got = [(p.door_letter, getattr(p, 'target_scene', None) or getattr(p, 'to', None))
            for p in want]
check(u'D1 行为：%s 的 obj_doorB 建出门且目标是 B 规则给的房间（%s）'
      % (_probe['_original']['src_room_name'] if _probe else '?', _got),
      bool(_probe) and bool(_got) and all(g[0] == 'B' for g in _got)
      and all(g[1] == _probe['to'] for g in _got), repr(_got))

# D2 对象级：obj_doorAmusicfade（`door_letter_of` 返回 None）必须靠 when_src 才建得出来
_probe2 = None
for r in SHIFT:
    if r.get('when_src') == 'obj_doorAmusicfade':
        _probe2 = r
        break
_got2, _got2_noroute = [], []
if _probe2:
    rn = _probe2['_original']['src_room_name']
    sc = _mk_scene(rn)
    _got2 = [p for p in II.build_props(sc, 'ut', 'light', routes=RL)
             if getattr(p, 'src', None) == 'obj_doorAmusicfade']
    _only_letter = [p for p in II.build_props(
        sc, 'ut', 'light', routes=[x for x in RL
                    if not (x.get('when_scene') == _probe2['when_scene']
                            and x.get('when_src') == 'obj_doorAmusicfade')])
        if getattr(p, 'src', None) == 'obj_doorAmusicfade']
    _got2_noroute = _only_letter
check(u'D2 行为：obj_doorAmusicfade 只有 `when_src` 那条能建门（撤掉它 ⇒ %d 扇）'
      % len(_got2_noroute),
      bool(_probe2) and len(_got2) >= 1 and not _got2_noroute,
      u'有路由 %d / 撤掉 %d' % (len(_got2), len(_got2_noroute)))

print(u'')
print(u'== E. 防回滚 ==')
check(u'E1 ut 段 ≥ %d 条（防批量删路由）' % EXPECT_UT, len(UT) >= EXPECT_UT, u'%d' % len(UT))
check(u'E2 shift 批 ≥ %d 条（防把位移门写丢）' % EXPECT_NEW,
      len(SHIFT) >= EXPECT_NEW, u'%d' % len(SHIFT))
check(u'E3 覆盖实例 ≥ %d' % EXPECT_COVERED, _cov_inst >= EXPECT_COVERED, u'%d' % _cov_inst)

print(u'')
print(u'== F. 自检 ==')


def _true_checks(path):
    out = []
    for node in ast.walk(ast.parse(io.open(path, encoding='utf-8', newline='').read())):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.id if isinstance(fn, ast.Name) else None
        if name not in ('check', 'ok'):
            continue
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) \
                and node.args[1].value is True:
            out.append((os.path.basename(path), node.lineno))
    return out


check(u'F1 没有 `check(x, True)` 恒真判据（AST 判，不扫注释）',
      not _true_checks(os.path.abspath(__file__)))
_rb = io.open(os.path.join(SCENES, '_routes.json'), encoding='utf-8', newline='').read()
check(u'F2 `_routes.json` 无 BOM / 无 U+FFFD', not _rb.startswith(u'\ufeff')
      and u'\ufffd' not in _rb)

print(u'')
print(u'---- 共 %d 条：PASS %d / FAIL %d' % (_n['p'] + _n['f'], _n['p'], _n['f']))
if _failed:
    print(u'失败项：')
    for d in _failed:
        print(u'  - %s' % d)
sys.exit(1 if _failed else 0)
