# -*- coding: utf-8 -*-
"""把三个 APK 解包到 E 盘，并做一级清点（只列结构，不猜内容）。"""
import os
import zipfile

OUT = r'E:\Download\apk_extract'
APKS = [
    ('undertale', r'C:\Users\23002\Downloads\undertale.apk'),
    ('outertale', r'C:\Users\23002\Downloads\outertale.apk'),
    ('huanghun',  r'C:\Users\23002\Downloads\黄魂.apk'),
]

os.makedirs(OUT, exist_ok=True)

for name, src in APKS:
    dst = os.path.join(OUT, name)
    print('=' * 70)
    print('[%s] %s -> %s' % (name, src, dst))
    if not os.path.exists(src):
        print('  !! 源文件不存在')
        continue
    os.makedirs(dst, exist_ok=True)
    try:
        with zipfile.ZipFile(src) as z:
            names = z.namelist()
            print('  条目数 =', len(names))
            # 顶层分布
            top = {}
            for n in names:
                k = n.split('/')[0] if '/' in n else '(root)'
                top[k] = top.get(k, 0) + 1
            for k, v in sorted(top.items(), key=lambda x: -x[1])[:20]:
                print('    %-28s %d' % (k, v))
            z.extractall(dst)
        print('  解包完成')
    except Exception as e:
        print('  !! 解包失败:', repr(e))

print()
print('=' * 70)
print('总量统计')
for name, _ in APKS:
    d = os.path.join(OUT, name)
    if not os.path.isdir(d):
        continue
    n = 0
    sz = 0
    for r, _, fs in os.walk(d):
        for f in fs:
            n += 1
            try:
                sz += os.path.getsize(os.path.join(r, f))
            except OSError:
                pass
    print('  %-12s %6d 文件  %8.1f MB' % (name, n, sz / 1048576.0))
