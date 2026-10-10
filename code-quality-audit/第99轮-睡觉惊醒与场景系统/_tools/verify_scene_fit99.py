# -*- coding: utf-8 -*-
u"""第99轮 · 「场景系统 = 把原作全屏化」回归锁（`fit_bg_world` + `K_ROOM_FILL`）。

用户口径（本轮逐字）
--------------------
    「那个场景系统就像是**把原作全屏化**似的，但**不是真的全屏，只是说像**哦」
    「（第44轮原始设计）场景图就和 ralsei 现在桌宠的体积与原作 ralsei 体积的
      比例**等比放大**，**剩下的用黑色填充**就好这样不违和」

本套件锁的是**本轮修掉的那条真缺陷**（真机 + 数据双证）：
    背景 PNG 是**屏幕像素分辨率**的截图（房间 320×240 ↔ 素材 640×480），
    而旧代码把"素材像素"当"世界逻辑单位"铺在房间原点 ⇒
      ① 素材比房间小 → 相机跟到房间另一侧时背景**整条出界** ⇒ 屏幕上零像素
         （`card_castle_1f` 真机：房间 1840×1080 / 素材 1280×751，相机 (1385,787)
          的视口与素材世界矩形无交集 ⇒ plan 只剩一条**窗口外**的 room_border
          ⇒ `canvas.grab()` 非透明采样 = 0 ⇒ 壁纸直接透出来）；
      ② 素材不小于房间 → 背景被额外放大 2 倍，用户只看到房间的**一个角**
         （`kris_s_room` 离线渲染对照：现状只显示左上 1/4，原作里整间房恰好一屏）。

判据分六段：
  A 口径在位（用户原话 + 两条被推翻的旧注释都已改写）
  B `fit_bg_world` 纯函数正负成对（含"必然盖满"这条**不变量**）
  C `plan_frame`：黑底在最前 / bg 盖满视口 / 桌面场景不透黑
  D 画布消费：`room_fill` 落笔、颜色取指令、顺序最底
  E ★ **全量普查不变量**（235 个真背景场景逐个跑，机器统计，零例外）
  G ★ 原作 `visible=False` 的**不可见触发器**不许画（真机第二缺陷：一屋子品红框）
  F 接线与纪律（零依赖 / 新 kind 两模块对齐 / 桌面场景不被盖）

★ 铁律：
  · 成功标记必须 `[PASS]` 字面量（`run_all.py` 按它计数）。
  · 正/负控制成对；**恒真判据比不写还危险**。
  · 行为判据必须用**真实量级输入**（房间/素材尺寸全部取自仓库真值）。
  · 判据名禁自带标记；本套件**不起真机**（零 Qt 窗口，只有 PyQt5 import 级）。
"""
import ast
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# ⚠️ 本脚本住在 `<轮次>/_tools/` ⇒ 比"直接放在轮次目录"的套件**多一层**
#    （第38轮起的老坑：`ROOT` 少写一个 `..` ⇒ `sys.path` 指错 ⇒ ImportError）。
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
MOD = os.path.join(ROOT, 'ralsei_pet', 'modules')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
sys.path.insert(0, MOD)

import scene_render as SR            # noqa: E402
import scene_camera as SC            # noqa: E402
import scene_system as SS            # noqa: E402
import scene_canvas as CV            # noqa: E402

_N = [0]
_FAIL = []


def ok(cond, msg):
    _N[0] += 1
    if cond:
        print('[PASS] %s' % msg)
    else:
        _FAIL.append(msg)
        print('[FAIL] %s' % msg)


