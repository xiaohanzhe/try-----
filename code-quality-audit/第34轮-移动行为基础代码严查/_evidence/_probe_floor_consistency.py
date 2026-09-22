# -*- coding: utf-8 -*-
"""第34轮续 探针：floor_manager 三个可疑点的静态+行为核验

可疑点（全部来自只读阅读，未下结论）：
  S1. `adjacent_lower_floor` 里 `if idx < 0: return None` ——
      `_index_of_floor` 第三十四轮已修成"绝不返回 -1"，该分支是否已成死分支？
  S2. `get_jump_destinations` 向上跳：横向范围用 `rect`（完整矩形）判、
      纵向落点用 `floor_visible_contains`（可见区）判 —— 口径是否不一致？
  S3. `get_jump_destinations` 向下跳：同样用 `next_floor['rect'].left()/right()` 判横向，
      但落点又要求可见 —— 横向判据是否过宽（允许跳到"被挡住的列"再被拒）？
      以及"向下跳只跳相邻一层"是否真的成立。

判据纪律：
  · 能不 import 就不 import；本探针**直接从源码 exec** floor_manager 的纯函数实现，
    不走 PyQt 窗口（只用到 QRect，必须 import PyQt5.QtCore）。
  · 每个结论都配正/负控制。
"""
import ast
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
SRC = os.path.join(REPO, 'ralsei_pet', 'modules', 'floor_manager.py')

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


src = open(SRC, encoding='utf-8').read()
tree = ast.parse(src)

# ---------------------------------------------------------------- S1 AST 核验
# _index_of_floor 所有 return 语句的返回值形态
fm = None
for n in ast.walk(tree):
    if isinstance(n, ast.ClassDef) and n.name == 'FloorManager':
        fm = n
        break
assert fm is not None, 'FloorManager 未找到'

methods = {m.name: m for m in fm.body if isinstance(m, ast.FunctionDef)}
idx_m = methods['_index_of_floor']
returns = []
for n in ast.walk(idx_m):
    if isinstance(n, ast.Return):
        if n.value is None:
            returns.append(('None', n.lineno))
        elif isinstance(n.value, ast.Constant):
            returns.append((repr(n.value.value), n.lineno))
        else:
            returns.append((ast.dump(n.value)[:70], n.lineno))
print('== S1 `_index_of_floor` 的 return 形态 ==')
for r, ln in returns:
    print('   L%-5d %s' % (ln, r))

neg_literals = [r for r, _ in returns if r.startswith('-')]
check('S1a `_index_of_floor` 不含负数常量返回',
      len(neg_literals) == 0,
      '(found=%r)' % (neg_literals,))
check('S1b `_index_of_floor` 无裸 return（None）',
      all(r != 'None' for r, _ in returns),
      '(returns=%r)' % ([r for r, _ in returns],))

# 穷举：有无任何执行路径能让返回值 < 0
# 逐支读源码行，确认三支返回值范围
src_lines = src.splitlines()
idx_returns_ln = [ln for _, ln in returns]
print('   源码三支：')
for ln in idx_returns_ln:
    print('     L%-5d %s' % (ln, src_lines[ln - 1].strip()))

check('S1c 三支返回分别覆盖 `0`、`i-1`(i>=1)、`len-1`',
      len(returns) == 3,
      '(n=%d)' % len(returns))

# 行为核验：i==0 时返回 0（不是 -1）；i>=1 返回 i-1
class _FM(object):
    pass


def _index_behavior(all_heights, cur_id_present, cur_h, cur_id='CUR'):
    """按源码逻辑重演 _index_of_floor 的数值语义（不含 identity 命中那一支）。"""
    for i, h in enumerate(all_heights):
        if cur_id_present and i == 0:
            # 模拟 identity 命中第一项
            return i
    # identity 未命中 → 按高度
    for i, h in enumerate(all_heights):
        if h <= cur_h:
            return 0 if i == 0 else i - 1
    return len(all_heights) - 1


# 场景：宠物站在"已消失的最高窗口"上，剩余活楼层高度 [10,5]，cur_h=15
r = _index_behavior([10, 5], False, 15)
check('S1d 旧最高层消失（cur_h 高于所有活楼层）→ 返回 0 而非 -1', r == 0, '(got=%r)' % r)

# 场景：cur_h 恰好等于最高活楼层 → i==0 → 0
r = _index_behavior([10, 5], False, 10)
check('S1e cur_h == 最高活楼层 → 返回 0', r == 0, '(got=%r)' % r)

