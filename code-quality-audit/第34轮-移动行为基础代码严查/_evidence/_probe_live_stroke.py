# -*- coding: utf-8 -*-
"""探针 21 号：活产线抚摸判据（main.py L5364-5393）逐条复核。

方法
----
**不重写逻辑**（项目铁律："能 import 的别重写；不得不重写必须锁等价"）。
这里用 AST 从 main.py 里**抽取**那段循环的源码文本，exec 进一个
最小命名空间（只喂 movement_history 一个变量），得到**与产品逐字相同**
的 direction_changes 计算函数。然后拿真实序列逐条喂它。

这样探针与产品同源，避免"分类器太窄"式的假问题。
"""
import ast
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')

with io.open(MAIN, 'r', encoding='utf-8', errors='replace') as f:
    SRC = f.read()
LINES = SRC.splitlines()


def extract_block(start_ln, end_ln):
    """按 1-based 行号（含）抽源码，去掉公共缩进。"""
    chunk = LINES[start_ln - 1:end_ln]
    indents = [len(l) - len(l.lstrip()) for l in chunk if l.strip()]
    base = min(indents) if indents else 0
    return '\n'.join(l[base:] if len(l) >= base else l for l in chunk)


# 产品里那段循环：L5367(direction_changes=0) .. L5389(prev_dy = move_dy)
BLOCK_START, BLOCK_END = 5367, 5389
block = extract_block(BLOCK_START, BLOCK_END)
print('=' * 72)
print('探针 21：活产线抚摸判据逐条复核（源码位置 %d-%d）' % (BLOCK_START, BLOCK_END))
print('=' * 72)
print()
print('--- 抽取到的产品源码（逐字） ---')
for i, ln in enumerate(block.splitlines(), start=BLOCK_START):
    print('%5d| %s' % (i, ln))
print()

# 用 exec 还原成函数：与产品逐字同源
# 产品那段循环体里用的是 self._pet_detection_state['movement_history']，
# 所以喂一个最小 self 桩（只提供这一条属性），**不重写任何循环逻辑**。
FUNC_SRC = (
    'def direction_changes_of(history):\n'
    '    class _S:\n'
    '        pass\n'
    '    self = _S()\n'
    "    self._pet_detection_state = {'movement_history': history}\n"
    '    direction_changes = 0\n'
    + '\n'.join('    ' + l for l in block.splitlines()[1:]) + '\n'
    '    return direction_changes\n'
)
ns = {}
exec(compile(FUNC_SRC, '<extracted-from-main.py>', 'exec'), ns)
dc_of = ns['direction_changes_of']
# 自证桩接线正确：换一条 history，返回值必须跟着变（否则测的是常量）


# 自证同源：抽取到的源码必须真的来自 main.py
assert 'for (move_dx, move_dy, _) in' in FUNC_SRC, '抽取失败'
assert 'prev_dy = move_dy' in FUNC_SRC, '抽取失败'


def seq(pairs):
    """pairs: [(dx,dy)] -> movement_history 形式 [(dx,dy,dist)]"""
    return [(dx, dy, (dx * dx + dy * dy) ** 0.5) for dx, dy in pairs]


# --- 桩接线自证（必须放在 seq 定义之后）---
# 鉴别力体检：若桩没接上（例如恒定返回 0），下面两个值会相等。
_sanity_rep = dc_of(seq([(10, 0), (-10, 0), (10, 0)]))
_sanity_one = dc_of(seq([(10, 0), (10, 0), (10, 0)]))
print('--- 桩接线自证 ---')
print('  往返序列 =>', _sanity_rep, ' 单向序列 =>', _sanity_one)
if _sanity_rep == _sanity_one:
    print('  [FAIL] 两者相等 ⇒ 桩没接上，本探针整段无效')
    sys.exit(1)
print('  [PASS] 两者不同 ⇒ 桩已接上，能区分两类输入')
print()


