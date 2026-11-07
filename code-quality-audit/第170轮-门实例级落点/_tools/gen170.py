# -*- coding: utf-8 -*-
u"""第170轮：按 GML 源码生成**修正计划**（只生成清单，不动 `_routes.json`）。

四类改动，各自独立、逐条可审
----------------------------
  A `door_x_add`  —— 给「能完整映射的 20 个房间」的规则补上门实例坐标
                     （判据来自 `feasible170.py` 的 FULL；每条分支唯一命中一扇门）
  B `ent_fill`    —— 表里没记 `entrance` 的，按源码补上（不算改错，是补空）
  C `ent_fix`     —— 表里记了但与源码不符的，改（逐条留「改前→改后」）
  D `new_rules`   —— GML 有、表里没有，且四个条件都满足的（第169轮 `unreg` 同一把尺）

★ 三条「不许猜」的护栏
  ① 同一 (源房, 目标, 对象) 在 GML 侧出现多条分支且 **entrance 不唯一** ⇒ 不补不改，进 `left`。
  ② 位置分支命中 0 个或 ≥2 个实例 ⇒ 该房间整批不进 A，进 `left`。
  ③ 目标房未登记成 scene ⇒ 不进 D（不许建指向不存在场景的门）。
"""
import collections
import glob
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
GML = os.path.join(ROUND, '_evidence', 'gml170.json')
FEAS = os.path.join(ROUND, '_evidence', 'feasible170.json')
DIFF = os.path.join(ROUND, '_evidence', 'diff170.json')
OUT = os.path.join(ROUND, '_evidence', 'fix170.json')

PRIO_BASE = 7190          # 新规则从 7190 起（第169轮止于 7189）


def jl(p):
    return json.loads(io.open(p, encoding='utf-8', errors='replace', newline='').read())


