# -*- coding: utf-8 -*-
u"""第65轮 · 把「Undertale 原版」与「黄魂(Undertale Yellow)」合成一张大图。

输入：ut_topology65.json / uty_topology65.json（+ 可选 ry_topology65.json 作第三来源对账）
输出：bigmap65.json

★ 纪律（本轮铁律）
  1. **跨作品连接点不臆造**：两侧房名命名空间完全不同
     （Undertale = `room_*` / 黄魂 = `rm_*`），是否连通必须**实证**，不能按"都是元游戏"硬连。
  2. **分量数守恒判据**：`union.components == ut.components + uty.components`
     —— 只要有一条跨作品边被误引入，等式立刻破。这是**会说话的判据**，不是恒真判据。
  3. **负控制**：往图里注入一条伪造跨作品边 ⇒ 分量数必须**恰好 -1**。
     若不变 ⇒ 分量算法没在图上跑（判据空转）。
  4. 边的 `sources` 逐条保留（哪份拓扑、哪条证据），不做无来源的"融合边"。
"""
from __future__ import print_function
import io, json, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
EV = os.path.join(HERE, '..', '_evidence')


def load(fn):
    p = os.path.join(EV, fn)
    return json.load(io.open(p, encoding='utf-8'))


# ---------------------------------------------------------------- 分量
def components(node_ids, edges):
    u"""返回 {node_id: comp_id}（1-based）与 sizes。edges 只认两端都存在的边。"""
    adj = collections.defaultdict(set)
    idset = set(node_ids)
    dropped = 0
    for e in edges:
        a, b = e['from'], e['to']
        if a is None or b is None:
            continue
        if a not in idset or b not in idset:
            dropped += 1
            continue
        adj[a].add(b)
        adj[b].add(a)
    comp, cid = {}, 0
    for n in node_ids:
        if n in comp:
            continue
        cid += 1
        seen, stack = {n}, [n]
        while stack:
            u = stack.pop()
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        for v in seen:
            comp[v] = cid
    sizes = collections.Counter(comp.values())
    return comp, sizes, dropped


# ---------------------------------------------------------------- 合并
def build(works):
    u"""works = [(work_key, title, topo_dict), ...] ⇒ bigmap dict。"""
    nodes, edges = [], []
    per_work = {}
    for key, title, t in works:
        nm2 = {}
        for r in t['rooms']:
            nid = '%s:%d' % (key, r['index'])
            nm2[r['index']] = r['name']
            nodes.append({'id': nid, 'work': key, 'index': r['index'],
                          'name': r['name'], 'w': r['w'], 'h': r['h']})
        ne, ncross = 0, 0
        for e in t['edges']:
            f, to = e['from'], e['to']
            fe = to is not None
            if not fe:
                continue  # 未解析边不进大图（保留在原拓扑里，见 unresolved 统计）
            edges.append({
                'from': '%s:%d' % (key, f), 'to': '%s:%d' % (key, to),
                'from_name': e.get('from_name'), 'to_name': e.get('to_name'),
                'via': e.get('via'), 'rule': e.get('rule'),
                'evidence_kind': e.get('evidence_kind'),
                'evidence_file': e.get('evidence_file'),
                'landing': e.get('landing'),
                'source_work': key,
            })
            ne += 1
        per_work[key] = {'title': title, 'room_count': len(t['rooms']),
                         'resolved_edges': ne,
                         'all_edges': len(t['edges']),
                         'unresolved': t['stats']['unresolved'],
                         'struct_rules': t.get('struct_rules', {}),
                         'source': t.get('source')}

    node_ids = [n['id'] for n in nodes]
    comp, sizes, dropped = components(node_ids, edges)

    # 命名空间交叠实证
    name_sets = {}
    for key, title, t in works:
        name_sets[key] = set(r['name'] for r in t['rooms'])
    keys = sorted(name_sets)
    pair_inter = {}
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = keys[i], keys[j]
            inter = sorted(name_sets[a] & name_sets[b])
            pair_inter['%s∩%s' % (a, b)] = {'count': len(inter), 'sample': inter[:10]}

    cross_edges = [e for e in edges if e['from'].split(':')[0] != e['to'].split(':')[0]]

    # 每个作品自己的分量（用于守恒判据）
    per_comp = {}
    for key, title, t in works:
        ids = ['%s:%d' % (key, r['index']) for r in t['rooms']]
        es = [e for e in edges if e['source_work'] == key]
        _, sz, _ = components(ids, es)
        per_comp[key] = {'components': len(sz), 'largest': sz.most_common(1)[0][1] if sz else 0,
                         'top': [list(x) for x in sz.most_common(8)]}

    exp_comp = sum(v['components'] for v in per_comp.values())
    conserve = (len(sizes) == exp_comp and not cross_edges)

    bigmap = {
        'round': 65,
        'generated_by': '_tools/merge_bigmap65.py',
        'note': u'两作品合成一张大图。跨作品连接点**无实证**（房名命名空间不相交、'
                u'跨作品边 = 0）⇒ 保留为互不相连的分量，见 reconcile / pending。',
        'works': per_work,
        'node_count': len(nodes),
        'edge_count': len(edges),
        'namespace_check': {
            'per_work_room_names': dict((k, len(v)) for k, v in name_sets.items()),
            'pairwise_intersection': pair_inter,
            'cross_work_edges': len(cross_edges),
            'cross_work_edge_sample': cross_edges[:5],
        },
        'components': {
            'count': len(sizes),
            'largest': sizes.most_common(1)[0][1] if sizes else 0,
            'top_sizes': [list(x) for x in sizes.most_common(12)],
            'per_work': per_comp,
            'conservation': {'expected': exp_comp, 'actual': len(sizes),
                             'equal': len(sizes) == exp_comp},
            'all_cross_work': len(cross_edges) == 0,
            'dangling_edges_dropped': dropped,
            'conserve_ok': conserve,
        },
        'nodes': nodes,
        'edges': edges,
    }
    return bigmap


