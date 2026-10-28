# -*- coding: utf-8 -*-
"""第115轮 · 交互点坐标表（门 / 命名标记 / 可读物 / 存档 / 宝箱 / 招牌 / 传送）

为什么有这个：全量物件坐标要重跑 UTMT（本轮被环境挡住，见 report115 §7），
但第68轮那批 `inst68.json` **本来就带 x/y**，覆盖的是"能交互的东西"——
door / marker / readable / savepoint / treasure / sign / warptouch。
对"把世界搬上桌面"来说，这一撮恰恰是**最需要坐标**的部分（门要连路线、可读物要能读、
存档点和宝箱要能碰）。

输入：_evidence/raw/chN/inst68.json（已蒸馏进仓库，不依赖临时盘）
输出：_evidence/deltarune_points115.json
      _evidence/deltarune_points115.txt
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

# 分类顺序即优先级；名字全是小写 obj_*，用包含匹配（比正则好读）
KINDS = [
    ('door', lambda n: 'door' in n),
    ('warp', lambda n: 'warp' in n),
    ('marker', lambda n: 'marker' in n),
    ('save', lambda n: 'savepoint' in n),
    ('treasure', lambda n: 'treasure' in n),
    ('readable', lambda n: n.startswith('obj_readable')),
    ('sign', lambda n: 'sign' in n),
]


def kind_of(name):
    n = name.lower()
    for k, f in KINDS:
        if f(n):
            return k
    return 'other'


def load(p):
    return json.load(io.open(p, encoding='utf-8'))


def main():
    chapters = []
    by_kind = collections.Counter()
    tot_points = 0
    rooms_total = 0
    rooms_hit = 0
    per_kind_ch = collections.defaultdict(lambda: collections.Counter())

    for ch in CHAPTERS:
        d = load(os.path.join(RAW, 'ch%d' % ch, 'inst68.json'))
        rooms_total += d['n_rooms_total']
        out_rooms = []
        s = 0
        for r in d['rooms']:
            pts = []
            for it in r['insts']:
                k = kind_of(it['obj'])
                by_kind[k] += 1
                per_kind_ch[ch][k] += 1
                pts.append({
                    'obj': it['obj'],
                    'kind': k,
                    'x': it['x'],
                    'y': it['y'],
                    'depth': it['depth'],
                })
                s += 1
            out_rooms.append({
                'index': r['index'],
                'name': r['name'],
                'w': r['w'],
                'h': r['h'],
                'points': pts,
            })
        assert s == d['n_inst'], 'ch%d 实例数对不上 %d vs %d' % (ch, s, d['n_inst'])
        assert len(out_rooms) == d['n_rooms_hit'], 'ch%d 房间数对不上' % ch
        rooms_hit += len(out_rooms)
        tot_points += s
        chapters.append({'ch': ch, 'rooms_total': d['n_rooms_total'], 'rooms': out_rooms})

    out = {
        'note': '第115轮 · 交互点坐标（门/标记/可读物/存档/宝箱/招牌/传送），不是全量物件坐标',
        'source': 'raw/chN/inst68.json（第68轮 UTMT 导出，带 x/y，只覆盖可交互类对象）',
        'coverage': {
            'rooms_total': rooms_total,
            'rooms_with_points': rooms_hit,
            'points': tot_points,
        },
        'by_kind': dict(by_kind),
        'by_kind_per_chapter': {str(c): dict(per_kind_ch[c]) for c in CHAPTERS},
        'chapters': chapters,
    }
    with io.open(os.path.join(EV, 'deltarune_points115.json'), 'w',
                 encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    lines = [u'第115轮 · 交互点坐标（%d 间房 / %d 个点）' % (rooms_hit, tot_points), u'']
    kind_lab = {'door': u'门', 'warp': u'传送', 'marker': u'命名标记', 'save': u'存档点',
                'treasure': u'宝箱', 'readable': u'可读物', 'sign': u'招牌', 'other': u'其它'}
    lines.append(u'分类：' + u' · '.join(u'%s %d' % (kind_lab[k], by_kind[k])
                                       for k, _ in sorted(by_kind.items(), key=lambda kv: -kv[1])))
    for c in chapters:
        n = sum(len(r['points']) for r in c['rooms'])
        lines.append(u'')
        lines.append(u'ch%d：%d/%d 间有交互点，共 %d 个' % (c['ch'], len(c['rooms']),
                                                         c['rooms_total'], n))
        lines.append(u'     ' + u' · '.join(u'%s %d' % (kind_lab[k], v)
                                           for k, v in sorted(per_kind_ch[c['ch']].items(),
                                                              key=lambda kv: -kv[1])))
        for r in c['rooms'][:3]:
            sample = u'  '.join(u'%s(%d,%d)' % (p['obj'].replace('obj_', ''), p['x'], p['y'])
                                for p in r['points'][:4])
            lines.append(u'     %-28s %d 个  %s' % (r['name'], len(r['points']), sample))
    with io.open(os.path.join(EV, 'deltarune_points115.txt'), 'w',
                 encoding='utf-8', newline='\n') as f:
        f.write(u'\n'.join(lines) + u'\n')

    print(u'\n'.join(lines[:6]))
    print(u'\n落盘：deltarune_points115.json / deltarune_points115.txt')


if __name__ == '__main__':
    main()
