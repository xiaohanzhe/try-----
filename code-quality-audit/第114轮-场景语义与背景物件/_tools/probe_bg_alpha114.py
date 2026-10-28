# -*- coding: utf-8 -*-
u"""诊断：合成底色后剩下的 RGB 差异，是「alpha 合成算法不同」还是「真画错了」。"""
import collections
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bg_base114 as BASEC
import oneshot_tmx as T
from PIL import Image
import numpy as np

ROUND = os.path.normpath(os.path.join(HERE, '..'))
REPO = os.path.normpath(os.path.join(ROUND, '..', '..'))
BG = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes', 'bg')


def main(argv):
    num = int(argv[0]) if argv else 200
    colors = BASEC.load_colors()
    name, rgba = colors.get(num, (None, (0, 0, 0, 255)))
    A = np.asarray(Image.open(os.path.join(BG, 'oneshot_map%d.png' % num))
                   .convert('RGBA')).astype(np.int16)
    B = np.asarray(Image.open('D:/_tmp/render_all/map%d.png' % num).convert('RGBA'))
    base = Image.new('RGBA', (B.shape[1], B.shape[0]), rgba)
    C = np.asarray(Image.alpha_composite(base, Image.fromarray(B))).astype(np.int16)
    d = np.abs(A[:, :, :3] - C[:, :, :3]).max(axis=2)
    al = B[:, :, 3]
    print(u'map%d 底色=%s%s' % (num, name, rgba))
    print(u'|Δ| 分布：0=%d 1~2=%d 3~8=%d 9~32=%d >32=%d'
          % ((d == 0).sum(), ((d >= 1) & (d <= 2)).sum(),
             ((d >= 3) & (d <= 8)).sum(), ((d >= 9) & (d <= 32)).sum(),
             (d > 32).sum()))
    bad = d > 2
    print(u'差异像素的「我的 alpha」分布：')
    h = collections.Counter()
    for v in al[bad].tolist():
        h['255' if v == 255 else ('0' if v == 0 else '1~254')] += 1
    print(u'   %s' % dict(h))
    print(u'全图 alpha 分布：a=255 %d，a=0 %d，中间 %d'
          % ((al == 255).sum(), (al == 0).sum(),
             ((al > 0) & (al < 255)).sum()))
    ys, xs = np.where(bad)
    print(u'差异像素 bbox: x %d~%d  y %d~%d' % (xs.min(), xs.max(), ys.min(), ys.max()))
    print(u'\n前 10 个差异点（x,y）PNG=(r,g,b,a) 我合成=(r,g,b) 我的原alpha：')
    for i in range(0, min(len(xs), 4000), 400):
        x, y = int(xs[i]), int(ys[i])
        print(u'   (%4d,%4d) PNG=%s  我=%s  alpha=%d'
              % (x, y, tuple(A[y, x]), tuple(C[y, x][:3]), al[y, x]))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))