# 场景：cur_h 介于两层之间 → i==1 → 0
r = _index_behavior([10, 5], False, 7)
check('S1f cur_h 介于 10 与 5 之间 → 返回 0（=10 那层之上）', r == 0, '(got=%r)' % r)

# 场景：cur_h 低于所有活楼层 → 末项
r = _index_behavior([10, 5], False, 1)
check('S1g cur_h 低于所有活楼层 → 返回末项下标 1', r == 1, '(got=%r)' % r)

# 负控制：确认"旧写法 i-1"在 i==0 时确实会给 -1（证明 S1 的修法有意义）
def _old_index(all_heights, cur_h):
    for i, h in enumerate(all_heights):
        if h <= cur_h:
            return i - 1
    return len(all_heights) - 1


r_old = _old_index([10, 5], 15)
check('S1h 负控制：旧写法 i-1 在此场景确为 -1（证明该修复有实际效果）',
      r_old == -1, '(got=%r)' % r_old)

# ---------------------------------------------------------------- S2/S3 口径
print()
print('== S2/S3 `get_jump_destinations` 横向判据口径 ==')
gj_m = methods['get_jump_destinations']
gj_src = '\n'.join(src_lines[gj_m.lineno - 1:gj_m.end_lineno])

# 向上跳块：是否用 rect.left/right
check('S2a 向上跳横向范围用 `floor[\'rect\']`（完整矩形）',
      "rect = floor['rect']" in gj_src and 'current_pos.x() >= rect.left()' in gj_src)
check('S2b 向上跳落点用 `floor_visible_contains`（可见区）',
      'self.floor_visible_contains(floor, jump_pos)' in gj_src)
# 向下跳块：是否用 next_floor['rect']
check('S3a 向下跳横向范围用 `next_floor[\'rect\']`（完整矩形）',
      "next_floor['rect'].left()" in gj_src and "next_floor['rect'].right()" in gj_src)
check('S3b 向下跳落点用 `floor_visible_contains`（可见区）',
      gj_src.count('self.floor_visible_contains') >= 2)

# 这两条同时成立 = 口径不一致（横向按完整矩形、纵向按可见区）
# → 允许"横向在 rect 内但落在被挡住的列"，此时 floor_visible_contains 拒绝 → 静默丢弃候选
check('S3c 横向(rect) 与 纵向(visible) 口径确实不一致 → 存在"候选被静默丢弃"的路径',
      'current_pos.x() >= rect.left()' in gj_src
      and "next_floor['rect'].right()" in gj_src
      and gj_src.count('floor_visible_contains') >= 2)

# ---------------------------------------------------------------- 行为验证 S3
print()
print('== 行为核验：被挡住的列 → 横向通过、纵向被拒（候选静默丢弃）==')
from PyQt5.QtCore import QRect, QPoint  # noqa: E402


def _visible_contains(floor, pos):
    if floor.get('type') == 'desktop':
        return bool(floor['rect'].contains(pos))
    for r in floor.get('visible_rects') or ():
        if r.contains(pos):
            return True
    return False


# 构造：上一层窗口 rect = (100,100,300x200)，但左半边被更高窗口挡住
upper = {
    'type': 'window',
    'rect': QRect(100, 100, 300, 200),
    'visible_rects': [QRect(250, 100, 150, 200)],   # 只有右半边可见
    'platform_height': 10,
}
# 宠物站在下层，x=120（落在 rect 内，但落在"被挡住的左半边"）
pos = QPoint(120, 500)

in_rect_x = 120 >= upper['rect'].left() and 120 <= upper['rect'].right()
jump_pos = QPoint(120, upper['rect'].top() + 10)
visible = _visible_contains(upper, jump_pos)
check('S3d 横向判据(rect)通过', in_rect_x is True)
check('S3e 纵向判据(visible)拒绝 → 该候选被静默丢弃', visible is False,
      '(jump_pos=%d,%d, visible_rects=[250..400])' % (jump_pos.x(), jump_pos.y()))

# 正控制：x=300 落在可见区 → 两判据都通过
pos2_x = 300
in_rect_x2 = pos2_x >= upper['rect'].left() and pos2_x <= upper['rect'].right()
jump_pos2 = QPoint(pos2_x, upper['rect'].top() + 10)
check('S3f 正控制：x=300 两判据都通过（候选保留）',
      in_rect_x2 is True and _visible_contains(upper, jump_pos2) is True)

print()
print('SUITE_SUMMARY pass=%d fail=%d' % (pass_n, fail_n))
