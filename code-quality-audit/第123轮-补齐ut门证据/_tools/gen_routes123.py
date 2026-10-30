# -*- coding: utf-8 -*-
u"""第123轮：把 ut 剩下的门（751 个实例）按**GML 位移机制**接上路由。

## 为什么第122轮只做了 548 / 1,299

第122轮只用「`conn115` 可信层里带反编译函数名的边」（110 条对象级）+「候选层里
`obj_doorA` 的 `dst == src+1`」（133 条字母级）。剩下的门里，`obj_doorB`(321) /
`obj_doorBmusicfade`(113) / `obj_doorAmusicfade`(101) / `obj_doorC`(60) / `obj_doorD`(61) /
`obj_doorCmusicfade` / `obj_doorDmusicfade` 在**两层证据里都没有边** —— 因为它们换房写的是

```gml
room_goto(room_previous(room));          // obj_doorB_Alarm_2
room_goto(room_next(room_next(room)));   // obj_doorC_Alarm_2
```

目标是**函数调用**而不是常量 ⇒ `conn_ut.csx` 只收常量目标 ⇒ 这些指令全落进
`n_nonconst_target: 30`，一条边都生不出来。

## 本轮的证据（GML 原文，UTMT 反编译，逐字）

| 对象 | `Alarm_2` 关键行 | 位移 |
|---|---|---|
| `obj_doorA` | `if (room != room_castle_prebarrier) room_goto(room_next(room));` + `else` 按 `global.flag[7]` 分叉 | **+1**，但 `castle_prebarrier` **排除** |
| `obj_doorAmusicfade` | 继承 `obj_doorA`（自己没有 `Alarm_2`，`PreCreate` 里 `event_inherited()`） | +1，同样排除 |
| `obj_doorB` | `room_goto(room_previous(room))` | **−1** |
| `obj_doorBmusicfade` | 继承 `obj_doorB` | −1 |
| `obj_doorC` / `obj_doorCmusicfade` | `room_goto(room_next(room_next(room)))` | **+2** |
| `obj_doorD` / `obj_doorDmusicfade` | `room_goto(room_previous(room_previous(room)))` | **−2** |
| `obj_papdoor` | `room_goto(room_next(room))` | +1 |

⇒ 与 Deltarune 的「A+1 / B−1 / C+2」**同一套约定**（同一作者的两部作品）。

`obj_elevatordoor` 是电梯 UI（`event_user(0)`），不是门位移；`obj_door_ruins13` 那批已经
在第122轮按 `if (room == X) room_goto(Y)` 逐条写死，本轮不碰。

## 三条硬纪律

1. **第122轮那 243 条一条不改** —— 直接读它的事实文件 `ut_doors122.json`，原样搬过来。
   本轮只**追加**新机制产生的条目；两边若在同一 (场景, 门) 上给出不同目标 ⇒ **冲突丢弃并记账**。
2. **条件分支的房间不套通用位移** —— `Alarm_2` 的 `if (...)` 条件里点名的房间一律排除
   （`obj_doorA` 的 `castle_prebarrier` 就是实例：`global.flag[7] == 1` 时去 `castle_trueexit`）。
3. **同场景同字母只能一条**（`verify_routes_order44` 的硬闸）。字母级的按 `(场景, 字母)` 去重，
   对象级的按 `(场景, 对象名)` 去重；目标不一致就整组丢弃，不挑一个凑数。

## 产物

· 就地重写 `ralsei_pet/assets/scenes/_routes.json` 的**整个 ut 段**（CRLF / 2 空格 / 无尾换行）
· `priority` 仍是独立段 4000+ **连续无洞**（在 122 的 4000~4242 之后顺延）
· 事实文件 `_evidence/ut_doors123.json`：机制表 + 每条路由 + 未采用账，供 `check123` 独立重推

用法::

    python gen_routes123.py --dry    # 只打印统计
    python gen_routes123.py          # 写盘
"""
import collections
import io
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
EVID = os.path.join(ROUND, '_evidence')
RAW = os.path.join(EVID, 'raw', 'ut')
RAW115 = os.path.join(os.path.dirname(ROUND), '第115轮-跨作品物件普查', '_evidence', 'raw', 'ut')
FACT122 = os.path.join(os.path.dirname(ROUND), '第122轮-ut门与房间连接', '_evidence',
                       'ut_doors122.json')

