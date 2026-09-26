# -*- coding: utf-8 -*-
"""vault 写入能力矩阵（正/负对照）—— 定位"新建文件失败、覆盖写成功"的边界。

上一轮 diag_vault51 的关键事实：
  · `open('E:\\RalseiMemory\\_probe51.tmp','w')`  -> OSError [Errno 22] Invalid argument
  · `open('E:\\RalseiMemory\\_probe51_target.json','w')`（**已存在**）-> 成功
  · 产品日志却报 `[WinError 5] 拒绝访问。config.json.tmp -> config.json`
⇒ 假设：该目录**拒绝创建新文件**，但允许覆盖已有文件。
本脚本用矩阵把它钉死，并带**负控制**（同卷另一目录 `E:\\Download\\_tmp` 应当全绿，
  否则说明问题不在目录而在别处 —— 避免"过宽判据"式的假归因）。

每个用例都留痕：写 / 读回 / 删除，全走 Python（不经 shell）。
"""
import os
import sys
import io
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

VAULT = r'E:\RalseiMemory'
CTRL = r'E:\Download\_tmp'

CASES = [
    ('新建 a.txt        ', 'a_wb51.txt'),
    ('新建 a.tmp        ', 'a_wb51.tmp'),
    ('新建 _a.tmp       ', '_a_wb51.tmp'),
    ('新建 .hidden      ', '.wb51_hidden'),
    ('新建 无扩展名     ', 'wb51_noext'),
    ('新建 中文名.txt   ', '写能力测试.txt'),
    ('新建 子目录       ', None),      # 特殊处理
]


def one(base, label, name):
    if name is None:
        d = os.path.join(base, 'wb51_subdir')
        try:
            os.makedirs(d, exist_ok=True)
            ok = os.path.isdir(d)
            try: os.rmdir(d)
            except OSError: pass
            return ('OK  ' if ok else 'FAIL', 'mkdir')
        except Exception as e:
            return ('FAIL', '%s: %s' % (type(e).__name__, e))
    p = os.path.join(base, name)
    try:
        with open(p, 'w', encoding='utf-8') as f:
            f.write('x')
        # 读回自证
        got = open(p, encoding='utf-8').read()
        try:
            os.remove(p)
        except OSError:
            pass
        return ('OK  ' if got == 'x' else 'BAD ', 'readback=%r' % got)
    except Exception as e:
        return ('FAIL', '%s: %s' % (type(e).__name__, e))


def overwrite(base, name):
    """覆盖**已存在**文件。"""
    p = os.path.join(base, name)
    try:
        with open(p, 'w', encoding='utf-8') as f:
            f.write('old')
        with open(p, 'w', encoding='utf-8') as f:
            f.write('new')
        got = open(p, encoding='utf-8').read()
        try: os.remove(p)
        except OSError: pass
        return ('OK  ' if got == 'new' else 'BAD ', 'readback=%r' % got)
    except Exception as e:
        try: os.remove(p)
        except OSError: pass
        return ('FAIL', '%s: %s' % (type(e).__name__, e))


def rename_replace(base, tag):
    """tmp -> replace 到**同目录**（产品的写法）。"""
    tmp = os.path.join(base, 'zz_%s.tmp' % tag)
    dst = os.path.join(base, 'zz_%s.json' % tag)
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write('{"v":1}')
        st1 = 'tmp 建成功'
    except Exception as e:
        return ('FAIL', '建 tmp 失败: %s: %s' % (type(e).__name__, e))
    try:
        os.replace(tmp, dst)
        st2 = 'replace 成功'
        res = ('OK  ', st1 + ' / ' + st2)
    except Exception as e:
        st2 = 'replace 失败: %s: %s' % (type(e).__name__, e)
        res = ('FAIL', st1 + ' / ' + st2)
    for p in (tmp, dst):
        try:
            if os.path.exists(p): os.remove(p)
        except OSError: pass
    return res


def run(base, title):
    print('\n=== %s ===' % title)
    print('  目录存在:', os.path.isdir(base), ' 可写(access):', os.access(base, os.W_OK))
    for label, name in CASES:
        r, msg = one(base, label, name)
        print('  [%s] %s %s' % (r, label, msg))
    r, msg = overwrite(base, 'a_wb51_ow.txt')
    print('  [%s] 覆盖已存在文件     %s' % (r, msg))
    r, msg = rename_replace(base, 'probe')
    print('  [%s] tmp -> os.replace  %s' % (r, msg))


def main():
    print('E 盘写能力矩阵  ', time.strftime('%Y-%m-%d %H:%M:%S'))
    run(VAULT, 'A 组：vault  E:\\RalseiMemory  （问题现场）')
    run(CTRL, 'B 组：对照  E:\\Download\\_tmp   （负控制，预期全绿）')
    print('\n注：A 组若"新建"全 FAIL 而"覆盖"OK，即锁定"该目录拒绝创建新文件"。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
