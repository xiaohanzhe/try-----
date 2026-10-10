# -*- coding: utf-8 -*-
u"""probe103i.py —— 第103轮侦察 9：找"原作自己渲染好的房间图"当标尺。

S0 已知：tmx 只有瓦片层（无对象层），tilewidth=16。
锚点需要一个**像素标尺**。候选来源：
  A gamedata/oneshot_minimap_info.json —— 小地图/预览图？
  B gamedata/tilesets/*.tsx + autotiles/*.tsx —— 瓦片集图（能否自渲染瓦片层）
  C ralsei_pet/assets/scenes/ —— 第101轮落盘的 OneShot 背景，是不是**房间整图**
  D OSD 内所有 png/jpg 尺寸大于 64x64 的（找房间预览图）
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
OSD = o.OSD


def rj(p):
    return json.loads(re.sub(r',(\s*[}\]])', r'\1',
                             io.open(p, encoding='utf-8', newline='').read()))


print('=' * 96)
print('A oneshot_minimap_info.json')
print('=' * 96)
for fn in ('oneshot_minimap_info.json', 'oneshot_minimap_nodes.json',
           'oneshot_map_names.json', 'oneshot_map_zone_names.json'):
    p = os.path.join(OSD, 'gamedata', fn)
    if not os.path.isfile(p):
        print('  %s 不存在' % fn)
        continue
    d = rj(p)
    print('  %s  type=%s' % (fn, type(d).__name__))
    print('     %s' % json.dumps(d, ensure_ascii=False)[:600])
    print()

print('=' * 96)
print('B tilesets/*.tsx 单个内容（自渲染瓦片层用）')
print('=' * 96)
tsx = os.path.join(OSD, 'gamedata', 'tilesets', 'green.tsx')
if os.path.isfile(tsx):
    print(io.open(tsx, encoding='utf-8', errors='replace').read()[:900])
tsx2 = os.path.join(OSD, 'gamedata', 'autotiles', 'green_water.tsx')
if os.path.isfile(tsx2):
    print('  --- green_water.tsx ---')
    print(io.open(tsx2, encoding='utf-8', errors='replace').read()[:700])
print('  tsx 引用的图片是否在位？')
for sub in ('tilesets', 'autotiles'):
    d = os.path.join(OSD, 'gamedata', sub)
    imgs = [f for f in os.listdir(d) if f.lower().endswith(('.png', '.jpg'))]
    print('    %-10s 图片 %d 张：%s' % (sub, len(imgs), sorted(imgs)[:8]))

print()
print('=' * 96)
print('C ralsei_pet/assets/scenes/ 结构（第101轮背景落盘）')
print('=' * 96)
SC = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
for dirpath, dirnames, filenames in os.walk(SC):
    rel = os.path.relpath(dirpath, SC)
    if len(rel.split(os.sep)) > 2:
        dirnames[:] = []
        continue
    print('  %-46s 文件 %d' % (rel + os.sep, len(filenames)))
    if rel != '.' and filenames:
        print('      例：%s' % sorted(filenames)[:6])

print()
print('=' * 96)
print('D OSD 内大图（可能是房间预览）')
print('=' * 96)
big = []
for dirpath, dirnames, filenames in os.walk(OSD):
    if len(dirpath.split(os.sep)) > len(OSD.split(os.sep)) + 3:
        continue
    for f in filenames:
        if f.lower().endswith(('.png', '.jpg')):
            p = os.path.join(dirpath, f)
            try:
                sz = os.path.getsize(p)
            except OSError:
                continue
            if sz > 20000:
                big.append((os.path.relpath(p, OSD), sz))
big.sort(key=lambda t: -t[1])
print('  共 %d 张 >20KB；前 12：' % len(big))
for r, s in big[:12]:
    print('    %-70s %d' % (r[:70], s))

print()
print('=' * 96)
print('E 房间 4 的 tmx 瓦片层 3 层非零数 + tileset_id')
print('=' * 96)
import xml.etree.ElementTree as ET                                      # noqa: E402
p = os.path.join(OSD, 'gamedata', 'maps', 'map4.tmx')
root = ET.fromstring(io.open(p, encoding='utf-8', errors='replace').read())
for L in root.findall('layer'):
    dat = L.find('data')
    txt = (dat.text or '').strip()
    vals = [int(v) for v in txt.replace('\n', '').split(',') if v.strip()]
    nz = sum(1 for v in vals if v)
    print('  %-14s 元素 %d  非零 %d  csv前12=%s' % (L.get('name'), len(vals), nz, vals[:12]))
print('  房间 4 尺寸 52x30 = %d' % (52 * 30))
