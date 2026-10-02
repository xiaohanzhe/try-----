# -*- coding: utf-8 -*-
"""B3 中间自检：pet_interaction 改造后是否可 import、映射表是否自洽。

注意：只读 + 纯函数调用，不启动 Qt。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet'))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import ast

# ① 语法
with open(os.path.join(ROOT, 'ralsei_pet', 'modules', 'pet_interaction.py'),
          'r', encoding='utf-8') as f:
    src = f.read()
try:
    ast.parse(src)
    print('[OK] ast.parse 通过')
except SyntaxError as e:
    print('[FAIL] 语法错误:', e)
    sys.exit(1)

from modules import pet_interaction as P
from modules import event_speech as E

print('[OK] import 成功')
print('BodyPart =', [b.value for b in P.BodyPart])
print('Gesture  =', [g.value for g in P.Gesture])

# ② 区域表覆盖：每个部位至少有一个区域
covered = set(p for p, *_ in P._REGIONS_PERCENT)
print('区域表覆盖部位 =', sorted(x.value for x in covered))
missing = set(P.BodyPart) - covered - {P.BodyPart.WHOLE_BODY}
print('未被任何区域覆盖 =', sorted(x.value for x in missing) or '（无）')

# ③ 映射表 key 必须在 EVENT_TIERS 里
all_kinds = set()
for part in P.BodyPart:
    for g in P.Gesture:
        k = P.kind_for(part, g)
        if k:
            all_kinds.add(k)
print()
print('kind_for 能产出的全部 kind（%d 个）:' % len(all_kinds))
print('   ', sorted(all_kinds))
not_reg = sorted(k for k in all_kinds if k not in E.EVENT_TIERS)
print('   ★ 未在 EVENT_TIERS 登记 =', not_reg or '（无 —— 全部已登记）')

# ④ RESPONSE_SPEC 的 key 必须被 kind_for 覆盖到
spec_keys = set(P.RESPONSE_SPEC)
unreachable = sorted(spec_keys - all_kinds)
print('   ★ RESPONSE_SPEC 里有但 kind_for 产不出的 =',
      unreachable or '（无）')

# ⑤ 逐条打印 (部位, 手势) → kind
print()
print('(部位, 手势) → kind 全表:')
for part in P.BodyPart:
    row = []
    for g in P.Gesture:
        k = P.kind_for(part, g)
        if k:
            row.append('%s=%s' % (g.value, k))
    print('  %-12s %s' % (part.value, ' '.join(row) or '（无回应）'))

# ⑥ 抚摸响应
print()
print('STROKE_EMOTIONS =', P.STROKE_EMOTIONS)
print('STROKE_POOL keys =', sorted(P.STROKE_POOL))
print('PET_PARTS =', E.PET_PARTS)
bad = [k for k in P.STROKE_POOL if k not in E.PET_PARTS]
print('   ★ STROKE_POOL 里不在 PET_PARTS 的 =', bad or '（无）')
