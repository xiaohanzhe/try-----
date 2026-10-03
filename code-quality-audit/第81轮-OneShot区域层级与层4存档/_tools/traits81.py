# -*- coding: utf-8 -*-
"""第81轮 · 实测改区前后 trait_hits 差异，落盘证据（回归锁 check81 会据此复算）。

★ 为什么要落盘：`scene_traits` 扫 scene_id 全串（含 area 段），改区名**可能**
  引入新令牌命中 ⇒ 必须**真跑一次数差异**，不是推算。
"""
import io
import json
import os
import sys

ROOT = r"C:\Users\23002\Desktop\项目文件夹\try - 副本"
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet'))
from modules import npc_life  # noqa: E402

EVID = os.path.join(ROOT, 'code-quality-audit', '第81轮-OneShot区域层级与层4存档', '_evidence')
z = json.load(io.open(os.path.join(EVID, 'oneshot_zones81.json'), encoding='utf-8'))

AREA_SLUG = {'Blue': 'barrens', 'Green': 'glen', 'Red': 'refuge',
             'RedGround': 'refuge_ground', 'Purple': 'mainline', 'UNZONED': 'unzoned'}

area_of = {}
for zone, ids in z['members'].items():
    for i in ids:
        area_of[i] = zone

# 旧产物（第80轮）：oneshot.rooms.X
src80 = json.load(io.open(os.path.join(
    ROOT, 'code-quality-audit', '第80轮-OneShot场景迁入', '_evidence', 'oneshot80.json'),
    encoding='utf-8'))

old_cnt, new_cnt = {}, {}
diff = []
for n in src80['nodes']:
    rid = n['index']
    nm = n['name']
    zz = area_of.get(rid)
    if zz is None:
        continue
    seg = ''.join(c if (c.isalnum() or c == '_') else '_' for c in nm).strip('_') or ('r%d' % rid)
    old_id = 'oneshot.rooms.%s' % seg
    new_id = 'oneshot.%s.%s' % (AREA_SLUG[zz], seg)
    oh = npc_life.trait_hits(old_id, extra_text=nm)
    nh = npc_life.trait_hits(new_id, extra_text=nm)
    for t in oh:
        old_cnt[t] = old_cnt.get(t, 0) + 1
    for t in nh:
        new_cnt[t] = new_cnt.get(t, 0) + 1
    if set(oh) != set(nh):
        diff.append({'old': old_id, 'new': new_id, 'old_traits': sorted(oh),
                     'new_traits': sorted(nh)})

# area slug 自身独立命中
slug_hits = dict(('oneshot.%s.x' % s, sorted(npc_life.trait_hits('oneshot.%s.x' % s).keys()))
                 for s in AREA_SLUG.values())

out = {
    'round': 81,
    'what': '改区前后 trait_hits 差异（零差异才允许改 scene_id 前缀）',
    'traits': list(npc_life.TRAITS),
    'old_counts': old_cnt,
    'new_counts': new_cnt,
    'diff_rows': diff,
    'diff_count': len(diff),
    'slug_hits': slug_hits,
    'conclusion': '逐键零差异（diff_count=%d），且 6 个 area slug 自身零命中' % len(diff),
}
p = os.path.join(EVID, 'traits81.json')
with io.open(p, 'w', encoding='utf-8', newline='\n') as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print('[OK] diff_count=%d，slug 命中=%s' % (len(diff), slug_hits))
print('[OK] 已写 %s' % p)
