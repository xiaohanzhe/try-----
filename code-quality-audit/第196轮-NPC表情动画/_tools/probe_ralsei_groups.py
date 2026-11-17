# -*- coding: utf-8 -*-
"""第196轮探针 5：Ralsei 自己的 115 组动画**全量列一遍**。

目的：确定「模板」到底长什么样。要把模板复制给每个 NPC，先得知道模板里
有哪些"情绪动作组"，以及 NPC 侧有没有同义词可对应（否则会出现
"Ralsei 会生气、别人不会"的对等问题）。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
ANIM = os.path.join(REPO, 'ralsei_pet', 'assets', 'animations.json')

EMO = r'laugh|cry|sad|surpris|shock|angry|mad|happy|smile|hurt|tired|sleep|annoy|exasperat|upset|worried|nervous|scared|afraid|blush'


def main():
    with io.open(ANIM, 'r', encoding='utf-8') as f:
        d = json.load(f)
    g = d.get('groups') or {}
    print('=' * 78)
    print('Ralsei animations.json')
    print('=' * 78)
    print('顶层键：%s' % sorted(d.keys()))
    print('meta  ：%s' % json.dumps(d.get('meta') or {}, ensure_ascii=False)[:400])
    print('groups：%d 组\n' % len(g))

    print('-' * 78)
    print('全部组名（按字母序）')
    print('-' * 78)
    names = sorted(g.keys())
    for i in range(0, len(names), 4):
        print('  ' + '  '.join('%-22s' % n for n in names[i:i + 4]))

    print('\n' + '-' * 78)
    print('情绪相关组')
    print('-' * 78)
    hits = [n for n in names if re.search(EMO, n, re.I)]
    for n in hits:
        v = g[n]
        nf = len(v.get('frames') or []) if isinstance(v, dict) else '?'
        print('  %-26s frames=%-3s %s' % (
            n, nf, json.dumps(v, ensure_ascii=False)[:150]))

    print('\n' + '-' * 78)
    print('单组结构（`laugh` 全文前 600 字）')
    print('-' * 78)
    print(json.dumps(g.get('laugh'), ensure_ascii=False, indent=1)[:900])

    print('\n' + '-' * 78)
    print('每组用了哪个目录/前缀（判断是否只有 Ralsei 一人）')
    print('-' * 78)
    from collections import Counter
    c = Counter()
    for n, v in g.items():
        for fr in ((v or {}).get('frames') or [])[:1]:
            s = json.dumps(fr)
            m = re.search(r'([\w/\\.-]+\.png)', s)
            c[os.path.basename(m.group(1)) if m else '?'] += 1
    for k, n in c.most_common(12):
        print('  %-45s %d' % (k, n))
    return 0


if __name__ == '__main__':
    sys.exit(main())
