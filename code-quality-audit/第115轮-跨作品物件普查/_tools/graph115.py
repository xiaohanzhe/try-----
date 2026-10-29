# -*- coding: utf-8 -*-
"""把三款连通数据做成可寻路的图，并量化「三种策略下到底能走多远」。

★ 为什么要算 BFS 而不是只报覆盖率：
  覆盖率说的是「有多少间房有出边」，可玩家关心的是「从入口走进去能走多远、会不会走进死胡同」。
  这两件事在链式地图上差别巨大：46% 的出边覆盖也可能一路走到底，85% 也可能一步就卡住。

三种策略（策略名会在导出文件里逐条落 provenance）：
  exact       只用 GML 写死的边
  safe        exact + 同区域的候选边（跨区域的默认关）
  loose       exact + 全部候选边

产物
----
_evidence/room_graph115.json   三款分层图（边带 scene_id / provenance / confidence）
_evidence/route115.txt         三种策略的 BFS 实测量

用法
----
    python graph115.py
"""
import collections
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence')
SCENES = os.path.abspath(os.path.join(ROUND, '..', '..', 'ralsei_pet', 'assets', 'scenes'))

KEYS = ['ut', 'uty', 'outertale']
# 入口：桌面上的门通向的那一间。★ 注意 `room_start` 是标题/菜单房、里面没有门，
#   拿它当起点会得到「一间都走不出去」的假结论 —— 真正的落地房是 room_area1（坠落处）。
ENTRY = {'ut': 'room_area1', 'uty': 'rm_ruins00', 'outertale': 'room_area1'}


def load_zone(key):
    """汇总该作品所有 zone 文件：返回 (area_id, {下标: scene_id}, {房名: scene_id})

    ★ 两条实测教训（别再退回旧写法）：
      1) outertale **不是**一个 `_zone.outertale.rooms.json`，而是按区域拆成 7 个文件。
      2) outertale 的房间名被改过（`s_start` 而不是 `room_start`），**按名字对不上**（实测 0/358）。
         但每个场景都带 `original_room_id` = 原作 Data.Rooms 的下标 —— 那才是可靠的主键。
    """
    import glob
    area, by_idx, by_name = None, {}, {}
    for p in sorted(glob.glob(os.path.join(SCENES, '_zone.%s.*.json' % key))):
        try:
            d = json.load(io.open(p, encoding='utf-8'))
        except Exception:
            continue
        if d.get('chapter_id') != key:
            continue
        if area is None:
            area = d.get('area_id')
        for sid, s in (d.get('scenes') or {}).items():
            ri = s.get('original_room_id')
            if isinstance(ri, int) and ri not in by_idx:
                by_idx[ri] = sid
            nm = s.get('name')
            if nm and nm not in by_name:
                by_name[nm] = sid
    return area, by_idx, by_name


def build(key):
    ex = json.load(io.open(os.path.join(EV, 'conn115.json'), encoding='utf-8'))[key]
    inf = json.load(io.open(os.path.join(EV, 'conn_inferred115.json'), encoding='utf-8'))[key]
    raw = json.load(io.open(os.path.join(EV, 'raw', key, 'conn_ut.json'), encoding='utf-8'))
    names = list(raw['room_names'])
    area, by_idx, by_name = load_zone(key)
    return ex, inf, area, by_idx, by_name, names


def bfs(adj, start, n):
    seen, q = set(), collections.deque([start])
    seen.add(start)
    while q:
        r = q.popleft()
        for d in adj.get(r, ()):
            if d not in seen:
                seen.add(d)
                q.append(d)
    return seen


def depth(adj, start):
    """最短路深度（层数），顺便给出最远那间"""
    dist = {start: 0}
    q = collections.deque([start])
    while q:
        r = q.popleft()
        for d in adj.get(r, ()):
            if d not in dist:
                dist[d] = dist[r] + 1
                q.append(d)
    far = max(dist, key=lambda k: dist[k]) if dist else start
    return dist[far], far, len(dist)


def analyse(key, ex, inf, names, policy):
    adj = collections.defaultdict(set)
    radj = collections.defaultdict(set)
    und = collections.defaultdict(set)
    used = []
    for e in ex['edges']:
        adj[e['src']].add(e['dst'])
        radj[e['dst']].add(e['src'])
        und[e['src']].add(e['dst'])
        und[e['dst']].add(e['src'])
        used.append((e['src'], e['dst'], 'exact'))
    if policy != 'exact':
        exact_src = set(adj)
        for e in inf['edges']:
            if policy == 'safe' and not e['same_area']:
                continue
            # room_first：这间房已经有精确门了，就别再拿候选边往里塞
            if policy == 'room_first' and e['src'] in exact_src:
                continue
            if e['dst'] in adj.get(e['src'], ()):
                continue
            adj[e['src']].add(e['dst'])
            radj[e['dst']].add(e['src'])
            und[e['src']].add(e['dst'])
            und[e['dst']].add(e['src'])
            used.append((e['src'], e['dst'], 'inferred'))
    n = ex['n_rooms']

    # 入口：找不到就显式标 fallback（取出边最多的房），不静默换起点
    want = ENTRY.get(key)
    start, fallback = None, False
    if want in names:
        start = names.index(want)
    else:
        cand = sorted(adj, key=lambda r: -len(adj[r]))
        if cand:
            start, fallback = cand[0], True
    if start is None:
        return None

    reach = bfs(adj, start, n)
    back = bfs(radj, start, n)
    d, far, _n = depth(adj, start)
    trap = sorted(reach - back)

    # 弱连通分量（只看有边的房）：回答「这张图整体是几块」
    comps, seen = [], set()
    for r in list(und):
        if r in seen:
            continue
        comp, q = set(), collections.deque([r])
        seen.add(r)
        while q:
            x = q.popleft()
            comp.add(x)
            for y in und.get(x, ()):
                if y not in seen:
                    seen.add(y)
                    q.append(y)
        comps.append(len(comp))
    comps.sort(reverse=True)

    return {
        'policy': policy,
        'start': start,
        'start_name': names[start],
        'start_fallback': fallback,
        'edges': len(used),
        'reach': len(reach),
        'back': len(back),
        'both': len(reach & back),
        'trap': len(trap),
        'trap_names': [names[i] for i in trap[:6]],
        'max_depth': d,
        'far_name': names[far],
        'rooms': n,
        'comps': comps[:3],
        'n_comps': len(comps),
    }


