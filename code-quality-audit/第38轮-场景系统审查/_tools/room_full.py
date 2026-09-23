# -*- coding: utf-8 -*-
"""第 38 轮：把原作五章 room 名字**全量**导出 + 校验 id↔scene 映射假设。

只读。
关键待验证假设：`_original_rooms.json` 的 `id` 就是 `rooms_map.json` 的下标
（第 37 轮说"ch1 的 20 个房间全对上"，本脚本要独立复核，不引用那个结论）。
"""
import io
import json
import os
import re

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
DR = r'E:\Download\_tmp\dr_out'
PAIRS = [('ch1', 'chapter1_windows'), ('ch2', 'chapter2_windows'),
         ('ch3', 'chapter3_windows'), ('ch4', 'chapter4_windows'),
         ('ch5', 'chapter5_windows')]
EV = os.path.join(ROOT, 'code-quality-audit', '第38轮-场景系统审查', '_evidence')

out = []


def w(s=''):
    out.append(str(s))
    print(s)


with io.open(os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes',
                          '_original_rooms.json'), 'r', encoding='utf-8') as fh:
    ORIG = json.load(fh)

# ---- 1. id 对齐复核 ----
w('=== 1. `_original_rooms.json` 的 id 是否等于 rooms_map 下标 ===')
roommaps = {}
for ch, folder in PAIRS:
    with io.open(os.path.join(DR, folder, 'rooms_map.json'), 'r',
                 encoding='utf-8') as fh:
        data = json.load(fh)
    rooms = data.get('rooms') if isinstance(data, dict) else data
    roommaps[ch] = [r for r in (rooms or []) if isinstance(r, dict)]

mismatch = []
allnames = {}
for ch, folder in PAIRS:
    rooms = roommaps[ch]
    entry = (ORIG.get('chapters') or {}).get(ch) or {}
    for r in entry.get('rooms') or []:
        rid = r.get('id')
        nm = r.get('name')
        got = rooms[rid]['name'] if isinstance(rid, int) and 0 <= rid < len(rooms) else '<越界>'
        allnames.setdefault(ch, []).append((rid, nm, got))
        # 判据不做"字符串相似"猜测，只打印，人眼/后续脚本核
print('（下面逐条列 id → scr_roomname 名 vs rooms_map[id] 资源名）')
for ch, rows in allnames.items():
    w('--- %s (%d 条) ---' % (ch, len(rows)))
    for rid, nm, got in rows:
        w('  id=%-4s 显示名=%-28s 资源名=%s' % (rid, nm, got))
w('')

# ---- 2. 全量名字 ----
w('=== 2. 五章 room 资源名全量 ===')
for ch, folder in PAIRS:
    rooms = roommaps[ch]
    names = [str(r.get('name') or '') for r in rooms]
    w('--- %s  %d 个 room ---' % (ch, len(rooms)))
    for i, n in enumerate(names):
        w('  [%3d] %s' % (i, n))
    w('')

os.makedirs(EV, exist_ok=True)
p = os.path.join(EV, '原作房间全量清单.txt')
with io.open(p, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(out) + '\n')
print('written:', p)
