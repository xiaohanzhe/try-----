# -*- coding: utf-8 -*-
"""第51轮 · 真机巡行 —— 用**真实产品代码路径**把场景系统全量跑一遍。

用户口径（第51轮逐字）：
    「你先开始运行程序，自己动手测一下到底能不能从桌面到其他地方
      （所有room，当然，不包括第3章）还有ralsei是否可以寻路，是否穿模，
      是否出现room显示不稳定等」「别看只看后台，要巡行程序」

「巡行」在沙箱里的可落地形式
---------------------------
GUI 的鼠标操作在本环境做不了（无屏幕自动化桌面端），但**被测对象不是鼠标**，
而是"场景系统这套真实代码能不能把 827 个房间正确地加载 / 渲染 / 连通 / 行走"。
所以本脚本**不 import Qt、不重写任何算法**，直接调用产品模块的真函数：

    scene_system.load_index / load_scene / load_worlds / world_of_scene
    scene_camera.Camera
    scene_render.plan_frame / plan_viewport / split_bubble_layers
    scene_pathfind.load_room_graph / build_adjacency / shortest_path /
                    resolve_target / plan_from_text
    scene_walk.load_obstacles / room_obstacles / plan_walk / blocks_at
    scene_routing（路由表）

⇒ 它跑出来的结论就是"产品在真机上会怎么表现"，不是另一个模拟器的结论。

六段判据（每段都**先打真实计数**，再看结论 —— 防"过宽/过窄"两头的假判据）
----------------------------------------------------------------------------
A  场景加载：827 个场景（= 1014 − ch3 187）逐个真加载
B  渲染稳定：每场景出 2 次同 tick 计划（比一致性）+ 跨 tick 比（验动效真的在动）
C  拓扑连通：原作门的图连通性（章内弱连通分量 / 从入口 BFS）
D  目的地定位：`resolve_target` 对别名表全部词条 + 场景名尾段
E  房间内行走：`plan_walk` 逐段回验是否穿障碍（穿模 = 事故）
F  接线：AST 扫 main.py，看这些能力**有没有产品调用方**（最贵的坑）

输出：控制台摘要 + `_evidence/patrol51.json`（机器可读，供报告引用）。
"""
import io
import json
import math
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, PET)
_MOD = os.path.join(PET, 'modules')
if _MOD not in sys.path:
    sys.path.append(_MOD)          # 与 main.py 完全同一条 sys.path 处理

import scene_system as SS          # noqa: E402
import scene_render as SR          # noqa: E402
import scene_camera as SC          # noqa: E402
import scene_pathfind as SP        # noqa: E402
import scene_walk as SW            # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

EXCLUDE = ('ch3',)                 # 用户口径：不包括第 3 章
MAIN_PY = os.path.join(PET, 'src', 'main.py')
EVID = os.path.join(ROUND, '_evidence')
REPORT = {'meta': {}, 'A': {}, 'B': {}, 'C': {}, 'D': {}, 'E': {}, 'F': {}}


def sec(t):
    print('\n' + '=' * 74)
    print(t)
    print('=' * 74)


def err(e):
    return '%s: %s' % (type(e).__name__, e)


# ===========================================================================
#  载入（真调用）
# ===========================================================================
T0 = time.time()
idx = SS.load_index()
scenes = idx.get('scenes') or {}
geo_all = {}
try:
    _raw = SS._read_json(os.path.join(SS.scenes_dir(), '_room_geometry.json')) or {}
    geo_all = _raw.get('rooms') or {}
except Exception:
    geo_all = {}

sec('0 基线')
print('仓库根        : %s' % ROOT)
print('scenes_dir()  : %s' % SS.scenes_dir())
print('索引 ok=%s  schema=%s  default_scene=%r'
      % (idx.get('ok'), idx.get('schema_version'), idx.get('default_scene')))
print('场景总数      : %d' % len(scenes))
print('房间几何表    : %d 条' % len(geo_all))
by_ch = {}
for sid, e in scenes.items():
    by_ch.setdefault(e.get('chapter_id'), []).append(sid)
