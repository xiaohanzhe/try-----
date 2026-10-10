# -*- coding: utf-8 -*-
u"""verify103.py —— 第103轮**独立验收**：不复用 `build103` 的任何函数/结论。

为什么需要它（而不只是 `check103`）：
  * `check103` 进 G2，铁律是**零外部盘依赖** ⇒ 它只能拿"第102轮落在仓库里的
    普查 JSON"当对账源。那对账源是**我们自己的产物**；
  * 本脚本走**另一条路**：直接读**原作** `gamedata/maps/events_map<N>.json`
    从头复算物件，直接读 `oneshot_props/*.png` **重新裁**每一格，
    然后与**真正落进产品的分片**逐条比对。
  * 两者都要绿，才排除"构建脚本与它的产物清单同错"。

★ 除了"重算一遍"，本脚本还查 `build103` **可能悄悄兜底**的两处
  （它们会让"数据不对"变成"数据被改得看起来对"）：
    (a) `direction` 不在 `{2,4,6,8}` —— `build103` 直接 `DIR_ROW[d]`，缺键会崩，
        所以它会崩反而说明"没兜底"；这里显式统计，把"崩"变成"报数"；
    (b) `pattern` 不在 `0..3` —— `build103` 写的是
        `col = p if p in (0,1,2,3) else 0`，**这是兜底**：原作若有 `pattern=4+`，
        就会被当作 `col=0` 静默画错。这里单独报出来，看它到底是 0 条还是若干条。
    (c) `character_name` 指向不存在的图集 —— 必须**如实跳过**并计数（应为 1 条 `npc_BIG`）。

⚠️ 本脚本**不进 G2**（要读 C 盘原作），是"验收工具"，不是回归锁。
"""
import collections
import hashlib
import io
import json
import os
import re
import struct
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image                                                     # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
EV = os.path.join(HERE, '..', '_evidence')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
PROPS = os.path.join(SCENES, 'oneshot_props')
CELLS = os.path.join(SCENES, 'oneshot_cells')
TILE = 16
DIR_ROW = {2: 0, 4: 1, 6: 2, 8: 3}          # 下/左/右/上

FAIL = []


def ok(cond, msg):
    if cond:
        print('[PASS] %s' % msg)
    else:
        FAIL.append(msg)
        print('[FAIL] %s' % msg)


def rj(p):
    return json.loads(re.sub(r',(\s*[}\]])', r'\1',
                             io.open(p, encoding='utf-8', newline='').read()))


def png_size(p):
    with open(p, 'rb') as fh:
        return struct.unpack('>II', fh.read(33)[16:24])


# ---------------------------------------------------------------- 0 找原作
# 路径来源：第100轮的 `os_bg100.py`（**不是** build103 —— build103 也是 import 它，
# 但本脚本只借"路径解析"，所有判定逻辑都是这里自己写的）。
import importlib.util
_spec = importlib.util.spec_from_file_location(
    'os_bg100', os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景',
                             '_tools', 'os_bg100.py'))
_o = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_o)
MAPS = os.path.join(_o.OSD, 'gamedata', 'maps')
print('原作 maps 目录：%s' % MAPS)
ok(os.path.isfile(os.path.join(MAPS, 'events_map4.json')),
   'V0 原作 `events_map4.json` 在位（独立验收需要原作，故本脚本不进 G2）')

# ---------------------------------------------------------------- 1 从头复算
HAVE = set(f[:-4] for f in os.listdir(PROPS) if f.endswith('.png'))
raw_objs = []          # (room, name, tile, sheet, col, row, aob, aot, d, p)
weird_dir = collections.Counter()
weird_pat = collections.Counter()
missing = collections.Counter()
miss_room = collections.Counter()      # ★ 缺图集的物件**也**要按房计数：
                                       #   否则 `raw_objs` 已经把它剔除，
                                       #   "原作侧 vs 分片侧"就永远看不出房间 96 的差
                                       #   （首跑正是栽在这 —— 判据自己把自己抹平了）
