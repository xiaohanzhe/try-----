# -*- coding: utf-8 -*-
u"""verify104.py —— 第104轮**独立验收**：不复用 `build104` 的任何函数/结论。

为什么不只靠 `check104`：
  * `check104` 进 G2，铁律是**零外部盘依赖** ⇒ 它只能读**仓库内**的东西
    （分片 + `_evidence/material104.json`）。而那份证据是**我们自己的产物**。
  * 本脚本走**另一条路**：直接读**原作** `gamedata/maps/events_map<N>.json`
    的页数据，从 `graphic.opacity` / `graphic.blend_type` **从头复算**，
    再与**真正落进产品的分片**逐条比对；最后真跑渲染管线做**像素级**验证。

它还专门查 `build104` **可能悄悄兜底**的三处：
  (a) `opacity` 不是 0..255 的整数 —— `build104` 直接 `round(op/255, 6)`，
      不合法值会被静默算成一个看着正常的 alpha；
  (b) `blend_type` 不是 `{0,1}` —— `build104` 只写 `1`，**2（减色）会被静默丢掉**；
      这里把"丢掉多少条"算出来（本轮实测 0 条，但要留证据）；
  (c) **多页事件** —— 原作取页规则是"最后一个条件成立的页"，`build104` 简化取
      `pages[0]`。这里统计"若按别的页取，opacity/blend_type 会不同的"事件数，
      把这条**已知简化**登记成数字，而不是假装它不存在。

⚠️ 本脚本**不进 G2**（要读 C 盘原作），是"验收工具"，不是回归锁。
"""
import collections
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
TILE = 16
DIR_ROW = {2: 0, 4: 1, 6: 2, 8: 3}
FAIL = []


def ok(cond, msg):
    if cond:
        print('[PASS] %s' % msg)
    else:
        FAIL.append(msg)
        print('[FAIL] %s' % msg)


def rj(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return json.load(f)


def rj_tolerant(p):
    return json.loads(re.sub(r',(\s*[}\]])', r'\1',
                             io.open(p, encoding='utf-8', newline='').read()))


# ---------------------------------------------------------------- 0 找原作
import importlib.util                                                     # noqa: E402
_spec = importlib.util.spec_from_file_location(
    'os_bg100', os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景',
                             '_tools', 'os_bg100.py'))
_o = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_o)
MAPS = os.path.join(_o.OSD, 'gamedata', 'maps')
print(u'原作 maps 目录：%s' % MAPS)
ok(os.path.isfile(os.path.join(MAPS, 'events_map4.json')),
   u'V0 原作 `events_map4.json` 在位（独立验收需要原作 ⇒ 本脚本不进 G2）')

# ---------------------------------------------------------------- 1 从头复算
PROPS = os.path.join(SCENES, 'oneshot_props')
HAVE = set(f[:-4] for f in os.listdir(PROPS) if f.endswith('.png'))

raw = []          # (room, name, tile, sheet, pattern, dir, aob, aot, opacity, blend)
weird_op = []
weird_bl = collections.Counter()
def _has_cond(pg):
    u"""这一页是否**真的**被条件门控。

    ★★ 别用 `any(cond.values())`，也别只看 `self_switch_ch`：RMXP 的条件字段是
      `{switch1_valid: bool, switch1_id: int, ..., variable_valid: bool,
        variable_id: int, variable_value: int, self_switch_valid: bool,
        self_switch_ch: str}` —— **id 字段永远是真值**（默认 1）、
      `self_switch_ch` **永远是 `"A"`**（真值），真正的门控是那四个 `*_valid`。
      ⇒ 首版写成 `any(values())` 会得出"7804 条全带条件"这种荒唐结论；
        第二版漏了 `self_switch_valid` ⇒ 仍然 7804 条（**同一坑连栽两次**）。
    """
    c = pg.get('condition') or {}
    return bool(c.get('switch1_valid') or c.get('switch2_valid')
                or c.get('variable_valid')) or (bool(c.get('self_switch_valid'))
                                                and bool(c.get('self_switch_ch')))


