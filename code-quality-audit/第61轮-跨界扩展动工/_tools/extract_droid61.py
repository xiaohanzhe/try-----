# -*- coding: utf-8 -*-
u"""第61轮 · 从 apk 提取 assets/game.droid（GameMaker 数据文件）到 E 盘。

产物 -> E:\\Download\\_extract61\\_data\\<源>\\game.droid
注意：E 盘 dirty 会让 makedirs/写入偶发失败 ⇒ 全部带重试。
"""
from __future__ import print_function

import io
import os
import time
import zipfile

OUT = u'E:\\Download\\_extract61\\_data'
JOBS = [
    (u'undertale', u'C:\\Users\\23002\\Downloads\\undertale.apk'),
    (u'undertale_yellow', u'C:\\Users\\23002\\Downloads\\黄魂.apk'),
]


def ensure_dir(d, tries=8, gap=0.35):
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


def main():
    ensure_dir(OUT)
    for name, apk in JOBS:
        print(u'\n### %s' % name)
        if not os.path.exists(apk):
            print(u'  !! apk 不存在')
            continue
        if not ensure_dir(os.path.join(OUT, name)):
            print(u'  !! 目录创建失败（E 盘 dirty）')
            continue
        dst = os.path.join(OUT, name, u'game.droid')
        zf = zipfile.ZipFile(apk)
        member = u'assets/game.droid'
        if member not in zf.namelist():
            print(u'  !! apk 内无 %s' % member)
            continue
        t0 = time.time()
        with zf.open(member) as src, io.open(dst, u'wb') as fh:
            n = 0
            while True:
                chunk = src.read(1 << 20)
                if not chunk:
                    break
                fh.write(chunk)
                n += len(chunk)
        print(u'  OK %s  %.1f MB  %.1fs' % (dst, n / 1048576.0, time.time() - t0))
    return 0


if __name__ == u'__main__':
    raise SystemExit(main())
