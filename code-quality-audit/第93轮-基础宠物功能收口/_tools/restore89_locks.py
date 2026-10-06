# -*- coding: utf-8 -*-
u"""把 89 轮 commit（`e3862a4`）里改过的**锁/验证脚本**分类：

  · `SAFE`   —— 90~93 轮**没动过** ⇒ 可取 ref89 版（纯恢复）
  · `CONFLICT` —— 90~93 轮动过 ⇒ **不许整取**，需人工合并

用法：
  C:\\Python311\\python.exe restore89_locks.py            # 只分类
  C:\\Python311\\python.exe restore89_locks.py --apply     # 对 SAFE 的执行 git checkout
"""
import os
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
TAG = 'backup/worktree-89round'


def git(*args):
    # ★ `-c core.quotepath=false`：否则 git 会把非 ASCII 路径加引号 + 八进制转义
    #   （`"code-quality-audit/\345\234..."`），于是 `endswith('.py')` 全部漏判
    #   —— 第一版就是这么把 13 个锁文件误判成"非 .py"的。
    r = subprocess.run(['git', '-c', 'core.quotepath=false'] + list(args), cwd=ROOT,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        return None, r.stderr.decode('utf-8', 'replace')
    return r.stdout.decode('utf-8', 'replace'), ''


def main():
    base, err = git('merge-base', 'HEAD', TAG)
    if base is None:
        print('merge-base 失败:', err)
        return 2
    base = base.strip()

    out, err = git('diff', '--name-only', TAG + '~1', TAG)
    if out is None:
        print('diff --name-only 失败:', err)
        return 2
    files = [f for f in out.split('\n') if f.strip()]

    safe, conflict, skipped = [], [], []
    for f in files:
        if not f.endswith('.py'):
            skipped.append((f, '非 .py（baseline/json/图）'))
            continue
        d, _ = git('diff', '--numstat', base, 'HEAD', '--', f)
        if d is None or not d.strip():
            safe.append(f)
        else:
            conflict.append((f, d.strip().replace('\t', ' ')))

    print('=== SAFE（90~93 未动过，可取 ref89 版）共 %d ===' % len(safe))
    for f in safe:
        print('   ', f)
    print('=== CONFLICT（90~93 动过，须人工合并）共 %d ===' % len(conflict))
    for f, d in conflict:
        print('   ', f, '->', d)
    print('=== 跳过 %d ===' % len(skipped))
    for f, why in skipped:
        print('   ', f, '->', why)

    if '--apply' in sys.argv:
        if not safe:
            print('没有 SAFE 项，未执行 checkout')
            return 0
        out, err = git('checkout', TAG, '--', *safe)
        print('checkout ->', out if out is not None else ('FAIL ' + err))
    return 0


if __name__ == '__main__':
    sys.exit(main())