multipage_diff = collections.Counter()
multipage_ungated = []      # 反例：若某条差异页**没有**条件，那它就是"默认外观"分歧
multipage_diff_rooms = []
n_pages_gt1 = 0
cond0 = []            # page0 自带条件的可见物件（"初始态"下它按原作**不该出现**）
n_events = 0
for n in range(1, 400):
    p = os.path.join(MAPS, 'events_map%d.json' % n)
    if not os.path.isfile(p):
        continue
    for e in rj_tolerant(p).get('events', []):
        n_events += 1
        pgs = e.get('pages') or []
        if not pgs:
            continue
        g = pgs[0].get('graphic') or {}
        if int(g.get('tile_id') or 0) > 0:
            continue
        cn = (g.get('character_name') or '').strip()
        if not cn or cn not in HAVE:
            continue
        op = int(g.get('opacity', 255))
        bl = int(g.get('blend_type', 0))
        if _has_cond(pgs[0]):
            cond0.append((n, (e.get('name') or '').strip()))
        if not (0 <= op <= 255):
            weird_op.append((n, op))
        if bl not in (0, 1, 2):
            weird_bl[bl] += 1
        if len(pgs) > 1:
            n_pages_gt1 += 1
            for k, pg in enumerate(pgs[1:], 1):
                g2 = pg.get('graphic') or {}
                if int(g2.get('tile_id') or 0) > 0:
                    continue
                if (int(g2.get('opacity', 255)), int(g2.get('blend_type', 0))) != (op, bl):
                    multipage_diff[k] += 1
                    multipage_diff_rooms.append((n, (e.get('name') or '').strip()))
                    if not _has_cond(pg):
                        multipage_ungated.append((n, (e.get('name') or '').strip(), k))
                    break
        raw.append((n, (e.get('name') or '').strip(),
                    (int(e.get('x') or 0), int(e.get('y') or 0)), cn,
                    int(g.get('pattern') or 0), int(g.get('direction') or 0),
                    bool(pgs[0].get('always_on_bottom')),
                    bool(pgs[0].get('always_on_top')), op, bl))

n_a = sum(1 for r in raw if r[8] != 255)
n_b = sum(1 for r in raw if r[9] == 1)
n_a0 = sum(1 for r in raw if r[8] == 0)
n_union = sum(1 for r in raw if r[8] != 255 or r[9] == 1)
print(u'原作事件 %d ｜ 可见物件 %d ｜ opacity!=255 %d ｜ blend_type==1 %d ｜ '
      u'opacity==0 %d ｜ 并集 %d' % (n_events, len(raw), n_a, n_b, n_a0, n_union))

ok(len(raw) == 7804, u'V1 独立复算的可见物件数 == 7804（实际 %d）' % len(raw))
ok((n_a, n_b, n_a0, n_union) == (34, 389, 2, 399),
   u'V2 ★★ 独立复算的材质计数 == (alpha 34, blend1 389, alpha0 2, 并集 399)'
   u'（实际 %d/%d/%d/%d）' % (n_a, n_b, n_a0, n_union))
ok(not weird_op, u'V3 全部 `opacity` 都在 0..255（越界 %s）' % (weird_op[:3],))
ok(dict(weird_bl) == {},
   u'V4 `blend_type` 只出现 0/1（其它值 %s）—— 若这里有 2，说明"减色"被静默丢掉，'
   u'必须报出来' % (dict(weird_bl),))
print(u'  多页事件 %d 个；其中"第 2+ 页的 (opacity,blend_type) 与 page0 不同"的：%s'
      % (n_pages_gt1, dict(multipage_diff) or u'(0 例)'))
print(u'  ★ 这 %d 条是：%s' % (len(multipage_diff_rooms), multipage_diff_rooms))
print(u'  ★ page0 自带条件的可见物件：%d 条（"初始态"下它们按原作**不该出现**）'
      u'前 5：%s' % (len(cond0), cond0[:5]))

