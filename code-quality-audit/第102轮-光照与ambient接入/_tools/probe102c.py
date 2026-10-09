# -*- coding: utf-8 -*-
u"""probe102c.py —— 第102轮侦察 3：找 `ambient` / 光照的**真源**，并量测「偏暗」。

 R1 `gamedata/` 全貌（有没有脚本定义文件）
 R2 `*_ambient` 这些名字在哪儿被定义（脚本真源）
 R3 从 `OneShotMG.exe`（托管程序集）里抠 UTF-16 字符串，看光照/黑暗相关的标识符
 R4 ★ 量测：263 张合成图的**亮度画像**（均亮度 / 暗像素占比）——「偏暗」到底成不成立
"""
import collections
import io
import os
import re
import struct
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image                                          # noqa: E402

OSD = (r'C:\Users\23002\Desktop\项目文件夹\niko的秘密'
       r'\OneShot.World.Machine.Edition.Build.16512634')
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_BG = os.path.normpath(os.path.join(HERE, '..', '..', '..',
                                        'ralsei_pet', 'assets', 'scenes', 'bg'))

print('=' * 78)
print('R1 gamedata/ 全貌')
print('=' * 78)
GD = os.path.join(OSD, 'gamedata')
for root, dirs, files in os.walk(GD):
    rel = root[len(GD):].strip(os.sep)
    depth = 0 if not rel else rel.count(os.sep) + 1
    if depth > 1:
        dirs[:] = []
        continue
    print('[%s]' % (rel or '.'))
    for f in sorted(files)[:30]:
        print('   %-48s %9d' % (f, os.path.getsize(os.path.join(root, f))))
    if len(files) > 30:
        print('   ... 另 %d 个文件' % (len(files) - 30))
    for d in sorted(dirs)[:20]:
        print('   <DIR> %s' % d)

print()
print('=' * 78)
print('R2 `*_ambient` 定义在哪儿')
print('=' * 78)
pat = re.compile(r'(\w*ambient\w*)', re.I)
found = collections.defaultdict(set)
for root, dirs, files in os.walk(GD):
    for f in files:
        p = os.path.join(root, f)
        if os.path.getsize(p) > 40_000_000:
            continue
        try:
            raw = open(p, 'rb').read()
        except Exception:
            continue
        for enc in ('utf-8', 'utf-16-le'):
            try:
                t = raw.decode(enc, 'replace')
            except Exception:
                continue
            for m in pat.finditer(t):
                found[m.group(1)].add(os.path.relpath(p, GD) + '|' + enc)
for k in sorted(found):
    print('   %-24s %s' % (k, sorted(found[k])[:4]))

print()
print('=' * 78)
print('R3 OneShotMG.exe 里的光照/黑暗标识符（UTF-16 字符串）')
print('=' * 78)
exe = os.path.join(OSD, 'OneShotMG.exe')
raw = open(exe, 'rb').read()
print('exe 大小 =', len(raw))
KEYS = ['lightmap', 'Lightmap', 'LightMap', 'ambient', 'Ambient',
        'darkness', 'Darkness', 'Tone', 'tone', 'Additive', 'opacity']
hits = collections.defaultdict(set)
# .NET #US 堆里的字符串是 UTF-16LE；直接按 UTF-16LE 解整文件会碎，改成滑窗找可打印段
for m in re.finditer(rb'(?:[\x20-\x7e]\x00){4,}', raw):
    s = m.group().decode('utf-16-le', 'replace')
    for k in KEYS:
        if k in s:
            hits[k].add(s)
for k in KEYS:
    v = sorted(hits[k])
    print('   %-12s %d 条' % (k, len(v)))
    for s in v[:6]:
        print('        %r' % s[:110])

print()
print('=' * 78)
print('R4 ★ 263 张合成图的亮度画像（均亮度 0~255）')
print('=' * 78)
print('目录 =', REPO_BG, os.path.isdir(REPO_BG))
if os.path.isdir(REPO_BG):
    rows = []
    for f in sorted(os.listdir(REPO_BG)):
        if not re.match(r'oneshot_map\d+\.png$', f):
            continue
        im = Image.open(os.path.join(REPO_BG, f)).convert('RGB')
        px = im.resize((min(im.width, 160), min(im.height, 160))).getdata()
        n = len(px)
        lum = [0.299 * r + 0.587 * g + 0.114 * b for r, g, b in px]
        mean = sum(lum) / n
        dark = sum(1 for x in lum if x < 40) / float(n)
        rows.append((f, im.size, mean, dark))
    rows.sort(key=lambda r: r[2])
    print('共 %d 张' % len(rows))
    tot = sum(r[2] for r in rows) / len(rows)
    print('全体均亮度 = %.1f / 255' % tot)
    print('--- 最暗 8 张 ---')
    for f, sz, m_, d in rows[:8]:
        print('   %-22s %-11s 均亮度 %6.1f  暗像素占比 %5.1f%%' % (f, sz, m_, d * 100))
    print('--- 最亮 8 张 ---')
    for f, sz, m_, d in rows[-8:]:
        print('   %-22s %-11s 均亮度 %6.1f  暗像素占比 %5.1f%%' % (f, sz, m_, d * 100))
    buckets = collections.Counter()
    for _, _, m_, _ in rows:
        buckets[int(m_ // 32)] += 1
    print('--- 亮度分布（每档 32） ---')
    for k in sorted(buckets):
        print('   %3d~%3d : %s %d' % (k * 32, k * 32 + 31, '#' * buckets[k], buckets[k]))
