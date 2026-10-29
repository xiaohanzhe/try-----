# -*- coding: utf-8 -*-
"""单案取证：UT 的 room_ruins1 -> room_ruins2 到底怎么跳的。

只看 UT。做法：
1) conn_ut.json 里有没有 dst == room_ruins2 的边，谁写的；
2) room_ruins1 里摆了哪些 doorish 对象；
3) 这些对象的**全部**事件 code 名（从对象表取），看它们是否出现在 conn_ut 里。
只读，只打印。
"""
import collections
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
RAW = os.path.join(ROUND, '_evidence', 'raw', 'ut')

DOORISH = re.compile(r'door|stairs|stair|elevator|ladder|pipe|exit|entrance', re.I)


def main():
    conn = json.load(io.open(os.path.join(RAW, 'conn_ut.json'), encoding='utf-8'))
    names = conn['room_names']
    tgt = names.index('room_ruins2')
    src = names.index('room_ruins1')
    print('room_ruins1 = %d, room_ruins2 = %d' % (src, tgt))

    hit = [x for x in conn['items'] if x['dst'] == tgt]
    print('指向 room_ruins2 的边 %d 条:' % len(hit))
    for x in hit:
        print('   src=%-4d op=%-9s code=%s' % (x['src'], x['op'], x['code']))

    doors = []
    cur = None
    with io.open(os.path.join(RAW, 'inst_full.tsv'), encoding='utf-8') as f:
        for ln in f:
            ln = ln.rstrip('\n')
            if ln.startswith('R\t'):
                cur = int(ln.split('\t')[1])
            elif ln.startswith('I\t') and cur == src:
                q = ln.split('\t')
                if DOORISH.search(q[1]):
                    doors.append((q[1], q[2], q[3]))
    print('room_ruins1 的 doorish 实例 %d 个: %s' % (len(doors), doors))

    # 这些对象在 conn_ut 里出现过吗
    codes = set(x['code'] for x in conn['items'])
    for o, x, y in doors:
        rel = sorted(c for c in codes if ('_' + o + '_') in c)
        print('   对象 %-24s 相关换房 code: %s' % (o, rel or '无'))

    print('-' * 70)
    print('obj_doorA 的全部换房记录（前 40 条）:')
    for x in conn['items']:
        if 'obj_doorA_' in x['code']:
            print('   src=%-4d dst=%-4d op=%s' % (x['src'], x['dst'], x['op']))
    print('-' * 70)
    print('room_goto_next / previous 的记录:')
    for x in conn['items']:
        if x['op'] in ('room_goto_next', 'room_goto_previous'):
            print('   src=%-4d op=%-18s code=%s' % (x['src'], x['op'], x['code']))
    print('-' * 70)
    print('index+1 关系被已知边覆盖了多少：')
    known = set((x['src'], x['dst']) for x in conn['items']
                if x['src'] >= 0 and x['dst'] >= 0)
    seq = [(i, i + 1) for i in range(len(names) - 1)]
    hit = [p for p in seq if p in known]
    print('   相邻对 %d，已知边命中 %d = %.1f%%'
          % (len(seq), len(hit), 100.0 * len(hit) / len(seq)))
    print('   反方向（i+1 -> i）命中 %d'
          % len([p for p in seq if (p[1], p[0]) in known]))


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
