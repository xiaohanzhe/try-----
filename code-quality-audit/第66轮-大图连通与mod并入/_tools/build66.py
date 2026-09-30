# -*- coding: utf-8 -*-
u"""第66轮 · 大图连通 + mod 并入正典图。

在 `topo_build65.py` 的边模型上补两种载体，并做三件事：
  ① **补载体 4** `cc-runtime`：事件里 `instance_create(.., obj_doorway)` + `with(..){ nextroom = N; }`
     —— 依据：UTY 的读取端 `obj_doorway` 碰撞时 `trn.newRoom = nextroom`（目标房只来自 nextroom）
  ② **判非门**：对象**所有事件**里都没有任何转场指令 ⇒ 不是出口，移出图、单独登记（带证据）
  ③ **连通**：加 `hub:*` 枢纽节点 + 对每个非主分量补一条 `hub-orphan` 合成边（★ 用户授权
     「我不管你中间怎么转，把地图联通就好」）；合成边**单独成表**、带 reason，**原始分量统计原样保留**
  ④ **mod 并入**：《红与黄》的 20 间增量房按**索引对齐**无损并入 ut 命名空间（338 → 358）

★ 纪律：真实边与合成边**分开存**，绝不混进 `edges`；判非门必须给出可复核的代码证据。
"""
from __future__ import print_function
import collections, io, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
AUD = os.path.join(HERE, '..')
EV = os.path.join(AUD, '_evidence')
R65 = os.path.join(HERE, '..', '..', u'第65轮-黄魂并入Undertale大地图', '_evidence')

GML = {
    'ut': r'E:\Download\_extract61\_data\undertale\u65\gml65ut',
    'uty': r'E:\Download\_extract61\_data\undertale_yellow\uty65\gml65',
    'ry': r'E:\Download\_extract64\assets\redyellow65\gml65',
}
INST = {
    'ut': r'E:\Download\_extract61\_data\undertale\u65\u65_doorinst.json',
    'uty': r'E:\Download\_extract61\_data\undertale_yellow\uty65\r65_doorinst.json',
    'ry': r'E:\Download\_extract64\assets\redyellow65\r65_doorinst.json',
}
TOPO = {'ut': 'ut_topology65.json', 'uty': 'uty_topology65.json', 'ry': 'ry_topology65.json'}

# --- 载体 4 / 判非门用的正则 ---
RX_TRANSITION = [
    ('room_goto', re.compile(r'room_goto\s*\(')),
    ('room_goto_next', re.compile(r'room_goto_next\s*\(')),
    ('room_next', re.compile(r'room_next\s*\(')),
    ('room_previous', re.compile(r'room_previous\s*\(')),
    ('nextroom_assign', re.compile(r'(?<![A-Za-z0-9_.])nextroom\s*=\s*(-?\d+)')),
    ('room_assign', re.compile(r'(?<![A-Za-z0-9_.])room\s*=\s*([A-Za-z_][A-Za-z0-9_]*)')),
]
RX_EV = re.compile(r'^(.+?)_((?:Alarm|Create|Destroy|Step|Draw|Other|PreCreate|'
                   r'Collision|Keyboard|Mouse|KeyPress|KeyRelease|User|Async|'
                   r'Gesture|CleanUp)_\d+)$')


def strip_c(s):
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    return re.sub(r'//[^\n]*', '', s)


def load_events_dir(d):
    u"""{obj: [(filename, text)]}（文件名 → 对象名，含全部事件）。"""
    byobj = collections.defaultdict(list)
    if not os.path.isdir(d):
        return byobj
    for fn in sorted(os.listdir(d)):
        if not fn.startswith('gml_Object_') or not fn.endswith('.gml'):
            continue
        rest = fn[len('gml_Object_'):-4]
        m = RX_EV.match(rest)
        obj = m.group(1) if m else rest
        txt = strip_c(io.open(os.path.join(d, fn), encoding='utf-8',
                              errors='replace').read())
        byobj[obj].append((fn, txt))
    return byobj


def scan_object(files):
    u"""扫一个对象的**全部事件**，返回 (转场指令命中, nextroom 目标集合, 出处文件)。"""
    hits, targets, evs, fname = {}, set(), [], None
    for fn, txt in files:
        evs.append(fn)
        for k, rx in RX_TRANSITION:
            ms = list(rx.finditer(txt))
            if not ms:
                continue
            hits[k] = hits.get(k, 0) + len(ms)
            if fname is None:
                fname = fn
            if k == 'nextroom_assign':
                for m in ms:
                    targets.add(int(m.group(1)))
    return hits, targets, evs, fname


