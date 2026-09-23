# -*- coding: utf-8 -*-
"""第 38 轮：把 1,251 个 room 分成「可当场景 / 非场景」并计数。

分类规则（保守：宁可多留，不误杀 —— 本项目铁律"误杀比漏过更糟"）：
  非场景 = 引擎占位 / 测试 / 调试 / 空房 / 结局演出屏
  其余   = 可当场景（真实地点，一屏一房间）
"""
import io
import json
import os
import re

DR = r'E:\Download\_tmp\dr_out'
PAIRS = [('ch1', 'chapter1_windows'), ('ch2', 'chapter2_windows'),
         ('ch3', 'chapter3_windows'), ('ch4', 'chapter4_windows'),
         ('ch5', 'chapter5_windows')]
EV = (r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
      r'\code-quality-audit\第38轮-场景系统审查\_evidence')

# 非场景判据（逐条给理由，便于人眼复核/日后放宽）
NONSCENE = [
    (re.compile(r'^ROOM_INITIALIZE$'), '引擎初始化房'),
    (re.compile(r'^PLACE_'), '引擎占位房（PLACE_CONTACT/DOG/LOGO/FAILURE/MENU）'),
    (re.compile(r'debug|failsafe', re.I), '调试/故障保护房'),
    (re.compile(r'test', re.I), '测试房（battletest/bullettest/animtest…）'),
    (re.compile(r'title_placeholder', re.I), '标题占位房'),
    (re.compile(r'^(room_empty|room_DARKempty)$'), '空房'),
    (re.compile(r'^(room_gameover|room_ed|room_splashscreen|room_man)$'),
     '演出/系统屏'),
    (re.compile(r'room_title', re.I), '标题屏'),
]
MAYBE = [
    (re.compile(r'^(room_legend|room_chapter_continue)$'), '剧情演出（有内容但不是"地点"）'),
    (re.compile(r'^(room_shop1|room_shop2)$'), '商店/系统菜单房'),
    (re.compile(r'room_myroom_dark'), '暗世界版自己房间（与 room_krisroom 重复地点）'),
    (re.compile(r'unusedroom', re.I), '原作标注 unused 的房间'),
]


def classify(name):
    for rx, why in NONSCENE:
        if rx.search(name):
            return 'nonscene', why
    for rx, why in MAYBE:
        if rx.search(name):
            return 'maybe', why
    return 'scene', ''


out = []


def w(s=''):
    out.append(str(s))
    print(s)


grand = {'scene': 0, 'maybe': 0, 'nonscene': 0}
detail = {}
for ch, folder in PAIRS:
    with io.open(os.path.join(DR, folder, 'rooms_map.json'), 'r',
                 encoding='utf-8') as fh:
        data = json.load(fh)
    rooms = data.get('rooms') if isinstance(data, dict) else data
    rooms = [r for r in (rooms or []) if isinstance(r, dict)]
    cnt = {'scene': 0, 'maybe': 0, 'nonscene': 0}
    kept, drop = [], []
    for r in rooms:
        n = str(r.get('name') or '')
        k, why = classify(n)
        cnt[k] += 1
        grand[k] += 1
        (kept if k == 'scene' else drop).append((n, k, why))
    detail[ch] = {'total': len(rooms), 'cnt': cnt, 'kept': [k[0] for k in kept],
                  'drop': drop}
    w('%-4s room=%-4d  可当场景=%-4d  待裁=%-3d  非场景=%-4d'
      % (ch, len(rooms), cnt['scene'], cnt['maybe'], cnt['nonscene']))

w('')
w('五章合计：room=%d  可当场景=%d  待裁=%d  非场景=%d'
  % (sum(v['total'] for v in detail.values()), grand['scene'],
     grand['maybe'], grand['nonscene']))
w('我们当前已登记场景 = 87')
w('')

w('--- 各类非场景清单（全部列名，便于复核）---')
seen = {}
for ch, v in detail.items():
    for n, k, why in v['drop']:
        seen.setdefault((k, why), []).append('%s:%s' % (ch, n))
for (k, why), lst in sorted(seen.items()):
    w('[%s] %s  (%d 个)' % (k, why, len(lst)))
    for x in lst:
        w('    %s' % x)
w('')

os.makedirs(EV, exist_ok=True)
p = os.path.join(EV, '可当场景房间分类.txt')
with io.open(p, 'w', encoding='utf-8') as fh:
    fh.write('\n'.join(out) + '\n')
    fh.write('\n' + '=' * 60 + '\n可当场景的房间名（逐章）\n')
    for ch, v in detail.items():
        fh.write('\n--- %s (%d) ---\n' % (ch, len(v['kept'])))
        for n in v['kept']:
            fh.write('  %s\n' % n)

jp = os.path.join(EV, '可当场景房间.json')
with io.open(jp, 'w', encoding='utf-8') as fh:
    json.dump(detail, fh, ensure_ascii=False, indent=1)
print('written:', p)
