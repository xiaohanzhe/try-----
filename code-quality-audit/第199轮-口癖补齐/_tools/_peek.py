# -*- coding: utf-8 -*-
"""第199轮 · 看清「正文 CRLF → 尾块 LF」边界到底在哪一行（只读）

eol199.py 报「74 份不符合」，先别当缺陷：很可能是我的边界取早了一行。
恒真的反面是恒空，误报也一样要拆干净 —— 直接把边界附近 120 字节打出来看。
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'ralsei_pet'))
PDIR = os.path.join(ROOT, 'assets', 'npc', 'persona')
TAIL_MARK = u'【本项目补充'.encode('utf-8')


def main():
    for n in ('asgore.txt', 'ot_sans.txt', 'ut_sans.txt', 'lancer.txt'):
        with open(os.path.join(PDIR, n), 'rb') as f:
            b = f.read()
        idx = b.rfind(TAIL_MARK)
        lo = max(0, idx - 60)
        seg = b[lo:idx + 20]
        print('=' * 60)
        print(n)
        print('  边界前 60 字节 repr: %r' % seg)
        # 统计
        crlf = b.count(b'\r\n')
        print('  全文 CRLF=%d  裸LF=%d  长度=%d  末尾=%r' % (
            crlf, b.count(b'\n') - crlf, len(b), b[-8:]))


if __name__ == '__main__':
    main()
