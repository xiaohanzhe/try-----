# -*- coding: utf-8 -*-
u"""把含某个子串的正文条目原样打出来（排查用，默认子串是 `\\[C]`）。

用途：判断"这个占位到底长什么样、原文语境是什么"，再决定解码器该怎么处理，
而不是照着残片猜。
"""
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(ROUND))
ASSET = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', '_readable_text.json')


def main(argv):
    needle = argv[0] if argv else u'\\[C]'
    doc = json.loads(io.open(ASSET, encoding='utf-8').read())
    n = 0
    for sid, entries in (doc.get('by_scene') or {}).items():
        for e in entries:
            for f in ('cn_tight', 'cn', 'en', 'ja'):
                t = e.get(f)
                if t and needle in t:
                    n += 1
                    print('%s / %s / %s' % (sid, e.get('obj'), e.get('key')))
                    print('    %-8s %r' % (f, t))
    print('')
    print('命中 %d 个字段' % n)
    if not n:
        print('[WARN] 一个都没有 —— 子串给错了')
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))
