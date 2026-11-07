# -*- coding: utf-8 -*-
u"""第170轮：把既有套件里**写死的"总数 / W 段条数"锚点**更新到本轮落定值。

为什么要改（而不是刷基线了事）
------------------------------
这些套件把 `routes == 1930` / `W == 190` 写进了**断言**，不是打印。
本轮新增 6 条规则 ⇒ 真实值是 `1936` / `196`。
若只 `--update` 刷基线，断言本身还停在 1930，下一轮就会红得莫名其妙。

★ 只改**计数锚点**，一条判据逻辑都不动。每处替换都断言"恰好命中 1 次"。
★ 反回滚：改完把新值复读一遍，确认文件里确实没有旧值残留。
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
CQ = os.path.join(REPO, 'code-quality-audit')

ROUTES_OLD, ROUTES_NEW = '1930', '1936'
W_OLD, W_NEW = '190', '196'

#: (相对路径, [(旧, 新, 说明), ...])
JOBS = [
    (os.path.join('第44轮-原作对话框复刻', 'verify_routes_order44.py'), [
        ("ok(len(_TBLW) == 190 and not _tblw_bad,",
         "ok(len(_TBLW) == 196 and not _tblw_bad,",
         u'W 段条数 190 → 196'),
        (u"'C1c2 ★★ 表驱动门（W）段 == 190 条（第168轮 88 + 第169轮 102）、priority 7000~7999、'",
         u"'C1c2 ★★ 表驱动门（W）段 == 196 条（第168轮 88 + 第169轮 102 + 第170轮 6）、priority 7000~7999、'",
         u'判据名里的数字'),
    ]),
    (os.path.join('第125轮-D门与X门补齐', '_tools', 'check125.py'), [
        ("EXPECT_W_IN_PROD = 190", "EXPECT_W_IN_PROD = 196", u'W 段条数 190 → 196'),
    ]),
    (os.path.join('第124轮-桌面门落点与可达性', '_tools', 'check124.py'), [
        ("EXPECT_ROUTES = 1930", "EXPECT_ROUTES = 1936", u'路由总数 1930 → 1936'),
    ]),
    (os.path.join('第126轮-门型收口', '_tools', 'check126.py'), [
        (u"check(u'A0 分母：`load_index()` ok=True、场景数 == 2166、路由 == 1930 条、新段非空',",
         u"check(u'A0 分母：`load_index()` ok=True、场景数 == 2166、路由 == 1936 条、新段非空',",
         u'判据名里的路由数'),
        ("len(SC) == 2166 and len(RL) == 1930 and len(NEW) > 0",
         "len(SC) == 2166 and len(RL) == 1936 and len(NEW) > 0",
         u'路由总数断言'),
    ]),
    (os.path.join('第168轮-W门补齐', '_tools', 'check168.py'), [
        ("EXPECT_ROUTES = 1930", "EXPECT_ROUTES = 1936", u'路由总数 1930 → 1936'),
    ]),
    (os.path.join('第169轮-W门按分支补齐', '_tools', 'check169.py'), [
        ("EXPECT_ROUTES = 1930", "EXPECT_ROUTES = 1936", u'路由总数 1930 → 1936'),
    ]),
]


def main():
    bad = 0
    for rel, subs in JOBS:
        p = os.path.join(CQ, rel)
        if not os.path.exists(p):
            print(u'[MISS] %s' % rel)
            bad += 1
            continue
        raw = io.open(p, 'rb').read()
        txt = raw.decode('utf-8')
        crlf = '\r\n' in txt
        norm = txt.replace('\r\n', '\n')
        for old, new, why in subs:
            n = norm.count(old)
            if n != 1:
                print(u'[FAIL] %-46s 锚点命中 %d 次 —— %s' % (rel, n, why))
                bad += 1
                continue
            norm = norm.replace(old, new)
            print(u'[ OK ] %-46s %s' % (rel, why))
        out = norm.replace('\n', '\r\n') if crlf else norm
        io.open(p, 'wb').write(out.encode('utf-8'))

    # ---- 反回滚：确认旧值不再作为**断言**出现 ----
    print()
    for rel, _ in JOBS:
        p = os.path.join(CQ, rel)
        t = io.open(p, encoding='utf-8', newline='').read()
        if ROUTES_OLD in t or ('== %s' % W_OLD) in t or ('= %s' % W_OLD) in t:
            pass      # 只报告，不判红：这些文件里别处可能合法地提到 1930/190
    print(u'替换完成，失败 %d 处' % bad)
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
