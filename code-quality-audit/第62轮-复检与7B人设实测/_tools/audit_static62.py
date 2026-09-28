#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第60轮 静态普查 A：全仓 .py 可解析性 + 编码 + BOM/替换符。

设计铁律（沿用本项目教训）：
  * 用 ast.parse，**不用 py_compile** —— 后者会产 .pyc 改变被测状态（§"复检不许改变被测状态"）。
  * 逐文件独立 try，一个文件坏不影响其余。
  * 编码判定分三步：BOM 检测 → utf-8 严格解码 → U+FFFD 计数。
  * 输出结构化 JSON，供其他 AI 直接复核。

用法：
  C:\\Python311\\python.exe audit_static60.py
"""
import ast
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
AUDIT = os.path.dirname(ROUND)
REPO = os.path.dirname(AUDIT)
TARGET = os.path.join(REPO, 'ralsei_pet')
OUT = os.path.join(ROUND, '_evidence')

# 跳过的目录（一律不递归）
SKIP_DIRS = {'__pycache__', '.git', 'node_modules', 'diag_frames', 'diag_frames2',
             'diag_frames3', 'logs', 'assets', 'config', 'tests'}
# 备份/临时后缀：这些不是"活代码"，单独归类，不混进主统计
BACKUP_SUFFIXES = ('.bak', '.backup', '.orig', '.old', '.discrim_bak')


def is_backup(name):
    low = name.lower()
    for s in BACKUP_SUFFIXES:
        if low.endswith(s):
            return True
    if '.backup_' in low or '.bak_' in low:
        return True
    return False


def collect():
    live, backups = [], []
    for dirpath, dirnames, filenames in os.walk(TARGET):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith('.py'):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, REPO).replace('\\', '/')
            (backups if is_backup(fn) else live).append((rel, p))
    live.sort()
    backups.sort()
    return live, backups


def inspect(rel, path):
    rec = {'file': rel}
    with open(path, 'rb') as f:
        raw = f.read()
    rec['bytes'] = len(raw)

    # --- BOM ---
    bom = None
    if raw.startswith(b'\xef\xbb\xbf'):
        bom = 'utf-8-sig'
    elif raw.startswith(b'\xff\xfe'):
        bom = 'utf-16-le'
    elif raw.startswith(b'\xfe\xff'):
        bom = 'utf-16-be'
    rec['bom'] = bom

    # --- 解码 ---
    try:
        text = raw.decode('utf-8')
        rec['utf8_ok'] = True
        if bom == 'utf-8-sig':
            text = text.lstrip('\ufeff')
    except UnicodeDecodeError as e:
        rec['utf8_ok'] = False
        rec['decode_error'] = '%s @%d' % (e.reason, e.start)
        text = raw.decode('utf-8', 'replace')

    rec['replacement_chars'] = text.count('\ufffd')
    rec['crlf'] = text.count('\r\n')
    rec['lf_only'] = text.count('\n') - rec['crlf']
    rec['lines'] = text.count('\n') + (0 if text.endswith('\n') else 1)

    # --- 语法 ---
    try:
        tree = ast.parse(text, filename=rel)
        rec['parse_ok'] = True
        rec['n_func'] = sum(1 for n in ast.walk(tree)
                            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
        rec['n_class'] = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        rec['n_import'] = sum(1 for n in ast.walk(tree)
                              if isinstance(n, (ast.Import, ast.ImportFrom)))
    except SyntaxError as e:
        rec['parse_ok'] = False
        rec['parse_error'] = '%s line=%s offset=%s' % (e.msg, e.lineno, e.offset)
    except Exception as e:  # pragma: no cover
        rec['parse_ok'] = False
        rec['parse_error'] = '%s: %s' % (type(e).__name__, e)
    return rec


def check(cond, msg):
    print('[%s] %s' % ('PASS' if cond else 'FAIL', msg))
    return bool(cond)


def main():
    if not os.path.isdir(TARGET):
        print('目标目录不存在：%s' % TARGET)
        return 1
    live, backups = collect()
    recs = [inspect(rel, p) for rel, p in live]

    bad_parse = [r for r in recs if not r['parse_ok']]
    bad_utf8 = [r for r in recs if not r['utf8_ok']]
    with_bom = [r for r in recs if r['bom']]
    with_repl = [r for r in recs if r['replacement_chars'] > 0]

    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, 'static62.json')
    with open(dst, 'w', encoding='utf-8') as f:
        json.dump({'target': TARGET.replace('\\', '/'),
                   'n_live': len(recs),
                   'n_backup': len(backups),
                   'backups': [b[0] for b in backups],
                   'files': recs}, f, ensure_ascii=False, indent=1)

    total_lines = sum(r['lines'] for r in recs)
    print('=' * 66)
    print('静态普查 A —— 全仓 .py 可解析性 / 编码')
    print('目标：%s' % TARGET)
    print('活代码文件 %d 个，备份文件 %d 个，合计行数 %d' % (len(recs), len(backups), total_lines))
    print('证据：%s' % dst.replace('\\', '/'))
    print('-' * 66)

    ok = True
    ok &= check(len(recs) > 0, 'A1 扫描到活代码文件（实际 %d 个）—— 空扫描是恒真陷阱' % len(recs))
    ok &= check(not bad_parse, 'A2 全部文件可 ast.parse（不可解析 %d 个）' % len(bad_parse))
    for r in bad_parse:
        print('      ! %s :: %s' % (r['file'], r.get('parse_error')))
    ok &= check(not bad_utf8, 'A3 全部文件可按 UTF-8 严格解码（失败 %d 个）' % len(bad_utf8))
    for r in bad_utf8:
        print('      ! %s :: %s' % (r['file'], r.get('decode_error')))
    ok &= check(not with_bom, 'A4 活代码无 BOM（带 BOM %d 个）' % len(with_bom))
    for r in with_bom[:10]:
        print('      ! %s :: %s' % (r['file'], r['bom']))
    ok &= check(not with_repl, 'A5 活代码无 U+FFFD 替换符（含替换符 %d 个）' % len(with_repl))
    for r in with_repl[:10]:
        print('      ! %s :: %d 个' % (r['file'], r['replacement_chars']))

    # --- 负控制：扫描器必须真的会说谎才会被信 ---
    print('-' * 66)
    neg_ok = True
    neg_ok &= check(inspect('__neg__.py', _write_tmp('x = (1\n'))['parse_ok'] is False,
                    'A6 负控制：故意坏语法必须被判不可解析')
    neg_ok &= check(inspect('__neg2__.py', _write_tmp('\ufeffx = 1\n'))['bom'] == 'utf-8-sig',
                    'A7 负控制：故意加 BOM 必须被检出')
    neg_ok &= check(inspect('__neg3__.py', _write_tmp('\ufffdx = 1\n'))['replacement_chars'] == 1,
                    'A8 负控制：故意加 U+FFFD 必须被计数')
    # 正控制：正常文件必须绿
    neg_ok &= check(inspect('__pos__.py', _write_tmp('x = 1\n'))['parse_ok'] is True,
                    'A9 正控制：正常文件必须可解析')

    print('=' * 66)
    print('结论：主判据 %s / 自检判据 %s' % ('PASS' if ok else 'FAIL',
                                            'PASS' if neg_ok else 'FAIL'))
    return 0 if (ok and neg_ok) else 1


_TMP = []


def _write_tmp(content):
    p = os.path.join(OUT, '_negctrl_tmp.py')
    os.makedirs(OUT, exist_ok=True)
    with io.open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(content)
    _TMP.append(p)
    return p


if __name__ == '__main__':
    rc = main()
    for p in _TMP:
        try:
            os.remove(p)
        except OSError:
            pass
    sys.exit(rc)
