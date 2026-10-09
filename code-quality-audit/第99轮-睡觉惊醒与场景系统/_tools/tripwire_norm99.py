# -*- coding: utf-8 -*-
# ★ 归档（第99轮收口）：本脚本是 run_all.py 里 --selftest-norm 第 5 条用例的
#   **破坏式自证** —— 临时把 normalize() 的 blank 初始化删掉，验证恰好那一条报红，
#   再按字节还原并校验 sha256。它证明该用例**不是恒真判据**。
#   跑法：C:////Python311////python.exe code-quality-audit\第99轮-睡觉惊醒与场景系统\_tools\tripwire_norm99.py
#   （会临时改写 code-quality-audit/regress/run_all.py，finally 里还原）

u"""第99轮 · 证明新加的"normalize() 本体"用例是**真绊线**（不是恒真判据）。

做法：临时把 `out, blank = [], False` 改回坏版本 `out = []`，跑 --selftest-norm：
  · 期望：**恰好 1 条报红**，且报红的就是新加的那条（前 4 条仍在测 normalize_noblank，
    它们不经过 normalize() 的空行分支，所以仍绿）；
  · 无论结果如何，**按字节还原**并校验 sha256 一致（不留半成品）。
"""
import hashlib
import io
import subprocess
import sys

P = (r'C:\Users\23002\WorkBuddy\Worktrees\try - 副本\main-a7556e9c'
     r'\code-quality-audit\regress\run_all.py')
GOOD = b'    out, blank = [], False\r\n'
BAD = b'    out = []\r\n'


def run():
    r = subprocess.run([r'C:\Python311\python.exe',
                        r'code-quality-audit\regress\run_all.py',
                        '--selftest-norm'],
                       cwd=(r'C:\Users\23002\WorkBuddy\Worktrees\try - 副本'
                            r'\main-a7556e9c'),
                       capture_output=True)
    return r.returncode, r.stdout.decode('utf-8', 'replace')


def main():
    with io.open(P, 'rb') as fh:
        orig = fh.read()
    h0 = hashlib.sha256(orig).hexdigest()
    print('原文件 sha256 =', h0[:16], ' 锚点 GOOD 命中 =', orig.count(GOOD))
    if orig.count(GOOD) != 1:
        print('FAIL 锚点不唯一，放弃')
        return 1
    try:
        with io.open(P, 'wb') as fh:
            fh.write(orig.replace(GOOD, BAD))
        rc, out = run()
        print('--- 破坏后 --selftest-norm（rc=%d）---' % rc)
        print(out.rstrip())
        n_bad = out.count('NORM99 FAIL')
        trip = 'blank 未初始化类 bug 的绊线' in out and 'NORM99 FAIL' in out
        print('---')
        print('报红条数 = %d（期望 1）' % n_bad)
        print('绊线条是否报红 = %s（期望 True）' % trip)
    finally:
        with io.open(P, 'wb') as fh:
            fh.write(orig)
    with io.open(P, 'rb') as fh:
        back = fh.read()
    h1 = hashlib.sha256(back).hexdigest()
    print('还原后 sha256 =', h1[:16], ' 一致 =', h0 == h1)
    ok = (n_bad == 1) and trip and (h0 == h1)
    print('TRIPWIRE =', 'PASS' if ok else 'FAIL')
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
