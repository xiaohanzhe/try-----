# -*- coding: utf-8 -*-
"""用**产品函数**（load_index / load_anchors / load_scene）确认索引真实状态。

铁律：能从源码拿的别 import，能 import 的别重写 —— 这里直接调产品函数。
"""
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
MODS = os.path.join(REPO, 'ralsei_pet', 'modules')
sys.path.insert(0, MODS)
sys.stdout.reconfigure(encoding='utf-8')

import scene_system as ss          # noqa: E402

idx = ss.load_index()
print('load_index ok=%s schema=%s default_scene=%r error=%r'
      % (idx.get('ok'), idx.get('schema_version'), idx.get('default_scene'), idx.get('error')))
scenes = idx.get('scenes') or {}
print('flat scenes =', len(scenes))
print('desktop entry =', json.dumps(scenes.get('desktop'), ensure_ascii=False)[:400])

anchors = ss.load_anchors()
print('anchors =', len(anchors) if hasattr(anchors, '__len__') else anchors)

# 抽样加载：锚点场景（独立文件）与分片场景各一个
def probe(sid):
    entry = scenes.get(sid)
    st = ss.load_scene(sid, entry=entry)
    print('  %-46s -> %s  name=%s bg=%s src=%s'
          % (sid, 'OK' if st else 'FAIL',
             getattr(st, 'name', None), getattr(st, 'bg', None),
             getattr(st, 'bg_source', None)))

print('sample loads:')
for sid in ['desktop'] + [s for s in sorted(scenes) if s != 'desktop'][:2] + \
           [s for s in sorted(scenes) if s.startswith('ch1.castle_town')][:2]:
    probe(sid)

# 失败计数（全量）
bad = []
for sid, entry in scenes.items():
    if ss.load_scene(sid, entry=entry) is None:
        bad.append(sid)
print('全量加载失败 =', len(bad), bad[:10])

meta = json.load(open(os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes', '_index.json'),
                      encoding='utf-8')).get('meta') or {}
print('meta keys =', sorted(meta.keys()))
print('zone_file_pattern =', meta.get('zone_file_pattern'))
