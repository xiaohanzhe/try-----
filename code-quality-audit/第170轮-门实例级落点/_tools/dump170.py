# -*- coding: utf-8 -*-
u"""第170轮：用 UTMT 把五章的 W 门控制器 GML **源码**导出来。

为什么要这一步
-------------
第169轮是从**字节码指令序列**反推 x 区间（`Push VAR=x / PushI lo / Cmp ...`），
73 条解不出条件。用户口径：「直接把原作代码搬过来」——GML 源码里
`if (x >= 290 && x <= 370)` 是**一眼能读**的，比反推可靠得多。

做法沿用第44轮的成熟路子（`dump <data.win> -o <dir> -c <code名>`），只读，不改 data.win。

★ 三条已踩过的坑（写死在这里，别再犯）：
  1. **`-c` 一次只吃一个 code 名** ⇒ 必须逐个跑（第44轮 `codeloop` 模式）。
  2. **stdin 必须接 DEVNULL**，否则 UTMT 在 .NET 10 下会挂死（CPU 0.06s、日志 0 字节）。
  3. 反编译产物的文件名形如 `CodeEntries/gml_Object_xxx.gml`。
"""
import io
import os
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
OUTROOT = os.path.join(ROUND, '_evidence', 'gml')

#: UTMT（E 盘原件所在目录已 exFAT 损坏读不了，改用 10-28 的整盘备份）
EXE = os.environ.get(
    'UTMT170_EXE',
    r'D:\E盘备份_20261028\Download\UTMT_CLI_v0.9.2.0\UndertaleModCli.exe')
CWD = os.path.dirname(EXE)

#: 原作 data.win（五章；同一份备份）
WINROOT = os.environ.get(
    'UTMT170_WINROOT', r'D:\E盘备份_20261028\Download\_tmp\drw')

#: 只搬这两段 —— 它们是 W 门的全部分流逻辑（第168轮 `CODE` 常量同一份）
CODE_NAMES = [
    'gml_Object_obj_doorW_Alarm_2',
    'gml_Object_obj_doorw_musfade_Alarm_2',
]


def win_of(ch):
    return os.path.join(WINROOT, 'chapter%d_windows' % ch, 'data.win')


def main():
    for p, why in ((EXE, 'UTMT'), (WINROOT, '原作假目录')):
        if not os.path.exists(p):
            print(u'[FAIL] %s 不存在: %s' % (why, p))
            return 1
    total = 0
    for ch in (1, 2, 3, 4, 5):
        win = win_of(ch)
        if not os.path.exists(win):
            print(u'[FAIL] ch%d data.win 不存在: %s' % (ch, win))
            return 1
        out = os.path.join(OUTROOT, 'ch%d' % ch)
        os.makedirs(out, exist_ok=True)
        print(u'== ch%d  %s  (%d B)' % (ch, win, os.path.getsize(win)))
        for cn in CODE_NAMES:
            a = [EXE, 'dump', win, '-o', out, '-c', cn]
            # ★ stdin=DEVNULL：不接就挂死（第168轮 §169.7 坑 1）
            q = subprocess.run(a, cwd=CWD, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            txt = q.stdout.decode('utf-8', 'replace')
            bad = 'does not contain' in txt or q.returncode != 0
            tail = txt.strip().splitlines()[-1][:110] if txt.strip() else u''
            print(u'   [%s] rc=%d %-40s %s'
                  % ('FAIL' if bad else 'ok', q.returncode, cn, tail))
            if bad:
                print(txt[:1500])
                return 1
        n = 0
        for r, d, f in os.walk(out):
            for x in f:
                if x.endswith('.gml'):
                    n += 1
                    print(u'      %-52s %d B' % (x, os.path.getsize(os.path.join(r, x))))
        total += n
        if n != len(CODE_NAMES):
            print(u'[FAIL] ch%d 只产出 %d 个 .gml（应 %d）' % (ch, n, len(CODE_NAMES)))
            return 1
    print()
    print(u'== 合计 %d 个 .gml ==' % total)
    return 0


if __name__ == '__main__':
    sys.exit(main())
