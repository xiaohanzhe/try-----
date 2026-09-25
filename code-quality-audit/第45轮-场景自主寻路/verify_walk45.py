# -*- coding: utf-8 -*-
"""第45轮(续) · 「场景内行走 + 障碍绕行」回归锁

配套模块：`ralsei_pet/modules/scene_walk.py`
数据资产：`ralsei_pet/assets/scenes/_obstacles.ch{1..5}.json`

★ 纪律（与 G2 其它套件同源）：
  1. 每条断言 **必须** `print('[PASS] ...')` 字面量（run_all.py 按 `[PASS]` 计数）；
  2. **正/负控制成对**（报了 A 也要证明"反过来不报"）；
  3. **行为判据必须用真实量级输入**（不要 10px 的小玩具房间）；
  4. **不 import Qt、不 import 项目内模块**（用 importlib 从文件路径直接加载，
     避免把初始化环接上）。
"""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
MOD = os.path.join(REPO, 'ralsei_pet', 'modules', 'scene_walk.py')
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')

PASS = 0
FAIL = 0


def check(name, cond, extra=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print('[PASS] %s' % name)
    else:
        FAIL += 1
        print('[FAIL] %s %s' % (name, extra))


def load_module():
    spec = importlib.util.spec_from_file_location('scene_walk_under_test', MOD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    print('=== 第45轮(续) 场景内行走 / 障碍绕行 回归锁 ===')
    print('模块: %s' % MOD)

    if not os.path.isfile(MOD):
        print('[FAIL] 找不到 scene_walk.py')
        return 1
    check('scene_walk.py 存在', True)

    W = load_module()

    # =======================================================================
    #  A 段：模块纪律（零 Qt / 零项目内依赖）
    # =======================================================================
    print()
    print('== A. 模块纪律 ==')
    src = open(MOD, encoding='utf-8').read()
    check('A1 未 import PyQt', 'PyQt' not in src)
    check('A2 未 import PySide', 'PySide' not in src)
    # 负控制：确认源码里**确实**有 import 语句（否则 A3 是恒真判据）
    check('A3a 源码含 import（A3 的前提）', '\nimport ' in src)
    import re
    mods = re.findall(r'^\s*(?:import|from)\s+([A-Za-z_][\w.]*)', src, re.M)
    bad = [m for m in mods if m.split('.')[0] in (
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'main', 'scene_system',
        'scene_routing', 'scene_camera', 'scene_render', 'scene_pathfind',
        'data_store', 'lazy_log')]
    check('A3 未 import 项目内模块 / Qt', not bad, 'got=%s' % bad)
    check('A4 import 了 math/json/os（A5 的反面前提）',
          all(m in mods for m in ('math', 'json', 'os')), 'mods=%s' % mods)

    # =======================================================================
    #  B 段：数据加载（真实量级）
    # =======================================================================
    print()
    print('== B. 障碍数据加载 ==')
    tot_rooms = tot_items = 0
    for ch in (1, 2, 3, 4, 5):
        d = W.load_obstacles(ch, SCENES)
        check('B1.%d ch%d 加载成功' % (ch, ch), d['ok'], 'err=%s' % d.get('error'))
        if d['ok']:
            n_items = sum(len(v['items']) for v in d['rooms'].values())
            tot_rooms += len(d['rooms'])
            tot_items += n_items
    check('B2 五章合计房数 == 408', tot_rooms == 408, 'got=%d' % tot_rooms)
    check('B3 五章合计障碍数 == 4452', tot_items == 4452, 'got=%d' % tot_items)

    # 负控制：不存在的章 → ok=False（不是抛异常）
    bad = W.load_obstacles(99, SCENES)
    check('B4 不存在的章 ok=False 且不抛', bad['ok'] is False and bad['rooms'] == {})

    # =======================================================================
    #  C 段：可走性判定（真实值 vs 已知真值）
    # =======================================================================
    print()
    print('== C. 可走性判定（对照原作实测坐标）==')
    obs = W.room_obstacles(1, 3, SCENES)   # ch1 room_krishallway
    check('C1 krishallway 障碍数 == 9', len(obs) == 9, 'got=%d' % len(obs))

    # 已知真值锚点：那条 221.05x18 的墙 x=61 y=109（锚点校验已精确断言过）
    wall = None
    for r in obs:
        if abs(r[0] - 61.0) < 0.01 and abs(r[1] - 109.0) < 0.01:
            wall = r
            break
    check('C2 找到 x=61 y=109 的墙', wall is not None)
    if wall:
        check('C3 该墙尺寸 ~221x18',
              abs(wall[2] - 221.0526) < 0.01 and abs(wall[3] - 18.0) < 0.01,
              'w=%s h=%s' % (wall[2], wall[3]))

    # 墙中心（x=61+110.5=171.5, y=109+9=118）：
    # krishallway 障碍的 y 区间（主角 bbox = 锚点 y+25 .. y+38，高 13 ⇒ y[ay+25, ay+38)）：
    #   (61,109,221.05,18)  => y[109,127)
    #   (57,166,422.05,18)  => y[166,184)
    # ⇒ 锚点 y 落在 [102,109) 会撞上层墙？ 不：bbox y[127,140) 起点 127 需 <127 才算重叠。
    #   要"不撞任何障碍"，需要 bbox 完全落在 [127,166) 之间窄带，或 y<84。
    #   y[127,166) 高 39 > bbox 高 13 ⇒ 存在合法锚点。
    #   取锚点 y = 110 ⇒ bbox y[135,148) ⊂ [127,166) ✅ 且 x=165 时 X 也在 [61,282.05) 内。
    check('C4a 锚点(165,85) bbox 压在墙上 ⇒ 被挡', W.blocks_at(obs, 165.0, 85.0) is True)
    check('C4b 锚点(165,110) bbox 落在两墙之间空隙 ⇒ 可走（负控制）',
          W.blocks_at(obs, 165.0, 110.0) is False)
    # ★ 已知真值：原作主角起点 obj_mainchara x=242 y=128（room_krishallway）
    #   必须**可走**（原作就在那儿站着；bbox 实测 19×14 + 偏移 y+25）。
    check('C5 ★ 原作主角起点(242,128)可走',
          W.blocks_at(obs, 242.0, 128.0) is False)
    # 负控制：把锚点上移到 y=90 ⇒ bbox y[115,129]，压住 x[238,258]y[112,132] 那块砖
    check('C5b 锚点(242,90) 撞上 (238,112) 那块砖（鉴别力）',
          W.blocks_at(obs, 242.0, 90.0) is True)
    # 负控制：很远处（避开障碍）可走
    check('C6 远处空地(500,20)可走', W.blocks_at(obs, 500.0, 20.0) is False)
    check('C6b 主角 bbox 常量 == 实测值',
          W.PLAYER_BBOX_W == 19 and W.PLAYER_BBOX_H == 13
          and W.PLAYER_BBOX_OFF_Y == 25,
          'w=%s h=%s offy=%s' % (W.PLAYER_BBOX_W, W.PLAYER_BBOX_H, W.PLAYER_BBOX_OFF_Y))

    # hit_obstacle 返回障碍本身；没撞返回 None
    hit = W.hit_obstacle(obs, 165.0, 85.0)
    check('C7 hit_obstacle 命中返回矩形', isinstance(hit, tuple) and len(hit) == 5)
    check('C8 hit_obstacle 未命中返回 None', W.hit_obstacle(obs, 242.0, 128.0) is None)

    # =======================================================================
    #  D 段：A* 寻路（真实房间 + 真实障碍）
    # =======================================================================
    print()
    print('== D. A* 寻路 ==')
    # room_krishallway 540x240；起点 (242,128) 到 (500,200)
    r = W.plan_walk(1, 3, (0.0, 0.0, 540.0, 240.0), (242.0, 128.0), (500.0, 200.0),
                    scene_dir_path=SCENES)
    check('D1 krishallway 能规划出路线', r['ok'], 'reason=%s' % r.get('reason'))
    if r['ok']:
        check('D2 航点数 >= 2', len(r['path']) >= 2, 'got=%d' % len(r['path']))
        check('D3 首点 == 起点', abs(r['path'][0][0] - 242.0) < 0.01 and abs(r['path'][0][1] - 128.0) < 0.01,
              'got=%s' % (r['path'][0],))
        check('D4 末点 == 终点', abs(r['path'][-1][0] - 500.0) < 0.01 and abs(r['path'][-1][1] - 200.0) < 0.01,
              'got=%s' % (r['path'][-1],))
        # ★★ 核心判据：整条路**每个航点都不撞障碍**（不是只查首尾）
        worst = None
        for i, (px, py) in enumerate(r['path']):
            if W.blocks_at(obs, px, py):
                worst = (i, px, py)
                break
        check('D5 ★ 全航点均不撞障碍', worst is None, '首个穿模点=%s' % (worst,))
        # 且相邻航点之间（用户看到的实际轨迹）也不撞墙
        pierced = None
        for i in range(len(r['path']) - 1):
            a, b = r['path'][i], r['path'][i + 1]
            if not W._segment_clear(obs, a[0], a[1], b[0], b[1], W.PLAYER_BBOX_W, W.PLAYER_BBOX_H, W.GRID_STEP):
                pierced = (i, a, b)
                break
        check('D6 ★ 相邻航点连线也不穿墙', pierced is None, '穿模段=%s' % (pierced,))

    # D7 负控制：被完全封死的目标 → ok=False（**不返回穿墙直线**）
    sealed = [(0.0, 0.0, 540.0, 20.0, 'solid'),     # 上墙
              (0.0, 220.0, 540.0, 20.0, 'solid'),   # 下墙
              (0.0, 0.0, 20.0, 240.0, 'solid'),     # 左墙
              (520.0, 0.0, 20.0, 240.0, 'solid'),   # 右墙
              (200.0, 0.0, 20.0, 240.0, 'solid')]   # 中间隔断（连通性被切断）
    r2 = W.plan_walk(1, 3, (0.0, 0.0, 540.0, 240.0), (50.0, 120.0), (450.0, 120.0),
                     obstacles=sealed, scene_dir_path=SCENES)
    check('D7 被隔断时 ok=False', r2['ok'] is False, 'ok=%s path=%s' % (r2['ok'], r2['path'][:3]))
    check('D8 被隔断时 path 为空（不返回穿墙直线）', r2['path'] == [], 'got=%s' % r2['path'][:3])
    check('D9 有可读 reason', bool(r2.get('reason')), 'reason=%r' % r2.get('reason'))
    # ★ D7b 把夹具前提**显式钉住**（第 45 轮鉴别力体检的教训）：
    #   D7/D8 要证明的是「**连通性被切断** ⇒ 如实说走不到」，
    #   而不是"起点落在障碍里 ⇒ 随便返回空"。若将来夹具漂了（比如起点挪进墙里），
    #   D7/D8 会"照样绿"却不再守那条代码路径（`astar` 返回 None 的分支）。
    check('D7b ★ 夹具两端本身都可走（证明切的是连通性，不是起点不可站）',
          W.blocks_at(sealed, 50.0, 120.0) is False
          and W.blocks_at(sealed, 450.0, 120.0) is False)

    # D10 正控制（与 D7 成对）：把隔断去掉 → 同两点必须可达
    opened = [sealed[0], sealed[1], sealed[2], sealed[3]]
    r3 = W.plan_walk(1, 3, (0.0, 0.0, 540.0, 240.0), (50.0, 120.0), (450.0, 120.0),
                     obstacles=opened, scene_dir_path=SCENES)
    check('D10 去掉隔断后可达（D7 的正控制）', r3['ok'], 'reason=%s' % r3.get('reason'))
    # ★ 证明 D7 是"真被隔断"而不是"判据太严"
    check('D11 D7/D10 结果不同（鉴别力）', r2['ok'] != r3['ok'])

    # =======================================================================
    #  E 段：平滑（自然路线）
    # =======================================================================
    print()
    print('== E. 路线平滑 ==')
    # E1 平滑确实增加了航点数（在拐角处插值）
    zig = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (200.0, 100.0)]
    sm = W.chaikin(zig, iterations=2)
    check('E1 chaikin 增加了中间点', len(sm) > len(zig), 'in=%d out=%d' % (len(zig), len(sm)))
    check('E2 chaikin 保留首尾',
          sm[0] == (0.0, 0.0) and sm[-1] == (200.0, 100.0), 'first=%s last=%s' % (sm[0], sm[-1]))
    # E3 负控制：2 点输入不该被"平滑"成更多点（避免无意义插值）
    sm2 = W.chaikin([(0.0, 0.0), (10.0, 10.0)], iterations=2)
    check('E3 chaikin 对 2 点输入原样返回', len(sm2) == 2, 'got=%d' % len(sm2))
    # E4 负控制：iterations=0 原样返回（不是恒真——对比 iterations=2 的输出长度）
    sm3 = W.chaikin(zig, iterations=0)
    check('E4 iterations=0 原样返回', len(sm3) == len(zig), 'got=%d' % len(sm3))
    check('E5 E1/E4 输出长度不同（鉴别力）', len(sm) != len(sm3))

    # E6 共线点被删（但形状不变的直线段）
    line = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (30.0, 0.0)]
    simp = W.simplify_collinear(line)
    check('E6 共线中继点被删', len(simp) == 2, 'got=%d %s' % (len(simp), simp))
    # E7 负控制：有拐角时不许删
    corner = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0)]
    simp2 = W.simplify_collinear(corner)
    check('E7 拐角点被保留', len(simp2) == 3, 'got=%d %s' % (len(simp2), simp2))

    # E8 ★ 平滑后逐点可走（"平滑不许穿墙"律）
    r4 = W.plan_walk(1, 3, (0.0, 0.0, 540.0, 240.0), (242.0, 128.0), (500.0, 200.0),
                     scene_dir_path=SCENES, smooth=True)
    check('E8 平滑版能规划', r4['ok'], 'reason=%s' % r4.get('reason'))
    if r4['ok']:
        check('E9 平滑确实生效', r4['smoothed'] is True, 'smoothed=%s' % r4['smoothed'])
        bad_pt = None
        for i, (px, py) in enumerate(r4['path']):
            if W.blocks_at(obs, px, py):
                bad_pt = (i, px, py)
                break
        check('E10 ★ 平滑后仍全航点可走', bad_pt is None, '穿模点=%s' % (bad_pt,))
        seg_bad = None
        for i in range(len(r4['path']) - 1):
            a, b = r4['path'][i], r4['path'][i + 1]
            if not W._segment_clear(obs, a[0], a[1], b[0], b[1], W.PLAYER_BBOX_W, W.PLAYER_BBOX_H, W.GRID_STEP):
                seg_bad = (i, a, b)
                break
        check('E11 ★ 平滑后相邻连线仍不穿墙', seg_bad is None, '穿模段=%s' % (seg_bad,))

    # E12 负控制：故意把平滑"推到墙里"，验证 keep_walkable 会回退。
    # 墙 = (30,30,60,40) ⇒ x[30,90) y[30,70)。主角 bbox 19×13（锚点 (x,y) ⇒ y+25..y+38）。
    # 原折线绕墙走（下方 y=120 ⇒ bbox y[145,158) 安全）；平滑会把中间点拉向直线，
    # 一旦拉进 x[30,90) y[5,45) 这个"bbox 会撞墙的锚点区"，必须被回退。
    obs_wall = [(30.0, 30.0, 60.0, 40.0, 'solid')]
    pts = [(0.0, 120.0), (30.0, 118.0), (60.0, 116.0), (95.0, 118.0), (120.0, 120.0)]
    # 前提断言：输入原折线本身必须全部可走（否则 E12 在测一个坏夹具）
    in_bad = [p for p in pts if W.blocks_at(obs_wall, p[0], p[1])]
    check('E12a 夹具输入全可走（E12 的前提）', not in_bad, '坏点=%s' % in_bad)
    kept = W.smooth_keep_walkable(pts, obs_wall, iterations=3)
    bad2 = [p for p in kept if W.blocks_at(obs_wall, p[0], p[1])]
    check('E12 平滑回退保证不穿墙（含贴墙输入）', not bad2, '穿模点=%s' % bad2[:3])
    # E12b 且平滑确实做了事（输出 != 输入），否则 E12 是"恒真判据"
    check('E12b 平滑确实改变了点列（鉴别力）',
          [tuple(round(c, 3) for c in p) for p in kept] != [tuple(round(c, 3) for c in p) for p in pts])

    # -----------------------------------------------------------------------
    # E13 ★ 鉴别力夹具（专治"平滑不回退"这类破坏）
    #   krishallway 的**贴边折线** —— 由 `pad=0` 建格跑出的真实 A* 路径
    #   （8 点；输入本身逐点 + 逐段全干净）。
    #   裸 chaikin 会把它推穿 `(479,123,25,44.2)` 的左上角（实测点穿模 42 个、
    #   段穿模 1 段），而 `smooth_keep_walkable` 必须把它修回不穿墙。
    #   ⇒ 任何"平滑不回退 / 回退失效"的破坏都必被 E13c/E13d/E13e 抓住。
    #   （E12 的夹具离线太远，裸 chaikin 恰好不穿墙 ⇒ 没鉴别力，故必须有 E13。）
    # -----------------------------------------------------------------------
    E13_PTS = [(242.0, 128.0), (405.0, 125.0), (435.0, 95.0), (435.0, 65.0),
               (485.0, 65.0), (505.0, 85.0), (505.0, 195.0), (500.0, 200.0)]
    in13_pts = [q for q in E13_PTS if W.blocks_at(obs, q[0], q[1])]
    check('E13a 夹具输入全航点可走（E13 的前提）', not in13_pts, '坏点=%s' % in13_pts[:3])
    in13_seg = None
    for i in range(len(E13_PTS) - 1):
        a, b = E13_PTS[i], E13_PTS[i + 1]
        if not W._segment_clear(obs, a[0], a[1], b[0], b[1],
                                W.PLAYER_BBOX_W, W.PLAYER_BBOX_H, W.GRID_STEP):
            in13_seg = (i, a, b)
            break
    check('E13b 夹具输入全段不穿墙（E13 的前提）', in13_seg is None, '坏段=%s' % (in13_seg,))
    # ★★ 正控制：裸 chaikin 在这条夹具上**必须**穿墙 —— 否则这条判据没有鉴别力
    raw13 = W.chaikin(E13_PTS, iterations=3)
    raw13_bad = [q for q in raw13 if W.blocks_at(obs, q[0], q[1])]
    check('E13c ★★ 裸 chaikin 在此夹具上会穿墙（证明夹具真有鉴别力）',
          bool(raw13_bad), '输入点数=%d 居然没穿墙' % len(raw13))
    kept13 = W.smooth_keep_walkable(E13_PTS, obs, iterations=3)
    bad13 = [q for q in kept13 if W.blocks_at(obs, q[0], q[1])]
    check('E13d ★ 平滑回退后仍不穿墙（专治"不回退"破坏）', not bad13, '穿模点=%s' % bad13[:3])
    seg13 = None
    for i in range(len(kept13) - 1):
        a, b = kept13[i], kept13[i + 1]
        if not W._segment_clear(obs, a[0], a[1], b[0], b[1],
                                W.PLAYER_BBOX_W, W.PLAYER_BBOX_H, W.GRID_STEP):
            seg13 = (i, a, b)
            break
    check('E13e ★ 平滑回退后全段不穿墙', seg13 is None, '穿模段=%s' % (seg13,))
    check('E13f 平滑确实改变了点列（不是恒真判据）',
          [tuple(round(c, 3) for c in q) for q in kept13] !=
          [tuple(round(c, 3) for c in q) for q in E13_PTS],
          '输出 %d 点 vs 输入 %d 点' % (len(kept13), len(E13_PTS)))

    # =======================================================================
    #  F 段：门面 / 集成
    # =======================================================================
    print()
    print('== F. 门面 ==')
    check('F1 describe_walk 成功有可读文案', '可行走' in W.describe_walk(r3))
    check('F2 describe_walk 失败有可读文案', '走不过去' in W.describe_walk(r2))
    check('F3 describe_walk 空输入不抛', isinstance(W.describe_walk(None), str))

    # F4 房间矩形非法 → 如实报错
    r5 = W.plan_walk(1, 3, (0.0, 0.0, 0.0, 0.0), (1.0, 1.0), (2.0, 2.0), scene_dir_path=SCENES)
    check('F4 非法房间矩形 ok=False', r5['ok'] is False and bool(r5['reason']))

    # F5 读不到障碍表时（错误章号）→ 按无障碍处理，且**不抛**
    r6 = W.plan_walk(99, 3, (0.0, 0.0, 540.0, 240.0), (10.0, 10.0), (500.0, 200.0),
                     scene_dir_path=SCENES)
    check('F5 障碍表缺失时仍能规划（降级不抛）', r6['ok'] is True, 'reason=%s' % r6.get('reason'))

    # F6 ★ 真实量级：大房间（room_town_north 1800x240，22 个障碍）
    obs_tn = W.room_obstacles(1, 9, SCENES)
    check('F6 town_north 障碍数 == 22', len(obs_tn) == 22, 'got=%d' % len(obs_tn))
    r7 = W.plan_walk(1, 9, (0.0, 0.0, 1800.0, 240.0), (660.0, 180.0), (1200.0, 180.0),
                     obstacles=obs_tn, scene_dir_path=SCENES)
    check('F7 town_north 横穿 540px 能规划', r7['ok'], 'reason=%s' % r7.get('reason'))
    if r7['ok']:
        bad3 = None
        for i, (px, py) in enumerate(r7['path']):
            if W.blocks_at(obs_tn, px, py):
                bad3 = (i, px, py)
                break
        check('F8 ★ town_north 全航点可走', bad3 is None, '穿模点=%s' % (bad3,))

    # F9 最坏场景：room_dark2 34 个障碍（ch1 障碍最多的房间）
    obs_d2 = W.room_obstacles(1, 36, SCENES)
    check('F9 dark2 障碍数 == 34', len(obs_d2) == 34, 'got=%d' % len(obs_d2))

    # =======================================================================
    #  G 段：五章全量扫描 ★★ 「行为判据必须用真实量级输入」的落地
    #     第 45 轮的核心教训：D/E 段只用 krishallway / town_north 那几对起终点，
    #     **漏掉了 17/2376 的穿模**（三个真 bug 全在这里暴露）：
    #       · `simplify_collinear` 按共线性删点，把"绕角锯齿"的中继点删掉 ⇒ 切角
    #       · `pts[0] = (sx,sy)` **替换**而非插入，抹掉了已验证的"起点→s格心"短段
    #       · `_nearest_free` 只按欧氏距离找格，不管连线是否被障碍挡住
    #     ⇒ 判据必须**扫全量**，不能只挑几个漂亮样本。
    # =======================================================================
    print()
    print('== G. 五章全量扫描（真实房间 × 固定种子起终点）==')
    import random
    rnd = random.Random(20260925)

    def _room_rect_of(items):
        mx = max((r[0] + r[2] for r in items), default=0.0)
        my = max((r[1] + r[3] for r in items), default=0.0)
        return (0.0, 0.0, float(max(200, int((mx + 40) // 40 * 40))),
                float(max(160, int((my + 60) // 40 * 40))))

    g_scanned = g_skip = g_bad_pt = g_bad_seg = 0
    g_first = None
    for ch in (1, 2, 3, 4, 5):
        d = W.load_obstacles(ch, SCENES)
        if not d['ok']:
            continue
        for idx in sorted(d['rooms']):
            items = d['rooms'][idx]['items']
            if len(items) < 2:
                continue
            rr = _room_rect_of(items)
            pair = None
            for _ in range(60):
                a = (rnd.uniform(10, rr[2] - 10), rnd.uniform(10, rr[3] - 10))
                b = (rnd.uniform(10, rr[2] - 10), rnd.uniform(10, rr[3] - 10))
                if W.blocks_at(items, a[0], a[1]) or W.blocks_at(items, b[0], b[1]):
                    continue
                pair = (a, b)
                break
            if pair is None:
                continue
            for smooth in (False, True):
                r = W.plan_walk(ch, idx, rr, pair[0], pair[1],
                                obstacles=items, smooth=smooth)
                if not r['ok']:
                    g_skip += 1
                    continue
                g_scanned += 1
                pth = r['path']
                if any(W.blocks_at(items, q[0], q[1]) for q in pth):
                    g_bad_pt += 1
                    if g_first is None:
                        g_first = ('点', ch, idx, smooth)
                for k in range(len(pth) - 1):
                    if not W._segment_clear(items, pth[k][0], pth[k][1],
                                            pth[k + 1][0], pth[k + 1][1],
                                            W.PLAYER_BBOX_W, W.PLAYER_BBOX_H, W.GRID_STEP):
                        g_bad_seg += 1
                        if g_first is None:
                            g_first = ('段', ch, idx, smooth)
                        break
    check('G1 全量扫描样本量 >= 300（证明判据真跑了）', g_scanned >= 300,
          'got=%d' % g_scanned)
    check('G2 ★★ 全量扫描：无任何航点穿模', g_bad_pt == 0,
          '穿模=%d/%d 首例=%s' % (g_bad_pt, g_scanned, g_first))
    check('G3 ★★ 全量扫描：无任何相邻连线穿模', g_bad_seg == 0,
          '穿模=%d/%d 首例=%s' % (g_bad_seg, g_scanned, g_first))
    print('   [INFO] 可规划=%d  走不到(如实报)=%d' % (g_scanned, g_skip))

    # -----------------------------------------------------------------------
    #  G4 ★★ 深度判据：**已知脆弱房间**的固定起终点对（钉死不放过）
    #
    #  为什么必须有 G4（而不是只靠 G 段的随机扫描）：
    #    鉴别力体检实测——把 `simplify_collinear` 的 obstacles 校验去掉
    #    （即回到"按共线性删点"的旧 bug），五章 2376 组里**仍有 2 段穿模**，
    #    但 G 段"每间房 1 组"的 714 个样本**恰好没命中** ⇒ 判据漏报。
    #    G4 把这些"曾出过事"的房间钉死，保证同类退化**必然**被抓。
    #
    #  这 5 组来自第 45 轮的全量定位（见 _evidence/ 里的扫描记录）：
    #    ch1#24 flowershop_1f 末段    · ch1#28 torielclass 首段
    #    ch2#40 flowershop_1f 首段    · ch3#41 lw_computer_lab 首段
    #    ch5#64 dw_castle_rooms_susie 首段
    # -----------------------------------------------------------------------
    print()
    print('== G4. 已知脆弱房间（固定起终点对）==')
    G4_CASES = [
        (1, 24, (0.0, 0.0, 360.0, 280.0), (342.9593, 214.6431), (36.5768, 134.6669)),
        (1, 28, (0.0, 0.0, 320.0, 280.0), (140.6171, 45.6653), (300.4267, 83.9294)),
        (2, 40, (0.0, 0.0, 360.0, 280.0), (65.1556, 140.1722), (172.7423, 75.6185)),
        (3, 41, (0.0, 0.0, 320.0, 280.0), (288.1304, 210.8694), (140.4759, 255.0843)),
        (5, 64, (0.0, 0.0, 600.0, 520.0), (303.71, 457.58), (567.64, 51.4)),
    ]
    g4_ok = 0
    for ch, idx, rr, a, b in G4_CASES:
        ob = W.room_obstacles(ch, idx, SCENES)
        for smooth in (False, True):
            r = W.plan_walk(ch, idx, rr, a, b, obstacles=ob, smooth=smooth)
            tag = 'ch%d#%d smooth=%s' % (ch, idx, smooth)
            if not r['ok']:
                check('G4 %s 能规划' % tag, False, 'reason=%s' % r.get('reason'))
                continue
            pth = r['path']
            badpt = None
            for i, q in enumerate(pth):
                if W.blocks_at(ob, q[0], q[1]):
                    badpt = (i, q)
                    break
            check('G4 %s 无航点穿模' % tag, badpt is None, '穿模点=%s' % (badpt,))
            badseg = None
            for i in range(len(pth) - 1):
                if not W._segment_clear(ob, pth[i][0], pth[i][1],
                                        pth[i + 1][0], pth[i + 1][1],
                                        W.PLAYER_BBOX_W, W.PLAYER_BBOX_H, W.GRID_STEP):
                    badseg = (i, pth[i], pth[i + 1])
                    break
            check('G4 %s 无相邻段穿模' % tag, badseg is None, '穿模段=%s' % (badseg,))
            g4_ok += 1
    check('G4z 已知脆弱房间全部覆盖（>=10 次规划）', g4_ok >= 10, 'got=%d' % g4_ok)

    print()
    print('=== RESULT: PASS=%d FAIL=%d ===' % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