def export(key, ex, inf, names, area, by_idx, by_name):
    """导出边表：每条边带 scene_id 与 provenance，产品侧按 provenance 过滤即可。"""
    def sid(i):
        return by_idx.get(i) or by_name.get(names[i])
    edges = []
    seen = set()
    for e in ex['edges']:
        seen.add((e['src'], e['dst']))
        edges.append({'src': e['src'], 'dst': e['dst'],
                      'src_scene': sid(e['src']), 'dst_scene': sid(e['dst']),
                      'src_name': e['src_name'], 'dst_name': e['dst_name'],
                      'provenance': 'exact', 'confidence': 'high',
                      'via': e['code'], 'off': None})
    for e in inf['edges']:
        if (e['src'], e['dst']) in seen:
            continue
        edges.append({'src': e['src'], 'dst': e['dst'],
                      'src_scene': sid(e['src']), 'dst_scene': sid(e['dst']),
                      'src_name': e['src_name'], 'dst_name': e['dst_name'],
                      'provenance': 'inferred',
                      'confidence': 'medium' if e['same_area'] else 'low',
                      'via': e['via'], 'off': e['off']})
    edges.sort(key=lambda x: (x['provenance'] != 'exact', x['src'], x['dst']))
    return {
        'chapter_id': key,
        'area_id': area,
        'n_rooms': ex['n_rooms'],
        'entry_room': ENTRY.get(key),
        'n_exact': sum(1 for e in edges if e['provenance'] == 'exact'),
        'n_inferred': sum(1 for e in edges if e['provenance'] == 'inferred'),
        'rule': 'exact = GML 写死 `if (room==N) room_goto(M)`；'
                'inferred = 对象事件 room_goto_next/previous（房间序 ±1），未经验证',
        'policy': {'exact': '只走 exact',
                   'safe': 'exact + inferred 中 confidence=medium（同区域）',
                   'loose': 'exact + 全部 inferred，含 confidence=low（跨区域，最可疑）'},
        'edges': edges,
    }


def main():
    out_json = {}
    lines = ['三款连通图的可达性实测（BFS，起点=桌面门通向的那间落地房）', '']
    for key in KEYS:
        ex, inf, area, by_idx, by_name, names = build(key)
        if not ex['edges']:
            lines.append('[%s] EMPTY：没有可信边' % key)
            continue
        out_json[key] = export(key, ex, inf, names, area, by_idx, by_name)
        hit_idx = sum(1 for i in range(len(names)) if i in by_idx)
        hit_name = sum(1 for nm in names if nm and nm in by_name)
        lines.append('=' * 70)
        lines.append('[%s] 房间 %d / 入口 %s / 对上产品 scene：按 original_room_id %d/%d，'
                     '按名字 %d/%d'
                     % (key, ex['n_rooms'], ENTRY.get(key),
                        hit_idx, len(names), hit_name, len(names)))
        lines.append('  %-10s %-7s %-7s %-7s %-7s %-7s %-6s %s'
                     % ('策略', '边数', '可达', '可回', '双向', '最深层', '连通块', '走进去出不来'))
        reach = {}
        for policy in ('exact', 'room_first', 'safe', 'loose'):
            r = analyse(key, ex, inf, names, policy)
            if not r:
                lines.append('  无可判入口 => EMPTY')
                break
            reach[policy] = {k2: v for k2, v in r.items() if k2 != 'trap_names'}
            reach[policy]['trap_names'] = r['trap_names']
            flag = '（fallback）' if r['start_fallback'] else ''
            lines.append('  %-10s %-7d %-7d %-7d %-7d %-7d %-6s %d%s'
                         % (policy, r['edges'], r['reach'], r['back'], r['both'],
                            r['max_depth'], '%d/%s' % (r['n_comps'], r['comps'][0]),
                            r['trap'], flag))
            lines.append('          起点=%s 最远=%s  出不来样例: %s'
                         % (r['start_name'], r['far_name'],
                            '、'.join(r['trap_names']) or '无'))
        out_json[key]['reachability'] = reach
        out_json[key]['scene_hit'] = {'by_room_id': hit_idx, 'by_name': hit_name,
                                      'n_rooms': len(names)}
    txt = '\n'.join(lines) + '\n'
    with io.open(os.path.join(EV, 'route115.txt'), 'w', encoding='utf-8', newline='') as f:
        f.write(txt)
    with io.open(os.path.join(EV, 'room_graph115.json'), 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(out_json, ensure_ascii=False, indent=1, sort_keys=True))
        f.write('\n')
    sys.stdout.write(txt)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
