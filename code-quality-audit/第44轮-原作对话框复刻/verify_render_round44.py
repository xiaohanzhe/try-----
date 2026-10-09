# -*- coding: utf-8 -*-
"""第44轮 · 房间渲染层回归锁（`scene_render` + 接线）。

判据分五段：
  A 原作依据在位（"背景移动=相机平移、零视差"的出处可查）
  B 纯函数正负成对（room_geometry / room_world_rect / viewport_size / to_output）
  C 视口剔除 visible_in_view（含非恒真正负控制）
  D 绘制计划 plan_frame（真实数据 + 假数据双路）
  E 产品接线（控制器定义 + main.py 真调用 + 预声明 + scene_scale 口径）

★ 铁律：
  · 行为判据**必须用真实量级输入**（房间 320×240 / 6,220×1,920 都是真实值）。
  · 正/负控制成对 —— 只测"能过"不算测过，必须能"报红"。
  · 成功标记必须 `[PASS]` 字面量（`run_all.py` 按它计数）。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
MOD = os.path.join(ROOT, 'ralsei_pet', 'modules')
sys.path.insert(0, MOD)

import scene_render as SR            # noqa: E402
import scene_camera as SC            # noqa: E402
import scene_system as SS            # noqa: E402

SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
GEO_PATH = os.path.join(SCENES, '_room_geometry.json')

_N = [0]
_FAIL = []


def ok(cond, msg):
    """★ 每条断言必须打 `[PASS]` 字面量 —— `run_all.py:425` 按它计数。

    （本项目踩过：套件里只写 `"  PASS  msg"` 或只在末尾打一次，
      G2 会显示 PASS=1，看着"绿了"其实 85 条断言只有 1 条被计数。）
    """
    _N[0] += 1
    if cond:
        print('[PASS] %s' % msg)
    else:
        _FAIL.append(msg)
        print('[FAIL] %s' % msg)


def _read(path):
    with open(path, 'r', encoding='utf-8') as fh:
        return fh.read()


def _geo_table():
    with open(GEO_PATH, 'r', encoding='utf-8') as fh:
        return json.load(fh).get('rooms') or {}


# ===========================================================================
# A 原作依据在位
# ===========================================================================
def sec_a():
    print('== A 原作依据在位 ==')
    cam_src = _read(os.path.join(MOD, 'scene_camera.py'))
    ok('camera_set_view_target' in cam_src, 'A1 相机模块写明原生相机族调用')
    ok('不是视差' in cam_src or '视差' in cam_src, 'A2 相机模块写明"不是视差"')
    ok('640' in cam_src and '480' in cam_src, 'A3 暗世界相机 640x480 在位')

    # A4 几何资产带来源与权威说明
    with open(GEO_PATH, 'r', encoding='utf-8') as fh:
        payload = json.load(fh)
    ok(isinstance(payload.get('source'), str) and payload['source'],
       'A4a 几何表带 source')
    ok(isinstance(payload.get('authority'), str) and payload['authority'],
       'A4b 几何表带 authority')
    ok(payload.get('schema_version') == 1, 'A4c 几何表 schema_version = 1')

    # A5 渲染模块零 Qt / 零项目内模块依赖（初始化环纪律）
    rsrc = _read(os.path.join(MOD, 'scene_render.py'))
    ok('PyQt5' not in rsrc and 'QtCore' not in rsrc,
       'A5a scene_render 不 import Qt')
    # AST 级检查 import 名
    import ast
    tree = ast.parse(rsrc)
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or '')
    bad = [n for n in names if n and not n.startswith('logging')]
    ok(bad == [], 'A5b scene_render 只依赖标准库 logging（实际 %s）' % bad)


# ===========================================================================
# B 纯函数正负成对
# ===========================================================================
def sec_b():
    print('== B 纯函数 ==')
    geo = _geo_table()

    # --- room_geometry ---
    r = SR.room_geometry(2, 'ch1', geo)
    ok(r == {'w': 320, 'h': 240, 'name': 'room_krisroom'},
       'B1 ch1:2 = 320x240 room_krisroom 实际=%s' % (r,))
    ok(SR.room_geometry(99999, 'ch1', geo) is None, 'B2 越界 id → None')
    ok(SR.room_geometry(2, 'ch9', geo) is None, 'B3 不存在章 → None')
    ok(SR.room_geometry(None, 'ch1', geo) is None, 'B4 room_id 非 int → None')
    ok(SR.room_geometry(2, 'ch1', None) is None, 'B5 geo_table 空 → None')
    ok(SR.room_geometry(2, 'ch1', {}) is None, 'B6 geo_table {} → None')

    # --- room_world_rect ---
    ok(SR.room_world_rect({'w': 320, 'h': 240}) == (0.0, 0.0, 320.0, 240.0),
       'B7 world_rect 正常')
    cam = SC.Camera((640, 480), 0, 1.0)
    ok(SR.room_world_rect(None, cam) == (0.0, 0.0, 640.0, 480.0),
       'B8 world_rect 退化 = 相机尺寸（非零！）')
    z = SR.room_world_rect(None, cam)
    ok(z[2] > 0 and z[3] > 0, 'B9 退化矩形面积 > 0（防除零/防全裁）')

    # --- viewport_size ---
    #   scale=1.0：相机逻辑窗口 = 640x480；房间 320x240 → 房间像素 320x240
    ok(SR.viewport_size(cam, {'w': 320, 'h': 240}) == (320, 240),
       'B10 小房间（320x240,scale=1）→ 视口收缩到房间 实际=%s'
       % (SR.viewport_size(cam, {'w': 320, 'h': 240}),))
    ok(SR.viewport_size(cam, {'w': 6220, 'h': 1920}) == (640, 480),
       'B11 超大房间 → 视口 = 相机')
    cam2 = SC.Camera((640, 480), 0, 2.0)
    ok(SR.viewport_size(cam2, {'w': 320, 'h': 240}) == (640, 480),
       'B12 320x240 @scale2 → 视口 640x480（= 原作现实世界输出尺寸）实际=%s'
       % (SR.viewport_size(cam2, {'w': 320, 'h': 240}),))
    # 两轴独立：宽 320x2=640（=相机，不收缩）；高 1160x2=2320 → 钳到 480
    ok(SR.viewport_size(cam2, {'w': 320, 'h': 1160}) == (640, 480),
       'B13 两轴独立（宽 640 与相机同、高钳到 480）实际=%s'
       % (SR.viewport_size(cam2, {'w': 320, 'h': 1160}),))
    ok(SR.viewport_size(cam2, {'w': 320, 'h': 240}) != (640, 240),
       'B13b 不是"一刀切按最小轴"（宽度不牵连高度）')
    # 负控制：非法 geo → 相机尺寸
    ok(SR.viewport_size(cam, None) == (640, 480), 'B14 geo None → 相机尺寸')
    ok(SR.viewport_size(cam, {'w': -5, 'h': 240}) == (640, 480),
       'B15 非法 w → 相机尺寸（不返回负数）')

    # --- to_output（**乘** scale：逻辑 → 输出像素）---
    ok(SR.to_output((0, 0, 640, 480), cam2) == (0, 0, 1280, 960),
       'B16 to_output ×scale 实际=%s' % (SR.to_output((0, 0, 640, 480), cam2),))
    ok(SR.to_output((100, 50, 300, 250), cam2) == (200, 100, 400, 400),
       'B17 to_output 非零原点 实际=%s' % (SR.to_output((100, 50, 300, 250), cam2),))
    ok(SR.to_output((10, 20, 30, 40), cam) == (10, 20, 20, 20),
       'B17b scale=1 → 原样')
    ok(SR.to_output(None, cam2) is None, 'B18 to_output None → None')
    ok(SR.to_output((1, 2, 3), cam2) is None, 'B19 to_output 长度错 → None')

    # --- output_size（相机原始尺寸；scale 在推导中约掉）---
    ok(SR.output_size(cam2) == (640, 480), 'B20 output_size = camera.size 实际=%s'
       % (SR.output_size(cam2),))
    ok(SR.output_size(cam) == (640, 480), 'B20b scale=1 同值')
    ok(SR.output_size(None) == (640, 480), 'B21 output_size None → 默认')

    # --- 坐标系自洽（★ 第44轮修正的核心断言）---
    # 相机逻辑窗口 = size/scale（640/2 = 320x240）
    ok(cam2.scoped_size() == (320, 240),
       'B22 scoped_size = size/scale = 320x240 实际=%s' % (cam2.scoped_size(),))
    # 320x240 房间 @scale2 且相机窗口逻辑 = 320x240 ⇒ 房间恰好一屏、相机不自移
    c = SC.Camera((640, 480), 0, 2.0)
    r = c.follow((0.0, 0.0, 320.0, 240.0), (152, 104, 168, 120))
    ok(r is not None and abs(r[2] - 320.0) < 0.01,
       'B23 相机矩形宽 = 320（逻辑窗口）实际=%s' % (r,))
    vwr = c.to_view_rect((0.0, 0.0, 320.0, 240.0))
    px = SR.to_output(vwr, c)
    ok(px is not None and px[2] == 640 and px[3] == 480,
       'B24 320x240@2 → 输出 640x480 像素 实际=%s' % (px,))


# ===========================================================================
# C 视口剔除
# ===========================================================================
def sec_c():
    print('== C 视口剔除 ==')
    ok(SR.visible_in_view((0, 0, 10, 10), (640, 480)), 'C1 左上角可见')
    ok(SR.visible_in_view((630, 470, 10, 10), (640, 480)), 'C2 右下角部分可见')
    ok(SR.visible_in_view((-10, -10, 20, 20), (640, 480)), 'C3 左上越界部分可见')
    ok(not SR.visible_in_view((700, 0, 10, 10), (640, 480)), 'C4 完全在右侧 → 剔除')
    ok(not SR.visible_in_view((0, 600, 10, 10), (640, 480)), 'C5 完全在下方 → 剔除')
    ok(not SR.visible_in_view((-100, 0, 50, 10), (640, 480)), 'C6 完全在左侧 → 剔除')
    ok(not SR.visible_in_view((640, 0, 10, 10), (640, 480)),
       'C7 正好贴右边界（x==vw）→ 剔除（半开区间）')
    # 负控制：坏输入必须为 False 而不是崩 / 而不是 True
    ok(not SR.visible_in_view(None, (640, 480)), 'C8 None → False')
    ok(not SR.visible_in_view((1, 2, 3), (640, 480)), 'C9 长度错 → False')
    ok(not SR.visible_in_view((0, 0, 10, 10), (0, 0)), 'C10 视口零尺寸 → False')
    ok(not SR.visible_in_view((0, 0, 0, 10), (640, 480)), 'C11 零宽矩形 → False')


# ===========================================================================
# D 绘制计划
# ===========================================================================
def sec_d():
    print('== D 绘制计划 ==')
    geo = _geo_table()
    idx = SS.load_index()
    scenes = idx.get('scenes') or {}

    # D1 空输入 → 空计划（不崩）
    ok(SR.plan_frame(None, None, geo) == [], 'D1a scene=None → []')
    ok(SR.plan_frame(SS.SceneState(), None, geo) == [], 'D1b camera=None → []')
    cam_nofollow = SC.Camera((640, 480), 0, 1.0)
    ok(SR.plan_frame(SS.SceneState(), cam_nofollow, geo) == [],
       'D1c 相机未 follow → []（不把世界坐标当屏幕坐标）')
    ok(SR.plan_viewport(None, None, geo) == (0, 0), 'D1d viewport 空输入 → (0,0)')

    # D2 真实数据：ch1 克里斯的房间
    sid = 'ch1.kris_room.kris_s_room'
    ent = scenes.get(sid)
    ok(ent is not None, 'D2a 场景 %s 已登记' % sid)
    sc = SS.load_scene(sid, entry=ent)
    ok(sc is not None, 'D2b 场景加载成功')
    ok(getattr(sc, 'original_room_id', None) == 2,
       'D2c original_room_id 从 entry 补上（=2）实际=%s'
       % (getattr(sc, 'original_room_id', None),))
    cam = SC.Camera((640, 480), 0, 2.0)
    world = SR.room_world_rect({'w': 320, 'h': 240}, cam)
    cam.follow(world, (152, 104, 168, 120))
    plan = SR.plan_frame(sc, cam, geo)
    ok(len(plan) >= 1, 'D2d 产出至少 1 条指令 实际=%d' % len(plan))
    bg_items = [i for i in plan if i['kind'] == SR.K_BG]
    ok(len(bg_items) == 1, 'D2e 有 1 条 bg 指令 实际=%d' % len(bg_items))
    if bg_items:
        ok(bg_items[0]['name'] == sc.bg, 'D2f bg 指令名与场景一致')
        ok(bg_items[0]['room_known'] is True, 'D2g room_known=True')
        r = bg_items[0]['rect']
        ok(r[2] == 640 and r[3] == 480,
           'D2h 320x240@2 → bg 输出 640x480 实际=%s' % (r,))
    vp = SR.plan_viewport(sc, cam, geo)
    ok(vp == (640, 480), 'D2i viewport = 640x480（= 原作现实世界输出）实际=%s' % (vp,))

    # D3 未登记房间 → placeholder（不静默空画）
    sc_d = SS.load_scene('desktop', entry=scenes.get('desktop'))
    ok(sc_d is not None, 'D3a desktop 场景加载成功')
    # D3 desktop：第89轮起 bg=`__transparent__` —— **声明式透明**，语义与
    #     `bg=None`（缺素材 ⇒ 画斜纹占位）**不同**。这里断两条：
    #       D3b 透明 ⇒ **不**产 placeholder（透出壁纸，不是"这里缺东西"）
    #       D3c 透明 ⇒ 但世界门仍在（"透明"不等于"整间空"）
    #     ★ 为什么必须区分（记忆 §4：判据别拿源码字面量代替产物输出）：
    #       若把透明与缺素材混为一谈，将来真把 bg 写丢时判据不会报红。
    #     ★★ 第99轮：D3c 原本写死 `== 8`。加第 9 扇门（Outertale）时它成了
    #       "判据与事实脱节"的样本。改成两条**不写死**的不变量：
    #         ① 声明的对象**全部**进绘制计划（声明 N ⇒ 计划里就有 N 条）；
    #         ② 下限 9 —— 桌面门数 = 五章(A~E) + UT(F) + 黄魂(W) + OneShot(X)
    #            + Outertale(Y)，第99轮起。
    cam3 = SC.Camera((640, 480), 0, 2.0)
    cam3.follow((0.0, 0.0, 640.0, 480.0), None)
    plan3 = SR.plan_frame(sc_d, cam3, geo)
    ph = [i for i in plan3 if i['kind'] == SR.K_PLACEHOLDER]
    ok(len(ph) == 0,
       'D3b desktop 声明式透明（bg=%s）⇒ 不产 placeholder 实际=%d'
       % (SCENES and getattr(sc_d, 'bg', '?'), len(ph)))
    _objs3 = [i for i in plan3 if i['kind'] == SR.K_OBJ]
    _want_objs3 = len(getattr(sc_d, 'objects', None) or [])
    ok(len(_objs3) == _want_objs3 and _want_objs3 >= 9,
       'D3c desktop 透明但仍渲染**全部** %d 个对象（透明≠整间空；下限 9 = 五章 + 四跨作品）'
       '实际=%d' % (_want_objs3, len(_objs3)))
    # D3d 负控制：真正的"缺素材"（bg=None）**必须**产 placeholder —— 证明
    #     D3b 的"0 条"不是因为渲染层坏了，而是因为 bg 声明了透明。
    class _FakeScene:
        bg = None
        bgm = None
        objects = []
        scene_id = 'unit_no_bg'
        chapter = area = 'unit'
    plan_nb = SR.plan_frame(_FakeScene(), cam3, geo)
    ph_nb = [i for i in plan_nb if i['kind'] == SR.K_PLACEHOLDER]
    ok(len(ph_nb) == 1 and ph_nb[0].get('room_known') is False and ph_nb[0].get('reason'),
       'D3d 负控制：bg=None（真缺素材）必产 1 条带原因的 placeholder 实际=%d'
       % len(ph_nb))

    # D4 大房间：房间边框
    sid4 = 'ch1.castle_town.castle_town'
    ent4 = scenes.get(sid4)
    if ent4:
        sc4 = SS.load_scene(sid4, entry=ent4)
        g4 = SR.room_geometry(getattr(sc4, 'original_room_id', None),
                              sc4.chapter_id, geo)
        w4 = SR.room_world_rect(g4, cam3)
        cam4 = SC.Camera((640, 480), 0, 2.0)
        cam4.follow(w4, (w4[2] / 2 - 8, w4[3] / 2 - 16, w4[2] / 2 + 8, w4[3] / 2))
        plan4 = SR.plan_frame(sc4, cam4, geo)
        rb = [i for i in plan4 if i['kind'] == SR.K_ROOM_BORDER]
        ok(len(rb) == 1, 'D4a 宽房间（%s）产 1 条房间边框 实际=%d'
           % (g4, len(rb)))
        # 负控制：小房间不该有边框
        # ★ 第60轮：原来是 `ok(True, 'D4b …')` —— 字面量恒真、无兜底，
        #   属"看着在守、其实没守"（第60轮恒真普查 B7 抓出）。
        #   现在补成**真的负控制**：与 D2 同一间 320x240 的房间，
        #   相机视口正好等于整间房 ⇒ 全房可见 ⇒ 不该画房间边框。
        #   （D4a 是正控制"宽房间要 1 条"，此处是它的镜像。）
        _w_small = SR.room_world_rect({'w': 320, 'h': 240}, cam)
        _cam_small = SC.Camera((640, 480), 0, 2.0)
        _cam_small.follow(_w_small, (152, 104, 168, 120))
        _plan_small = SR.plan_frame(sc, _cam_small, geo)
        _rb_small = [i for i in _plan_small if i['kind'] == SR.K_ROOM_BORDER]
        ok(len(_rb_small) == 0,
           'D4b 小房间（320x240，视口=整间房）不产房间边框 实际=%d' % len(_rb_small))

    # D5 物件：合成一个带 pos 的场景（**真实坐标量级**：320x240 房间内）
    st = SS.SceneState()
    st.scene_id = 'ch1.kris_room.kris_s_room'
    st.chapter_id = 'ch1'
    st.original_room_id = 2
    st.bg = 'bg/fake.png'
    st.objects = [
        # 房间中心附近（应可见；相机在 320x240 房间上居中 → 相机左上 = (-160,-120)）
        {'pos': [160, 200], 'sprite': 'spr_kris_idle_0.png'},
        {'pos': [100000, 100000], 'sprite': 'spr_far.png'},   # 远在天边 → 剔除
        {'pos': 'bad'},                                        # 坏数据 → 跳过
    ]
    cam5 = SC.Camera((640, 480), 0, 2.0)
    cam5.follow((0.0, 0.0, 320.0, 240.0), (152, 104, 168, 120))
    plan5 = SR.plan_frame(st, cam5, geo, sprite_size=lambda n: (21, 41))
    objs = [i for i in plan5 if i['kind'] == SR.K_OBJ]
    ok(len(objs) == 1, 'D5a 3 个物件 → 只留下 1 个可见 实际=%d (plan=%s)'
       % (len(objs), SR.plan_summary(plan5)))
    ok(objs and objs[0]['name'] == 'spr_kris_idle_0.png', 'D5b 留下的是可见那个')
    # 原 21x41 @scale2 → 输出 42x82（= 产品当前 Ralsei 的显示尺寸）
    ok(objs and objs[0]['rect'][2] == 42 and objs[0]['rect'][3] == 82,
       'D5c 精灵尺寸 21x41@2 = 42x82 实际=%s'
       % (objs[0]['rect'] if objs else None,))
    # 正/负控制：把同一个物件挪到远处 → 必须被剔除（证明剔除真在工作）
    st2 = SS.SceneState()
    st2.chapter_id = 'ch1'
    st2.original_room_id = 2
    st2.bg = 'bg/fake.png'
    st2.objects = [{'pos': [5000, 5000], 'sprite': 'spr_x.png'}]
    plan6 = SR.plan_frame(st2, cam5, geo, sprite_size=lambda n: (21, 41))
    ok(len([i for i in plan6 if i['kind'] == SR.K_OBJ]) == 0,
       'D5d 远处物件被剔除（负控制）')

    # D6 plan_summary
    ok(SR.plan_summary([]) == '（无绘制指令）', 'D6a 空计划摘要')
    s = SR.plan_summary(plan)
    ok('bg' in s, 'D6b 摘要含 bg 实际=%s' % s)

    # D7 ★★★ 背景**按素材原尺寸**绘制（第44轮真机实测修正的判据）
    #    早先版本把"房间世界矩形"整个拉伸给背景 —— 真机一跑就错：`castle_front`
    #    房间 1000×1000 但背景只有 660×480，拉伸 = 放大 1.5 倍 ⇒ 像素风糊掉。
    #    正确：背景落在 `素材像素 × scale`，位置在房间原点（原作背景层偏移恒 0）。
    st7 = SS.SceneState()
    st7.chapter_id = 'ch1'
    st7.original_room_id = 46          # room_castle_front：房间 1000×1000
    st7.bg = 'bg/ch1_castle_town_castle_front.png'   # 素材实际 660×480
    st7.objects = []
    g7 = SR.room_geometry(46, 'ch1', geo)
    ok(g7 is not None and g7['w'] == 1000 and g7['h'] == 1000,
       'D7a 房间世界 1000x1000（与素材尺寸**不同**，才测得出拉伸）实际=%s' % (g7,))
    cam7 = SC.Camera((640, 480), 0, 2.0)
    # 相机置于房间中心，背景完全在视野内
    cam7.follow((0.0, 0.0, 1000.0, 1000.0), (400, 380, 416, 396))
    plan7 = SR.plan_frame(st7, cam7, geo, sprite_size=lambda n: (660, 480))
    bg7 = [i for i in plan7 if i['kind'] == SR.K_BG]
    ok(len(bg7) == 1, 'D7b 背景产出 1 条 实际=%d' % len(bg7))
    if bg7:
        r7 = bg7[0]['rect']
        # ★★★ 第99轮修正：旧判据「按素材 660x480@2 = 1320x960」已被**推翻**。
        #     背景 PNG 是**屏幕像素分辨率**的截图（房间 320x240 <-> 素材 640x480），
        #     把素材像素当世界逻辑单位用会让背景被额外放大 2 倍、只看到房间的一个角
        #     （`kris_s_room` 离线渲染对照：现状只显示左上 1/4）；素材比房间小时更会
        #     整片空白（`card_castle_1f` 真机：相机视口与素材世界矩形无交集）。
        #     现口径 = 等比放大到**盖满**整间房（`scene_render.fit_bg_world`）。
        _k7 = max(1000.0 / 660.0, 1000.0 / 480.0)      # 独立复算，不调被测函数
        ok(r7[2] == int(round(660 * _k7 * 2)) and r7[3] == int(round(480 * _k7 * 2)),
           'D7c 等比 k=max(1000/660,1000/480)=%.5f => 输出 %dx%d（盖满房间 2000x2000）实际=%s'
           % (_k7, int(round(660 * _k7 * 2)), int(round(480 * _k7 * 2)), r7))
        ok(r7[2] >= 1000 * 2 and r7[3] >= 1000 * 2,
           'D7c2 两轴都 >= 房间像素（cover 的定义，留黑=0）实际=%s' % (r7,))
        ok(bg7[0].get('fit') == 'cover', 'D7c3 指令标记 fit=cover 实际=%s'
           % (bg7[0].get('fit'),))
        _sx = r7[2] / float(660 * 2)
        _sy = r7[3] / float(480 * 2)
        ok(abs(_sx - _sy) < 0.01,
           'D7c4 等比：两轴倍率相同（sx=%.4f sy=%.4f，禁非等比拉伸）' % (_sx, _sy))
        ok(bg7[0].get('native') == (660, 480),
           'D7d bg 指令带 native=(660,480) 实际=%s' % (bg7[0].get('native'),))
    # 负控制：不给 sprite_size → 退回房间矩形（**保守安全**，不是崩）
    plan7b = SR.plan_frame(st7, cam7, geo, sprite_size=None)
    bg7b = [i for i in plan7b if i['kind'] == SR.K_BG]
    ok(bg7b and bg7b[0].get('native') == (None, None),
       'D7e 无 sprite_size → native=(None,None)（退化为房间矩形，不崩）实际=%s'
       % (bg7b[0].get('native') if bg7b else None,))
    ok(bg7b and bg7b[0]['rect'][2] == 1000 * 2,
       'D7f 退化时按房间 1000x1000@2 = 2000x2000 实际=%s'
       % (bg7b[0]['rect'] if bg7b else None,))
    ok(bg7b and bg7b[0].get('fit') == 'room',
       'D7g 退化分支显式标 fit=room（不冒充 cover）实际=%s'
       % (bg7b[0].get('fit') if bg7b else None,))

    # D8 背景在相机偏移下**同步平移**（"背景相对运动"的算术表达）
    #    相机右移 Δ 逻辑 → bg 像素左移 Δ×scale。这是零视差的直接判据。
    cam8a = SC.Camera((640, 480), 0, 2.0)
    cam8a.follow((0.0, 0.0, 1000.0, 1000.0), (200, 380, 216, 396))
    pa = SR.plan_frame(st7, cam8a, geo, sprite_size=lambda n: (660, 480))
    cam8b = SC.Camera((640, 480), 0, 2.0)
    cam8b.follow((0.0, 0.0, 1000.0, 1000.0), (300, 380, 316, 396))   # 目标右移 100
    pb = SR.plan_frame(st7, cam8b, geo, sprite_size=lambda n: (660, 480))
    ba = [i for i in pa if i['kind'] == SR.K_BG]
    bb = [i for i in pb if i['kind'] == SR.K_BG]
    if ba and bb:
        dx = bb[0]['rect'][0] - ba[0]['rect'][0]
        ok(dx == -100 * 2,
           'D8 相机右移 100 逻辑 → 背景左移 200 像素（零视差）实际 dx=%s' % dx)

    # D9 ★★★ 相机在房间任意角落，背景都**必须**盖满视口（第99轮真机缺陷的回归锁）
    # 旧判据是「背景完全在视野外 -> 被剔除（不画看不见的东西）」—— 那条**已被推翻**：
    # 它把"按素材原尺寸铺"当成了正确行为，于是相机跟到房间另一侧时背景整条消失，
    # 屏幕上什么都不画、壁纸直接透出来（第99轮真机：`card_castle_1f` 房间 1840x1080 /
    # 素材 1280x751，相机 (1385,787) 的视口与素材世界矩形无交集，plan 只剩一条
    # 窗口外的 room_border，`canvas.grab()` 非透明采样 = 0）。
    # 现口径：等比放大到盖满 -> 相机永远在背景内部 -> **必然可见**。
    st9 = SS.SceneState()
    st9.chapter_id = 'ch1'
    st9.original_room_id = 46
    st9.bg = 'bg/x.png'
    st9.objects = []
    cam9 = SC.Camera((640, 480), 0, 2.0)
    # 把相机推到房间右下角（目标远在天边 -> 四向钳制到右下）
    cam9.follow((0.0, 0.0, 1000.0, 1000.0), (5000, 5000, 5016, 5016))
    plan9 = SR.plan_frame(st9, cam9, geo, sprite_size=lambda n: (660, 480))
    _bg9 = [i for i in plan9 if i['kind'] == SR.K_BG]
    ok(len(_bg9) == 1,
       'D9a 相机贴房间右下角 -> 背景**仍产出** 1 条（不得再整条消失）实际=%d' % len(_bg9))
    ok(len([i for i in plan9 if i['kind'] == SR.K_PLACEHOLDER]) == 0,
       'D9b 背景盖满 != 缺背景（不产 placeholder）')
    if _bg9:
        _r9 = _bg9[0]['rect']
        ok(_r9[0] <= 0 and _r9[1] <= 0 and _r9[0] + _r9[2] >= 640
           and _r9[1] + _r9[3] >= 480,
           'D9c 背景矩形**覆盖整个视口** 640x480（x<=0 y<=0 且右下>=视口）实际=%s' % (_r9,))
    # D9d 房间底色（K_ROOM_FILL）在位、且盖满视口、在最前（= 最底层）
    _rf9 = [i for i in plan9 if i['kind'] == SR.K_ROOM_FILL]
    ok(len(_rf9) == 1, 'D9d1 无背景声明的场景产 1 条房间底色 实际=%d' % len(_rf9))
    if _rf9:
        ok(_rf9[0].get('color') == SR.ROOM_FILL_RGBA and SR.ROOM_FILL_RGBA[:3] == (0, 0, 0),
           'D9d2 房间底色 = 不透明纯黑 %s（用户口径「剩下的用黑色填充」）'
           % (SR.ROOM_FILL_RGBA,))
        _rr9 = _rf9[0]['rect']
        ok(_rr9[0] <= 0 and _rr9[1] <= 0 and _rr9[0] + _rr9[2] >= 640
           and _rr9[1] + _rr9[3] >= 480,
           'D9d3 房间底色盖满视口实际=%s' % (_rr9,))
    ok(plan9 and plan9[0]['kind'] == SR.K_ROOM_FILL,
       'D9d4 房间底色是计划里**第一条**（先画=最底层）实际首条=%s'
       % (plan9[0]['kind'] if plan9 else None,))
    # D9e 负控制：真·缺素材（bg=None）仍产 placeholder，且**仍有**房间底色
    #     （证明 D9b 的 0 条不是"渲染层坏了"）
    _fake9 = SS.SceneState()
    _fake9.chapter_id = 'ch1'
    _fake9.original_room_id = 46
    _fake9.bg = None
    _fake9.objects = []
    _p9e = SR.plan_frame(_fake9, cam9, geo)
    ok(len([i for i in _p9e if i['kind'] == SR.K_ROOM_FILL]) == 1
       and len([i for i in _p9e if i['kind'] == SR.K_PLACEHOLDER]) == 1,
       'D9e 缺素材 -> 黑底 + 1 条占位（黑底不因缺图而消失）实际=%s'
       % (SR.plan_summary(_p9e),))
    # D9f 负控制：桌面场景（声明式透明）**不许**产房间底色（否则盖住壁纸）
    _fake9.bg = SR.TRANSPARENT_BG
    _p9f = SR.plan_frame(_fake9, cam9, geo)
    ok(len([i for i in _p9f if i['kind'] == SR.K_ROOM_FILL]) == 0
       and len([i for i in _p9f if i['kind'] == SR.K_PLACEHOLDER]) == 0,
       'D9f 声明式透明 -> 0 黑底 0 占位（桌面场景透出壁纸）实际=%s'
       % (SR.plan_summary(_p9f),))
    # D9g fit_bg_world 纯函数：正/负成对
    ok(SR.fit_bg_world(320, 240, (0.0, 0.0, 320.0, 240.0))
       == (0.0, 0.0, 320.0, 240.0),
       'D9g1 素材==房间 -> 原样（k=1）实际=%s'
       % (SR.fit_bg_world(320, 240, (0.0, 0.0, 320.0, 240.0)),))
    _f = SR.fit_bg_world(660, 480, (0.0, 0.0, 1000.0, 1000.0))
    ok(_f is not None and _f[2] >= 1000.0 and _f[3] >= 1000.0,
       'D9g2 素材小于房间 -> 放大到两轴都 >= 房间 实际=%s' % (_f,))
    ok(SR.fit_bg_world(0, 480, (0.0, 0.0, 1000.0, 1000.0)) is None,
       'D9g3 负控制：素材宽 0 -> None（不伪装成合法矩形）')
    ok(SR.fit_bg_world(660, 480, None) is None, 'D9g4 负控制：room=None -> None')
    ok(SR.fit_bg_world(660, 480, (0.0, 0.0, 0.0, 1000.0)) is None,
       'D9g5 负控制：房间宽 0 -> None')


# ===========================================================================
# E 产品接线
# ===========================================================================
def sec_e():
    print('== E 产品接线 ==')
    ctl = _read(os.path.join(MOD, 'scene_controller.py'))
    main = _read(os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py'))

    ok('def load_geometry(' in ctl, 'E1 控制器定义 load_geometry')
    ok('def plan_frame(' in ctl, 'E2 控制器定义 plan_frame')
    ok('def render_summary(' in ctl, 'E3 控制器定义 render_summary')
    ok('import scene_render' in ctl, 'E4 控制器 import scene_render')

    # ★ main.py 真的调了（"函数写对了但产品没用上"是最贵的坑）
    ok('self.scene.load_geometry()' in main, 'E5 main.py 真调 load_geometry()')

    # 预声明
    ok('self._scene_geometry' in main, 'E6a main.py 预声明 _scene_geometry')
    ok('self._geometry_loaded' in main, 'E6b main.py 预声明 _geometry_loaded')
    ok('self.scene_plan' in main, 'E6c main.py 预声明 scene_plan')

    # ★ 缩放口径（用户 44 轮：至少与 Ralsei 大小一致）
    ok('self.scene_scale = 2.0' in main,
       'E7 scene_scale = 2.0（与 Ralsei 显示倍率一致）')
    ok('scene_scale = 1.5' not in main, 'E7b 无残留的 1.5')
    # 依据可查
    ok('21' in main and '41' in main, 'E8 注释写明原作精灵 21x41')

    # 负控制：控制器不该有 QTimer / 不该 import Qt
    ok('QTimer' not in ctl, 'E9a 控制器无 QTimer（P1 也不注册定时器）')
    ok('PyQt5' not in ctl, 'E9b 控制器不 import Qt')

    # 套件自身恒真自查：确认判据数量够
    ok(_N[0] > 40, 'E10 断言条数 > 40（实际 %d）' % _N[0])


def main():
    print('第44轮 渲染层回归锁（%s）' % os.path.basename(__file__))
    sec_a()
    sec_b()
    sec_c()
    sec_d()
    sec_e()
    print()
    if _FAIL:
        print('[FAIL] 共 %d 条失败（断言 %d）' % (len(_FAIL), _N[0]))
        for f in _FAIL:
            print('   - ' + f)
        return 1
    print('渲染层回归锁：%d/%d 全绿' % (_N[0], _N[0]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