# ---------------------------------------------------------------- 负控制
def selftest(bigmap):
    """负控制：注入一条伪造跨作品边 ⇒ 分量数必须恰好 -1。"""
    out = []
    ids = [n['id'] for n in bigmap['nodes']]
    base = bigmap['components']['count']
    # A: 基线
    _, s0, _ = components(ids, bigmap['edges'])
    out.append(('A 基线分量数', len(s0), base))
    # B: 注入伪造跨作品边（取两作品各自最大分量里的一对节点）
    pick = {}
    comp, sizes, _ = components(ids, bigmap['edges'])
    big = sizes.most_common(1)[0][0]
    for n in ids:
        if comp[n] == big and n.split(':')[0] not in pick:
            pick[n.split(':')[0]] = n
    # 黄魂最大分量与 Undertale 最大分量各自一个节点
    per = bigmap['components']['per_work']
    cand = {}
    for k in per:
        # 找该作品最大分量的节点
        c, sz, _ = components([n['id'] for n in bigmap['nodes'] if n['work'] == k],
                              [e for e in bigmap['edges'] if e['source_work'] == k])
        bid = sz.most_common(1)[0][0]
        cand[k] = next(n['id'] for n in bigmap['nodes']
                       if n['work'] == k and c[n['id']] == bid)
    ks = sorted(cand)
    fake = dict(bigmap['edges'][0])
    fake.update({'from': cand[ks[0]], 'to': cand[ks[1]],
                 'from_name': 'FAKE', 'to_name': 'FAKE', 'rule': 'selftest'})
    _, s1, _ = components(ids, bigmap['edges'] + [fake])
    out.append(('B 注入伪造跨作品边后', len(s1), base - 1))
    # C: 反向控制 —— 注入一条同作品自环（不应改变分量数）
    same = dict(bigmap['edges'][0])
    same.update({'from': cand[ks[0]], 'to': cand[ks[0]], 'rule': 'selftest-selfloop'})
    _, s2, _ = components(ids, bigmap['edges'] + [same])
    out.append(('C 同作品自环（不该变）', len(s2), base))
    ok = (out[0][1] == out[0][2]) and (out[1][1] == out[1][2]) and (out[2][1] == out[2][2])
    return ok, out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ut = load('ut_topology65.json')
    uty = load('uty_topology65.json')
    works = [('ut', ut['work'], ut), ('uty', uty['work'], uty)]
    big = build(works)

    # --- 第三来源对账：红与黄（可选） ---
    ry_path = os.path.join(EV, 'ry_topology65.json')
    rec = {'present': os.path.isfile(ry_path)}
    if rec['present']:
        ry = load('ry_topology65.json')
        unames = [r['name'] for r in ut['rooms']]
        rnames = [r['name'] for r in ry['rooms']]
        same = sum(1 for a, b in zip(rnames, unames) if a == b)
        extra = rnames[len(unames):]
        # 增量房（index >= 338）相关的边
        ne = len(unames)
        inc_edges = [e for e in ry['edges'] if (e['from'] or 0) >= ne or (e['to'] or 0) >= ne]
        # 基线区（0..337）上 ry 与 ut 的边差异
        def eset(t, lo, hi):
            return set((e['from'], e['to'], e['via'])
                       for e in t['edges'] if lo <= (e['from'] or -1) <= hi and e['to'] is not None)
        a = eset(ut, 0, ne - 1)
        b = eset(ry, 0, ne - 1)
        rec.update({
            'work': ry['work'],
            'room_count': ry['room_count'],
            'same_order_vs_ut': same,
            'same_order_total': len(unames),
            'extra_count': len(extra),
            'extra_names': extra,
            'extra_edges': len(inc_edges),
            'base_only_in_ut': len(a - b),
            'base_only_in_ry': len(b - a),
            'base_shared': len(a & b),
            'sample_only_in_ry': [list(x) for x in sorted(b - a)[:8]],
            'extra_edges_detail': [
                {'from': e['from'], 'from_name': e['from_name'], 'to': e['to'],
                 'to_name': e['to_name'], 'via': e['via'],
                 'evidence_kind': e['evidence_kind']}
                for e in sorted(inc_edges, key=lambda x: (x['from'] or 0, x['to'] or 0))
            ],
            'verdict': u'红与黄 = 原版 Undertale 同序 %d 间 + 追加 %d 间（同一命名空间、索引对齐）'
                       % (same, len(extra)),
        })

        # --- 独立 overlay：mod 增量房 + 「基础房 → 增量房」的实证连接点 ---
        #   注意：这类边的两端**同一命名空间**（都是原版索引），证据来自 GML 的 cond/uncond 分支，
        #   与「黄魂↔Undertale」的跨作品无实证边是两回事，不可混为一谈。
        ex_rooms = [r for r in ry['rooms'] if r['index'] >= ne]
        ex_idx = set(r['index'] for r in ex_rooms)
        attach = []
        for e in ry['edges']:
            f, t = e['from'], e['to']
            if t is None or f is None:
                continue
            if f < ne <= t:
                attach.append({'base_index': f, 'base_name': e['from_name'],
                               'via': e['via'], 'to_index': t, 'to_name': e['to_name'],
                               'evidence_kind': e['evidence_kind'],
                               'evidence_file': e.get('evidence_file')})
        ex_edges = [e for e in ry['edges']
                    if e['to'] is not None and (e['from'] >= ne or e['to'] >= ne)]
        overlay = {
            'round': 65,
            'generated_by': '_tools/merge_bigmap65.py',
            'purpose': u'《红与黄》= Undertale + mod，其 20 间增量房如何挂到原版 338 间上。'
                       u'**待裁定**：是否把 mod 房并入正典图（第65轮只出数据，不接线）。',
            'base_room_count': ne,
            'extra_rooms': [{'index': r['index'], 'name': r['name'], 'w': r['w'], 'h': r['h']}
                            for r in ex_rooms],
            'attach_points': attach,
            'extra_edges': [{'from': e['from'], 'to': e['to'], 'from_name': e['from_name'],
                             'to_name': e['to_name'], 'via': e['via'],
                             'evidence_kind': e['evidence_kind']} for e in ex_edges],
            'stats': {'extra_rooms': len(ex_rooms), 'attach_points': len(attach),
                      'extra_edges': len(ex_edges)},
        }
        io.open(os.path.join(EV, 'bigmap65_ry_overlay.json'), 'w', encoding='utf-8').write(
            json.dumps(overlay, ensure_ascii=False, indent=1))
        rec['overlay_file'] = 'bigmap65_ry_overlay.json'
        rec['attach_points'] = len(attach)
    big['reconcile_third_source'] = rec

    outp = os.path.join(EV, 'bigmap65.json')
    io.open(outp, 'w', encoding='utf-8').write(
        json.dumps(big, ensure_ascii=False, indent=1, sort_keys=False))

    st = big['components']
    print('===== bigmap65 =====')
    print('nodes=%d  edges=%d' % (big['node_count'], big['edge_count']))
    for k, v in big['works'].items():
        print('  [%s] %s : rooms=%d resolved_edges=%d unresolved=%d'
              % (k, v['title'], v['room_count'], v['resolved_edges'], v['unresolved']))
    print('namespace_check:')
    for k, v in big['namespace_check']['pairwise_intersection'].items():
        print('   %s -> %d' % (k, v['count']))
    print('   cross_work_edges = %d' % big['namespace_check']['cross_work_edges'])
    print('components: count=%d largest=%d' % (st['count'], st['largest']))
    for k, v in st['per_work'].items():
        print('   [%s] components=%d largest=%d' % (k, v['components'], v['largest']))
    print('   conservation: expected=%d actual=%d equal=%s'
          % (st['conservation']['expected'], st['conservation']['actual'],
             st['conservation']['equal']))
    print('   conserve_ok = %s' % st['conserve_ok'])
    ok, rows = selftest(big)
    print('selftest (正/负控制):')
    for name, got, want in rows:
        print('   %-28s got=%s want=%s %s' % (name, got, want, 'PASS' if got == want else 'FAIL'))
    print('   => %s' % ('PASS' if ok else 'FAIL'))
    if rec['present']:
        print('reconcile 红与黄: %s' % rec['verdict'])
        print('   extra(%d)=%s' % (rec['extra_count'], rec['extra_names']))
        print('   base shared=%d  only_in_ut=%d  only_in_ry=%d'
              % (rec['base_shared'], rec['base_only_in_ut'], rec['base_only_in_ry']))
        print('   增量房连接点 attach_points=%d（基础房 → 增量房，GML 实证）' % rec.get('attach_points', 0))
        print('   -> %s' % rec.get('overlay_file'))
    print('   -> %s' % outp)
    return 0 if ok and st['conserve_ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
