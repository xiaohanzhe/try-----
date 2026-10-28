# -*- coding: utf-8 -*-
"""第115轮 · 全量实例坐标（把 raw/chN/inst_full.tsv 汇总成人能用的索引）

TSV 是唯一真源（UTMT csx 直接产物，47,895 行），本脚本**不复制**逐实例数据，
只产出「索引 + 聚合」：
  _evidence/deltarune_instances115.json   每章每房（房间名/尺寸/层数/实例数）+ 每个对象的聚合
  _evidence/deltarune_instances115.txt    人看的摘要

TSV 列义（`_tools/dump_instances.csx` 定义）：
  H  <rooms> <gameObjectsTotal>
  R  <房号> <房名> <宽> <高> <层数> <层内实例数> <GameObjects数>
  I  <对象名> <x> <y> <scaleX> <scaleY> <rotation> <imageIndex> <imageSpeed> <depth> <层名>

★ 坐标系提醒：每间房的 x/y 是**该房自己的局部系**，跨房比距离/比较 bbox 在原理上不成立
  （第44轮已证伪）。本文件里的 bbox 只用来"看量级"，不要拿去算远近。
"""
import io
import json
import os
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EV = os.path.join(ROUND, '_evidence')
RAW = os.path.join(EV, 'raw')
CHAPTERS = [1, 2, 3, 4, 5]


def parse_tsv(p):
    hdr = None
    rooms = []
    cur_room = None
    objs = collections.defaultdict(lambda: {
        'inst': 0, 'x0': None, 'x1': None, 'y0': None, 'y1': None,
        'scales': collections.Counter(), 'rots': collections.Counter(),
        'depths': set(), 'rooms': set(), 'chapters': set(),
    })
    with io.open(p, encoding='utf-8') as f:
        for ln in f:
            ln = ln.rstrip('\n')
            if not ln:
                continue
            c = ln[0]
            if c == 'H':
                p2 = ln.split('\t')
                # 注意：CSV 头第二个数是 `Data.GameObjects.Count` = **对象定义数**，
                # 不是实例数（ch1 是 353）。实例数只能靠房间行累加。
                hdr = {'rooms': int(p2[1]), 'object_defs': int(p2[2])}
            elif c == 'R':
                _, idx, name, w, h, nl, ni, ng = ln.split('\t')
                cur_room = {'index': int(idx), 'name': name, 'w': int(w), 'h': int(h),
                            'layers': int(nl), 'inst': int(ni), 'gameobjects': int(ng)}
                rooms.append(cur_room)
            elif c == 'I':
                p2 = ln.split('\t')
                _, on, x, y, sx, sy, rot, idx2, isp, depth, layer = p2
                x = float(x)
                y = float(y)
                e = objs[on]
                e['inst'] += 1
                e['x0'] = x if e['x0'] is None else min(e['x0'], x)
                e['x1'] = x if e['x1'] is None else max(e['x1'], x)
                e['y0'] = y if e['y0'] is None else min(e['y0'], y)
                e['y1'] = y if e['y1'] is None else max(e['y1'], y)
                e['scales'][(sx, sy)] += 1
                e['rots'][rot] += 1
                e['depths'].add(int(depth))
                e['rooms'].add(cur_room['name'])
    return hdr, rooms, objs


