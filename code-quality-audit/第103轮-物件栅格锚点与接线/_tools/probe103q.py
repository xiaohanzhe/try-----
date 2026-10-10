# -*- coding: utf-8 -*-
u"""probe103q.py —— 给 `check103` 定数值：把锁要断言的每个量**从磁盘现算一遍**。

为什么不直接抄 `objects103.json`：那份是 `build103` 自己写的**结论**。
锁必须能从**原始产物**（379 个格 PNG + 6 个区域分片 + `_index.json` +
第102轮的 `objects_census102.json`）把数复算出来，否则"锁"只是把构建脚本的
输出再读一遍 —— 构建脚本算错了也照样绿。
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
EV102 = os.path.join(ROOT, 'code-quality-audit', '第102轮-光照与ambient接入', '_evidence')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
PROPS = os.path.join(SCENES, 'oneshot_props')
CELLS = os.path.join(SCENES, 'oneshot_cells')
TILE = 16


def rj(p):
    return json.loads(re.sub(r',(\s*[}\]])', r'\1',
                             io.open(p, encoding='utf-8', newline='').read()))


def png_size(p):
    with open(p, 'rb') as fh:
        head = fh.read(33)
    return struct.unpack('>II', head[16:24])


CEN = rj(os.path.join(EV102, 'objects_census102.json'))
ZONE_FILES = sorted(f for f in os.listdir(SCENES) if f.startswith('_zone.oneshot.'))
idx = rj(os.path.join(SCENES, '_index.json'))

# ---------------------------------------------------------------- 分片里的物件
objs = []          # (zone, sid, room, obj)
for zf in ZONE_FILES:
    d = rj(os.path.join(SCENES, zf))
    for sid, ent in (d.get('scenes') or {}).items():
        if not isinstance(ent, dict):
            continue
        for o in (ent.get('objects') or []):
            objs.append((zf, sid, ent.get('original_room_id'), o))
print('分片物件 %d ｜ 有物件的场景 %d ｜ 分片 %d'
      % (len(objs), len({s for _z, s, _r, _o in objs}), len(ZONE_FILES)))

# ---------------------------------------------------------------- 格 PNG
disk = sorted(f for f in os.listdir(CELLS) if f.endswith('.png'))
extra = sorted(f for f in os.listdir(CELLS) if not f.endswith('.png'))
print('cells 目录 %d PNG ｜ 杂项 %s' % (len(disk), extra or '(无)'))
cell_size = {}
cell_sha = {}
cell_b = {}
trans = []
for f in disk:
    p = os.path.join(CELLS, f)
    im = Image.open(p).convert('RGBA')
    cell_size[f] = im.size
    if im.getchannel('A').getbbox() is None:
        trans.append(f)
    cell_b[f] = os.path.getsize(p)
    cell_sha[f] = hashlib.sha256(open(p, 'rb').read()).hexdigest()
print('全透明格 %d %s ｜ 合计 %.3f MB' % (len(trans), trans, sum(cell_b.values()) / 1048576.0))

# ---------------------------------------------------------------- 规则复算
bad_anchor = []
bad_frac = []
bad_disk = []
sheets = set()
for zf, sid, room, o in objs:
    sp = o.get('sprite') or ''
    fn = os.path.basename(sp)
    if fn not in cell_size:
        bad_disk.append((sid, sp))
        continue
    cw, ch = cell_size[fn]
    m = re.match(r'^(.*)__c(\d)r(\d)$', fn[:-4])
    sheet = m.group(1)
    sheets.add(sheet)
    # ① 栅格：格 * 4 == 图集尺寸
    ps = os.path.join(PROPS, sheet + '.png')
    sw, sh = png_size(ps)
    if (cw * 4, ch * 4) != (sw, sh):
        bad_frac.append((fn, (cw, ch), (sw, sh)))
    # ② 锚点：pos 由 tile + cell 复算
    tx, ty = o['tile']
    exp = [tx * TILE + TILE // 2 - cw // 2, ty * TILE + TILE - ch]
    if list(o['pos']) != exp:
        bad_anchor.append((sid, fn, o['tile'], o['pos'], exp))
print('物件引用 sheet %d ｜ 缺格 %d ｜ 栅格不符 %d ｜ 锚点不符 %d'
      % (len(sheets), len(bad_disk), len(bad_frac), len(bad_anchor)))
print('  样例 anchor 不符', bad_anchor[:2])

# 格 PNG 与图集裁切**逐像素**相同
mism = []
for fn in disk:
    m = re.match(r'^(.*)__c(\d)r(\d)$', fn[:-4])
    sheet, col, row = m.group(1), int(m.group(2)), int(m.group(3))
    cw, ch = cell_size[fn]
    a = Image.open(os.path.join(PROPS, sheet + '.png')).convert('RGBA')
    b = Image.open(os.path.join(CELLS, fn)).convert('RGBA')
    if a.crop((col * cw, row * ch, (col + 1) * cw, (row + 1) * ch)).tobytes() != b.tobytes():
        mism.append(fn)
print('逐像素裁切不一致 %d %s' % (len(mism), mism[:3]))

# ---------------------------------------------------------------- depth / layer
bad_depth = []
lay = collections.Counter()
for zf, sid, room, o in objs:
    ty = o['tile'][1]
    g = ty * TILE + TILE
    L = o.get('layer')
    lay[L] += 1
    exp = g - 10 ** 6 if L == 'bottom' else (g + 10 ** 6 if L == 'top' else g)
    if o['depth'] != exp:
        bad_depth.append((sid, o['tile'], L, o['depth'], exp))
print('layer %s ｜ depth 不符 %d' % (dict(lay), len(bad_depth)))
mono = []
byroom = collections.defaultdict(list)
for zf, sid, room, o in objs:
    byroom[sid].append(o)
for sid, v in byroom.items():
    key = [(o['depth'], o['tile'][1], o['tile'][0]) for o in v]
    if key != sorted(key):
        mono.append(sid)
print('场景内 (depth,tile_y,tile_x) 非降：不符 %d %s' % (len(mono), mono[:3]))

# ---------------------------------------------------------------- 两层登记
inline_nonempty = []
inline_total = 0
for an, av in ((idx['chapters'].get('oneshot') or {}).get('areas') or {}).items():
    for sid, e in ((av or {}).get('scenes') or {}).items():
        inline_total += 1
        if e.get('objects'):
            inline_nonempty.append(sid)
print('索引内联 oneshot 场景 %d ｜ 内联 objects 非空 %d' % (inline_total, len(inline_nonempty)))
print('meta.objects_source 在：%s' % ('objects_source' in (idx.get('meta') or {})))

# ---------------------------------------------------------------- 守恒
per_room = {str(r['room_id']): r['n'] for r in CEN['rooms']}
w = collections.Counter()
for zf, sid, room, o in objs:
    w[str(room)] += 1
diff = {k: (per_room[k], w.get(k, 0)) for k in per_room if per_room[k] != w.get(k, 0)}
print('census 房 %d ｜ 分片房 %d ｜ 逐房不等 %s' % (len(per_room), len(w), diff))
print('census visible %d ｜ 写入 %d ｜ 差 %d' % (CEN['counts']['visible'], len(objs),
                                              CEN['counts']['visible'] - len(objs)))
print('triples census %d ｜ 分片 distinct (sheet,col,row) %d'
      % (len(CEN['triples']), len(set(re.match(r'^(.*)__c(\d)r(\d)$', f[:-4]).groups()
                                      for f in disk))))

# ---------------------------------------------------------------- 渲染面
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
room2sid = {}
for zf in ZONE_FILES:
    for sid, e in (rj(os.path.join(SCENES, zf)).get('scenes') or {}).items():
        if isinstance(e, dict) and isinstance(e.get('original_room_id'), int):
            room2sid.setdefault(e['original_room_id'], sid)

for rid in (4, 12, 240, 43):
    sid = room2sid.get(rid)
    sc = SS.load_scene(sid, entry=ENT.get(sid))
    g = GEO['oneshot:%d' % rid]
    rw, rh = g['w'], g['h']
    cache = SCV.SceneAssetCache()
    cam = SCC.Camera((rw, rh), 0, 1.0)
    cam.follow((0.0, 0.0, float(rw), float(rh)), (0.0, 0.0, float(rw), float(rh)))
    plan = SR.plan_frame(sc, cam, GEO, tick=0, sprite_size=cache.sprite_size)
    objs_p = [it for it in plan if it['kind'] == SR.K_OBJ]
    kinds = collections.Counter(it['kind'] for it in plan)
    img = QImage(rw, rh, QImage.Format_ARGB32_Premultiplied)
    img.fill(0)
    pt = QPainter(img)
    ndraw = SCV.paint_on(pt, plan, cache, view_size=(rw, rh))
    pt.end()
    bad_rect = []
    for o, it in zip(sc.objects, objs_p):
        cw, ch = cell_size[os.path.basename(o['sprite'])]
        exp = (o['tile'][0] * TILE + TILE // 2 - cw // 2, o['tile'][1] * TILE + TILE - ch,
               cw, ch)
        if tuple(it['rect']) != exp:
            bad_rect.append((it['name'], it['rect'], exp))
    print('room%-4d %-22s %dx%d 物件 %3d ｜ K_OBJ %3d ｜ kinds %s ｜ 画出 %d ｜ 缺素材 %s ｜ rect 不符 %d'
          % (rid, sid, rw, rh, len(sc.objects), len(objs_p), dict(kinds), ndraw,
             cache.missing[:2], len(bad_rect)))
    # 负控制：挪 16px
    o0 = sc.objects[0]
    saved = list(o0['pos'])
    o0['pos'] = [saved[0] + TILE, saved[1]]
    cam2 = SCC.Camera((rw, rh), 0, 1.0)
    cam2.follow((0.0, 0.0, float(rw), float(rh)), (0.0, 0.0, float(rw), float(rh)))
    p2 = [it for it in SR.plan_frame(sc, cam2, GEO, tick=0, sprite_size=cache.sprite_size)
          if it['kind'] == SR.K_OBJ]
    o0['pos'] = saved
    print('    负控制 挪 +16px：rect[0] %d -> %d（差 %d）'
          % (objs_p[0]['rect'][0], p2[0]['rect'][0], p2[0]['rect'][0] - objs_p[0]['rect'][0]))

# ---------------------------------------------------------------- 证据等级
ga = rj(os.path.join(EV, 'grid_anchor103.json'))
ac = rj(os.path.join(EV, 'anchor_cases103.json'))
print('证据等级 vertical=%r horizontal=%r' % (ga['anchor']['vertical'], ga['anchor']['horizontal']))
print('anchor_cases: winner %s ｜ unique_bottom_center %d ｜ bottom_left %d ｜ bottom_right %d ｜ any_top %d'
      % (ac['winner_table'], ac['unique_bottom_center'], ac['unique_bottom_left'],
         ac['unique_bottom_right'], ac['any_top_winner']))
print('objects103:', json.dumps({k: v for k, v in rj(os.path.join(EV, 'objects103.json')).items()
                                 if k in ('objects_total', 'objects_written', 'skipped_missing_sheet',
                                          'rooms_with_objects', 'rooms_registered', 'unmapped_rooms',
                                          'cells', 'cells_transparent', 'layer_bottom', 'layer_top',
                                          'scenes_patched')}, ensure_ascii=False))
