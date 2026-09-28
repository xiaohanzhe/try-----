# -*- coding: utf-8 -*-
u"""第61轮 · 段A 素材源勘查（只读；不改动、不解包任何源文件）。

纪律：
- 只判断「能读到什么」，绝不写入源目录。
- 某源不存在 -> exists=False 且 ok=False（绝不因为"还没放"就放绿）。
- 自检（正/负控制成对）：A1 伪造路径必不存在 / A2 空 zip 必被识别 /
  A3 非 zip 必不被识别 / A4 本脚本自身存在。
"""
from __future__ import print_function

import io
import json
import os
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EVID = os.path.join(ROUND, u'_evidence')
if not os.path.isdir(EVID):
    os.makedirs(EVID)
OUT = os.path.join(EVID, u'survey61.json')

SOURCES = [
    (u'S1', u'OneShot (PC 目录)',
     u'C:\\Users\\23002\\Desktop\\项目文件夹\\niko的秘密\\OneShot.World.Machine.Edition.Build.16512634'),
    (u'S2', u'Undertale (apk)', u'C:\\Users\\23002\\Downloads\\undertale.apk'),
    (u'S3', u'outertale (apk)', u'C:\\Users\\23002\\Downloads\\outertale.apk'),
    (u'S4', u'黄魂 (apk)', u'C:\\Users\\23002\\Downloads\\黄魂.apk'),
]

#: 关心的扩展名（用于目录源的关键文件探测）
INTERESTING_EXT = (u'.win', u'.exe', u'.dll', u'.apk', u'.obb', u'.json', u'.png', u'.ogg')


def human(n):
    v = float(n)
    for u in (u'B', u'KB', u'MB', u'GB'):
        if v < 1024.0 or u == u'GB':
            return u'%.2f %s' % (v, u)
        v /= 1024.0
    return u'%.2f GB' % v


def dir_size(path, budget_s=8.0, max_files=300000):
    """有界遍历：超时或超量即停，如实返回 truncated。"""
    t0 = time.time()
    total = 0
    files = 0
    trunc = False
    for root, dirs, fs in os.walk(path):
        for f in fs:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
            files += 1
            if files >= max_files or (time.time() - t0) > budget_s:
                trunc = True
                break
        if trunc:
            break
    return total, files, trunc


def find_interesting(path, max_depth=4, limit=40):
    """限深找关键文件（data.win / exe / dll ...）。"""
    base_depth = path.rstrip(os.sep).count(os.sep)
    hits = []
    for root, dirs, fs in os.walk(path):
        if root.count(os.sep) - base_depth >= max_depth:
            dirs[:] = []
        for f in fs:
            if f.lower().endswith(INTERESTING_EXT):
                rel = os.path.relpath(os.path.join(root, f), path)
                try:
                    sz = os.path.getsize(os.path.join(root, f))
                except OSError:
                    sz = -1
                hits.append([rel, sz])
                if len(hits) >= limit:
                    return hits
    return hits


def survey_one(sid, label, path):
    d = {u'label': label, u'path': path, u'exists': os.path.exists(path)}
    if not d[u'exists']:
        d[u'ok'] = False
        d[u'note'] = u'路径不存在 —— 需用户提供/确认'
        return d
    d[u'is_dir'] = os.path.isdir(path)
    if d[u'is_dir']:
        try:
            top = sorted(os.listdir(path))
        except OSError as e:
            top = []
            d[u'listdir_err'] = str(e)
        d[u'top_count'] = len(top)
        d[u'top_entries'] = top[:40]
        size, files, trunc = dir_size(path)
        d[u'bytes'] = size
        d[u'human'] = human(size)
        d[u'file_count'] = files
        d[u'size_truncated'] = trunc
        d[u'interesting'] = find_interesting(path)
    else:
        try:
            d[u'bytes'] = os.path.getsize(path)
        except OSError:
            d[u'bytes'] = -1
        d[u'human'] = human(d[u'bytes']) if d[u'bytes'] >= 0 else u'n/a'
        try:
            d[u'is_zip'] = zipfile.is_zipfile(path)
        except OSError as e:
            d[u'is_zip'] = False
            d[u'ziperr'] = str(e)
        if d[u'is_zip']:
            try:
                zf = zipfile.ZipFile(path)
                names = zf.namelist()
                d[u'zip_entries'] = len(names)
                tops = sorted(set(n.split(u'/')[0] for n in names))
                d[u'zip_top'] = tops[:60]
                d[u'zip_top_count'] = len(tops)
                d[u'has_dex'] = any(n.endswith(u'.dex') for n in names)
                d[u'has_assets'] = any(n.startswith(u'assets/') for n in names)
                d[u'has_lib'] = any(n.startswith(u'lib/') for n in names)
                d[u'has_meta'] = any(n.startswith(u'META-INF/') for n in names)
                infos = sorted(zf.infolist(), key=lambda i: -i.file_size)[:15]
                d[u'largest'] = [[i.filename, i.file_size] for i in infos]
                d[u'sample'] = names[:60]
            except Exception as e:  # noqa: BLE001 — 如实记录任何解压失败
                d[u'zip_read_err'] = u'%s: %s' % (type(e).__name__, e)
    d[u'ok'] = True
    return d


