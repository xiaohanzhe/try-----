# -*- coding: utf-8 -*-
u"""probe102.py —— 第102轮侦察：OneShot 原作的 lightmaps / ambient 到底长什么样。

只读。回答四个问题：
 Q1 `Content/lightmaps/` 里有哪些文件、什么格式、多大
 Q2 场景 json 里的 `ambient` 字段在哪、值是什么、覆盖多少间房
 Q3 原作**代码**里光照是怎么用的（lightmap 贴在哪、什么混合模式、尺寸对不对得上）
 Q4 仓库这一侧（`ralsei_pet/assets/scenes/`）现在有没有 ambient
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OSD = (r'C:\Users\23002\Desktop\项目文件夹\niko的秘密'
       r'\OneShot.World.Machine.Edition.Build.16512634')
REPO_SCENES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           '..', '..', '..', 'ralsei_pet', 'assets', 'scenes')


def ls(d, pat=None, limit=40):
    if not os.path.isdir(d):
        print('   (不存在) %s' % d)
        return []
    fs = sorted(os.listdir(d))
    if pat:
        fs = [f for f in fs if re.search(pat, f, re.I)]
    for f in fs[:limit]:
        p = os.path.join(d, f)
        if os.path.isfile(p):
            print('   %-46s %9d' % (f, os.path.getsize(p)))
        else:
            print('   %-46s <DIR>' % f)
    if len(fs) > limit:
        print('   ... 另 %d 项' % (len(fs) - limit))
    return fs


print('=' * 78)
print('Q0 原作根目录')
print('=' * 78)
print('OSD 存在 =', os.path.isdir(OSD))
ls(OSD)

print()
print('=' * 78)
print('Q1 lightmaps')
print('=' * 78)
for cand in ['Content', 'content', 'Content/lightmaps', 'content/lightmaps']:
    d = os.path.join(OSD, cand)
    if os.path.isdir(d):
        print('--- %s (%d 项) ---' % (cand, len(os.listdir(d))))
        if 'lightmap' in cand.lower():
            ls(d)
        else:
            ls(d, limit=30)

print()
print('=' * 78)
print('Q2 场景 json 里的 ambient')
print('=' * 78)
hits = []
for root, dirs, files in os.walk(OSD):
    depth = root[len(OSD):].count(os.sep)
    if depth > 3:
        dirs[:] = []
        continue
    for f in files:
        if not f.endswith('.json'):
            continue
        p = os.path.join(root, f)
        if os.path.getsize(p) > 12_000_000:
            continue
        try:
            t = io.open(p, encoding='utf-8', errors='replace', newline='').read()
        except Exception:
            continue
        if 'ambient' in t:
            hits.append((p, t.count('ambient')))
for p, n in hits[:20]:
    print('   %-72s x%d' % (p[len(OSD) + 1:], n))
print('   命中文件 %d' % len(hits))

print()
print('=' * 78)
print('Q3 原作代码里光照的用法')
print('=' * 78)
code_hits = []
for root, dirs, files in os.walk(OSD):
    depth = root[len(OSD):].count(os.sep)
    if depth > 3:
        dirs[:] = []
        continue
    for f in files:
        if not f.endswith(('.json', '.txt', '.xml', '.tmx', '.tsx')):
            continue
        p = os.path.join(root, f)
        if os.path.getsize(p) > 12_000_000:
            continue
        try:
            t = io.open(p, encoding='utf-8', errors='replace', newline='').read()
        except Exception:
            continue
        if re.search(r'lightmap|Lightmap|LightMap|start_lightmaps', t):
            code_hits.append(p)
for p in code_hits[:30]:
    print('   %s' % p[len(OSD) + 1:])
print('   命中文件 %d' % len(code_hits))
print('   可执行/程序集：')
for f in sorted(os.listdir(OSD)):
    if f.lower().endswith(('.exe', '.dll')):
        print('   %-46s %9d' % (f, os.path.getsize(os.path.join(OSD, f))))

print()
print('=' * 78)
print('Q4 仓库侧 ralsei_pet/assets/scenes')
print('=' * 78)
d = os.path.normpath(REPO_SCENES)
print('存在 =', os.path.isdir(d), d)
if os.path.isdir(d):
    ls(d, limit=60)
    n_amb = 0
    for f in sorted(os.listdir(d)):
        if f.startswith('_zone.') and f.endswith('.json'):
            t = io.open(os.path.join(d, f), encoding='utf-8', newline='').read()
            n_amb += t.count('"ambient"')
    print('   仓库场景 json 里 "ambient" 出现 %d 次' % n_amb)
