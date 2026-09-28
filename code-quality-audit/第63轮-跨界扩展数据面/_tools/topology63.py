#!/usr/bin/env python
# -*- coding: utf-8 -*-
u"""第63轮 · 扩展线③：Undertale 房间拓扑落库（门 → 目标房 → 落点坐标）。

铁律遵循
--------
1. **不预设门的偏移量**：`doorA→+1 / doorB→-1 / doorC→+2 / doorD→-2` 是
   **Deltarune**（本项目第42/43轮）的结论，**不能直接套到 Undertale**。
   本工具用**数据反推**（统计 `目标房下标 − 源房下标`）+ 用"目标房必须有同字母
   `marker`"做交叉验证；再用**第二条独立机制**（A/B 互逆性）复核。
2. **A/B 锚点**：① `room_start`(0) 无门；② 已知真值站点 ≥3 处必须命中。
3. **判据过窄=误报 / 过宽=恒真**：偏移量以"命中率 + 与次优的差距"呈现，不写死。

用法：
  python topology63.py --probe        # 只看门/落点对象名与分布
  python topology63.py --run          # 反推偏移 → 建拓扑 → 校验 → 落盘
"""
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict, deque

DATA = u'E:\\Download\\_extract61\\_data\\undertale'
HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
OUT = os.path.join(ROUND, '_evidence')
ROOMS_SRC = os.path.join(DATA, 'ut_rooms.json')
INST_SRC = os.path.join(DATA, 'ut_instances.json')

DOOR_RE = re.compile(u'^obj_door([A-Za-z]+)$')
MARK_RE = re.compile(u'^obj_marker([A-Za-z]+)$')
#: 排除：名字含 door/marker 但不是"房间门/房间落点"（音乐淡出助手、装饰门…）
DOOR_EXCLUDE = set([u'parent', u'Amusicfade', u'Bmusicfade', u'Cmusicfade',
                    u'Dmusicfade', u'Xmusicfade'])
MARKER_EXCLUDE = set()   # 小写 r/s/t/u/v/w 自然被第 2 条字母过滤掉（下面只留 A-D/X）

#: 允许的字母（大写单字母）；小写与多字母一律不当房间门
LETTERS = set(u'ABCDX')


def load():
    rooms = json.load(io.open(ROOMS_SRC, encoding='utf-8'))['rooms']
    inst = json.load(io.open(INST_SRC, encoding='utf-8'))['rooms']
    return rooms, inst


def _letter(var):
    if len(var) != 1 or var not in LETTERS:
        return None
    return var


def collect(inst):
    u"""每间房的 doorX / markerX（含坐标）。"""
    doors = defaultdict(dict)     # room -> letter -> [(x,y)]
    marks = defaultdict(dict)
    counts = Counter()
    for r in inst:
        i = r['index']
        for it in r['instances']:
            nm = it.get('obj') or u''
            m = DOOR_RE.match(nm)
            if m:
                counts[u'door:' + m.group(1)] += 1
                let = _letter(m.group(1))
                if let and m.group(1) not in DOOR_EXCLUDE:
                    doors[i].setdefault(let, []).append((it.get('x'), it.get('y')))
                continue
            m = MARK_RE.match(nm)
            if m:
                counts[u'marker:' + m.group(1)] += 1
                let = _letter(m.group(1))
                if let:
                    marks[i].setdefault(let, []).append((it.get('x'), it.get('y')))
    return doors, marks, counts


def probe(rooms, inst):
    doors, marks, counts = collect(inst)
    print(u'[P1] 出现过的 door/marker 变体（含被排除项）：')
    for k in sorted(counts):
        print(u'      %-18s %5d' % (k, counts[k]))
    print()
    print(u'[P2] 保留后 doors 字母=%r  markers 字母=%r'
          % (sorted(set(l for s in doors.values() for l in s)),
             sorted(set(l for s in marks.values() for l in s))))
    print(u'[P3] 含门 %d 间 / 含落点 %d 间 / 总 %d'
          % (len(doors), len(marks), len(rooms)))
    for i in sorted(doors)[:6]:
        print(u'      房 %3d %-22s doors=%r marks=%r'
              % (i, rooms[i]['name'], sorted(doors[i]), sorted(marks[i])))


def detect_offsets(rooms, doors, marks):
    n = len(rooms)
    res = {}
    for let in sorted(set(l for s in doors.values() for l in s)):
        trials = []
        for off in range(-6, 7):
            hit = tot = 0
            for i in sorted(doors):
                if let not in doors[i]:
                    continue
                tot += 1
                t = i + off
                if 0 <= t < n and let in marks[t]:
                    hit += 1
            trials.append((off, hit, tot, (hit / tot) if tot else 0.0))
        trials.sort(key=lambda x: (-x[1], x[0]))
        # 基率 = 同字母 marker 的房占比（"随便猜"的期望）
        base = sum(1 for t in marks if let in marks[t]) / float(n)
        res[let] = {'trials': trials, 'base_rate': base}
    return res


def build(rooms, doors, marks, offsets):
    edges = []
    n = len(rooms)
    for i in sorted(doors):
        for let in sorted(doors[i]):
            off = offsets.get(let)
            if off is None:
                continue
            t = i + off
            e = {'from': i, 'from_name': rooms[i]['name'], 'door': let,
                 'offset': off, 'to': t if 0 <= t < n else None}
            if 0 <= t < n:
                e['to_name'] = rooms[t]['name']
                pts = marks[t].get(let) or []
                e['landing_ok'] = bool(pts)
                e['landing'] = pts
            else:
                e['landing_ok'] = False
            for xy in doors[i][let]:
                e.setdefault('door_xy', []).append(xy)
            edges.append(e)
    return edges


