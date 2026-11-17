# -*- coding: utf-8 -*-
"""第196轮探针 8：**配色一致性** —— 抓"这张帧其实是别人 / 带纯色底"。

为什么 alpha 那套抓不到
------------------------
· `spr_susie_mad_face_up_0`（25×44）：几何完全正常（宽高、实心量都对），
  但画的是 **Kris**（深棕头发 + 浅蓝衣服）而不是 Susie（品红头发 + 紫外套）；
· `spr_susie_walk_left_candy_cane_surprise_0`（33×45）：旁边还有一个人、
  并且带一块**亮绿底色** —— 绿底只占一部分，所以 `opaque_ratio` 没到 0.85。

两者都能用"配色"量出来：同一个角色的像素画，主色是稳定的。
  ① 从该角色**走路帧**取调色板（量化到 5bit/通道，取出现次数前 N 个）；
  ② 候选帧里属于该调色板的像素占比 = `share`；
  ③ `share` 太低 ⇒ 不是这个人 / 掺了纯色底。

★ 本脚本只测量、给分布，阈值另定（不许拍脑袋）。
"""
from __future__ import print_function

import io
import json
import os
import sys
from collections import Counter

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
DROP = os.path.join(ROOT, 'ralsei_pet', 'assets', 'sprites', 'dr')
EVID = os.path.join(ROUND, '_evidence')
ALPHA_MIN = 32
BITS = 5
TOPN = 24


def q(rgb):
    m = (1 << (8 - BITS)) - 1
    return (rgb[0] & ~m, rgb[1] & ~m, rgb[2] & ~m)


def colors(path):
    im = Image.open(path)
    im.load()
    im = im.convert('RGBA')
    px = im.load()
    out = []
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if a > ALPHA_MIN:
                out.append(q((r, g, b)))
    return out


def palette(paths):
    c = Counter()
    for p in paths:
        c.update(colors(p))
    return set(k for k, _ in c.most_common(TOPN)), c


def share(pal, cs):
    if not cs:
        return 0.0
    hit = sum(1 for c in cs if c in pal)
    return hit / float(len(cs))


def main():
    with io.open(os.path.join(DROP, '_npc_frames.json'), 'r', encoding='utf-8') as f:
        fr_man = json.load(f).get('characters') or {}
    with io.open(os.path.join(DROP, '_npc_anims.json'), 'r', encoding='utf-8') as f:
        an_man = json.load(f).get('characters') or {}

    base_pal = {}
    for cid, e in fr_man.items():
        fr = (e or {}).get('frames') or {}
        d = 'down' if 'down' in fr else (sorted(fr)[0] if fr else None)
        if not d:
            continue
        paths = [os.path.join(DROP, cid, r['f']) for r in fr[d][:4]]
        paths = [p for p in paths if os.path.isfile(p)]
        if paths:
            pal, cnt = palette(paths)
            base_pal[cid] = (pal, cnt)

    print('=' * 92)
    print('逐角色：候选帧的"配色占比" share（越接近 1 越像本人）')
    print('=' * 92)
    rows = []
    for cid in sorted(an_man):
        if cid not in base_pal:
            continue
        pal, _cnt = base_pal[cid]
        print('\n### %s  调色板大小 %d' % (cid, len(pal)))
        for emo in sorted(an_man[cid]):
            for dd in sorted(an_man[cid][emo]):
                for i, row in enumerate(an_man[cid][emo][dd]):
                    p = os.path.join(DROP, cid, row['f'])
                    cs = colors(p)
                    s = share(pal, cs)
                    rows.append((s, cid, emo, dd, i, row['src_name']))
                    flag = '★低' if s < 0.70 else ''
                    print('    %-10s %-6s[%d] share=%-5s n=%-4d %-44s %s'
                          % (emo, dd, i, round(s, 3), len(cs),
                             row['src_name'][:42], flag))

    print('\n' + '=' * 92)
    print('按 share 升序（最可疑的排前面）')
    print('=' * 92)
    for s, cid, emo, dd, i, fn in sorted(rows)[:25]:
        print('  %-6s %-12s %-10s %-6s[%d] %s' % (round(s, 3), cid, emo, dd, i, fn))
    print('\n合计 %d 帧；share<0.70 的 %d 帧；share<0.55 的 %d 帧'
          % (len(rows), sum(1 for r in rows if r[0] < 0.70),
             sum(1 for r in rows if r[0] < 0.55)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
