# -*- coding: utf-8 -*-
u"""背景图对账（第三版）：仓库 `bg/oneshot_map*.png` 和「tmx 各层 + 底色」到底差多少。

★ 这一版是**被负控制逼出来的**。前两版都栽了：
  · 第一版直接比逐层渲染 ⇒ 109 间被判"不一致"，其实只是**缺一层底色**。
  · 第二版补上底色后，用「两边 alpha>0 的像素集合」当几何判据 ⇒ **恒真**：
    底色不透明，合成后整张图 alpha 全 255 ⇒ `仅PNG / 仅我` 永远是 0。
    **是被 `negcontrol()`（把渲染右移 16px 必须报红）抓出来的**，否则会把
    "263/263 几何完全一致"当成结论写进报告。
  ⇒ 现在只用**逐像素 RGB 差异率**，并且带上错位负控制来证明这个尺子看得见错位。

指标：
  mismatch  = |Δ|>2 的像素 / 全画布像素（0 = 逐像素相同）
  semi_share= 差异像素里「我的 alpha < 255」的占比（越高越说明差异在半透明瓦片上）
  shift16   = 把渲染右移 16px（正好一格）后的 mismatch ⇒ 负控制，必须明显变大
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import oneshot_tmx as T

try:
    from PIL import Image
    import numpy as np
except ImportError:                              # pragma: no cover
    Image = None

ROUND = os.path.normpath(os.path.join(HERE, '..'))
REPO = os.path.normpath(os.path.join(ROUND, '..', '..'))
BG = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes', 'bg')
MINE = 'D:/_tmp/render_all'
TOL = 2

# `oneshot_map_colors.json` 是**带尾逗号的 JS 对象**，`json.load` 直接抛（第59轮踩过同款）
_TRAIL = re.compile(r',(\s*[}\]])')


def load_colors():
    p = os.path.join(T.GD, 'oneshot_map_colors.json')
    raw = io.open(p, encoding='utf-8', newline='').read()
    d = json.loads(_TRAIL.sub(r'\1', raw))
    out = {}
    for g in d.get('mapColors') or []:
        c = g.get('color') or {}
        rgba = (int(c.get('r', 0)), int(c.get('g', 0)), int(c.get('b', 0)),
                int(c.get('a', 255)))
        for m in g.get('maps') or []:
            out[int(m)] = (g.get('name'), rgba)
    return out


def _pair(num, colors):
    p = os.path.join(BG, 'oneshot_map%d.png' % num)
    q = os.path.join(MINE, 'map%d.png' % num)
    if not (os.path.isfile(p) and os.path.isfile(q)):
        return None
    A = np.asarray(Image.open(p).convert('RGBA'))
    B = Image.open(q).convert('RGBA')
    if A.shape[:2] != (B.size[1], B.size[0]):
        return None
    base = Image.new('RGBA', B.size, colors.get(num, (None, (0, 0, 0, 255)))[1])
    C = np.asarray(Image.alpha_composite(base, B))
    return A, B, C


def _mismatch(A, C, al):
    d = np.abs(A[:, :, :3].astype(np.int16) - C[:, :, :3].astype(np.int16)).max(axis=2)
    bad = d > TOL
    n = bad.size
    semi = int((bad & (al < 255)).sum())
    return {'mismatch': float(bad.sum()) / n, 'semi_share': (semi / float(bad.sum())) if bad.sum() else 1.0}


def cmp_one(num, colors):
    got = _pair(num, colors)
    if got is None:
        return None
    A, B, C = got
    al = np.asarray(B)[:, :, 3]
    r = {'map': num, 'group': colors.get(num, (None,))[0]}
    r.update(_mismatch(A, C, al))
    return r


def shift_mismatch(num, colors, dx=16):
    u"""负控制：同一对图，把渲染右移一格再比 —— 判据必须报出大得多的差异。"""
    got = _pair(num, colors)
    if got is None:
        return None
    A, B, _ = got
    sh = Image.new('RGBA', B.size, (0, 0, 0, 0))
    sh.alpha_composite(B, (dx, 0))
    base = Image.new('RGBA', B.size, colors.get(num, (None, (0, 0, 0, 255)))[1])
    C2 = np.asarray(Image.alpha_composite(base, sh))
    al = np.asarray(B)[:, :, 3]
    return _mismatch(A, C2, al)['mismatch']


def main(argv):
    if Image is None:
        print(u'需要 Pillow + numpy')
        return 2
    colors = load_colors()
    print(u'底色表：%d 个 map 有分组' % len(colors))
    nums = [int(x) for x in argv if x.strip()] or list(range(1, 264))
    rows = [r for r in (cmp_one(n, colors) for n in nums) if r]
    rows.sort(key=lambda r: -r['mismatch'])
    ok = [r for r in rows if r['mismatch'] <= 0.01]
    print(u'比对 %d 间：逐像素差异 ≤1%% 的 %d 间；>1%% 的 %d 间' % (len(rows), len(ok), len(rows) - len(ok)))
    if len(rows) - len(ok):
        print(u'差异最大的 12 间（semi=差异像素里半透明占比）：')
        for r in rows[:12]:
            print(u'   map%-4d mismatch=%.4f semi=%.3f 底色=%s'
                  % (r['map'], r['mismatch'], r['semi_share'], r['group']))
    print(u'mismatch 中位 %.4f｜均值 %.4f'
          % (sorted(r['mismatch'] for r in rows)[len(rows) // 2],
             sum(r['mismatch'] for r in rows) / len(rows)))

    # ---- 负控制：正确对齐 vs 右移一格 ----
    # ★ 判据先写成"右移后差异 >5 倍"，实测 map200/244 只有 3.0~3.2 倍 —— 但它们的**绝对值**
    #   从 0.077→0.231、0.125→0.400，错位已经一目了然。倍数低只是因为"正确对齐"本身
    #   就有 7~12% 的半透明混合差。⇒ 改成「绝对增量 ≥0.05 **且** ≥2 倍」：
    #   一个整格错位必然同时满足两者，而"判据看不见错位"时增量为 0 ⇒ 仍会被抓。
    ctrl = []
    for n in (4, 200, 244, 85):
        a = cmp_one(n, colors)
        b = shift_mismatch(n, colors)
        if a and b is not None:
            good = (b - a['mismatch'] >= 0.05) and (b >= a['mismatch'] * 2)
            ctrl.append((n, a['mismatch'], b, good))
    for n, base_m, sh_m, good in ctrl:
        print(u'[%s] 负控制 map%-4d 正确对齐 %.4f → 右移一格 %.4f'
              % ('PASS' if good else 'FAIL', n, base_m, sh_m))
    all_good = all(c[3] for c in ctrl)
    print(u'[%s] 负控制合计：%s'
          % ('PASS' if all_good else 'FAIL',
             u'判据看得见错位（4/4）' if all_good else u'判据太钝，数不可信'))
    if argv:
        p = os.path.join(ROUND, '_evidence', 'bg_composite114.json')
        with io.open(p, 'w', encoding='utf-8', newline='\n') as f:
            f.write(json.dumps(rows, ensure_ascii=False, indent=1))
        print(u'明细 → %s' % p)
    return 0 if all_good else 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))
