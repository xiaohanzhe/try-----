# -*- coding: utf-8 -*-
u"""第190轮 · 把「哪些 sprite 落在彩色页上」查清楚。

要回答的问题
------------
用户问：「有没有可能有些原版头像就是没颜色只是黑白呢」

半程已证的结论（第190轮实测，已肉眼确认）：
  · 黄魂 117 张贴图页里 **98 页是真彩色**，14 页是 2 色、5 页是退化的占位图
  · 但 `spr_portrait_*`（124 个角色肖像）的 UV **全部落在 p060**，
    而 p060 的肖像区域是**黑底白线稿**（black 72% + white 28%，零透明、零其它色）
  · 包里**只有一套** portrait 家族，没有第二个彩色变体

所以现在的关键问题不是"能不能解码"（能），而是**彩色内容到底被谁用**。
本脚本按页聚合 sprite，把"彩色页"和"落上去的 sprite 名"连起来，一次看清全貌。

★ 判据设计要点（踩过的坑）
--------------------------
不能只报"这页是彩色"就完事 —— 那只能说明图集里有颜色，不能说明
**我要的角色**有颜色。必须 `页 → sprite 名` 双向可查，否则又会重演
"看到 98 张彩色页就以为肖像有颜色"这种误判。

用法
----
    python pagemap190.py --tag hy
    python pagemap190.py --tag hy --page 60      # 只看某一页上有谁
"""
import io
import os
import sys
import collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from PIL import Image  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence')
PAGE_DIR = {
    'hy': u'D:\\_tmp190\\hy_export_pages190\\pages',
    'ut': u'D:\\_tmp190\\ut_export_pages190\\pages',
    'ot': u'D:\\_tmp190\\ot_export_pages190\\pages',
}


def arg(key, default=None):
    a = sys.argv[1:]
    if key not in a:
        return default
    i = a.index(key)
    return a[i + 1] if i + 1 < len(a) else default


def page_colors(path):
    """返回 (唯一色数, 不透明率%)。"""
    im = Image.open(path).convert('RGBA')
    px = list(im.getdata())
    n = float(len(px))
    return len(set(px)), 100.0 * sum(1 for p in px if p[3] > 16) / n


def read_uv(path):
    rows = []
    for l in io.open(path, encoding='utf-8').read().splitlines():
        if not l.strip() or l.startswith('#'):
            continue
        f = l.split('\t')
        if len(f) < 7:
            continue
        rows.append((f[0], int(f[1]), int(f[2])))
    return rows


def main():
    tag = arg('--tag', 'hy')
    only_page = arg('--page')
    uv_path = os.path.join(EV, 'uv', tag + '.tsv')
    if not os.path.isfile(uv_path):
        uv_path = u'D:\\_tmp190\\hy_uv\\uv.tsv'
    pdir = PAGE_DIR.get(tag)
    if not os.path.isfile(uv_path) or not pdir:
        print('[停手] 缺 uv 表或页目录')
        return 2

    uv = read_uv(uv_path)
    by_page = collections.defaultdict(list)
    for name, _fr, pg in uv:
        by_page[pg].append(name)

    if only_page:
        p = int(only_page)
        print('[p%03d] 上有 %d 条 sprite：' % (p, len(by_page.get(p, []))))
        for n in sorted(set(by_page.get(p, []))):
            print('   %s' % n)
        return 0

    print('[uv] %d 条，涉及 %d 页' % (len(uv), len(by_page)))
    print('')
    print('%-5s %-11s %-6s %-7s %-6s %s' %
          ('page', 'size', 'colors', 'opaque%', 'sprs', '判定 / 代表 sprite'))

    stats = {}
    for p in sorted(by_page):
        fn = os.path.join(pdir, 'p%03d.png' % p)
        if not os.path.isfile(fn):
            print('%-5d %-11s %-6s %-7s %-6d %s' % (p, '-', '-', '-', len(by_page[p]), '缺页'))
            continue
        nc, op = page_colors(fn)
        size = Image.open(fn).size
        kinds = '彩色' if nc > 2 else '2色'
        sample = sorted(set(by_page[p]))[:2]
        print('%-5d %-11s %-6d %-7.1f %-6d %s  %s'
              % (p, '%dx%d' % size, nc, op, len(by_page[p]), kinds,
                 ', '.join(s[:42] for s in sample)))
        stats[p] = (nc, op)

    # ★ 汇总：肖像族落在哪些页、那些页是彩色还是 2 色
    print('')
    fams = collections.defaultdict(lambda: collections.Counter())
    for name, _fr, pg in uv:
        if 'portrait' in name:
            fam = 'portrait'
        elif 'face' in name:
            fam = 'face'
        else:
            fam = 'other'
        nc = stats.get(pg, (0, 0))[0]
        fams[fam]['彩色页' if nc > 2 else '2色页'] += 1
    for fam, c in fams.items():
        print('[族] %-9s 落页情况：%s' % (fam, dict(c)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