print('分章          : %s' % {k: len(v) for k, v in sorted(by_ch.items())})
REPORT['meta'] = {
    'scenes_dir': SS.scenes_dir(), 'n_scenes': len(scenes),
    'default_scene': idx.get('default_scene'),
    'geo_rooms': len(geo_all),
    'by_chapter': {k: len(v) for k, v in sorted(by_ch.items())},
    'exclude': list(EXCLUDE),
}
# 桌面场景的登记行（用户问"从桌面到其他地方"，先看它有什么）
_desk = scenes.get('desktop') or {}
print('desktop 登记行: %s' % json.dumps(
    {k: _desk.get(k) for k in ('scene_id', 'chapter_id', 'area_id',
                               'original_room_id', 'name', 'bg')},
    ensure_ascii=False))
REPORT['meta']['desktop_entry'] = {k: _desk.get(k) for k in (
    'scene_id', 'chapter_id', 'area_id', 'original_room_id', 'name', 'bg')}

# ===========================================================================
#  A 场景加载
# ===========================================================================
sec('A 场景加载（真实 load_scene）')
A = {'n': 0, 'ok': 0, 'fail': [], 'no_roomid': [], 'no_bg': [],
     'no_objects': 0, 'world_none': [], 'objects_total': 0}
worlds = SS.load_worlds()
print('_worlds.json ok=%s rooms=%d overrides=%d'
      % (worlds.get('ok'), len(worlds.get('rooms') or {}),
         len(worlds.get('overrides') or {})))
t = time.time()
for ch in sorted(by_ch):
    if ch in EXCLUDE:
        continue
    for sid in sorted(by_ch[ch]):
        A['n'] += 1
        entry = scenes[sid]
        try:
            sc = SS.load_scene(sid, entry=entry)
        except Exception as e:
            A['fail'].append([sid, err(e)])
            continue
        if sc is None:
            A['fail'].append([sid, 'load_scene 返回 None'])
            continue
        A['ok'] += 1
        if not isinstance(getattr(sc, 'original_room_id', None), int):
            A['no_roomid'].append(sid)
        if not getattr(sc, 'bg', None):
            A['no_bg'].append(sid)
        objs = getattr(sc, 'objects', None) or []
        A['objects_total'] += len(objs)
        if not objs:
            A['no_objects'] += 1
        if SS.world_of_scene(sc, worlds) is None:
            A['world_none'].append(sid)
A['seconds'] = round(time.time() - t, 2)
print('加载 %d 个场景，成功 %d，失败 %d（%.2fs）'
      % (A['n'], A['ok'], len(A['fail']), A['seconds']))
if A['fail']:
    print('  失败样例: %s' % A['fail'][:5])
print('无 original_room_id : %d %s' % (len(A['no_roomid']), A['no_roomid'][:5]))
print('无 bg（走占位斜纹）  : %d / %d' % (len(A['no_bg']), A['n']))
print('无可视物件          : %d / %d（物件实例合计 %d）'
      % (A['no_objects'], A['n'], A['objects_total']))
print('判不出明/暗世界      : %d %s' % (len(A['world_none']), A['world_none'][:5]))
REPORT['A'] = A

# ===========================================================================
#  B 渲染稳定性
# ===========================================================================
sec('B 渲染稳定性（真 Camera + 真 geometry + plan_frame）')
B = {'n': 0, 'exc': [], 'unstable': [], 'empty_plan': [], 'bad_view': [],
     'placeholder': 0, 'n_bg': 0, 'anim_scenes': 0, 'anim_moved': 0,
     'tick_same_scenes': 0}
