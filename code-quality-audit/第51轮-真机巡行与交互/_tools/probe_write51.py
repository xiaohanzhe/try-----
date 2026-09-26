# -*- coding: utf-8 -*-
"""判别实验：vault 里"既有文件"是否**普遍**拒绝写入？

两种互斥假设：
  H1 「文件系统 / ACL 层」  ⇒ vault 内**所有**既有文件都不可写（新建可以）
  H2 「个别文件被进程独占」 ⇒ 只有 config.json / memory.json 等被打开的文件不可写

判据（正/负控制齐备）：
  · A 组：vault 内全部既有文件（顶层 + logs/ + cache/）逐个 `O_WRONLY|O_APPEND` 探测
  · B 组：**新建**一个文件并立刻追加写它（若这都不行，说明连新建也不稳）
  · C 组：负控制 —— 同卷 `E:\\Download\\_tmp` 的既有文件（预期可写）
只用 O_APPEND 打开、**不写任何字节**，因此不会改动任何文件内容；
新建的探针文件测完即删。
"""
import os
import sys
import io
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

VAULT = r'E:\RalseiMemory'
CTRL = r'E:\Download\_tmp'
O_WA = os.O_WRONLY | os.O_APPEND


def try_append(fp):
    try:
        fd = os.open(fp, O_WA)
        os.close(fd)
        return 'OK'
    except Exception as e:
        return '%s' % type(e).__name__


def scan(base, label):
    print('\n=== %s ===' % label)
    ok = fail = 0
    fails = []
    entries = []
    for root, dirs, files in os.walk(base):
        if root.count(os.sep) - base.count(os.sep) > 1:
            continue
        for f in files:
            entries.append(os.path.join(root, f))
    for fp in sorted(entries):
        rel = os.path.relpath(fp, base)
        r = try_append(fp)
        if r == 'OK':
            ok += 1
        else:
            fail += 1
            fails.append((rel, r))
        print('  [%-4s] %-46s %s' % ('OK' if r == 'OK' else 'FAIL', rel, r if r != 'OK' else ''))
    print('  ---- 可写 %d / 不可写 %d ----' % (ok, fail))
    return ok, fail, fails


def main():
    print('判别实验 ', time.strftime('%Y-%m-%d %H:%M:%S'))

    # A 组
    ok, fail, fails = scan(VAULT, 'A 组：vault  E:\\RalseiMemory 全部既有文件')

    # B 组：新建立刻追加
    print('\n=== B 组：新建 -> 立刻追加写 ===')
    p = os.path.join(VAULT, 'zz51_probe.txt')
    try:
        with open(p, 'w', encoding='utf-8') as f:
            f.write('x')
        print('  新建 OK')
        print('  立刻追加 %s' % try_append(p))
    except Exception as e:
        print('  新建失败 %s: %s' % (type(e).__name__, e))
    try:
        os.remove(p)
        print('  已清理')
    except Exception as e:
        print('  ★ 清理失败（残留文件）: %s' % e)

    # C 组：负控制
    scan(CTRL, 'C 组（负控制）：E:\\Download\\_tmp 既有文件')

    print('\n===== 结论指引 =====')
    print('  A 组"几乎全 FAIL" ⇒ H1（文件系统/ACL 层，与进程无关）')
    print('  A 组"只有 config/memory FAIL" ⇒ H2（被进程独占）')
    print('  C 组若也 FAIL ⇒ 判据本身有问题，先查判据')
    return 0


if __name__ == '__main__':
    sys.exit(main())
