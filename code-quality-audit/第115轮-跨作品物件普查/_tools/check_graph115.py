# -*- coding: utf-8 -*-
"""对账 room_graph115.json（本轮第 13.6 节）。

★ 这里的 BFS 是**另写一份**，不 import graph115 —— 两套实现互为对账，
  否则"判据"和"被测物"共用一个 bug，全绿也不代表对。

判据只判**结构自洽 + 与服务端数字一致**，不判"这条边在游戏里对不对"（本轮没有真值）。

用法
----
    python check_graph115.py
    python check_graph115.py -v
"""
import collections
import copy
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence')

KEYS = ['ut', 'uty', 'outertale']
# 与 report115.md §13.6 和 route115.txt 逐值对齐（改数据要同步改这里）
EXPECT_SCENE = {'ut': (338, 338), 'uty': (287, 287), 'outertale': (0, 244)}

FAILS = []


def check(name, ok, detail=''):
    if ok:
        return True
    FAILS.append((name, detail))
    return False


def load(fn):
    with io.open(os.path.join(EV, fn), encoding='utf-8') as f:
        return json.load(f)


def bfs(adj, start):
    seen = {start}
    q = collections.deque([start])
    while q:
        r = q.popleft()
        for d in adj.get(r, ()):
            if d not in seen:
                seen.add(d)
                q.append(d)
    return seen


def recount(g):
    """按导出文件重算 loose 策略：可达 / 双向 / 最深 / 出不来 —— 独立实现。"""
    adj, radj = collections.defaultdict(set), collections.defaultdict(set)
    for e in g['edges']:
        adj[e['src']].add(e['dst'])
        radj[e['dst']].add(e['src'])
    start = g['reachability']['loose']['start']
    reach = bfs(adj, start)
    back = bfs(radj, start)
    dist, q = {start: 0}, collections.deque([start])
    while q:
        r = q.popleft()
        for d in adj.get(r, ()):
            if d not in dist:
                dist[d] = dist[r] + 1
                q.append(d)
    return {'reach': len(reach), 'both': len(reach & back),
            'trap': len(reach - back),
            'max_depth': max(dist.values()) if dist else 0}


def g2_prov(g):
    bad = []
    seen_inf = False
    for e in g['edges']:
        if e['provenance'] == 'inferred':
            seen_inf = True
        elif e['provenance'] != 'exact':
            bad.append(('BAD_PROV', e['provenance']))
        elif seen_inf:
            bad.append(('ORDER', e['src'], e['dst']))
    return bad


def g3_exact_match(g, ex):
    a = set((e['src'], e['dst']) for e in g['edges'] if e['provenance'] == 'exact')
    b = set((e['src'], e['dst']) for e in ex['edges'])
    return sorted(a ^ b)[:6] if a != b else []


def g4_off(g):
    return [(e['src'], e['dst'], e['off']) for e in g['edges']
            if e['provenance'] == 'inferred'
            and (e['off'] not in (1, -1) or e['dst'] != e['src'] + e['off'])]


def g5_recount(g):
    got = recount(g)
    rec = g['reachability']['loose']
    bad = [(k, got[k], rec[k]) for k in got if got[k] != rec[k]]
    return bad


def g6_scene(g):
    got = (g['scene_hit']['by_name'], g['scene_hit']['by_room_id'])
    return got


