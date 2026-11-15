# -*- coding: utf-8 -*-
u"""第190轮 · 按 UV 从 UTMT 导出的整页 PNG 里裁出人物肖像。

为什么重写（v1 → v2）
--------------------
v1 自己解贴图页（包括自己写 QOI 解码器），卡在"任何起点都能解满但只吃 ~500 字节、
出彩条噪声"。v2 改用 `export_pages190.csx` 让 **UTMT 自己**把整页吐成 PNG，
本脚本只做纯裁切 —— 不再碰任何压缩格式。

★★★ 本轮最重要的一条教训：**旧判据「颜色数 ≤ 2 就是蒙版/解码失败」是错的**。
    用户 2026-11-15 一问点破：「有没有可能有些原版头像就是没颜色只是黑白呢」
    实证：黄魂 117 页里
      · 98 页真彩色（p010 向日葵脸、p099 真彩肖像，肉眼已确认）
      · 14 页 2 色，其中 p083 是 **纯白+全透明(白占 19.2%)** 的遮罩/剪影 —— 原作就是这样
      · 5 页尺寸退化（1x1 / 64x64 渐变条）—— 图集占位
    ⇒ 颜色数**不能**当"解码是否成功"的判据；它只反映"这张图画了几种颜色"。
    正确的判据是组合：颜色数 + 不透明率 + 水平平涂率 + 连通块数 + **肉眼确认**。
    ★ 这条已写进 color190.py 的 docstring，别再犯。

用法
----
    python crop190b.py --tag hy            # 全量裁 + 出 manifest
    python crop190b.py --tag hy --only ceroba   # 只裁名字含 ceroba 的
"""
import io
import json
import os
import sys
import collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from PIL import Image  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence')
OUT_ROOT = u'D:\\_tmp190\\cropped'

# 各作品的页面目录（UTMT 导出物，留在工作区不进仓库：几百 MB 二进制）
PAGE_DIR = {
    'hy': u'D:\\_tmp190\\hy_export_pages190\\pages',
    'ut': u'D:\\_tmp190\\ut_export_pages190\\pages',
    'ot': u'D:\\_tmp190\\ot_export_pages190\\pages',
    'dr2': u'D:\\_tmp190\\dr2_export_pages190\\pages',
    'dr3': u'D:\\_tmp190\\dr3_export_pages190\\pages',
}


def arg(key, default=None):
    a = sys.argv[1:]
    if key not in a:
        return default
    i = a.index(key)
    return a[i + 1] if i + 1 < len(a) else default


def read_uv(path):
    """uv.tsv: name, frame, pageIdx, sx, sy, sw, sh（首行 # 注释）。"""
    rows = []
    for l in io.open(path, encoding='utf-8').read().splitlines():
        if not l.strip() or l.startswith('#'):
            continue
        f = l.split('\t')
        if len(f) < 7:
            continue
        rows.append({'name': f[0], 'frame': int(f[1]), 'page': int(f[2]),
                     'sx': int(f[3]), 'sy': int(f[4]),
                     'sw': int(f[5]), 'sh': int(f[6])})
    return rows


def main():
    tag = arg('--tag')
    only = arg('--only')
    if not tag:
        print(__doc__)
        return 2
    uv_path = os.path.join(EV, 'uv', tag + '.tsv')
    if not os.path.isfile(uv_path):
        # 兼容旧落点
        uv_path = u'D:\\_tmp190\\hy_uv\\uv.tsv' if tag == 'hy' else uv_path
    if not os.path.isfile(uv_path):
        print('[停手] 找不到 uv 表：%s' % uv_path)
        return 2
    pdir = PAGE_DIR.get(tag)
    if not pdir or not os.path.isdir(pdir):
        print('[停手] 找不到页面目录：%s' % pdir)
        return 2

    uv = read_uv(uv_path)
    if only:
        uv = [r for r in uv if only in r['name']]
    print('[uv] %d 条  %s' % (len(uv), uv_path))
    print('[保] %s' % pdir)

    out = os.path.join(OUT_ROOT, tag)
    os.makedirs(out)

    cache = {}
    written = 0
    bad_size = []
    blank = []
    man = []
    for r in uv:
        pi = r['page']
        if pi not in cache:
            p = os.path.join(pdir, 'p%03d.png' % pi)
            if not os.path.isfile(p):
                cache[pi] = None
            else:
                cache[pi] = Image.open(p).convert('RGBA')
        page = cache[pi]
        if page is None:
            bad_size.append((r['name'], pi, 'no-page'))
            continue
        W, H = page.size
        # ★ 闸①：UV 矩形必须真的落在页内，越界就是 UV 表或页序错了
        if r['sx'] < 0 or r['sy'] < 0 or r['sx'] + r['sw'] > W or r['sy'] + r['sh'] > H:
            bad_size.append((r['name'], pi, 'uv %d,%d %dx%d > page %dx%d'
                             % (r['sx'], r['sy'], r['sw'], r['sh'], W, H)))
            continue
        crop = page.crop((r['sx'], r['sy'], r['sx'] + r['sw'], r['sy'] + r['sh']))

        # ★ 闸②：裁出来必须**不是全透明**（全透明说明 UV 指了一片空白 ⇒ 表错了）
        px = list(crop.getdata())
        n_op = sum(1 for p in px if p[3] > 16)
        if n_op == 0:
            blank.append((r['name'], pi))
            continue
        ncol = len(set(px))

        fn = '%s_f%d.png' % (r['name'], r['frame'])
        crop.save(os.path.join(out, fn))
        written += 1
        man.append({'name': r['name'], 'frame': r['frame'], 'page': pi,
                    'rect': [r['sx'], r['sy'], r['sw'], r['sh']],
                    'wxh': [r['sw'], r['sh']], 'colors': ncol,
                    'opaque_pct': round(100.0 * n_op / len(px), 1),
                    'file': fn})

    # ★ 闸③：裁出张数必须等于 UV 数据行数（否则就是有行被跳过了）
    print('')
    print('[结果] 写出 %d / %d' % (written, len(uv)))
    if bad_size:
        print('[越界/无页] %d 条：' % len(bad_size))
        for b in bad_size[:6]:
            print('   %s' % (b,))
    if blank:
        print('[全透明] %d 条：%s' % (len(blank), blank[:6]))
    if written != len(uv):
        print('[报红] 张数对不上 ⇒ 不许当成功')

    # 颜色分布：用来区分"彩色肖像"与"黑白/遮罩"
    cb = collections.Counter()
    for m in man:
        cb['彩色(>2)' if m['colors'] > 2 else '2色'] += 1
    print('[颜色] ' + '  '.join('%s=%d' % (k, v) for k, v in sorted(cb.items())))

    mf = os.path.join(out, '_manifest.json')
    with io.open(mf, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(json.dumps(man, ensure_ascii=False, indent=1))
    print('[manifest] %s' % mf)
    return 0 if written == len(uv) else 6


if __name__ == '__main__':
    sys.exit(main())
