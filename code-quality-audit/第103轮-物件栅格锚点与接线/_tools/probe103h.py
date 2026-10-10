# -*- coding: utf-8 -*-
u"""probe103h.py —— 第103轮侦察 8：**打开 tmx**（Tiled 地图）找锚点 ground truth。

S0 已知：maps/ 里有 263 个 map#.tmx。若 tmx 里带
  · 瓦片层（含 tilewidth/tileheight）  → 世界格尺寸的权威值
  · **objectgroup（像素坐标的对象）**  → 那可能就是"物件画到哪儿"的**直接答案**
本脚本把 tmx 结构摊开看：
  A 逐层：layer / objectgroup / group / imagelayer，各层属性与元素数
  B 若存在 objectgroup：打印前若干 object 的 name/x/y/width/height/gid/point
  C 头属性：width/height/tilewidth/tileheight/orientation/infinite
  D tilesets 引用 + oneshot_tilesets.json / tilesets 目录
"""
import collections
import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/../../../ralsei_pet/src')
import importlib.util                                                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
spec = importlib.util.spec_from_file_location(
    'os_bg100', os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景',
                             '_tools', 'os_bg100.py'))
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)
MAPS = os.path.join(o.OSD, 'gamedata', 'maps')

for n in (4, 240):
    p = os.path.join(MAPS, 'map%d.tmx' % n)
    print('=' * 96)
    print('map%d.tmx    存在=%s  %d bytes' % (n, os.path.isfile(p),
                                            os.path.getsize(p) if os.path.isfile(p) else 0))
    print('=' * 96)
    if not os.path.isfile(p):
        continue
    raw = io.open(p, encoding='utf-8', errors='replace').read()
    print('  原始前 400 字：%s' % raw[:400].replace('\n', ' | '))
    root = ET.fromstring(raw)
    print('  <map> 属性 = %s' % root.attrib)
    print('  子元素：')
    for ch in root:
        tag = ch.tag
        if tag == 'layer':
            dat = ch.find('data')
            print('    layer        name=%-18s w=%s h=%s 元素=%s encoding=%s'
                  % (ch.get('name'), ch.get('width'), ch.get('height'),
                     len(dat) if dat is not None else 0,
                     (dat.get('encoding') if dat is not None else None)))
        elif tag == 'objectgroup':
            objs = ch.findall('object')
            print('    objectgroup  name=%-18s 对象数=%d' % (ch.get('name'), len(objs)))
            for ob in objs[:8]:
                print('        obj name=%-18s x=%-8s y=%-8s w=%-6s h=%-6s gid=%s point=%s'
                      % (ob.get('name'), ob.get('x'), ob.get('y'), ob.get('width'),
                         ob.get('height'), ob.get('gid'),
                         'yes' if ob.find('point') is not None else 'no'))
        elif tag == 'tileset':
            print('    tileset      firstgid=%s source=%s' % (ch.get('firstgid'), ch.get('source')))
        elif tag == 'imagelayer':
            img = ch.find('image')
            print('    imagelayer   name=%-18s image=%s' % (
                ch.get('name'), (img.get('source') if img is not None else None)))
        elif tag == 'group':
            print('    group        name=%-18s 子层=%d' % (ch.get('name'), len(list(ch))))
        else:
            print('    <%s> %s' % (tag, ch.attrib))
    # B: 若 objectgroup 有对象，打印全部（前 40）
    print()
    print('  --- 全部对象（前 40）---')
    cnt = 0
    for og in root.findall('objectgroup'):
        for ob in og.findall('object'):
            if cnt >= 40:
                break
            print('     [%s] name=%-20s x=%-8s y=%-8s w=%-6s h=%-6s gid=%s'
                  % (og.get('name'), str(ob.get('name'))[:20], ob.get('x'), ob.get('y'),
                     ob.get('width'), ob.get('height'), ob.get('gid')))
            cnt += 1
    print('  （共 %d 个对象）' % sum(len(og.findall('object'))
                                   for og in root.findall('objectgroup')))
    print()

print('=' * 96)
print('gamedata 相关文件')
print('=' * 96)
ts = os.path.join(o.OSD, 'gamedata', 'oneshot_tilesets.json')
if os.path.isfile(ts):
    d = json.loads(re.sub(r',(\s*[}\]])', r'\1',
                          io.open(ts, encoding='utf-8', newline='').read()))
    print('  oneshot_tilesets.json 类型=%s' % type(d).__name__)
    print('  %s' % json.dumps(d, ensure_ascii=False)[:1200])
for sub in ('tilesets', 'twm', 'autotiles'):
    d = os.path.join(o.OSD, 'gamedata', sub)
    if os.path.isdir(d):
        lst = sorted(os.listdir(d))
        print('  gamedata/%-10s %d 项：%s' % (sub, len(lst), lst[:12]))
