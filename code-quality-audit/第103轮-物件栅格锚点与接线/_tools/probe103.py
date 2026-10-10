# -*- coding: utf-8 -*-
u"""probe103.py —— 第103轮侦察 1：把「图集怎么切」的**数据依据**找出来。

为什么先做这个
--------------
第102轮由 `events_map<N>.json` 的 `pages[0]['graphic']` 只有 7 个键
（tile_id / character_hue / direction / pattern / opacity / blend_type / character_name）
**推断**「没有 `character_index` ⇒ 多块图集取哪一块没依据」，于是只做了"整张入库"。

★★★ 但 RPG Maker VX Ace 的 `character_index` 是 **`RPG::Event::Page` 的字段**，
   **和 `graphic` 平级，不在 `graphic` 里面**！
   ⇒ 第102轮那句结论**可能是"只翻了 graphic 没翻 page"造成的看漏**。
   本轮第一件事就是**把它验掉**：翻 page 级键全集。

本脚本只读、不写盘。产出：
  Q1 page 级键全集（全库并集）+ 样例
  Q2 `character_index` 值域分布 / 是否每 (name) 恒定
  Q3 关键反证：**同一个 (name, direction, pattern) 会不会对应多个 character_index**
     （若会 ⇒ 它跟帧无关；若恒定且 >0 ⇒ 它就是选块依据）
  Q4 若存在：把 (name,index,direction,pattern) 四元组数出来 —— 这才是真正的"帧数"
  Q5 图集尺寸分布（为栅格分母提供候选）
  Q6 `direction` / `pattern` 值域复核（第102轮说 pattern 有 0/1/2/3）
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
SPEC = importlib.util.spec_from_file_location(
    'os_bg100', os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景',
                             '_tools', 'os_bg100.py'))
o = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(o)
MAPS = os.path.join(o.OSD, 'gamedata', 'maps')
NPC = os.path.join(o.OSD, 'content', 'npc')


def rj(p):
    return json.loads(re.sub(r',(\s*[}\]])', r'\1',
                             io.open(p, encoding='utf-8', newline='').read()))


page_keys = collections.Counter()
page_keys_by = collections.defaultdict(collections.Counter)   # key -> 出现值样例
idx_dist = collections.Counter()
idx_of_name = collections.defaultdict(set)
idx_of_triple = collections.defaultdict(set)
quad = collections.Counter()
dir_dist = collections.Counter()
pat_dist = collections.Counter()
n_pages_total = 0
name_pages = collections.Counter()

print('=' * 78)
print('Q1 page 级键全集（全库并集）')
print('=' * 78)
for n in range(1, 264):
    p = os.path.join(MAPS, 'events_map%d.json' % n)
    if not os.path.isfile(p):
        continue
    for e in rj(p).get('events', []):
        for pg in (e.get('pages') or []):
            n_pages_total += 1
            for k, v in pg.items():
                page_keys[k] += 1
                if len(page_keys_by[k]) < 6:
                    page_keys_by[k][type(v).__name__ + ':' + repr(v)[:44]] += 1
                if k == 'character_index':
                    idx_dist[v] += 1
                    g = pg.get('graphic') or {}
                    nm = (g.get('character_name') or '').strip()
                    if nm:
                        idx_of_name[nm].add(v)
                        idx_of_triple[(nm, int(g.get('direction') or 0),
                                       int(g.get('pattern') or 0))].add(v)
                        quad[(nm, v, int(g.get('direction') or 0),
                              int(g.get('pattern') or 0))] += 1
                        name_pages[nm] += 1
            g = pg.get('graphic') or {}
            if (g.get('character_name') or '').strip():
                dir_dist[int(g.get('direction') or 0)] += 1
                pat_dist[int(g.get('pattern') or 0)] += 1

print('  事件 page 总数 = %d' % n_pages_total)
for k, c in page_keys.most_common():
    print('   %-20s %7d  样例 %s' % (k, c, dict(list(page_keys_by[k].items())[:3])))

print()
print('=' * 78)
print('Q2 `character_index` 值域 + 是否每 (name) 恒定')
print('=' * 78)
if not idx_dist:
    print('  ★★ 全库**没有** `character_index` 这个键 —— 第102轮的结论成立（不是看漏）')
else:
    print('  值域分布 = %s' % dict(sorted(idx_dist.items())))
    multi = {k: sorted(v) for k, v in idx_of_name.items() if len(v) > 1}
    print('  图集名 %d 个，其中 index **不唯一**的 = %d 个 %s'
          % (len(idx_of_name), len(multi), list(multi.items())[:5]))
    print('  ⇒ %s' % ('index 随 (name) 固定 ⇒ **可能是选块依据**' if not multi
                      else 'index 在同一图集内会变 ⇒ 它**不是**选块依据，或另有含义'))

print()
print('=' * 78)
print('Q3 同一 (name,dir,pattern) 对应几个 index')
print('=' * 78)
multi_t = {k: sorted(v) for k, v in idx_of_triple.items() if len(v) > 1}
print('  三元组 %d 个，其中 index 不唯一的 = %d 个' % (len(idx_of_triple), len(multi_t)))
for k, v in list(multi_t.items())[:8]:
    print('     %s -> %s' % (k, v))

print()
print('=' * 78)
print('Q4 四元组 (name,index,dir,pattern) 数')
print('=' * 78)
print('  三元组 = %d ；四元组 = %d' % (len(idx_of_triple), len(quad)))
print('  四元组计数前 6 = %s' % quad.most_common(6))

print()
print('=' * 78)
print('Q5 图集尺寸分布（栅格分母候选）')
print('=' * 78)
names = sorted({k for k in idx_of_name} or
               {t[0] for t in idx_of_triple} or set())
if not names:
    # 兜底：重新扫一遍可见 name
    for n in range(1, 264):
        p = os.path.join(MAPS, 'events_map%d.json' % n)
        if not os.path.isfile(p):
            continue
        for e in rj(p).get('events', []):
            for pg in (e.get('pages') or []):
                nm = ((pg.get('graphic') or {}).get('character_name') or '').strip()
                if nm:
                    names.append(nm)
    names = sorted(set(names))

spec_path = os.path.join(ROOT, 'code-quality-audit', '第102轮-光照与ambient接入',
                         '_evidence', 'ingest102.json')
sizes = {}
if os.path.isfile(spec_path):
    ing = json.load(io.open(spec_path, encoding='utf-8'))
    sizes = {f['name']: (f['w'], f['h']) for f in ing['files']}
sz = collections.Counter(sizes.values())
print('  有尺寸的图集 %d 个；尺寸分布（前 18）：' % len(sizes))
for (w, h), c in sz.most_common(18):
    print('    %4d x %-4d  %2d 张   ÷4=%.1fx%.1f  ÷8=%.1fx%.1f  ÷3=%.1fx%.1f'
          % (w, h, c, w / 4.0, h / 4.0, w / 8.0, h / 8.0, w / 3.0, h / 3.0))

print()
print('=' * 78)
print('Q6 direction / pattern 值域复核')
print('=' * 78)
print('  direction = %s' % dict(sorted(dir_dist.items())))
print('  pattern   = %s' % dict(sorted(pat_dist.items())))
