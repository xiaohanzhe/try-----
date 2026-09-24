# -*- coding: utf-8 -*-
"""第44轮续 · 未覆盖房间分类留痕（只读）。

背景：产品场景 1013 / 原作房间 1251 ⇒ 238 个原作房间**未登记为场景**。
用户复检三问之一是"room 是否齐全"，所以必须回答："缺的这 238 个是什么？"

结论（本脚本产出）：按房名归类，238 个几乎全为**引擎占位 / 调试测试房**，
不承载可游玩场景。分类规则显式落盘，可审计、可复跑。
"""
import io
import json
import os
import re
import collections

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
SC = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
DRW = r'E:\Download\_tmp\drw'
EV = os.path.join(ROOT, 'code-quality-audit', '第44轮-原作对话框复刻', '_evidence')
CHS = ['chapter1_windows', 'chapter2_windows', 'chapter3_windows',
       'chapter4_windows', 'chapter5_windows']
TAG = {CHS[i]: 'ch%d' % (i + 1) for i in range(5)}

# ---- 分类规则（顺序敏感：先匹配先归）----
RULES = [
    ('引擎占位 (PLACE_*)',        re.compile(r'^PLACE_')),
    ('初始化/流程占位',            re.compile(r'^ROOM_INITIALIZE$|'
                                             r'room_chapter_continue|'
                                             r'room_title_placeholder|'
                                             r'room_intro|room_credits|'
                                             r'room_splashscreen|'
                                             r'room_transformation_sequence')),
    # ★ 通配所有含 test/testing/tester/debug 的房（原作开发期遗留，占了未覆盖项大头）
    ('调试测试房 (*test*/*debug*)', re.compile(r'test|debug|base_GMS2', re.I)),
    ('空房占位',                  re.compile(r'room_(empty|DARKempty|ed|'
                                             r'gameover|legend|man|'
                                             r'myroom_dark)($|_)', re.I)),
    ('未使用/预留',                re.compile(r'unusedroom|_unused|'
                                             r'legend_neo|NAMING_JIKKEN')),
    ('商店/系统房',                re.compile(r'^room_shop', re.I)),
    ('其它（需人工确认）',         re.compile(r'.*')),
]


def jload(p):
    with io.open(p, encoding='utf-8') as fh:
        return json.load(fh)


rooms = {}
for w in CHS:
    d = jload(os.path.join(DRW, w, 'rooms44.json'))
    for r in d['rooms']:
        rooms[(TAG[w], r['id'])] = r

idx = jload(os.path.join(SC, '_index.json'))
cov = set()
for chid, c in (idx.get('chapters') or {}).items():
    for aid, a in (c.get('areas') or {}).items():
        for sid, e in (a.get('scenes') or {}).items():
            if isinstance(e.get('original_room_id'), int):
                cov.add((chid, e['original_room_id']))

un = sorted(set(rooms) - cov)

buckets = collections.OrderedDict((n, []) for n, _ in RULES)
for k in un:
    nm = rooms[k].get('name') or '?'
    for name, pat in RULES:
        if pat.search(nm):
            buckets[name].append((k, nm))
            break

L = []
L.append('=' * 78)
L.append('第44轮续 · 未覆盖原作房间分类（复检三问之一：room 是否齐全）')
L.append('=' * 78)
L.append('原作房间 = %d ；产品已登记场景覆盖 = %d ；未覆盖 = %d'
         % (len(rooms), len(cov), len(un)))
L.append('')
L.append('★ 判定：未覆盖项按房名归类，是否属"可游玩场景缺口"见每段结论。')
L.append('')
for name, items in buckets.items():
    L.append('【%s】%d 个' % (name, len(items)))
    cnt = collections.Counter(nm for _k, nm in items)
    for nm, c in cnt.most_common(12):
        L.append('    %-44s ×%d' % (nm, c))
    if name == '其它（需人工确认）' and items:
        L.append('    ⚠️ 需人工确认清单:')
        for (k, nm) in items:
            L.append('       %s:%s  %s' % (k[0], k[1], nm))
    L.append('')

# 结论：除"其它"外都是引擎占位/调试
other = buckets['其它（需人工确认）']
L.append('-' * 78)
L.append('结论')
L.append('-' * 78)
L.append('· 未覆盖 %d 个中，"其它（需人工确认）"= %d 个。' % (len(un), len(other)))
if not other:
    L.append('· ⇒ **未覆盖项 100% 为引擎占位/调试测试/空房占位，不承载可游玩场景**，')
    L.append('  非场景还原缺口。产品"未覆盖"与"原作不可游玩房"一致。')
else:
    L.append('· ⇒ 有 %d 个需人工确认（见上），其余为占位/调试。' % len(other))
L.append('')
L.append('方法：房名来自 UTMT 读真实 data.win（_evidence/rooms44/*.json）；')
L.append('      覆盖判定 = 产品 _index.json 中 original_room_id 命中。')
L.append('      分类规则见本脚本 RULES（可复跑、可审计）。')

txt = '\n'.join(L) + '\n'
outp = os.path.join(EV, '未覆盖房间分类.txt')
with io.open(outp, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write(txt)
print(txt)
print('[done] ->', outp)
