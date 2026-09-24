# -*- coding: utf-8 -*-
"""把 obj 绘制需要的 25 个 sprite 搬进仓库（assets/scenes/objs/）。

为什么落 `assets/scenes/objs/`：
  `scene_canvas.SceneAssetCache` 无前缀的素材名相对 `assets/scenes/` 解析，
  所以 objects 里写 `objs/spr_doorA_0.png` 就能被直接读到，零改代码。

搬哪些：只搬「实例真正引用到的 sprite」（25 个 / 200 文件，见 copy_plan）。
  **不搬全量 7 万张** —— 那是浪费仓库体积，且绝大部分与本产品无关。

幂等：已存在且大小一致 → 跳过（可重复跑）。
"""
import io
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
EV = os.path.join(ROOT, 'code-quality-audit', '第44轮-原作对话框复刻', '_evidence')
PLAN = os.path.join(EV, 'obj_sprite_copy_plan44.json')
DST = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'objs')
CHDIR = {'ch1': 'chapter1_windows', 'ch2': 'chapter2_windows',
         'ch3': 'chapter3_windows', 'ch4': 'chapter4_windows',
         'ch5': 'chapter5_windows'}


def main():
    with io.open(PLAN, 'r', encoding='utf-8') as fh:
        plan = json.load(fh)
    src_root = plan['source_root']
    per_spr = plan['plan']

    if not os.path.isdir(DST):
        os.makedirs(DST)
        print('建目录 %s' % os.path.relpath(DST, ROOT))

    copied = skipped = 0
    seen = set()
    for spr, chmap in per_spr.items():
        for ch, files in chmap.items():
            sd = os.path.join(src_root, CHDIR[ch], 'Sprites')
            for f in files:
                if f in seen:
                    continue
                seen.add(f)
                src = os.path.join(sd, f)
                dst = os.path.join(DST, f)
                if not os.path.exists(src):
                    print('  !! 源缺失 %s' % src)
                    continue
                if os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src):
                    skipped += 1
                    continue
                shutil.copy2(src, dst)
                copied += 1

    n = len(os.listdir(DST))
    total = sum(os.path.getsize(os.path.join(DST, f)) for f in os.listdir(DST))
    print('')
    print('copied=%d skipped=%d' % (copied, skipped))
    print('objs/ 现有文件 %d 个，共 %.2f MB' % (n, total / 1048576.0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
