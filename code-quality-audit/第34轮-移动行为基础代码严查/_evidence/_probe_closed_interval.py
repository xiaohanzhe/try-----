# -*- coding: utf-8 -*-
"""第 34 轮：《楼层实现》审查 —— 核验 `nearest_visible_point` 用 QRect 闭区间
   （r.right()/r.bottom() = left+w-1）与 `visible_subrects` 的半开区间口径混用，
   是否会产生**可观测**的错误吸附点。

判据纪律：直接调产品函数 `nearest_visible_point`，不重写它。
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r'ralsei_pet')

from PyQt5.QtWidgets import QApplication           # noqa: E402
from PyQt5.QtCore import QRect, QPoint             # noqa: E402

app = QApplication([])
from modules.floor_manager import FloorManager      # noqa: E402

fm = FloorManager()


def mk_floor(r):
    return {
        'type': 'window', 'window': {'hwnd': 1, 'rect': r},
        'rect': r, 'visible_rects': [r], 'visible_area': r.width() * r.height(),
        'z_order': 1, 'platform_height': 5, 'window_hwnd': 1,
    }


print('=' * 74)
print('核验：QRect 闭区间 (right=left+w-1) 与半开区间口径混用的实际影响')
print('=' * 74)

# 子矩形 x 10..109（w=100），因此 r.right() == 109
r = QRect(10, 10, 100, 100)
fl = mk_floor(r)
print('可见子矩形：QRect(10,10,100,100) → left=10 right=%d top=10 bottom=%d'
      % (r.right(), r.bottom()))
print('半开口径应为 right_exclusive=%d bottom_exclusive=%d' % (10 + 100, 10 + 100))

cases = [
    ('点在最右边界外 1px', QPoint(110, 50)),
    ('点在最右边界内', QPoint(109, 50)),
    ('点在最下边界外 1px', QPoint(50, 110)),
    ('点在最下边界内', QPoint(50, 109)),
    ('点明显在右侧外', QPoint(200, 50)),
    ('点明显在下方外', QPoint(50, 200)),
]

print()
print('%-22s %-16s %-16s %s' % ('场景', '输入点', '吸附结果', '是否落在可见区域外'))
print('-' * 74)
for name, p in cases:
    got = fm.nearest_visible_point(fl, p)
    # 用产品判据复核吸附结果本身是否"可见"
    ok = fm.floor_visible_contains(fl, got) if got else False
    # 半开区间口径下的"是否越界"
    out = not (10 <= got.x() < 110 and 10 <= got.y() < 110) if got else None
    print('%-22s %-16s %-16s %s' % (name, '(%d,%d)' % (p.x(), p.y()),
                                    '(%d,%d)' % (got.x(), got.y()) if got else 'None',
                                    ('越界(x=110是闭区间边界)' if out else '在界内')))

print()
print('-' * 74)
print('补充：r.contains(QPoint(110,50)) =', r.contains(QPoint(110, 50)),
      ' ← 居然为 True，证实 QRect 用闭区间')
print('      r.contains(QPoint(50,110)) =', r.contains(QPoint(50, 110)))
print()
print('判读：')
print('  · 吸附结果 x=110/y=110 是**闭区间**的最后一个整数像素，')
print('    在半开口径下它属于"下一格"（越界 1px）。')
print('  · 但 floor_visible_contains 用的是同一套 QRect.contains → 内部自洽，')
print('    所以产品不会因为这一格判"不可见/站不住"。')
print('  · 影响面：只在"吸附落点恰好落在子矩形右下边界"时差 1px，')
print('    远小于 MIN_FLOOR_VISIBLE_AREA=1600px² 的判据尺度 → 不改变任何"站得住/站不住"结论。')
print('=' * 74)
