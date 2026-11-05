# -*- coding: utf-8 -*-
"""第163轮 · 动画素材与容器的实测（只读，不改产品）。

用户口径：「尤其是**运动类**和**动画类**那一部分」⇒ 先把"动画到底长什么样"量清楚，
不凭印象报问题。

量四件事：
  ① 每个动画的帧数、每帧原始像素尺寸（同一动画内是否一致）
  ② 每个动画的**容器尺寸**（`update_animation` 取"本动画最大帧 × scale_factor"）
  ③ 每帧的 **alpha 包围盒**（真实可见区域 —— 容器不等于角色）
  ④ 跨动画对比：容器/可见区域的宽高比与高度差（人物换动作时会不会"忽大忽小"）

为什么必须看 alpha bbox：容器是"最大帧的整张画布"，而 Ralsei 的精灵图四周有大量
透明留白；两张画布尺寸不同、可见区域却可能一样高。只看容器会把"留白差异"误报成
"角色变形"。

用法：`C:\\Python311\\python.exe probe163_anim.py [--json out.json]`
零网络 / 零外部盘 / offscreen。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'ralsei_pet', 'modules'))

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('RALSEI_DATA_DIR', os.path.join(os.environ.get('TEMP', '.'), 'probe163'))

from PyQt5.QtWidgets import QApplication          # noqa: E402
from PyQt5.QtGui import QImage                    # noqa: E402

app = QApplication(sys.argv[:1])


def alpha_bbox(qpix):
    """可见区域（alpha > 8 的包围盒），返回 (x, y, w, h)；全透明返回 None。"""
    if qpix is None or qpix.isNull():
        return None
    img = qpix.toImage().convertToFormat(QImage.Format_ARGB32)
    w, h = img.width(), img.height()
    minx, miny, maxx, maxy = w, h, -1, -1
    for y in range(h):
        # 逐行取整条扫描线，比逐像素调用快得多
        line = img.constScanLine(y)
        try:
            data = line.asstring(w * 4)
        except Exception:
            data = bytes(line)
        for x in range(w):
            if data[x * 4 + 3] > 8:
                if x < minx:
                    minx = x
                if x > maxx:
                    maxx = x
                if y < miny:
                    miny = y
                if y > maxy:
                    maxy = y
    if maxx < 0:
        return None
    return (minx, miny, maxx - minx + 1, maxy - miny + 1)


def main():
    from sprite_loader import SpriteLoader
    sl = SpriteLoader()
    sl.load_sprites()

    names = sorted(sl.sprites.keys())
    print('动画总数 = %d' % len(names))
    print('sprite_dir = %s' % sl.sprite_dir)

    rows = []
    for nm in names:
        frames = sl.sprites.get(nm) or []
        sizes = []
        for f in frames:
            if f is not None and not f.isNull():
                sizes.append((f.width(), f.height()))
        if not sizes:
            rows.append({'name': nm, 'frames': 0, 'note': 'empty'})
            continue
        uniq = sorted(set(sizes))
        # 容器 = 每维取最大（与 update_animation 的口径一致）
        cw = max(s[0] for s in sizes)
        ch = max(s[1] for s in sizes)
        # 只对首帧算 bbox（1116 张全算太慢，首帧足够代表可见区域）
        bb = alpha_bbox(frames[0])
        rows.append({
            'name': nm,
            'frames': len(sizes),
            'uniq_sizes': uniq,
            'container': [cw, ch],
            'bbox0': list(bb) if bb else None,
        })

    print('\n%-28s %5s %-22s %-12s %-16s %s'
          % ('anim', 'frames', 'raw sizes(uniq)', 'container', 'bbox0(x,y,w,h)', 'bbox/容器'))
    for r in rows:
        if r.get('note'):
            print('%-28s %5d  <empty>' % (r['name'], 0))
            continue
        c = r['container']
        bb = r['bbox0']
        ratio = ''
        if bb:
            ratio = '%.2f x %.2f' % (bb[2] / c[0], bb[3] / c[1])
        print('%-28s %5d %-22s %-12s %-16s %s'
              % (r['name'], r['frames'], str(r['uniq_sizes'])[:22],
                 '%dx%d' % (c[0], c[1]), str(bb), ratio))

    # ---- 跨动画对比：以 idle 为基准 ----
    print('\n==== 跨动画：容器/可见高度 相对 idle 的偏差 ====')
    base = next((r for r in rows if r['name'] == 'idle' and r.get('bbox0')), None)
    if not base:
        print('idle 缺失，跳过')
    else:
        bc = base['container']
        bb = base['bbox0']
        print('baseline idle: container=%dx%d bbox=%s 可见宽高比=%.2f'
              % (bc[0], bc[1], bb, bb[2] / bb[3]))
        cols = []
        for r in rows:
            if r.get('note') or not r.get('bbox0'):
                continue
            c, b = r['container'], r['bbox0']
            dh = (b[3] - bb[3]) / bb[3] * 100.0      # 可见高度差 %
            dw = (b[2] - bb[2]) / bb[2] * 100.0      # 可见宽度差 %
            dar = (b[2] / b[3]) / (bb[2] / bb[3])    # 宽高比之比
            cols.append((abs(dh), r['name'], dh, dw, dar, c, b))
        cols.sort(reverse=True)
        print('\n%-28s %8s %8s %8s  %s' % ('anim', 'Δh%', 'Δw%', 'AR比', 'container/bbox'))
        for _, nm, dh, dw, dar, c, b in cols[:25]:
            print('%-28s %+7.1f%% %+7.1f%% %8.2f  %dx%d / %s'
                  % (nm, dh, dw, dar, c[0], c[1], b))

    # ---- 同动画内：帧尺寸不一致的 ----
    print('\n==== 同一动画内帧尺寸不一致的（容器法能兜住，但说明素材本身不齐） ====')
    n = 0
    for r in rows:
        if r.get('note'):
            continue
        if len(r['uniq_sizes']) > 1:
            n += 1
            print('%-28s %d 种: %s' % (r['name'], len(r['uniq_sizes']), r['uniq_sizes']))
    print('合计 %d 个动画存在帧尺寸不一致' % n)

    if '--json' in sys.argv:
        i = sys.argv.index('--json')
        out = sys.argv[i + 1] if i + 1 < len(sys.argv) else os.path.join(HERE, 'probe163_anim.json')
        with io.open(out, 'w', encoding='utf-8') as fh:
            json.dump(rows, fh, ensure_ascii=False, indent=1)
        print('\n[json] %s' % out)


if __name__ == '__main__':
    main()