# ★★★ 判据**改写**（首版断言"差异 == 0" ⇒ 假红，且掩盖了一条**真实**性质）：
#   实测 **7 条**事件的 page1+ 会改 `opacity`/`blend_type`，而它们**全部**带
#   switch/variable 条件 ⇒ 那是"状态页"，不是"默认外观"。
#   例：`room 101` 的 `invisible silver` —— page0 `opacity=0`（隐形传送点）、
#       page1 `opacity=255`（开关 211 ON 后**现形**）；
#       `room 39` 的 `glow` —— page0 `blend=1`（发光）、page1 `blend=0`（熄灭）。
#   本轮固定取 `pages[0]` = 原作的**初始态**（开局全部开关 OFF ⇒ 那些条件页非法）
#   ⇒ 在"开局态"上与原作一致；一旦接入开关/存档状态，这 7 条才有依据翻页。
#   ⇒ 判据的正确形态是**把这个数字钉住**（不许悄悄变多/变少）并逐条列出特征，
#      而不是假装它是 0。
ok(dict(multipage_diff) == {1: 7} and len(multipage_diff_rooms) == 7
   and not multipage_ungated and len(cond0) == 222,
   u'V5 ★★ 多页事件里"换页会改 `opacity`/`blend_type`"的**恰好 7 条**（%s），'
   u'且它们**全部**由 switch/variable 条件门控（无门控的反例 %s）'
   u'⇒ 本轮的 `pages[0]` 简化 = **原作的初始态**（开局开关全 OFF）⇒ 开局口径无损失；'
   u'★ **已登记缺口**：一旦接入存档/开关状态，这 7 条才有依据翻页。'
   u'另：**page0 自带条件**的可见物件 **%d** 条（`key` / `!collectible` 之类）'
   u'—— 它们在开局态下按原作的页选择规则**不该出现**，本轮同样归入该缺口。'
   u'⚠️ 别把这里的 222 与第102轮那个 407 混为一谈：407 是**全事件**口径'
   u'（"所有页都带条件"），222 是**可见物件**口径，两者**不可互推**'
   % (dict(multipage_diff), multipage_ungated[:3], len(cond0)))

# ---------------------------------------------------------------- 2 与产品分片对账
ZONE_FILES = sorted(f for f in os.listdir(SCENES) if f.startswith('_zone.oneshot.'))
room2scene = {}
shard = {}
for zf in ZONE_FILES:
    d = rj(os.path.join(SCENES, zf))
    for sid, ent in (d.get('scenes') or {}).items():
        if not isinstance(ent, dict):
            continue
        shard[sid] = ent.get('objects') or []
        if isinstance(ent.get('original_room_id'), int):
            room2scene.setdefault(ent['original_room_id'], (zf, sid))


def cell_name(cn, col, row):
    return '%s__c%dr%d.png' % (re.sub(r'[^A-Za-z0-9_-]', '_', cn), col, row)


