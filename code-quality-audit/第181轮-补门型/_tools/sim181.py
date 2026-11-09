# -*- coding: utf-8 -*-
u"""第181轮 · 可达性模拟（只读，不写产品）。

把「A/B/C/D/E/F 位移门」推出的净新增边**只在内存里**加进去，比较：
  ① 桌面可达场景数（改前 / 改后）
  ② 弱连通分量数（改前 / 改后）
  ③ 净增边逐条列出（源 → 目标 + 依据）

★ 模拟 ≠ 落盘。本脚本绝不写 `_routes.json`。
"""
import io
import json
import os
import sys
import collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
EV42 = os.path.join(REPO, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')

CHAPTERS = [
    ('ch1', 'inst42.json'),
    ('ch2', 'ch2_inst42.json'),
    ('ch3', 'ch3_inst42.json'),
    ('ch4', 'ch4_inst42.json'),
    ('ch5', 'ch5_inst42.json'),
]

#: 见 calc181.py docstring：逐指令取证 + ch1 反编译 GML 双向核对
SHIFT = {
    'obj_doorA': +1, 'obj_doorA_musfade': +1,
    'obj_doorB': -1, 'obj_doorB_musfade': -1,
    'obj_doorC': +2, 'obj_doorC_musfade': +2,
    'obj_doorD': -2, 'obj_doorD_musfade': -2,
    'obj_doorE': +3, 'obj_doorF': -3,
}

#: 取证到的**单点覆盖**：ch3 的 obj_doorC 在 room#110 特判去 28
#:   证据 `probe181b.ch3.json` → `gml_Object_obj_doorC_Alarm_2`:
#:     if (global.chapter == 3 && room == 110) { room_goto(28); exit; }
OVERRIDE = {('ch3', 110, 'obj_doorC'): 28}


def load_scenes():
    idx = json.load(io.open(os.path.join(SCENES, '_index.json'), encoding='utf-8'))
    by_rid, all_ids = {}, set()
    for w, wd in idx['chapters'].items():
        for a, ad in wd.get('areas', {}).items():
            for sid, sd in ad.get('scenes', {}).items():
                all_ids.add(sid)
                rid = sd.get('original_room_id')
                if rid is not None:
                    by_rid[(w, rid)] = sid
    return by_rid, all_ids


def reach(nodes, adj, start):
    seen = {start}
    dq = collections.deque([start])
    while dq:
        u = dq.popleft()
        for v in adj.get(u, ()):
            if v in nodes and v not in seen:
                seen.add(v)
                dq.append(v)
    return seen


def n_comp(nodes, adj):
    seen = set()
    n = 0
    for s in nodes:
        if s in seen:
            continue
        n += 1
        stack = [s]
        seen.add(s)
        while stack:
            u = stack.pop()
            for v in list(adj.get(u, ())) + list(rev.get(u, ())):
                if v in nodes and v not in seen:
                    seen.add(v)
                    stack.append(v)
    return n


def main():
    global rev
    by_rid, all_ids = load_scenes()
    routes = json.load(io.open(os.path.join(SCENES, '_routes.json'), encoding='utf-8'))['routes']
    adj = collections.defaultdict(set)
    for r in routes:
        adj[r['when_scene']].add(r['to'])

    before = reach(all_ids, adj, 'desktop')

    order = json.load(io.open(os.path.join(EV42, '_room_order.json'), encoding='utf-8'))['chapters']
    new = []
    for ch, f in CHAPTERS:
        p = os.path.join(EV42, f)
        if not os.path.exists(p):
            continue
        d = json.load(io.open(p, encoding='utf-8'))
        rid2name = {r['index']: r['name'] for r in order[ch]['rooms']}
        maxidx = max(rid2name) if rid2name else -1
        for rm in d['rooms']:
            src = by_rid.get((ch, rm['index']))
            if not src:
                continue
            for inst in rm['insts']:
                kind = inst['obj']
                if kind not in SHIFT:
                    continue
                tgt_idx = OVERRIDE.get((ch, rm['index'], kind), rm['index'] + SHIFT[kind])
                if tgt_idx < 0 or tgt_idx > maxidx:
                    continue
                dst = by_rid.get((ch, tgt_idx))
                if not dst:
                    continue
                if dst in adj.get(src, ()):
                    continue
                new.append((ch, rm['index'], rm['name'], kind, tgt_idx, rid2name.get(tgt_idx), src, dst))

    # 只加不重复的 (src,dst)
    seen = set()
    cand = []
    for t in new:
        k = (t[6], t[7])
        if k in seen:
            continue
        seen.add(k)
        cand.append(t)

    for t in cand:
        adj[t[6]].add(t[7])

    after = reach(all_ids, adj, 'desktop')

    print(u'=' * 90)
    print(u'第181轮 · 可达性模拟（只在内存里加边，不落盘）')
    print(u'=' * 90)
    print(u'场景总数            %d' % len(all_ids))
    print(u'候选净新增边        %d 条（去重后）' % len(cand))
    print(u'桌面可达（改前）    %d' % len(before))
    print(u'桌面可达（改后）    %d   (+%d)' % (len(after), len(after) - len(before)))
    print(u'')
    print(u'--- 净增边逐条 ---')
    for t in cand:
        print(u'  %-4s #%-5d %-34s %-20s -> #%-5d %-34s  %s'
              % (t[0], t[1], t[2], t[3], t[4], t[5], t[7]))
    return 0


rev = collections.defaultdict(set)

if __name__ == '__main__':
    # 供 n_comp 用
    routes0 = json.load(io.open(os.path.join(SCENES, '_routes.json'), encoding='utf-8'))['routes']
    for r in routes0:
        rev[r['to']].add(r['when_scene'])
    sys.exit(main())
