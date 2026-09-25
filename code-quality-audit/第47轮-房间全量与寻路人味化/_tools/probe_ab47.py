# -*- coding: utf-8 -*-
"""第47轮探针③：**真 A/B** —— 改前版 vs 工作区版 `scene_walk`。

为什么不用"我记得改前是 74 对"
------------------------------
改前改后必须是**同一时刻、同一夹具**跑出来的两个实现，否则"变好了"无法归因。
A 版 = 仓库内冻结快照 `_evidence/_scene_walk_HEAD47.py`
（= 改前 `git show HEAD:ralsei_pet/modules/scene_walk.py` 落盘，sha1 记录在证据里），
B 版 = 工作区文件，用**同一批真实房间/起终点**跑，逐对比较。

两个硬指标（"像不像机器人"的可观测量）
------------------------------------
· `visible_hard`：**可见硬拐角**数 —— 转角 ≥ 80° **且两条腿都 ≥ 5px**
  （腿太短的算"亚像素抖动"，人眼看不见，不计入；否则会把噪声当缺陷）。
· `max_regress`：**最深回溯距离**（px）—— 沿原折线的弧长"往回走"的最大值。
  真人走路不会倒回去；> 一个格步（10px）就是画面上能看见的抽动。
"""
import importlib.util
import io
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
#: ★ A 版 = **仓库内冻结快照**（改前 `git show HEAD:` 落盘，与 B 段负控制共用一份）。
#: ❗不要改成读 `git show HEAD` —— 一旦本轮提交，HEAD 前移，A/B 会变成"新版比新版"，
#:   对照静默失效（且 `E:\Download\_tmp` 是"用后即删"区，回归判据不许依赖它）。
SNAP = os.path.join(HERE, '..', '_evidence', '_scene_walk_HEAD47.py')

HARD = 80.0
MIN_LEG = 5.0


def load_from(path, name):
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
        if turn_deg(a, b, c) >= HARD:
            n += 1
    return n


def max_regress(W, path, ref):
    """沿参考折线 `ref` 的弧长，路径最多往回走多少 px。"""
    if len(path) < 2 or len(ref) < 2:
        return 0.0
    worst = 0.0
    prev = W._arc_pos(path[0], ref)
    for p in path[1:]:
        cur = W._arc_pos(p, ref)
        worst = max(worst, prev - cur)
        prev = cur
    return worst