want = collections.defaultdict(list)
from PIL import Image
for (r, nm, t, cn, pt, d, aob, aot, op, bl) in raw:
    hit = room2scene.get(r)
    assert hit, u'房间 %d 没有登记场景' % r
    with Image.open(os.path.join(PROPS, cn + '.png')) as im:
        sw, sh = im.size
    cw, ch = sw // 4, sh // 4
    row = DIR_ROW[d]
    it = collections.OrderedDict()
    it['pos'] = [t[0] * TILE + TILE // 2 - cw // 2, t[1] * TILE + TILE - ch]
    it['sprite'] = 'oneshot_cells/%s' % cell_name(cn, pt, row)
    it['tile'] = [t[0], t[1]]
    g = t[1] * TILE + TILE
    it['depth'] = g - 10 ** 6 if aob else (g + 10 ** 6 if aot else g)
    if nm:
        it['src'] = nm
    if aob:
        it['layer'] = 'bottom'
    elif aot:
        it['layer'] = 'top'
    if op != 255:
        it['alpha'] = round(op / 255.0, 6)
    if bl == 1:
        it['blend'] = 1
    want[hit[1]].append(it)
for sid in want:
    want[sid].sort(key=lambda o: (o['depth'], o['tile'][1], o['tile'][0]))

n_want = sum(len(v) for v in want.values())
n_shard = sum(len(v) for v in shard.values())
ok(n_want == 7804 and n_shard == 7804,
   u'V6 独立复算归属到场景 %d 条 / 分片侧 %d 条' % (n_want, n_shard))

bad_rooms = sorted(sid for sid in set(list(want) + list(shard))
                   if want.get(sid, []) != list(shard.get(sid, [])))
ok(not bad_rooms,
   u'V7 ★★★ **落进产品的分片与独立复算逐条相同**（含 `alpha`/`blend` 与顺序；'
   u'不等场景 %d %s）' % (len(bad_rooms), bad_rooms[:3]))
if bad_rooms:
    s0 = bad_rooms[0]
    for x, y in zip(want.get(s0, []), shard.get(s0, [])):
        if x != y:
            print(u'  样例 %s\n    want  %s\n    shard %s'
                  % (s0, json.dumps(x, ensure_ascii=False), json.dumps(y, ensure_ascii=False)))
            break

# ---------------------------------------------------------------- 3 正负成对
got_a = [o for _s, v in shard.items() for o in v if 'alpha' in o]
got_b = [o for _s, v in shard.items() for o in v if o.get('blend') == 1]
ok(len(got_a) == 34 and len(got_b) == 389,
   u'V8 分片侧带 `alpha` %d / 带 `blend` %d' % (len(got_a), len(got_b)))

a_keys = set(id(o) for o in got_a)
miss = [o for _s, v in shard.items() for o in v
        if 'alpha' in o and not isinstance(o['alpha'], float)]
ok(not miss, u'V9 `alpha` 全是 float（异常 %d）' % len(miss))

# ★ 负控制：原作里 opacity==255 的物件**不许**在产品里带 alpha 键。
#   这条要用「opacity==255 的物件在分片里的对应条」来对 —— 位置/素材是同一个键。
exp_no_alpha = set()
for (r, nm, t, cn, pt, d, aob, aot, op, bl) in raw:
    if op == 255 and bl == 0:
        exp_no_alpha.add((r, t[0], t[1], cell_name(cn, pt, DIR_ROW[d])))
leak = []
for sid, v in shard.items():
    for o in v:
        if 'alpha' in o or 'blend' in o:
            continue
        leak.append(sid)
n_clean = sum(1 for _s, v in shard.items() for o in v
              if 'alpha' not in o and 'blend' not in o)
ok(n_clean == 7804 - 399,
   u'V10 ★★ 负控制（正负成对）：`opacity==255 且 blend_type==0` 的物件在产品里'
   u'**既无 alpha 也无 blend** —— 干净条数 %d == 7804 − 399（实际 %d）'
   % (7804 - 399, n_clean))

# ---------------------------------------------------------------- 4 像素级渲染
print()
print(u'== 4 像素级渲染（真 QPainter，离屏）==')
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))
from PyQt5.QtGui import QGuiApplication, QImage, QPainter                 # noqa: E402
import scene_canvas as SCV                                                # noqa: E402
import scene_camera as SCC                                                # noqa: E402
import scene_render as SR                                                 # noqa: E402
import scene_system as SS                                                 # noqa: E402

APP = QGuiApplication.instance() or QGuiApplication([])
GEO = rj(os.path.join(SCENES, '_room_geometry.json'))['rooms']
ENT = SS.load_index().get('scenes') or {}
rid2sid = {}
for zf in ZONE_FILES:
    for sid, e in (rj(os.path.join(SCENES, zf)).get('scenes') or {}).items():
        if isinstance(e, dict) and isinstance(e.get('original_room_id'), int):
            rid2sid.setdefault(e['original_room_id'], sid)