SCALE = 2.0                      # 现实世界 320×240 ×2（记忆 §7）；暗世界 640×480
for ch in sorted(by_ch):
    if ch in EXCLUDE:
        continue
    for sid in sorted(by_ch[ch]):
        entry = scenes[sid]
        sc = SS.load_scene(sid, entry=entry)
        if sc is None:
            continue
        B['n'] += 1
        try:
            rid = getattr(sc, 'original_room_id', None)
            rec = geo_all.get('%s:%d' % (ch, rid)) if isinstance(rid, int) else None
            if isinstance(rec, dict) and isinstance(rec.get('w'), int):
                room_rect = (0.0, 0.0, float(rec['w']), float(rec['h']))
            else:
                room_rect = (0.0, 0.0, 640.0, 480.0)
            cam = SC.Camera(SC.DEFAULT_CAMERA_SIZE, SC.DEFAULT_BORDER, SCALE)
            # 目标 = 角色（19×38）站在房间左上偏内的位置
            tx = room_rect[0] + min(50.0, max(1.0, room_rect[2] / 2.0))
            ty = room_rect[1] + min(50.0, max(1.0, room_rect[3] / 2.0))
            cam.follow(room_rect, (tx, ty, tx + 19, ty + 38))
            p1 = SR.plan_frame(sc, cam, geo_all, tick=1000)
            p2 = SR.plan_frame(sc, cam, geo_all, tick=1000)
            view = SR.plan_viewport(sc, cam, geo_all)
            if not (isinstance(p1, list) and isinstance(p2, list)):
                B['unstable'].append([sid, 'plan 不是 list'])
                continue
            if p1 != p2:
                B['unstable'].append([sid, '同 tick 两次计划不同'])
            if not p1:
                B['empty_plan'].append(sid)
            if not (isinstance(view, (list, tuple)) and len(view) == 2
                    and view[0] > 0 and view[1] > 0):
                B['bad_view'].append([sid, view])
            kinds = [it.get('kind') for it in p1]
            if SR.K_BG in kinds:
                B['n_bg'] += 1
            if SR.K_PLACEHOLDER in kinds:
                B['placeholder'] += 1
            # 动效：该场景有无多帧物件；有则跨 tick 必须换帧
            anims = [it for it in p1 if isinstance(it.get('anim_frames'), int)
                     and it['anim_frames'] > 1]
            if anims:
                B['anim_scenes'] += 1
                pa = SR.plan_frame(sc, cam, geo_all, tick=0)
                pb = SR.plan_frame(sc, cam, geo_all, tick=100000)
                fa = [it.get('anim_frame') for it in pa
                      if isinstance(it.get('anim_frames'), int)]
                fb = [it.get('anim_frame') for it in pb
                      if isinstance(it.get('anim_frames'), int)]
                if fa != fb:
                    B['anim_moved'] += 1
        except Exception as e:
            B['exc'].append([sid, err(e)])
print('渲染 %d 个场景：异常 %d，同 tick 不稳定 %d，空计划 %d，视口非法 %d'
      % (B['n'], len(B['exc']), len(B['unstable']), len(B['empty_plan']),
         len(B['bad_view'])))
if B['exc']:
    print('  异常样例: %s' % B['exc'][:5])
if B['unstable']:
    print('  不稳定样例: %s' % B['unstable'][:5])
if B['bad_view']:
    print('  视口非法样例: %s' % B['bad_view'][:5])
print('真背景 %d / 占位斜纹 %d' % (B['n_bg'], B['placeholder']))
print('含多帧物件的场景 %d，其中跨 tick 换帧 %d（应全部换帧）'
      % (B['anim_scenes'], B['anim_moved']))
print('空计划场景（前 8）: %s' % B['empty_plan'][:8])
REPORT['B'] = B

# ===========================================================================
#  C 拓扑连通（回答"能不能从桌面到各 room"）
# ===========================================================================
sec('C 原作拓扑连通（room graph）')
C = {'graph_ok': None, 'edges': {}, 'per_chapter': {}}
g = SP.load_room_graph()
print('房间图 ok=%s 路径=%s' % (g.get('ok'), SP.room_graph_path()))
C['graph_ok'] = bool(g.get('ok'))
edges_by_ch = g.get('edges_by_chapter') or {}
C['edges'] = {k: len(v) for k, v in edges_by_ch.items()}
print('各章边数: %s' % C['edges'])