# ------------------------------------------------------------------ 建图
def build(work, rooms, resolved_edges, files_dir):
    pass


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.path.insert(0, os.path.join(HERE, '..', '..',
                                    u'第65轮-黄魂并入Undertale大地图', '_tools'))
    import topo_build65 as T65

    out = {'round': 66, 'generated_by': '_tools/build66.py', 'works': {},
           'nodes': [], 'edges': [], 'non_doors': [], 'notes': []}

    # ============ 1) 逐作品：补载体4 + 判非门 ============
    for work in ('ut', 'uty', 'ry'):
        topo = json.load(io.open(os.path.join(R65, TOPO[work]), encoding='utf-8'))
        rooms = topo['rooms']
        n = len(rooms)
        idx2name = dict((r['index'], r['name']) for r in rooms)
        name2idx = {}
        for r in rooms:
            name2idx.setdefault(r['name'], r['index'])
        byobj = load_events_dir(GML[work])
        instraw = json.load(io.open(INST[work], encoding='utf-8'))['rooms']
        room_objs = {}
        for r in instraw:
            room_objs[r['index']] = set(d['obj'] for d in r.get('doors', []))

        edges = [dict(e) for e in topo['edges']]
        # 已解析边覆盖到的 (room, obj)
        resolved_pairs = set()
        obj_resolved_rooms = collections.defaultdict(set)
        for e in edges:
            if e['to'] is not None:
                resolved_pairs.add((e['from'], e['via']))
                obj_resolved_rooms[e['via']].add(e['from'])

        non_doors = []
        added = []
        still_unresolved = []
        for e in edges:
            if e['to'] is not None:
                continue
            obj = e['via']
            rn = e['from']
            files = byobj.get(obj, [])
            if not files:
                e['evidence_kind'] = 'no-rule'
                e['note'] = 'object has no dumped events -> unjudged'
                non_doors.append({'work': work, 'obj': obj, 'room': rn,
                                  'rooms': [rn], 'reason': 'code-not-dumped',
                                  'files': 0,
                                  'evidence': u'本轮转储里没有该对象的任何事件文件 ⇒ '
                                              u'**无法判定**（不等于无出口）'})
                continue
            hits, targets, evs, fname = scan_object(files)
            real = [t for t in sorted(targets) if 0 <= t < n]
            if real:
                # —— 载体 4：事件里运行期写 nextroom
                for t in real:
                    added.append({
                        'from': rn, 'from_name': idx2name.get(rn),
                        'to': t, 'to_name': idx2name.get(t), 'via': obj,
                        'rule': 'cc-runtime', 'evidence_file': fname,
                        'evidence_kind': 'runtime-nextroom',
                        'note': 'instance_create + with(){nextroom=N} in event',
                    })
                continue
            has_trans = any(k in hits for k in
                            ('room_goto', 'room_goto_next', 'room_next',
                             'room_previous', 'room_assign'))
            sib = sorted(objs for objs in [room_objs.get(rn, set())] for objs in [objs])
            same_room_real = any((rn, o) in resolved_pairs for o in room_objs.get(rn, ()))
            if not has_trans:
                # 判非门：全事件无转场指令
                non_doors.append({
                    'work': work, 'obj': obj, 'room': rn, 'rooms': [rn],
                    'reason': ('non-door-superseded' if same_room_real
                               else 'non-door-noexit'),
                    'files': len(files), 'events': sorted(set(evs)),
                    'same_room_has_resolved_door': same_room_real,
                    'evidence': 'no transition instruction in any event',
                })
            else:
                e['note'] = 'has transition code but no branch for this room (dead/gated door)'
                e['pattern_hits'] = hits
                still_unresolved.append({'work': work, 'obj': obj, 'room': rn,
                                         'rooms': [rn], 'reason': 'dead-or-gated',
                                         'hits': hits})
        edges.extend(added)
        # 按 (from,to,via,rule) 去重
        uniq, seen = [], set()
        for e in edges:
            k = (e['from'], e['to'], e['via'], e['rule'], e.get('evidence_kind'))
            if k in seen:
                continue
            seen.add(k)
            uniq.append(e)
        topo['edges'] = uniq
        out['works'][work] = topo
        out['non_doors'].extend(non_doors)
        out['still_unresolved'] = out.get('still_unresolved', []) + still_unresolved
        print('== %s == 房间 %d ；补载4 新增 %d 条；判非门 %d 个对象；仍无解 %d 条'
              % (work, n, len(added), len(non_doors), len(still_unresolved)))

    # ============ 2) ut 家族：并入 ry 的 20 间增量房 ============
    ut = out['works']['ut']
    ry = out['works']['ry']
    n_ut = len(ut['rooms'])
    ut_names = [r['name'] for r in ut['rooms']]
    ry_names = [r['name'] for r in ry['rooms']]
    same = sum(1 for a, b in zip(ry_names, ut_names) if a == b)
    extra = [r for r in ry['rooms'] if r['index'] >= n_ut]

    def ekey(e):
        return (e['from'], e['to'], e['via'])

    ut_keys = set(ekey(e) for e in ut['edges'] if e['to'] is not None)
    merge_add = []
    for e in ry['edges']:
        if e['to'] is None:
            continue
        if ekey(e) in ut_keys:
            continue
        ee = dict(e)
        ee['origin'] = 'ry'
        if 'rule' not in ee:
            ee['rule'] = 'ry-extra'
        merge_add.append(ee)
        ut_keys.add(ekey(e))
    # 索引对齐：ry 的 0..337 与原版同名同序 ⇒ 新增房直接接在 338..
    extra_nodes = []
    for r in extra:
        extra_nodes.append({'index': r['index'], 'name': r['name'],
                            'w': r['w'], 'h': r['h'], 'origin': 'ry'})
    ut_rooms = ([dict(r) for r in ut['rooms']]
                + [{'index': r['index'], 'name': r['name'], 'w': r['w'], 'h': r['h'],
                    'origin': 'ry'} for r in extra])
    ut_edges = [dict(e) for e in ut['edges'] if e['to'] is not None]
    for e in ut_edges:
        e.setdefault('origin', 'ut')
    ut_edges = ut_edges + merge_add
    out['works']['ut'] = {
        'work': 'ut', 'title': ut['work'], 'rooms': ut_rooms, 'edges': ut_edges,
        'room_count': len(ut_rooms),
        'merged_from': {'ry_extra_rooms': len(extra), 'ry_extra_edges': len(merge_add),
                        'ry_base_same_order': same},
    }
    print('== ut 家族合并 == 合并前 %d 间 → %d 间；新增边 %d 条；ry 前 %d 间同名同序'
          % (n_ut, len(ut_rooms), len(merge_add), same))
    out['notes'].append(
        'ut 家族 = Undertale 原版 338 间 + 《红与黄》mod 增量 %d 间（索引对齐，无损 %d/%d 同名）；'
        '合并新增边 %d 条（其中 mod 对基础房的重路由含在内）。'
        % (len(extra), same, n_ut, len(merge_add)))

    # ============ 3) 统一节点/边 + 真实分量 ============
    nodes, edges = [], []
    for work in ('ut', 'uty'):
        t = out['works'][work]
        nm = {}
        for r in t['rooms']:
            nid = '%s:%d' % (work, r['index'])
            nm[r['index']] = r['name']
            nodes.append({'id': nid, 'work': work, 'index': r['index'],
                          'name': r['name'], 'w': r['w'], 'h': r['h'],
                          'origin': r.get('origin', work)})
        for e in t['edges']:
            if e['to'] is None:
                continue
            tgt = e['to']
            if not (0 <= tgt < len(t['rooms'])):
                continue
            edges.append({
                'from': '%s:%d' % (work, e['from']),
                'to': '%s:%d' % (work, tgt),
                'from_name': e.get('from_name'), 'to_name': e.get('to_name'),
                'via': e['via'], 'rule': e.get('rule'),
                'evidence_kind': e.get('evidence_kind'),
                'evidence_file': e.get('evidence_file'),
                'origin': e.get('origin', work),
            })
    node_ids = [n['id'] for n in nodes]
    comp, sizes, dropped = components(node_ids, edges)
    real_stats = {'components': len(sizes),
                  'largest': sizes.most_common(1)[0][1] if sizes else 0,
                  'top_sizes': [list(x) for x in sizes.most_common(12)],
                  'dropped_dangling': dropped}

    # ============ 4) hub + 合成边（用户授权） ============
    HUBS = [('hub:desktop', 'desktop', u'桌面（本项目既有概念：桌面也是一个场景）'),
            ('hub:ut', 'ut', u'Undertale 世界枢纽'),
            ('hub:uty', 'uty', u'黄魂世界枢纽')]
    hub_nodes = [{'id': i, 'work': w, 'index': -1, 'name': i, 'kind': 'hub'} for i, w, _ in HUBS]
    hub_edges, synth = [], []
    # 桌面 ↔ 各世界枢纽（走"暗之泉/桌面门户"）
    for h in ('hub:ut', 'hub:uty'):
        hub_edges.append({'from': 'hub:desktop', 'to': h, 'via': 'hub',
                          'rule': 'hub-link', 'evidence_kind': 'synthetic',
                          'note': u'桌面上通向该世界的门户（暗之泉式）'})
    # 各世界的入口房（= 该作品 index 最小的房，确定性）
    entry = {'ut': 'ut:0', 'uty': 'uty:0'}
    for w, tgt in entry.items():
        hub_edges.append({'from': 'hub:' + w, 'to': tgt, 'via': 'hub',
                          'rule': 'hub-entry', 'evidence_kind': 'synthetic',
                          'note': u'该作品的开场房（%s）'
                                  % next(n['name'] for n in nodes if n['id'] == tgt)})
    # 每个「不含入口房」的分量 → 该作品 hub
    #   ★ 不按"最大分量"豁免：原作里最大分量未必含开场房（实测 ut 开场房不在最大分量里），
    #     按"最大"豁免会漏挂 ⇒ 图仍不连通。唯一豁免 = 入口房所在分量。
    comp_of = collections.defaultdict(list)
    for nid in node_ids:
        comp_of[comp[nid]].append(nid)
    entry_comp = dict((w, comp[t]) for w, t in entry.items())
    for cid, ids in sorted(comp_of.items()):
        ws = set(i.split(':')[0] for i in ids)
        if len(ws) != 1:
            continue
        w = ws.pop()
        if cid == entry_comp[w]:
            continue
        rep = min(ids, key=lambda s: int(s.split(':')[1]))
        synth.append({'from': 'hub:' + w, 'to': rep, 'via': 'hub',
                      'rule': 'hub-orphan', 'evidence_kind': 'synthetic',
                      'note': u'该分量在原作门机制下不可达（%d 间），挂到世界枢纽'
                              % len(ids)})

    all_nodes = node_ids + [h['id'] for h in hub_nodes]
    _, sizes2, _ = components(all_nodes, edges + hub_edges + synth)
    final = {'components': len(sizes2),
             'largest': sizes2.most_common(1)[0][1] if sizes2 else 0,
             'top_sizes': [list(x) for x in sizes2.most_common(6)]}

    out['nodes'] = nodes
    out['edges'] = edges
    out['hub'] = {'nodes': hub_nodes, 'edges': hub_edges}
    out['synthetic_edges'] = synth
    out['connectivity'] = {'real': real_stats, 'with_synthetic': final}
    out['counts'] = {
        'nodes': len(nodes), 'edges': len(edges), 'hub_nodes': len(hub_nodes),
        'hub_edges': len(hub_edges), 'synthetic_edges': len(synth),
        'by_work': dict((w, {'rooms': out['works'][w]['room_count'],
                             'edges': len([e for e in edges if e['from'].split(':')[0] == w])})
                        for w in ('ut', 'uty')),
        'by_evidence': dict(collections.Counter(e['evidence_kind'] for e in edges)),
    }
    dst = os.path.join(EV, 'bigmap66.json')
    io.open(dst, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=1))
    print('\n===== bigmap66 =====')
    print('nodes=%d  edges=%d' % (len(nodes), len(edges)))
    print('  真实分量 = %d（最大 %d）；+hub/合成后 = %d（最大 %d）'
          % (real_stats['components'], real_stats['largest'],
             final['components'], final['largest']))
    print('  by_evidence = %s' % json.dumps(out['counts']['by_evidence'], ensure_ascii=False))
    print('  非门对象 %d 个' % len(out['non_doors']))
    print('-> %s' % dst)
    return 0


# ------------------------------------------------------------------ 图工具
def components(node_ids, edges):
    adj = collections.defaultdict(set)
    idset = set(node_ids)
    dropped = 0
    for e in edges:
        a, b = e['from'], e['to']
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
        seen, st = {n}, [n]
        while st:
            u = st.pop()
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    st.append(v)
        for v in seen:
            comp[v] = cid
    return comp, collections.Counter(comp.values()), dropped


if __name__ == '__main__':
    raise SystemExit(main())
