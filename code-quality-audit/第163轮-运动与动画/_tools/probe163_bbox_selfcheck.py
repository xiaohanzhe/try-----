# -*- coding: utf-8 -*-
"""第163轮 · `union_bbox` 的正/负控制（不 import main，纯 PyQt，秒级）。

为什么必须做：`probe163_round2.py` 报「34 个动画的视觉脚底全部 = 1000.0，跨度 0.0px」。
这个数字太整齐，必须排除两种可能：
  (a) `union_bbox` 恒返回"触到画布底"（判据恒真 ⇒ 数字是假的）；
  (b) `_compose_anchored_sprite` 的合成画布高恰等于窗口高，导致减法退化成常数。
本支用**已知答案的图**喂给 union_bbox 本体（源码从 round2 里抽出来 exec，不复制一份），
四组正负控制 + 一组真实帧。

跑法：C:\\Python311\\python.exe probe163_bbox_selfcheck.py
"""
import os
import re
import sys

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
HERE = os.path.dirname(os.path.abspath(__file__))

from PyQt5.QtWidgets import QApplication       # noqa: E402
from PyQt5.QtGui import QPixmap, QColor, QPainter, QImage  # noqa: E402
from PyQt5.QtCore import Qt                    # noqa: E402

app = QApplication(sys.argv[:1])

# —— 从 round2 抽 union_bbox 源码（避免第二份实现）——
src = open(os.path.join(HERE, 'probe163_round2.py'), encoding='utf-8').read()
m = re.search(r'\ndef union_bbox\(pixmap\):.*?\n(?=\ndef )', src, re.S)
assert m, '没能从 probe163_round2.py 抽出 union_bbox'
ns = {'QPixmap': QPixmap, 'QImage': QImage}
exec(m.group(0).lstrip('\n'), ns)
union_bbox = ns['union_bbox']
print('已从 probe163_round2.py 抽取 union_bbox（%d 行）' % m.group(0).count('\n'))


def make(w, h, rect=None, color=QColor(255, 0, 0, 255)):
    pm = QPixmap(w, h)
    pm.fill(Qt.transparent)
    if rect:
        p = QPainter(pm)
        p.fillRect(*rect, color)
        p.end()
    return pm


fails = []


def check(desc, got, want):
    ok = (got == want)
    print('  [%s] %-46s got=%s want=%s'
          % ('PASS' if ok else 'FAIL', desc, got, want))
    if not ok:
        fails.append(desc)


print('\n==== 负控制：不该有像素/不该触底 ====')
check('全透明 10x10 → None', union_bbox(make(10, 10)), None)
check('20x20 只在 (8,3)-(12,7) 有不透明 → (8,3,12,7)',
      union_bbox(make(20, 20, (8, 3, 4, 4))), (8, 3, 12, 7))

print('\n==== 正控制：触底/不触底必须能区分 ====')
check('20x20 顶部 2 行不透明 → 底=2（≠20，证明不是恒返回画布高）',
      union_bbox(make(20, 20, (0, 0, 20, 2))), (0, 0, 20, 2))
check('20x20 底部 2 行不透明 → 底=20',
      union_bbox(make(20, 20, (0, 18, 20, 2))), (0, 18, 20, 20))
check('20x20 左侧 1 列不透明 → (0,0,1,20)',
      union_bbox(make(20, 20, (0, 0, 1, 20))), (0, 0, 1, 20))

print('\n==== 对照：把同一张图下移 4px，底必须跟着变 4px ====')
b1 = union_bbox(make(20, 20, (6, 6, 4, 4)))
b2 = union_bbox(make(20, 20, (6, 10, 4, 4)))
check('底沿随图形下移而变化（4px）', (b1[3], b2[3]), (10, 14))

print('\n==== 结论 ====')
if fails:
    print('  %d 项 FAIL ⇒ union_bbox 不可信，脚底数据作废：%s' % (len(fails), fails))
    sys.exit(1)
print('  全部 PASS ⇒ union_bbox 能正确区分"触底"与"不触底"，'
      '「视觉脚底=1000.0 恒定」不是恒真判据造成的。')
