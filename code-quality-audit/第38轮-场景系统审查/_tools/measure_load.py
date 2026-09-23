# -*- coding: utf-8 -*-
"""第 38 轮：实测"全量加载 1,013 个场景"的真实开销，用数据决定是否需要火把式惰性加载。

测三件事：
  A. 一份**完整场景表**（1,013 条、产品会用的字段形状）序列化后多大、json.loads 多快
  B. 走**单个大文件** vs 走 **1,013 个小文件** vs 走 **32 个区域分片** 的读取耗时
  C. 常驻内存增量

只写 E:\\Download\\_tmp\\（临时），不碰仓库。
"""
import io
import json
import os
import shutil
import sys
import tempfile
import time

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
EV = os.path.join(ROOT, 'code-quality-audit', '第38轮-场景系统审查', '_evidence')
# ⚠️ E:\Download\_tmp 下 `os.makedirs` 被沙箱拦（WinError 1）；%TEMP% 可用 —— 实测为准
TMP = os.path.join(tempfile.gettempdir(), 's38_measure')

with io.open(os.path.join(EV, '房间表_全量.json'), 'r', encoding='utf-8') as fh:
    table = json.load(fh)

# --- 构造产品形状的场景表 ---
scenes = []
for ch, recs in table.items():
    for r in recs:
        if r['cls'] != 'scene':
            continue
        scenes.append({
            'scene_id': '%s.%s.%s' % (ch, r['area_id'], r['resource'].replace('room_', '')),
            'name': (r.get('anchor_name') or r['resource']),
            'chapter_id': ch, 'chapter_name': ch,
            'area_id': r['area_id'], 'area_name': r['area_name'],
            'bg': 'bg/%s.png' % r['resource'].replace('room_', ''),
            'bgm': None,
            'ambient': {'lighting': None, 'weather': None, 'particles': None},
            'objects': [], 'anchors': {}, 'transition': None,
            'original_room_id': r['room_index'],
            'original_resource': r['resource'],
        })
n = len(scenes)
print('场景数 =', n)

blob = json.dumps(scenes, ensure_ascii=False, indent=1)
b = blob.encode('utf-8')
print('A. 单文件 JSON 体积 = %d B = %.1f KB' % (len(b), len(b) / 1024))

# --- A. json.loads 耗时（best of 7）---
ts = []
for _ in range(7):
    t0 = time.perf_counter()
    json.loads(blob)
    ts.append(time.perf_counter() - t0)
print('   json.loads 耗时 min=%.2f ms  median=%.2f ms'
      % (min(ts) * 1000, sorted(ts)[len(ts) // 2] * 1000))

# --- B. 三种物理布局的读取耗时 ---
if os.path.isdir(TMP):
    shutil.rmtree(TMP, ignore_errors=True)
os.makedirs(TMP)

# B1: 单文件
p_all = os.path.join(TMP, '_all_scenes.json')
with io.open(p_all, 'w', encoding='utf-8') as fh:
    fh.write(blob)
t0 = time.perf_counter()
with io.open(p_all, 'r', encoding='utf-8') as fh:
    _ = json.load(fh)
t_all = time.perf_counter() - t0

# B2: 1,013 个小文件
d_one = os.path.join(TMP, 'one')
os.makedirs(d_one)
for s in scenes:
    with io.open(os.path.join(d_one, s['scene_id'] + '.json'), 'w',
                 encoding='utf-8') as fh:
        json.dump({'room_index': s['original_room_id'],
                   'original_resource': s['original_resource']}, fh,
                  ensure_ascii=False)
t0 = time.perf_counter()
cnt = 0
for fn in os.listdir(d_one):
    with io.open(os.path.join(d_one, fn), 'r', encoding='utf-8') as fh:
        json.load(fh)
    cnt += 1
t_one = time.perf_counter() - t0

# B3: 32 个区域分片
d_sh = os.path.join(TMP, 'shard')
os.makedirs(d_sh)
by_area = {}
for s in scenes:
    by_area.setdefault(s['area_id'], []).append(s)
for aid, lst in by_area.items():
    with io.open(os.path.join(d_sh, aid + '.json'), 'w', encoding='utf-8') as fh:
        json.dump(lst, fh, ensure_ascii=False, indent=1)
t0 = time.perf_counter()
got = 0
for fn in os.listdir(d_sh):
    with io.open(os.path.join(d_sh, fn), 'r', encoding='utf-8') as fh:
        got += len(json.load(fh))
t_shard = time.perf_counter() - t0

print('B. 读取全部场景：')
print('   单文件        = %6.2f ms' % (t_all * 1000))
print('   %d 个小文件   = %6.2f ms  (逐个 open)' % (cnt, t_one * 1000))
print('   %d 个区域分片 = %6.2f ms  (读到 %d 条)'
      % (len(by_area), t_shard * 1000, got))

# --- C. 内存 ---
try:
    import psutil
    proc = psutil.Process()
    before = proc.memory_info().rss
    holder = json.loads(blob)
    after = proc.memory_info().rss
    print('C. 常驻内存增量 ≈ %.2f MB' % ((after - before) / 1048576))
    del holder
except Exception as e:
    print('C. psutil 不可用：', e)

# --- 分片体积 ---
tot = sum(os.path.getsize(os.path.join(d_sh, f)) for f in os.listdir(d_sh))
print('')
print('分片总体积 = %.1f KB（%d 个文件）' % (tot / 1024, len(os.listdir(d_sh))))
print('小文件总体积 = %.1f KB' % (
    sum(os.path.getsize(os.path.join(d_one, f)) for f in os.listdir(d_one)) / 1024))
