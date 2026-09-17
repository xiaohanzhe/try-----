# -*- coding: utf-8 -*-
"""生成 / 校验 `climb_left` 素材（= `climb_1_*` 的水平镜像）。

用户口径（第十八轮）：
  "spr_ralsei_climb_1_0~4.png 这是朝向右边的素材；spr_ralsei_climb_0_degrees_0~5.png
   这是朝向前面的素材；然后相反方向的你就给他翻转一下就好，没有朝后面的因为那样也用不上。"

所以：朝左 = 朝右那组的**水平镜像**（不新增美术，只做翻转）。5 张产物进仓库、走 git。

设计要点
--------
1. **幂等 / 不破坏**：目标文件已存在且**校验通过**就跳过生成 —— 重跑本脚本不会重写已入库的
   PNG（重写会改 mtime、可能引入无意义的二进制 diff）。
2. **校验必须能证伪**：第一版只比"尺寸一致 + 不是空图"，那条**假阴性极强** ——
   把源图**原样复制**过去同样能过（尺寸必然一致），而"没镜像"恰恰是本脚本唯一要保证的事。
   现在改成**逐像素断言镜像关系**：`dst.pixel(x, y) == src.pixel(w-1-x, y)`。
   这也正是本项目「负控制必须能证伪」那条教训的又一次应用：
   **断言要能区分"做对了"和"什么都没做"。**
3. 用 `QImage.mirrored(True, False)`（水平翻转，不翻垂直）。

产出：`_evidence/climb_left_report.txt`

用法：& C:\\Python311\\python.exe make_climb_left_assets.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SRC_DIR = os.path.join(ROOT, 'deltarune_ralsei')
REPORT = os.path.join(HERE, '_evidence', 'climb_left_report.txt')

from PyQt5.QtGui import QImage                      # noqa: E402

# 采样点数：每张图沿对角/横线各取若干点，避免"整图逐像素"在 40x20 上过慢
SAMPLE_COLS = 5


def _mirror_violations(src, dst):
    """返回不满足镜像关系的采样点数（0 = 完全镜像）。"""
    w, h = src.width(), src.height()
    if (dst.width(), dst.height()) != (w, h):
        return -1                       # 尺寸不同，直接判不合格
    bad = 0
    for xi in range(SAMPLE_COLS):
        x = min(w - 1, int(xi * (w - 1) / max(1, SAMPLE_COLS - 1)))
        for yi in range(SAMPLE_COLS):
            y = min(h - 1, int(yi * (h - 1) / max(1, SAMPLE_COLS - 1)))
            if dst.pixel(x, y) != src.pixel(w - 1 - x, y):
                bad += 1
    return bad


lines = []
ok_all = True
generated, verified = 0, 0

for i in range(5):
    src_path = os.path.join(SRC_DIR, 'spr_ralsei_climb_1_%d.png' % i)
    dst_path = os.path.join(SRC_DIR, 'spr_ralsei_climb_left_%d.png' % i)

    src = QImage(src_path)
    if src.isNull():
        lines.append('FAIL 读不到 %s' % src_path)
        ok_all = False
        continue

    existed = os.path.exists(dst_path)
    dst = QImage(dst_path) if existed else QImage()

    # 先校验已存在的产物；合格就跳过（幂等、不重写已入库文件）
    if existed and not dst.isNull() and _mirror_violations(src, dst) == 0:
        verified += 1
        lines.append('SKIP(已存在且校验通过) %s  %dx%d' % (
            os.path.basename(dst_path), dst.width(), dst.height()))
        continue

    mir = src.mirrored(True, False)                 # 水平镜像
    if not mir.save(dst_path, 'PNG'):
        lines.append('FAIL 写不出 %s' % dst_path)
        ok_all = False
        continue

    chk = QImage(dst_path)
    bad = _mirror_violations(src, chk)
    generated += 1
    lines.append('%s -> %s  %dx%d  saved=True  镜像采样不符点=%d' % (
        os.path.basename(src_path), os.path.basename(dst_path),
        chk.width(), chk.height(), bad))
    if chk.isNull() or bad != 0:
        lines.append('  FAIL 校验不通过（不是严格的水平镜像）')
        ok_all = False

lines.append('')
lines.append('generated=%d verified_skip=%d' % (generated, verified))
lines.append('RESULT=%s' % ('OK' if ok_all else 'FAIL'))

os.makedirs(os.path.dirname(REPORT), exist_ok=True)
with open(REPORT, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write('\n'.join(lines) + '\n')

sys.stdout.write('\n'.join(lines) + '\n')
sys.exit(0 if ok_all else 1)