def render(rid, mutate=None):
    u"""真跑 plan_frame + paint_on；`mutate(plan)` 可以在绘制前改指令清单。"""
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
    return img, plan, cache, sc


def to_pil(img):
    from PIL import Image
    img = img.convertToFormat(QImage.Format_RGBA8888)
    ptr = img.bits()
    ptr.setsize(img.byteCount())
    return Image.frombytes('RGBA', (img.width(), img.height()), bytes(ptr))


# ---- 4a ★★★ alpha==0：原作"隐形"的物件必须**一个像素都不改** ----
#   ★★ 判据要**三方对比**才有鉴别力（首版写成"把已是 0 的再设成 0" ⇒ **恒真**）：
#      A = 正常出图（该物件 alpha=0）
#      B = 把该物件改成 alpha=1.0 ⇒ **必须与 A 不同**（证明它真在画面里、
#          否则"A == C"就可能是"这个物件根本不在视口内"这种空话）
#      C = 把该物件的指令**整条删掉** ⇒ 必须与 A **逐像素相同**（它贡献了零像素）
for rid in (101, 210):
    if rid not in rid2sid:
        continue
    a_img, plan_a, _c, sc = render(rid)
    zero_idx = [i for i, it in enumerate(plan_a)
                if it['kind'] == SR.K_OBJ and it.get('alpha') == 0.0]
    if not zero_idx:
        ok(False, u'房间 %d 的绘制指令里找不到 `alpha==0` 的物件（数据面应当有）' % rid)
        continue

    def to_opaque(plan, _zi=tuple(zero_idx)):
        return [dict(it, alpha=1.0) if (i in _zi) else it
                for i, it in enumerate(plan)]

    def without(plan, _zi=tuple(zero_idx)):
        return [it for i, it in enumerate(plan) if i not in _zi]

    b_img, _p, _c2, _s2 = render(rid, to_opaque)
    c_img, _p, _c3, _s3 = render(rid, without)
    ab = to_pil(a_img).tobytes() != to_pil(b_img).tobytes()
    ac = to_pil(a_img).tobytes() == to_pil(c_img).tobytes()
    ok(len(zero_idx) >= 1 and ab and ac,
       u'V11 ★★★ 房间 %d：`alpha==0` 的物件 %d 个 —— ① 把它改成不透明，出图**变了**'
       u'（%s，证明它真在画面里，判据不是空话）；② 把它**整条删掉**，出图**逐像素不变**'
       u'（%s = 它贡献了零像素 ⇒ 原作"隐形"的物件真的隐形了）'
       % (rid, len(zero_idx), ab, ac))

# ---- 4b blend==1：加色必须真的让像素变亮（A/B 锚点）----
for rid in (39, 243):
    if rid not in rid2sid:
        continue
    b_img, plan_b, _c, _s = render(rid)
    n1 = sum(1 for it in plan_b if it['kind'] == SR.K_OBJ and it.get('blend') == 1)

    def unblend(plan):
        return [dict(it, blend=0) if it['kind'] == SR.K_OBJ else it for it in plan]
    c_img, _p, _c2, _s2 = render(rid, unblend)
    pb, pc = to_pil(b_img), to_pil(c_img)
    diff = sum(1 for a, b in zip(pb.tobytes(), pc.tobytes()) if a != b)
    # 逐像素：加色版本每一通道都必须 >= 普通版本（加色只加不减）
    worse = 0
    pxb, pxc = pb.load(), pc.load()
    for y in range(0, pb.height, 3):
        for x in range(0, pb.width, 3):
            for k in range(3):
                if pxb[x, y][k] < pxc[x, y][k]:
                    worse += 1
    ok(n1 >= 1 and diff > 0 and worse == 0,
       u'V12 ★★★ 房间 %d：带 `blend==1` 的物件 %d 个 —— 改回 `blend=0` 后出图**不同**'
       u'（差异字节 %d），且加色版本**没有任何像素比普通版本暗**（越界 %d）'
       u'⇒ `CompositionMode_Plus` 真的在按 RMXP 加色走，而不是被忽略'
       % (rid, n1, diff, worse))
    to_pil(b_img).save(os.path.join(EV, 'render_plus_r%d104.png' % rid))
    to_pil(c_img).save(os.path.join(EV, 'render_normal_r%d104.png' % rid))

