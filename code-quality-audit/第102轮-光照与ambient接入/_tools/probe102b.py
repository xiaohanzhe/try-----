# -*- coding: utf-8 -*-
u"""probe102b.py —— 第102轮侦察 2：把「偏暗」的**真因**查实（不许靠猜）。

要回答：
 P1 `ambient` 到底是**事件命令**还是**房间字段**？（打印原文上下文）
 P2 lightmap 命令同理
 P3 tmx 里有没有"暗层"/"雾层"之类的**层**？263 张图的层名全谱是什么
 P4 map 级 `<property>` 全谱是什么（有没有 darkness / ambient 之类）
 P5 `content/fogs/` 是什么
 P6 合成图的**亮度画像**：是不是真的比"原作应有的样子"暗
"""
import collections
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OSD = (r'C:\Users\23002\Desktop\项目文件夹\niko的秘密'
       r'\OneShot.World.Machine.Edition.Build.16512634')
MAPS = os.path.join(OSD, 'gamedata', 'maps')
_TAG = re.compile(r'<(\w+)([^>]*?)/?>')
_ATTR = re.compile(r'(\w+)\s*=\s*"([^"]*)"')
SUF = {'ambient': [], 'lightmap': []}
for f in sorted(os.listdir(MAPS)):
    if not f.endswith('.json'):
        continue
    p = os.path.join(MAPS, f)
    if os.path.getsize(p) > 20_000_000:
        continue
    t = io.open(p, encoding='utf-8', errors='replace', newline='').read()
    for k in SUF:
        if k in t:
            SUF[k].append((f, t))

print('=' * 78)
print('P1 `ambient` 的**原文上下文**（看清它是命令还是字段）')
print('=' * 78)
for f, t in SUF['ambient'][:6]:
    for m in re.finditer(r'ambient', t):
        a, b = max(0, m.start() - 170), min(len(t), m.start() + 170)
        seg = t[a:b].replace('\n', ' ').replace('\r', '')
        print('--- %s ---\n    ...%s...' % (f, seg))
        break
print()
print('=' * 78)
print('P2 lightmap 的原文上下文')
print('=' * 78)
for f, t in SUF['lightmap'][:6]:
    for m in re.finditer(r'lightmap', t, re.I):
        a, b = max(0, m.start() - 170), min(len(t), m.start() + 170)
        seg = t[a:b].replace('\n', ' ').replace('\r', '')
        print('--- %s ---\n    ...%s...' % (f, seg))
        break

print()
print('=' * 78)
print('P3 263 张 tmx 的「层名全谱」+ map 级 property 全谱')
print('=' * 78)
layer_names = collections.Counter()
prop_names = collections.Counter()
prop_vals = collections.defaultdict(collections.Counter)
n_maps = 0
for f in sorted(os.listdir(MAPS)):
    if not f.endswith('.tmx'):
        continue
    n_maps += 1
    s = io.open(os.path.join(MAPS, f), encoding='utf-8', newline='').read()
    for name, tail in _TAG.findall(s):
        at = dict(_ATTR.findall(tail))
        if name == 'property':
            prop_names[at.get('name')] += 1
            prop_vals[at.get('name')][str(at.get('value'))[:40]] += 1
    for lay in re.findall(r'<layer\b([^>]*)>', s):
        at = dict(_ATTR.findall(lay))
        layer_names[at.get('name')] += 1
print('tmx 数 =', n_maps)
print('--- 层名全谱 ---')
for k, v in layer_names.most_common():
    print('   %-40s %d' % (repr(k), v))
print('--- <property> 名全谱 ---')
for k, v in prop_names.most_common():
    print('   %-40s %d' % (repr(k), v))
    for val, c in prop_vals[k].most_common(8):
        print('        = %-36s x%d' % (repr(val), c))

print()
print('=' * 78)
print('P5 content/fogs 与 the_world_machine')
print('=' * 78)
for sub in ['fogs', 'the_world_machine', 'shaders', 'panoramas', 'transitions']:
    d = os.path.join(OSD, 'content', sub)
    if os.path.isdir(d):
        fs = sorted(os.listdir(d))
        print('--- %s (%d) ---' % (sub, len(fs)))
        for x in fs[:14]:
            pp = os.path.join(d, x)
            print('   %-46s %s' % (x, os.path.getsize(pp) if os.path.isfile(pp) else '<DIR>'))
        if len(fs) > 14:
            print('   ... 另 %d' % (len(fs) - 14))
