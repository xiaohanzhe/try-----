# -*- coding: utf-8 -*-
"""第189轮b · 把 NPC 人设**尾块**的行尾归一为 LF（正文保持原样）。

为什么需要它
------------
`assets/npc/persona/*.txt` 的体例是：**正文 CRLF + 尾块 LF**（尾块 = 从
`【本项目补充` 起的那一段，76 份逐字节相同，是单一真源；口径见 `_personas.json.tail_text`）。

★ 本轮实测的坑：`git checkout -- <人设>.txt` 之后，`autocrlf=true` 会把**整个文件**
（包括尾块）写成 CRLF ⇒ `check115 C2c/C2d` 当场红（distinct=2 / 含 CR 的文件数=2）。
也就是说：**每次用过 `git checkout` 还原人设，都必须跑一次本脚本**。

口径
----
* 只动尾块：`tail.replace('\r\n', '\n')`，正文一个字节不碰。
* 幂等：尾块本来就 LF ⇒ 算出的 payload 与磁盘相同 ⇒ 不写盘。
* 自证：写前断言"正文部分逐字节相同"，写后回读比对。

用法
----
    python tail_lf189.py            # 只报（列出哪些文件的尾块含 CR）
    python tail_lf189.py --write    # 修
"""
import glob
import io
import os
import shutil
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PER = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', 'persona')
BACKUP = r'D:\_tmp189\tailbak'
MARK = '【本项目补充'


def main():
    do_write = '--write' in sys.argv
    files = sorted(glob.glob(os.path.join(PER, '*.txt')))
    print('扫描 %d 份人设' % len(files))
    bad = []
    for p in files:
        raw = open(p, 'rb').read()
        t = raw.decode('utf-8')
        i = t.find(MARK)
        if i <= 0:
            print('  [跳过] %s 没有尾块标记' % os.path.basename(p))
            continue
        body, tail = t[:i], t[i:]
        if '\r' not in tail:
            continue
        new = body + tail.replace('\r\n', '\n')
        bad.append((p, raw, new.encode('utf-8'), tail.count('\r')))

    print('尾块含 CR 的 %d 份：%s' % (len(bad), '、'.join(
        os.path.basename(b[0]) for b in bad) or '（无）'))
    if not bad:
        print('已是体例（正文 CRLF + 尾块 LF），无需处理')
        return 0
    if not do_write:
        print('\n（dry：未写盘。加 --write 执行）')
        return 0

    stamp = time.strftime('%Y%m%d_%H%M%S')
    if not os.path.isdir(BACKUP):
        os.makedirs(BACKUP)
    for p, raw, data, n_cr in bad:
        name = os.path.basename(p)
        # ★ 自证：正文（含其后的空行）必须逐字节相同 —— 只允许尾块换行符变化
        i_old = raw.decode('utf-8').find(MARK)
        assert data.decode('utf-8').find(MARK) == i_old, '%s 正文长度变了' % name
        shutil.copy2(p, os.path.join(BACKUP, '%s_%s.txt' % (name[:-4], stamp)))
        tmp = p + '.tmp'
        with io.open(tmp, 'wb') as fh:
            fh.write(data)
        os.replace(tmp, p)
        back = open(p, 'rb').read()
        assert back == data, '%s 写后回读不一致' % name
        print('  [写入] %-22s %d → %d B（尾块 CR %d → 0）'
              % (name, len(raw), len(data), n_cr))
    print('\n备份在 %s' % BACKUP)
    return 0


if __name__ == '__main__':
    sys.exit(main())
