# -*- coding: utf-8 -*-
"""勘查解包后的三个游戏：引擎版本 / 素材分布 / 可用的文本与房间数据。"""
import io
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

EX = r'E:\Download\apk_extract'


def size(p):
    try:
        return os.path.getsize(p)
    except OSError:
        return -1


def head(p, n=64):
    try:
        with open(p, 'rb') as f:
            return f.read(n)
    except OSError:
        return b''


print('=' * 78)
print('[1] GameMaker data 文件头（判断引擎/版本）')
for name in ('undertale', 'huanghun'):
    for rel in (r'assets\game.droid',):
        p = os.path.join(EX, name, rel)
        if os.path.isfile(p):
            b = head(p, 32)
            print('  %-10s %-22s %10.1f MB' % (name, rel, size(p) / 1048576.0))
            print('       hex=%s' % b[:16].hex())
            print('       raw=%r' % b[:32])

print()
print('=' * 78)
print('[2] undertale assets/ 非 ogg 的文件')
d = os.path.join(EX, 'undertale', 'assets')
if os.path.isdir(d):
    for f in sorted(os.listdir(d)):
        p = os.path.join(d, f)
        if not f.lower().endswith(('.ogg', '.mp3')):
            print('   %-32s %10.1f MB' % (f, size(p) / 1048576.0))

print()
print('=' * 78)
print('[3] huanghun assets/ 结构')
d = os.path.join(EX, 'huanghun', 'assets')
if os.path.isdir(d):
    for root, dirs, files in os.walk(d):
        lvl = root[len(d):].count(os.sep)
        if lvl > 2:
            dirs[:] = []
            continue
        rel = os.path.relpath(root, d)
        print('  [%s] %d dirs %d files' % (rel, len(dirs), len(files)))
        for f in sorted(files)[:12]:
            print('       %-44s %9.1f KB' % (f, size(os.path.join(root, f)) / 1024.0))

print()
print('=' * 78)
print('[4] outertale assets/www 入口文件')
d = os.path.join(EX, 'outertale', 'assets', 'www')
if os.path.isdir(d):
    for f in sorted(os.listdir(d)):
        p = os.path.join(d, f)
        if os.path.isfile(p) and f.lower().endswith(('.html', '.js', '.css')):
            print('   %-30s %9.1f KB' % (f, size(p) / 1024.0))
    for f in ('index.html',):
        p = os.path.join(d, f)
        if os.path.isfile(p):
            t = io.open(p, encoding='utf-8', errors='replace').read()
            print('   --- index.html 前 800 ---')
            print(t[:800])
