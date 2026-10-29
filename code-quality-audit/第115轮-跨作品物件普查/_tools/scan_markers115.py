# -*- coding: utf-8 -*-
u"""扫一遍 `_readable_text.json` 的正文里到底有哪些非常规字符。

动手写解码器之前先量：如果正文里只出现 `% & / ^`，那解码器就只处理这四类；
若还出现 `\\`（颜色/音效）、`>`（选项定位）、`*`（图标）等，必须一并覆盖，
否则"解完还剩一堆控制符"会在界面上直接暴露。

输出：每类标记的出现次数 + 词表（前若干条，带上下文）
"""
import collections
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.dirname(HERE)                       # 第115轮-…
ROOT = os.path.dirname(os.path.dirname(ROUND))      # 仓库根（try - 副本）
ASSET = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', '_readable_text.json')


def main():
    doc = json.loads(io.open(ASSET, encoding='utf-8').read())
    by_scene = doc.get('by_scene') or {}
    if not by_scene:
        print('[FAIL] by_scene 为空 —— 没东西可扫')
        return 1

    cnt = collections.Counter()
    ctx = collections.defaultdict(list)
    total = 0
    for sid, entries in by_scene.items():
        for e in entries:
            for field in ('cn_tight', 'cn', 'en', 'ja'):
                t = e.get(field)
                if not t:
                    continue
                total += 1
                for i, ch in enumerate(t):
                    if ch in u'%&/^\\>*':
                        cnt[ch] += 1
                        if len(ctx[ch]) < 6:
                            lo = max(0, i - 12)
                            hi = min(len(t), i + 13)
                            ctx[ch].append(t[lo:hi].replace(u'\n', u'\\n'))
                # ^N 里的数字也算（只统计形态）
    print('正文字段总数 = %d（场景 %d）' % (total, len(by_scene)))
    print('')
    for ch, n in cnt.most_common():
        print('  %-3r %6d 次' % (ch, n))
        for s in ctx[ch][:3]:
            print('         … %s …' % s)
    print('')
    if not cnt:
        print('[FAIL] 一个标记都没数到 —— 要么资产里真没有，要么字段名变了')
        return 1
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
