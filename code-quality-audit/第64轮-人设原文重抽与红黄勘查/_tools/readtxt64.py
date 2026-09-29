# -*- coding: utf-8 -*-
u"""第64轮 · 段3：读 `红与黄.apk` 里的说明文本（你好啊.txt / credits.txt / INSTALLATION.txt）。只读。"""
from __future__ import print_function
import io, sys, zipfile

try:
    sys.stdout.reconfigure(encoding=u'utf-8', errors=u'replace')
except Exception:
    pass

APK = u'C:\\Users\\23002\\Downloads\\红与黄.apk'
WANT = [u'你好啊.txt', u'assets/credits.txt', u'assets/INSTALLATION.txt']
zf = zipfile.ZipFile(APK)
have = zf.namelist()

for w in WANT:
    cand = [n for n in have if n.endswith(w.split(u'/')[-1])]
    if not cand:
        print(u'!! 未找到 %s' % w)
        continue
    for n in cand[:2]:
        b = zf.read(n)
        print(u'=' * 70)
        print(u'FILE %s  (%d 字节)' % (n, len(b)))
        print(u'=' * 70)
        for enc in (u'utf-8', u'utf-8-sig', u'gbk', u'big5'):
            try:
                t = b.decode(enc)
                print(u'[编码 %s]' % enc)
                print(t[:4000])
                break
            except UnicodeDecodeError:
                continue
        else:
            print(u'[无法解码] 前 300 字节 = %r' % b[:300])
        print()
