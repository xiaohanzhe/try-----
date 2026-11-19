# -*- coding: utf-8 -*-
"""第200轮 · 只读探测：OneShot（os_*）素材到底是"单张立绘"还是"格子表"。

判据：在**非透明包围盒**内部，找"整列/整行全透明"的缝隙 ⇒ 缝隙把图切成格。
★ 这一步是"客观量"，不是猜：只有真正全透明的行列才算缝，所以精灵画到边界上
  的情况不会被误切。
"""
from __future__ import print_function

import io
import json
import os
import sys

from PIL import Image

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
SPR = os.path.join(ROOT, 'ralsei_pet', 'assets', 'sprites')
PLAN = os.path.join(ROUND, '_evidence', 'sheet_plan.json')
OUT = os.path.join(ROUND, '_evidence', 'grid200.json')


def runs(flags):
    """把 [True,True,False,...] 切成连续 True 的区间列表 [(a,b)]（b 含）。"""
    out, a = [], None
    for i, v in enumerate(flags):
        if v and a is None:
            a = i
        elif not v and a is not None:
            out.append((a, i - 1))
            a = None
    if a is not None:
        out.append((a, len(flags) - 1))
    return out


def analyze(p):
    im = Image.open(p).convert('RGBA')
    a = im.split()[3]
    w, h = im.size
    # 包围盒
    bb = a.getbbox()
    if not bb:
        return {'size': [w, h], 'empty': True}
    x0, y0, x1, y1 = bb
    px = a.load()
    cols = [any(px[x, y] for y in range(y0, y1)) for x in range(x0, x1)]
    rows = [any(px[x, y] for x in range(x0, x1)) for y in range(y0, y1)]
    cx = [(a + x0, b + x0) for a, b in runs(cols)]
    ry = [(a + y0, b + y0) for a, b in runs(rows)]
    return {'size': [w, h], 'bbox': list(bb), 'cols': len(cx), 'rows': len(ry),
            'col_w': sorted(set(b - a + 1 for a, b in cx)),
            'row_h': sorted(set(b - a + 1 for a, b in ry)),
            'col_spans': cx, 'row_spans': ry}


def main():
    plan = json.loads(io.open(PLAN, encoding='utf-8').read())
    res = {}
    for it in plan:
        if not it['id'].startswith('os_'):
            continue
        for fn in it['files']:
            p = os.path.join(SPR, it['work'], fn)
            if os.path.isfile(p):
                res[it['id'] + '/' + fn] = analyze(p)
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(res, ensure_ascii=False, indent=1))
    print('%-30s %-10s %-9s %-5s %-5s %s' % ('文件', 'canvas', 'bbox', '列', '行', '格宽/格高'))
    for k, v in sorted(res.items()):
        if v.get('empty'):
            print('%-30s %-10s %s' % (k, 'x'.join(map(str, v['size'])), '全透明'))
            continue
        print('%-30s %-10s %-9s %-5d %-5d %s / %s'
              % (k, 'x'.join(map(str, v['size'])),
                 '%dx%d' % (v['bbox'][2] - v['bbox'][0], v['bbox'][3] - v['bbox'][1]),
                 v['cols'], v['rows'], v['col_w'], v['row_h']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
