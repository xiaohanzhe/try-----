# -*- coding: utf-8 -*-
u"""重验「`assets/scenes/bg/oneshot_map*.png` 与 tmx 不一致」这条结论（第114轮）。

★ 为什么必须重验：那批 PNG 是**第100/101轮从同一份 tmx 合成**的，说它 30.4% 不一致
  等于说那两轮白干。这种"推翻前轮"的结论必须先排除自己的夹具问题 —— 之前已经栽过
  「夹具不保真＝报假问题」和「背景移动是相机平移不是视差」（第102轮归因更正）。

判据（三层，逐层收紧）：
  L1 尺寸：PNG 尺寸 == tmx 宽高 × 16（不是就说明连画布都不对，先看这一层）
  L2 覆盖率：我的渲染 vs PNG，两边"非透明"像素集合的重合度（IoU）
  L3 逐像素：RGB 完全相同的像素占比（只在两边都非透明的像素里算）

★ L2/L3 都用「双非透明」做分母，避免透明区域把数字灌水（透明 vs 透明本来就算"一样"，
  那样 23 间空房会白送 100%）。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import oneshot_tmx as T

try:
    from PIL import Image
    import numpy as np
except ImportError:                              # pragma: no cover
    Image = None
    np = None

ROUND = os.path.normpath(os.path.join(HERE, '..'))
REPO = os.path.normpath(os.path.join(ROUND, '..', '..'))
BG = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes', 'bg')
MINE = 'D:/_tmp/render_all'


def stat_one(num):
    p = os.path.join(BG, 'oneshot_map%d.png' % num)
    q = os.path.join(MINE, 'map%d.png' % num)
    out = {'map': num, 'png': os.path.isfile(p), 'mine': os.path.isfile(q)}
    m = T.load_map(num)
    out['tmx'] = (m['W'] * m['TW'], m['H'] * m['TH'])
    if not out['png']:
        return out
    a = Image.open(p).convert('RGBA')
    out['size'] = a.size
    out['size_ok'] = (a.size == out['tmx'])
    if not out['mine']:
        return out
    b = Image.open(q).convert('RGBA')
    if b.size != a.size:
        return out
    A = np.asarray(a)
    B = np.asarray(b)
    na = A[:, :, 3] > 0
    nb = B[:, :, 3] > 0
    both = int((na & nb).sum())
    only_a = int((na & ~nb).sum())
    only_b = int((~na & nb).sum())
    same = int(((A[:, :, :3] == B[:, :, :3]).all(axis=2) & na & nb).sum())
    out.update({'both': both, 'only_png': only_a, 'only_mine': only_b,
                'same': same,
                'iou': (both / float(both + only_a + only_b)) if (both + only_a + only_b) else 1.0,
                'rgb_eq': (same / float(both)) if both else 1.0,
                # ★ PNG 多出来的像素里有多少是"渲染成透明但 PNG 有底色"（`oneshot_map_colors.json`
                #   的底色层）。把它单列出来，否则空房（blank.tsx）会被判成"完全不同"。
                'png_only_ratio': (only_a / float(na.sum())) if na.sum() else 0.0})
    return out


def main(argv):
    if Image is None:
        print(u'需要 Pillow')
        return 2
    nums = [int(x) for x in argv if x.strip()] or list(range(1, 264))
    rows = [stat_one(n) for n in nums]
    bad_size = [r for r in rows if r.get('png') and not r.get('size_ok')]
    print(u'房间 %d 间：有 PNG %d，尺寸不符 %d'
          % (len(rows), sum(1 for r in rows if r.get('png')), len(bad_size)))
    for r in bad_size[:10]:
        print(u'   map%-4d png=%s tmx=%s' % (r['map'], r.get('size'), r['tmx']))
    cmp = [r for r in rows if 'iou' in r]
    if not cmp:
        print(u'!! 没有可逐像素比对的房间（渲染图缺失？）')
        return 1
    cmp.sort(key=lambda r: r['iou'])
    print(u'\n可逐像素比对 %d 间。IoU 最低的 8 间：' % len(cmp))
    for r in cmp[:8]:
        print(u'   map%-4d IoU=%.3f RGB同=%.3f  两边都有=%d 仅PNG=%d 仅渲染=%d'
              % (r['map'], r['iou'], r['rgb_eq'], r['both'], r['only_png'],
                 r['only_mine']))
    print(u'IoU 最高的 5 间：')
    for r in cmp[-5:]:
        print(u'   map%-4d IoU=%.3f RGB同=%.3f' % (r['map'], r['iou'], r['rgb_eq']))
    good = [r for r in cmp if r['iou'] >= 0.95]
    mid = [r for r in cmp if 0.6 <= r['iou'] < 0.95]
    low = [r for r in cmp if r['iou'] < 0.6]
    print(u'\n分档：IoU>=0.95 完全一致(可用于核对) %d 间｜0.6~0.95 偏差 %d 间｜<0.6 明显不同 %d 间'
          % (len(good), len(mid), len(low)))
    print(u'<0.6 的：%s' % [r['map'] for r in low][:40])
    if argv:
        p = os.path.join(ROUND, '_evidence', 'bg_vs_tmx114.json')
        with io.open(p, 'w', encoding='utf-8', newline='\n') as f:
            f.write(json.dumps(rows, ensure_ascii=False, indent=1))
        print(u'明细 → %s' % p)
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))