n_events = 0
for n in range(1, 400):
    p = os.path.join(MAPS, 'events_map%d.json' % n)
    if not os.path.isfile(p):
        continue
    for e in rj(p).get('events', []):
        n_events += 1
        pgs = e.get('pages') or []
        if not pgs:
            continue
        g = (pgs[0].get('graphic') or {})
        if int(g.get('tile_id') or 0) > 0:
            continue
        cn = (g.get('character_name') or '').strip()
        if not cn:
            continue
        d = int(g.get('direction') or 0)
        pt = int(g.get('pattern') or 0)
        if d not in DIR_ROW:
            weird_dir[d] += 1
        if pt not in (0, 1, 2, 3):
            weird_pat[pt] += 1
        if cn not in HAVE:
            missing[cn] += 1
            miss_room[n] += 1
            continue
        raw_objs.append((n, (e.get('name') or '').strip(),
                         (int(e.get('x') or 0), int(e.get('y') or 0)),
                         cn, pt, d,
                         bool(pgs[0].get('always_on_bottom')),
                         bool(pgs[0].get('always_on_top'))))
print('原作事件 %d ｜ 可见物件（含缺图集）%d ｜ 缺图集 %s ｜ 怪 direction %s ｜ 怪 pattern %s'
      % (n_events, len(raw_objs) + sum(missing.values()), dict(missing),
         dict(weird_dir), dict(weird_pat)))

ok(dict(weird_dir) == {},
   'V1 全部可见物件的 `direction` 都在 %s 里（越界 %s）—— 若不为空，'
   '`build103` 的 `DIR_ROW[d]` 会直接 KeyError（即它**没有**兜底）'
   % (sorted(DIR_ROW), dict(weird_dir)))
ok(dict(weird_pat) == {},
   'V2 ★ 全部可见物件的 `pattern` 都在 0..3（越界 %s）—— 这条专门查 `build103` 的'
   '`col = p if p in (0,1,2,3) else 0` 兜底：**若这里报出非空，说明有物件被静默当成 '
   'col=0 画错**，而构建脚本不会有任何提示' % (dict(weird_pat),))
ok(dict(missing) == {'npc_BIG': 1},
   'V3 缺图集**恰好** 1 条 `npc_BIG`（实际 %s）—— 守恒等式右边就靠它' % (dict(missing),))
ok(len(raw_objs) == 7804,
   'V4 ★ 独立复算的可见物件数 == 7804（实际 %d）' % len(raw_objs))

# ---------------------------------------------------------------- 2 重新裁格
# 每格：从图集裁 → 与磁盘 PNG **逐像素**比。这是"切帧正确"的第二条独立证据。
seen = {}
bad_cell = []
for (_r, _nm, _t, cn, pt, d, _a, _b) in raw_objs:
    seen.setdefault((cn, pt, DIR_ROW[d]), 0)
    seen[(cn, pt, DIR_ROW[d])] += 1
for (cn, col, row) in sorted(seen):
    sw, sh = png_size(os.path.join(PROPS, cn + '.png'))
    assert sw % 4 == 0 and sh % 4 == 0, (cn, sw, sh)
    cw, ch = sw // 4, sh // 4
    fn = '%s__c%dr%d.png' % (re.sub(r'[^A-Za-z0-9_-]', '_', cn), col, row)
    p = os.path.join(CELLS, fn)
    if not os.path.isfile(p):
        bad_cell.append((fn, '不在盘上'))
        continue
    a = Image.open(os.path.join(PROPS, cn + '.png')).convert('RGBA')
    cut = a.crop((col * cw, row * ch, (col + 1) * cw, (row + 1) * ch)).tobytes()
    b = Image.open(p).convert('RGBA').tobytes()
    if cut != b:
        bad_cell.append((fn, '像素不同'))
ok(not bad_cell and len(seen) == 379,
   'V5 ★★ 独立复算的 distinct (sheet,col,row) == 379，且**每个格的磁盘 PNG 都等于'
   '「重裁一遍」的像素**（不符 %d %s）' % (len(bad_cell), bad_cell[:3]))

disk = sorted(f for f in os.listdir(CELLS) if f.endswith('.png'))
exp_names = sorted('%s__c%dr%d.png' % (re.sub(r'[^A-Za-z0-9_-]', '_', c), col, row)
                   for (c, col, row) in seen)
ok(disk == exp_names,
   'V6 ★ 磁盘上的 379 个格文件名集合 == 独立复算的集合（多 %s / 少 %s）'
   % (sorted(set(disk) - set(exp_names))[:3], sorted(set(exp_names) - set(disk))[:3]))