# 每章：房间集合（来自索引） + 弱连通分量 + 从入口 BFS
for ch in sorted(by_ch):
    if ch in EXCLUDE:
        continue
    rooms = {}
    for sid in by_ch[ch]:
        rid = scenes[sid].get('original_room_id')
        if isinstance(rid, int) and rid not in rooms:
            rooms[rid] = sid
    edges = edges_by_ch.get(ch) or []
    adj = SP.build_adjacency({ch: edges}).get(ch) or {}
    # 弱连通（无向）
    und = {}
    for e in edges:
        und.setdefault(e['src'], set()).add(e['dst'])
        und.setdefault(e['dst'], set()).add(e['src'])
    seen, comps = set(), []
    for r in sorted(set(list(rooms) + list(und))):
        if r in seen:
            continue
        stack, comp = [r], set()
        while stack:
            n = stack.pop()
            if n in comp:
                continue
            comp.add(n)
            stack.extend(und.get(n, ()))
        seen |= comp
        comps.append(comp)
    comps.sort(key=len, reverse=True)
    # 入口房间 = 最大分量里**下标最小**且登记为场景的 room
    main_comp = comps[0] if comps else set()
    entry = None
    for r in sorted(main_comp):
        if r in rooms:
            entry = r
            break
    reached = set()
    if entry is not None:
        stack = [entry]
        while stack:
            n = stack.pop()
            if n in reached:
                continue
            reached.add(n)
            for e in adj.get(n) or []:
                stack.append(e['dst'])
    unreach = sorted(set(main_comp) - reached)
    C['per_chapter'][ch] = {
        'n_rooms_in_index': len(rooms),
        'n_nodes_in_graph': len(und),
        'components': [len(c) for c in comps[:8]],
        'entry_room': entry,
        'entry_scene': rooms.get(entry),
        'reached_from_entry': len(reached),
        'unreachable_from_entry': unreach[:20],
        'n_unreachable_from_entry': len(unreach),
    }
    pc = C['per_chapter'][ch]
    print('%-4s 索引房间 %3d / 图节点 %3d / 弱连通分量 %s'
          % (ch, pc['n_rooms_in_index'], pc['n_nodes_in_graph'],
             pc['components']))
    print('     入口 room=%s(%s) → 可达 %d 间，走不到 %d 间 %s'
          % (pc['entry_room'], pc['entry_scene'], pc['reached_from_entry'],
             pc['n_unreachable_from_entry'], pc['unreachable_from_entry'][:8]))

# 从桌面出发（用户的原问题）
desk_room = _desk.get('original_room_id')
desk_ch = _desk.get('chapter_id')
print('桌面 original_room_id=%r chapter=%r ⇒ 桌面是**独立前置章**，'
      '原作门图里没有它的节点' % (desk_room, desk_ch))
print('  ⇒ 「从桌面走到 ch1 某房间」这条链在产品里**跨章**：'
      '`plan_from_text` 明确不支持（见 scene_pathfind）')
C['desktop_crosschapter'] = {
    'desktop_room': desk_room if isinstance(desk_room, int) else None,
    'desktop_chapter': desk_ch,
    'cross_chapter_supported': False,
}
REPORT['C'] = C

# ===========================================================================
#  D 目的地定位（"Ralsei 能不能寻路"里的 ②）
# ===========================================================================
sec('D 目的地定位 resolve_target（别名表 + 场景名）')
D = {'n_alias': 0, 'alias_ok': 0, 'alias_fail': [], 'ambiguous': [],
     'name_ok': 0, 'name_fail': [], 'n_name': 0}
al = SP.load_aliases()
ents = al.get('entries') or {}
print('别名表 ok=%s 词条 %d' % (al.get('ok'), len(ents)))
D['n_alias'] = len(ents)
for zh in sorted(ents):
    rv = SP.resolve_target(zh, idx)
    if rv.get('ok') and not rv.get('ambiguous'):
        D['alias_ok'] += 1
    elif rv.get('ambiguous'):
        D['ambiguous'].append([zh, len(rv.get('candidates') or [])])
        D['alias_ok'] += 1          # 多解也算"认得这个词"
    else:
        D['alias_fail'].append([zh, rv.get('error')])
print('别名词条识别: %d/%d 命中（多解 %d，完全不认 %d）'
      % (D['alias_ok'], D['n_alias'], len(D['ambiguous']), len(D['alias_fail'])))
if D['alias_fail']:
    print('  不认的: %s' % D['alias_fail'][:10])
if D['ambiguous']:
    print('  多解的: %s' % D['ambiguous'][:10])

# 场景名尾段（抽样：每章前 6 个）
for ch in sorted(by_ch):
    if ch in EXCLUDE:
        continue
    for sid in sorted(by_ch[ch])[:6]:
        nm = (scenes[sid].get('name') or '')
        tail = nm.rsplit('·', 1)[-1] if '·' in nm else nm
        if not tail:
            continue
        D['n_name'] += 1
        rv = SP.resolve_target(tail, idx, current_chapter=ch)
        if rv.get('ok') and rv.get('scene_id'):
            D['name_ok'] += 1
        else:
            D['name_fail'].append([ch, sid, tail,
                                   rv.get('error') or 'ambiguous'])
print('场景名尾段定位: %d/%d 唯一命中' % (D['name_ok'], D['n_name']))
if D['name_fail']:
    print('  未唯一命中样例: %s' % D['name_fail'][:8])

