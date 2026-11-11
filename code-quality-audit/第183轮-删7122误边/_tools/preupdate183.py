# -*- coding: utf-8 -*-
u"""第183轮 · 一次性核对：准备 --update 的那 16 个 DIFF 套件，**PASS/FAIL 总数必须一字未变**。

只改回显数字（条数/字节/计数）才允许 `--update`；一旦某个套件的 PASS 或 FAIL 变了，
说明判据真被削弱/加强了，得先看清楚，不能刷基线。
"""
import io
import os
import re
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
OUT = os.path.join(ROOT, 'code-quality-audit', 'regress', '_out')

TARGETS = ['scene_route_original', 'routes_order44', 'check_r0_76', 'check105',
           'check124', 'check125', 'check126', 'check168', 'check169', 'check170',
           'check171', 'check172', 'check173', 'check174', 'check176', 'check181']

RE_SUM = re.compile(r'(?:PASS|pass)\D{0,4}(\d+)\D{0,24}?(?:FAIL|fail)\D{0,4}(\d+)')

#: 已知且**有据**的条数变化：只允许写在这里，别的套件变了就是真变了。
#: `check181`：F5 是"本文件恒发 N 条断言"，本轮新增 A1b（验证账本里的删除确实不在表里）
#:   ⇒ 39 → 40。这不是削弱，是**加了一条更硬的**（见第183轮报告 §8）。
ALLOW = {'check181': ((39, 0), (40, 0))}


def nums(txt):
    u"""数断言行。⚠️ 标记有两套：多数套件用 `[PASS]`，`scene_route_original` 用 `[ OK ]`
    —— 只数 `[PASS]` 会把它算成 (0,0)，等于对该套件**没有校验**（第182轮那个
    "扫描器恒空＝恒真的反面"的坑）。两套都数。"""
    return (txt.count('[PASS]') + txt.count('[ OK ]'),
            txt.count('[FAIL]') + txt.count('[BAD ]'))


def main():
    bad = []
    for t in TARGETS:
        cur_p = os.path.join(OUT, '%s.txt' % t)
        base_p = os.path.join(OUT, '%s.baseline.txt' % t)
        if not (os.path.isfile(cur_p) and os.path.isfile(base_p)):
            print('[MISS] %-22s 缺 now/baseline 输出，无法核对' % t)
            bad.append(t)
            continue
        # ★ 全量总数，不是"被改动的行数"：直接数两份输出里的断言行。
        no = nums(io.open(base_p, encoding='utf-8', newline='').read())
        nn = nums(io.open(cur_p, encoding='utf-8', newline='').read())
        ok = (no == nn)
        allowed = ALLOW.get(t)
        note = ''
        if allowed and (no, nn) == allowed:
            ok = True
            note = u'  ← 已知有据的 %r→%r' % (no, nn)
        print('%s %-22s 基线 %r  现在 %r%s'
              % ('[OK  ]' if ok else '[BAD ]', t, no, nn, note))
        if not ok:
            bad.append(t)
    print('')
    print(u'可安全 --update：%d/%d' % (len(TARGETS) - len(bad), len(TARGETS)))
    if bad:
        print(u'需先看清楚：%r' % (bad,))
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
