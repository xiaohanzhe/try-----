# -*- coding: utf-8 -*-
u"""probe103g.py —— 第103轮侦察 7：**引擎指纹 + 可用属性普查**（为锚点找依据）。

栅格规则已由像素定死（cell=(w/4,h/4)、col=pattern、row=DIR_ROW）。
剩下的是**锚点**："格画到哪儿"。锚点不能靠猜，要先看两件事：
  S1 事件/页/graphic **到底有哪些键**（引擎指纹：有 character_hue/blend_type = RPG Maker XP 系）
  S2 maps 目录里**有没有瓦片层**（tile layer）——若物件同时也作为瓦片出现在地图层，
     就能拿"瓦片位置"当锚点的**ground truth**
  S3 完整打印 1 个事件（逐键），确认没有藏着 size/offset 字段
  S4 打印要用的图集尺寸
"""
import collections
import importlib.util
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
spec = importlib.util.spec_from_file_location(
    'os_bg100', os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景',
                             '_tools', 'os_bg100.py'))
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)
MAPS = os.path.join(o.OSD, 'gamedata', 'maps')


def rj(p):
    return json.loads(re.sub(r',(\s*[}\]])', r'\1',
                             io.open(p, encoding='utf-8', newline='').read()))


print('=' * 96)
print('S0 maps 目录清单（看有没有瓦片层 / 元数据）')
print('=' * 96)
allf = sorted(os.listdir(MAPS))
print('  共 %d 个文件' % len(allf))
kinds = collections.Counter(re.sub(r'\d+', '#', f) for f in allf)
for k, v in sorted(kinds.items()):
    print('    %-40s %d' % (k, v))
print('  非 events_ 开头的：%s' % [f for f in allf if not f.startswith('events_')][:20])

print()
print('=' * 96)
print('S1 键全集普查（事件 / 页 / graphic / 页内其它子对象）')
print('=' * 96)
KEV = collections.Counter()
KPG = collections.Counter()
KGR = collections.Counter()
KPGSUB = collections.Counter()
n_ev = n_pg = n_gr = 0
for n in range(1, 400):
    p = os.path.join(MAPS, 'events_map%d.json' % n)
    if not os.path.isfile(p):
        continue
    for e in rj(p).get('events', []):
        n_ev += 1
        for k in e:
            KEV[k] += 1
        for pg in (e.get('pages') or []):
            n_pg += 1
            for k in pg:
                KPG[k] += 1
            g = pg.get('graphic') or {}
            if g:
                n_gr += 1
                for k in g:
                    KGR[k] += 1
            for k, v in pg.items():
                if isinstance(v, dict):
                    KPGSUB['%s{%s}' % (k, ','.join(sorted(v)))] += 1
print('  事件 %d / 页 %d / graphic %d' % (n_ev, n_pg, n_gr))
print('  --- 事件的键 ---')
for k, v in KEV.most_common():
    print('    %-24s %d' % (k, v))
print('  --- 页的键 ---')
for k, v in KPG.most_common():
    print('    %-24s %d' % (k, v))
print('  --- graphic 的键（★ 引擎指纹）---')
for k, v in KGR.most_common():
    print('    %-24s %d' % (k, v))
print('  --- 页内子对象的键组合 ---')
for k, v in KPGSUB.most_common(20):
    print('    %-70s %d' % (k[:70], v))

print()
print('=' * 96)
print('S2 瓦片层是否存在（有的话可当锚点 ground truth）')
print('=' * 96)
for n in (4, 11, 240):
    p = os.path.join(MAPS, 'events_map%d.json' % n)
    if not os.path.isfile(p):
        continue
    d = rj(p)
    print('  map%-4d 顶层键 = %s' % (n, sorted(d)))
for probe in ('mapdata', 'tiles', 'layers', 'map'):
    cand = os.path.join(o.OSD, 'gamedata', probe)
    print('  候选目录 %-10s 存在=%s' % (probe, os.path.isdir(cand)))
for other in ('gamedata', 'gamedata/maps'):
    d = os.path.join(o.OSD, other)
    if os.path.isdir(d):
        sub = sorted(os.listdir(d))
        print('  %s -> %s' % (other, sub[:30]))
print('  OSD = %s' % o.OSD)

print()
print('=' * 96)
print('S3 完整打印 1 个事件（确认没有藏 size/offset）')
print('=' * 96)
d = rj(os.path.join(MAPS, 'events_map4.json'))
for e in d.get('events', []):
    if (e.get('name') or '').lower().startswith('north door'):
        print(json.dumps(e, ensure_ascii=False, indent=1)[:2600])
        break
else:
    ev = d.get('events', [])
    if ev:
        print(json.dumps(ev[0], ensure_ascii=False, indent=1)[:2600])

print()
print('=' * 96)
print('S4 图集尺寸（用于反推 cell）')
print('=' * 96)
ING = json.load(io.open(os.path.join(
    ROOT, 'code-quality-audit', '第102轮-光照与ambient接入', '_evidence',
    'ingest102.json'), encoding='utf-8'))
SIZES = {f['name']: (f['w'], f['h']) for f in ING['files']}
for nm in ('green_npc_cedric', 'pc', 'items_tut', 'DOORS', 'DOORS2', 'bed',
           'green_marimo', 'green_marimo2', 'water_waves_green2',
           'water_waves_green_tall', 'green_npc_adult3', 'red_rue',
           'jars_new', 'sparkle_blue1'):
    w, h = SIZES.get(nm, (0, 0))
    print('  %-26s %4dx%-4d  4x4格=%s  3x4格=%s' % (
        nm, w, h, ('%gx%g' % (w / 4.0, h / 4.0)) if w else '-',
        ('%gx%g' % (w / 3.0, h / 4.0)) if w else '-'))
sz = collections.Counter(SIZES.values())
print('  尺寸种类 %d；最常见 12 种：' % len(sz))
for k, v in sz.most_common(12):
    print('    %4dx%-4d  %d 张' % (k[0], k[1], v))
