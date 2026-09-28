# -*- coding: utf-8 -*-
u"""第61轮 · 段A3：直读 zip 内样本，判断 outertale / 黄魂 的数据结构（不落盘）。"""
from __future__ import print_function

import io
import json
import os
import zipfile


def show(label, text, n=1400):
    print(u'\n----- %s -----' % label)
    t = text if len(text) <= n else text[:n] + u'\n...(截断)'
    print(t)


def main():
    print(u'=' * 78)
    print(u'第61轮 · 段A3 zip 内样本直读')
    print(u'=' * 78)

    # ---- outertale: assets/www 样本 ----
    ap = u'C:\\Users\\23002\\Downloads\\outertale.apk'
    if os.path.exists(ap):
        zf = zipfile.ZipFile(ap)
        names = zf.namelist()
        picks = [u'assets/www/86-D16Sv77D.json',
                 u'assets/www/CORE-DtkqgNq-.json',
                 u'assets/www/CORE_critical-3N0OlLud.json']
        for p in picks:
            if p in names:
                try:
                    raw = zf.read(p)
                    show(p, raw.decode(u'utf-8', u'replace'))
                except Exception as e:  # noqa: BLE001
                    show(p, u'<读取失败 %s: %s>' % (type(e).__name__, e))
        # 一个 csv 样本
        csvs = [n for n in names if n.endswith(u'.csv')]
        if csvs:
            for p in csvs[:2]:
                try:
                    raw = zf.read(p)
                    show(p + u'  (前 600 字节)', raw[:600].decode(u'utf-8', u'replace'))
                except Exception as e:  # noqa: BLE001
                    show(p, u'<失败 %s>' % e)
        # html / 顶层入口
        for p in (u'assets/www/index.html',):
            if p in names:
                show(p, zf.read(p)[:800].decode(u'utf-8', u'replace'))
        # js 头部（看是不是打包后的 bundle / 是否有房间表）
        js = [n for n in names if n.endswith(u'.js')]
        for p in js[:1]:
            raw = zf.read(p)
            show(p + u'  (前 900 字节)', raw[:900].decode(u'utf-8', u'replace'))

    # ---- 黄魂: lang 样本 ----
    ap2 = u'C:\\Users\\23002\\Downloads\\黄魂.apk'
    if os.path.exists(ap2):
        zf2 = zipfile.ZipFile(ap2)
        n2 = zf2.namelist()
        langs = sorted(set(n.split(u'/')[2] for n in n2 if n.startswith(u'assets/lang/') and n.count(u'/') >= 3))
        print(u'\n### 黄魂 lang 语言: %s' % u', '.join(langs[:20]))
        cand = [n for n in n2 if n.startswith(u'assets/lang/en/')]
        if not cand:
            cand = [n for n in n2 if n.startswith(u'assets/lang/') and n.endswith(u'.json')]
        for p in cand[:2]:
            try:
                d = json.loads(zf2.read(p).decode(u'utf-8', u'replace'))
                keys = list(d.keys())[:15] if isinstance(d, dict) else None
                show(p + u'  (类型=%s, 键数=%s)' % (type(d).__name__, len(d)),
                     u'前 15 键: %s\n样本:\n%s' % (
                         keys,
                         json.dumps({k: d[k] for k in list(d)[:3]}, ensure_ascii=False, indent=1)[:700]
                         if isinstance(d, dict) else str(d)[:700]))
            except Exception as e:  # noqa: BLE001
                show(p, u'<失败 %s>' % e)
    return 0


if __name__ == u'__main__':
    raise SystemExit(main())
