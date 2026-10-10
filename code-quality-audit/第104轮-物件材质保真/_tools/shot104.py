# -*- coding: utf-8 -*-
u"""shot104.py —— 第104轮的**目视证据**：把"材质接没接上"画成左右对照图。

口径（用户）：「**一定要看录像而不是只读后台输出**」。场景系统这一层的等价物
就是**真跑渲染管线出图**（`scene_render.plan_frame` → `scene_canvas.paint_on`
→ 真 `QImage`），而不是只看 PASS 计数。

产出（落 `_evidence/`）：
  · `cmp_material_r101_104.png`  房间 101：现状（`opacity=0` **隐形**）｜ 强制不透明
  · `cmp_material_r210_104.png`  房间 210：同上（`invisi-proto`）
  · `cmp_material_r39_104.png`   房间 39 ：加色（`blend=1`）｜ 普通叠加
  · `cmp_material_r243_104.png`  房间 243：加色（3 条 `portal_rays`）｜ 普通叠加

用法：`python shot104.py`（离屏，不弹窗；`QT_QPA_PLATFORM=offscreen`）
"""
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

from PyQt5.QtGui import QGuiApplication, QImage, QPainter                  # noqa: E402
from PIL import Image, ImageDraw                                          # noqa: E402
import scene_canvas as SCV                                                # noqa: E402
import scene_camera as SCC                                                # noqa: E402
import scene_render as SR                                                 # noqa: E402
import scene_system as SS                                                 # noqa: E402

APP = QGuiApplication.instance() or QGuiApplication([])


def rj(p):
    return json.loads(re.sub(r',(\s*[}\]])', r'\1',
                             io.open(p, encoding='utf-8', newline='').read()))


GEO = rj(os.path.join(SCENES, '_room_geometry.json'))['rooms']
ENT = SS.load_index().get('scenes') or {}
ZONE_FILES = sorted(f for f in os.listdir(SCENES) if f.startswith('_zone.oneshot.'))
rid2sid = {}
for zf in ZONE_FILES:
    for sid, e in (rj(os.path.join(SCENES, zf)).get('scenes') or {}).items():
        if isinstance(e, dict) and isinstance(e.get('original_room_id'), int):
            rid2sid.setdefault(e['original_room_id'], sid)


def render(rid, mutate=None):
    sid = rid2sid[rid]
    sc = SS.load_scene(sid, entry=ENT.get(sid))
    g = GEO['oneshot:%d' % rid]
    rw, rh = g['w'], g['h']
    cache = SCV.SceneAssetCache()
    cam = SCC.Camera((rw, rh), 0, 1.0)
    cam.follow((0.0, 0.0, float(rw), float(rh)), (0.0, 0.0, float(rw), float(rh)))
    plan = SR.plan_frame(sc, cam, GEO, tick=0, sprite_size=cache.sprite_size)
    if mutate:
        plan = mutate(plan)
    img = QImage(rw, rh, QImage.Format_ARGB32_Premultiplied)
    img.fill(0)
    pt = QPainter(img)
    SCV.paint_on(pt, plan, cache, view_size=(rw, rh))
    pt.end()
    return img, plan, sc


def to_pil(img):
    img = img.convertToFormat(QImage.Format_RGBA8888)
    ptr = img.bits()
    ptr.setsize(img.byteCount())
    return Image.frombytes('RGBA', (img.width(), img.height()), bytes(ptr)).convert('RGB')


def save_cmp(rid, mutate, tag, name, zoomname=None, scale=4, pad=24):
    a, plan, sc = render(rid)
    b, _p, _s = render(rid, mutate)
    pa, pb = to_pil(a), to_pil(b)
    w, h = pa.size
    top = 18
    out = Image.new('RGB', (w * 2 + 8, h + top), (24, 24, 24))
    out.paste(pa, (0, top))
    out.paste(pb, (w + 8, top))
    d = ImageDraw.Draw(out)
    d.text((4, 4), 'A: as shipped (104)', fill=(255, 255, 255))
    d.text((w + 12, 4), 'B: %s' % tag, fill=(255, 210, 80))
    p = os.path.join(EV, name)
    out.save(p)
    # ★ 自证：A/B 必须真的不同（否则这张对照图没有信息量）
    diff = sum(1 for x, y in zip(pa.tobytes(), pb.tobytes()) if x != y)
    print(u'%s  room %d  %dx%d  bytes-diff=%d' % (name, rid, w, h, diff))

    # ★★ 整间房太宽的话，材质物件只有十几像素 —— 再出一张**放大 4 倍**的局部图，
    #    否则"看得见"这件事就只是我嘴上说的（用户口径：一定要看，而不是只读输出）。
    if zoomname:
        xs, ys = [], []
        for it in plan:
            if it['kind'] == SR.K_OBJ and (it.get('alpha', 1.0) != 1.0
                                           or it.get('blend')):
                x, y, ow, oh = it['rect']
                xs += [x, x + ow]
                ys += [y, y + oh]
        if xs:
            x0 = max(0, min(xs) - pad)
            y0 = max(0, min(ys) - pad)
            x1 = min(w, max(xs) + pad)
            y1 = min(h, max(ys) + pad)
            za = pa.crop((x0, y0, x1, y1)).resize(
                ((x1 - x0) * scale, (y1 - y0) * scale), Image.NEAREST)
            zb = pb.crop((x0, y0, x1, y1)).resize(
                ((x1 - x0) * scale, (y1 - y0) * scale), Image.NEAREST)
            zw, zh = za.size
            zo = Image.new('RGB', (zw * 2 + 8, zh + top), (24, 24, 24))
            zo.paste(za, (0, top))
            zo.paste(zb, (zw + 8, top))
            dz = ImageDraw.Draw(zo)
            dz.text((4, 4), 'A: as shipped  x%d  (zoom)' % scale, fill=(255, 255, 255))
            dz.text((zw + 12, 4), 'B: %s' % tag, fill=(255, 210, 80))
            zo.save(os.path.join(EV, zoomname))
            print(u'   %s  局部放大 x%d  裁剪 %s' % (zoomname, scale, (x0, y0, x1, y1)))
    return diff


_FORCE_OPAQUE = (lambda p: [dict(it, alpha=1.0)
                            if (it['kind'] == SR.K_OBJ and it.get('alpha') == 0.0)
                            else it for it in p])
_PLAIN = (lambda p: [dict(it, blend=0) if it['kind'] == SR.K_OBJ else it for it in p])

d1 = save_cmp(101, _FORCE_OPAQUE, 'B: alpha forced to 1 (would be visible)',
              'cmp_material_r101_104.png', 'zoom_material_r101_104.png')
d2 = save_cmp(210, _FORCE_OPAQUE, 'B: alpha forced to 1 (would be visible)',
              'cmp_material_r210_104.png', 'zoom_material_r210_104.png')
d3 = save_cmp(39, _PLAIN, 'B: blend disabled (plain SourceOver)',
              'cmp_material_r39_104.png', 'zoom_material_r39_104.png')
d4 = save_cmp(243, _PLAIN, 'B: blend disabled (plain SourceOver)',
              'cmp_material_r243_104.png', 'zoom_material_r243_104.png')

print()
print(u'★ 四张对照图的 A/B 差异字节：%s —— 全部 > 0 才算"这张图有信息量"'
      % ([d1, d2, d3, d4],))
sys.exit(0 if all(x > 0 for x in (d1, d2, d3, d4)) else 1)
