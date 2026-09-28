# -*- coding: utf-8 -*-
"""OneShot WME 数据层勘查。

★ 坑：`gamedata/*.json` 由 Newtonsoft.Json 写出，**允许尾逗号**（如
  oneshot_map_zone_names.json 最后一项后仍带 `,`）—— 标准 `json.load` 会直接抛。
  ⇒ 勘查器必须容忍尾逗号，否则会得出"文件坏了"的错误结论。
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SUB = r'C:\Users\23002\Desktop\项目文件夹\niko的秘密\OneShot.World.Machine.Edition.Build.16512634'
GD = os.path.join(SUB, 'gamedata')

_TRAIL = re.compile(r',(\s*[}\]])')


def loose(text):
    """去掉对象/数组里最后一个元素后的逗号，再解析。"""
    prev = None
    while prev != text:
        prev = text
        text = _TRAIL.sub(r'\1', text)
    return json.loads(text)


def load(*parts):
    p = os.path.join(GD, *parts)
    return loose(io.open(p, encoding='utf-8').read())


print('=' * 78)
for f in ('oneshot_map_zone_names.json', 'oneshot_map_names.json'):
    d = load(f)
    print('[%s] %s len=%d' % (f, type(d).__name__, len(d)))
    if isinstance(d, dict):
        for k, v in list(d.items())[:20]:
            print('    %-10s -> %s' % (k, v))
    else:
        # map_names: {"map_names":[...]}
        lst = d.get('map_names') if isinstance(d, dict) else d
        print('    前 20 项:', [(x.get('id'), x.get('name')) for x in lst[:20]])
    print()

print('=' * 78)
print('items / vars / flags')
for f in ('oneshot_items.json', 'oneshot_var_names.json', 'oneshot_flag_names.json'):
    d = load(f)
    top = list(d.keys())
    print('  %-30s keys=%s' % (f, top))
    for k in top:
        v = d[k]
        print('        %-18s %s len=%d' % (k, type(v).__name__, len(v)))
    print()

print('=' * 78)
MD = os.path.join(GD, 'maps')
fs = [f for f in os.listdir(MD) if f.startswith('events_map')]
print('events_map 文件数 =', len(fs))
sizes = sorted(((os.path.getsize(os.path.join(MD, f)), f) for f in fs), reverse=True)
print('最大 5:', sizes[:5])
print('最小 5:', sizes[-5:])

print()
for name in ('events_map12.json', 'events_map1.json'):
    p = os.path.join(MD, name)
    d = loose(io.open(p, encoding='utf-8').read())
    print('--- %s : %s ---' % (name, type(d).__name__))
    if isinstance(d, dict):
        print('   keys =', list(d.keys())[:20])
        for k in list(d.keys())[:2]:
            print('   [%s] =' % k, json.dumps(d[k], ensure_ascii=False)[:500])
    else:
        print('   len =', len(d))
        if d:
            print('   首元素 =', json.dumps(d[0], ensure_ascii=False)[:500])
    print()