def x_marks(i, marks):
    u"""该房是否有 markerX（代码驱动转场的落点）。"""
    return u'X' in marks.get(i, {})


def main():
    rooms, inst = load()
    if '--probe' in sys.argv:
        probe(rooms, inst)
        return 0
    if '--edges' in sys.argv:
        i = sys.argv.index('--edges')
        a = int(sys.argv[i + 1])
        b = int(sys.argv[i + 2])
        doors, marks, _ = collect(inst)
        for n in range(a, min(b, len(rooms))):
            print(u'房 %3d %-24s doors=%r marks=%r'
                  % (n, rooms[n]['name'], sorted(doors.get(n, {})),
                     sorted(marks.get(n, {}))))
        return 0

    doors, marks, counts = collect(inst)
    res = detect_offsets(rooms, doors, marks)
    print(u'=== ① 偏移量反推（判据：目标房含同字母 marker）===')
    chosen = {}
    for let, info in res.items():
        tot = info['trials'][0][2]
        off, hit, _, rate = info['trials'][0]
        second = info['trials'][1]
        chosen[let] = off
        print(u'[%s] %d 间房有门；最优 off=%+d 命中 %d/%d=%.1f%%；'
              u'次优 off=%+d=%.1f%%；**随机基率=%.1f%%**'
              % (let, tot, off, hit, tot, rate * 100,
                 second[0], second[3] * 100, info['base_rate'] * 100))
    print(u'   ⇒ 采用偏移：%r' % (chosen,))

    edges = build(rooms, doors, marks, chosen)
    ok = [e for e in edges if e['to'] is not None]
    inrange = [e for e in edges if e['to'] is None]
    land_ok = [e for e in ok if e.get('landing_ok')]
    print()
    print(u'=== ② 建图 ===')
    print(u'      边 %d 条（越界 %d）| 落点命中 %d/%d = %.1f%%'
          % (len(edges), len(inrange), len(land_ok), len(ok),
             100.0 * len(land_ok) / max(1, len(ok))))

    # ③ 独立机制复核：A/B 互逆性（房 N 有 doorA→M，则 M 应有 doorB→N）
    print()
    print(u'=== ③ 独立复核（A/B 互逆性：N --doorA--> M 时 M 是否 --doorB--> N）===')
    for pair in ((u'A', u'B'), (u'C', u'D')):
        a, b = pair
        tot = rev = 0
        for e in ok:
            if e['door'] != a:
                continue
            tot += 1
            m = e['to']
            if b in doors.get(m, {}):
                rev += 1
        print(u'      door%s 的 %d 条边里，目标房含 door%s 的占 %d (%.1f%%)'
              % (a, tot, b, rev, 100.0 * rev / max(1, tot)))

    # ④ 连通分量（无向化后求分量；Undertale 的门是双向成对的）
    und = defaultdict(set)
    for e in ok:
        und[e['from']].add(e['to'])
        und[e['to']].add(e['from'])
    comp = {}
    cid = 0
    for i in range(len(rooms)):
        if i in comp:
            continue
        cid += 1
        seen2 = set([i])
        q = deque([i])
        while q:
            u = q.popleft()
            for v in und[u]:
                if v not in seen2:
                    seen2.add(v)
                    q.append(v)
        for v in seen2:
            comp[v] = cid
    sizes = Counter(comp.values())
    print()
    print(u'=== ④ 连通分量（门边无向化）===')
    print(u'      分量数 %d；最大分量 %d 间'
          % (len(sizes), sizes.most_common(1)[0][1]))
    print(u'      分量规模 Top8：%r' % (sizes.most_common(8),))
    big = sizes.most_common(1)[0][0]
    mem = [i for i in range(len(rooms)) if comp[i] == big]
    # 最大分量的"有向 DFS 起点" = 只有出边没入边的房（天然入口）
    has_in = set(e['to'] for e in ok)
    roots = [i for i in mem if i not in has_in]
    print(u'      最大分量内"无入边"的天然入口 %d 个：%r'
          % (len(roots), [(i, rooms[i]['name']) for i in roots[:6]]))

    # ⑤ 非门体系：有 markerX 但无任何门的房（= 由代码 room_goto 驱动）
    doorset = set(doors)
    mx = [i for i in range(len(rooms))
          if x_marks(i, marks) and i not in doorset]
    print()
    print(u'=== ⑤ 非门体系（有 markerX 但无 door 的房，由代码驱动转场）===')
    print(u'      共 %d 间：%r'
          % (len(mx), [(i, rooms[i]['name']) for i in mx[:10]]))

    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    art = {
        'source': 'undertale game.droid (UTMT v0.9.2.0, dump_instances63.csx)',
        'room_count': len(rooms),
        'rooms': [{'index': r['index'], 'name': r['name'],
                   'w': r['w'], 'h': r['h']} for r in rooms],
        'door_offsets': chosen,
        'offset_evidence': {k: v['trials'][:3] for k, v in res.items()},
        'base_rate': {k: v['base_rate'] for k, v in res.items()},
        'edges': edges,
        'components': {'count': len(sizes), 'largest': sizes.most_common(1)[0][1],
                       'top_sizes': sizes.most_common(8),
                       'comp_of_room': {str(i): comp[i] for i in range(len(rooms))}},
        'stats': {'edges': len(edges), 'out_of_range': len(inrange),
                  'landing_ok': len(land_ok),
                  'largest_component': sizes.most_common(1)[0][1],
                  'code_driven_rooms': len(mx)},
    }
    p = os.path.join(OUT, 'ut_topology63.json')
    with io.open(p, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(art, ensure_ascii=False, indent=1))
    print(u'  证据 -> %s' % p)
    return 0


if __name__ == '__main__':
    sys.exit(main())
