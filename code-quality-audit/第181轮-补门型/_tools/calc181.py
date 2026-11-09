# -*- coding: utf-8 -*-
u"""第181轮 · A/B/C 门（含 musfade 变体）候选边推导（只读）。

## 取证结论（`probe181.ch1.txt`，逐指令）

| 门型 | entrance | 换房调用 | 位移 |
|---|---|---|---|
| `obj_doorA` | 1 | `room_goto_next()` | **+1** |
| `obj_doorB` | 2 | `room_goto_previous()` | **−1** |
| `obj_doorC` | 4 | `room_goto(room_next(room_next(room)))` | **+2** |
| `obj_doorD` | 5 | `room_goto(room_previous(room_previous(room)))` | **−2** |
| `obj_doorA_musfade` | 1 | `room_goto_next()` | +1 |
| `obj_doorB_musfade` | 2 | `room_goto_previous()` | −1 |
| `obj_doorC_musfade` | 4 | `room_next`×2 | +2 |

★ 位移全部落在 `Data.Rooms` **下标**上（`_room_order.json` 的 meta 已写明）：
  「门对象的 ±1/±2/±3 位移全部基于本表下标」。
★ 位移**不夹取**：`room_next` 在 GMS2 里越界返回 −1（`room_goto(-1)` 是无效目标）
  ⇒ 越界必须如实记 `out_of_range`，**不许钳到最后一间**（那会造出原作没有的边）。

本脚本只统计，不写产品：
  ① 每种门型 → 候选边数 / 落点已是场景 / 落点未登记 / 越界
  ② 与**已有路由**比对：已存在（同 when→to）⇒ 跳过
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

#: 门型 → 位移（正 = 往后，负 = 往前）。取证来源见模块 docstring。
SHIFT = {
    'obj_doorA': +1,
    'obj_doorA_musfade': +1,
    'obj_doorB': -1,
    'obj_doorB_musfade': -1,
    'obj_doorC': +2,
    'obj_doorC_musfade': +2,
    'obj_doorD': -2,
    'obj_doorD_musfade': -2,
}


def load_scenes():
    idx = json.load(io.open(os.path.join(SCENES, '_index.json'), encoding='utf-8'))
    by_rid = {}
    for w, wd in idx['chapters'].items():
        for a, ad in wd.get('areas', {}).items():
            for sid, sd in ad.get('scenes', {}).items():
                rid = sd.get('original_room_id')
                if rid is not None:
                    by_rid[(w, rid)] = sid
    return by_rid


def main():
    by_rid = load_scenes()
    routes = json.load(io.open(os.path.join(SCENES, '_routes.json'), encoding='utf-8'))['routes']
    have = collections.defaultdict(set)
    for r in routes:
        have[r['when_scene']].add(r['to'])

    order = json.load(io.open(os.path.join(EV42, '_room_order.json'), encoding='utf-8'))['chapters']

    stat = collections.defaultdict(collections.Counter)
    per_kind = collections.defaultdict(list)
    for ch, f in CHAPTERS:
        p = os.path.join(EV42, f)
        if not os.path.exists(p):
            print(u'!! 缺证据 %s' % p)
            continue
        d = json.load(io.open(p, encoding='utf-8'))
        rid2name = {r['index']: r['name'] for r in order[ch]['rooms']}
        maxidx = max(rid2name) if rid2name else -1
        for rm in d['rooms']:
            src_sid = by_rid.get((ch, rm['index']))
            if not src_sid:
                continue
            for inst in rm['insts']:
                kind = inst['obj']
                if kind not in SHIFT:
                    continue
                st = stat[kind]
                st['inst'] += 1
                tgt_idx = rm['index'] + SHIFT[kind]
                if tgt_idx < 0 or tgt_idx > maxidx:
                    st['out_of_range'] += 1
                    per_kind[kind].append((ch, rm['index'], rm['name'], kind,
                                           tgt_idx, None, 'out_of_range'))
                    continue
                tgt_sid = by_rid.get((ch, tgt_idx))
                if not tgt_sid:
                    st['no_scene'] += 1
                    per_kind[kind].append((ch, rm['index'], rm['name'], kind,
                                           tgt_idx, rid2name.get(tgt_idx), 'no_scene'))
                    continue
                if tgt_sid in have.get(src_sid, ()):
                    st['dup'] += 1
                    continue
                st['new'] += 1
                per_kind[kind].append((ch, rm['index'], rm['name'], kind,
                                       tgt_idx, tgt_sid, 'new'))

    print(u'=' * 84)
    print(u'第181轮 · 按序号位移的候选边（只读）')
    print(u'=' * 84)
    print(u'%-22s %5s %6s %6s %6s %6s' % (u'门型', u'实例', u'新边', u'已有', u'无场景', u'越界'))
    tot = collections.Counter()
    for k in sorted(stat, key=lambda x: -stat[x]['inst']):
        s = stat[k]
        print(u'%-22s %5d %6d %6d %6d %6d'
              % (k, s['inst'], s['new'], s['dup'], s['no_scene'], s['out_of_range']))
        for f in s:
            tot[f] += s[f]
    print(u'-' * 84)
    print(u'%-22s %5d %6d %6d %6d %6d'
          % (u'合计', tot['inst'], tot['new'], tot['dup'], tot['no_scene'], tot['out_of_range']))

    print(u'')
    print(u'--- 无场景 / 越界 明细（前 30）---')
    n = 0
    for k in per_kind:
        for row in per_kind[k]:
            if row[6] == 'new':
                continue
            n += 1
            if n > 30:
                break
            print(u'  %-4s #%-5d %-34s %-20s -> #%-5d %s  [%s]'
                  % (row[0], row[1], row[2], row[3], row[4], row[5], row[6]))
    print(u'  (共 %d 条非新边)' % n)
    return 0


if __name__ == '__main__':
    sys.exit(main())
