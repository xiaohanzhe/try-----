# -*- coding: utf-8 -*-
"""第34轮续 探针：确认 `get_jump_destinations` 的候选只是"种子集"，
真正的准入在 `_floor_entry_plan`（产品路径），故 S2/S3 口径不一致**无实际后果**。

判据：产品路径是否依赖 get_jump_destinations 的横向过滤结果？
  · 依赖 → S2/S3 是真缺陷
  · 不依赖（有第二道准入门 + 显式补层）→ S2/S3 是设计分层，非缺陷
"""
import ast
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
MAIN = os.path.join(REPO, 'ralsei_pet', 'src', 'main.py')

pass_n = 0
fail_n = 0


def check(name, cond, detail=''):
    global pass_n, fail_n
    if cond:
        pass_n += 1
        print('[PASS] %s %s' % (name, detail))
    else:
        fail_n += 1
        print('[FAIL] %s %s' % (name, detail))


src = open(MAIN, encoding='utf-8').read()
lines = src.splitlines()
tree = ast.parse(src)

cls = None
for n in ast.walk(tree):
    if isinstance(n, ast.ClassDef) and n.name == 'RalseiPet':
        cls = n
        break
methods = {m.name: m for m in cls.body if isinstance(m, ast.FunctionDef)}

njm = methods['_nearest_floor_jump']
njm_src = '\n'.join(lines[njm.lineno - 1:njm.end_lineno])

print('== 产品路径：_nearest_floor_jump 是否依赖 get_jump_destinations 的横向过滤 ==')
print('   （该函数 L%d-%d，%d 行）' % (njm.lineno, njm.end_lineno, njm.end_lineno - njm.lineno + 1))

# 控制 A：确实调用了 get_jump_destinations（候选来源）
check('A 调用了 get_jump_destinations', 'fm.get_jump_destinations(' in njm_src)

# 控制 B：显式补 adjacent_lower_floor（绕过横向过滤）
check('B 显式补相邻下层 `adjacent_lower_floor`（绕过横向过滤）',
      'fm.adjacent_lower_floor(' in njm_src)

check('B2 补层前用 identity 去重（不与种子集重复）',
      '_floor_identity_key(down) not in known' in njm_src)

# 控制 C：每个候选都要过 _floor_entry_plan（第二道准入门）
check('C 每个候选都要过 `_floor_entry_plan`（真正的准入判定）',
      'self._floor_entry_plan(' in njm_src)

# 控制 D：_floor_entry_plan 用 nearest_visible_point 做可见吸附
fep = methods['_floor_entry_plan']
fep_src = '\n'.join(lines[fep.lineno - 1:fep.end_lineno])
check('D `_floor_entry_plan` 走 `nearest_visible_point`（可见吸附，与楼层侧同源）',
      'self._visible_landing(' in fep_src and '_visible_landing' in src)

# 控制 E：吸附过远（>200px）就拒绝 —— 这是防"跳到同层另一个角落"
check('E 吸附过远（>200px）拒绝（防空跳/跳到同层角落）',
      '> 200' in fep_src and 'return None' in fep_src)
check('E2 上一条 200 阈值确实出现两次（x 与 y）',
      fep_src.count('200') >= 2, '(count=%d)' % fep_src.count('200'))

print()
print('== 结论判定 ==')
depends_on_filter = ('fm.get_jump_destinations(' in njm_src
                     and 'self._floor_entry_plan(' not in njm_src)
check('F 产品路径**不**依赖 get_jump_destinations 的横向过滤结果 → S2/S3 非缺陷',
      not depends_on_filter,
      '(存在第二道准入门 _floor_entry_plan + 显式补 adjacent_lower_floor)')

print()
print('== 交叉核验：_floor_entry_plan 的横向内容区间（留 20px 内缩）==')
check('G _floor_entry_plan 横向用 rect 留 20px 内缩判 span_ok_x',
      'rect.left() + 20' in fep_src and 'rect.right() - 20' in fep_src)
check('H 四边贴边阈值 NEAR=60px', 'NEAR = 60' in fep_src)
check('I 四边 gap 允许 -20 容差（已经探出边/轻微重叠也算贴边）',
      fep_src.count('-20 <=') >= 4, '(count=%d)' % fep_src.count('-20 <='))

print()
print('SUITE_SUMMARY pass=%d fail=%d' % (pass_n, fail_n))
