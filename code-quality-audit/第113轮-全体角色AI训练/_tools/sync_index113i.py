# -*- coding: utf-8 -*-
"""第113轮i · 只同步 `_personas.json` 的登记字段（不碰正文）。

什么时候用
----------
`apply_loc113i.py` 已经带了索引同步，但它有一条守门「拉丁占比必须至少降 5 个百分点」——
那句话在**首次落地**时成立，在**事后微调措辞**时必然不成立（原文已经是译版了）。
所以单独留一个只同步索引的入口，避免为了改一个字段去绕守门。

口径（与 `personas113.py` 一致，别自己发明）
------------------------------------------
  chars      = len(磁盘文本，含 CRLF)
  bytes      = UTF-8 字节数
  sha256     = CRLF 磁盘版本的 sha256
  sha256_lf  = LF 归一化版本的 sha256（可从 git blob 复现）
  sections   = **正文**里的【xxx】标题，不含尾部「本项目补充」块

用法：python sync_index113i.py <npc_id> [--write]
"""
import hashlib
import io
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
NPC = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc')
IDX = os.path.join(NPC, '_personas.json')
TAIL_ANCHOR = '【本项目补充'
SEC_RE = re.compile(r'^【(.+?)】\s*$', re.M)
FIELDS = ('chars', 'bytes', 'sha256', 'sha256_lf', 'sections')


def main(argv):
    write = '--write' in argv
    ids = [a for a in argv if not a.startswith('--')]
    if not ids:
        print('用法：sync_index113i.py <npc_id> [--write]')
        return 2

    rawidx = io.open(IDX, encoding='utf-8', newline='').read()
    idx = json.loads(rawidx)
    recs = {r['id']: r for r in idx['personas']}

    todo = []
    for nid in ids:
        rec = recs.get(nid)
        if rec is None:
            print('FAIL: 索引里没有 %s' % nid)
            return 3
        p = os.path.join(NPC, rec['file'])
        if not os.path.isfile(p):
            print('FAIL: 人设文件不存在 %s' % p)
            return 3
        t = io.open(p, encoding='utf-8', newline='').read()
        body = t.split(TAIL_ANCHOR)[0]          # ★ 只数正文段，不含运行口径块
        new = {
            'chars': len(t),
            'bytes': len(t.encode('utf-8')),
            'sha256': hashlib.sha256(t.encode('utf-8')).hexdigest(),
            'sha256_lf': hashlib.sha256(t.replace('\r\n', '\n').encode('utf-8')).hexdigest(),
            'sections': [m.group(1).strip() for m in SEC_RE.finditer(body)],
        }
        diff = {k: (rec.get(k), new[k]) for k in FIELDS if rec.get(k) != new[k]}
        print('%-14s %s' % (nid, ('无变化' if not diff else '')))
        for k, (o, n) in diff.items():
            if k == 'sections':
                print('   %-10s %d 段 → %d 段  %r' % (k, len(o or []), len(n), n))
            elif k in ('sha256', 'sha256_lf'):
                print('   %-10s %s → %s' % (k, str(o)[:12], str(n)[:12]))
            else:
                print('   %-10s %r → %r' % (k, o, n))
        todo.append((rec, new))

    changes = sum(1 for rec, new in todo if any(rec.get(k) != new[k] for k in FIELDS))
    print()
    print('需要更新 %d / %d 条' % (changes, len(todo)))
    if not changes:
        return 0
    if not write:
        print('（dry：未写盘。加 --write 执行）')
        return 0

    for rec, new in todo:
        rec.update(new)
    payload = json.dumps(idx, ensure_ascii=False, indent=1)
    if '\r\n' in rawidx:
        payload = payload.replace('\n', '\r\n')
    tmp = IDX + '.tmp'
    with io.open(tmp, 'wb') as fh:
        fh.write(payload.encode('utf-8'))
    os.replace(tmp, IDX)

    chk = json.loads(io.open(IDX, encoding='utf-8', newline='').read())
    by = {r['id']: r for r in chk['personas']}
    bad = [nid for nid in ids if any(by[nid].get(k) != recs[nid].get(k) for k in FIELDS)]
    print('写回校验：不一致 = %r' % (bad,))
    return 0 if not bad else 3


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
