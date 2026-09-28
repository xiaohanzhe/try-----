# -*- coding: utf-8 -*-
u"""第61轮 · 段A2：三个 apk 的 assets/ 清单（只读，不提取）。

目的：判断「哪些资源可以零依赖直接取」，哪些必须靠 UTMT 解 game.droid。
"""
from __future__ import print_function

import io
import json
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EVID = os.path.join(ROUND, u'_evidence')
OUT = os.path.join(EVID, u'assets61.json')

APKS = [
    (u'Undertale', u'C:\\Users\\23002\\Downloads\\undertale.apk'),
    (u'outertale', u'C:\\Users\\23002\\Downloads\\outertale.apk'),
    (u'黄魂', u'C:\\Users\\23002\\Downloads\\黄魂.apk'),
]


def human(n):
    v = float(n)
    for u in (u'B', u'KB', u'MB', u'GB'):
        if v < 1024.0 or u == u'GB':
            return u'%.2f %s' % (v, u)
        v /= 1024.0
    return u'? '


def main():
    out = {}
    print(u'=' * 78)
    print(u'第61轮 · 段A2 apk assets 清单')
    print(u'=' * 78)
    for label, path in APKS:
        print(u'\n### %s  (%s)' % (label, path))
        if not os.path.exists(path):
            print(u'  !! 不存在'); out[label] = {u'exists': False}; continue
        zf = zipfile.ZipFile(path)
        names = zf.namelist()
        info = {i.filename: i.file_size for i in zf.infolist()}

        # 顶层分类
        tops = {}
        for n in names:
            t = n.split(u'/')[0]
            tops[t] = tops.get(t, 0) + 1
        print(u'  顶层: %s' % u', '.join(u'%s(%d)' % (k, v) for k, v in sorted(tops.items())))

        # assets/ 下一级
        lvl1 = {}
        for n in names:
            if n.startswith(u'assets/'):
                rest = n[len(u'assets/'):]
                if not rest:
                    continue
                k = rest.split(u'/')[0]
                lvl1[k] = lvl1.get(k, 0) + 1
        print(u'  assets/*: %s' % u', '.join(u'%s(%d)' % (k, v) for k, v in sorted(lvl1.items())))

        # 扩展名统计（全 apk）
        exts = {}
        for n in names:
            e = os.path.splitext(n)[1].lower()
            exts[e] = exts.get(e, 0) + 1

        # assets 下可直接取的大文件（非 game.droid）
        big = sorted(
            [(n, info[n]) for n in names if n.startswith(u'assets/') and info[n] > 200 * 1024],
            key=lambda x: -x[1])[:25]
        print(u'  assets 大文件(>200KB):')
        for n, sz in big:
            print(u'      %-62s %s' % (n, human(sz)))

        # 音频类
        auds = [n for n in names if n.lower().endswith((u'.ogg', u'.mp3', u'.wav', u'.flac'))]
        print(u'  音频条目: %d 个（ogg=%d mp3=%d wav=%d）'
              % (len(auds),
                 sum(1 for n in auds if n.lower().endswith(u'.ogg')),
                 sum(1 for n in auds if n.lower().endswith(u'.mp3')),
                 sum(1 for n in auds if n.lower().endswith(u'.wav'))))

        # www 目录（outertale）
        if any(n.startswith(u'assets/www/') for n in names):
            www = sorted(n for n in names if n.startswith(u'assets/www/'))
            print(u'  assets/www 条目: %d 个' % len(www))
            for n in www[:25]:
                print(u'      %-62s %s' % (n, human(info.get(n, 0))))

        out[label] = {
            u'exists': True,
            u'entries': len(names),
            u'tops': tops,
            u'assets_lvl1': lvl1,
            u'exts': exts,
            u'assets_big': big,
            u'audio_count': len(auds),
            u'www': [n for n in names if n.startswith(u'assets/www/')][:120],
        }
        print(u'  扩展名:', u', '.join(u'%s:%d' % (k, v) for k, v in sorted(exts.items())[:20]))

    with io.open(OUT, u'w', encoding=u'utf-8') as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=2))
    print(u'\n证据 -> %s' % OUT)
    return 0


if __name__ == u'__main__':
    raise SystemExit(main())
