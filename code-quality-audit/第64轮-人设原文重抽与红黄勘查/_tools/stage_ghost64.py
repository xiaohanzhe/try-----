# -*- coding: utf-8 -*-
u"""第64轮 · 把「红与黄」幽灵素材沉淀进仓库。

- 产品资产：幽灵族 PNG -> `ralsei_pet/assets/sprites/ghost/`（原文 sprite 名不改，便于溯源）
- 证据：全部 13 个精灵 + UTMT 日志 -> `code-quality-audit/第64轮.../_evidence/spr64/`
- 溯源：`assets/sprites/ghost/_source.json`（APK / data.droid / sprite / 帧数 / 尺寸 / 原点）

判据：G1 逐字节复制一致；G2 只落"幽灵族"（truechara 只进证据，不进产品）；
      G3 `_source.json` 里每个文件都在磁盘上；G4 含非空 PNG 头。
"""
from __future__ import print_function

import hashlib
import io
import json
import os
import shutil
import sys

try:
    sys.stdout.reconfigure(encoding=u'utf-8', errors=u'replace')
except Exception:
    pass

SRC = os.path.join(os.environ.get(u'TEMP', r'C:\Windows\Temp'), u'spr64_ry')
REPO = u'C:\\Users\\23002\\Desktop\\项目文件夹\\try - 副本'
PROD = os.path.join(REPO, u'ralsei_pet', u'assets', u'sprites', u'ghost')
EVID = os.path.join(REPO, u'code-quality-audit', u'第64轮-人设原文重抽与红黄勘查',
                    u'_evidence', u'spr64')

#: 幽灵产品族（其余 truechara* 只进证据）
GHOST_PREFIX = (u'spr_ghost_chara_', u'spr_ghost_clover_', u'spr_clover_ghostu')

LOG = os.path.join(SRC, u'spr_log64.txt')


def sha(p):
    return hashlib.sha256(io.open(p, 'rb').read()).hexdigest()


def main(argv):
    write = u'--write' in argv
    if not os.path.isdir(SRC):
        print(u'★ 缺源目录 %s' % SRC)
        return 2
    files = sorted(f for f in os.listdir(SRC) if f.endswith(u'.png'))
    print(u'源 %s  %d 个 PNG' % (SRC, len(files)))
    ghost = [f for f in files if f.startswith(GHOST_PREFIX)]
    other = [f for f in files if f not in ghost]
    print(u'  幽灵族 %d ；其余（只进证据）%d = %r' % (len(ghost), len(other), other))

    # 读 UTMT 日志里的帧数/尺寸
    logtxt = io.open(LOG, encoding='utf-8').read() if os.path.isfile(LOG) else u''
    meta = {}
    for ln in logtxt.splitlines():
        p = ln.split(u'\t')
        if p and p[0] == u'OK':
            d = {}
            for kv in p[2:]:
                if u'=' in kv:
                    k, _, v = kv.partition(u'=')
                    d[k] = v
            meta[p[1]] = d

    ok = []
    for f in files:
        s = os.path.join(SRC, f)
        if os.path.getsize(s) < 8 or io.open(s, 'rb').read(8) != b'\x89PNG\r\n\x1a\n':
            print(u'  ★ 非 PNG: %s' % f)
            return 3
    print(u'  [G4] 全部 %d 个文件都是真 PNG（魔数校验）' % len(files))

    if not write:
        print(u'（dry-run）产品目录将写 %d 个文件到 %s' % (len(ghost), PROD))
        print(u'  证据目录将写 %d 个文件到 %s' % (len(files) + 2, EVID))
        return 0

    for d in (PROD, EVID):
        if not os.path.isdir(d):
            os.makedirs(d)

    src_map = {}
    for f in files:
        s = os.path.join(SRC, f)
        e = os.path.join(EVID, f)
        shutil.copyfile(s, e)
        src_map[f] = sha(s)
        if e not in ():
            assert io.open(s, 'rb').read() == io.open(e, 'rb').read(), f
    for f in ghost:
        s = os.path.join(SRC, f)
        p = os.path.join(PROD, f)
        shutil.copyfile(s, p)
        assert io.open(s, 'rb').read() == io.open(p, 'rb').read(), f
        ok.append(f)
    print(u'  [G1] 产品 %d 份 / 证据 %d 份，逐字节复制一致' % (len(ok), len(files)))

    # UTMT 日志也进证据
    if os.path.isfile(LOG):
        shutil.copyfile(LOG, os.path.join(EVID, u'spr_log64.txt'))

    prov = {
        u'note': u'第64轮取材：用户「我把 chara 改了一下，就用红与黄.apk 里面的幽灵就好」',
        u'source_apk': u'C:\\Users\\23002\\Downloads\\红与黄.apk（235,686,156 字节；实为「Undertale Red & Yellow」，署名 C-G_O_A_T）',
        u'source_datafile': u'assets/game.droid（134,313,139 字节）',
        u'extractor': u'UndertaleModCli v0.9.2.0 + code-quality-audit/第64轮-人设原文重抽与红黄勘查/_tools/export_spr64.csx',
        u'files': {},
    }
    for f in sorted(ghost):
        nm = f.rsplit(u'_', 1)[0]
        prov[u'files'][f] = {u'bytes': os.path.getsize(os.path.join(PROD, f)),
                             u'sha256': sha(os.path.join(PROD, f)),
                             u'sprite': nm,
                             u'meta': meta.get(nm, {})}
    with io.open(os.path.join(PROD, u'_source.json'), 'wb') as fh:
        fh.write(json.dumps(prov, ensure_ascii=False, indent=1).encode('utf-8'))

    # G3
    miss = [f for f in prov[u'files'] if not os.path.isfile(os.path.join(PROD, f))]
    print(u'  [G3] _source.json 登记的 %d 个文件都在磁盘 = %s'
          % (len(prov[u'files']), u'PASS' if not miss else u'FAIL %r' % miss))
    print()
    print(u'产品 -> %s  (%d PNG)' % (PROD, len(ghost)))
    print(u'证据 -> %s' % EVID)
    return 0


if __name__ == u'__main__':
    raise SystemExit(main(sys.argv[1:]))
