# -*- coding: utf-8 -*-
"""修法依据：既有文件"不可写"时，还能不能改名 / 删除？

若 `os.rename` / `os.remove` 可用 ⇒ 产品可以「改名旧文件 → 写新文件」绕开限制。
被测对象为 `E:\\Download\\_tmp` 下 45 轮以来的废弃脚本（垃圾，破坏无副作用）。

对照项（负/正控制）：
  · 目录内**新建**文件的 remove（预期 OK）
  · 老文件的 rename（探索）
  · 老文件的 remove（探索；成功即文件消失，属垃圾无妨）
  · **不可写目录外**：`E:\\RalseiMemory\\config.json` 只做 rename 探测**并立刻还原**
    —— 若 rename 成功必须还原，保证产品数据不受影响。
"""
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

D = r'E:\Download\_tmp'
V = r'E:\RalseiMemory'


def step(label, fn):
    try:
        r = fn()
        print('  [OK  ] %s%s' % (label, ('  -> %s' % r) if r else ''))
        return True
    except Exception as e:
        print('  [FAIL] %s  -> %s: %s' % (label, type(e).__name__, e))
        return False


def main():
    print('=== A. 目录内新建文件（正控制）===')
    n = os.path.join(D, '_zz51_tmp_new.txt')
    step('新建文件', lambda: open(n, 'w', encoding='utf-8').write('x'))
    step('remove 新文件', lambda: os.remove(n))

    print('\n=== B. 老文件 rename（探索）===')
    p = os.path.join(D, '_detappend3.py')
    q = p + '.zz51ren'
    if not os.path.exists(p):
        print('  被测老文件不存在:', p)
    else:
        if step('os.rename 老文件 -> *.zz51ren', lambda: os.rename(p, q)):
            step('rename 还原', lambda: os.rename(q, p))

    print('\n=== C. 老文件 remove（探索，垃圾文件）===')
    for name in ('_utf8chk.py', '_attrib.py'):
        g = os.path.join(D, name)
        if os.path.exists(g):
            step('remove %s' % name, lambda g=g: os.remove(g))
        else:
            print('  -- %s 不存在' % name)

    print('\n=== D. vault 关键文件：仅**非破坏性**探测 ===')
    # ⚠️ 原方案要 rename config.json（有数据风险，收益已被 B 段覆盖：同一 E 卷）。
    #    改为纯探测：O_RDWR 打开（不写） + access 检查，绝不改动产品数据。
    cfg = os.path.join(V, 'config.json')
    if os.path.exists(cfg):
        step('os.access(config.json, W_OK)', lambda: os.access(cfg, os.W_OK))
        def _rdwr():
            fd = os.open(cfg, os.O_RDWR)
            os.close(fd)
        step('os.open(config.json, O_RDWR) 只探测不写', _rdwr)
        # 对照：vault 内**新建**文件（预期可写）
        n2 = os.path.join(V, '_zz51_vault_probe.txt')
        if step('vault 内新建文件', lambda: open(n2, 'w', encoding='utf-8').write('x')):
            step('vault 内 remove 新文件', lambda: os.remove(n2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
