# -*- coding: utf-8 -*-
"""第44轮续 · 速查本（MEMORY.md）逐令牌回验。

判据：本轮速查本新增/压缩时，凡"下沉到详版"的令牌，必须能在详版里 `in` 到。
宽式匹配（§ 可选），避免"判据太窄"的误报（§41 教训）。
"""
import io
import os

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
QS = os.path.join(ROOT, '.workbuddy', 'memory', 'MEMORY.md')
XS = os.path.join(ROOT, '.workbuddy', 'memory', '参考-契约与历轮（详版）.md')

qs = io.open(QS, encoding='utf-8').read()
xs = io.open(XS, encoding='utf-8').read()


def js(t):
    return len(t.strip().encode('utf-16-le')) // 2


# 本轮从速查本移除/压缩的令牌（应仍能在详版找到）
# ⚠️ 用"实际存在于详版的形态"作判据，别用我脑补的措辞（否则判据太窄→误报）
DROPPED = [
    'measure_token_ratio.py',
    'progress',
    'Q4 78/87',
    'obj_mainchara_Step_2',
    '_room_order',
    '_room_graph',
    '各 2 次',
    'Assets 层',
    '黑幕',
    '契约',
    'utmost',  # 负控制：不存在 ⇒ 应报 MISS
]

print('=' * 70)
print('速查本 js_len = %d / 10000' % js(qs))
print('=' * 70)
print('逐令牌回验（移除的令牌应在详版仍在）：')
miss = []
for t in DROPPED:
    hit = t in xs
    print('  [%s] %-40s' % ('OK  ' if hit else 'MISS', t))
    if not hit:
        miss.append(t)

print()
print('missing = %d' % len(miss))
if miss:
    print('  ⚠️ 需确认以下令牌是否真的丢了（可能语义已被覆盖）：')
    for m in miss:
        print('     -', m)

# 关键判据令牌必须**仍在速查本**（不许被压丢）
MUST_KEEP = [
    '10000', 'utf-16-le', 'Global\\RalseiPetMutex', 'HERMETIC_IDS',
    "print('[PASS] %s')", 'SCENE_LAYER_ENABLED', 'scene_scale',
    '_room_geometry', 'routes_order44', '45.9', '§45', '1818',
]
print()
print('关键令牌必须仍在速查本：')
miss2 = []
for t in MUST_KEEP:
    hit = t in qs
    print('  [%s] %-32s' % ('OK  ' if hit else 'MISS', t))
    if not hit:
        miss2.append(t)
print()
print('关键令牌 missing = %d' % len(miss2))
