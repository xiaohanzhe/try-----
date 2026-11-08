# -*- coding: utf-8 -*-
"""第171轮 · 更新既有套件里的**硬编码计数锚点**（1936 → 1961、196 → 221 …）。

为什么必须一个个改：这些数字是"只增不减"的锚，不更新就会在 G2 里报 DIFF/FAIL，
而那种红**不是回归**，是锚过时。第170轮同样处理过（`bump_counts170.py`）。

规矩：
  · 每处替换断言"**恰好命中 1 次**"（0 次 = 锚点已被人改过，2 次 = 会误伤别处）；
  · 保持原 EOL（这些文件都是 CRLF）；
  · 判据**名字里**带数字的也要一起改，否则下次读输出的人会以为还是旧数。
用法: python bump_counts171.py
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))

OLD_R, NEW_R = '1936', '1961'
OLD_U, NEW_U = '1931', '1956'
OLD_W, NEW_W = '196', '221'

EDITS = [
    ('第44轮-原作对话框复刻/verify_routes_order44.py', [
        ('len(_TBLW) == 196 and', 'len(_TBLW) == 221 and'),
        (u'表驱动门（W）段 == 196 条（第168轮 88 + 第169轮 102 + 第170轮 6）',
         u'表驱动门（W）段 == 221 条（第168轮 88 + 第169轮 102 + 第170轮 6 + 第171轮 25）'),
    ]),
    ('第124轮-桌面门落点与可达性/_tools/check124.py', [
        ('EXPECT_ROUTES = 1936', 'EXPECT_ROUTES = 1961'),
        ('#: ★ 第170轮：门实例级落点补了 6 条 ⇒ 唯一边 1925 → **1931**（路由 1936，仍是 5 组）',
         '#: ★ 第170轮：门实例级落点补了 6 条 ⇒ 唯一边 1925 → **1931**（路由 1936，仍是 5 组）\n'
         '#: ★ 第171轮：按逐房间实例表补了 25 条 ⇒ 唯一边 1931 → **1956**（路由 1961，仍是 5 组）'),
        ('EXPECT_UNIQUE_EDGES = 1931', 'EXPECT_UNIQUE_EDGES = 1956'),
    ]),
    ('第125轮-D门与X门补齐/_tools/check125.py', [
        ('EXPECT_W_IN_PROD = 196', 'EXPECT_W_IN_PROD = 221'),
    ]),
    ('第126轮-门型收口/_tools/check126.py', [
        (u'A0 分母：`load_index()` ok=True、场景数 == 2166、路由 == 1936 条、新段非空',
         u'A0 分母：`load_index()` ok=True、场景数 == 2166、路由 == 1961 条、新段非空'),
        ('len(RL) == 1936 and', 'len(RL) == 1961 and'),
    ]),
    ('第168轮-W门补齐/_tools/check168.py', [
        ('EXPECT_ROUTES = 1936', 'EXPECT_ROUTES = 1961'),
    ]),
    ('第169轮-W门按分支补齐/_tools/check169.py', [
        ('EXPECT_ROUTES = 1936', 'EXPECT_ROUTES = 1961'),
    ]),
    ('第170轮-门实例级落点/_tools/check170.py', [
        ('EXPECT_ROUTES = 1936', 'EXPECT_ROUTES = 1961'),
        ('EXPECT_W_RULES = 196                 # 190（168/169）+ 6（170）',
         'EXPECT_W_RULES = 221                 # 190（168/169）+ 6（170）+ 25（171）'),
    ]),
]


def main():
    total, bad = 0, 0
    for rel, pairs in EDITS:
        p = os.path.join(REPO, 'code-quality-audit', rel)
        if not os.path.isfile(p):
            print('[SKIP] 不存在 %s' % rel)
            bad += 1
            continue
        txt = io.open(p, encoding='utf-8', newline='').read()
        crlf = '\r\n' in txt
        norm = txt.replace('\r\n', '\n')
        for old, new in pairs:
            n = norm.count(old)
            if n != 1:
                print('[FAIL] %-46s 命中 %d 次：%r' % (os.path.basename(p), n, old[:48]))
                bad += 1
                continue
            norm = norm.replace(old, new)
            total += 1
            print('[ OK ] %-46s %s' % (os.path.basename(p), old.split('\n')[0][:44]))
        out = norm.replace('\n', '\r\n') if crlf else norm
        io.open(p, 'w', encoding='utf-8', newline='').write(out)
    print('')
    print('替换完成，%d 处，失败 %d 处' % (total, bad))
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
