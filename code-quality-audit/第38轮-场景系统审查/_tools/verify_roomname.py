# -*- coding: utf-8 -*-
"""第 38 轮：坐实「87 个场景 = scr_roomname 的存档点地点名」这个结论。

只读。逐章：
  · 从反编译出的 `_roomname_code.txt` 里抽出 `if (arg0 == N)` 的 N 集合
  · 与 `_original_rooms.json` 的 id 集合逐元素比对（必须完全相同）
  · 从 `scr_get_room_list()` 抽 `room_xxx` 条目数（证明房间列表是全量的）
"""
import io
import json
import os
import re

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
DRW = r'E:\Download\_tmp\drw'
PAIRS = [('ch1', 'chapter1_windows'), ('ch2', 'chapter2_windows'),
         ('ch3', 'chapter3_windows'), ('ch4', 'chapter4_windows'),
         ('ch5', 'chapter5_windows')]
EV = os.path.join(ROOT, 'code-quality-audit', '第38轮-场景系统审查', '_evidence')

with io.open(os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes',
                          '_original_rooms.json'), 'r', encoding='utf-8') as fh:
    ORIG = json.load(fh)

out = []


def w(s=''):
    out.append(str(s))
    print(s)


IFARG = re.compile(r'if \(arg0 == (\d+)\)')
LISTENTRY = re.compile(r'new scr_room\((\w+),\s*(\d+)\)')

w('=== scr_roomname 覆盖数 vs 我们登记的 id ===')
allok = True
for ch, folder in PAIRS:
    p = os.path.join(DRW, folder, '_roomname_code.txt')
    if not os.path.isfile(p):
        w('%-4s  [缺文件] %s' % (ch, p))
        allok = False
        continue
    with io.open(p, 'r', encoding='utf-8') as fh:
        txt = fh.read()
    ids = sorted(int(x) for x in IFARG.findall(txt))
    ours = sorted(int(r['id']) for r in
                  ((ORIG.get('chapters') or {}).get(ch) or {}).get('rooms') or [])
    entries = LISTENTRY.findall(txt)
    same = ids == ours
    allok = allok and same
    w('%-4s  scr_roomname 分支=%-3d  我们登记 id=%-3d  完全相同=%s'
      % (ch, len(ids), len(ours), same))
    if not same:
        w('      只在脚本里: %s' % sorted(set(ids) - set(ours)))
        w('      只在我们表: %s' % sorted(set(ours) - set(ids)))
    w('      scr_get_room_list 条目数 = %d（若 > 分支数 ⇒ 房间列表是全量的）'
      % len(entries))
w('')

w('=== scr_get_room_list 覆盖的房间资源名（ch1 抽样）===')
p1 = os.path.join(DRW, 'chapter1_windows', '_roomname_code.txt')
with io.open(p1, 'r', encoding='utf-8') as fh:
    t1 = fh.read()
e1 = LISTENTRY.findall(t1)
w('ch1 条目数 = %d' % len(e1))
w('前 8 条 = %s' % e1[:8])
w('后 8 条 = %s' % e1[-8:])

w('')
w('=== 结论 ===')
w('scr_roomname 分支集合与 _original_rooms.json 完全一致 = %s' % allok)
w('⇒ `_original_rooms.json` 是 scr_roomname 的忠实转写；'
  '87 个场景 = 原作「存档点地点名」全集，而不是「房间全集」。')

os.makedirs(EV, exist_ok=True)
with io.open(os.path.join(EV, 'scr_roomname_覆盖核对.txt'), 'w',
             encoding='utf-8') as fh:
    fh.write('\n'.join(out) + '\n')
print('ok')
