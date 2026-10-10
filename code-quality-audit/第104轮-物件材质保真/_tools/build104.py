# -*- coding: utf-8 -*-
u"""build104.py —— 第104轮构建：把原作页的 **`opacity` / `blend_type`** 接进 OneShot 物件。

依据（全部来自原作 `events_map<N>.json` 的页数据，字段名即 RMXP 语义）：
  · `graphic.opacity`（0..255）⇒ 物件 `alpha = opacity/255`。**只写 != 255 的**。
  · `graphic.blend_type`（0=普通, 1=加色, 2=减色）⇒ 物件 `blend`。**实测只出现 0/1**，
    所以本轮只落 `1`（加色）；出现 2 也不写（渲染器不认 ⇒ 保持普通叠加，并登记）。
  · `graphic.character_hue` / `step_anime` / `move_route` —— **本轮刻意不做**：
    原作是 MonoGame/.NET（`OneShotMG.exe`），没有可读脚本 ⇒ 色相算法与动画节拍
    **无从照抄**；按第102轮教训（"依据不足就不做"）只登记进遗留。

写盘纪律（沿用 build103）：
  · **只重写"内容真的变了"的 `objects` 行**，就地替换；保留原 EOL 与缩进。
  · 先**重算整张物件表**并与磁盘逐条比对（**忽略新加的两个键**）——
    必须**完全一致**才允许写；这同时证明"本轮没顺手改到别的字段"。
  · 读回自证 + `\r\n` 计数守恒。

产出：
  · 6 个 `_zone.oneshot.<area>.json` 里受影响物件的 `alpha` / `blend` 键
  · `_evidence/material104.json`（399 条受影响物件的清单 + 计数）
"""
import collections
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image                                                     # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
EV = os.path.join(HERE, '..', '_evidence')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
PROPS = os.path.join(SCENES, 'oneshot_props')

import importlib.util                                                     # noqa: E402
_spec = importlib.util.spec_from_file_location(
    'os_bg100', os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景',
                             '_tools', 'os_bg100.py'))
o = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(o)
MAPS = os.path.join(o.OSD, 'gamedata', 'maps')

TILE = 16
DIR_ROW = {2: 0, 4: 1, 6: 2, 8: 3}
ZONES = sorted(f for f in os.listdir(SCENES) if f.startswith('_zone.oneshot.'))
HAVE = set(f[:-4] for f in os.listdir(PROPS) if f.endswith('.png'))
NEW_KEYS = ('alpha', 'blend')


