# -*- coding: utf-8 -*-
u"""第64轮 · 段2：把用户给的两份原文**存证入库** + 勘查 `红与黄.apk`。

背景：第62轮吃过一次「人设原文已不在本机」的亏 ⇒ 这次用户重新提供后**立刻存证**。

只读用户文件；写入仅限本轮的 `_evidence/`。
"""
from __future__ import print_function

import hashlib
import io
import json
import os
import shutil
import sys
import zipfile

try:
    sys.stdout.reconfigure(encoding=u'utf-8', errors=u'replace')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EVID = os.path.join(ROUND, u'_evidence')

SRC = [(u'C:\\Users\\23002\\Desktop\\其余人物设定.txt', u'src_personas64.txt'),
       (u'C:\\Users\\23002\\Desktop\\人物关系叙述.txt', u'src_relations64.txt')]
APK = u'C:\\Users\\23002\\Downloads\\红与黄.apk'
KEYS = (u'ghost', u'chara', u'spirit', u'phantom', u'soul', u'determin', u'narrator',
        u'幽灵', u'决心')


def sha(p):
    return hashlib.sha256(io.open(p, 'rb').read()).hexdigest()


def main():
    if not os.path.isdir(EVID):
        os.makedirs(EVID)
    rep = {u'staged': []}

    print(u'=== 段2-A 原文存证（防再次丢失）===')
    for s, dst in SRC:
        if not os.path.isfile(s):
            print(u'  !! 缺失 %s' % s)
            continue
        d = os.path.join(EVID, dst)
        shutil.copyfile(s, d)
        h = sha(s)
        n = os.path.getsize(s)
        ok = (sha(d) == h and os.path.getsize(d) == n)
        print(u'  %s' % dst)
        print(u'     %d 字节  sha256=%s' % (n, h))
        print(u'     复制校验：%s' % (u'一致 OK' if ok else u'★不一致 FAIL'))
        rep[u'staged'].append({u'file': dst, u'bytes': n, u'sha256': h, u'copy_ok': bool(ok)})

    print()
    print(u'=== 段2-B 勘查 红与黄.apk ===')
    if not os.path.isfile(APK):
        print(u'  !! 不存在 %s' % APK)
    else:
        print(u'  大小 %d 字节（%.1f MB）' % (os.path.getsize(APK),
                                              os.path.getsize(APK) / 1048576.0))
        zf = zipfile.ZipFile(APK)
        names = zf.namelist()
        info = {i.filename: i.file_size for i in zf.infolist()}
        print(u'  条目 %d 个' % len(names))
        tops = {}
        for n in names:
            tops[n.split(u'/')[0]] = tops.get(n.split(u'/')[0], 0) + 1
        print(u'  顶层：%s' % u', '.join(u'%s(%d)' % (k, v) for k, v in sorted(tops.items())[:20]))
        lvl1 = {}
        for n in names:
            if n.startswith(u'assets/'):
                r = n[len(u'assets/'):]
                k = r.split(u'/')[0] if r else u''
                lvl1[k] = lvl1.get(k, 0) + 1
        print(u'  assets/*：%s' % u', '.join(u'%s(%d)' % (k, v) for k, v in sorted(lvl1.items())[:20]))
        exts = {}
        for n in names:
            e = os.path.splitext(n)[1].lower()
            exts[e] = exts.get(e, 0) + 1
        print(u'  扩展名：%s' % u', '.join(u'%s:%d' % (k, v) for k, v in
                                          sorted(exts.items(), key=lambda x: -x[1])[:14]))
        big = sorted([(n, info[n]) for n in names if info[n] > 1024 * 1024],
                     key=lambda x: -x[1])[:12]
        print(u'  大文件(>1MB)：')
        for n, sz in big:
            print(u'      %-64s %.1f MB' % (n, sz / 1048576.0))
        print()
        print(u'  --- 关键词命中（按文件名）---')
        hits = {}
        for k in KEYS:
            hit = [n for n in names if k in n.lower()]
            if hit:
                hits[k] = hit[:20]
                print(u'    %-10s %3d 个：%s' % (k, len(hit), u', '.join(hit[:8])))
        rep[u'apk'] = {u'bytes': os.path.getsize(APK), u'entries': len(names),
                       u'tops': tops, u'assets_lvl1': lvl1, u'exts': exts,
                       u'big': big, u'keyword_hits': hits}
        # 找 GameMaker 数据文件
        gm = [n for n in names if n.endswith((u'game.droid', u'.win', u'data.win'))]
        print(u'    GameMaker 数据文件：%r' % (gm,))
        rep[u'apk'][u'gm_data'] = gm

    p = os.path.join(EVID, u'stage64.json')
    with io.open(p, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(rep, ensure_ascii=False, indent=1))
    print()
    print(u'证据 -> %s' % p)
    return 0


if __name__ == u'__main__':
    raise SystemExit(main())
