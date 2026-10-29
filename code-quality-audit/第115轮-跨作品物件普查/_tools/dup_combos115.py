# -*- coding: utf-8 -*-
u"""查 `_readable_text.json` 里「同一 (场景, 对象) 有多条」到底有多少 —— 决定查找语义。

如果一条都没有，查找就是简单的 dict[scene][obj]；
如果有一批，就必须在代码里明确"取哪一条"，否则是静默随机。
"""
import collections
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(ROUND))
ASSET = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', '_readable_text.json')


def main():
    doc = json.loads(io.open(ASSET, encoding='utf-8').read())
    by_scene = doc.get('by_scene') or {}
    combos = collections.Counter()
    for sid, entries in by_scene.items():
        for e in entries:
            combos[(sid, e.get('obj'))] += 1
    dup = {k: v for k, v in combos.items() if v > 1}
    print('组合总数 = %d，其中重复 = %d' % (len(combos), len(dup)))
    for k, v in list(dup.items())[:10]:
        print('   %s / %s  ×%d' % (k[0], k[1], v))
    print('')
    # 顺带：每个场景的条目数分布
    dist = collections.Counter(len(v) for v in by_scene.values())
    print('每场景条目数分布（条目数: 场景数）= %s' % dict(sorted(dist.items())))
    if not combos:
        print('[FAIL] 组合为空 —— 资产没被正确读取')
        return 1
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