def main():
    g = jl(GML)
    feas = jl(FEAS)
    diff = jl(DIFF)
    routes = jl(os.path.join(SCENES, '_routes.json'))['routes']

    M = {}
    by_room = collections.defaultdict(dict)
    for f in glob.glob(os.path.join(SCENES, '_zone.*.json')):
        z = jl(f)
        ch = z.get('chapter_id') or ''
        s = z.get('scenes')
        it = (s.items() if isinstance(s, dict) else ((v.get('scene_id'), v) for v in s))
        for k, v in it:
            if not isinstance(v, dict):
                continue
            sid = v.get('scene_id') or k
            M[sid] = v.get('objects') or []
            if v.get('original_room_id') is not None:
                by_room[ch][v['original_room_id']] = sid

    #: (ch, src_room_id, via) -> 规则列表（table 侧）
    tbl = collections.defaultdict(list)
    for r in routes:
        o = r.get('_original') or {}
        if o.get('via') not in ('obj_doorW', 'obj_doorw_musfade'):
            continue
        tbl[(o.get('chapter'), o.get('src_room_id'), o.get('via'))].append(r)

    door_x_add = []
    left = []
    same = 0

    # ---------- A: door_x ----------
    for f in feas['rows']:
        if f['tag'] != 'FULL':
            left.append({'kind': 'door_x', 'why': f['tag'], 'ch': f['ch'],
                         'room': f['room'], 'sid': f['sid'],
                         'detail': [{'cond': x['cond'], 'hit': x['hit']} for x in f['detail']]})
            continue
        inst = [(i, o.get('pos') or [None, None])
                for i, o in enumerate(M.get(f['sid']) or []) if o.get('src') == f['obj']]
        # ★ `feasible170` 的 `hit` 存的是**原始 objects 下标**（不是过滤后的序号），
        #   拿它去索引这个过滤后的列表会越界。先建 下标→pos 的字典。
        pos_by_idx = dict(inst)
        rid = _room_id_of(g, f)
        rs = tbl.get((f['ch'], rid, f['obj']), [])
        for x in f['detail']:
            idx = x['hit'][0]
            pp = pos_by_idx.get(idx)
            if pp is None:
                left.append({'kind': 'door_x', 'why': 'inst_idx_missing', 'room': f['room']})
                continue
            cx, cy = pp[0], pp[1]
            if cx is None:
                left.append({'kind': 'door_x', 'why': 'no_pos_x', 'room': f['room']})
                continue
            hit_rules = [r for r in rs
                         if (r.get('_original') or {}).get('dst_room_id') == x['to']]
            if len(hit_rules) != 1:
                left.append({'kind': 'door_x', 'why': 'rules_%d_for_dst_%s'
                             % (len(hit_rules), x['to']), 'room': f['room'],
                             'cond': x['cond']})
                continue
            r = hit_rules[0]
            o = r['_original']
            # ★★★ 已一致的不算「修」：第169轮有些 `door_x` 本来就对
            #   （例：`town_mid -> lw_icee_pizza` 的 `door_x` 已经是 301）。
            #   把它们也算进「改动」会让差异表虚高，且白改一遍文件。
            if x['axis'] == 'x' and o.get('door_x') == cx:
                same += 1
                continue
            if x['axis'] == 'y' and o.get('door_y') == cy:
                same += 1
                continue
            door_x_add.append({
                'priority': r.get('priority'), 'scene': r.get('when_scene'),
                'src_room_id': rid,
                'room': f['room'], 'via': f['obj'], 'dst': r['to'],
                'cond': x['cond'], 'axis': x['axis'],
                'x': cx, 'y': cy, 'inst_index': idx,
                'old_door_x': o.get('door_x'),
                'old_door_y': o.get('door_y'),
            })

    # ---------- B/C: entrance ----------
    # GML 侧：(ch, src_room, via, dst) -> set(ent)
    gmap = collections.defaultdict(set)
    for ch, chd in g['chapters'].items():
        for obj, d in chd.items():
            for room, v in d['rooms'].items():
                if v['room_id'] is None:
                    continue
                for b in v['branches']:
                    if b['ent'] is not None:
                        gmap[(ch, v['room_id'], obj, b['to_id'])].add(b['ent'])
    ent_fill, ent_fix, ent_left = [], [], []
    for (ch, rid, via), rs in tbl.items():
        for r in rs:
            o = r['_original']
            dst = o.get('dst_room_id')
            ents = gmap.get((ch, rid, via, dst))
            if not ents:
                ent_left.append({'priority': r.get('priority'), 'why': 'no_gml_ent',
                                 'scene': r.get('when_scene')})
                continue
            if len(ents) > 1:
                ent_left.append({'priority': r.get('priority'), 'why': 'gml_ent_ambiguous%r' % (sorted(ents),),
                                 'scene': r.get('when_scene')})
                continue
            v = next(iter(ents))
            cur = o.get('entrance')
            if cur is None:
                ent_fill.append({'priority': r.get('priority'), 'scene': r.get('when_scene'),
                                 'dst': r['to'], 'ent': v})
            elif cur != v:
                ent_fix.append({'priority': r.get('priority'), 'scene': r.get('when_scene'),
                                'dst': r['to'], 'old': cur, 'new': v})

    # ---------- D: 新增规则 ----------
    plan = jl(os.path.join(ROUND, '_evidence', 'plan170.json'))
    new_rules = [r for r in plan['rows'] if r['ok']]

    out = {'stat': {'door_x_add': len(door_x_add), 'door_x_same': same,
                    'ent_fill': len(ent_fill),
                    'ent_fix': len(ent_fix), 'new_rules': len(new_rules),
                    'left': len(left) + len(ent_left)},
           'door_x_add': door_x_add, 'ent_fill': ent_fill, 'ent_fix': ent_fix,
           'new_rules': new_rules, 'left': left, 'ent_left': ent_left}
    print(u'== 修正计划 ==')
    for k, v in out['stat'].items():
        print(u'  %-14s %d' % (k, v))
    print()
    print(u'--- A door_x 补坐标（%d 条）---' % len(door_x_add))
    for x in door_x_add:
        print(u'  prio=%-6s %-46s -> %-42s x=%-6s %s'
              % (x['priority'], x['scene'], x['dst'], x['x'], x['cond']))
    print()
    print(u'--- C entrance 改错（%d 条）---' % len(ent_fix))
    for x in ent_fix:
        print(u'  prio=%-6s %-46s -> %-40s %s => %s'
              % (x['priority'], x['scene'], x['dst'], x['old'], x['new']))
    print()
    print(u'--- D 新增规则（%d 条）---' % len(new_rules))
    for x in new_rules:
        print(u'  %s %-44s -> %-44s %-6s ent=%s'
              % (x['ch'], x['sid_s'], x['sid_t'], x['kind'], x['ent']))
    print()
    print(u'--- 留档不动的 %d 条（逐条点名）---' % (len(left) + len(ent_left)))
    c = collections.Counter(x['why'] for x in left + ent_left)
    for k, v in sorted(c.items(), key=lambda t: -t[1]):
        print(u'  %-24s %d' % (k, v))

    text = json.dumps(out, ensure_ascii=False, indent=1)
    io.open(OUT, 'wb').write(text.replace('\n', '\r\n').encode('utf-8'))
    print()
    print(u'落盘 %s (%d B)' % (OUT, os.path.getsize(OUT)))


def _room_id_of(g, f):
    u"""从 gml170 里反查该 room 的数字房号（feasible 的 rows 没带 room_id）。"""
    for obj, d in g['chapters'][f['ch']].items():
        v = d['rooms'].get(f['room'])
        if v:
            return v['room_id']
    return None


if __name__ == '__main__':
    main()