def read_raw(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def write_raw(p, s):
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(s)


def rj(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return json.load(f)


def cell_file(cn, col, row):
    return '%s__c%dr%d.png' % (cn, col, row)


def cell_size(sp):
    with Image.open(sp) as im:
        w, h = im.size
    return w // 4, h // 4


# --------------------------------------------------------------- S1 重算物件表
print('=' * 96)
print(u'S1 重算物件表（与 build103 完全同口径：page0 / character_name 非空 / tile_id==0）')
print('=' * 96)
rooms = {}
for n in range(1, 400):
    p = os.path.join(MAPS, 'events_map%d.json' % n)
    if not os.path.isfile(p):
        continue
    evs = []
    for e in rj(p).get('events', []):
        pgs = e.get('pages') or []
        if not pgs:
            continue
        pg = pgs[0]
        g = pg.get('graphic') or {}
        if int(g.get('tile_id') or 0) > 0:
            continue
        cn = (g.get('character_name') or '').strip()
        if not cn:
            continue
        evs.append(dict(
            name=(e.get('name') or '').strip(),
            x=int(e.get('x') or 0), y=int(e.get('y') or 0), cn=cn,
            d=int(g.get('direction') or 0), p=int(g.get('pattern') or 0),
            aob=bool(pg.get('always_on_bottom')), aot=bool(pg.get('always_on_top')),
            opacity=int(g.get('opacity', 255)),
            blend=int(g.get('blend_type', 0)),
        ))
    if evs:
        rooms[n] = evs
print(u'  有物件房 %d 间 / 物件 %d 个' % (len(rooms), sum(len(v) for v in rooms.values())))

objs_by_room = {}
mat = []          # 受影响清单（证据）
for rid in sorted(rooms):
    ent = []
    for e in rooms[rid]:
        if e['cn'] not in HAVE:
            continue
        col = e['p'] if e['p'] in (0, 1, 2, 3) else 0
        row = DIR_ROW[e['d']]
        cw, ch = cell_size(os.path.join(PROPS, e['cn'] + '.png'))
        x, y = e['x'], e['y']
        ground = y * TILE + TILE
        depth = ground - 10 ** 6 if e['aob'] else (ground + 10 ** 6 if e['aot'] else ground)
        it = collections.OrderedDict()
        it['pos'] = [x * TILE + TILE // 2 - cw // 2, y * TILE + TILE - ch]
        it['sprite'] = 'oneshot_cells/%s' % cell_file(e['cn'], col, row)
        it['tile'] = [x, y]
        it['depth'] = depth
        if e['name']:
            it['src'] = e['name']
        if e['aob']:
            it['layer'] = 'bottom'
        elif e['aot']:
            it['layer'] = 'top'
        # ---- 本轮新增：材质 ----
        if e['opacity'] != 255:
            it['alpha'] = round(e['opacity'] / 255.0, 6)
        if e['blend'] == 1:
            it['blend'] = 1
        elif e['blend'] != 0:
            pass          # 只出现在 0/1；别的值不写（登记在报告）
        if e['opacity'] != 255 or e['blend'] == 1:
            mat.append(dict(room=rid, src=e['name'], sprite=it['sprite'],
                            tile=[x, y], opacity=e['opacity'], blend=e['blend'],
                            alpha=it.get('alpha')))
        ent.append(it)
    ent.sort(key=lambda o2: (o2['depth'], o2['tile'][1], o2['tile'][0]))
    objs_by_room[rid] = ent

n_written = sum(len(v) for v in objs_by_room.values())
n_alpha = sum(1 for _, v in objs_by_room.items() for it in v if 'alpha' in it)
n_blend = sum(1 for _, v in objs_by_room.items() for it in v if it.get('blend') == 1)
n_a0 = sum(1 for _, v in objs_by_room.items() for it in v if it.get('alpha') == 0.0)
print(u'  写入 %d 个物件 · 带 alpha %d · 带 blend=1 %d · 交集 %d · alpha==0 %d'
      % (n_written, n_alpha, n_blend, n_alpha + n_blend - len(mat), n_a0))

# --------------------------------------------------------------- S2 与磁盘比对
print()
print('=' * 96)
print(u'S2 与磁盘比对（**忽略 alpha/blend**，必须逐字节一致 ⇒ 证明没顺手改别的）')
print('=' * 96)
room2scene = {}
for zf in ZONES:
    raw = rj(os.path.join(SCENES, zf))
    for sid, entry in (raw.get('scenes') or {}).items():
        if isinstance(entry, dict) and isinstance(entry.get('original_room_id'), int):
            room2scene.setdefault(entry['original_room_id'], []).append((zf, sid))
dup = {r: v for r, v in room2scene.items() if len(v) > 1}
print(u'  一房多场景 %s' % (dup or u'(无)'))

mismatch = []
n_disk = 0
for zf in ZONES:
    raw = rj(os.path.join(SCENES, zf))
    for sid, entry in (raw.get('scenes') or {}).items():
        if not isinstance(entry, dict):
            continue
        rid = entry.get('original_room_id')
        disk = []
        for it in (entry.get('objects') or []):
            if not isinstance(it, dict):
                continue
            disk.append({k: v for k, v in it.items() if k not in NEW_KEYS})
        want = [{k: v for k, v in it.items() if k not in NEW_KEYS}
                for it in objs_by_room.get(rid, [])] if isinstance(rid, int) else []
        n_disk += len(disk)
        if disk != want:
            mismatch.append((zf, sid, rid, len(disk), len(want)))
print(u'  磁盘物件总计 %d ；不一致场景 %d %s'
      % (n_disk, len(mismatch), mismatch[:5]))
assert not mismatch, u'重算结果与磁盘不一致 —— 拒绝写盘（先查取页口径）'

# --------------------------------------------------------------- S3 就地补键
print()
print('=' * 96)
print(u'S3 就地补 alpha/blend（只改"内容真的变了"的 objects 行）')
print('=' * 96)
payload = {}
for rid, ent in objs_by_room.items():
    hit = room2scene.get(rid)
    if hit:
        payload.setdefault(hit[0][0], {})[hit[0][1]] = ent

total_lines = 0
for zf in ZONES:
    path = os.path.join(SCENES, zf)
    text = read_raw(path)
    n_crlf = text.count('\r\n')
    lines = text.split('\n')
    want = payload.get(zf, {})
    changed = 0
    for i, ln in enumerate(lines):
        st = ln.rstrip('\r').strip()
        mkey = None
        import re
        mkey = re.match(r'^"([^"]+)"\s*:\s*\{\s*$', st)
        if not mkey or mkey.group(1) not in want:
            continue
        sid = mkey.group(1)
        ind = None
        for j in range(i + 1, min(i + 40, len(lines))):
            if lines[j].rstrip('\r').strip().startswith('"objects"'):
                ind = j
                break
        assert ind is not None, u'%s / %s 找不到 objects 行' % (zf, sid)
        raw_ln = lines[ind]
        indent = raw_ln[:len(raw_ln) - len(raw_ln.lstrip())]
        comma = ',' if raw_ln.rstrip('\r').rstrip().endswith(',') else ''
        cr = '\r' if raw_ln.endswith('\r') else ''
        blob = json.dumps(want[sid], ensure_ascii=False, separators=(',', ':'))
        new_ln = '%s"objects": %s%s%s' % (indent, blob, comma, cr)
        if new_ln != raw_ln:
            lines[ind] = new_ln
            changed += 1
    new = '\n'.join(lines)
    assert new.count('\r\n') == n_crlf, u'%s EOL 被改动' % zf
    if changed:
        write_raw(path, new)
    total_lines += changed
    print(u'  %-30s 改 %2d 个场景行 · EOL 守恒 %s'
          % (zf, changed, new.count('\r\n') == n_crlf))
print(u'  合计改 %d 个场景行（受影响物件 %d 条）' % (total_lines, len(mat)))

# --------------------------------------------------------------- S4 读回自证
print()
print('=' * 96)
print(u'S4 读回自证')
print('=' * 96)
got_a = got_b = got_a0 = 0
for zf in ZONES:
    raw = rj(os.path.join(SCENES, zf))
    for sid, entry in (raw.get('scenes') or {}).items():
        if not isinstance(entry, dict):
            continue
        for it in (entry.get('objects') or []):
            if not isinstance(it, dict):
                continue
            if 'alpha' in it:
                got_a += 1
                if it['alpha'] == 0.0:
                    got_a0 += 1
            if it.get('blend') == 1:
                got_b += 1
print(u'  读回：alpha %d（== 写入 %d：%s）｜ blend=1 %d（== %d：%s）｜ alpha==0 %d'
      % (got_a, n_alpha, got_a == n_alpha, got_b, n_blend, got_b == n_blend, got_a0))
assert got_a == n_alpha and got_b == n_blend, u'读回不一致'

# --------------------------------------------------------------- S5 证据落盘
ev = dict(
    schema=1,
    note=u'第104轮：OneShot 物件材质（opacity→alpha / blend_type→blend）。'
         u'来源＝原作 events_map<N>.json 页数据（page0，口径同 build103）。',
    counts=dict(objects=n_written, alpha=n_alpha, blend1=n_blend,
                alpha0=n_a0, union=len(mat)),
    alpha_values=sorted(set(r['opacity'] for r in mat if r['alpha'] is not None)),
    blend_values=sorted(set(r['blend'] for r in mat)),
    items=sorted(mat, key=lambda r: (r['room'], r['src'], r['tile'][0], r['tile'][1])),
)
os.makedirs(EV, exist_ok=True)
with io.open(os.path.join(EV, 'material104.json'), 'w', encoding='utf-8', newline='') as f:
    json.dump(ev, f, ensure_ascii=False, indent=1)
print(u'  _evidence/material104.json 落盘（%d 条；alpha 取值 %s；blend 取值 %s）'
      % (len(ev['items']), ev['alpha_values'], ev['blend_values']))
print()
print(u'完成。')
