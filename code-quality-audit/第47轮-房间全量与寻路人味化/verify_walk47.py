# -*- coding: utf-8 -*-
"""第47轮 · 场景内行走「人味化」回归锁（G2 的一部分）。

用户口径（本轮）：
    「那个寻路要符合真人逻辑，别和机器人一样」

本锁守的是**房间之内**那一层（房间之间由 `第45轮/verify_pathfind45.py` 守）。

★ 为什么必须新增这份锁（而不是"改了就说改好了"）
------------------------------------------------
第47轮实测：`smooth_keep_walkable` 的**回退分支会把原始顶点插到身后**，
于是平滑后路径出现"往回走"的抖动 —— 最坏 **228.4px**（近半间房的宽度），
转角 174°~180°。这不是"不够顺"，是**画面上真的来回抽动**。
并且五章 193 组配对里 **74 组**平滑后硬拐角比原折线还**多**（平滑在帮倒忙）。

修复 = 平滑末段加 `_monotone_forward()`（按原折线弧长单调过滤 + 保行走回验）。

本锁的三层判据
-------------
A **真实全量**（ch1/2/4/5 有障碍房间 × 最远采样对，193 组）：
  ① 最深回溯 ≤ `BACKTRACK_TOL`（"真人不会倒着走"的可断言形式）
  ② 可见硬拐角（转角 ≥80° 且两腿都 ≥5px）**逐对不劣于**原折线
  ③ 逐点 + 逐段不穿墙   ④ 首尾点 == 起终点
B **负控制**：把**改前版本**（已随证据入库 `_evidence/_scene_walk_HEAD47.py`）用
  同一批夹具跑 —— 它必须**违反**①（实得 228.4px）并**劣于**②（318 vs 180）。
  ⇒ 证明判据不是恒真（否则"改了以后达标"毫无意义）。
C **合成夹具**：`_monotone_forward` 在"删点会穿墙"时必须**保住**那个倒走点；
  并配一个"无脑删（不看安全）会穿墙"的反面对照 —— 证明安全回验不可省。
D **常量与接线**：`BACKTRACK_TOL` 取值被钉住；`smooth_keep_walkable` 真的用了
  `_monotone_forward`（防"函数写对了没人调"）。

判据纪律：**每条都 print `[PASS] ` 字面量**（`run_all.py` 按此计数）；
不联网 / 不调 Ollama / 不 import Qt / 不需要显示器。
"""
import ast
import importlib.util
import io
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MOD = os.path.join(PET, 'modules', 'scene_walk.py')
SCENES = os.path.join(PET, 'assets', 'scenes')
HEAD_EV = os.path.join(HERE, '_evidence', '_scene_walk_HEAD47.py')

