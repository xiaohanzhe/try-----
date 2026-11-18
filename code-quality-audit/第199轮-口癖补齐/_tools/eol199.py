# -*- coding: utf-8 -*-
"""第199轮 · 人设文件行尾/尾块结构体检（只读）

为什么必须先查：189b 踩过两次
  · `git checkout -- <人设>.txt` 会把尾块一起转 CRLF ⇒ check115 C2c/C2d 当场红
  · EOL 归一后必须**逐字节相同**，否则回滚不干净
所以改之前先量清楚：正文是 CRLF 还是 LF、尾块从哪行开始、文件末尾有没有多余空行。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'ralsei_pet'))
PDIR = os.path.join(ROOT, 'assets', 'npc', 'persona')
TAIL_MARK = u'【本项目补充'


def raw(p):
    with open(p, 'rb') as f:
        return f.read()


def main():
    names = sorted(n for n in os.listdir(PDIR) if n.endswith('.txt'))
    stat = {}
    tails = {}
    for n in names:
        b = raw(os.path.join(PDIR, n))
        crlf = b.count(b'\r\n')
        lf = b.count(b'\n') - crlf
        # 尾块起点：最后出现的 TAIL_MARK 所在行首字节偏移
        mb = TAIL_MARK.encode('utf-8')
        idx = b.rfind(mb)
        tail_from = b.rfind(b'\n', 0, idx) + 1 if idx > 0 else -1
        head = b[:tail_from] if tail_from > 0 else b
        tail = b[tail_from:] if tail_from > 0 else b''
        h_crlf = head.count(b'\r\n')
        h_lf = head.count(b'\n') - h_crlf
        t_crlf = tail.count(b'\r\n')
        t_lf = tail.count(b'\n') - t_crlf
        key = (('H:CRLF' if h_crlf else 'H:LF') if (h_crlf or h_lf) else 'H:none',
               ('T:CRLF' if t_crlf else 'T:LF') if (t_crlf or t_lf) else 'T:none')
        stat[key] = stat.get(key, 0) + 1
        # 末尾空行数
        endnl = len(b) - len(b.rstrip(b'\r\n'))
        tails[n] = (crlf, lf, h_crlf, h_lf, t_crlf, t_lf, endnl)

    print('=== 行尾形态分布 ===')
    for k, v in sorted(stat.items(), key=lambda x: -x[1]):
        print('%2d 份  %s / %s' % (v, k[0], k[1]))

    print('\n=== 逐份 ===')
    print('%-30s %5s %5s | %5s %5s | %5s %5s | 尾空行' % (
        'file', 'CRLF', 'LF', '头CRLF', '头LF', '尾CRLF', '尾LF'))
    bad = []
    for n in names:
        c, l, hc, hl, tc, tl, e = tails[n]
        print('%-30s %5d %5d | %5d %5d | %5d %5d | %d' % (n, c, l, hc, hl, tc, tl, e))
        # 期望：头全 CRLF 无裸 LF；尾全 LF 无 CRLF
        if hl > 0 or tc > 0:
            bad.append(n)

    print('\n=== 不符合「正文 CRLF + 尾块 LF」的 ===')
    print('%d 份：%s' % (len(bad), ', '.join(bad) if bad else '（无）'))

    # 尾空行分布
    es = {}
    for n in names:
        es[tails[n][6]] = es.get(tails[n][6], 0) + 1
    print('末尾换行字节数分布：%s' % sorted(es.items()))


if __name__ == '__main__':
    main()
