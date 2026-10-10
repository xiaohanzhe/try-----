# -*- coding: utf-8 -*-
u"""sheet103.py —— 第103轮出图：**把真实 plan_frame 的输出画成 PNG**（走真画布）。

为什么要走真画布（`scene_canvas.SceneAssetCache` + `paint_on`）而不是自己拼图：
  ① 只有它会**真的按名字解析路径** ⇒ 能抓到"`oneshot_cells/x.png` 解析不到"这类
     数据对了但画不出来的错；
  ② 它就是产品真机用的那条路径（第99轮的真机症状都从这条路上暴露）。
相机 = **整间房 1:1**（`scale=1.0`、output 尺寸 = 房间尺寸）⇒ 出图可与
`bg/oneshot_map<N>.png` 直接逐像素对照。
"""
import importlib.util
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
EV = os.path.join(HERE, '..', '_evidence')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))

from PyQt5.QtGui import QGuiApplication, QImage, QPainter                 # noqa: E402
import scene_canvas as SCV                                                # noqa: E402
import scene_camera as SCC                                                # noqa: E402
import scene_render as SR                                                 # noqa: E402
import scene_system as SS                                                 # noqa: E402

APP = QGuiApplication.instance() or QGuiApplication([])

ROOMS = [4, 12, 240, 43]


def rj(p):
    return json.loads(re.sub(r',(\s*[}\]])', r'\1',
                             io.open(p, encoding='utf-8', newline='').read()))


GEO = rj(os.path.join(SCENES, '_room_geometry.json'))['rooms']
room2sid = {}
for f in sorted(os.listdir(SCENES)):
    if not f.startswith('_zone.oneshot.'):
        continue
    for sid, e in (rj(os.path.join(SCENES, f)).get('scenes') or {}).items():
        if isinstance(e, dict) and isinstance(e.get('original_room_id'), int):
            room2sid.setdefault(e['original_room_id'], sid)
IDX = SS.load_index()
ENTRIES = IDX.get('scenes') or {}

print('=' * 96)
print('整间房 1:1 真渲染（真画布 + 真路径解析）')
print('=' * 96)
rows = []
for rid in ROOMS:
    sid = room2sid.get(rid)
    if not sid:
        print('  room%-4d 无登记场景' % rid)
        continue
    sc = SS.load_scene(sid, entry=ENTRIES.get(sid))
    g = GEO.get('oneshot:%d' % rid)
    rw, rh = g['w'], g['h']
    n_obj = len(sc.objects)
    # 独立核对：每个物件的 sprite 文件必须**真在盘上**
    miss_file = [o['sprite'] for o in sc.objects
                 if not os.path.isfile(os.path.join(SCENES, o.get('sprite') or ''))]
    cache = SCV.SceneAssetCache()
    cam = SCC.Camera((rw, rh), 0, 1.0)
    cam.follow((0.0, 0.0, float(rw), float(rh)), (0.0, 0.0, float(rw), float(rh)))
    plan = SR.plan_frame(sc, cam, GEO, tick=0, sprite_size=cache.sprite_size)
    kinds = {}
    for it in plan:
        kinds[it['kind']] = kinds.get(it['kind'], 0) + 1

    def _render(objs, tag):
        sc.objects = objs
        cam2 = SCC.Camera((rw, rh), 0, 1.0)
        cam2.follow((0.0, 0.0, float(rw), float(rh)),
                    (0.0, 0.0, float(rw), float(rh)))
        pl = SR.plan_frame(sc, cam2, GEO, tick=0, sprite_size=cache.sprite_size)
        img = QImage(rw, rh, QImage.Format_ARGB32_Premultiplied)
        img.fill(0)
        pt = QPainter(img)
        n = SCV.paint_on(pt, pl, cache, view_size=(rw, rh))
        pt.end()
        out = os.path.join(EV, 'render_map%d%s_103.png' % (rid, tag))
        img.save(out)
        return n, out, len(pl)

    n_all, out_all, nplan = _render(sc.objects, '')
    n_bg, out_bg, _ = _render([], '_bgonly')
    print('  room%-4d %-14s %s 物件 %3d 缺文件 %d | plan %3d 条 %s'
          % (rid, sid.split('.')[-1], '%dx%d' % (rw, rh), n_obj, len(miss_file),
             nplan, kinds))
    print('       画出 %3d 条 -> %s' % (n_all, os.path.basename(out_all)))
    print('       仅背景 %3d 条 -> %s' % (n_bg, os.path.basename(out_bg)))
    if miss_file:
        print('       ★ 缺文件 %s' % miss_file[:3])
    if cache.missing:
        print('       ★ 画布报缺素材 %s' % cache.missing[:3])
    rows.append(dict(room=rid, sid=sid, w=rw, h=rh, objects=n_obj,
                     plan_items=nplan, kinds=kinds, drawn=n_all,
                     drawn_bg_only=n_bg, missing_files=miss_file,
                     cache_missing=cache.missing,
                     png=os.path.basename(out_all), png_bg=os.path.basename(out_bg)))

print()
print('=' * 96)
print('★ 全量：7804 个物件的素材路径逐个查盘')
print('=' * 96)
bad = []
tot = 0
for sid, entry in ENTRIES.items():
    if not sid.startswith('oneshot.'):
        continue
    sc = SS.load_scene(sid, entry=entry)
    if sc is None:
        continue
    for o in sc.objects:
        tot += 1
        sp = o.get('sprite') or ''
        if not os.path.isfile(os.path.join(SCENES, sp)):
            bad.append((sid, sp))
print('  查了 %d 个物件；文件不在盘上 %d 个 %s' % (tot, len(bad), bad[:5]))

io.open(os.path.join(EV, 'render103.json'), 'w', encoding='utf-8',
        newline='\n').write(json.dumps(
            dict(note='第103轮真渲染（整间房 1:1，真画布）', rooms=rows,
                 path_check=dict(objects=tot, missing=len(bad), bad=bad[:20])),
            ensure_ascii=False, indent=1))
print('  证据 -> _evidence/render103.json')