def main():
    snap = os.path.abspath(SNAP)
    if not os.path.isfile(snap):
        print('缺少改前快照：%s' % snap)
        return 1
    A = load_from(snap, 'walk_head47')
    B = load_from(os.path.join(ROOT, 'ralsei_pet', 'modules', 'scene_walk.py'), 'walk_work47')
    print('A 版 = 改前快照（%d 字节）  B 版 = 工作区（%d 字节）'
          % (os.path.getsize(snap), os.path.getsize(os.path.join(ROOT, 'ralsei_pet', 'modules', 'scene_walk.py'))))

    geo = json.load(io.open(os.path.join(SCENES, '_room_geometry.json'),
                            'r', encoding='utf-8')).get('rooms') or {}
    pairs = []
    for ch in (1, 2, 4, 5):
        d = A.load_obstacles(ch, SCENES)
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
                    if not A.blocks_at(obs, x, y):
                        pts.append((x, y))
            far = None
            for a_ in range(len(pts)):
                for b_ in range(a_ + 1, len(pts)):
                    dd = math.hypot(pts[b_][0] - pts[a_][0], pts[b_][1] - pts[a_][1])
                    if far is None or dd > far[0]:
                        far = (dd, pts[a_], pts[b_])
            if far is None:
                continue
            pairs.append((ch, idx, rect, far[1], far[2], obs))

    aggs = {}
    rh = {}
    better = worse = same = 0
    reg_better = reg_worse = 0
    worstB = None
    worse_pairs = []          # ★ 逐对"B 反而比 A 多硬拐角"的样例（如实列出，不藏）
    for tag, M in (('A', A), ('B', B)):
        hh = rr = 0
        for ch, idx, rect, s, t, obs in pairs:
            r = M.plan_walk(ch, idx, rect, s, t, obstacles=obs)
            if not r.get('ok') or len(r.get('path') or []) < 3:
                continue
            raw = M.plan_walk(ch, idx, rect, s, t, obstacles=obs, smooth=False)
            if raw.get('ok'):
                rh[tag] = rh.get(tag, 0) + visible_hard(raw['path'])
            hh += visible_hard(r['path'])
            if raw.get('ok') and len(raw['path']) >= 2:
                rr = max(rr, max_regress(M, r['path'], raw['path']))
        aggs[tag] = (hh, rr)

    # 逐对比较（都平滑）
    for ch, idx, rect, s, t, obs in pairs:
        ra = A.plan_walk(ch, idx, rect, s, t, obstacles=obs)
        rb = B.plan_walk(ch, idx, rect, s, t, obstacles=obs)
        if not (ra.get('ok') and rb.get('ok')) or len(ra['path']) < 3 or len(rb['path']) < 3:
            continue
        # 用各自的原折线（smooth=False）当参考，衡量"平滑把路带偏多少"
        refa = A.plan_walk(ch, idx, rect, s, t, obstacles=obs, smooth=False)['path']
        refb = B.plan_walk(ch, idx, rect, s, t, obstacles=obs, smooth=False)['path']
        ha, hb = visible_hard(ra['path']), visible_hard(rb['path'])
        ga, gb = max_regress(A, ra['path'], refa), max_regress(B, rb['path'], refb)
        if hb < ha:
            better += 1
        elif hb > ha:
            worse += 1
            raw_a = visible_hard(refa)
            raw_b = visible_hard(refb)
            worse_pairs.append((ch, idx, ha, hb, raw_a, raw_b, len(ra['path']), len(rb['path'])))
        else:
            same += 1
        if gb < ga - 0.5:
            reg_better += 1
        elif gb > ga + 0.5:
            reg_worse += 1
        if worstB is None or gb > worstB[0]:
            worstB = (gb, ch, idx, ga)

    print('')
    print('      平滑后可见硬拐角 / 原折线可见硬拐角')
    print('A 版（HEAD）：%d / %d   最深回溯=%.1fpx' % (aggs['A'][0], rh.get('A', 0), aggs['A'][1]))
    print('B 版（工作区）：%d / %d   最深回溯=%.1fpx' % (aggs['B'][0], rh.get('B', 0), aggs['B'][1]))
    print('')
    print('逐对（可见硬拐角）：B 更少 %d / 相同 %d / ★更多 %d' % (better, same, worse))
    print('逐对（最深回溯）  ：B 更浅 %d / ★更深 %d' % (reg_better, reg_worse))
    if worstB:
        print('B 版最深回溯的一例：%.1fpx（A 版同例 %.1fpx）ch%d 房%d'
              % (worstB[0], worstB[3], worstB[1], worstB[2]))
    if worse_pairs:
        print('')
        print('★ 逐对"B 比 A 更差"的 %d 例（ch 房  A拐角→B拐角  [各自原折线拐角]  航点数）：'
              % len(worse_pairs))
        for ch, idx, ha, hb, ra_, rb_, na, nb in worse_pairs:
            flag = '★劣于原折线' if hb > rb_ else '仍不劣于原折线'
            print('  ch%d 房%-4d  %d→%d  [%d / %d]  %d→%d 点  %s'
                  % (ch, idx, ha, hb, ra_, rb_, na, nb, flag))

    dest = os.path.join(HERE, '..', '_evidence', 'AB对照_平滑47.txt')
    with io.open(dest, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('第47轮 A/B 对照：改前快照 vs 工作区 scene_walk\n')
        fh.write('配对样本 %d\n' % len(pairs))
        fh.write('A(HEAD) 可见硬拐角=%d 最深回溯=%.1fpx\n' % aggs['A'])
        fh.write('B(工作区) 可见硬拐角=%d 最深回溯=%.1fpx\n' % aggs['B'])
        fh.write('逐对硬拐角 B更少=%d 相同=%d 更多=%d\n' % (better, same, worse))
        fh.write('逐对回溯 B更浅=%d 更深=%d\n' % (reg_better, reg_worse))
        if worstB:
            fh.write('B 最深回溯=%.1fpx ch%d#%d（A 同例 %.1fpx）\n' % worstB)
        if worse_pairs:
            fh.write('\n★ 逐对"B 比 A 更差"的 %d 例'
                     '（ch 房  A拐角→B拐角  [各自原折线拐角]  航点数）：\n' % len(worse_pairs))
            for ch, idx, ha, hb, ra_, rb_, na, nb in worse_pairs:
                flag = '★劣于原折线' if hb > rb_ else '仍不劣于原折线'
                fh.write('  ch%d 房%-4d  %d→%d  [%d / %d]  %d→%d 点  %s\n'
                         % (ch, idx, ha, hb, ra_, rb_, na, nb, flag))
    return 0


if __name__ == '__main__':
    sys.exit(main())
