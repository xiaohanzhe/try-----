# -*- coding: utf-8 -*-
"""精确摘录改造前 main.py 各手势分支的 (emotion adds, animation, kind)。

只读，输出到 stdout；用途：为 pet_interaction.RESPONSE_SPEC 提供**逐字**依据。
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
MAIN = os.path.join(ROOT, 'ralsei_pet', 'src', 'main.py')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

with open(MAIN, 'r', encoding='utf-8') as f:
    lines = f.readlines()


def show(a, b, tag):
    print('=' * 70)
    print('[%s] main.py %d~%d' % (tag, a, b))
    print('=' * 70)
    for i in range(a - 1, min(b, len(lines))):
        ln = lines[i].rstrip('\n')
        if ln.strip():
            print('%5d| %s' % (i + 1, ln))


# 单击部位（mousePressEvent 8396~8414）
show(8396, 8414, 'PUSH')
# 长按（mouseReleaseEvent 8805~8851）
show(8805, 8851, 'PINCH/PULL')
# 双击（mouseDoubleClickEvent 8876~8912）
show(8876, 8912, 'PAT')
# 抚摸（mouseMoveEvent 8613~8628）
show(8613, 8628, 'STROKE')
