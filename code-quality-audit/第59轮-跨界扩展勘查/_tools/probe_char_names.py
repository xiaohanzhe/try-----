# -*- coding: utf-8 -*-
"""提取三个游戏的"角色主名"（用于生成需要用户提供设定的清单）。"""
import io
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 噪音词：非角色（UI/系统/特效/攻击）
NOISE = re.compile(
    r'^(attack|bullet|asset|ui|menu|bt|button|text|font|snd|mus|sfx|bg|room|rm|'
    r'ts|tile|part|obj|scr|gml|save|file|view|fnt|path|shop|stat|item|act|'
    r'draw|blt|mett|cted|er|no|max|min|can|pt|time|spr|solid|fade|screen|'
    r'logo|title|cursor|box|bar|icon|hud|overlay|frame|panel|arrow|key|'
    r'dummy|test|debug|unused|old|copy|backup)', re.I)


def gm_names(path):
    RX = re.compile(rb'[\x20-\x7e]{4,48}')
    data = open(path, 'rb').read()
    toks = {t.decode('ascii', 'ignore') for t in RX.findall(data)}
    del data
    spr = {m.group(1) for s in toks for m in [re.fullmatch(r'spr_([a-z0-9_]+)', s)] if m}
    obj = {m.group(1) for s in toks for m in [re.fullmatch(r'obj_([a-z0-9_]+)', s)] if m}
    return spr, obj


def roots(names):
    c = Counter()
    for n in names:
        if n[0].isdigit():
            continue
        head = n.split('_')[0]
        if len(head) < 3 or NOISE.match(head) or NOISE.fullmatch(head):
            continue
        c[head] += 1
    return c


print('=' * 78)
print('[undertale]')
spr, obj = gm_names(r'E:\Download\apk_extract\undertale\assets\game.droid')
c = roots(spr) + roots(obj)
print('  sprite=%d obj=%d' % (len(spr), len(obj)))
print('  主名 top60:')
print('   ', ', '.join('%s(%d)' % (k, v) for k, v in c.most_common(60)))

print()
print('=' * 78)
print('[huanghun / Undertale Yellow]')
spr, obj = gm_names(r'E:\Download\apk_extract\huanghun\assets\game.droid')
c = roots(spr) + roots(obj)
print('  sprite=%d obj=%d' % (len(spr), len(obj)))
print('  主名 top60:')
print('   ', ', '.join('%s(%d)' % (k, v) for k, v in c.most_common(60)))

print()
print('=' * 78)
print('[outertale] assets/www 里的 png 基础名（去 hash 后缀）')
W = r'E:\Download\apk_extract\outertale\assets\www'
pngs = [f for f in os.listdir(W) if f.endswith('.png')]
base = Counter()
for f in pngs:
    stem = f[:-4]
    m = re.match(r'^(.*)-[A-Za-z0-9_\-]{8}$', stem)
    base[(m.group(1) if m else stem).lower()] += 1
print('  png=%d 基础名=%d' % (len(pngs), len(base)))
keys = sorted(base)
print('  全部基础名（前 220）：')
for i in range(0, min(len(keys), 220), 6):
    print('   ', ', '.join(keys[i:i + 6]))
