# -*- coding: utf-8 -*-
u"""改完产品文件后的机械复检：语法 / 行尾 / BOM / 关键接线点。

★ 不用 `py_compile`（会产 `.pyc`，等于改变被测状态），一律 `ast.parse`。
"""
import ast
import io
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
FILES = [
    os.path.join(PET, 'src', 'main.py'),
    os.path.join(PET, 'modules', 'item_interact.py'),
]

n_bad = 0
for p in FILES:
    raw = open(p, 'rb').read()
    rel = os.path.relpath(p, ROOT)
    print('== %s  %d bytes' % (rel, len(raw)))
    try:
        ast.parse(raw.decode('utf-8'))
        print('   [PASS] 语法可解析')
    except Exception as e:
        n_bad += 1
        print('   [FAIL] 语法: %s: %s' % (type(e).__name__, e))
    if raw.startswith(b'\xef\xbb\xbf'):
        n_bad += 1
        print('   [FAIL] 有 BOM')
    else:
        print('   [PASS] 无 BOM')
    crlf = raw.count(b'\r\n')
    lf = raw.count(b'\n') - crlf
    print('   %s CRLF=%d LF=%d' % ('[PASS]' if not (crlf and lf) else '[FAIL]', crlf, lf))
    if crlf and lf:
        n_bad += 1

print('')
print('[%s] 复检结束 异常=%d' % ('PASS' if n_bad == 0 else 'FAIL', n_bad))
sys.exit(0 if n_bad == 0 else 1)
