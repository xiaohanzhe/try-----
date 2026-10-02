# -*- coding: utf-8 -*-
"""B3 前置取证：量化 main.py 手写手势系统 与 modules/pet_interaction.py 的差异面。

只读，不改任何文件；输出到 stdout。
判据纪律：本脚本只做"计数与枚举"，不下论断（论断由我据数字写）。
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
PI = os.path.join(ROOT, 'ralsei_pet', 'modules', 'pet_interaction.py')
EV = os.path.join(ROOT, 'ralsei_pet', 'modules', 'event_speech.py')

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


def read(p):
    with open(p, 'r', encoding='utf-8') as f:
        return f.read()


def count_lines(text, start_pat, end_pat):
    """数 start_pat 到 end_pat 之间的行数（粗略，用于量级）。"""
    lines = text.split('\n')
    s = e = None
    for i, ln in enumerate(lines):
        if s is None and start_pat in ln:
            s = i
        elif s is not None and end_pat in ln:
            e = i
            break
    if s is None or e is None:
        return None
    return e - s


main_src = read(MAIN)
pi_src = read(PI)
ev_src = read(EV)

print('=' * 70)
print('[A] 部位名集合对比')
print('=' * 70)

# main.py get_ralsei_body_part 的区域表
# ★ 修正：区域表是 `body_parts = [ ... ]`（不是函数第一行），且条目形如 ("ear", 0, 0, 30, 40)
m = re.search(r'body_parts\s*=\s*\[(.*?)\n\s*\]', main_src, re.S)
main_parts = []
if m:
    main_parts = re.findall(r'\("([a-z_]+)"\s*,', m.group(1))
main_parts_set = sorted(set(main_parts))
print('main.py get_ralsei_body_part 区域名（去重）:')
print('   ', main_parts_set)
print('    条目数 =', len(main_parts), '（含重复区间）')
assert main_parts, '区域表抽取失败 —— 判据本身错了，先修正则'

# pet_interaction.py BodyPart / Gesture —— 只取两个枚举类体内
def enum_vals(src, cls):
    m = re.search(r'class %s\(str, Enum\):(.*?)(?=\nclass |\Z)' % cls, src, re.S)
    if not m:
        return []
    return sorted(set(re.findall(r'=\s*"([a-z_]+)"', m.group(1))))

pi_vals = enum_vals(pi_src, 'BodyPart')
pi_gest = enum_vals(pi_src, 'Gesture')
print('pet_interaction.py BodyPart 枚举值:')
print('   ', pi_vals, ' 共', len(pi_vals), '个')
assert pi_vals and pi_vals != pi_gest, '两个枚举抽成一样了 —— 判据错了'

only_main = sorted(set(main_parts_set) - set(pi_vals))
only_pi = sorted(set(pi_vals) - set(main_parts_set))
both = sorted(set(main_parts_set) & set(pi_vals))
print('  ⇒ 只有 main 有 :', only_main)
print('  ⇒ 只有 pi  有 :', only_pi)
print('  ⇒ 两边都有     :', both)

print()
print('=' * 70)
print('[B] 手势集合对比')
print('=' * 70)
print('pet_interaction.py Gesture 枚举值:', pi_gest)
assert pi_gest, 'Gesture 抽取失败'

# main.py 侧：靠"事件名"推断
main_events = sorted(set(re.findall(r'speak_event\(\s*"([a-z_]+)"', main_src)))
print('main.py speak_event 用到的 kind（全量，含非手势）:')
print('   ', main_events)

print()
print('=' * 70)
print('[C] 代码体量（行数）')
print('=' * 70)
print('pet_interaction.py 总行数 =', len(pi_src.split('\n')))
print('main.py 总行数           =', len(main_src.split('\n')))

segs = [
    ('get_ralsei_body_part', 'def get_ralsei_body_part', 'def mousePressEvent'),
    ('mousePressEvent', 'def mousePressEvent', 'def start_following_mouse'),
    ('mouseMoveEvent', 'def mouseMoveEvent', 'def mouseReleaseEvent'),
    ('mouseReleaseEvent', 'def mouseReleaseEvent', 'def mouseDoubleClickEvent'),
    ('mouseDoubleClickEvent', 'def mouseDoubleClickEvent', 'def '),
]
tot = 0
for name, s, e in segs:
    n = count_lines(main_src, s, e)
    if n:
        tot += n
        print('  %-24s ~%4d 行' % (name, n))
print('  ⇒ 合计约 %d 行（mouseDoubleClickEvent 边界为近似值）' % tot)

print()
print('=' * 70)
print('[D] 接线状态（硬事实）')
print('=' * 70)
print('main.py 里出现 "pet_interaction" 次数 =', main_src.count('pet_interaction'))
print('main.py 里出现 "PetInteractionTracker" 次数 =',
      main_src.count('PetInteractionTracker'))
print('全仓库（除模块本身）真正 import pet_interaction 的文件（AST 级）:')
import ast
import glob
hits = []
strhits = []
for p in glob.glob(os.path.join(ROOT, 'ralsei_pet', '**', '*.py'), recursive=True):
    if os.path.basename(p) == 'pet_interaction.py':
        continue
    t = read(p)
    try:
        tree = ast.parse(t)
    except SyntaxError:
        continue
    imported = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if 'pet_interaction' in a.name:
                    imported = True
        elif isinstance(node, ast.ImportFrom):
            if node.module and 'pet_interaction' in node.module:
                imported = True
            for a in node.names:
                if 'pet_interaction' in a.name:
                    imported = True
    if imported:
        hits.append(os.path.relpath(p, ROOT))
    elif 'pet_interaction' in t:
        # 只是字符串/注释里出现（例如事件类型名 'pet_interaction'）
        strhits.append(os.path.relpath(p, ROOT))
print('   ★ 真 import :', hits if hits else '（无 —— 零接线，确认）')
print('   ○ 仅字符串出现:', strhits)

print()
print('=' * 70)
print('[E] event_speech.py 的 PET_PARTS（事件名 → 是否 AI 档）')
print('=' * 70)
m2 = re.search(r'PET_PARTS\s*=\s*[\(\[]([^\)\]]*)[\)\]]', ev_src, re.S)
print(m2.group(1).strip() if m2 else '（未找到 PET_PARTS）')
