# -*- coding: utf-8 -*-
"""第51轮诊断：`A3b` 的那 1 对劣化是**本轮改动引入**的，还是**本来就存在**的？

做法：用 `git show HEAD:...` 取出本轮改动前的 `scene_walk.py`，与工作区版本
在**同一批夹具**上并排跑 `A3b`（逐对比较可见硬拐角），看劣化对数。

★ 判据纪律：本脚本自带"结果可信度"自检 ——
  ① 两版本源码必须**确实不同**（否则是同一份代码自比）；
  ② 输出 pre51 与 now 两套劣化对，逐对可核对。
"""
import importlib.util
import io
import json
import math
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MOD = os.path.join(PET, 'modules', 'scene_walk.py')
SCENES = os.path.join(PET, 'assets', 'scenes')

HARD_DEG = 80.0
MIN_LEG = 5.0


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


def hard_detail(path):
    out = []
    for i in range(1, len(path) - 1):
        a, b, c = path[i - 1], path[i], path[i + 1]
        l1 = math.hypot(b[0] - a[0], b[1] - a[1])
        l2 = math.hypot(c[0] - b[0], c[1] - b[1])
        if l1 < MIN_LEG or l2 < MIN_LEG:
            continue
        t = turn_deg(a, b, c)
        if t >= HARD_DEG:
            out.append((i, round(t, 1), round(l1, 1), round(l2, 1)))
    return out


def build_samples(W):
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


def run(ver, W, samples, tag):
    worse = []
    n_ok = 0
    hard_now = hard_raw = 0
    for ch, idx, rect, s, t, obs in samples:
        raw = W.plan_walk(ch, idx, rect, s, t, obstacles=obs, smooth=False)
        now = W.plan_walk(ch, idx, rect, s, t, obstacles=obs)
        if not (raw.get('ok') and now.get('ok')):
            continue
        if len(now['path']) < 3 or len(raw['path']) < 3:
            continue
        n_ok += 1
        hn, hr = visible_hard(now['path']), visible_hard(raw['path'])
        hard_now += hn
        hard_raw += hr
        if hn > hr:
            worse.append((ch, idx, hr, hn, hard_detail(now['path'])))
    print('[%s] n_ok=%d  可见硬拐角 raw合计=%d now合计=%d  劣化 %d 对'
          % (tag, n_ok, hard_raw, hard_now, len(worse)))
    for w in worse:
        print('    ch%d:%d  raw=%d now=%d  now硬拐角明细=%r'
              % (w[0], w[1], w[2], w[3], w[4]))
    return worse


def main():
    src_now = io.open(MOD, 'r', encoding='utf-8').read()
    src_pre = subprocess.run(['git', 'show', 'HEAD:ralsei_pet/modules/scene_walk.py'],
                             cwd=ROOT, capture_output=True).stdout.decode('utf-8')
    print('自检① 两版本源码确实不同：', src_now != src_pre,
          '（now %d 行 / pre51 %d 行）' % (src_now.count('\n'), src_pre.count('\n')))
    fd, tmp = tempfile.mkstemp(suffix='_pre51.py')
    with io.open(fd, 'w', encoding='utf-8') as f:
        f.write(src_pre)
    try:
        Wpre = load(tmp, 'walk_pre51')
        Wnow = load(MOD, 'walk_now51')
        s_pre = build_samples(Wpre)
        s_now = build_samples(Wnow)
        print('夹具组数：pre51=%d  now=%d  同构=%s'
              % (len(s_pre), len(s_now), len(s_pre) == len(s_now)))
        print()
        w_pre = run(Wpre, Wpre, s_pre, 'pre51(HEAD)')
        print()
        w_now = run(Wnow, Wnow, s_now, 'now(工作区)')
        print()
        print('=== 结论 ===')
        print('本轮改动引入的劣化对：%r'
              % [x[:4] for x in w_now if x[:4] not in [y[:4] for y in w_pre]])
        print('本轮改动消除的劣化对：%r'
              % [x[:4] for x in w_pre if x[:4] not in [y[:4] for y in w_now]])
    finally:
        os.unlink(tmp)
    return 0


if __name__ == '__main__':
    sys.exit(main())
