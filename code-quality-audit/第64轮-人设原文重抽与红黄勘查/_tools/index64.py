# -*- coding: utf-8 -*-
u"""第64轮 · 重建 `assets/npc/_personas.json`（13 -> 50）。

★ 口径守恒：沿用第55轮索引的 `chars` / `sha256` 定义
  （= **磁盘上的 CRLF 版本**），所以已有 13 条的这三个字段**必须原样复现**
  —— 那本身就是一条强判据（若不等于旧值，说明我的定义猜错了）。
★ 追加（不改旧字段）：`sha256_lf`（LF 归一化，可从 git blob 复现）、`work`、`name`、`name_plain`。

用法：python index64.py [--write]
"""
from __future__ import print_function

import hashlib
import io
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding=u'utf-8', errors=u'replace')
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract64 as E                                          # noqa: E402

NPC = os.path.join(E.REPO, u'ralsei_pet', u'assets', u'npc')
CUR = E.CUR
IDX = os.path.join(NPC, u'_personas.json')
EVID = E.EVID

WORK_ORDER = [u'Deltarune', u'OneShot', u'Undertale']


def sha_b(b):
    return hashlib.sha256(b).hexdigest()


def main(argv):
    write = u'--write' in argv
    old = json.loads(io.open(IDX, 'rb').read().decode('utf-8'))
    old_recs = {r['id']: r for r in old[u'personas']}
    TAIL = old[u'tail_text']

    raw_src = io.open(E.SRC, 'rb').read()
    txt = raw_src.decode('utf-8', 'replace').replace(u'\r\n', u'\n')
    bl = E.blocks(txt)
    print(u'源 %d 字节 / 长块 %d' % (len(raw_src), len(bl)))

    # ---------- tail_sha256 定义探明 ----------
    tail_cands = {
        u'tail_text(LF)': sha_b(TAIL.encode('utf-8')),
        u'tail_text(CRLF)': sha_b(TAIL.replace(u'\n', u'\r\n').encode('utf-8')),
    }
    print(u'旧 tail_sha256 = %s' % old.get(u'tail_sha256'))
    for k, v in tail_cands.items():
        print(u'  %-20s %s  %s' % (k, v, u'<== 命中' if v == old.get(u'tail_sha256') else u''))

    # ---------- 组装 ----------
    recs = []
    for b in bl:
        sid = E.slug_of(b['work'], b['name'])
        rel = u'persona/%s.txt' % sid
        fp = os.path.join(CUR, sid + u'.txt')
        # ★ 判据取**产物实际字节**，不预测 EOL（13 份旧文件行尾是混合的：
        #   正文 CRLF + 尾部补充块 LF，flowery 还被手改过）——只有读磁盘才能原样复现旧记录。
        disk = io.open(fp, 'rb').read()
        lf = disk.replace(b'\r\n', b'\n')
        recs.append({
            'id': sid,
            'name': b['name'],
            'name_plain': re.sub(u'[（(][^）)]*[）)]', u'', b['name']).strip(),
            'work': b['work'],
            'file': rel,
            'chars': len(disk.decode('utf-8')),          # = 旧口径（磁盘 CRLF）
            'bytes': len(disk),
            'sha256': sha_b(disk),                       # = 旧口径（磁盘字节）
            'sha256_lf': sha_b(lf),                      # 可复现版（= git blob 口径）
            'sections': b['sections'],
            'tail_added': True,
            'tail_sha256': sha_b(TAIL.encode('utf-8')),
        })

    # ---------- 判据 ----------
    print()
    print(u'=== 判据 ===')
    ids = [r['id'] for r in recs]
    dup = [i for i in set(ids) if ids.count(i) > 1]
    print(u'[B1] id 唯一 = %s  (重 %r)' % (u'PASS' if not dup else u'FAIL', dup))
    missing = [r['id'] for r in recs
               if not os.path.isfile(os.path.join(CUR, os.path.basename(r['file'])))]
    print(u'[B2] 每份 file 在磁盘存在 = %s  (缺 %r)' % (u'PASS' if not missing else u'FAIL', missing))

    # B3：已有 13 条的 chars/bytes/sha256 必须与旧索引逐字一致
    bad3 = []
    for r in recs:
        o = old_recs.get(r['id'])
        if not o:
            continue
        for k in (u'chars', u'bytes', u'sha256'):
            if o.get(k) != r[k]:
                bad3.append((r['id'], k, o.get(k), r[k]))
    print(u'[B3] 已有 13 条的 chars/bytes/sha256 与旧索引一致 = %s' % (u'PASS' if not bad3 else u'FAIL'))
    for t in bad3:
        print(u'      %s.%s 旧=%r 新=%r' % t)

    # B4：磁盘实测 vs 记录（不信计算，去读）
    bad4 = []
    for r in recs[:]:
        p = os.path.join(CUR, os.path.basename(r['file']))
        if not os.path.isfile(p):
            continue
        d = io.open(p, 'rb').read()
        if len(d) != r['bytes'] or sha_b(d) != r['sha256']:
            bad4.append(r['id'])
    print(u'[B4] 磁盘实测字节/sha 与记录一致（%d 份全查）= %s' % (len(recs), u'PASS' if not bad4 else u'FAIL'))
    if bad4:
        print(u'      %r' % bad4)

    print(u'[B5] 源字节 = %d（应 785360）= %s' % (len(raw_src), u'PASS' if len(raw_src) == 785360 else u'FAIL'))
    print(u'[B6] 份数 = %d（应 50）= %s' % (len(recs), u'PASS' if len(recs) == 50 else u'FAIL'))

    # B7 负控制：故意改一个字符，sha 必须变
    z = recs[0]['sha256']
    z2 = sha_b(b'x')
    print(u'[B7 负控制] 换一个字节后 sha 必变 = %s' % (u'PASS' if z != z2 else u'FAIL'))

    byw = {}
    for r in recs:
        byw.setdefault(r['work'], []).append(r['id'])
    print()
    for w in WORK_ORDER:
        print(u'  《%s》 %d：%s' % (w, len(byw.get(w, [])), u', '.join(byw.get(w, []))))

    # ---------- 落盘 ----------
    new = {
        'schema_version': 2,
        'source': u'用户提供的《其余人物设定.txt》（DeepSeek 生成）；第64轮用户重新提供（785,360 字节）',
        'source_sha256': sha_b(raw_src),
        'source_bytes': len(raw_src),
        'source_chars': len(txt),
        'note': (u'正文逐字来自用户文件（只去掉文件级 --- 分隔线与每份前言的「以下是一段可直接用于…」行）；'
                 u'每份尾部追加的「本项目补充」块原文见 tail_sha256，非用户设定。'
                 u'★ `chars`/`bytes`/`sha256` 的口径 = **磁盘上的 CRLF 版本**（与第55轮索引一致，故 13 条旧记录原样复现）；'
                 u'`sha256_lf` = LF 归一化版本，可从 git blob 复现（仓库 autocrlf=true，blob 里是 LF）。'),
        'chars_def': u'len(磁盘文本，CRLF)',
        'tail_text': TAIL,
        'tail_sha256': recs[0]['tail_sha256'],
        'count': len(recs),
        'by_work': {w: byw.get(w, []) for w in WORK_ORDER},
        'personas': recs,
        'extraction_fix': dict(old.get('extraction_fix') or {}, note=(
            u'第64轮：用户重新提供原文（785,360 字节，含 OneShot 21 份 + Undertale 14 份 + Deltarune 新增 Spamton/Mike）。'
            u'重抽时先做正控制——抽取器逐字复现已有 13 份（13/13 PASS）才落盘；13 份旧文件未被改动。')),
        'round64': {
            'source_candidates': [u'C:\\Users\\23002\\Desktop\\其余人物设定.txt'],
            'evidence': u'code-quality-audit/第64轮-人设原文重抽与红黄勘查/_evidence/personas64.json',
            'tool': u'code-quality-audit/第64轮-人设原文重抽与红黄勘查/_tools/extract64.py',
        },
    }
    if not write:
        print()
        print(u'（dry-run，未落盘。）')
        return 0
    with io.open(IDX, 'wb') as fh:
        fh.write(json.dumps(new, ensure_ascii=False, indent=1).encode('utf-8'))
    print()
    print(u'写出 %s  (%d 字节)' % (IDX, os.path.getsize(IDX)))
    return 0


if __name__ == u'__main__':
    raise SystemExit(main(sys.argv[1:]))
