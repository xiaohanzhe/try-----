# -*- coding: utf-8 -*-
u"""UT / UTY / Outertale 全量实例坐标的摘要（读 raw/，写 _evidence/cross_works115.txt）。

只读 raw/{ut,uty,outertale}/inst_full.tsv，不碰游戏目录、不碰临时盘。
判据不在这里下（在 check_ut115.py），这里只做汇总。
"""
import collections
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
RAW = os.path.join(ROUND, '_evidence', 'raw')
OUT = os.path.join(ROUND, '_evidence', 'cross_works115.txt')

WORKS = [
    ('ut', u'Undertale', u'room_*，门为 obj_doorA~D（详版 §87.11）'),
    ('uty', u'Undertale Yellow', u'rm_*，门为 obj_doorway / obj_exit / obj_door（详版 §87.11）'),
    ('outertale', u'Outertale', u'首次测定，无历史登记'),
]


def parse(key):
    p = os.path.join(RAW, key, 'inst_full.tsv')
    rooms, insts = [], []
    if not os.path.isfile(p):
        return rooms, insts
    cur = None
    with io.open(p, encoding='utf-8') as f:
        for ln in f:
            ln = ln.rstrip('\n')
            if ln.startswith('R\t'):
                q = ln.split('\t')
                cur = {'name': q[2], 'w': int(q[3]), 'h': int(q[4]), 'n': int(q[6]), 'go': int(q[7])}
                rooms.append(cur)
            elif ln.startswith('I\t'):
                q = ln.split('\t')
                insts.append({'room': cur['name'], 'obj': q[1],
                              'x': float(q[2]), 'y': float(q[3]),
                              'sx': float(q[4]), 'sy': float(q[5]),
                              'rot': float(q[6]), 'depth': int(q[9]), 'layer': q[10]})
    return rooms, insts


def main():
    L = []
    L.append(u'第115轮 · 跨作品实例坐标（UT / UTY / Outertale）')
    L.append(u'')
    tot_r = tot_i = 0
    per = {}
    for key, title, note in WORKS:
        rooms, insts = parse(key)
        per[key] = (rooms, insts)
        tot_r += len(rooms)
        tot_i += len(insts)
    L.append(u'合计 %d 间房 / %d 个实例（三款）' % (tot_r, tot_i))
    L.append(u'')
    for key, title, note in WORKS:
        rooms, insts = per[key]
        objs = collections.Counter(i['obj'] for i in insts if i['obj'])
        scaled = sum(1 for i in insts if abs(i['sx'] - 1.0) > 1e-9 or abs(i['sy'] - 1.0) > 1e-9)
        rots = sum(1 for i in insts if abs(i['rot']) > 1e-9)
        L.append(u'%s（%s）：%d 间 / %d 实例 / %d 个不同对象'
                 u'（带非 1 缩放的 %d 个、带旋转的 %d 个）'
                 % (title, note, len(rooms), len(insts), len(objs), scaled, rots))
    L.append(u'')

    for key, title, note in WORKS:
        rooms, insts = per[key]
        L.append(u'--- %s 明细 ---' % title)
        objs = collections.Counter(i['obj'] for i in insts if i['obj'])
        rooms_of = collections.defaultdict(set)
        for i in insts:
            if i['obj']:
                rooms_of[i['obj']].add(i['room'])
        L.append(u'实例最多的 10 个：')
        for name, n in objs.most_common(10):
            xs = [i['x'] for i in insts if i['obj'] == name]
            ys = [i['y'] for i in insts if i['obj'] == name]
            L.append(u'  %-34s inst=%-5d rooms=%-5d x[%g..%g] y[%g..%g]'
                     % (name, n, len(rooms_of[name]), min(xs), max(xs), min(ys), max(ys)))
        pre = collections.Counter()
        for r in rooms:
            nm = r['name']
            pre[nm.split('_')[0] + '_' if '_' in nm else '(无下划线)'] += 1
        L.append(u'房间名前缀：' + u'  '.join(u'%s=%d' % kv for kv in pre.most_common(6)))
        # 空对象名 / 空层名
        empty_obj = sum(1 for i in insts if not i['obj'])
        empty_layer = sum(1 for i in insts if not i['layer'])
        L.append(u'空对象名实例 %d 个 / 空层名实例 %d 个' % (empty_obj, empty_layer))
        # 层类型分布
        lay = collections.Counter(i['layer'] for i in insts)
        L.append(u'层名 top5：' + u'  '.join(u'%s(%d)' % kv for kv in lay.most_common(5)))
        L.append(u'')

    # UTY 已知差异
    rooms, insts = per['uty']
    hit = [r for r in rooms if r['n'] != r['go']]
    L.append(u'已知差异（已在 check_ut115.py U4b 白名单登记）：')
    if hit:
        for r in hit:
            L.append(u'  uty / %s：层内实例 %d，引擎 GameObjects %d（老格式房间，有 1 个实例没挂层）'
                     % (r['name'], r['n'], r['go']))
    else:
        L.append(u'  无')
    L.append(u'')
    L.append(u'复现：python _tools/run_dump_ut.py（要 UTMT + 三份 game.droid）'
             u' → python _tools/cross_works115.py → python _tools/check_ut115.py')

    txt = u'\n'.join(L) + u'\n'
    with io.open(OUT, 'w', encoding='utf-8', newline='') as f:
        f.write(txt)
    print(u'[PASS] 写出 %s  %d 字符 / %d 行' % (OUT, len(txt), len(L)))
    print(txt[:1200])


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