# ---------------------------------------------------------------- 3 与产品分片对账
ZONE_FILES = sorted(f for f in os.listdir(SCENES) if f.startswith('_zone.oneshot.'))
room2sid = {}
shard = {}          # sid -> [obj]
for zf in ZONE_FILES:
    d = rj(os.path.join(SCENES, zf))
    for sid, ent in (d.get('scenes') or {}).items():
        if not isinstance(ent, dict):
            continue
        shard[sid] = ent.get('objects') or []
        if isinstance(ent.get('original_room_id'), int):
            room2sid.setdefault(ent['original_room_id'], sid)

# 独立复算 → "产品应有的样子"
want = collections.defaultdict(list)
for (r, nm, t, cn, pt, d, aob, aot) in raw_objs:
    sid = room2sid.get(r)
    assert sid, '房间 %d 没有登记场景' % r
    sw, sh = png_size(os.path.join(PROPS, cn + '.png'))
    cw, ch = sw // 4, sh // 4
    row = DIR_ROW[d]
    fn = '%s__c%dr%d.png' % (re.sub(r'[^A-Za-z0-9_-]', '_', cn), pt, row)
    px = t[0] * TILE + TILE // 2 - cw // 2
    py = t[1] * TILE + TILE - ch
    g = t[1] * TILE + TILE
    depth = g - 10 ** 6 if aob else (g + 10 ** 6 if aot else g)
    it = {'pos': [px, py], 'sprite': 'oneshot_cells/%s' % fn, 'tile': [t[0], t[1]],
          'depth': depth}
    if nm:
        it['src'] = nm
    if aob:
        it['layer'] = 'bottom'
    elif aot:
        it['layer'] = 'top'
    want[sid].append(it)
for sid in want:
    want[sid].sort(key=lambda o: (o['depth'], o['tile'][1], o['tile'][0]))

ok(sum(len(v) for v in want.values()) == 7804,
   'V7 独立复算后**归属到场景**的物件总数 == 7804（实际 %d）'
   % sum(len(v) for v in want.values()))

bad_rooms = sorted(sid for sid in set(list(want) + list(shard))
                   if want.get(sid, []) != list(shard.get(sid, [])))
ok(not bad_rooms,
   'V8 ★★★ **落进产品的分片与独立复算逐条相同**（含顺序；不等场景 %d %s）'
   % (len(bad_rooms), bad_rooms[:3]))
if bad_rooms:
    s0 = bad_rooms[0]
    print('  样例 %s：want %d 条 / shard %d 条' % (s0, len(want.get(s0, [])),
                                                 len(shard.get(s0, []))))
    for i, (x, y) in enumerate(zip(want.get(s0, []), shard.get(s0, []))):
        if x != y:
            print('    第 %d 条\n      want  %s\n      shard %s'
                  % (i, json.dumps(x, ensure_ascii=False), json.dumps(y, ensure_ascii=False)))
            break

# ---------------------------------------------------------------- 4 按房间对账
# 原作侧 = 写进去的 + 缺图集跳过的（缺的**必须**算进来，否则判据自相抵消）
w_room = collections.Counter(miss_room)
for (r, _nm, _t, _c, _p, _d, _a, _b) in raw_objs:
    w_room[r] += 1
s_room = collections.Counter()
for zf in ZONE_FILES:
    d = rj(os.path.join(SCENES, zf))
    for sid, ent in (d.get('scenes') or {}).items():
        if isinstance(ent, dict) and isinstance(ent.get('original_room_id'), int):
            s_room[ent['original_room_id']] += len(ent.get('objects') or [])
ok(sum(w_room.values()) == 7805 and sum(s_room.values()) == 7804,
   'V9 ★ 逐房计数合计：原作侧 %d（含缺图集 1）/ 分片侧 %d'
   % (sum(w_room.values()), sum(s_room.values())))
d96 = {k: (w_room[k], s_room[k]) for k in sorted(set(w_room) | set(s_room))
       if w_room[k] != s_room[k]}
ok(d96 == {96: (1, 0)},
   'V10 ★★ 两边**唯一**的差就是房间 96 的 `(1, 0)`（实际 %s）—— '
   '它就是缺图集的 `npc_BIG`，被**如实跳过**而不是伪造一个坐标' % (d96,))

