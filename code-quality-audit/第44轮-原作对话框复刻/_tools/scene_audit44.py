# -*- coding: utf-8 -*-
"""第44轮续 · 场景数据资产体检（只读）。

回答用户口径里的两个硬问题：
  1) room 是否齐全（原作 1,251 间 → 产品 1,013/1,014 场景）
  2) 连接顺序是否对（原作 782 边 → 产品路由表）
另附：bg 素材覆盖率、锚点、分片自洽性。
"""
import io
import json
import os
import re

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
SC = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
TMP = r'E:\Download\_tmp'


def jload(p):
    with io.open(p, encoding='utf-8') as fh:
        return json.load(fh)


idx = jload(os.path.join(SC, '_index.json'))
orig = jload(os.path.join(SC, '_original_rooms.json'))
routes = jload(os.path.join(SC, '_routes.json'))
anchors = jload(os.path.join(SC, '_anchors.json'))

print('=' * 72)
print('[1] 索引元信息')
print('  schema_version =', idx['schema_version'])
print('  default_scene  =', idx['default_scene'])
print('  meta keys      =', sorted(idx['meta']))
for k, v in sorted(idx['meta'].items()):
    print('    %-22s = %s' % (k, v))

print('=' * 72)
print('[2] 各章场景数 / 房间数')
tot_scenes = 0
tot_rooms_idx = 0
for ch, v in sorted(idx['chapters'].items()):
    zones = v.get('zones') or {}
    n_sc = sum(len(z.get('scenes', [])) if isinstance(z, dict) else len(z)
               for z in zones.values()) if isinstance(zones, dict) else len(zones)
    n_rooms = v.get('room_count') or v.get('rooms') or len(v.get('room_ids', []))
    tot_scenes += n_sc
    try:
        tot_rooms_idx += int(n_rooms)
    except Exception:
        pass
    print('  %-6s scenes=%-5s rooms=%-5s keys=%s'
          % (ch, n_sc, n_rooms, sorted(v)[:8]))
print('  ---- 合计 scenes=%d rooms=%d' % (tot_scenes, tot_rooms_idx))

print('=' * 72)
print('[3] _original_rooms.json 结构')
if isinstance(orig, dict):
    print('  top keys =', sorted(orig)[:10])
    for k, v in list(orig.items())[:3]:
        print('   %s -> %s len=%s' % (k, type(v), len(v) if hasattr(v, '__len__') else v))
        if isinstance(v, list) and v:
            print('      样例:', json.dumps(v[0], ensure_ascii=False)[:200])
        elif isinstance(v, dict) and v:
            kk = list(v)[0]
            print('      %s: %s' % (kk, json.dumps(v[kk], ensure_ascii=False)[:200]))
elif isinstance(orig, list):
    print('  list len =', len(orig))
    print('  样例:', json.dumps(orig[0], ensure_ascii=False)[:300])

print('=' * 72)
print('[4] _routes.json 结构')
if isinstance(routes, dict):
    print('  top keys =', sorted(routes)[:10])
    rr = routes.get('routes') or routes.get('rules') or []
    print('  rules 数 =', len(rr))
    if isinstance(rr, list):
        for r in rr[:3]:
            print('    ', json.dumps(r, ensure_ascii=False)[:260])
elif isinstance(routes, list):
    print('  list len =', len(routes))
    print('  样例:', json.dumps(routes[0], ensure_ascii=False)[:300])

print('=' * 72)
print('[5] _anchors.json 结构')
if isinstance(anchors, dict):
    print('  top keys =', sorted(anchors)[:10])
    for k in list(anchors)[:2]:
        v = anchors[k]
        print('   %s -> %s len=%s' % (k, type(v), len(v) if hasattr(v, '__len__') else v))
elif isinstance(anchors, list):
    print('  list len =', len(anchors))
    print('  样例:', json.dumps(anchors[0], ensure_ascii=False)[:300])

print('=' * 72)
print('[6] 分片自洽性（每个 _zone.*.json 的场景集合 vs 索引）')
files = sorted(f for f in os.listdir(SC) if f.startswith('_zone.'))
print('  分片数 =', len(files))
import collections
dup = collections.Counter()
all_ids = []
for f in files:
    z = jload(os.path.join(SC, f))
    if isinstance(z, dict):
        sids = z.get('scene_ids') or [s['id'] if isinstance(s, dict) else s
                                      for s in z.get('scenes', [])]
    else:
        sids = [s['id'] if isinstance(s, dict) else s for s in z]
    all_ids.extend(sids)
print('  分片内场景总数 =', len(all_ids), ' 去重后 =', len(set(all_ids)))
dup = collections.Counter(all_ids)
d2 = [k for k, v in dup.items() if v > 1]
print('  跨分片重复 ID 数 =', len(d2), d2[:10])

print('=' * 72)
print('[7] 背景素材覆盖')
bgs = set()
for ch, v in sorted(idx['chapters'].items()):
    zones = v.get('zones') or {}
    it = zones.values() if isinstance(zones, dict) else zones
    for z in it:
        scenes = z.get('scenes', []) if isinstance(z, dict) else z
        for s in scenes:
            if isinstance(s, dict):
                bg = s.get('bg')
                if bg:
                    bgs.add((s.get('bg_source', '?'), bg))
print('  带 bg 的场景引用数 =', len(bgs))
src_c = collections.Counter(k for k, _ in bgs)
print('  按 bg_source:', dict(src_c))

print('=' * 72)
print('[8] 与第43轮原作数据对齐（若临时文件还在）')
for fn, label in (('_room_order.json', '原作房间全序'), ('_room_graph.json', '原作边表')):
    p = os.path.join(TMP, fn)
    if os.path.isfile(p):
        d = jload(p)
        n = len(d) if hasattr(d, '__len__') else '?'
        print('  %-12s 在盘：%s  条目=%s' % (fn, label, n))
        if isinstance(d, dict):
            print('     keys =', sorted(d)[:8])
    else:
        print('  %-12s **不在盘**（临时区已清或未生成）' % fn)
print('[done]')
