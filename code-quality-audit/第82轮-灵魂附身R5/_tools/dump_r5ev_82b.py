# -*- coding: utf-8 -*-
u"""第82轮 · 把 ut_r5b_code.json 里的关键段落盘到 _evidence/。

★ 白名单挑选（与 r5b 过滤器同名），只落关键段，不生搬 19 段全量。
"""
import io, json, os

BASE = r'E:\Download\_tmp\r5_82\_data'
SRC = os.path.join(BASE, 'ut_r5b_code.json')
DST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_evidence')
if not os.path.isdir(DST):
    os.makedirs(DST)

# 只落这些（关键 + 有内容的）
KEEP = [
    'gml_Object_obj_time_Create_0',
    'gml_Object_obj_time_Step_1',
    'gml_Object_obj_time_Step_2',
    'gml_Object_obj_time_KeyPress_114',
    'gml_Object_obj_interactable_PreCreate_0',
    'gml_Object_obj_doorparent_PreCreate_0',
]

d = json.load(io.open(SRC, 'r', encoding='utf-8'))
codes = {c['name']: c['src'] for c in d['codes']}
written = 0
for name in KEEP:
    if name not in codes:
        print('[miss] %s' % name); continue
    src = codes[name]
    out = os.path.join(DST, name + '.gml')
    with io.open(out, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(src)
    print('[ok] %-46s %6d B -> %s' % (name, len(src.encode('utf-8')), os.path.basename(out)))
    written += 1

print('written=%d' % written)
