# -*- coding: utf-8 -*-
"""第189轮 · 把 `persona/asgore.txt` 的行尾恢复成该目录的既有体例（写盘）。

事故经过
--------
第189轮改 `asgore.txt`（口癖频控 / 口语化 / 加中性正例）用的是行级替换工具，
它把**整个文件重写成了 LF**：改前正文是 CRLF（与其余 75 份一致，susie/toriel 各 108 处），
改后 `body CRLF = 0`。这违反了「保持原 EOL」这条铁律，也会让
`sha256` 与 `sha256_lf` **相等**（正常应当不同），把索引口径搅乱。

恢复口径（与 `personas113.py` 的写盘口径逐字节一致）
---------------------------------------------------
    正文(CRLF) + '\\r\\n\\n' + 尾块(LF) + '\\n'

* 正文 = 「本项目补充」标记之前，去掉尾部空白，行尾统一 CRLF。
* 尾块**不重写**：直接取索引 `tail_text`（单一真源，76 份逐字节相同）。
  取前先校验磁盘上的尾块与 `tail_text` 一致，不一致就报错退出、不写。

★ 幂等：已经合规时算出 `payload == 磁盘原文`，直接报「已是目标体例」不写盘。

用法
----
    python fixeol189.py            # 只检查
    python fixeol189.py --write    # 修
"""
import hashlib
import io
import json
import os
import shutil
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
NPC = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc')
IDX = os.path.join(NPC, '_personas.json')
TARGET = os.path.join(NPC, 'persona', 'asgore.txt')
BACKUP = r'D:\_tmp189\eol_backup'
MARK = '【本项目补充'


def main():
    do_write = '--write' in sys.argv
    idx = json.load(io.open(IDX, 'rb'))
    tail = idx['tail_text']

    raw = open(TARGET, 'rb').read()
    text = raw.decode('utf-8')
    i = text.find(MARK)
    assert i > 0, '找不到尾块标记'
    body, tail_on_disk = text[:i], text[i:]

    # ① 尾块必须先核对（不一致说明这文件被别人动过，停手问人）
    if tail_on_disk.rstrip('\n') != tail:
        print('[停手] 磁盘尾块与索引 tail_text 不一致，不写盘')
        print('  磁盘尾块 %d 字 / 索引 %d 字' % (len(tail_on_disk), len(tail)))
        return 2
    print('尾块核对：磁盘 %d 字 == 索引 tail_text（尾部换行 %d 个）'
          % (len(tail), len(tail_on_disk) - len(tail_on_disk.rstrip('\n'))))

    # ② 正文按「去尾部空白 + CRLF」重建
    body_norm = body.replace('\r\n', '\n').strip('\n').rstrip()
    body_crlf = body_norm.replace('\n', '\r\n')
    payload = (body_crlf + '\r\n\n' + tail + '\n').encode('utf-8')

    print('改前：%d B  正文 CRLF=%d LF-only=%d  sha256=%s  sha256_lf=%s'
          % (len(raw), raw.count(b'\r\n'),
             raw.count(b'\n') - raw.count(b'\r\n'),
             hashlib.sha256(raw).hexdigest()[:12],
             hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()[:12]))
    print('目标：%d B  正文 CRLF=%d LF-only=0  sha256=%s  sha256_lf=%s'
          % (len(payload), payload.count(b'\r\n'),
             hashlib.sha256(payload).hexdigest()[:12],
             hashlib.sha256(payload.replace(b'\r\n', b'\n')).hexdigest()[:12]))

    if payload == raw:
        print('已经是目标体例（幂等，不写盘）')
        return 0
    # ③ 独立校验「只动了换行符」：把两边都归一成 LF 后必须逐字节相同
    #    （这条不是自我印证 —— 右边是磁盘原文，左边是准备写的内容）
    if payload.replace(b'\r\n', b'\n') != raw:
        print('[停手] 归一化后仍有字节差异，超出「只改 EOL」的范围')
        print('  准备写 %d B / 磁盘 %d B（LF 归一后）'
              % (len(payload.replace(b'\r\n', b'\n')), len(raw)))
        return 2
    print('EOL 独立校验：两侧按 LF 归一后逐字节相同（只差换行符）')
    if not do_write:
        print('\n（dry：未写盘。加 --write 执行）')
        return 0

    stamp = time.strftime('%Y%m%d_%H%M%S')
    if not os.path.isdir(BACKUP):
        os.makedirs(BACKUP)
    bak = os.path.join(BACKUP, 'asgore_%s.txt' % stamp)
    shutil.copy2(TARGET, bak)
    tmp = TARGET + '.tmp'
    with io.open(tmp, 'wb') as fh:
        fh.write(payload)
    os.replace(tmp, TARGET)
    back = open(TARGET, 'rb').read()
    assert back == payload, '写后回读不一致'
    print('\n[写入] %s  %d B  备份 → %s' % (TARGET, len(payload), bak))
    return 0


if __name__ == '__main__':
    sys.exit(main())
