#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第60轮 清理：只删**本探针自己创建**的落物（显式文件名，不用通配符）。

口径：本人习惯把临时物放 E:\\Download\\_tmp（用后即删），
      但 E:\\RalseiMemory 是**产品数据目录**，只删本轮探针明确写进去的那几个名字，
      绝不碰 config.json / memory.json / logs / cache。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)

EXPLICIT = {
    r'E:\Download\_tmp': [
        'g2_full_60.txt', 'g2_ab_e.txt', 'commit59.txt',
        '_probe_60.txt', '_probe_60b.txt', '_ps_probe.txt',
        '_samp1.txt', '_samp2.txt', '_samp3.txt',
        '_wchk60_a.txt', '_wchk60_c.txt', '_wchk60_c.tmp',
        '_wchk60_d.tmp', '_wchk60_d_target.txt',
        '_wchk60_f.txt', '_wchk60_f.tmp',
        '_rn_src.txt', '_rn_dst.txt',
    ],
    r'E:\RalseiMemory': [
        '_wtest.txt', '_wtest2.json', '_wtest2.tmp',
        '_wchk60_a.txt', '_wchk60_c.txt', '_wchk60_c.tmp',
        '_wchk60_d.tmp', '_wchk60_d_target.txt',
        '_wchk60_f.txt', '_wchk60_f.tmp',
    ],
}
# 只按前缀删的目录（本探针自建的临时目录）
PREFIX_DIRS = [
    (os.environ.get('TEMP') or r'C:\Users\23002\AppData\Local\Temp', ['wchk60_']),
]


def main():
    removed, kept, failed = [], [], []
    for d, names in EXPLICIT.items():
        for n in names:
            p = os.path.join(d, n)
            if not os.path.exists(p):
                continue
            try:
                os.remove(p)
                removed.append(p)
            except OSError as e:
                failed.append('%s :: %s' % (p, e))
    # 前缀目录（只删本探针建的）
    for d, prefixes in PREFIX_DIRS:
        if not os.path.isdir(d):
            continue
        for e in sorted(os.listdir(d)):
            if any(e.startswith(p) for p in prefixes):
                p = os.path.join(d, e)
                try:
                    if os.path.isdir(p):
                        for f in os.listdir(p):
                            os.remove(os.path.join(p, f))
                        os.rmdir(p)
                    else:
                        os.remove(p)
                    removed.append(p)
                except OSError as ex:
                    failed.append('%s :: %s' % (p, ex))

    # 报告：E:\RalseiMemory 里剩下的**非本轮**东西（只列，不动）
    v = r'E:\RalseiMemory'
    if os.path.isdir(v):
        kept = sorted(os.listdir(v))
    print('删除 %d 项：' % len(removed))
    for p in removed:
        print('  - %s' % p)
    if failed:
        print('失败 %d 项：' % len(failed))
        for p in failed:
            print('  ! %s' % p)
    print()
    print('E:\\RalseiMemory 现存（只列不动）：%s' % kept)
    return 0


if __name__ == '__main__':
    sys.exit(main())