ZONE = os.path.join(SCENES, '_zone.ut.rooms.json')
ROUTES = os.path.join(SCENES, '_routes.json')
FACT = os.path.join(EVID, 'ut_doors123.json')

MODULES = os.path.join(REPO, 'ralsei_pet', 'modules')
sys.path.insert(0, MODULES)
import item_interact as II       # noqa: E402

#: ut 段 priority 起点（与第122轮同一个段；本轮顺延）
UT_PRIO_BASE = 4000

#: `room_goto(room_next(room))` 这类**以调用为参数**的写法 —— 逐个显式匹配，不做模糊推断
SHIFT_PATTERNS = [
    (re.compile(r'room_goto\s*\(\s*room_next\s*\(\s*room\s*\)\s*\)\s*;'),
     1, u'room_next(room)'),
    (re.compile(r'room_goto\s*\(\s*room_previous\s*\(\s*room\s*\)\s*\)\s*;'),
     -1, u'room_previous(room)'),
    (re.compile(r'room_goto\s*\(\s*room_next\s*\(\s*room_next\s*\(\s*room\s*\)\s*\)\s*\)\s*;'),
     2, u'room_next(room_next(room))'),
    (re.compile(r'room_goto\s*\(\s*room_previous\s*\(\s*room_previous\s*\(\s*room\s*\)\s*\)\s*\)\s*;'),
     -2, u'room_previous(room_previous(room))'),
    (re.compile(r'room_goto_next\s*\(\s*\)\s*;'), 1, u'room_goto_next()'),
    (re.compile(r'room_goto_previous\s*\(\s*\)\s*;'), -1, u'room_goto_previous()'),
]

RE_IFCOND = re.compile(r'if\s*\(([^)]*)\)')


def _json(p):
    with io.open(p, encoding='utf-8', newline='') as f:
        return json.load(f)


def _rows(p):
    for ln in io.open(p, encoding='utf-8', newline='').read().split('\n'):
        if ln:
            yield ln.split('\t')


def _write_like_original(path, data):
    u"""按仓库既有排版写回：`indent=2` + **CRLF** + **无尾换行**（与原件逐字节同构）。"""
    s = json.dumps(data, ensure_ascii=False, indent=2)
    with io.open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(s.replace('\n', '\r\n'))


def obj_of_code(code, names):
    u"""`gml_Object_obj_doorB_Alarm_2` → `obj_doorB`（最长前缀匹配）。"""
    if not code.startswith('gml_Object_'):
        return None
    tail = code[len('gml_Object_'):]
    best = None
    for nm in names:
        if (tail == nm or tail.startswith(nm + '_')) and (best is None or len(nm) > len(best)):
            best = nm
    return best


def event_of(code):
    u"""`gml_Object_obj_doorB_Alarm_2` → `Alarm_2`。"""
    i = code.rfind('_')
    j = code.rfind('_', 0, i)
    return code[j + 1:]


def shift_of(src):
    u"""取位移：返回 (off, 命中写法)；多种位移并存 ⇒ (None, 原因)。"""
    hits = []
    for rx, off, why in SHIFT_PATTERNS:
        if rx.search(src):
            hits.append((off, why))
    if not hits:
        return None, u'无位移写法'
    if len(set(h[0] for h in hits)) > 1:
        return None, u'同段多位移 %s' % sorted(set(h[0] for h in hits))
    return hits[0]


def cond_rooms_of(src):
    u"""`if (...)` 条件里点名的房间（`room ==` 和 `room !=` 都算 —— 后者是 doorA 的 prebarrier）。"""
    out = set()
    for m in RE_IFCOND.finditer(src):
        cond = m.group(1)
        if 'room' not in cond:
            continue
        out.update(re.findall(r'room_(\w+)', cond))
    return out