# 端到端：从一章入口场景出发，plan_from_text 到该章另一个场景
e2e = []
for ch in sorted(by_ch):
    if ch in EXCLUDE:
        continue
    pc = C['per_chapter'].get(ch) or {}
    start_sid = pc.get('entry_scene')
    if not start_sid:
        continue
    cand = [s for s in sorted(by_ch[ch]) if s != start_sid]
    for goal_sid in cand[:3]:
        nm = scenes[goal_sid].get('name') or ''
        tail = nm.rsplit('·', 1)[-1] if '·' in nm else nm
        pl = SP.plan_from_text(tail, idx, g, ents, current_scene_id=start_sid)
        e2e.append([ch, start_sid, goal_sid, bool(pl.get('ok')),
                    pl.get('hops'), pl.get('error')])
ok_e2e = sum(1 for r in e2e if r[3])
print('端到端 plan_from_text 抽样 %d 例，成功 %d 例' % (len(e2e), ok_e2e))
for r in e2e[:12]:
    print('   %-4s %s → %s ok=%s hops=%s %s'
          % (r[0], r[1], r[2], r[3], r[4], (r[5] or '')[:60]))
D['e2e'] = e2e
D['e2e_ok'] = ok_e2e
REPORT['D'] = D

# ===========================================================================
#  E 房间内行走（穿模 = 事故）
# ===========================================================================
sec('E 房间内行走 plan_walk（逐段回验是否穿障碍）')
E = {'n_rooms': 0, 'n_pairs': 0, 'walk_ok': 0, 'walk_fail': [],
     'penetrate': [], 'no_obstacles_rooms': 0, 'chapters': {}}
MAX_PAIRS = 8            # 每房间最多 8 组点对（控制耗时）
CAND = 6                 # 候选点网格边长
for ch in sorted(by_ch):
    if ch in EXCLUDE:
        continue
    # ⚠️ 障碍表按 `_obstacles.ch<数字>.json` 命名 ⇒ 没有数字章节的场景（`desktop`）
    #    **没有障碍表**，直接跳过（本轮首跑就是在这里 int('sktop') 崩的）。
    if not ch[2:].isdigit():
        continue
    num = int(ch[2:])
    obs = SW.load_obstacles(num)
    E['chapters'][ch] = {'rooms_with_obs': len(obs.get('rooms') or {}),
                         'pairs': 0, 'walk_ok': 0, 'walk_fail': 0,
                         'penetrate': 0}
    if not obs.get('ok'):
        print('%-4s 障碍表不可用: %s' % (ch, obs.get('error')))
        continue
    for rid_s, rec in sorted((obs.get('rooms') or {}).items(),
                             key=lambda kv: int(kv[0])):
        rid = int(rid_s)
        items = rec.get('items') or []
        if not items:
            E['no_obstacles_rooms'] += 1
            continue
        geo = geo_all.get('%s:%d' % (ch, rid))
        if not (isinstance(geo, dict) and isinstance(geo.get('w'), int)):
            continue
        w, h = int(geo['w']), int(geo['h'])
        room_rect = (0.0, 0.0, float(w), float(h))
        E['n_rooms'] += 1
        # 取候选可走点（锚点 = sprite 左上；bbox 偏移 y+25）
        cand = []
        for iy in range(CAND):
            for ix in range(CAND):
                x = 20.0 + (w - 40.0) * ix / float(max(1, CAND - 1))
                y = 20.0 + (h - 40.0) * iy / float(max(1, CAND - 1))
                if not SW.blocks_at(items, x, y):
                    cand.append((x, y))
        pairs = 0
        for i in range(len(cand)):
            if pairs >= MAX_PAIRS:
                break
            for j in range(i + 1, len(cand)):
                if pairs >= MAX_PAIRS:
                    break
                a, b = cand[i], cand[j]
                if math.hypot(b[0] - a[0], b[1] - a[1]) < 60:
                    continue
                pairs += 1
                res = SW.plan_walk(num, rid, room_rect, a, b, obstacles=items)
                E['n_pairs'] += 1
                E['chapters'][ch]['pairs'] += 1
                if not res.get('ok'):
                    E['walk_fail'].append([ch, rid, a, b, res.get('reason')])
                    E['chapters'][ch]['walk_fail'] += 1
                    continue
                E['walk_ok'] += 1
                E['chapters'][ch]['walk_ok'] += 1
                # ★ 独立回验（不用产品的 _segment_clear，自己密集采样）
                path = res.get('path') or []
                hit = None
                for k in range(len(path) - 1):
                    x0, y0 = path[k]
                    x1, y1 = path[k + 1]
                    d = math.hypot(x1 - x0, y1 - y0)
                    n = max(1, int(d / 0.5))       # 每 0.5px 采一点（★独立采样族，
                    #   与产品里的解析判定（Liang-Barsky）**不同实现** ⇒ 交叉验证；
                    #   产品判据若恒真，这里就会报出穿模）
                    for q in range(n + 1):
                        tt = q / float(n)
                        if SW.blocks_at(items, x0 + (x1 - x0) * tt,
                                        y0 + (y1 - y0) * tt):
                            hit = (k, path[k], path[k + 1])
                            break
                    if hit:
                        break
                if hit:
                    E['penetrate'].append([ch, rid, a, b, hit])
                    E['chapters'][ch]['penetrate'] += 1
