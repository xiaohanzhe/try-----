# -*- coding: utf-8 -*-
"""第 38 轮：原作 1251 个 room 的**名字分布** —— 判断哪些才是"真场景"。

只读。输出：
  · 每章 unique 名字数 / 技术房间数 / 名字重复情况
  · 每章完整 unique 名字清单（落盘，供人眼过）
"""
import io
import json
import os
import re
from collections import Counter, OrderedDict

DR = r'E:\Download\_tmp\dr_out'
CHS = [('ch1', 'chapter1_windows'), ('ch2', 'chapter2_windows'),
       ('ch3', 'chapter3_windows'), ('ch4', 'chapter4_windows'),
       ('ch5', 'chapter5_windows')]

out = []
EV = (r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
      r'\code-quality-audit\第38轮-场景系统审查\_evidence')


def w(s=''):
    out.append(str(s))
    print(s)


TECH = re.compile(r'^(ROOM_|room_|obj_|__|test|Test|Dummy|dummy)', re.I)

summary = {}
for ch, folder in CHS:
    p = os.path.join(DR, folder, 'rooms_map.json')
    with io.open(p, 'r', encoding='utf-8') as fh:
        data = json.load(fh)
    # 有的章是 {"rooms": [...]}，有的是裸 list —— 两种都吃掉。
    rooms = data.get('rooms') if isinstance(data, dict) else data
    rooms = [r for r in (rooms or []) if isinstance(r, dict)]
    names = [str(r.get('name') or '') for r in rooms]
    tech = [n for n in names if TECH.match(n) or not n]
    techset = set(tech)
    real = [n for n in names if n not in techset]

    uniq_all = OrderedDict((n, None) for n in names)
    uniq_real = OrderedDict((n, None) for n in real)
    dup = [n for n, c in Counter(real).items() if c > 1]

    summary[ch] = {
        'rooms': len(rooms),
        'tech': len(tech),
        'tech_unique': len(techset),
        'real_instances': len(real),
        'real_unique': len(uniq_real),
        'dup_names': sorted(dup),
        'names': list(uniq_real),
    }
    w('=== %s ===' % ch)
    w('  room 总数        = %d' % len(rooms))
    w('  技术房间(实例)   = %d  (unique %d)' % (len(tech), len(techset)))
    w('  技术房间名       = %s' % sorted(techset)[:12])
    w('  非技术(实例)     = %d  →  unique 名字 = %d'
      % (len(real), len(uniq_real)))
    w('  重名(同名多房间) = %d 个名字 %s'
      % (len(dup), dup[:8]))
    w('')

w('--- 汇总 ---')
tot_rooms = sum(v['rooms'] for v in summary.values())
tot_tech = sum(v['tech'] for v in summary.values())
tot_real_i = sum(v['real_instances'] for v in summary.values())
tot_real_u = sum(v['real_unique'] for v in summary.values())
w('五章 room 实例合计      = %d' % tot_rooms)
w('其中技术房间            = %d' % tot_tech)
w('非技术房间（实例）      = %d' % tot_real_i)
w('非技术 unique 名字合计  = %d  ← 跨章相加（含跨章重名）' % tot_real_u)
allnames = set()
for v in summary.values():
    allnames |= set(v['names'])
w('非技术 unique 名字去重  = %d' % len(allnames))
w('我们已登记场景          = 87')
w('')

# 落盘完整清单
os.makedirs(EV, exist_ok=True)
p1 = os.path.join(EV, '原作房间名字清单.txt')
with io.open(p1, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(out) + '\n\n')
    for ch, v in summary.items():
        fh.write('=' * 60 + '\n%s  unique 非技术房间名 %d 个\n' % (ch, len(v['names'])))
        for n in v['names']:
            fh.write('  %s\n' % n)

jsonp = os.path.join(EV, '原作房间名字.json')
with io.open(jsonp, 'w', encoding='utf-8') as fh:
    json.dump({ch: {k: v2 for k, v2 in v.items()} for ch, v in summary.items()},
              fh, ensure_ascii=False, indent=1)
print('written:', p1)
print('written:', jsonp)
