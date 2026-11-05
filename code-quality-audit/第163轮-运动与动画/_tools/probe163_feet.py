# -*- coding: utf-8 -*-
"""第163轮 · 「换动画时脚底/本体到底动多少」（纯计算，不跑事件循环）。

背景：
  · 第98轮 `_anim_anchor_offset` 的口径是"把**每帧最大 alpha 连通块**的中心钉到
    该帧画布中心"，它的注释写着「画布中心 == 窗口中心，窗口 resize 是'保中心'」。
  · 第162轮把 resize 从**保中心**改成了**水平保中心 / 垂直保底边**（`anchored_resize_xy`）。
  两者叠加后，"脚底是否真的不动"就不能靠推导，必须逐动画算。

本支用**产品自己的**算法算（`_main_component_bbox` / `_alpha_row_bits`），
不复制一份实现 —— 观察量必须由被测代码给出。

对每个动画输出（屏幕坐标，假设窗口底边 fixed = 1000，scale 取产品的 `_cached_scale_factor`）：
  · 窗口高 / 窗口宽
  · 本体 bbox（在画布内）
  · **脚底屏幕 y** = 窗口底 − 窗口高 + (bbox 底在画布内) × scale
  · **本体中心屏幕 y**（锚点钉的那个点）
  · **本体中心屏幕 x**

判据（看离散度）：
  若"脚底不动"成立 ⇒ 所有动画的脚底 y 应该几乎相同（差 ≤1~2px）。
  若"本体中心不动"成立 ⇒ 中心 y 也几乎相同。
  两者不可能同时成立（除非 bbox 底恰好等于画布底）。

跑法：`C:\\Python311\\python.exe probe163_feet.py`
"""
import os
import sys

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['RALSEI_DATA_DIR'] = os.path.join(
    __import__('tempfile').gettempdir(), 'pet163_data')
os.makedirs(os.environ['RALSEI_DATA_DIR'], exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'src'))

import memory_store as _ms
_ms.find_device_dir = lambda create=True: None
import data_store as _ds
_ds.vault_root = lambda create=True: None

from PyQt5.QtWidgets import QApplication   # noqa: E402
app = QApplication(sys.argv[:1])

# 只看桌面上真会播的那批（第163轮静态扫描：字面量 21 个 + walk_/run_ 四个方向 + spell_anim）
WATCH = ['idle', 'walk_down', 'walk_left', 'walk_right', 'walk_up',
         'run_down', 'run_left', 'run_right', 'run_up',
         'jump', 'jump_ball', 'jump_ready', 'fall', 'fall_back', 'fall_mad',
         'land', 'splat', 'sleep', 'sit', 'sit_rest',
         'spell', 'act', 'dance', 'sing', 'laugh', 'wave', 'pose', 'happy',
         'sad', 'neutral', 'look_up', 'surprised', 'nuzzle', 'cry']


def main():
    from main import RalseiPet
    w = RalseiPet()
    scale = float(getattr(w, '_cached_scale_factor', 2.0))
    print('scale = %s' % scale)

    BOTTOM = 1000.0        # 假设窗口底边固定在这里（第162轮：保底边 ⇒ 这就是不变量）
    rows = []
    for a in WATCH:
        frames = w.sprite_loader.sprites.get(a)
        if not frames:
            continue
        # 容器 = 全动画最大帧（与 update_animation 同口径）
        cw = max((f.width() for f in frames if f and not f.isNull()), default=0)
        ch = max((f.height() for f in frames if f and not f.isNull()), default=0)
        if cw <= 0 or ch <= 0:
            continue
        # 逐帧本体 bbox，取"最靠下的脚底"和"第 0 帧的中心"两种口径都算
        feet = []
        centers = []
        for f in frames:
            if f is None or f.isNull():
                continue
            rows_bits = w._alpha_row_bits(f)
            bb = w._main_component_bbox(rows_bits, f.width())
            if bb is None:
                continue
            # bb = (x, y, w, h) in 该帧画布
            feet.append(bb[1] + bb[3])
            centers.append(((bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0))
        if not feet:
            continue
        win_w = cw * scale
        win_h = ch * scale
        top = BOTTOM - win_h
        # 脚底：本体最下沿（画布坐标）× scale + 窗口顶
        feet_y = [top + (ch - (ch - fy)) * 0 for fy in feet]   # 占位，下面重算
        feet_screen = [top + fy * scale for fy in feet]
        ctr_screen = [top + cy * scale for _, cy in centers]
        cx_screen = [top * 0 for _ in feet]  # 占位
        # 水平：窗口保中心 ⇒ 窗口中心固定；本体中心被钉到画布中心 ⇒ 屏幕 x 恒等于窗口中心
        rows.append({
            'name': a,
            'container': (cw, ch),
            'win': (round(win_w, 1), round(win_h, 1)),
            'feet_min': min(feet_screen), 'feet_max': max(feet_screen),
            'ctr_min': min(ctr_screen), 'ctr_max': max(ctr_screen),
            'bbox_bottom_in_canvas': [round(ch - fy, 1) for fy in feet[:4]],
        })

    print('\n%-14s %-12s %-13s %-16s %-16s'
          % ('anim', 'container', 'window', '脚底 y (min~max)', '本体中心 y (min~max)'))
    for r in rows:
        print('%-14s %-12s %-13s %-16s %-16s'
              % (r['name'], '%dx%d' % r['container'],
                 '%.0fx%.0f' % r['win'],
                 '%.1f~%.1f' % (r['feet_min'], r['feet_max']),
                 '%.1f~%.1f' % (r['ctr_min'], r['ctr_max'])))

    print('\n==== 跨动画离散度（只看桌面上真会播的）====')
    all_feet = [r['feet_min'] for r in rows] + [r['feet_max'] for r in rows]
    all_ctr = [r['ctr_min'] for r in rows] + [r['ctr_max'] for r in rows]
    print('脚底 y 全range   = %.1f ~ %.1f  （跨度 %.1f px）'
          % (min(all_feet), max(all_feet), max(all_feet) - min(all_feet)))
    print('本体中心 y range = %.1f ~ %.1f  （跨度 %.1f px）'
          % (min(all_ctr), max(all_ctr), max(all_ctr) - min(all_ctr)))

    # 每个动画内部：多帧之间脚底是否也在抖（同一动画内逐帧）
    print('\n==== 同一动画内：逐帧脚底抖动 top 10 ====')
    inner = []
    for r in rows:
        inner.append((r['feet_max'] - r['feet_min'], r['name']))
    inner.sort(reverse=True)
    for d, nm in inner[:10]:
        print('  %-14s 帧间脚底跨度 %.1f px' % (nm, d))

    print('\n==== 距画布底的空隙（决定"保底边"等不等于"保脚底"）====')
    for r in rows:
        gaps = r['bbox_bottom_in_canvas']
        print('  %-14s 容器高 %2d  本体距底(前4帧) %s'
              % (r['name'], r['container'][1], gaps))


if __name__ == '__main__':
    main()
