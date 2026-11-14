# -*- coding: utf-8 -*-
"""第189轮 · 只把 `assets/npc/_personas.json` 的**派生字段**按磁盘重算（写盘）。

为什么不跑 `personas113.py --write`
-----------------------------------
`personas113.py` 的口径是「用 `其余人物设定.txt` 的**源正文**覆盖人设文件」。
第189轮改过 `asgore.txt`（口癖频控 + 口语化 + 中性正例），
一跑 `--write` 就会把改动**冲回源文**（正文重建），等于白改。
所以这里**只读磁盘、只算派生字段**，绝不重写任何 `.txt` 正文。

改哪些字段（与 `personas113.py` ④ 完全同口径，口径单一）
--------------------------------------------------------
`chars` = 磁盘文本字符数 / `bytes` = 磁盘字节数 /
`sha256` = 磁盘原文 / `sha256_lf` = CRLF→LF 后 /
`tail_sha256` = 索引级 `tail_sha256`（尾块是单一真源，逐份相同）/
`sections` = 【…】小节名（只取「本项目补充」之前的正文）/
`tail_added` = 该文件含尾块标记。

★ 幂等：全部字段都是「从磁盘重算」，重跑两次字节完全一致（脚本自带这层自检）。

用法
----
    python reindex189.py            # 只对比，不写
    python reindex189.py --write    # 写盘（先备份到 D:\\_tmp189\\personas_idx_backup）
"""
import hashlib
import io
import json
import os
import re
import shutil
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
NPC = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc')
IDX = os.path.join(NPC, '_personas.json')
BACKUP = r'D:\_tmp189\personas_idx_backup'
MARK = '【本项目补充'
SEC = re.compile(u'【([^】]{1,24})】')

#: 目录里应有 76 份人设（分母闸：少一份就说明路径错了，不许静默少算）
EXPECT_N = 76


def dump(idx):
    """与 personas113.py 的落盘体例逐字节一致（indent=1 / 不转义中文 / 末尾一个 \\n）。"""
    return json.dumps(idx, ensure_ascii=False, indent=1).encode('utf-8') + b'\n'


def fields_of(path, tail_sha):
    raw = open(path, 'rb').read()
    text = raw.decode('utf-8')
    i = text.find(MARK)
    body = text[:i] if i > 0 else text
    return {
        'chars': len(text),
        'bytes': len(raw),
        'sha256': hashlib.sha256(raw).hexdigest(),
        'sha256_lf': hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest(),
        'sections': SEC.findall(body),
        'tail_added': i > 0,
        'tail_sha256': tail_sha,
    }


def main():
    do_write = '--write' in sys.argv
    idx = json.load(io.open(IDX, 'rb'))
    recs = idx.get('personas') or []
    assert len(recs) == EXPECT_N, '记录数 %d != %d' % (len(recs), EXPECT_N)
    tail_sha = idx['tail_sha256']

    plan, missing = [], []
    for rec in recs:
        path = os.path.join(NPC, rec['file'])
        if not os.path.isfile(path):
            missing.append(rec['id'])
            continue
        want = fields_of(path, tail_sha)
        diff = {k: (rec.get(k), v) for k, v in want.items() if rec.get(k) != v}
        if diff:
            plan.append((rec, diff, want))
    if missing:
        print('[警告] 磁盘缺文件 %d 份：%r' % (len(missing), missing[:5]))

    print('记录 %d 份，需更新 %d 份：%s'
          % (len(recs), len(plan), '、'.join(p[0]['id'] for p in plan) or '（无）'))
    for rec, diff, _ in plan:
        print('  %-12s %s' % (rec['id'], ', '.join(
            '%s %s→%s' % (k, (str(a)[:10] + '…' if isinstance(a, str) and len(str(a)) > 10 else a),
                          (str(b)[:10] + '…' if isinstance(b, str) and len(str(b)) > 10 else b))
            for k, (a, b) in diff.items())))
    if not do_write:
        print('\n（dry：未写盘。加 --write 执行）')
        return 0

    stamp = time.strftime('%Y%m%d_%H%M%S')
    if not os.path.isdir(BACKUP):
        os.makedirs(BACKUP)
    bak = os.path.join(BACKUP, 'personas_%s.json' % stamp)
    shutil.copy2(IDX, bak)
    print('  备份 → %s' % bak)

    for rec, _, want in plan:
        rec.update(want)

    payload = dump(idx)
    tmp = IDX + '.tmp'
    with io.open(tmp, 'wb') as fh:
        fh.write(payload)
    os.replace(tmp, IDX)

    # ① 写后回读 == 打算写的字节
    back = open(IDX, 'rb').read()
    assert back == payload, '写后回读不一致'
    # ② 幂等自检：改成「不需要更新」后重跑一遍，字节必须一模一样
    again = json.load(io.open(IDX, 'rb'))
    assert dump(again) == payload, '重load再dump不一致（体例不稳，会污染 diff）'
    print('  [写入] %s  %d B  %d 份已更新' % (IDX, len(payload), len(plan)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
