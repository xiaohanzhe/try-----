# -*- coding: utf-8 -*-
u"""第61轮 · 提取零依赖明文素材（apk 内可直取的部分）到 E 盘工作区。

不触碰仓库；不修改任何源文件。产物 -> E:\\Download\\_extract61\\<源>\\
"""
from __future__ import print_function

import io
import json
import os
import sys
import time
import zipfile

BASE = u'E:\\Download\\_extract61'


def ensure_dir(d, tries=8, gap=0.35):
    u"""E 盘 dirty 会让新建目录偶发 WinError 1 —— 重试 + 复核，绝不假装成功。"""
    if os.path.isdir(d):
        return True
    for _ in range(tries):
        try:
            os.makedirs(d)
        except OSError:
            pass
        if os.path.isdir(d):
            return True
        time.sleep(gap)
    return os.path.isdir(d)

JOBS = [
    {
        u'name': u'undertale',
        u'apk': u'C:\\Users\\23002\\Downloads\\undertale.apk',
        u'rule': lambda n: (
            (n.startswith(u'assets/') and n.lower().endswith((u'.ogg', u'.png')))
            or n in (u'assets/options.ini', u'assets/abc_123_a.ogg')
        ),
    },
    {
        u'name': u'undertale_yellow',   # 黄魂
        u'apk': u'C:\\Users\\23002\\Downloads\\黄魂.apk',
        u'rule': lambda n: (
            n.startswith((u'assets/mus/', u'assets/snd/', u'assets/lang/'))
            or n in (u'assets/options.ini', u'assets/splash.png', u'assets/portrait_splash.png')
        ),
    },
    {
        u'name': u'outertale',
        u'apk': u'C:\\Users\\23002\\Downloads\\outertale.apk',
        u'rule': lambda n: n.startswith(u'assets/www/') and not n.endswith(u'/'),
    },
]


def extract_one(job):
    name, apk, rule = job[u'name'], job[u'apk'], job[u'rule']
    print(u'\n### %s  <- %s' % (name, apk))
    if not os.path.exists(apk):
        print(u'  !! 源不存在'); return (False, 0, 0)
    outdir = os.path.join(BASE, name)
    if not ensure_dir(outdir):
        print(u'  !! 无法创建输出目录 %s（E 盘 dirty）' % outdir)
        return (False, 0, 0)
    zf = zipfile.ZipFile(apk)
    names = [n for n in zf.namelist() if not n.endswith(u'/')]
    picked = [n for n in names if rule(n)]
    print(u'  命中 %d / %d 条目' % (len(picked), len(names)))
    n_ok = 0
    total = 0
    t0 = time.time()
    for i, n in enumerate(picked):
        rel = n[len(u'assets/'):] if n.startswith(u'assets/') else n
        dst = os.path.join(outdir, rel.replace(u'/', os.sep))
        d = os.path.dirname(dst)
        if d and not os.path.isdir(d):
            ensure_dir(d)
        try:
            data = zf.read(n)
            with io.open(dst, u'wb') as fh:
                fh.write(data)
            n_ok += 1
            total += len(data)
        except Exception as e:  # noqa: BLE001
            print(u'  !! 失败 %s : %s' % (n, e))
        if (i + 1) % 400 == 0:
            print(u'    ...%d/%d  %.1fs' % (i + 1, len(picked), time.time() - t0))
    print(u'  ✅ 写出 %d 个文件，%.1f MB，用时 %.1fs'
          % (n_ok, total / 1048576.0, time.time() - t0))
    return (True, n_ok, total)


def main():
    print(u'=' * 78)
    print(u'第61轮 · 零依赖素材提取 -> %s' % BASE)
    print(u'=' * 78)
    summary = {}
    for job in JOBS:
        ok, cnt, tot = extract_one(job)
        summary[job[u'name']] = {u'ok': ok, u'files': cnt, u'bytes': tot}
    print(u'\n===== 汇总 =====')
    for k, v in summary.items():
        print(u'  %-18s ok=%s files=%d  %.1f MB' % (k, v[u'ok'], v[u'files'], v[u'bytes'] / 1048576.0))
    if not os.path.isdir(BASE):
        ensure_dir(BASE)
    with io.open(os.path.join(BASE, u'_summary61.json'), u'w', encoding=u'utf-8') as fh:
        fh.write(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == u'__main__':
    raise SystemExit(main())