def main():
    per = {}
    allobj = collections.defaultdict(lambda: {
        'inst': 0, 'x0': None, 'x1': None, 'y0': None, 'y1': None,
        'scales': collections.Counter(), 'rots': collections.Counter(),
        'depths': set(), 'rooms': 0, 'chapters': set(),
    })
    tot_rooms = tot_inst = 0
    room_index = []

    for ch in CHAPTERS:
        hdr, rooms, objs = parse_tsv(os.path.join(RAW, 'ch%d' % ch, 'inst_full.tsv'))
        n_inst = sum(r['inst'] for r in rooms)
        assert hdr['rooms'] == len(rooms), 'ch%d H 头的房间数与实际行数不一致' % ch
        assert n_inst > 0
        per[str(ch)] = {'rooms': len(rooms), 'inst': n_inst, 'objects': len(objs),
                        'object_defs': hdr['object_defs']}
        tot_rooms += len(rooms)
        tot_inst += n_inst
        room_index.append({'ch': ch, 'rooms': [
            {'i': r['index'], 'name': r['name'], 'w': r['w'], 'h': r['h'],
             'layers': r['layers'], 'inst': r['inst']} for r in rooms]})
        for name, e in objs.items():
            a = allobj[name]
            a['inst'] += e['inst']
            for k, kk in (('x0', 'x0'), ('x1', 'x1'), ('y0', 'y0'), ('y1', 'y1')):
                v = e[k]
                if v is None:
                    continue
                a[kk] = v if a[kk] is None else (min if '0' in k else max)(a[kk], v)
            a['scales'].update(e['scales'])
            a['rots'].update(e['rots'])
            a['depths'] |= e['depths']
            a['rooms'] += len(e['rooms'])
            a['chapters'].add(ch)

    objects = []
    n_scaled = n_rot = 0
    for name in sorted(allobj, key=lambda n: (-allobj[n]['inst'], n)):
        a = allobj[name]
        scaled = any((sx, sy) != ('1', '1') for (sx, sy) in a['scales'])
        rots = [r for r in a['rots'] if r not in ('0', '0.0', '0.00', '0.0000')]
        if scaled:
            n_scaled += 1
        if rots:
            n_rot += 1
        objects.append({
            'name': name,
            'inst': a['inst'],
            'rooms': a['rooms'],
            'chapters': sorted(a['chapters']),
            'x': [a['x0'], a['x1']],
            'y': [a['y0'], a['y1']],
            'n_scales': len(a['scales']),
            'scales': [list(k) for k, _ in a['scales'].most_common(3)],
            'n_rots': len(a['rots']),
            'rots': [float(r) for r, _ in a['rots'].most_common(3)],
            'depths': sorted(a['depths']),
        })

    out = {
        'note': '第115轮 · 全量实例坐标索引（逐实例数据在 raw/chN/inst_full.tsv，本文件只给聚合）',
        'source': '_tools/dump_instances.csx 经 UTMT CLI v0.9.2.0 导出，五章 data.win 副本 sha256 已核对',
        'coord_warning': 'x/y 是每间房的局部坐标系，跨房不可比（第44轮已证伪），bbox 只用于看量级',
        'per_chapter': per,
        'totals': {'rooms': tot_rooms, 'inst': tot_inst, 'objects': len(objects),
                   'objects_scaled': n_scaled, 'objects_rotated': n_rot},
        'objects': objects,
        'room_index': room_index,
    }
    pj = os.path.join(EV, 'deltarune_instances115.json')
    with io.open(pj, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    lines = [u'第115轮 · 全量实例坐标索引',
             u'%d 间房 / %d 个实例 / %d 个不同对象（其中带非 1 缩放的 %d 个、带旋转的 %d 个）'
             % (tot_rooms, tot_inst, len(objects), n_scaled, n_rot), u'']
    for ch in CHAPTERS:
        d = per[str(ch)]
        lines.append(u'ch%d：%d 间 / %d 实例 / %d 对象'
                     % (ch, d['rooms'], d['inst'], d['objects']))
    lines.append(u'')
    lines.append(u'实例最多的 10 个（x/y 区间是跨房原始值，只用于看量级）：')
    for o in objects[:10]:
        lines.append(u'  %-42s inst=%-5d rooms=%-4d x[%s..%s] y[%s..%s]'
                     % (o['name'], o['inst'], o['rooms'], o['x'][0], o['x'][1],
                        o['y'][0], o['y'][1]))
    lines.append(u'')
    lines.append(u'带缩放的（前 10 个）：')
    for o in [o for o in objects if o['n_scales'] > 1][:10]:
        lines.append(u'  %-42s %d 种缩放 最常见的 %s' % (o['name'], o['n_scales'], o['scales'][0]))
    pt = os.path.join(EV, 'deltarune_instances115.txt')
    with io.open(pt, 'w', encoding='utf-8', newline='\n') as f:
        f.write(u'\n'.join(lines) + u'\n')

    print(u'\n'.join(lines[:10]))
    print(u'落盘：deltarune_instances115.json (%.0f KB) / .txt'
          % (os.path.getsize(pj) / 1024.0))


if __name__ == '__main__':
    main()