# ---------------------------------------------------------------- 5 格尺寸/内容
sz_bad = []
empty = []
for (cn, col, row) in sorted(seen):
    sw, sh = png_size(os.path.join(PROPS, cn + '.png'))
    fn = '%s__c%dr%d.png' % (re.sub(r'[^A-Za-z0-9_-]', '_', cn), col, row)
    p = os.path.join(CELLS, fn)
    if png_size(p) != (sw // 4, sh // 4):
        sz_bad.append(fn)
    if os.path.getsize(p) <= 0:
        empty.append(fn)
ok(not sz_bad and not empty,
   'V11 每格尺寸 == 图集的 1/4 且文件非空（尺寸不符 %d / 空文件 %d）'
   % (len(sz_bad), len(empty)))

# ---------------------------------------------------------------- 6 两层登记
idx = rj(os.path.join(SCENES, '_index.json'))
inline = {}
for _an, _av in ((idx['chapters'].get('oneshot') or {}).get('areas') or {}).items():
    for sid, e in ((_av or {}).get('scenes') or {}).items():
        inline[sid] = e
ok(len(inline) == 263 and set(inline) == set(shard),
   'V12 ★ 索引内联 263 条与分片 263 条**同集合**（%d vs %d）' % (len(inline), len(shard)))
ok(not [s for s, e in inline.items() if e.get('objects')],
   'V13 索引内联副本的 `objects` 全为占位空表（非空 %d）—— 与 `meta.objects_source` '
   '的声明一致' % len([s for s, e in inline.items() if e.get('objects')]))
ok(u'区域分片' in (idx['meta'].get('objects_source') or ''),
   'V14 索引 `meta.objects_source` 写明了"物件只在区域分片"')
ok(sum(len(v) for v in shard.values()) == 7804,
   'V15 分片侧物件合计 == 7804（实际 %d）' % sum(len(v) for v in shard.values()))

# ---------------------------------------------------------------- 7 渲染 1:1
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))
from PyQt5.QtGui import QGuiApplication, QImage, QPainter                 # noqa: E402
import scene_canvas as SCV                                                # noqa: E402
import scene_camera as SCC                                                # noqa: E402
import scene_render as SR                                                 # noqa: E402
import scene_system as SS                                                 # noqa: E402
APP = QGuiApplication.instance() or QGuiApplication([])
GEO = rj(os.path.join(SCENES, '_room_geometry.json'))['rooms']
ENT = SS.load_index().get('scenes') or {}
n_obj = n_draw = 0
bad = []
for rid in sorted(room2sid):
    sid = room2sid[rid]
    sc = SS.load_scene(sid, entry=ENT.get(sid))
    if sc is None or not sc.objects:
        continue
    g = GEO.get('oneshot:%d' % rid)
    if not g:
        continue
    rw, rh = g['w'], g['h']
    cache = SCV.SceneAssetCache()
    cam = SCC.Camera((rw, rh), 0, 1.0)
    cam.follow((0.0, 0.0, float(rw), float(rh)), (0.0, 0.0, float(rw), float(rh)))
    plan = SR.plan_frame(sc, cam, GEO, tick=0, sprite_size=cache.sprite_size)
    kinds = collections.Counter(it['kind'] for it in plan)
    if kinds.get(SR.K_OBJ, 0) != len(sc.objects):
        bad.append((rid, len(sc.objects), kinds.get(SR.K_OBJ, 0)))
    img = QImage(rw, rh, QImage.Format_ARGB32_Premultiplied)
    img.fill(0)
    pt = QPainter(img)
    drew = SCV.paint_on(pt, plan, cache, view_size=(rw, rh))
    pt.end()
    n_obj += len(sc.objects)
    n_draw += drew
    if cache.missing:
        bad.append((rid, '缺素材', cache.missing[:2]))
ok(not bad and n_obj == 7804,
   'V16 ★★★ **全量 188 个有物件的场景**逐个真跑 `plan_frame`：`K_OBJ` 条数 == 物件数、'
   '真画布零缺素材（物件合计 %d；异常 %s）' % (n_obj, bad[:3]))
print('    真画布累计画出 %d 条指令' % n_draw)

print()
if FAIL:
    print('[FAIL] 共 %d 条失败' % len(FAIL))
    for f in FAIL:
        print('   - ' + f)
    sys.exit(1)
print('独立验收：全部通过（不复用 build103 的任何函数/结论）')
