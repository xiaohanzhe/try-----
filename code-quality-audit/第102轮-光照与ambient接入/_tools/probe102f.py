# -*- coding: utf-8 -*-
u"""probe102f.py —— 第102轮侦察 6：地面真值。原作自己怎么说它的房间/光照。

 S1 `gamedata/txt/`、`Content/pictures|ui|titles|the_world_machine`、`gamedata/twm` 里有什么
 S2 原作 `log.txt` 头部（游戏自己的日志）
 S3 `OneShotMG.exe` 里 `ambient` 相关字符串的**邻接上下文**（谁给 ambient 默认值）
 S4 263 张图的名字画像：有多少是占位/未用（ignore / X room / C1 / S1 …）
 S5 `oneshot_common_events.json` 里有没有 lightmap / ambient 的脚本体
"""
import collections
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OSD = (r'C:\Users\23002\Desktop\项目文件夹\niko的秘密'
       r'\OneShot.World.Machine.Edition.Build.16512634')
GD = os.path.join(OSD, 'gamedata')


def ls(rel, limit=40):
    d = os.path.join(OSD, rel)
    if not os.path.isdir(d):
        print('   (缺) %s' % rel)
        return
    fs = sorted(os.listdir(d))
    print('--- %s (%d) ---' % (rel, len(fs)))
    for x in fs[:limit]:
        p = os.path.join(d, x)
        print('   %-46s %s' % (x, os.path.getsize(p) if os.path.isfile(p) else '<DIR>'))
    if len(fs) > limit:
        print('   ... 另 %d' % (len(fs) - limit))


print('=' * 78)
print('S1 目录')
print('=' * 78)
for rel in ['gamedata/txt', 'gamedata/twm', 'content/pictures', 'content/ui',
            'content/titles', 'content/the_world_machine', 'content/facepics']:
    ls(rel, 22)

print()
print('=' * 78)
print('S2 log.txt 头部 60 行')
print('=' * 78)
lp = os.path.join(OSD, 'log.txt')
if os.path.isfile(lp):
    t = io.open(lp, encoding='utf-8', errors='replace', newline='').read()
    print(t[:2600])
    print('  ... [log 全文 %d 字节]' % len(t))

print()
print('=' * 78)
print('S3 exe 里 ambient 字符串的邻接')
print('=' * 78)
raw = open(os.path.join(OSD, 'OneShotMG.exe'), 'rb').read()
strs = []
for m in re.finditer(rb'(?:[\x20-\x7e]\x00){2,}', raw):
    strs.append((m.start(), m.group().decode('utf-16-le', 'replace')))
for i, (off, s) in enumerate(strs):
    if 'ambient' in s:
        nb = [x[1] for x in strs[max(0, i - 4):i + 5]]
        print('   off=%-7d %r' % (off, s[:90]))
        print('        邻接: %s' % ' | '.join(repr(x[:60]) for x in nb))

print()
print('=' * 78)
print('S4 263 张图的名字画像')
print('=' * 78)
names = json.loads(re.sub(r',(\s*[}\]])', r'\1',
                          io.open(os.path.join(GD, 'oneshot_map_names.json'),
                                  encoding='utf-8', newline='').read()))['map_names']
nm = {e['id']: e['name'] for e in names}
PH = re.compile(r'^(ignore|unused|X room|C\d+|S\d+|test\w*|temp\w*|-+|\?+)$', re.I)
ph = [k for k, v in nm.items() if PH.match(v.strip())]
print('   有名字的图 = %d / 263' % len(nm))
print('   疑似占位名 = %d 张 %s' % (len(ph), sorted(ph)[:40]))
print('   名字样本（前 30，按 id）:')
for k in sorted(nm)[:30]:
    print('      map%-4d %s' % (k, nm[k]))
no_name = [i for i in range(1, 264) if i not in nm]
print('   无名字的 map 数 = %d %s' % (len(no_name), no_name[:20]))

print()
print('=' * 78)
print('S5 common_events 里的 lightmap / ambient')
print('=' * 78)
ce = io.open(os.path.join(GD, 'oneshot_common_events.json'),
             encoding='utf-8', errors='replace', newline='').read()
for k in ['lightmap', 'ambient']:
    n = ce.lower().count(k)
    print('   %-10s 出现 %d 次' % (k, n))
    for m in list(re.finditer(k, ce, re.I))[:3]:
        a, b = max(0, m.start() - 150), min(len(ce), m.start() + 150)
        print('        ...%s...' % ce[a:b].replace('\n', ' ').replace('\r', ''))
