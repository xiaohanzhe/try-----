# -*- coding: utf-8 -*-
"""第199轮 · 改动自检（只读；拿 `_evidence/_persona_bak/` 当基准）

判据（每条都要能红，见 check199 的变异）
  V1 尾块逐字节不变（76 份，与备份比）—— 这是 check115 C2c/C2d 的命门
  V2 正文无裸 LF / 尾块无 CR（正文 CRLF、尾块 LF）
  V3 行数变化只可能是 0（15 处改写）或 +2（补正例），不许有别的
  V4 无「。。」这类拼接事故
  V5 真强化语命中数从 60 降下来
  V6 正例份数：64 份各 2 条；12 份 0 条（排除名单）
"""
import hashlib
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
PER = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', 'persona')
TAIL = u'【本项目补充'.encode('utf-8')

sys.path.insert(0, HERE)
import apply199 as A          # noqa: E402
#: ★ 备份在临时区，**不进工作区**（`git add -A` 会把它记成新增/污染）。
#:   路径只认一个真源：`apply199.BAK`，别在这里再写一遍。
BAK = A.BAK

OK, BAD = [], []


def chk(name, cond, detail=''):
    (OK if cond else BAD).append(name)
    print('%s %s  %s' % ('[OK]' if cond else '[NG]', name, detail))


def rd(p):
    with open(p, 'rb') as f:
        return f.read()


def tail_of(b):
    i = b.rfind(TAIL)
    if i < 0:
        return None
    j = b.rfind(b'\n', 0, i) + 1
    return b[j:]


def main():
    names = sorted(n for n in os.listdir(PER) if n.endswith('.txt'))
    tails, deltas, tails_same = set(), {}, 0
    bad_eol, dbl, noex = [], [], []

    for n in names:
        cur = rd(os.path.join(PER, n))
        old = rd(os.path.join(BAK, n + '.before199'))
        t = tail_of(cur)
        tails.add(t)
        if t == tail_of(old):
            tails_same += 1
        else:
            bad_eol.append(n)       # 借这个列表记"尾块被动过"
        d = (cur.count(b'\n') - cur.count(b'\r\n')) - (old.count(b'\n') - old.count(b'\r\n'))
        # 正文行数变化 = CRLF 数变化
        deltas[n] = cur.count(b'\r\n') - old.count(b'\r\n')
        txt = cur.decode('utf-8')
        if u'。。' in txt:
            dbl.append(n)

    chk('V1 尾块 76 份逐字节相同', len(tails) == 1, 'distinct=%d' % len(tails))
    chk('V1b 尾块与备份逐字节相同', not bad_eol, '变了=%s' % (bad_eol[:5] or '无'))

    # V2 正文裸 LF 数**与备份相同**（我的改动只加 CRLF）
    #    ★ 不能用"绝对值 <=1"当标准：这 76 份人设正文与尾块之间的空行本来就是裸 LF，
    #      有的 1 个、有的 2 个（eol199 实测）。拿绝对值判会误报 74 份。
    bad_lf = []

    def bare(b):
        i = b.rfind(TAIL)
        j = b.rfind(b'\n', 0, i) + 1
        head = b[:j]
        return head.count(b'\n') - head.count(b'\r\n')

    for n in names:
        if bare(rd(os.path.join(PER, n))) != bare(rd(os.path.join(BAK, n + '.before199'))):
            bad_lf.append(n)
    chk('V2 正文裸 LF 数与备份一致', not bad_lf, '变了=%s' % (bad_lf[:5] or '无'))

    # V3 行数变化只有 0 / +2
    weird = {k: v for k, v in deltas.items() if v not in (0, 2)}
    chk('V3 行数变化只有 0 或 +2', not weird, '异常=%s' % (weird or '无'))

    # V4 拼接事故
    chk('V4 无「。。」', not dbl, '命中=%s' % (dbl[:5] or '无'))

    # V5 强化语命中数
    def boost_count():
        import survey_quirks199 as S
        tot = 0
        files = set()
        for n in names:
            txt = rd(os.path.join(PER, n)).decode('utf-8')
            style = u''
            for h, b in S.sections(txt):
                if u'语言风格' in h:
                    style = b
                    break
            for it in S.items(style):
                for w, _c in S.boost_hits(it):
                    tot += 1
                    files.add(n)
        return tot, len(files)

    def boost_count_old():
        import survey_quirks199 as S
        tot = 0
        files = set()
        for n in names:
            txt = rd(os.path.join(BAK, n + '.before199')).decode('utf-8')
            style = u''
            for h, b in S.sections(txt):
                if u'语言风格' in h:
                    style = b
                    break
            for it in S.items(style):
                for w, _c in S.boost_hits(it):
                    tot += 1
                    files.add(n)
        return tot, len(files)

    b_new, f_new = boost_count()
    b_old, f_old = boost_count_old()
    print('    强化语：改前 %d 条/%d 份 → 改后 %d 条/%d 份（删了 %d 条）'
          % (b_old, f_old, b_new, f_new, b_old - b_new))
    chk('V5 强化语确实减少', b_new < b_old, '%d → %d' % (b_old, b_new))

    # V6 正例份数
    n_ex = {}
    for n in names:
        txt = rd(os.path.join(PER, n)).decode('utf-8')
        n_ex[n] = sum(1 for x in A.EX_POOL if x in txt)
    has2 = [n for n, c in n_ex.items() if c == 2]
    has0 = [n for n, c in n_ex.items() if c == 0]
    skip = sorted(A.SKIP_EX)
    chk('V6a 64 份各 2 条正例', len(has2) == 64, 'got=%d' % len(has2))
    chk('V6b 12 份排除名单 0 条', sorted(has0) == skip,
        'got=%d expect=%d 差=%s' % (len(has0), len(skip),
                                    sorted(set(has0) ^ set(skip))[:4]))
    others = [n for n, c in n_ex.items() if c not in (0, 2)]
    chk('V6c 没有 1 条/3 条的半成品', not others, '异常=%s' % (others[:5] or '无'))

    print('\n=== 结论 ===')
    print('OK=%d  NG=%d' % (len(OK), len(BAD)))
    if BAD:
        print('红的：%s' % BAD)
    return 1 if BAD else 0


if __name__ == '__main__':
    sys.exit(main())