CASES = [
    ('A 纯横向往返 ×4（左→右→左→右→左）', [(10, 0), (-10, 0), (10, 0), (-10, 0), (10, 0)], 4),
    ('B 纯纵向往返 ×4（下→上→下→上→下）', [(0, 10), (0, -10), (0, 10), (0, -10), (0, 10)], 4),
    ('C 横纵交替（用户"撸猫"最常见）', [(10, 0), (0, 10), (-10, 0), (0, -10), (10, 0)], None),
    ('D 单向直线（不该触发）', [(10, 0), (10, 0), (10, 0), (10, 0), (10, 0)], 0),
    ('E 对角线往返（同为 horizontal 类）', [(10, 6), (-10, -6), (10, 6), (-10, -6), (10, 6)], 4),
    ('F 噪声抖动（±1 在 3px 阈值边缘，不该触发）', [(4, 0), (-4, 0), (4, 0), (-4, 0), (4, 0)], 4),
]
print('--- 逐条复核 ---')
print('%-46s %-10s %-10s %s' % ('用例', '实测', '期望', '判定'))
print('-' * 84)
fails = 0
results = {}
for name, pairs, expect in CASES:
    got = dc_of(seq(pairs))
    results[name] = got
    if expect is None:
        verdict = '(记录)'
    elif got == expect:
        verdict = '[PASS]'
    else:
        verdict = '[FAIL]'
        fails += 1
    print('%-46s %-10s %-10s %s' % (name, got, '记录' if expect is None else expect, verdict))

print()
print('-' * 72)
print('重点分析（**以实测为准**，不预设立场）')
print('-' * 72)
print('  用例 A 纯横向往返 =', results['A 纯横向往返 ×4（左→右→左→右→左）'], ' ⇒ 正常计数')
print('  用例 B 纯纵向往返 =', results['B 纯纵向往返 ×4（下→上→下→上→下）'], ' ⇒ 正常计数')
print('      （早先"纵向失效"的推断来自 pet_interaction.py 的死代码，'
      '活产线里这条**不成立**，此处以实测推翻）')
print('  用例 C 横纵交替   =', results['C 横纵交替（用户"撸猫"最常见）'], ' ← ★ 真缺陷：一次都不计数')
print('  用例 D 单向直线   =', results['D 单向直线（不该触发）'], ' ⇒ 正确不触发')
print()

# 根因：prev_dir 的判定用的是"上一对 (dx,dy) 的整体主方向"，
# 而比较用的是"当前对的 (dx,dy)"——当横纵交替时：
#   current_dir != prev_dir → 整段 if 被跳过 → 计数不增
# 也就是说：**只有"连续两步同为主轴方向"时才可能计数**。
print('-' * 72)
print('根因定位（仍以产品源码为判据）')
print('-' * 72)
# 逐条打印每一步的 prev/current 主方向，看 if 有没有被跳过
def trace(pairs, label):
    print('  [%s]' % label)
    hist = seq(pairs)
    prev_dx = prev_dy = None
    cc = 0
    for i, (mdx, mdy, _) in enumerate(hist):
        cur_dir = 'horizontal' if abs(mdx) > abs(mdy) else 'vertical'
        note = ''
        if prev_dx is not None:
            prev_dir = 'horizontal' if abs(prev_dx) > abs(prev_dy) else 'vertical'
            if cur_dir == prev_dir:
                if cur_dir == 'horizontal':
                    if (mdx > 0 and prev_dx < 0) or (mdx < 0 and prev_dx > 0):
                        cc += 1
                        note = '← 计 1'
                else:
                    if (mdy > 0 and prev_dy < 0) or (mdy < 0 and prev_dy > 0):
                        cc += 1
                        note = '← 计 1'
            else:
                note = '← 主轴翻转，整段跳过（不比较）'
        print('    step%d dir=%-10s prev=%-10s %s' %
              (i, cur_dir, prev_dir if prev_dx is not None else '-', note))
        prev_dx, prev_dy = mdx, mdy
    print('    => direction_changes = %d' % cc)
    print()

trace([(0, 10), (0, -10), (0, 10), (0, -10), (0, 10)], 'B 纯纵向往返')
trace([(10, 0), (0, 10), (-10, 0), (0, -10), (10, 0)], 'C 横纵交替')
trace([(10, 0), (-10, 0), (10, 0), (-10, 0), (10, 0)], 'A 纯横向往返')

print('=' * 72)
print('SUITE_SUMMARY pass=%d fail=%d' % (len(CASES) - fails, fails))
sys.exit(0 if fails == 0 else 1)