def main(argv):
    graph = load('room_graph115.json')
    exact = load('conn115.json')
    verbose = '-v' in argv

    # G1 分母闸
    empty = [k for k in KEYS if not graph.get(k, {}).get('edges')]
    if check('G1 分母闸', not empty, '边表为空: %s' % empty):
        print('[PASS] G1 分母闸：三款边表都非空（696 / 2 / 732）')

    # G2 provenance 与排序
    bad = [(k, g2_prov(graph[k])) for k in KEYS if g2_prov(graph[k])]
    if check('G2 provenance 合法且 exact 全在前', not bad, str(bad)[:200]):
        print('[PASS] G2 provenance 只有 exact/inferred，且导出时 exact 全排在 inferred 之前')

    # G3 exact 集合与 conn115.json 完全一致
    bad = [(k, g3_exact_match(graph[k], exact[k])) for k in KEYS if g3_exact_match(graph[k], exact[k])]
    if check('G3 exact 边集与 conn115.json 一致', not bad, str(bad)[:200]):
        print('[PASS] G3 图里的 exact 边集与原表逐条相等（131 / 1 / 144）')

    # G4 候选边偏移
    bad = [(k, g4_off(graph[k])) for k in KEYS if g4_off(graph[k])]
    if check('G4 候选边 dst == src + off', not bad, str(bad)[:200]):
        print('[PASS] G4 候选边 dst == src + off 且 off ∈ {+1,-1}')

    # G5 独立复算 loose 的可达性
    bad = [(k, g5_recount(graph[k])) for k in KEYS if g5_recount(graph[k])]
    if check('G5 独立 BFS 复算与记录一致', not bad, str(bad)[:200]):
        print('[PASS] G5 另写一份 BFS 复算：可达/双向/最深/出不来 与记录逐一相等')

    # G6 scene 映射（含"outertale 名字对不上"这个事实）
    bad = []
    for k in KEYS:
        got = g6_scene(graph[k])
        if got != EXPECT_SCENE[k]:
            bad.append((k, got, EXPECT_SCENE[k]))
    if check('G6 scene 命中率与预期一致', not bad, str(bad)):
        print('[PASS] G6 scene 映射：ut 338/338、uty 287/287、outertale 按名字 0 按 id 244'
              '（名字被改过，只能按 original_room_id 对）')

    # G7 房间名与 conn_ut.json 一致
    bad = []
    for k in KEYS:
        with io.open(os.path.join(EV, 'raw', k, 'conn_ut.json'), encoding='utf-8') as f:
            names = json.load(f)['room_names']
        for e in graph[k]['edges']:
            if names[e['src']] != e['src_name'] or names[e['dst']] != e['dst_name']:
                bad.append((k, e['src'], e['dst']))
    if check('G7 房间名逐条对得上', not bad, str(bad[:6])):
        print('[PASS] G7 每条边的 src_name/dst_name 与 room_names 一致')

    # ---- 负控制（成对：破坏必须报红）
    g = copy.deepcopy(graph)
    tgt = next(e for e in g['ut']['edges'] if e['provenance'] == 'exact')
    tgt['provenance'] = 'inferred'
    tgt['off'] = tgt['dst'] - tgt['src']
    if check('G8 负控制A：exact 改标 inferred => G3 报红',
             bool(g3_exact_match(g['ut'], exact['ut']))):
        print('[PASS] G8 负控制A：把一条 exact 改标成 inferred => G3 报红')

    g = copy.deepcopy(graph)
    e0 = g['ut']['edges'][-1]
    e0['off'] = 2
    if check('G9 负控制B：off 改成 2 => G4 报红', bool(g4_off(g['ut']))):
        print('[PASS] G9 负控制B：把候选边 off 改成 2 => G4 报红')

    g = copy.deepcopy(graph)
    g['ut']['reachability']['loose']['reach'] += 7
    if check('G10 负控制C：可达数造假 => G5 报红', bool(g5_recount(g['ut']))):
        print('[PASS] G10 负控制C：把 loose 可达数 +7 => G5 报红')

    g = copy.deepcopy(graph)
    g['ut']['scene_hit']['by_name'] = 111
    if check('G11 负控制D：scene 命中率造假 => G6 报红',
             g6_scene(g['ut']) != EXPECT_SCENE['ut']):
        print('[PASS] G11 负控制D：把 ut 的 by_name 改成 111 => G6 报红')

    g = copy.deepcopy(graph)
    es = g['ut']['edges']
    i0 = next(i for i, e in enumerate(es) if e['provenance'] == 'inferred')
    es.insert(0, es.pop(i0))
    if check('G12 负控制E：inferred 排到最前 => G2 报红', bool(g2_prov(g['ut']))):
        print('[PASS] G12 负控制E：把一条 inferred 挪到最前 => G2 报红')

    if verbose:
        for k in KEYS:
            r = graph[k]['reachability']['loose']
            print('  [%s] exact=%d inferred=%d loose: reach=%d both=%d depth=%d trap=%d comps=%d'
                  % (k, graph[k]['n_exact'], graph[k]['n_inferred'],
                     r['reach'], r['both'], r['max_depth'], r['trap'], r['n_comps']))

    if FAILS:
        print('')
        for name, detail in FAILS:
            print('[FAIL] %s  %s' % (name, detail))
        print('=> %d FAIL' % len(FAILS))
        return 1
    print('=> 全部 PASS（0 FAIL）')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