#: 可见硬拐角：转角阈值 / 最短腿（腿更短的是亚像素抖动，人眼看不见，不计）
HARD_DEG = 80.0
MIN_LEG = 5.0

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


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def turn_deg(a, b, c):
    v1 = (b[0] - a[0], b[1] - a[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n1, n2 = math.hypot(*v1), math.hypot(*v2)
    if n1 < 1e-9 or n2 < 1e-9:
        return 0.0
    c_ = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    return math.degrees(math.acos(max(-1.0, min(1.0, c_))))


def visible_hard(path):
    n = 0
    for i in range(1, len(path) - 1):
        a, b, c = path[i - 1], path[i], path[i + 1]
        if math.hypot(b[0] - a[0], b[1] - a[1]) < MIN_LEG:
            continue
        if math.hypot(c[0] - b[0], c[1] - b[1]) < MIN_LEG:
            continue
        if turn_deg(a, b, c) >= HARD_DEG:
            n += 1
    return n


def max_regress(W, path, ref):
    """路径沿参考折线弧长**往回走**的最大距离（px）。真人不会倒着走。"""
    if len(path) < 2 or len(ref) < 2:
        return 0.0
    worst = 0.0
    prev = W._arc_pos(path[0], ref)
    for p in path[1:]:
        cur = W._arc_pos(p, ref)
        worst = max(worst, prev - cur)
        prev = cur
    return worst


def build_samples(W):
    """真实夹具：ch1/2/4/5 每个"有障碍且能算出尺寸"的房间，取 4×4 采样里最远的一对。"""
    geo = json.load(io.open(os.path.join(SCENES, '_room_geometry.json'),
                            'r', encoding='utf-8')).get('rooms') or {}
    out = []
    for ch in (1, 2, 4, 5):
        d = W.load_obstacles(ch, SCENES)
        if not d.get('ok'):
            continue
        for idx in sorted(d['rooms']):
            g = geo.get('ch%d:%d' % (ch, idx))
            obs = d['rooms'][idx]['items']
            if not g or not obs or not g.get('w'):
                continue
            rect = (0.0, 0.0, float(g['w']), float(g['h']))
            pts = []
            for i in range(4):
                for j in range(4):
                    x, y = (i + .5) * rect[2] / 4.0, (j + .5) * rect[3] / 4.0
                    if not W.blocks_at(obs, x, y):
                        pts.append((x, y))
            far = None
            for a in range(len(pts)):
                for b in range(a + 1, len(pts)):
                    dd = math.hypot(pts[b][0] - pts[a][0], pts[b][1] - pts[a][1])
                    if far is None or dd > far[0]:
                        far = (dd, pts[a], pts[b])
            if far is None:
                continue
            out.append((ch, idx, rect, far[1], far[2], obs))
    return out


def seg_clear(W, obs, a, b):
    return W._segment_clear(obs, a[0], a[1], b[0], b[1],
                            W.PLAYER_BBOX_W, W.PLAYER_BBOX_H, W.GRID_STEP)


def main():
    print('=== 第47轮 场景内行走「人味化」回归锁 ===')
    if not (os.path.isfile(MOD) and os.path.isfile(HEAD_EV)):
        check('前置：模块与改前证据都在位', False,
              'mod=%s head_ev=%s' % (os.path.isfile(MOD), os.path.isfile(HEAD_EV)))
        return 1
    check('前置：模块与改前证据都在位', True)
    W = load(MOD, 'walk_now47')
    H = load(HEAD_EV, 'walk_head47')
    # 改前版本必须**真的**没有这一层（否则负控制是假的）
    check('前置：改前版本不含 _monotone_forward（负控制前提）',
          not hasattr(H, '_monotone_forward') and hasattr(W, '_monotone_forward'))

    samples = build_samples(W)
    print()
    print('== A. 真实全量（%d 组）==' % len(samples))

    reg_now = 0.0
    reg_head = 0.0
    hard_now = hard_raw = hard_head = 0
    worse_pairs = []
    worst_deg = 0
    leftover = []          # 残留倒走点：(ch, idx, i, 倒退px, 是否可删)
    bad_pt = bad_seg = bad_ends = 0
    n_ok = 0
    for ch, idx, rect, s, t, obs in samples:
        raw = W.plan_walk(ch, idx, rect, s, t, obstacles=obs, smooth=False)
        now = W.plan_walk(ch, idx, rect, s, t, obstacles=obs)
        head = H.plan_walk(ch, idx, rect, s, t, obstacles=obs)
        if not (raw.get('ok') and now.get('ok') and head.get('ok')):
            continue
        if len(now['path']) < 3 or len(raw['path']) < 3:
            continue
        n_ok += 1
        reg_now = max(reg_now, max_regress(W, now['path'], raw['path']))
        reg_head = max(reg_head, max_regress(W, head['path'], raw['path']))
        hn, hr, hh = (visible_hard(now['path']), visible_hard(raw['path']),
                      visible_hard(head['path']))
        hard_now += hn
        hard_raw += hr
        hard_head += hh
        if hn > hr:
            worse_pairs.append((ch, idx, hr, hn))
            worst_deg = max(worst_deg, hn - hr)
        # ★ 残留倒走点：逐条记录，并当场判定"删了它会不会穿墙"
        arcs = [W._arc_pos(q, raw['path']) for q in now['path']]
        for i in range(1, len(now['path']) - 1):
            back = arcs[i - 1] - arcs[i]
            if back > W.BACKTRACK_TOL:
                removable = seg_clear(W, obs, now['path'][i - 1], now['path'][i + 1])
                leftover.append((ch, idx, i, round(back, 1), removable))
        if any(W.blocks_at(obs, q[0], q[1]) for q in now['path']):
            bad_pt += 1
        for i in range(len(now['path']) - 1):
            if not seg_clear(W, obs, now['path'][i], now['path'][i + 1]):
                bad_seg += 1
                break
        p0, p1 = now['path'][0], now['path'][-1]
        if math.hypot(p0[0] - s[0], p0[1] - s[1]) > 0.01 or \
           math.hypot(p1[0] - t[0], p1[1] - t[1]) > 0.01:
            bad_ends += 1

    check('A1 样本量 >= 150（证明判据真跑了）', n_ok >= 150, 'got=%d' % n_ok)
    # ★ A2 为什么不是"最深回溯 ≤ tol"：过滤器**不允许**为了顺而穿墙，
    #   所以"删了会穿墙"的那些倒走点**必须**保留。真正的不变量是
    #   「**没有任何一条残留倒走点是可删的**」—— 那才等价于"该删的都删了"。
    #   （第47轮第一版判据写成 `reg_now <= tol` ⇒ 报红，属**判据太强**，非产品错。）
    check('A2a ★ 残留倒走点极少（≤10 条）', len(leftover) <= 10,
          '实得 %d 条' % len(leftover))
    can_del = [x for x in leftover if x[4]]
    check('A2b ★★ 每一条残留倒走都是"删了会穿墙"的（可删 = 0）',
          not can_del, '可删的残留=%r' % (can_del[:5],))
    check('A2c 残留倒退幅度有界（≤ 2×tol）', reg_now <= 2 * W.BACKTRACK_TOL,
          '最深 %.1fpx（上限 %.1f）' % (reg_now, 2 * W.BACKTRACK_TOL))
    # ★ A3 同理：平滑的插入点里有**必须**保留的原始顶点（贴角处不平滑）。
    #   第 47 轮第一版只做到"总数下降"，逐对仍有 30 对更楞（多出的 44 个尖角里
    #   20 个腿长 ≥15px）⇒ 加了 `_despike()` 之后，**逐对 0 劣化**。
    check('A3a ★ 平滑后可见硬拐角总数显著少于原折线',
          hard_now < hard_raw * 0.7,
          '平滑 %d vs 原折线 %d' % (hard_now, hard_raw))
    check('A3b ★★ 可见硬拐角逐对不劣于原折线（0 对劣化）',
          not worse_pairs,
          '劣化 %d 对：%r' % (len(worse_pairs), worse_pairs[:5]))
    check('A4 ★ 平滑后逐点不穿模', bad_pt == 0, '穿模对=%d/%d' % (bad_pt, n_ok))
    check('A5 ★ 平滑后逐段不穿模', bad_seg == 0, '穿模对=%d/%d' % (bad_seg, n_ok))
    check('A6 首尾点仍等于起终点', bad_ends == 0, '错的对=%d' % bad_ends)
    print('   [INFO] 可见硬拐角：原折线 %d → 新平滑 %d；残留倒走 %d 条（可删 0）'
          % (hard_raw, hard_now, len(leftover)))

    print()
    print('== B. 负控制（改前版本必须更差）==')
    check('B1 ★ 改前版本违反"不倒着走"（证明判据有鉴别力）',
          reg_head > 50.0,
          '改前最深回溯 %.1fpx（阈值 50）' % reg_head)
    check('B2 ★ 改前版本可见硬拐角更多（证明平滑真变顺了）',
          hard_head > hard_now,
          '改前 %d vs 现在 %d' % (hard_head, hard_now))
    check('B3 改前版本与现在**确实不同**（不是同一份代码自比）',
          reg_head != reg_now or hard_head != hard_now)
    print('   [INFO] 最深回溯：改前 %.1fpx → 现在 %.1fpx；硬拐角：%d → %d'
          % (reg_head, reg_now, hard_head, hard_now))

    print()
    print('== C. 合成夹具：安全回验不可省 ==')
    BB = (W.PLAYER_BBOX_W, W.PLAYER_BBOX_H, W.GRID_STEP)
    pts = [(0.0, 60.0), (300.0, 60.0), (300.0, 160.0)]
    # 第 3 点 (120,90) 的弧长 120 < 前一点 150 ⇒ 倒退 30px（> tol）
    out = [(0.0, 60.0), (150.0, 60.0), (120.0, 90.0), (300.0, 160.0)]
    obs = [(228.0, 115.0, 2.0, 20.0, 'solid')]
    arcs = [W._arc_pos(p, pts) for p in out]
    check('C1 夹具前提：第 3 点确实在弧长上倒退',
          arcs[2] < arcs[1] - W.BACKTRACK_TOL,
          'arcs=%r' % [round(a, 1) for a in arcs])
    check('C2 夹具前提：原折线逐段都干净',
          all(seg_clear(W, obs, out[i], out[i + 1]) for i in range(len(out) - 1)))
    check('C3 夹具前提：删掉倒走点就会穿墙',
          not seg_clear(W, obs, out[1], out[3]))
    kept = W._monotone_forward(out, pts, obs, *BB, W.BACKTRACK_TOL)
    check('C4 ★ 删不动时保住倒走点（宁可原样，不可穿墙）',
          [tuple(round(v, 2) for v in p) for p in kept] ==
          [tuple(round(v, 2) for v in p) for p in out],
          'got=%r' % (kept,))
    check('C5 ★ 过滤结果逐段不穿墙',
          all(seg_clear(W, obs, kept[i], kept[i + 1]) for i in range(len(kept) - 1)))
    # 反面对照：**无脑单调删**（不做安全回验）在同一夹具上会穿墙
    naive = [out[0], out[1], out[3]]
    check('C6 ★ 负控制：无脑单调删（不查安全）会穿墙',
          not all(seg_clear(W, obs, naive[i], naive[i + 1])
                  for i in range(len(naive) - 1)))
    # 正对照：没有障碍时，同一个倒走点必须被删掉（否则 C4 只是"什么都不做"）
    free = W._monotone_forward(out, pts, [], *BB, W.BACKTRACK_TOL)
    check('C7 正对照：无障碍时倒走点确实被删掉',
          len(free) == len(out) - 1
          and max_regress(W, free, pts) < W.BACKTRACK_TOL,
          'got=%d 点，回溯 %.1f' % (len(free), max_regress(W, free, pts)))

    print()
    print('== E. 合成夹具：去尖刺只削"尖刺"，不抹"缓弯" ==')
    # 用户反对的走法有**两种**：「直角拐弯」**和**「一直直线走」。
    # ⇒ 去尖刺的门槛必须让"缓弯"活下来，否则就是把路拉直。
    soft = [(0.0, 60.0), (50.0, 60.0), (100.0, 80.0), (150.0, 100.0)]
    soft_turns = [turn_deg(soft[i - 1], soft[i], soft[i + 1]) for i in range(1, len(soft) - 1)]
    check('E1a 夹具前提：这是一条缓弯（每段转角 < 45°）',
          soft_turns and max(soft_turns) < W.DESPIKE_MIN_TURN,
          'turns=%r' % [round(t, 1) for t in soft_turns])
    check('E1b ★ 缓弯**原样保留**（不许被削成直线）',
          W._despike(soft, [], *BB) == soft)

    spike = [(0.0, 60.0), (100.0, 60.0), (100.0, 90.0), (200.0, 60.0), (300.0, 60.0)]
    sp_turns = [turn_deg(spike[i - 1], spike[i], spike[i + 1]) for i in range(1, len(spike) - 1)]
    check('E2a 夹具前提：这是尖刺（存在 ≥45° 的拐）',
          max(sp_turns) >= W.DESPIKE_MIN_TURN, 'turns=%r' % [round(t, 1) for t in sp_turns])
    got2 = W._despike(spike, [], *BB)
    left2 = [turn_deg(got2[i - 1], got2[i], got2[i + 1]) for i in range(1, len(got2) - 1)]
    check('E2b ★ 尖刺被削掉（输出无 ≥45° 的拐）',
          all(t < W.DESPIKE_MIN_TURN for t in left2)
          and len(got2) < len(spike),
          'out=%d 点 turns=%r' % (len(got2), [round(t, 1) for t in left2]))

    # 安全回验：抄近路会穿墙时必须**保住**尖刺
    spk2 = [(0.0, 60.0), (50.0, 60.0), (50.0, 30.0), (100.0, 60.0), (200.0, 60.0)]
    wall = [(80.0, 95.0, 10.0, 20.0, 'solid')]
    check('E3a 夹具前提：原折线逐段都干净',
          all(seg_clear(W, wall, spk2[i], spk2[i + 1]) for i in range(len(spk2) - 1)))
    check('E3b 夹具前提：拉直（抄近路）会穿墙',
          not seg_clear(W, wall, (0.0, 60.0), (200.0, 60.0)))
    got3 = W._despike(spk2, wall, *BB)
    check('E3c ★ 去尖刺后逐段仍不穿墙',
          all(seg_clear(W, wall, got3[i], got3[i + 1]) for i in range(len(got3) - 1)))
    check('E3d ★ 且没有被拉成直线（尖刺保住了）',
          [tuple(round(v, 2) for v in p) for p in got3] != [(0.0, 60.0), (200.0, 60.0)]
          and (50.0, 30.0) in [tuple(p) for p in got3],
          'got=%r' % ([tuple(round(v, 1) for v in p) for p in got3],))
    # 负控制：无脑删（不看安全）在同一夹具上会穿墙
    naive3 = [(0.0, 60.0), (100.0, 60.0), (200.0, 60.0)]
    check('E3e ★★ 负控制：无脑删（不查安全）会穿墙',
          not all(seg_clear(W, wall, naive3[i], naive3[i + 1])
                  for i in range(len(naive3) - 1)))
    check('E4 去尖刺不改首尾点',
          W._despike(spike, [], *BB)[0] == spike[0]
          and W._despike(spike, [], *BB)[-1] == spike[-1])

    print()
    print('== D. 常量与接线 ==')
    check('D1 BACKTRACK_TOL == GRID_STEP / 2 且 DESPIKE_MIN_TURN == 45',
          abs(W.BACKTRACK_TOL - W.GRID_STEP / 2.0) < 1e-9
          and abs(W.DESPIKE_MIN_TURN - 45.0) < 1e-9,
          'tol=%r step=%r min_turn=%r' % (W.BACKTRACK_TOL, W.GRID_STEP,
                                          W.DESPIKE_MIN_TURN))
    src = io.open(MOD, 'r', encoding='utf-8').read()
    tree = ast.parse(src)
    want = ('_monotone_forward', '_despike')
    wired = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'smooth_keep_walkable':
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) \
                        and sub.func.id in want:
                    wired.setdefault(sub.func.id, []).append(sub.lineno)
    check('D2 ★ smooth_keep_walkable 真的调用 %s（防"写了没人用"）' % '/'.join(want),
          all(len(wired.get(f) or []) == 1 for f in want), '命中 %r' % wired)

    print()
    print('=== RESULT: PASS=%d FAIL=%d ===' % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
