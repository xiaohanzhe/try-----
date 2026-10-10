# -*- coding: utf-8 -*-
u"""probe104.py —— 第104轮**普查**：OneShot 物件的「材质」字段到底有多少、长什么样。

只读仓库内的 6 个区域分片 + 本轮证据 `_evidence/material104.json`。
**零外部盘依赖**（不碰 C 盘原作）⇒ 可以在任何机器上重跑。

它回答三个问题（都不带结论，只报事实）：
  ① 有多少物件的 `alpha`/`blend` 被写进去了？取值域是什么？
  ② 这些物件落在哪些分片/房间？`blend=1` 的都是些什么物件？
  ③ 证据文件 `material104.json` 与分片**逐条对得上**吗？

用法：`python probe104.py`
"""
import collections
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
EV = os.path.join(HERE, '..', '_evidence')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
ZONE_FILES = sorted(f for f in os.listdir(SCENES) if f.startswith('_zone.oneshot.'))

_OK = [0]
_BAD = []


def jload(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return json.load(f)


def ok(cond, msg):
    _OK[0] += 1
    print('[%s] %s' % ('PASS' if cond else 'FAIL', msg))
    if not cond:
        _BAD.append(msg)


# ---------------------------------------------------------------- 1 分片侧
objs = []            # (zone, sid, room, obj)
for zf in ZONE_FILES:
    d = jload(os.path.join(SCENES, zf))
    for sid, ent in (d.get('scenes') or {}).items():
        if not isinstance(ent, dict):
            continue
        for o in (ent.get('objects') or []):
            objs.append((zf, sid, ent.get('original_room_id'), o))

n_all = len(objs)
n_a = [o for _z, _s, _r, o in objs if 'alpha' in o]
n_b = [o for _z, _s, _r, o in objs if o.get('blend') == 1]
union = [o for _z, _s, _r, o in objs if ('alpha' in o or o.get('blend') == 1)]
a0 = [o for _z, _s, _r, o in objs if o.get('alpha') == 0.0]

print('=' * 96)
print(u'1 分片侧（%d 个分片 / %d 个物件）' % (len(ZONE_FILES), n_all))
print('=' * 96)
print(u'  带 alpha      ：%d' % len(n_a))
print(u'  带 blend==1   ：%d' % len(n_b))
print(u'  并集（受影响）：%d' % len(union))
print(u'  alpha == 0    ：%d' % len(a0))
print(u'  alpha 取值（按 round(x*255) 还原 opacity）：%s'
      % sorted(set(int(round(o['alpha'] * 255)) for o in n_a)))
print(u'  blend 出现过的值：%s'
      % sorted(set(o.get('blend') for _z, _s, _r, o in objs if 'blend' in o)))

ok(n_all == 7804, u'分片侧物件总数 %d（第103轮接线数 7804）' % n_all)

# 分布
by_zone = collections.Counter(zf for zf, _s, _r, o in objs
                              if 'alpha' in o or o.get('blend') == 1)
by_room = collections.Counter(r for _z, _s, r, o in objs
                              if 'alpha' in o or o.get('blend') == 1)
scenes_hit = set(s for _z, s, _r, o in objs if 'alpha' in o or o.get('blend') == 1)
print(u'  按分片：%s' % dict(by_zone))
print(u'  涉及房间 %d 间、场景 %d 个（有物件的场景共 %d 个）'
      % (len(by_room), len(scenes_hit),
         len(set(s for _z, s, _r, o in objs if o))))

print()
print(u'  ★ blend==1 的物件按 sheet 归类（前 12）：')
sheet_of = collections.Counter(
    os.path.basename(o['sprite']).split('__c')[0] for o in n_b)
for k, v in sheet_of.most_common(12):
    print(u'      %-28s %d' % (k, v))

print()
print(u'  ★ alpha != 1 的物件（全部 %d 条，含 room / sheet / opacity）：' % len(n_a))
for zf, sid, r, o in objs:
    if 'alpha' not in o:
        continue
    print(u'      room %-4s %-40s opacity=%-4d blend=%s  src=%s'
          % (r, os.path.basename(o['sprite'])[:40], int(round(o['alpha'] * 255)),
             o.get('blend'), o.get('src')))

# ---------------------------------------------------------------- 2 结构
print()
print('=' * 96)
print(u'2 结构（新键不许长得不像"opacity/255"）')
print('=' * 96)
# ★ 容差必须是 1e-3 而不是 1e-6：`build104` 写的是 `round(opacity/255, 6)`
#   —— 6 位小数本身带 ~5e-7 的舍入误差，乘 255 后放大成 ~1.3e-4。
#   首跑用 1e-6 就报了 32 条**假红**（220/255=0.862745 ⇒ ×255=219.999975）。
bad_frac = [(r, o['alpha']) for _z, _s, r, o in objs
            if 'alpha' in o and abs(o['alpha'] * 255 - round(o['alpha'] * 255)) > 1e-3]
ok(not bad_frac, u'每个 alpha 都恰好是 `n/255`（n 为整数，容差 1e-3）；不符 %d %s'
   % (len(bad_frac), bad_frac[:3]))
# 正/负控制：容差不是"放到什么都过得去"—— 挪 1/255 就必须报红
_pert = 220 / 255.0 + 1 / 255.0
ok(abs(_pert * 255 - round(_pert * 255)) <= 1e-3
   and abs(0.5 * 255 - round(0.5 * 255)) > 1e-3,
   u'容差正负控制：`220/255 + 1/255` = 221/255 仍判为"整数份"（221），'
   u'而 `0.5`（=127.5/255）判为**不是**整数份 ⇒ 判据有鉴别力')

ALLOWED = {'pos', 'sprite', 'tile', 'depth', 'src', 'layer', 'alpha', 'blend'}
extra = collections.Counter()
for _z, _s, _r, o in objs:
    for k in o:
        if k not in ALLOWED:
            extra[k] += 1
ok(not extra, u'物件键集合 ⊆ %s（越界键 %s）' % (sorted(ALLOWED), dict(extra)))

ok(all(isinstance(o['alpha'], float) and 0.0 <= o['alpha'] <= 1.0 for o in n_a),
   u'全部 alpha 都在 [0,1] 且是 float')
# ★ 首跑这里写成 `len(set(int(o.get('blend',0)) ...)) == 1` —— 恒假：
#   集合里必然同时有 0（399−389 个"没写 blend"的物件）与 1 ⇒ 长度 2。
#   本意是"`blend` **这个键**只以 `1` 的形式出现"，所以要分别断言两件事。
_bad_blend = [(r, o.get('blend')) for _z, _s, r, o in objs
              if 'blend' in o and o.get('blend') != 1]
_no2 = [r for _z, _s, r, o in objs if o.get('blend') == 2]
ok(not _bad_blend and not _no2,
   u'`blend` 键**只**以 `1` 的形式出现（异常 %d %s）；且全集里**没有** `blend_type=2`'
   u'（减色）⇒ 本轮不做它、只登记（见报告）' % (len(_bad_blend), _bad_blend[:3]))

# ---------------------------------------------------------------- 3 与证据对账
print()
print('=' * 96)
print(u'3 与 `_evidence/material104.json` 对账')
print('=' * 96)
ev = jload(os.path.join(EV, 'material104.json'))
print(u'  证据 counts = %s' % ev['counts'])
ok(ev['counts'] == dict(objects=n_all, alpha=len(n_a), blend1=len(n_b),
                        alpha0=len(a0), union=len(union)),
   u'证据里的五个计数与分片侧**独立数出来的**完全一致')

mine = sorted((r, o.get('src') or '', o['sprite'], tuple(o['tile']),
               int(round(o['alpha'] * 255)) if 'alpha' in o else 255,
               int(o.get('blend', 0)))
              for _z, _s, r, o in objs if 'alpha' in o or o.get('blend') == 1)
theirs = sorted((it['room'], it['src'] or '', it['sprite'], tuple(it['tile']),
                 it['opacity'], it['blend']) for it in ev['items'])
ok(mine == theirs and len(mine) == 399,
   u'证据的 %d 条与分片侧逐条相同（房间/名字/素材/瓦片/opacity/blend 六元组）'
   % len(theirs))
if mine != theirs:
    print(u'     首处不同：mine=%s theirs=%s'
          % (next((a for a, b in zip(mine, theirs) if a != b), None),
             next((b for a, b in zip(mine, theirs) if a != b), None)))

print()
print(u'%d/%d 通过' % (_OK[0], _OK[0]) if not _BAD else u'失败 %d 条' % len(_BAD))
sys.exit(1 if _BAD else 0)
