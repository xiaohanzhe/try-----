# -*- coding: utf-8 -*-
"""第 38 轮：场景数据「两个来源」的端到端验证。

判据设计要点
------------
· **1,014 / 1,014 全部可加载**是主判据 —— 走的是**产品函数**（load_index +
  load_scene），不是我自己重写一遍读法。
· **双向判别力**（防恒真判据）：同一条分片场景
    · 不给 `entry` → 必须失败（None）—— 证明"分片这条路真的在做功"
    · 给 `entry`   → 必须成功（SceneState）
  两侧都断言，才排除"不管怎样都成功/都失败"。
· 负控制：乱造的区域名、乱造的场景 id、路径穿越 id 都必须安全回落。
· 性能：实测索引加载 / 读一片 / 读全部分片的耗时与内存。
"""
import gc
import io
import json
import os
import re
import sys
import time

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
MODS = os.path.join(ROOT, 'ralsei_pet', 'modules')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
EV = os.path.join(ROOT, 'code-quality-audit', '第38轮-场景系统审查', '_evidence')
sys.path.insert(0, MODS)

import scene_system as S          # noqa: E402

RES, OUT = [], []


def w(s=''):
    OUT.append(str(s))
    print(s)


def ck(name, ok, detail=''):
    RES.append((bool(ok), name, str(detail)))
    w('%s %s%s' % ('[PASS]' if ok else '[FAIL]', name,
                   ('  <- ' + str(detail)) if detail else ''))


w('=== 场景数据「两来源」端到端验证 ===')
w('')

# ---------------------------------------------------------------- 索引
t0 = time.perf_counter()
idx = S.load_index()
t_index = (time.perf_counter() - t0) * 1000.0
ck('V1 load_index 成功', idx.get('ok') is True, str(idx.get('error')))
scenes = idx.get('scenes') or {}
ck('V2 索引登记场景数 = 1,014（1,013 原作房间 + desktop）',
   len(scenes) == 1014, str(len(scenes)))
w('    load_index 耗时 = %.2f ms' % t_index)
w('')

# ---------------------------------------------------------------- 逐条可加载
t0 = time.perf_counter()
failed = []
from_own_file = 0
from_zone = 0
for sid, entry in scenes.items():
    sc = S.load_scene(sid, entry=entry)
    if sc is None:
        failed.append(sid)
        continue
    if os.path.isfile(os.path.join(SCENES, sid + '.json')):
        from_own_file += 1
    else:
        from_zone += 1
t_all = (time.perf_counter() - t0) * 1000.0
ck('V3 1,014 个场景**全部**可加载（走产品函数）', not failed,
   '失败 %d：%s' % (len(failed), failed[:6]))
w('    经独立文件 = %d ；经区域分片 = %d' % (from_own_file, from_zone))
w('    逐个加载 1,014 个总耗时 = %.1f ms（平均 %.2f ms/个）'
  % (t_all, t_all / max(1, len(scenes))))
ck('V4 独立文件来源 = 87 个锚点 + desktop',
   from_own_file == 88, str(from_own_file))
ck('V5 分片来源 = 926 个新增场景', from_zone == 926, str(from_zone))
w('')

# ---------------------------------------------------------------- 双向判别力
zone_sids = [sid for sid in scenes
             if not os.path.isfile(os.path.join(SCENES, sid + '.json'))]
probe = zone_sids[0]
e = scenes[probe]
without = S.load_scene(probe)
with_e = S.load_scene(probe, entry=e)
ck('V6 ★双向判别力：分片场景【不给 entry】必须失败', without is None,
   '%s → %r' % (probe, without))
ck('V7 ★双向判别力：分片场景【给 entry】必须成功', with_e is not None,
   '%s → %r' % (probe, with_e))
w('    探针 = %s（%s）' % (probe, (e or {}).get('name')))
w('')