def _read(path):
    with open(path, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def _png_size(path):
    """零依赖读 PNG 宽高（IHDR）—— 避免为了量尺寸去起 Qt。"""
    try:
        with open(path, 'rb') as fh:
            head = fh.read(33)
    except OSError:
        return None
    if len(head) < 24 or head[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    return struct.unpack('>II', head[16:24])


def _geo_table():
    with open(os.path.join(SCENES, '_room_geometry.json'), 'r',
              encoding='utf-8') as fh:
        return json.load(fh).get('rooms') or {}


#: 宠物在屏幕上的归一化位置（产品默认在**右下角** ⇒ ≈0.84；与
#: `main._screen_point_to_room_rect` 的 `fx/fy` 同一口径）。
PET_FX = 0.84
PET_FY = 0.84


def _cam_at(room_w, room_h, out_w=640, out_h=480, scale=2.0):
    """把相机摆到"宠物在屏幕上那个位置时所对应的房间坐标"（真机同口径）。"""
    cw, ch = out_w / scale, out_h / scale
    cx, cy = room_w * PET_FX, room_h * PET_FY
    tgt = (cx - cw / 2.0, cy - ch / 2.0, cx + cw / 2.0, cy + ch / 2.0)
    cam = SC.Camera((out_w, out_h), 0, scale)
    cam.follow((0.0, 0.0, float(room_w), float(room_h)), tgt)
    return cam


def _covers(rect, view):
    """`rect` 是否盖满视口 `(vw, vh)`（x<=0, y<=0, x+w>=vw, y+h>=vh）。"""
    if not rect or not view:
        return False
    x, y, w, h = rect
    return x <= 0 and y <= 0 and x + w >= view[0] and y + h >= view[1]


# ===========================================================================
# A 口径在位
# ===========================================================================
def sec_a():
    print('== A 口径在位 ==')
    rsrc = _read(os.path.join(MOD, 'scene_render.py'))
    csrc = _read(os.path.join(MOD, 'scene_canvas.py'))

    # A1 用户原话必须写在代码里（可被复查，不是"我记得用户说过"）
    ok('剩下的用黑色填充' in rsrc and '剩下的用黑色填充' in csrc,
       'A1 用户原话「剩下的用黑色填充」在渲染层与画布层都可查')
    ok(('全屏化' in rsrc) or ('全屏化' in csrc),
       'A2 用户口径「把原作全屏化」在模块里可查')
    ok('等比' in rsrc, 'A3 「等比放大」写在渲染层（禁非等比拉伸同时保留）')
    # A4 ★★ 旧口径必须**在代码层面**消失（不是"注释里别出现" —— 那是本项目
    #    已经栽过四次的**裸子串扫描**误报陷阱：只要我在注释里引用旧写法做对比，
    #    子串判据就会红。所以这里判的是**旧口径的代码签名**是否还在。
    #    ★ 用 `ast.unparse`：注释被丢弃 ⇒ 只看真代码。
    _code = ast.unparse(ast.parse(rsrc))
    ok('float(bg_w), float(bg_h)' not in _code,
       'A4a 旧口径的代码签名 (0,0,float(bg_w),float(bg_h)) 已消失（AST，剥注释）')
    oktree = ast.parse(rsrc)
    _fit_calls = []
    for _fn in ast.walk(oktree):
        if isinstance(_fn, ast.FunctionDef) and _fn.name == 'plan_frame':
            for _n2 in ast.walk(_fn):
                if isinstance(_n2, ast.Call) and isinstance(_n2.func, ast.Name) \
                        and _n2.func.id == 'fit_bg_world':
                    _fit_calls.append(_n2.lineno)
    ok(bool(_fit_calls),
       'A4b plan_frame **真的调用** fit_bg_world（不是只写了函数没人用）行=%s'
       % _fit_calls)
    # A4c 画布侧的文档必须与新规矩同源（AST 取 `_paint_bg` 的 docstring）
    _doc_c = ''
    for _fn in ast.walk(ast.parse(csrc)):
        if isinstance(_fn, ast.FunctionDef) and _fn.name == '_paint_bg':
            _doc_c = ast.get_docstring(_fn) or ''
    ok('fit_bg_world' in _doc_c,
       'A4c `_paint_bg` docstring 指向唯一定义处 fit_bg_world（文档与新规矩同步）')

    # A5 零依赖纪律（初始化环）：scene_render 顶层 import ⊆ logging
    tree = ast.parse(rsrc)
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or '')
    bad = [n for n in names if n and not n.startswith('logging')]
    ok(bad == [], 'A5 scene_render 只依赖标准库 logging（实际 %s）' % bad)


# ===========================================================================
# B fit_bg_world 纯函数
# ===========================================================================
def sec_b():
    print('== B fit_bg_world 纯函数 ==')
    F = SR.fit_bg_world

    # B1 恒等：素材 == 房间
    ok(F(320, 240, (0.0, 0.0, 320.0, 240.0)) == (0.0, 0.0, 320.0, 240.0),
       'B1 素材==房间 → 原样（k=1）')
    # B2 真实量级：kris_s_room（房间 320x240 / 素材 640x480 = 屏幕分辨率截图）
    ok(F(640, 480, (0.0, 0.0, 320.0, 240.0)) == (0.0, 0.0, 320.0, 240.0),
       'B2 素材是房间的 2 倍（屏幕分辨率）→ 缩到房间尺寸，恰好铺满')
    # B3 真实量级：card_castle_1f（房间 1840x1080 / 素材 1280x751）
    f3 = F(1280, 751, (0.0, 0.0, 1840.0, 1080.0))
    ok(f3 is not None and f3[2] >= 1840.0 and f3[3] >= 1080.0,
       'B3 card_castle_1f：两轴都 >= 房间（必然盖满）实际=%s' % (f3,))
    # B4 等比：两轴倍率**完全相同**（禁非等比拉伸）
    if f3:
        kx = f3[2] / 1280.0
        ky = f3[3] / 751.0
        ok(abs(kx - ky) < 1e-9, 'B4 等比：kx=%.6f ky=%.6f 完全一致' % (kx, ky))
    # B5 锚点 = 房间左上（不是居中、不是右下的"猜"）
    f5 = F(100, 100, (7.0, 9.0, 207.0, 209.0))
    ok(f5 is not None and f5[0] == 7.0 and f5[1] == 9.0,
       'B5 锚点 = 房间左上 (l, t) 实际=%s' % (f5,))
    # B6 取 max（cover）而不是 min（contain）—— 这是"绝不留黑边"的定义
    f6 = F(660, 480, (0.0, 0.0, 1000.0, 1000.0))
    ok(f6 is not None and f6[3] >= 1000.0,
       'B6 取 max 倍率（cover）：高度也必须 >= 房间（contain 会留黑边）实际=%s' % (f6,))
    ok(f6 is not None and abs(f6[2] - 660 * (1000.0 / 480.0)) < 1e-6,
       'B6b 宽 = 素材宽 × max(1000/660,1000/480) 实际=%.4f' % (f6[2] if f6 else -1))
    # B7~B11 负控制：非法输入一律 None（**不伪装成合法矩形**）
    ok(F(0, 480, (0.0, 0.0, 100.0, 100.0)) is None, 'B7 素材宽 0 → None')
    ok(F(100, -1, (0.0, 0.0, 100.0, 100.0)) is None, 'B8 素材高负数 → None')
    ok(F(100, 100, None) is None, 'B9 房间 None → None')
    ok(F(100, 100, (0.0, 0.0, 0.0, 100.0)) is None, 'B10 房间零宽 → None')
    ok(F('x', 100, (0.0, 0.0, 100.0, 100.0)) is None, 'B11 非数素材 → None（不抛）')
    # B12 不变量（对任意合法输入都成立）：结果必然盖满房间
    _bad = []
    for bw, bh, rw, rh in ((320, 240, 320, 240), (640, 480, 320, 240),
                           (1280, 751, 1840, 1080), (614, 214, 5400, 1000),
                           (480, 480, 4600, 480), (1, 1, 6400, 480)):
        r = F(bw, bh, (0.0, 0.0, float(rw), float(rh)))
        if r is None or r[2] < rw - 1e-6 or r[3] < rh - 1e-6:
            _bad.append((bw, bh, rw, rh, r))
    ok(_bad == [], 'B12 不变量：6 组真实量级输入**全部**盖满房间（例外=%s）' % _bad)


# ===========================================================================
# C plan_frame：黑底 + 盖满
# ===========================================================================
def sec_c():
    print('== C plan_frame：黑底最前 + bg 盖满 ==')
    geo = _geo_table()

    # C1 本轮真机 bug 的场景：card_castle_1f
    st = SS.SceneState()
    st.chapter_id = 'ch1'
    st.original_room_id = 114
    st.bg = 'bg/ch1_card_castle_card_castle_1f.png'
    st.objects = []
    g = SR.room_geometry(114, 'ch1', geo)
    ok(g is not None and g['w'] == 1840 and g['h'] == 1080,
       'C1a 房间 ch1:114 = 1840x1080 实际=%s' % (g,))
    sz = _png_size(os.path.join(SCENES, st.bg))
    ok(sz == (1280, 751), 'C1b 素材 = 1280x751（比房间小 —— 旧代码在这里整条出界）实际=%s'
       % (sz,))
    cam = _cam_at(g['w'], g['h'])
    plan = SR.plan_frame(st, cam, geo, sprite_size=lambda n: sz)
    kinds = [it['kind'] for it in plan]
    ok(SR.K_ROOM_FILL in kinds, 'C1c 产房间底色 实际=%s' % (kinds,))
    ok(SR.K_BG in kinds,
       'C1d 产 bg 指令（**旧代码这里是 0 条 —— 本轮缺陷的回归锁**）实际=%s' % (kinds,))
    ok(kinds and kinds[0] == SR.K_ROOM_FILL, 'C1e 房间底色是第一条（最底层）')
    bg = [it for it in plan if it['kind'] == SR.K_BG]
    vw, vh = SR.plan_viewport(st, cam, geo)
    ok(bg and _covers(bg[0]['rect'], (vw, vh)),
       'C1f bg 矩形盖满视口 %s 实际=%s' % ((vw, vh), bg[0]['rect'] if bg else None))
    ok(bg and bg[0].get('fit') == 'cover', 'C1g 标记 fit=cover')
    ok(bg and bg[0].get('native') == (1280, 751), 'C1h native 如实记载素材真像素')

    # C2 同场景**把相机推到房间四个角** → 每一处都必须盖满（正/负成对的核心）
    _miss = []
    for tx, ty in ((0, 0), (1840, 0), (0, 1080), (1840, 1080), (920, 540)):
        c = SC.Camera((640, 480), 0, 2.0)
        c.follow((0.0, 0.0, 1840.0, 1080.0),
                 (tx - 8, ty - 16, tx + 8, ty))
        p = SR.plan_frame(st, c, geo, sprite_size=lambda n: sz)
        b = [it for it in p if it['kind'] == SR.K_BG]
        if len(b) != 1 or not _covers(b[0]['rect'], (vw, vh)):
            _miss.append((tx, ty, b[0]['rect'] if b else None))
    ok(_miss == [], 'C2 相机在房间 5 个位置（四角+中心）bg **全部**盖满视口（例外=%s）'
       % _miss)

    # C3 桌面场景（声明式透明）不许产黑底/占位（否则把用户壁纸盖住）
    sc_d = SS.load_scene('desktop', entry=(SS.load_index().get('scenes') or
                                           {}).get('desktop'))
    ok(sc_d is not None and getattr(sc_d, 'bg', None) == SR.TRANSPARENT_BG,
       'C3a desktop 的 bg = %r（声明式透明）' % (getattr(sc_d, 'bg', None),))
    c3 = SC.Camera((640, 480), 0, 2.0)
    c3.follow((0.0, 0.0, 640.0, 480.0), None)
    p3 = SR.plan_frame(sc_d, c3, geo)
    k3 = [it['kind'] for it in p3]
    ok(SR.K_ROOM_FILL not in k3, 'C3b 桌面场景 0 条黑底 实际=%s' % (k3,))
    ok(SR.K_PLACEHOLDER not in k3, 'C3c 桌面场景 0 条占位（不盖壁纸）')
    ok(SR.K_OBJ in k3, 'C3d 桌面场景的门仍在（透明≠整间空）实际=%s' % (k3,))

    # C4 负控制：真·缺素材（bg=None）→ 黑底仍在 + 1 条占位
    st4 = SS.SceneState()
    st4.chapter_id = 'ch1'
    st4.original_room_id = 114
    st4.bg = None
    st4.objects = []
    p4 = SR.plan_frame(st4, cam, geo)
    k4 = [it['kind'] for it in p4]
    ok(k4.count(SR.K_ROOM_FILL) == 1 and k4.count(SR.K_PLACEHOLDER) == 1,
       'C4 缺素材 → 黑底 + 占位 各 1 条 实际=%s' % (k4,))

    # C5 黑底颜色 = 不透明纯黑（用户口径的**逐字**产物，不是"我觉得黑色好看"）
    rf = [it for it in plan if it['kind'] == SR.K_ROOM_FILL]
    ok(rf and rf[0].get('color') == (0, 0, 0, 255),
       'C5 黑底颜色 = (0,0,0,255) 实际=%s' % (rf[0].get('color') if rf else None,))

    # C6 房间未知（几何查不到）也不许崩、且仍出黑底
    st6 = SS.SceneState()
    st6.chapter_id = 'ch1'
    st6.original_room_id = 999999
    st6.bg = 'bg/ch1_card_castle_card_castle_1f.png'
    st6.objects = []
    p6 = SR.plan_frame(st6, cam, geo, sprite_size=lambda n: sz)
    ok(isinstance(p6, list) and len(p6) >= 1 and p6[0]['kind'] == SR.K_ROOM_FILL,
       'C6 房间未知 → 不崩，仍出黑底 + %d 条' % len(p6))


# ===========================================================================
# D 画布消费
# ===========================================================================
def sec_d():
    print('== D 画布消费 ==')

    class _P(object):
        def __init__(self):
            self.calls = []
            self.fills = []

        def fillRect(self, r, br=None):
            self.calls.append('fill')
            self.fills.append((r.x(), r.y(), r.width(), r.height(), br))

        def drawPixmap(self, *a):
            self.calls.append('pix')

        def drawRect(self, r):
            self.calls.append('rect')

        def drawLine(self, *a):
            self.calls.append('line')

        def setPen(self, p):
            pass

        def setOpacity(self, o):
            pass

    class _A(object):
        def get(self, n):
            return None

        def sprite_size(self, n):
            return None

    p = _P()
    n = CV.paint_on(p, [{'kind': CV.K_ROOM_FILL, 'rect': (-100, -100, 2000, 2000),
                         'color': (0, 0, 0, 255)}], _A())
    ok(n == 1, 'D1a room_fill 被画出（返回 1）实际=%d' % n)
    ok(p.fills and p.fills[0][:4] == (-100, -100, 2000, 2000),
       'D1b 用**指令给的**矩形 实际=%s' % (p.fills[:1],))
    col = p.fills[0][4].color().getRgb() if p.fills and p.fills[0][4] else None
    ok(col == (0, 0, 0, 255), 'D1c 颜色取指令 color 实际=%s' % (col,))
    # 负控制 1：没带 color → 兜底仍是不透明黑
    p = _P()
    CV.paint_on(p, [{'kind': CV.K_ROOM_FILL, 'rect': (0, 0, 4, 4)}], _A())
    col = p.fills[0][4].color().getRgb() if p.fills and p.fills[0][4] else None
    ok(col == (0, 0, 0, 255), 'D2 无 color → 兜底不透明黑 实际=%s' % (col,))
    # 负控制 2：空 rect → 不落笔
    p = _P()
    n = CV.paint_on(p, [{'kind': CV.K_ROOM_FILL, 'rect': None}], _A())
    ok(n == 0 and p.fills == [], 'D3 空 rect → 不落笔（实际 %d）' % n)
    # 顺序：黑底先于 bg
    p = _P()
    CV.paint_on(p, [{'kind': CV.K_ROOM_FILL, 'rect': (0, 0, 10, 10),
                     'color': (0, 0, 0, 255)},
                    {'kind': CV.K_BG, 'name': 'x', 'rect': (0, 0, 10, 10)}], _A())
    ok(p.calls and p.calls[0] == 'fill', 'D4 黑底先于 bg 落笔 实际序=%s' % (p.calls,))
    # 常量两模块对齐（改一边忘另一边 → 立刻报红）
    ok(CV.K_ROOM_FILL == SR.K_ROOM_FILL, 'D5a K_ROOM_FILL 两模块一致（%s）'
       % CV.K_ROOM_FILL)
    ok(hasattr(CV, 'K_ROOM_FILL') and hasattr(SR, 'K_ROOM_FILL'),
       'D5b 两模块都定义了 K_ROOM_FILL')
    ok(getattr(CV, 'ROOM_FILL_COLOR', None) is not None,
       'D5c 画布层有兜底颜色常量 ROOM_FILL_COLOR')


# ===========================================================================
# E ★ 全量普查不变量（235 个真背景场景逐个跑 —— 机器统计，不看单例）
# ===========================================================================
def sec_e():
    print('== E 全量普查不变量（真背景场景逐个跑）==')
    idx = SS.load_index()
    geo = _geo_table()
    scenes = idx.get('scenes') or {}
    stat = {'n': 0, 'no_bg_item': 0, 'bg_not_cover': 0, 'no_fill': 0,
            'fill_not_cover': 0, 'no_room': 0, 'fit_not_cover': 0}
    worst = []
    for sid, ent in scenes.items():
        sc = SS.load_scene(sid, entry=ent)
        if sc is None:
            continue
        bg = getattr(sc, 'bg', None)
        if not isinstance(bg, str) or not bg or bg == SR.TRANSPARENT_BG:
            continue
        rid = getattr(sc, 'original_room_id', None)
        ch = getattr(sc, 'chapter_id', None)
        if not isinstance(rid, int) or not ch:
            stat['no_room'] += 1
            continue
        rec = geo.get('%s:%d' % (ch, rid))
        if not isinstance(rec, dict):
            stat['no_room'] += 1
            continue
        rw, rh = rec.get('w'), rec.get('h')
        sz = _png_size(os.path.join(SCENES, bg.replace('/', os.sep)))
        if not sz or not (isinstance(rw, int) and isinstance(rh, int)
                          and rw > 0 and rh > 0):
            stat['no_room'] += 1
            continue
        cam = _cam_at(rw, rh)
        plan = SR.plan_frame(sc, cam, geo, sprite_size=lambda n, _s=sz: _s)
        view = SR.plan_viewport(sc, cam, geo)
        stat['n'] += 1
        bgs = [it for it in plan if it['kind'] == SR.K_BG]
        fills = [it for it in plan if it['kind'] == SR.K_ROOM_FILL]
        if len(bgs) != 1:
            stat['no_bg_item'] += 1
            worst.append((sid, 'no_bg', len(bgs)))
        elif not _covers(bgs[0]['rect'], view):
            stat['bg_not_cover'] += 1
            worst.append((sid, 'bg_not_cover', bgs[0]['rect'], view))
        elif bgs[0].get('fit') != 'cover':
            stat['fit_not_cover'] += 1
        if len(fills) != 1:
            stat['no_fill'] += 1
        elif not _covers(fills[0]['rect'], view):
            stat['fill_not_cover'] += 1
            worst.append((sid, 'fill_not_cover', fills[0]['rect'], view))
    print('  普查：样本 %d ｜ 无 bg 指令 %d ｜ bg 未盖满 %d ｜ 无黑底 %d ｜ '
          '黑底未盖满 %d ｜ 跳过(无房间/无素材) %d'
          % (stat['n'], stat['no_bg_item'], stat['bg_not_cover'],
             stat['no_fill'], stat['fill_not_cover'], stat['no_room']))
    ok(stat['n'] >= 200,
       'E1 普查样本 >= 200（真实规模；实际 %d —— 若骤降说明素材/几何被删）' % stat['n'])
    ok(stat['no_bg_item'] == 0,
       'E2 **零**场景在"宠物默认位置"下缺 bg 指令（旧代码在此大量出界）实际=%d' % stat['no_bg_item'])
    ok(stat['bg_not_cover'] == 0,
       'E3 **零**场景的 bg 未盖满视口（例外=%s）' % (worst[:3],))
    ok(stat['no_fill'] == 0, 'E4 **零**场景缺房间底色 实际=%d' % stat['no_fill'])
    ok(stat['fill_not_cover'] == 0,
       'E5 **零**场景的房间底色未盖满视口 实际=%d' % stat['fill_not_cover'])
    ok(stat['fit_not_cover'] == 0,
       'E6 **零**场景走了非 cover 分支却仍有 bg（标记须如实）实际=%d'
       % stat['fit_not_cover'])


# ===========================================================================
# G ★ 原作 `visible=False` 的**不可见触发器**不许画（第99轮真机第二缺陷）
# ===========================================================================
#: 本轮的"过滤面"golden —— 场景数据里**全部会被过滤掉的原作对象名**（46 个）。
#: ★ 为什么把这份名单**蒸馏进仓库**而不是现场读第43轮的转储：
#:   `run_all.py` 的 G2 套件**不许依赖临时区/外部盘**（E 盘掉线就暴露过一次）。
#:   这 46 个名字逐个都在 `objmap43.txt` 里核过 `vis=False`（见第99轮报告），
#:   名单本身就是那份证据的**可复现蒸馏**：过滤面变大/变小 ⇒ 立刻报红。
_HIDDEN_SRC_SEEN = (
    'obj_ch2_room_city_savepoint', 'obj_ch2_room_cyber_shop',
    'obj_ch2_room_mansion_entrance', 'obj_ch2_room_spamton_shop_exterior',
    'obj_ch2_scene21_puzzle_entrance', 'obj_church_entrance',
    'obj_darkwakeevent', 'obj_doorA', 'obj_doorA_musfade', 'obj_doorB',
    'obj_doorB_musfade', 'obj_doorC', 'obj_doorC_musfade', 'obj_doorD',
    'obj_doorD_musfade', 'obj_doorE', 'obj_doorF', 'obj_doorW', 'obj_doorX',
    'obj_doorX_musfade', 'obj_doorw_musfade', 'obj_dw_church_staircase',
    'obj_dw_cliff_shop', 'obj_dw_fcastle_entrance',
    'obj_dw_fcastle_top_staircase_1', 'obj_dw_fcastle_top_staircase_2',
    'obj_dw_garden_riverchest', 'obj_dw_post_fountain_close',
    'obj_elevator_warp',
    'obj_lockedDoor_mansion_east_2f_transformed_new', 'obj_markerA',
    'obj_markerB', 'obj_markerC', 'obj_markerD', 'obj_markerE', 'obj_markerF',
    'obj_markerX', 'obj_markerw', 'obj_readable_room1',
    'obj_room_backstage_shop', 'obj_room_flowershop_1f',
    'obj_room_flowershop_2f', 'obj_room_puzzle_closet_1a',
    'obj_room_schooldoor', 'obj_room_snow_zone_east_door',
    'obj_schoollobbycutscene',
)

#: 反向正控制：**必须是画得出来**的原作对象（存盘点 / 存档点）。
#: 它们也在场景数据里带 `src`，如果过滤面失控，第一个被误杀的就是它们。
_MUST_STILL_DRAW = ('obj_savepoint',)


def _scan_src_hidden(scenes):
    """遍历全部场景，返回 `(带 src 实例总数, 被过滤数, 被过滤的 distinct src,
    loaded, 按命名空间拆分的 {(前缀): [总数, 被过滤数]})`。

    ⚠️ **一次加载、多次复用**：`load_scene(entry=)` 每次都重读区域分片
       （分片可达数百 KB），2166 个场景若反复加载会把套件的墙钟拖到分钟级
       —— G2 里每个套件都这么慢是不可接受的。所以这里自己缓存一次。

    ★★★ 第103轮：**按 `sprite` 前缀拆两本账**（这是本函数返回第 5 项的动机）。
      第103轮把 OneShot 的 7,804 个物件接进场景（`sprite` = `oneshot_cells/...`），
      带 `src` 的实例从 **3,206 → 11,010**。G24 的"被过滤比例"分母一变大，
      比例就从 **85.5% 掉到 24.9%** —— 看起来像"过滤失效"，实际是**分母换了物种**：
      `_obj_visible.json` 的 901 个隐形名单全是**原作 Deltarune 触发器名**，
      OneShot 的事件名（`EV005` / `remote` …）一个都不在里面，所以那 7,804 条
      **本来就该全部照画**。混在一个分母里，这条判据既量不准 Deltarune 的过滤率，
      也看不出 OneShot 有没有被误杀。
      ⇒ 拆成 `objs/`（Deltarune，46 个触发器名所在的种群）与
        `oneshot_cells/`（OneShot，应当 **0 被过滤**），各守各的真值。
    """
    tot = 0
    hid = 0
    seen = set()
    loaded = {}
    ns = {}
    for sid, ent in scenes.items():
        sc = SS.load_scene(sid, entry=ent)
        if sc is None:
            continue
        loaded[sid] = sc
        hidden = getattr(sc, 'hidden_objects', None)
        for o in getattr(sc, 'objects', None) or []:
            if not isinstance(o, dict):
                continue
            src = o.get('src')
            if not isinstance(src, str) or not src:
                continue
            tot += 1
            spr = o.get('sprite')
            key = (spr.split('/', 1)[0] + '/') if isinstance(spr, str) and '/' in spr \
                else '(无前缀)'
            slot = ns.setdefault(key, [0, 0])
            slot[0] += 1
            if not SS.is_drawable_object(o, hidden):
                hid += 1
                slot[1] += 1
                seen.add(src)
    return tot, hid, seen, loaded, ns


def sec_g():
    print('== G 原作 visible=False 的不可见触发器不许画 ==')
    jpath = os.path.join(SCENES, '_obj_visible.json')
    raw = None
    if os.path.isfile(jpath):
        with open(jpath, 'r', encoding='utf-8') as fh:
            raw = json.load(fh)

    # ---- G 数据面 ----
    ok(isinstance(raw, dict) and raw.get('schema_version') == 1,
       'G1 `_obj_visible.json` 在位且 schema_version==1')
    counts = (raw or {}).get('counts') or {}
    ok(counts.get('visible_count', -1) + counts.get('hidden_count', -1)
       == counts.get('objects_seen', -2),
       'G2 counts 自洽 visible+hidden==seen（%s+%s vs %s）'
       % (counts.get('visible_count'), counts.get('hidden_count'),
          counts.get('objects_seen')))
    ok(counts.get('objects_seen') == 4891,
       'G3 原作对象表收录 4891 个（第43轮转储的真实规模）实际=%s'
       % counts.get('objects_seen'))
    ok(counts.get('hidden_count') == 901,
       'G4 隐形 901 个（899 原始 + 2 个多章冲突取保守侧）实际=%s'
       % counts.get('hidden_count'))
    ok(counts.get('files') == 5,
       'G5 覆盖五章转储 ch1~ch5 实际=%s' % counts.get('files'))

    hidden = SS.load_obj_visible()
    ok(isinstance(hidden, frozenset) and len(hidden) == 901,
       'G6 load_obj_visible 返回 frozenset(901)（实际 %s/%d）'
       % (type(hidden).__name__, len(hidden)))
    ok(SS.load_obj_visible() is hidden,
       'G7 load_obj_visible 命中进程内缓存（幂等，箭头同一对象）—— 每帧调用不重读盘')
    for nm in ('obj_doorA', 'obj_markerB', 'obj_readable_room1'):
        ok(nm in hidden, 'G8 真机那三个框的对象 %s 在隐形名单里' % nm)
    for nm in _MUST_STILL_DRAW:
        ok(nm not in hidden,
           'G8b 正控制：可见对象 %s **不在**隐形名单里' % nm)
    ok(SS.load_obj_visible(os.path.join(SCENES, '__nope__')) == frozenset(),
       'G9 负控制：目录里没有名单文件 → 空集合（= 回落旧行为，不是"全藏"）')

    # ---- G 纯函数正负成对 ----
    ok(SS.is_drawable_object({'src': 'obj_doorA'}, hidden) is False,
       'G10 vis=False 的对象 → 不画')
    ok(SS.is_drawable_object({'src': 'obj_savepoint'}, hidden) is True,
       'G11 vis=True 的对象 → 照画（正控制）')
    ok(SS.is_drawable_object({'pos': [1, 2]}, hidden) is True,
       'G12 没有 src 的自造物件 → 照画（它们没有 visible 这回事）')
    ok(SS.is_drawable_object({'src': 'obj_doorA'}, None) is True
       and SS.is_drawable_object({'src': 'obj_doorA'}, frozenset()) is True,
       'G13 名单缺失/为空 → 逐字回到旧行为（不静默"全藏"）')
    # ★ 字符串的 `in` 是**子串匹配** ⇒ 必须先拒掉：否则 `'obj_doorA' in 'xx'`
    #   会变成"名字像就藏"，比不判更糟。
    ok(SS.is_drawable_object({'src': 'obj_doorA'}, 'zzobj_doorAzz') is True,
       'G14 负控制：hidden 传字符串 → 拒子串匹配，照画')
    ok(SS.is_drawable_object(None, hidden) is True
       and SS.is_drawable_object('x', hidden) is True,
       'G15 非 dict 入参 → 照画（不抛）')
    # ★ 判的是 **src（对象级）** 而不是 sprite（素材级）—— 同 sprite 三条并排。
    _same_spr = 'objs/spr_interactable_0.png'
    ok(SS.is_drawable_object({'sprite': _same_spr, 'src': 'obj_doorA'},
                             hidden) is False
       and SS.is_drawable_object({'sprite': _same_spr,
                                  'src': 'obj_never_seen_xyz'}, hidden) is True
       and SS.is_drawable_object({'sprite': _same_spr}, hidden) is True,
       'G16 同一 sprite 三种 src ⇒ 只有命中隐形名单的那个不画（对象级，不是素材级）')

    # ---- G ★★★ 自造物件逃生门（第99轮 G2 实测逼出来的，别删）----
    #   桌面上那 9 扇门是我们自己摆的、却借用了原作的 `src`（obj_doorA/B/...）
    #   来复用贴图与路由 ⇒ 不豁免就整批被藏（实测 desktop 的 plan 9 → 1，
    #   `scene_p0` H11 / `check89` E 段 / `render_round44` D3c 三处报红）。
    ok(SS.is_drawable_object({'src': 'obj_doorA', 'authored': True},
                             hidden) is True,
       'G16b `authored=True` ⇒ 照画（显式逃生门）')
    ok(SS.is_drawable_object({'src': 'obj_doorA', 'kind': 'prop'},
                             hidden) is True,
       'G16c `kind="prop"` ⇒ 照画（兜底逃生门：转储物件从不写 kind）')
    ok(SS.is_drawable_object({'src': 'obj_doorA', 'authored': False},
                             hidden) is False,
       'G16d 负控制：`authored=False` **不**豁免（只认 `is True`）')
    ok(SS.is_drawable_object({'src': 'obj_doorA', 'kind': 'obj'},
                             hidden) is False,
       'G16e 负控制：`kind="obj"` **不**豁免（只认白名单里的 kind）')
    ok(SS.is_drawable_object({'src': 'obj_doorA'}, hidden) is False,
       'G16f 鉴别力：**没有任何自造标记**的 obj_doorA 必须仍被过滤'
       '（证明逃生门是必要的，不是摆设）')
    ok(tuple(getattr(SS, '_AUTHORED_KINDS', ())) == ('prop',),
       'G16g 自造 kind 白名单 = (prop,)，且是**收紧**的（实际 %r）'
       % (getattr(SS, '_AUTHORED_KINDS', None),))
    ok(getattr(SR, '_AUTHORED_KINDS', None) == getattr(SS, '_AUTHORED_KINDS', None),
       'G16h 两份刻意重复的白名单**逐值一致**（scene_render vs scene_system）')

    # ---- G 真链路：载入 → 注入 → 计划 ----
    idx = SS.load_index()
    scenes = idx.get('scenes') or {}
    ch1 = SS.load_scene('ch1.kris_room.kris_s_room',
                        entry=scenes.get('ch1.kris_room.kris_s_room'))
    ok(ch1 is not None and len(ch1.hidden_objects) == 901,
       'G17 载入的场景**带着**隐形名单（load_scene 注入生效）')
    geo = _geo_table()
    plan = SR.plan_frame(ch1, _cam_at(320, 240), geo,
                         sprite_size=lambda n: (20, 20))
    objs = [it for it in plan if it['kind'] == SR.K_OBJ]
    ok(len(ch1.objects) == 9 and objs == [],
       'G18 真机那间房：9 个物件全是触发器 ⇒ **零 obj 指令**（实际 %d 条）'
       % len(objs))
    ch4 = SS.load_scene('ch4.kris_room.kris_s_room',
                        entry=scenes.get('ch4.kris_room.kris_s_room'))
    plan4 = SR.plan_frame(ch4, _cam_at(320, 240), geo,
                          sprite_size=lambda n: (20, 20))
    objs4 = [it for it in plan4 if it['kind'] == SR.K_OBJ]
    ok(ch4 is not None and len(ch4.objects) == 10 and len(objs4) == 1
       and objs4[0]['name'] == 'objs/spr_savepoint_0.png',
       'G18b 正控制：ch4 同房间 10 个物件里**存盘点照画**（恰 1 条 obj）'
       '实际=%s' % [it['name'] for it in objs4])
    # ★ 手搓 SceneState（`from_dict`，不走 load_scene）⇒ 与第99轮之前逐字一致。
    bare = SS.SceneState.from_dict({
        'scene_id': 'bare', 'bg': None,
        'objects': [{'pos': [10, 10], 'sprite': 'objs/spr_doorA_0.png',
                     'src': 'obj_doorA'}]})
    ok(bare.hidden_objects == frozenset(),
       'G19 手搓 SceneState 的隐形名单为空（`from_dict` 不给默认值以外的行为）')
    bare_objs = [it for it in SR.plan_frame(bare, _cam_at(320, 240), geo,
                                           sprite_size=lambda n: (20, 20))
                 if it['kind'] == SR.K_OBJ]
    ok(len(bare_objs) == 1,
       'G20 零行为变化：手搓场景里同一个 obj_doorA **仍然被画**（实际 %d）'
       % len(bare_objs))
    ok('hidden_objects' in SS.SceneState.__slots__,
       'G21 `hidden_objects` 在 SceneState 的 __slots__ 里（不是动态属性）')
    # ★★ 产品级正控制：桌面 9 扇门**一扇都不许少**（自造物件逃生门的端到端证据）
    desk = SS.load_scene('desktop', entry=scenes.get('desktop'))
    dplan = SR.plan_frame(desk, _cam_at(320, 240), geo,
                          sprite_size=lambda n: (20, 20))
    dobjs = [it for it in dplan if it['kind'] == SR.K_OBJ]
    ok(desk is not None and len(dobjs) == 9,
       'G21b **桌面 9 扇门全部照画**（自造物件逃生门的端到端正控制）实际=%d' % len(dobjs))
    ok(desk is not None
       and all(o.get('authored') is True for o in desk.objects),
       'G21c `desktop.json` 的 9 扇门在**数据里**显式标了 `authored: true`'
       '（自解释，不靠"kind 恰好是 prop"）')
    ok(desk is not None and all(SS.is_drawable_object(o, desk.hidden_objects)
                                for o in desk.objects),
       'G21d 桌面的门逐条过 `is_drawable_object` 都为真')

    # ---- G 全量过滤面普查（机器统计，不看单例）----
    tot, hid, seen, loaded, ns = _scan_src_hidden(scenes)
    d_tot, d_hid = ns.get('objs/', [0, 0])            # Deltarune（46 个触发器名的种群）
    o_tot, o_hid = ns.get('oneshot_cells/', [0, 0])   # OneShot（第103轮接线，全可见）
    oth = sorted((k, v) for k, v in ns.items()
                 if k not in ('objs/', 'oneshot_cells/') and v[0])
    print('  过滤面：带 src 实例 %d（objs/ %d ｜ oneshot_cells/ %d ｜ 其他 %d）'
          ' ｜ 被过滤 %d (%.1f%%) ｜ distinct src %d'
          % (tot, d_tot, o_tot, sum(v[0] for _k, v in oth),
             hid, 100.0 * hid / max(1, tot), len(seen)))
    ok(d_tot >= 3000 and o_tot >= 7800,
       'G23 带 src 的实例规模：`objs/`(Deltarune) %d >= 3000、'
       '`oneshot_cells/`(OneShot) %d >= 7800（骤降说明场景数据被删）'
       % (d_tot, o_tot))
    ok(0.6 <= d_hid / max(1, d_tot) <= 0.95,
       'G24 被过滤比例在 60%%~95%%（金标 85.5%%；过低=漏过滤，过高=误杀）实际=%.1f%%'
       ' —— ★★ 分母**只数 `objs/` 命名空间**：那 46 个隐形触发器名全属 Deltarune，'
       '把 OneShot 的 7,804 条并进来会让比例变成 %.1f%% 的**假异常**'
       % (100.0 * d_hid / max(1, d_tot), 100.0 * hid / max(1, tot)))
    ok(o_hid == 0,
       'G24b ★★ OneShot 命名空间被过滤 **0** 条（`oneshot_cells/` 的 %d 条全是'
       '真道具/NPC，一个都不该落进 901 个原作触发器名单；误杀 %d）' % (o_tot, o_hid))
    ok(not oth,
       'G24c `sprite` 前缀**只有** `objs/` 与 `oneshot_cells/` 两种'
       '（出现第三种 ⇒ 有素材被放到没人守的命名空间里：%s）' % (oth[:3],))
    _diff = sorted(seen ^ set(_HIDDEN_SRC_SEEN))
    ok(_diff == [],
       'G25 过滤面 **恰好**是那 46 个触发器名（多/少都报红；差异=%s）'
       % _diff[:8])

    # ---- G 两份实现的对账闸（刻意重复 ⇒ 靠这里抓不一致）----
    mism = 0
    for sid, sc in loaded.items():
        hd = getattr(sc, 'hidden_objects', None)
        for o in getattr(sc, 'objects', None) or []:
            if SS.is_drawable_object(o, hd) != (not SR.obj_is_hidden(o, hd)):
                mism += 1
    ok(mism == 0,
       'G26 scene_system 与 scene_render 两份实现**逐条一致**（%d 场景全量，'
       '实际不一致 %d）' % (len(loaded), mism))

    cnt = {}
    for sc in loaded.values():
        hd = getattr(sc, 'hidden_objects', None)
        for o in getattr(sc, 'objects', None) or []:
            if not isinstance(o, dict) or SS.is_drawable_object(o, hd):
                continue
            cnt[o.get('src')] = cnt.get(o.get('src'), 0) + 1
    for nm, want in (('obj_readable_room1', 921), ('obj_markerA', 227),
                     ('obj_markerB', 223), ('obj_doorW', 212)):
        ok(cnt.get(nm) == want,
           'G27 逐类计数 %s = %d（实际 %s）' % (nm, want, cnt.get(nm)))
    ok(not (set(_MUST_STILL_DRAW) & seen),
       'G28 正控制：可见对象从未出现在过滤面里（%s）' % (_MUST_STILL_DRAW,))

    # ---- G 语义边界（只影响绘制，不越界到交互/道具）----
    _sem = (raw or {}).get('semantics', '')
    ok('只影响' in _sem and '绘制' in _sem,
       'G29 数据文件写清语义边界（只影响绘制）')
    _doc = ''
    for _fn in ast.walk(ast.parse(_read(os.path.join(MOD, 'scene_system.py')))):
        if isinstance(_fn, ast.FunctionDef) and _fn.name == 'is_drawable_object':
            _doc = ast.get_docstring(_fn) or ''
    ok('只影响' in _doc and '绘制' in _doc,
       'G30 `is_drawable_object` docstring 写明"只影响绘制"（边界可复查）')
    _docr = ''
    for _fn in ast.walk(ast.parse(_read(os.path.join(MOD, 'scene_render.py')))):
        if isinstance(_fn, ast.FunctionDef) and _fn.name == 'obj_is_hidden':
            _docr = ast.get_docstring(_fn) or ''
    ok('scene_system.is_drawable_object' in _docr,
       'G31 镜像实现 `obj_is_hidden` 的 docstring 指向唯一真源')
    # ★ 只影响绘制：过滤是"计划层"的事，`scene.objects` 本身一个都没少。
    ok(len(ch1.objects) == 9,
       'G32 过滤不动 `scene.objects` 本身（仍是 9 个 —— 触发器照旧可交互）'
       '实际 %d' % len(ch1.objects))
    ok('obj_is_hidden' in ast.unparse(ast.parse(
        _read(os.path.join(MOD, 'scene_render.py')))),
       'G33 过滤真的接在渲染层（AST：`obj_is_hidden` 在代码里被调用）')
    _cfg = ast.unparse(ast.parse(_read(os.path.join(MOD, 'scene_system.py'))))
    ok('is_drawable_object(obj, hidden)' in _cfg,
       'G34 过滤接在 `visible_objects` 的绘制筛选里（AST 代码签名）')


# ===========================================================================
# F 接线与纪律
# ===========================================================================
def sec_f():
    print('== F 接线与纪律 ==')
    main = _read(os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py'))
    # F1 黑底不会被"只有黑底、没别的"的场景误触发上屏（1931 个无背景场景）
    ok("it.get('kind') in ('bg', 'obj')" in main,
       "F1 main 仍按 bg/obj 判是否显示画布（黑底**不**单独触发显示）")
    ok('_hide_scene_layer' in main and '_show_scene_layer' in main,
       'F2 显示/隐藏两个入口都在')
    # F3 scene_scale 口径未动（用户"放大比例不用我说"= 已裁定的 2.0）
    ok('self.scene_scale = 2.0' in main, 'F3 scene_scale 仍为 2.0（本轮不动放大比例）')
    # F4 画布仍是独立顶层窗口（第89/93轮血泪，本轮不许回退）
    ok('as_window=True' in main.replace(' ', ''), 'F4 画布仍是独立顶层窗口')
    # F5 断言条数自查（防"套件只剩几条判据"）
    ok(_N[0] > 50, 'F5 断言条数 > 50（实际 %d）' % _N[0])


def main():
    print('第99轮 场景系统「把原作全屏化」回归锁（%s）'
          % os.path.basename(__file__))
    sec_a()
    sec_b()
    sec_c()
    sec_d()
    sec_e()
    sec_g()
    sec_f()
    print()
    if _FAIL:
        print('[FAIL] 共 %d 条失败（断言 %d）' % (len(_FAIL), _N[0]))
        for f in _FAIL:
            print('   - ' + f)
        return 1
    print('场景系统全屏化回归锁：%d/%d 全绿' % (_N[0], _N[0]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
