# -*- coding: utf-8 -*-
u"""probe103d.py —— 第103轮侦察 4：**用透明度剖面客观找出真实网格**（不再靠肉眼猜）。

原理
----
如果一张图集真的是"N×M 个格的拼板"，那么格与格之间（多半）有**全透明的缝**：
  · 沿 x 的 alpha 列和会在缝处掉到 0 ⇒ 切出列数
  · 沿 y 的 alpha 行和会在缝处掉到 0 ⇒ 切出行数
这不是猜测，是**像素事实**。

对每张图集输出：
  - x 向零列区间 / y 向零行区间
  - 由此推得的 **列数 / 行数**
  - 与候选规则对照：A(w/4 × h/4) / B(w/3 × h/4) / D(1×1 整张) / E(1×4 竖四条) …
"""
import collections
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image                                              # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
PROPS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'oneshot_props')


def segs(profile):
    u"""把 [v0..vn] 中**恒为 0** 的连续区间切出来（缝），返回 [(start, end)]（左闭右开）。"""
    out, s = [], None
    for i, v in enumerate(profile):
        if v == 0:
            if s is None:
                s = i
        else:
            if s is not None:
                out.append((s, i))
                s = None
    if s is not None:
        out.append((s, len(profile)))
    return out


def axis_report(prof, n):
    u"""零区间 -> (缝数, 由缝推得的「块」数, 缝外的块边界)。"""
    z = segs(prof)
    inner = [s for s in z if s[0] > 0 and s[1] < n]        # 排除整张全透明 / 贴边的
    blocks = [0] + [e for _s, e in inner] + [n]
    edges = sorted({0, n} | {v for s in inner for v in s})
    return z, inner, edges


names = sorted(f[:-4] for f in os.listdir(PROPS) if f.endswith('.png'))
ING = json.load(io.open(os.path.join(
    ROOT, 'code-quality-audit', '第102轮-光照与ambient接入', '_evidence',
    'ingest102.json'), encoding='utf-8'))
SIZES = {f['name']: (f['w'], f['h']) for f in ING['files']}

rows = []
print('=' * 100)
print('alpha 剖面找缝（只列「有缝」的；全无缝 = 整块无缝拼板）')
print('=' * 100)
n_cols_hist = collections.Counter()
n_rows_hist = collections.Counter()
for nm in names:
    p = os.path.join(PROPS, nm + '.png')
    im = Image.open(p).convert('RGBA')
    w, h = im.size
    a = im.getchannel('A')
    colp = [sum(a.crop((x, 0, x + 1, h)).getdata()) for x in range(w)]
    rowp = [sum(a.crop((0, y, w, y + 1)).getdata()) for y in range(h)]
    zx, ix, ex = axis_report(colp, w)
    zy, iy, ey = axis_report(rowp, h)
    ncol = len([v for i, v in enumerate(ex[:-1])])       # 边界数
    # 块数 = 内部缝数 + 1
    ncol = len(ix) + 1
    nrow = len(iy) + 1
    n_cols_hist[ncol] += 1
    n_rows_hist[nrow] += 1
    rows.append(dict(name=nm, w=w, h=h, ncol=ncol, nrow=nrow,
                     xseams=ix, yseams=iy,
                     cell=(w / float(ncol), h / float(nrow))))
    if ix or iy:
        print('  %-28s %4dx%-4d  列=%d 行=%d  格=%.1fx%.1f  x缝%s  y缝%s'
              % (nm, w, h, ncol, nrow, w / float(ncol), h / float(nrow),
                 ix[:4], iy[:4]))

print()
print('=' * 100)
print('列数分布 / 行数分布（由缝推得）')
print('=' * 100)
print('  列数：%s' % dict(sorted(n_cols_hist.items())))
print('  行数：%s' % dict(sorted(n_rows_hist.items())))

print()
print('=' * 100)
print('★ 关键对照：由缝推得的「列数」vs 候选规则')
print('=' * 100)
agree = collections.Counter()
mism = []
for r in rows:
    w, h = r['w'], r['h']
    cand = {
        '4x4': (4, 4),
        '3x4': (3, 4),
        '1x1': (1, 1),
        '1x4': (1, 4),
        '4x1': (4, 1),
        'w/32 x h/32': (max(1, w // 32), max(1, h // 32)),
    }
    hit = [k for k, (c, rr) in cand.items() if c == r['ncol'] and rr == r['nrow']]
    if hit:
        for k in hit:
            agree[k] += 1
    else:
        mism.append((r['name'], w, h, r['ncol'], r['nrow']))
for k in ('4x4', '3x4', '1x1', '1x4', '4x1', 'w/32 x h/32'):
    print('   %-13s 命中 %3d / %d' % (k, agree[k], len(rows)))
print('   无候选命中 %d 个，前 12：' % len(mism))
for m in mism[:12]:
    print('      %-28s %4dx%-4d 列=%d 行=%d' % m)

io.open(os.path.join(HERE, '..', '_evidence', 'grid103.json'), 'w',
        encoding='utf-8', newline='\n').write(
    json.dumps(dict(note='由 alpha 零剖面推得的图集网格（第103轮）', rows=rows),
               ensure_ascii=False, indent=1))
print()
print('   证据 -> _evidence/grid103.json')