def selfcheck():
    sc = []
    fake = u'C:\\__no_such_dir_61_survey__'
    sc.append([u'A1 伪造路径必不存在', (not os.path.exists(fake)) is True])

    p_zip = os.path.join(EVID, u'_tmp_empty61.zip')
    with zipfile.ZipFile(p_zip, u'w') as z:
        pass
    sc.append([u'A2 空 zip 必被识别为 zip', zipfile.is_zipfile(p_zip) is True])
    os.remove(p_zip)

    p_txt = os.path.join(EVID, u'_tmp_notzip61.txt')
    with io.open(p_txt, u'w', encoding=u'utf-8') as fh:
        fh.write(u'this is definitely not a zip archive')
    sc.append([u'A3 非 zip 必不被识别为 zip', (not zipfile.is_zipfile(p_txt)) is True])
    os.remove(p_txt)

    sc.append([u'A4 本脚本自身存在', os.path.exists(os.path.abspath(__file__)) is True])
    return sc


def main():
    out = {u'round': 61, u'stage': u'A 素材源勘查', u'sources': {}, u'selfcheck': [], u'ok': True}
    print(u'=' * 78)
    print(u'第61轮 · 段A 素材源勘查')
    print(u'=' * 78)
    for sid, label, path in SOURCES:
        d = survey_one(sid, label, path)
        out[u'sources'][sid] = d
        print(u'\n[%s] %s' % (sid, label))
        print(u'    path      : %s' % path)
        print(u'    exists    : %s' % d[u'exists'])
        if d[u'exists'] and d[u'is_dir']:
            print(u'    size      : %s  (files=%d, truncated=%s)'
                  % (d[u'human'], d[u'file_count'], d[u'size_truncated']))
            print(u'    top(%d)   : %s' % (d[u'top_count'], u', '.join(d[u'top_entries'][:12])))
            if d.get(u'interesting'):
                print(u'    key files :')
                for rel, sz in d[u'interesting'][:12]:
                    print(u'        %-58s %s' % (rel, human(sz) if sz >= 0 else u'?'))
        elif d[u'exists']:
            print(u'    size      : %s' % d[u'human'])
            print(u'    is_zip    : %s' % d.get(u'is_zip'))
            if d.get(u'is_zip'):
                print(u'    entries   : %d  (top dirs=%d)'
                      % (d[u'zip_entries'], d.get(u'zip_top_count', -1)))
                print(u'    top dirs  : %s' % u', '.join(d.get(u'zip_top', [])[:14]))
                print(u'    dex/assets/lib/meta : %s / %s / %s / %s'
                      % (d.get(u'has_dex'), d.get(u'has_assets'), d.get(u'has_lib'), d.get(u'has_meta')))
                print(u'    largest   :')
                for nm, sz in d.get(u'largest', [])[:8]:
                    print(u'        %-58s %s' % (nm, human(sz)))
            if d.get(u'zip_read_err'):
                print(u'    !! zip read err: %s' % d[u'zip_read_err'])
        else:
            print(u'    !! 不存在 —— %s' % d.get(u'note', u''))
        out[u'ok'] = out[u'ok'] and d[u'ok']

    print(u'\n' + u'-' * 78)
    print(u'自检：')
    sc = selfcheck()               # ★ 只调一次：复用同一份结果打印 + 落盘
    out[u'selfcheck'] = [list(x) for x in sc]
    all_sc = True
    for name, ok in sc:
        all_sc = all_sc and ok
        print(u'  [%s] %s' % (u'PASS' if ok else u'FAIL', name))
    out[u'selfcheck_ok'] = all_sc
    print(u'\n结果：sources_ok=%s  selfcheck_ok=%s' % (out[u'ok'], all_sc))

    with io.open(OUT, u'w', encoding=u'utf-8') as fh:
        fh.write(json.dumps(out, ensure_ascii=False, indent=2))
    print(u'证据 -> %s' % OUT)
    return 0 if (out[u'ok'] and all_sc) else 1


if __name__ == u'__main__':
    raise SystemExit(main())