def resolve_mechanism(codes, objs):
    u"""返回 {对象: dict(off, why, src_obj, alarm_code, cond_rooms)} —— 沿父链解析 Alarm_2。"""
    names = set(o['name'] for o in objs)
    parent = {o['name']: (o.get('parent') or '') for o in objs}
    src_of, code_of = {}, {}
    for it in codes:
        o = obj_of_code(it['name'], names)
        if not o:
            continue
        ev = event_of(it['name'])
        src_of[(o, ev)] = it['src']
        code_of[(o, ev)] = it['name']

    mech = {}
    for o in sorted(names):
        cur, seen, depth, found = o, set(), 0, None
        while cur and cur not in seen and depth < 8:
            seen.add(cur)
            if (cur, 'Alarm_2') in src_of:
                found = cur
                break
            cur = parent.get(cur, '')
            depth += 1
        if found is None:
            mech[o] = {'off': None, 'why': u'父链上没有 Alarm_2', 'src_obj': None,
                       'alarm_code': None, 'cond_rooms': []}
            continue
        s = src_of[(found, 'Alarm_2')]
        off, why = shift_of(s)
        mech[o] = {'off': off, 'why': why, 'src_obj': found,
                   'alarm_code': code_of[(found, 'Alarm_2')],
                   'cond_rooms': sorted(cond_rooms_of(s))}
    return mech


