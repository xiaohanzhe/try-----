# -*- coding: utf-8 -*-
u"""列出「解码后为空」和「被判为重复」的条目 —— 确认丢掉的都是该丢的。

335 保留 / 355 原始，差的 20 条必须有账：是重复（第二层守卫未解），
还是解完真的什么都没剩（例如正文只有 `/%%`）。
"""
import collections
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(ROUND))
PET = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, os.path.join(PET, 'modules'))
import item_interact as II                                   # noqa: E402

ASSET = os.path.join(PET, 'assets', 'scenes', '_readable_text.json')


def main():
    doc = json.loads(io.open(ASSET, encoding='utf-8').read())
    empty, dup = [], []
    seen = collections.Counter()
    for sid, entries in (doc.get('by_scene') or {}).items():
        for e in entries:
            obj = e.get('obj')
            raw = (e.get('cn_tight') or e.get('cn') or e.get('en') or e.get('ja'))
            txt = II.decode_readable(raw)
            key = (sid, obj)
            if not txt:
                empty.append((sid, obj, e.get('key'), raw))
            elif seen[key]:
                dup.append((sid, obj, e.get('key')))
            seen[key] += 1
    print('解完为空 = %d' % len(empty))
    for r in empty:
        print('   %s / %s / %s\n        raw=%r' % r)
    print('')
    print('判为重复（只留第一条）= %d' % len(dup))
    for r in dup:
        print('   %s / %s / %s' % r)
    print('')
    print('账目：%d(空) + %d(重复) + 335(保留) = %d（原始 %d）'
          % (len(empty), len(dup), len(empty) + len(dup) + 335,
             sum(len(v) for v in (doc.get('by_scene') or {}).values())))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
