# -*- coding: utf-8 -*-
"""修正 `_original_rooms.json`（原作 scr_roomname 的转写）两处偏差。

依据（`_evidence/` 里的取证文件）：
  · `scr_roomname_覆盖核对.txt` —— 逐章比对 scr_roomname 分支集合 vs 本文件登记 id：
        ch1 20/20 ✅   ch2 20 vs 22 ❌（多 199/200）   ch3 9/9 ✅
        ch4 20/20 ✅   ch5 26 vs 21 ❌（漏 205/222/224/225/230）
  · `ch5漏登记与ch2多登记.txt` —— 给出 ch5 那 5 条的真实资源名与显示名。

做法：**文本级替换**（不 json.dump 重排），保持原格式（2 空格缩进 + rooms 一行一条 + LF）。
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
P = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', '_original_rooms.json')

raw = io.open(P, encoding='utf-8').read()
orig = raw

log = []


def sub(old, new, tag):
    global raw
    assert old in raw, '找不到锚点：%s' % tag
    n = raw.count(old)
    assert n == 1, '锚点不唯一(%d)：%s' % (n, tag)
    raw = raw.replace(old, new)
    log.append('OK  %s' % tag)


# ---------------------------------------------------------------- 1. 删 ch2 的 199/200
OLD_CH2 = ('        {"id": 196, "name": "Queen\'s Mansion - 4F"},\n'
           '        {"id": 199, "name": "Queen\'s Mansion - Rooftop"},\n'
           '        {"id": 200, "name": "Queen\'s Mansion - Rooftop"}\n')
NEW_CH2 = '        {"id": 196, "name": "Queen\'s Mansion - 4F"}\n'
sub(OLD_CH2, NEW_CH2, '① ch2 删 199/200（scr_roomname 无这两个分支）')

# ---------------------------------------------------------------- 2. 重排 + 补 ch5 的 5 条
CH5_ROOMS = [
    (0, '---'),
    (13, "Kris's Room"),
    (24, 'Hometown'),
    (54, 'My Castle Town'),
    (112, 'Castle Town - TV Building'),
    (120, 'Dark World'),
    (122, 'Garden - Beginning'),
    (129, 'Garden - Flowery Helped'),
    (133, 'Garden - Ideal Diner'),
    (141, 'Garden - Shrine'),
    (144, 'Cliffs - Beginning'),          # ← 原文件里排在 150 之后（乱序），本次一并按 id 排好
    (150, 'Garden - Way Home'),
    (161, 'Cliffs - Shop'),
    (167, 'Cliffs - Below Castle'),
    (177, 'Flower Castle - Cafe'),
    (179, 'Flower Castle - Jail'),
    (183, 'Flower Castle - Left Doors'),
    (187, 'Flower Castle - Left Stage'),
    (189, 'Flower Castle - Left End'),
    (202, 'Flower Castle - Right Diner'),
    (205, 'Flower Castle - Right View'),      # ← 新增（原漏登）
    (207, 'Flower Castle - Right End'),
    (222, 'Top of Castle - Beginning'),       # ← 新增
    (224, "Top of Castle - Green's Shop"),    # ← 新增
    (225, 'Top of Castle - Castle Top'),      # ← 新增
    (230, 'Top of Castle - Boss?'),           # ← 新增
]
assert len(CH5_ROOMS) == 26, len(CH5_ROOMS)

lines = ['        {"id": %d, "name": %s}' % (i, json.dumps(nm, ensure_ascii=False))
         for i, nm in CH5_ROOMS]
lines = [l + ',' for l in lines[:-1]] + [lines[-1]]
NEW_CH5 = '\n'.join(lines) + '\n'

# 旧 ch5 rooms 段（从 id 0 到 id 207 的那一行）
i0 = raw.find('        {"id": 0, "name": "---"},\n        {"id": 13, "name": "Kris\'s Room"},\n'
              '        {"id": 24, "name": "Hometown"},')
assert i0 > 0, '找不到 ch5 rooms 起点'
END_ANCHOR = '        {"id": 207, "name": "Flower Castle - Right End"}\n'
i1 = raw.find(END_ANCHOR, i0)
assert i1 > 0, '找不到 ch5 rooms 终点'
OLD_CH5 = raw[i0:i1 + len(END_ANCHOR)]
raw = raw[:i0] + NEW_CH5 + raw[i1 + len(END_ANCHOR):]
log.append('OK  ② ch5 rooms 按 id 重排 + 补 205/222/224/225/230（26 条）')

# ---------------------------------------------------------------- 3. areas：flower_castle 并上 "Top of Castle"
OLD_AREAS = ('        "flower_castle": ["Flower Castle"]')
NEW_AREAS = ('        "flower_castle": ["Flower Castle", "Top of Castle"]')
sub(OLD_AREAS, NEW_AREAS,
    '③ ch5.areas：flower_castle 并上 "Top of Castle" 前缀（与全量房间表口径一致）')

# ---------------------------------------------------------------- 4. meta 里留痕
OLD_USAGE = ('    "usage": "本文件是**只读参考数据**，不参与运行时加载。'
             '场景登记表是 _index.json；本文件是它的依据与溯源。"')
NEW_USAGE = (
    '    "corrections": [\n'
    '      "第 38 轮：ch2 删除 id 199/200 —— scr_roomname 里没有这两个分支（原转写多录）。",\n'
    '      "第 38 轮：ch5 补登 id 205/222/224/225/230 —— 原转写漏了这 5 个分支。'
    '补登后逐章分支数与 scr_roomname 一致：ch1 20 / ch2 20 / ch3 9 / ch4 20 / ch5 26。",\n'
    '      "第 38 轮：ch5 的 rooms 一并按 id 升序排好（原先 144 排在 150 之后）。",\n'
    '      "第 38 轮：ch5.areas 的 flower_castle 并上 \\"Top of Castle\\" 前缀 —— 原作显示名虽然'
    '分成两段，但**我们的区域桶**（见 房间表_全量.json）把它们统一归在 flower_castle。"\n'
    '    ],\n' + OLD_USAGE)
sub(OLD_USAGE, NEW_USAGE, '④ meta 增补 corrections（本次修正的留痕）')

# ---------------------------------------------------------------- 写出 + 校验
assert raw != orig, '没有任何改动'
assert '\r\n' not in raw, '出现了 CRLF'
io.open(P, 'w', encoding='utf-8', newline='').write(raw)

b = io.open(P, 'rb').read()
assert list(b[:3]) != [239, 187, 191], '写出后带 BOM'
assert b.count(b'\xef\xbf\xbd') == 0, '写出后含 U+FFFD'

d = json.loads(raw)
print('\n'.join(log))
print()
print('=== 校验（scr_roomname 分支数作参照）===')
EXPECT = {'ch1': 20, 'ch2': 20, 'ch3': 9, 'ch4': 20, 'ch5': 26}
allok = True
for cid, exp in EXPECT.items():
    rooms = d['chapters'][cid]['rooms']
    ids = [r['id'] for r in rooms]
    same = len(rooms) == exp
    sorted_ok = ids == sorted(ids)
    dup = len(ids) != len(set(ids))
    allok = allok and same and sorted_ok and not dup
    print('  %-4s n=%-3d (期望 %-3d) %s   id升序=%s  无重复=%s'
          % (cid, len(rooms), exp, 'OK ' if same else 'FAIL', sorted_ok, not dup))
print()
print('bytes=%d  (改前 %d)  LF-only=%s'
      % (len(b), len(orig.encode('utf-8')), b.count(b'\r\n') == 0))
print('全部校验:', 'PASS' if allok else 'FAIL')
sys.exit(0 if allok else 1)