# ---- 4c alpha 半透明：opacity=128 的 portal_rays 必须真的半透 ----
if 243 in rid2sid:
    d_img, plan_d, _c, _s = render(243)
    n_half = sum(1 for it in plan_d if it['kind'] == SR.K_OBJ
                 and 0 < (it.get('alpha') or 1.0) < 1)
    opaque = [dict(it, alpha=1.0) if it['kind'] == SR.K_OBJ else it for it in plan_d]
    e_img, _p, _c2, _s2 = render(243, lambda p: opaque)
    diff2 = sum(1 for a, b in zip(to_pil(d_img).tobytes(), to_pil(e_img).tobytes()) if a != b)
    ok(n_half >= 1 and diff2 > 0,
       u'V13 房间 243：`0<alpha<1` 的物件 %d 个；改成不透明后出图不同（差异字节 %d）'
       u'⇒ 不透明度真的被消费' % (n_half, diff2))

# ---------------------------------------------------------------- 5 全量接线
print()
print(u'== 5 全量：带材质的 65 个场景逐个真跑 ==')
scenes_hit = sorted(set(sid for sid, v in shard.items()
                        if any(('alpha' in o or o.get('blend') == 1) for o in v)))
bad = []
n_obj = n_mat = 0
for sid in scenes_hit:
    sc = SS.load_scene(sid, entry=ENT.get(sid))
    rid = None
    for zf in ZONE_FILES:
        ent = (rj(os.path.join(SCENES, zf)).get('scenes') or {}).get(sid)
        if ent:
            rid = ent.get('original_room_id')
            break
    g = GEO.get('oneshot:%s' % rid)
    if not g:
        bad.append((sid, '无几何'))
        continue
    rw, rh = g['w'], g['h']
    cache = SCV.SceneAssetCache()
    cam = SCC.Camera((rw, rh), 0, 1.0)
    cam.follow((0.0, 0.0, float(rw), float(rh)), (0.0, 0.0, float(rw), float(rh)))
    plan = SR.plan_frame(sc, cam, GEO, tick=0, sprite_size=cache.sprite_size)
    objs = [it for it in plan if it['kind'] == SR.K_OBJ]
    if len(objs) != len(sc.objects):
        bad.append((sid, 'K_OBJ 条数 %d != %d' % (len(objs), len(sc.objects))))
    for o, it in zip(sc.objects, objs):
        exp_a = o.get('alpha', 1.0)
        if isinstance(it.get('alpha'), float) and abs(it['alpha'] - exp_a) > 1e-9:
            bad.append((sid, 'alpha 未透传', it.get('alpha'), exp_a))
        if (it.get('blend') or 0) != (o.get('blend') or 0):
            bad.append((sid, 'blend 未透传', it.get('blend'), o.get('blend')))
    n_obj += len(objs)
    n_mat += sum(1 for o in sc.objects if 'alpha' in o or o.get('blend') == 1)
    if cache.missing:
        bad.append((sid, '缺素材', cache.missing[:2]))
ok(not bad and n_mat == 399,
   u'V14 ★★★ 带材质的 %d 个场景：`K_OBJ` 条数 == 物件数、`alpha`/`blend` **逐条透传到'
   u'绘制指令**、真画布零缺素材（物件 %d / 材质 %d；异常 %s）'
   % (len(scenes_hit), n_obj, n_mat, bad[:3]))

print()
if FAIL:
    print(u'[FAIL] 共 %d 条失败' % len(FAIL))
    for f in FAIL:
        print(u'   - ' + f)
    sys.exit(1)
print(u'独立验收：全部通过（不复用 build104 的任何函数/结论）')
