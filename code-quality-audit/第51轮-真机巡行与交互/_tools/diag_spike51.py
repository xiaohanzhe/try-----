# -*- coding: utf-8 -*-
"""第51轮 · 尖刺漏删检验 —— `walk_round47` 那 1 对「劣化」到底是不是正当的。

第51轮把 `_segment_clear` 改成解析判定后，`walk_round47` 报：
    A3b 可见硬拐角逐对不劣于原折线 ⇒ 劣化 **1 对**：(ch1, room105, 原 1 → 平滑 2)
    INFO 硬拐角总数 355 → **122**（改前 107），A4/A5（逐点/逐段不穿模）仍 PASS

两种可能，必须分清（纪律：**先问夹具真把破坏写进去了吗，再怀疑判据**）：
  ① **正当**：严格判据后"抄近路会穿墙"，尖刺**必须**保留 ⇒ 该改判据（太强）
  ② **产品错**：`_despike` 留下了"削了也不穿墙"的尖刺 ⇒ 该改产品

本脚本直接给出判决：对全量样本里**每一个尖刺点** b（`turn >= 45°` 且 `detour > 1`），
用 `_despike` 自己的判据问一句"删掉 b（a→c 直连）会不会穿墙"：
  · 会穿墙 ⇒ `must_keep`（正当保留）
  · 不会穿墙 ⇒ `sprayable`（**可削却没削 = `_despike` 漏删**，必须为 0）
"""
import io
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
sys.path.insert(0, PET)
_MOD = os.path.join(PET, 'modules')
if _MOD not in sys.path:
    sys.path.append(_MOD)

import scene_system as SS      # noqa: E402
import scene_walk as SW        # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

geo_raw = SS._read_json(os.path.join(SS.scenes_dir(), '_room_geometry.json')) or {}
GEO = geo_raw.get('rooms') or {}

CAND, MAX_PAIRS = 6, 8
MIN_TURN = SW.DESPIKE_MIN_TURN
n_ok = 0
sprayable = []
must_keep = 0


def clear(obs, a, c):
    return SW._segment_clear(obs, a[0], a[1], c[0], c[1],
                             SW.PLAYER_BBOX_W, SW.PLAYER_BBOX_H, SW.GRID_STEP)


for ch in ('ch1', 'ch2', 'ch4', 'ch5'):
    num = int(ch[2:])
    obs_all = SW.load_obstacles(num)
    if not obs_all.get('ok'):
        continue
    for rid_s, rec in sorted((obs_all.get('rooms') or {}).items(),
                             key=lambda kv: int(kv[0])):
        rid = int(rid_s)
        items = rec.get('items') or []
        if not items:
            continue
        geo = GEO.get('%s:%d' % (ch, rid))
        if not (isinstance(geo, dict) and isinstance(geo.get('w'), int)):
            continue
        w, h = int(geo['w']), int(geo['h'])
        rect = (0.0, 0.0, float(w), float(h))
        cand = []
        for iy in range(CAND):
            for ix in range(CAND):
                x = 20.0 + (w - 40.0) * ix / float(CAND - 1)
                y = 20.0 + (h - 40.0) * iy / float(CAND - 1)
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
                r = SW.plan_walk(num, rid, rect, a, b, obstacles=items)
                if not r.get('ok') or len(r['path']) < 3:
                    continue
                # ★ 关键对照：若 smooth=False 与默认的 path **逐点相同**，
                #   说明走了 `smooth_keep_walkable` 的 `bailed` 兜底
                #   （阶段 2 段级回退失败 ⇒ 整条退回原折线，**跳过** monotone/despike）
                #   ⇒ 这时候"残留尖刺"是设计律 3「宁可不平滑，不可穿墙」的合法结果。
                r_raw = SW.plan_walk(num, rid, rect, a, b, obstacles=items,
                                     smooth=False)
                bailed = bool(r_raw.get('ok')
                              and r_raw['path'] == r['path'])
                n_ok += 1
                p = r['path']
                for k in range(1, len(p) - 1):
                    a1, b1, c1 = p[k - 1], p[k], p[k + 1]
                    turn = SW._turn_deg(a1, b1, c1)
                    detour = (math.hypot(b1[0] - a1[0], b1[1] - a1[1])
                              + math.hypot(c1[0] - b1[0], c1[1] - b1[1])
                              - math.hypot(c1[0] - a1[0], c1[1] - a1[1]))
                    if turn < MIN_TURN or detour <= 1.0:
                        continue
                    if clear(items, a1, c1):
                        # ★ 削了不穿墙 ⇒ 本该被 `_despike` 删掉
                        sprayable.append([ch, rid, k, round(turn, 1),
                                          round(detour, 1), bailed,
                                          [round(v, 1) for v in a1],
                                          [round(v, 1) for v in b1],
                                          [round(v, 1) for v in c1]])
                    else:
                        must_keep += 1

n_bailed = sum(1 for s in sprayable if s[5])
print('样本 %d 组；尖刺点判定：' % n_ok)
print('  削了会穿墙 ⇒ **正当保留**  : %d' % must_keep)
print('  削了不穿墙 ⇒ 可削却没削     : %d' % len(sprayable))
print('    其中来自 **bailed 兜底**  : %d（设计律 3：宁可不平滑，不可穿墙）'
      % n_bailed)
print('    ★其中**真平滑过却没削**   : %d（这才是产品问题，必须为 0）'
      % (len(sprayable) - n_bailed))
if sprayable:
    print('  样例（前 6）：')
    for s in sprayable[:6]:
        print('   ', s)
out = os.path.join(ROUND, '_evidence', 'spike51.json')
os.makedirs(os.path.dirname(out), exist_ok=True)
with io.open(out, 'w', encoding='utf-8', newline='\n') as fh:
    json.dump({'n_samples': n_ok, 'must_keep': must_keep,
               'sprayable': sprayable}, fh, ensure_ascii=False, indent=1)
print('落盘: %s' % out)
sys.exit(1 if sprayable else 0)
