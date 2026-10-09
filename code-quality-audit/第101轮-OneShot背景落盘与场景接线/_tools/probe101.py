# -*- coding: utf-8 -*-
"""第101轮侦察：OneShot scene <-> map 对应关系（只读）。

问三件事：
 1. 6 个 `_zone.oneshot.*.json` 里到底有多少个 scene，各自的 room_id / bg / bg_source 现状
 2. 这 263(?) 个 room_id 与 `gamedata/maps/map<N>.tmx` 的编号集是否一致
 3. `_index.json` 的 chapters.oneshot 里 scene 记录长什么样（有没有 bg 字段 —— 决定改一处还是两处）
"""
import io
import json
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
OSD = (r'C:\Users\23002\Desktop\项目文件夹\niko的秘密'
       r'\OneShot.World.Machine.Edition.Build.16512634')
MAPS = os.path.join(OSD, 'gamedata', 'maps')


def jload(p):
    with io.open(p, encoding='utf-8') as f:
        return json.load(f)


print('=' * 74)
print('1) zone 分片现状')
print('=' * 74)
zones = sorted(f for f in os.listdir(SCENES) if f.startswith('_zone.oneshot.'))
print('zone 分片 %d 个' % len(zones))
sc = {}
for z in zones:
    d = jload(os.path.join(SCENES, z))
    n = len(d.get('scenes') or {})
    print('  %-30s area=%-14s scenes=%d' % (z, d.get('area_id'), n))
    for sid, s in (d.get('scenes') or {}).items():
        if sid in sc:
            print('    !! 重复 scene_id: %s' % sid)
        sc[sid] = (z, s)

print('合计 scene = %d（唯一 %d）' % (len(sc), len(set(sc))))
print('scene_id 前缀分布 =', Counter(sid.split('.')[1] for sid in sc))
print('bg 非 None 的 = %d' % sum(1 for _, s in sc.values() if s.get('bg')))
print('bg_source 分布 =', dict(Counter(s.get('bg_source') for _, s in sc.values())))
print('字段集（取第一个）= %s' % sorted(list(sc.values())[0][1]))

print()
print('=' * 74)
print('2) scene 的 room_id  vs  原作 map 编号')
print('=' * 74)
rids = [int(s['original_room_id']) for _, s in sc.values()]
sr = set(rids)
print('room_id 唯一 %d 个，范围 %s' % (len(sr), (min(sr), max(sr))))
tmx = sorted(int(re.search(r'map(\d+)', f).group(1))
             for f in os.listdir(MAPS) if f.endswith('.tmx'))
sm = set(tmx)
print('map 文件 %d 个，范围 %s' % (len(sm), (min(sm), max(sm))))
print('room_id 有、map 无（%d）：%s' % (len(sr - sm), sorted(sr - sm)[:30]))
print('map 有、room_id 无（%d）：%s' % (len(sm - sr), sorted(sm - sr)[:30]))
print('交集 = %d' % len(sr & sm))
# 1:1 吗
dup = [k for k, v in Counter(rids).items() if v > 1]
print('同一 room_id 被多个 scene 引用（%d）：%s' % (len(dup), sorted(dup)[:20]))

print()
print('=' * 74)
print('3) _index.json 的 oneshot 记录形态')
print('=' * 74)
idx = jload(os.path.join(SCENES, '_index.json'))
och = (idx.get('chapters') or {}).get('oneshot') or {}
areas = och.get('areas') or {}
print('areas = %s' % list(areas))
cnt = 0
samples = []
for ak, av in areas.items():
    n = len((av or {}).get('scenes') or {})
    cnt += n
    print('  %-16s scenes=%d' % (ak, n))
    for sid, s in ((av or {}).get('scenes') or {}).items():
        if len(samples) < 2:
            samples.append((sid, s))
print('oneShot scene 总数（_index）= %d' % cnt)
for sid, s in samples:
    print('  样本 %s -> keys=%s' % (sid, sorted(s)))
print('  （有无 bg 字段：%s）' % any('bg' in s for _, s in samples))
