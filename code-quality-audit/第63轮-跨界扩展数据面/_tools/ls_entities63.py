# -*- coding: utf-8 -*-
u"""读 outertale63_assets.json，打印"跨族 + 单族"两组的完整词元清单（供人工归类）。"""
import io
import json
import os

ROUND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(ROUND, '_evidence', 'outertale63_assets.json')
d = json.load(io.open(p, encoding='utf-8'))
print(u'named=%d image_only=%d' % (d['named_sprite_count'], d['image_only_count']))
print(u'anchors=%s' % json.dumps(d['anchors']['geom_ok']))
ch = d['characters_multi_family']
lo = d['single_family']
print()
print(u'== 跨族（%d）==' % len(ch))
for k, v in sorted(ch.items(), key=lambda kv: -kv[1]['sprites']):
    print(u'  %-16s %3d  %s' % (k, v['sprites'], ','.join(v['fams'])))
print()
print(u'== 单族（%d）==' % len(lo))
for k, v in sorted(lo.items(), key=lambda kv: -kv[1]['sprites']):
    print(u'  %-16s %3d  %s' % (k, v['sprites'], ','.join(v['fams'])))