print('有障碍的房间 %d 间，点对 %d 组：plan_walk 成功 %d，失败 %d，**穿模 %d**'
      % (E['n_rooms'], E['n_pairs'], E['walk_ok'], len(E['walk_fail']),
         len(E['penetrate'])))
print('无障碍房间（跳过）%d' % E['no_obstacles_rooms'])
if E['walk_fail']:
    print('  走不到样例: %s' % E['walk_fail'][:5])
if E['penetrate']:
    print('  ★穿模样例: %s' % E['penetrate'][:5])
for ch, d in sorted(E['chapters'].items()):
    print('   %-4s 有障碍房 %3d / 点对 %4d / ok %4d / 失败 %2d / 穿模 %d'
          % (ch, d['rooms_with_obs'], d['pairs'], d['walk_ok'],
             d['walk_fail'], d['penetrate']))
REPORT['E'] = E

# ===========================================================================
#  F 接线（最贵的坑：函数写对了但产品用不上）
# ===========================================================================
sec('F 接线检查（AST 扫 main.py）')
F = {}
import ast  # noqa: E402
try:
    src = io.open(MAIN_PY, 'r', encoding='utf-8').read()
    tree = ast.parse(src)
except Exception as e:
    src, tree = '', None
    F['error'] = err(e)

# 收集 main.py 里所有被**调用**的名字（含属性链尾）
called = set()
for node in ast.walk(tree) if tree else []:
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Name):
            called.add(f.id)
        elif isinstance(f, ast.Attribute):
            called.add(f.attr)
# 收集 main.py 里 import 的模块名
imports = set()
for node in ast.walk(tree) if tree else []:
    if isinstance(node, ast.Import):
        for a in node.names:
            imports.add((a.asname or a.name).split('.')[0])
    elif isinstance(node, ast.ImportFrom):
        for a in node.names:
            imports.add(a.asname or a.name)

WANT = ['plan_walk', 'scene_walk', 'follow_route', 'pick_route',
        'resolve_destination', 'plan_route_to', 'destinations',
        'load_pathfind_data', 'route_goal', 'enter_door', 'door',
        'toggle_bubble', 'equip', 'unequip']
print('main.py 行数 %d' % (src.count('\n') + 1))
for w in WANT:
    in_import = w in imports
    in_call = w in called
    in_text = w in src
    F[w] = {'import': in_import, 'called': in_call, 'text': in_text}
    print('  %-20s import=%-5s 调用=%-5s 文本出现=%-5s'
          % (w, in_import, in_call, in_text))
# 关键判断
wired = [w for w in ('plan_walk',) if F[w]['called'] or F[w]['import']]
F['walk_wired'] = bool(wired)
F['route_wired'] = bool(F['follow_route']['called'] or
                        F['pick_route']['called'])
F['pathfind_wired'] = bool(F['plan_route_to']['called'] or
                           F['resolve_destination']['called'])
print('⇒ 房间内行走（plan_walk/scene_walk）被产品调用: %s' % F['walk_wired'])
print('⇒ 路由执行（follow_route/pick_route）被产品调用: %s' % F['route_wired'])
print('⇒ 寻路规划（plan_route_to/resolve_destination）被产品调用: %s'
      % F['pathfind_wired'])
REPORT['F'] = F

# ===========================================================================
out = os.path.join(EVID, 'patrol51.json')
os.makedirs(EVID, exist_ok=True)
with io.open(out, 'w', encoding='utf-8', newline='\n') as fh:
    json.dump(REPORT, fh, ensure_ascii=False, indent=1)
sec('完成')
print('总耗时 %.1fs，证据落盘: %s' % (time.time() - T0, out))