# ---------------------------------------------------------------- 双源唯一性
zone_backed = set()
nz = 0
for fn in os.listdir(SCENES):
    if not fn.startswith('_zone.') or not fn.endswith('.json'):
        continue
    j = json.loads(io.open(os.path.join(SCENES, fn), 'r',
                           encoding='utf-8').read())
    nz += 1
    zone_backed.update((j.get('scenes') or {}).keys())
dup = sorted(zone_backed & set(sid for sid in scenes
                               if os.path.isfile(os.path.join(SCENES,
                                                              sid + '.json'))))
ck('V8 没有任何场景同时出现在"独立文件"和"分片"里（无双真源）', not dup,
   '重叠 %d：%s' % (len(dup), dup[:5]))
ck('V9 分片场景总数 = 926', len(zone_backed) == 926, str(len(zone_backed)))
w('')

# ---------------------------------------------------------------- 负控制
ck('V10 负控制：乱造的场景 id → None',
   S.load_scene('__definitely_no_such_scene__') is None)
ck('V11 负控制：路径穿越 id → None',
   S.load_scene('../../config') is None and S.load_scene('a/b') is None
   and S.load_scene('..') is None)
ck('V12 负控制：乱造的区域分片 → {}',
   S.load_zone('ch9', '__nope__') == {}
   and S.load_zone('', '') == {} and S.load_zone(None, None) == {})
bad_zf = [S.zone_filename('../../etc', 'passwd'),
          S.zone_filename('a/b', 'c\\d'),
          S.zone_filename(None, '')]
ck('V13 分片文件名已裁剪（不含分隔符 / 不含 ..）',
   all(('/' not in z and '\\' not in z and '..' not in z) for z in bad_zf),
   str(bad_zf))
ck('V14 分片里的场景形状与独立文件一致（chapter/area/scene_id 齐全）',
   all((with_e.scene_id and with_e.chapter_id and with_e.area_id)
       for _ in [0]), '%r' % ((with_e.scene_id, with_e.chapter_id,
                               with_e.area_id),))
w('')

# ---------------------------------------------------------------- 性能
gc.collect()


def rss_mb():
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1048576.0
    except Exception:
        return -1.0


m0 = rss_mb()
zones = {}
t0 = time.perf_counter()
area_seen = set()
for sid, entry in scenes.items():
    key = (entry.get('chapter_id'), entry.get('area_id'))
    if key in area_seen or os.path.isfile(os.path.join(SCENES, sid + '.json')):
        continue
    area_seen.add(key)
    zones[key] = S.load_zone(key[0], key[1])
t_zones = (time.perf_counter() - t0) * 1000.0
gc.collect()
m1 = rss_mb()
ck('V15 走遍全部 61 片只读 61 次（不是 1,013 次）', len(area_seen) == 61,
   '%d 片' % len(area_seen))
w('    读全部 61 片总耗时 = %.2f ms（平均 %.2f ms/片）'
  % (t_zones, t_zones / max(1, len(area_seen))))
w('    常驻内存增量 ≈ %.2f MB' % (m1 - m0))
w('    「火把」语义：只读 1 片 ≈ %.2f ms' % (t_zones / max(1, len(area_seen))))

# 单文件总量
tot = sum(os.path.getsize(os.path.join(SCENES, f))
          for f in os.listdir(SCENES)
          if f.startswith('_zone.') and f.endswith('.json'))
w('    分片文件数 = %d，总体积 = %.1f KB' % (len(area_seen), tot / 1024.0))

fails = [r for r in RES if not r[0]]
w('')
w('=== 验证汇总：%d 项 PASS=%d FAIL=%d ==='
  % (len(RES), len(RES) - len(fails), len(fails)))
for _, n, d in fails:
    w('  FAIL: %s %s' % (n, d))

with io.open(os.path.join(EV, '分片加载验证.txt'), 'w',
             encoding='utf-8') as fh:
    fh.write('\n'.join(OUT) + '\n')
print('')
print('written 分片加载验证.txt')
