# -*- coding: utf-8 -*-
"""第101轮侦察②：A0 两层登记一致性 + 既有 bg_source 取值规范（只读）。"""
import io
import json
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')


def jload(p):
    with io.open(p, encoding='utf-8') as f:
        return json.load(f)


idx = jload(os.path.join(SCENES, '_index.json'))

# --- A0：index 内联副本 vs zone 分片，逐字段比对（oneshot 263）-------------
zone = {}
for z in sorted(f for f in os.listdir(SCENES) if f.startswith('_zone.oneshot.')):
    d = jload(os.path.join(SCENES, z))
    for sid, s in (d.get('scenes') or {}).items():
        zone[sid] = s

inline = {}
for ak, av in ((idx['chapters'].get('oneshot') or {}).get('areas') or {}).items():
    for sid, s in ((av or {}).get('scenes') or {}).items():
        inline[sid] = s

print('=' * 74)
print('A0 两层登记一致性（index 内联 vs zone 分片）')
print('=' * 74)
print('zone=%d  index=%d' % (len(zone), len(inline)))
print('键集差：zone-only=%s  index-only=%s'
      % (sorted(set(zone) - set(inline))[:5], sorted(set(inline) - set(zone))[:5]))
diff_keys = []
for sid in set(zone) & set(inline):
    a, b = zone[sid], inline[sid]
    if set(a) != set(b) or json.dumps(a, sort_keys=True, ensure_ascii=False) != \
            json.dumps(b, sort_keys=True, ensure_ascii=False):
        diff_keys.append(sid)
print('内容不一致的 scene = %d %s' % (len(diff_keys), diff_keys[:5]))
if diff_keys:
    k = diff_keys[0]
    print('  样本 %s' % k)
    print('   zone  =%s' % json.dumps(zone[k], ensure_ascii=False, sort_keys=True)[:300])
    print('   index =%s' % json.dumps(inline[k], ensure_ascii=False, sort_keys=True)[:300])

# --- 既有 bg_source 取值规范 -------------------------------------------------
print()
print('=' * 74)
print('既有 bg_source 取值分布（全部作品）')
print('=' * 74)
vals = Counter()
per_work = {}
# 独立 scene 文件
for f in sorted(os.listdir(SCENES)):
    if f.endswith('.json') and not f.startswith('_'):
        d = jload(os.path.join(SCENES, f))
        if 'bg_source' in d:
            vals[d['bg_source']] += 1
            w = str(d.get('scene_id', '?')).split('.')[0]
            per_work.setdefault(w, Counter())[d['bg_source']] += 1
        elif 'scene_id' in d:
            vals['<无 bg_source 键>'] += 1
# zone 分片
for z in sorted(f for f in os.listdir(SCENES) if f.startswith('_zone.')):
    d = jload(os.path.join(SCENES, z))
    ch = d.get('chapter_id', '?')
    for sid, s in (d.get('scenes') or {}).items():
        v = s.get('bg_source', '<无键>')
        vals[v] += 1
        per_work.setdefault(ch, Counter())[v] += 1

for v, n in vals.most_common():
    print('  %-24s %d' % (v, n))
print()
for w, c in sorted(per_work.items()):
    print('  %-10s %s' % (w, dict(c)))

# --- bg 文件名规范 ----------------------------------------------------------
print()
print('=' * 74)
print('既有 bg/ 命名（前 6 + 计数）')
print('=' * 74)
bgdir = os.path.join(SCENES, 'bg')
bgs = sorted(os.listdir(bgdir))
print('bg/ 文件 %d 个' % len(bgs))
for b in bgs[:6]:
    print('  ', b)
print('  ...')
print('非 .png 的 =', [b for b in bgs if not b.endswith('.png')])