def main(argv):
    dry = '--dry' in argv
    scenes = _json(ZONE)['scenes']
    rid2sid, name2sid = {}, {}
    for sid, sc in scenes.items():
        if not isinstance(sc, dict):
            continue
        rid = sc.get('original_room_id')
        if isinstance(rid, int):
            rid2sid[rid] = sid
        name2sid[sc.get('name')] = (sid, sc.get('original_room_id'))

    objs_all = set(r[1] for r in _rows(os.path.join(RAW115, 'objmap_ut.txt'))
                   if len(r) >= 5 and r[0] != 'GameObjects')
    insts = collections.Counter()
    cur = None
    for r in _rows(os.path.join(RAW115, 'inst_full.tsv')):
        if r[0] == 'R':
            cur = r[2]
        elif r[0] == 'I' and cur is not None:
            insts[(cur, r[1])] += 1

    codes = _json(os.path.join(RAW, 'door_codes123.json'))['codes']
    objs = _json(os.path.join(RAW, 'door_objects123.json'))['objects']
    mech = resolve_mechanism(codes, objs)
    door_kinds = set(o for o in objs_all if (II.classify(o) or {}).get('kind') == 'door')
    n_door_inst = sum(n for (rn, o), n in insts.items() if o in door_kinds)

    # ---- 第122轮那 243 条：原样搬（不重算、不改字段）----
    old = list(_json(FACT122).get('routes') or [])
    old_L = {}
    old_S = set()
    for r in old:
        o = r.get('when_src')
        if o:
            old_S.add((r['_original'].get('src_room_name'), o))
        else:
            old_L[(r['_original'].get('src_room_name'), r.get('when_door'))] = r

    stat = collections.Counter()
    drop = collections.defaultdict(list)
    cand, conflict = {}, []

    for (rn, o), n in sorted(insts.items()):
        if o not in door_kinds:
            continue
        # ★ 先扣掉第122轮**对象级**已经写过的（那批门根本没有位移写法，
        #   若不留这一步，它们会掉进 `no_mechanism` 被算成"未覆盖"= 重复记账）。
        if (rn, o) in old_S:
            stat['covered_122_obj'] += n
            continue
        m = mech.get(o) or {}
        off = m.get('off')
        if off is None:
            stat['no_mechanism'] += n
            drop['no_mechanism'].append((rn, o, m.get('why')))
            continue
        pair = name2sid.get(rn)
        if not pair or pair[1] is None:
            stat['src_unregistered'] += n
            drop['src_unregistered'].append((rn, o))
            continue
        src_sid, rid = pair
        if rn in (m.get('cond_rooms') or []):
            stat['cond_room'] += n
            drop['cond_room'].append((rn, o, off))
            continue
        dst_sid = rid2sid.get(rid + off)
        if not dst_sid:
            stat['dst_out_of_range'] += n
            drop['dst_out_of_range'].append((rn, o, rid + off))
            continue
        if dst_sid == src_sid:
            stat['self_loop'] += n
            drop['self_loop'].append((rn, o))
            continue

        letter = II.door_letter_of(o)
        key = ('L', src_sid, letter) if letter else ('S', src_sid, o)
        prev = cand.get(key, 'MISSING')
        if prev != 'MISSING':
            if prev is None or prev['to'] != dst_sid:
                conflict.append((key, None if prev is None else prev['to'], dst_sid))
                cand[key] = None
                stat['conflict'] += n
            continue
        cand[key] = {'to': dst_sid, 'key': key, 'obj': o, 'room': rn, 'insts': n,
                     'off': off, 'why': m['why'], 'alarm': m['alarm_code'],
                     'rid': rid, 'dst_rid': rid + off, 'letter': letter}
        stat['cand_%s' % ('letter' if letter else 'obj')] += n

    # ---- 与第122轮去重：它已写过的键本轮不重复；目标不一致 ⇒ 记账（不偷偷改它）----
    built, clash122 = [], []
    for key in sorted(cand, key=lambda k: (k[0], k[1], k[2])):
        rec = cand[key]
        if rec is None:
            continue
        if key[0] == 'L':
            k122 = (rec['room'], key[2])
            if k122 in old_L:
                if old_L[k122].get('to') != rec['to']:
                    clash122.append((k122, old_L[k122].get('to'), rec['to']))
                stat['skip_122_letter'] += rec['insts']
                continue
        else:
            if (rec['room'], rec['obj']) in old_S:
                stat['skip_122_obj'] += rec['insts']
                continue

        sid_src = name2sid[rec['room']][0]
        dn = scenes[rec['to']].get('name')
        built.append({
            'to': rec['to'], 'priority': 0,
            'reason': (u'原作 GML：%s 的 `Alarm_2` 调 `room_goto(%s)` ⇒ 房间 %s'
                       u'（下标 %d）%+d = %s（下标 %d）。'
                       % (rec['obj'], rec['why'], rec['room'], rec['rid'],
                          rec['off'], dn, rec['dst_rid'])),
            'when_scene': sid_src,
            'when_door': rec['letter'],
            'when_src': None if rec['letter'] else rec['obj'],
            '_original': {'kind': 'ut_door_shift', 'off': rec['off'], 'via': rec['obj'],
                          'how': rec['why'], 'alarm': rec['alarm'],
                          'src_room_name': rec['room'], 'dst_room_name': dn,
                          'src_room_id': rec['rid'], 'dst_room_id': rec['dst_rid']},
            'work': 'ut',
        })

    allr = old + built
    allr.sort(key=lambda x: (0 if x.get('when_src') else 1,
                             x['when_scene'], x.get('when_src') or '',
                             x.get('when_door') or ''))
    for i, r in enumerate(allr):
        r['priority'] = UT_PRIO_BASE + i

    # ---- 覆盖账（分母 = 门实例；分子按 (房间, 对象) 站位求实例数）----
    cov_pairs = set()
    for r in allr:
        o = r.get('when_src')
        if not o:
            # 字母级：只认本轮写到的那批对象（122 的 A 段就是 obj_doorA）
            o = r['_original'].get('via') or 'obj_doorA'
        cov_pairs.add((r['_original'].get('src_room_name'), o))
    n_cov = sum(insts.get(k, 0) for k in cov_pairs)

    print(u'== 机制表（沿父链解析 Alarm_2）==')
    for o in sorted(mech):
        m = mech[o]
        if m['off'] is None:
            continue
        print(u'  %-24s %+d  %-30s %s%s'
              % (o, m['off'], m['why'],
                 (u'继承自 ' + m['src_obj']) if m['src_obj'] != o else u'自有',
                 (u'  排除 %s' % m['cond_rooms']) if m['cond_rooms'] else u''))

    print(u'')
    print(u'== 计数 ==')
    for k in ('covered_122_obj', 'cand_letter', 'cand_obj', 'skip_122_letter', 'skip_122_obj',
              'conflict', 'no_mechanism', 'cond_room', 'dst_out_of_range', 'self_loop',
              'src_unregistered'):
        print(u'  %-20s %d' % (k, stat[k]))
    print(u'  对账：122 对象级 %d + 走位移机制 %d + 无机制 %d = %d（门实例总数 %d）'
          % (stat['covered_122_obj'], stat['cand_letter'] + stat['cand_obj'],
             stat['no_mechanism'],
             stat['covered_122_obj'] + stat['cand_letter'] + stat['cand_obj']
             + stat['no_mechanism'], n_door_inst))
    print(u'       其中「位移候选 %d」里有 %d 个实例落在 122 已写的字母 A 上'
          u'（去重后新增 %d）'
          % (stat['cand_letter'] + stat['cand_obj'], stat['skip_122_letter'],
             stat['cand_letter'] + stat['cand_obj'] - stat['skip_122_letter']))
    kinds = collections.Counter(r['_original']['kind'] for r in allr)
    print(u'  第122轮 %d 条 ＋ 本轮新增 %d 条 ⇒ ut 段共 %d 条 %s'
          % (len(old), len(built), len(allr), dict(kinds)))
    print(u'  覆盖站位 %d / 实例 %d / 门实例总数 %d = %.1f%%'
          % (len(cov_pairs), n_cov, n_door_inst, 100.0 * n_cov / max(1, n_door_inst)))

    print(u'')
    print(u'== 未采用账（逐类前 3）==')
    for k in ('cond_room', 'no_mechanism', 'dst_out_of_range', 'self_loop', 'src_unregistered'):
        v = drop.get(k) or []
        print(u'  %-20s %3d  %s' % (k, len(v), v[:3]))
    if conflict:
        print(u'  ⚠同键多目标（整键丢弃）%d 组：%s' % (len(conflict), conflict[:3]))
    if clash122:
        print(u'  ⚠与第122轮目标不一致 %d 组（保留 122 的写法，只记账）：%s'
              % (len(clash122), clash122[:3]))

    ev = {
        'schema_version': 1,
        'how': u'第123轮：ut 门的**位移机制**（Alarm_2 的 room_goto(room_prev/next(...))）'
               u'→ 目标房间。第122轮那 243 条原样保留。',
        'ut_prio_base': UT_PRIO_BASE,
        'n_routes_total': len(allr),
        'n_from_122': len(old),
        'n_new': len(built),
        'n_door_instances': n_door_inst,
        'n_covered_instances': n_cov,
        'n_covered_pairs': len(cov_pairs),
        'mechanism': {o: {'off': m['off'], 'how': m['why'], 'src_obj': m['src_obj'],
                          'alarm': m['alarm_code'], 'cond_rooms': m['cond_rooms']}
                      for o, m in sorted(mech.items())},
        'stat': dict(stat),
        'conflict': [list(map(str, c)) for c in conflict],
        'clash122': [list(map(str, c)) for c in clash122],
        'dropped': {k: [list(map(str, x)) for x in v] for k, v in drop.items()},
        'routes': built,
    }

    if dry:
        print(u'')
        print(u'[dry] 不写盘')
        return 0

    rj = _json(ROUTES)
    keep = [r for r in (rj.get('routes') or [])
            if not str((r or {}).get('when_scene') or '').startswith('ut.')]
    removed = len(rj.get('routes') or []) - len(keep)
    rj['routes'] = keep + allr

    meta = rj.setdefault('meta', {})
    note = meta.get('note') or u''
    tag = u'★ 第123轮：'
    if tag in note:
        note = note.split(tag)[0].rstrip(u'\n')
    meta['note'] = note + u'\n' + (
        u'★ 第123轮：ut 段由 %d 条增到 %d 条（+%d）。新增的都是**位移机制**门：'
        u'`obj_doorB`/`obj_doorBmusicfade` = `room_previous(room)`（−1）、'
        u'`obj_doorC`/`obj_doorCmusicfade` = `room_next(room_next(room))`（+2）、'
        u'`obj_doorD`/`obj_doorDmusicfade` = 双 `room_previous`（−2）、'
        u'`obj_doorAmusicfade`/`obj_papdoor` = +1 —— 全部来自 `Alarm_2` 的反编译原文，'
        u'与 Deltarune 的「A+1 / B−1 / C+2」同一套约定。'
        u'条件分支点名的房间（如 `obj_doorA` 的 `castle_prebarrier`，按 `global.flag[7]` 分叉）'
        u'**不套位移**、如实留空。生成器 '
        u'`code-quality-audit/第123轮-补齐ut门证据/_tools/gen_routes123.py`。'
        % (len(old), len(allr), len(built)))

    os.makedirs(EVID, exist_ok=True)
    _write_like_original(ROUTES, rj)
    _write_like_original(FACT, ev)
    print(u'')
    print(u'[ok] 删旧 ut 条目 %d，写入 %d 条（122 的 %d + 新增 %d）；总计 %d 条'
          % (removed, len(allr), len(old), len(built), len(rj['routes'])))
    print(u'[ok] 事实文件 %s' % os.path.relpath(FACT, REPO))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))
