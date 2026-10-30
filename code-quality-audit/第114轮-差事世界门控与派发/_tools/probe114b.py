# -*- coding: utf-8 -*-
"""探针 B（只读）：`_routes.json` 与 `_worlds.json` 的真实结构。

A 探针发现「oneshot/ut 的房间 world = unknown」⇒ 必须搞清楚：
  ① 桌面 4 条路线到底存在哪个键里；
  ② `_worlds.json` 对跨作品章的判定口径（meta / areas）。
★ 只读。
"""
import collections
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PROJ = os.path.join(ROOT, 'ralsei_pet')
SCENES = os.path.join(PROJ, 'assets', 'scenes')

OUT = []


def _load(p):
    try:
        with io.open(p, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception as e:
        return {'__err__': repr(e)}


# ---------------- _routes.json ----------------
rp = os.path.join(SCENES, '_routes.json')
OUT.append('=== _routes.json (%s) ===' % rp)
rw = _load(rp)
OUT.append('顶层键: %s' % sorted(rw.keys()) if isinstance(rw, dict) else repr(type(rw)))

if isinstance(rw, dict):
    for k, v in rw.items():
        if isinstance(v, dict):
            OUT.append('  %s: dict(%d) keys=%s' % (k, len(v), list(v.keys())[:12]))
        elif isinstance(v, list):
            OUT.append('  %s: list(%d)' % (k, len(v)))
            for item in v[:6]:
                OUT.append('      %r' % (item,))
        else:
            OUT.append('  %s: %r' % (k, v))

# ---------------- _worlds.json ----------------
wp = os.path.join(SCENES, '_worlds.json')
OUT.append('')
OUT.append('=== _worlds.json (%s) ===' % wp)
ww = _load(wp)
OUT.append('顶层键: %s' % sorted(ww.keys()))
OUT.append('')
OUT.append('--- meta ---')
OUT.append(json.dumps(ww.get('meta'), ensure_ascii=False, indent=1)[:3000])

OUT.append('')
OUT.append('--- areas（逐章）---')
areas = ww.get('areas') or {}
for ch in sorted(areas):
    rec = areas[ch]
    if isinstance(rec, dict):
        cnt = collections.Counter(rec.values())
        OUT.append('  %-14s n=%-5d %s' % (ch, len(rec), dict(cnt)))
    else:
        OUT.append('  %-14s %r' % (ch, rec))

OUT.append('')
OUT.append('--- rooms（逐章取值分布）---')
rooms = ww.get('rooms') or {}
for ch in sorted(rooms):
    rec = rooms[ch] or {}
    cnt = collections.Counter(rec.values())
    OUT.append('  %-14s n=%-5d %s' % (ch, len(rec), dict(cnt)))
    if ch in ('oneshot', 'ut'):
        OUT.append('       前 12 条: %s' % sorted(rec.items())[:12])

OUT.append('')
OUT.append('--- 未判定清单（meta 里的，原文照抄）---')
meta = ww.get('meta') or {}
for k, v in meta.items():
    if 'unknown' in str(k).lower() or '未' in str(k) or 'pending' in str(k).lower():
        OUT.append('  %s = %s' % (k, json.dumps(v, ensure_ascii=False)[:2000]))

txt = '\n'.join(OUT)
print(txt)
with io.open(os.path.join(HERE, 'probe114b.txt'), 'w', encoding='utf-8', newline='\n') as fh:
    fh.write(txt + '\n')
