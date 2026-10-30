# -*- coding: utf-8 -*-
"""编辑保真复检：语法 + 字节忠实行尾（`newline=''`）+ 编码。

★ 为什么要单独做：本项目的 `main.py` 是 **CRLF**（16821 行），
  一次"看似无害"的编辑就可能把整份文件变成 LF（git diff 会显示全文件改动，
  且 `check107` 那类锚点判据会误报）。`npc_system.py` / `npc_errand.py` 是 LF。
★ 判据：**只 `ast.parse`**，不 `py_compile`（不产 `.pyc`，不改变被测状态）。
"""
import ast
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))

#: (相对路径, 期望的换行风格, 改动前的基线)
TARGETS = (
    ('ralsei_pet/modules/npc_system.py', 'LF', None),
    ('ralsei_pet/modules/npc_errand.py', 'LF', None),
    ('ralsei_pet/src/main.py', 'CRLF', 16821),
    # ★ 本轮**新改**的第四个文件：行尾风格先只**观测**（`None`），
    #   跑一次看到基线值后再决定要不要设成硬判据。
    ('ralsei_pet/modules/dialogue_ui.py', None, None),
)

ok = fail = 0


def ck(name, cond, detail=''):
    global ok, fail
    if cond:
        ok += 1
        print('[PASS] %s%s' % (name, ('  | ' + detail) if detail else ''))
    else:
        fail += 1
        print('[FAIL] %s  | %s' % (name, detail))


for rel, style, base_crlf in TARGETS:
    p = os.path.join(ROOT, *rel.split('/'))
    with io.open(p, 'r', encoding='utf-8', newline='') as fh:
        s = fh.read()
    crlf = s.count('\r\n')
    bare_lf = s.count('\n') - crlf
    bare_cr = s.count('\r') - crlf
    nbytes = len(s.encode('utf-8'))
    try:
        ast.parse(s)
        syn = True
    except SyntaxError as e:
        syn = False
        print('       SyntaxError: %r' % (e,))
    print('--- %s' % rel)
    print('    bytes=%d  crlf=%d  bare_lf=%d  bare_cr=%d  bom=%s  ufffd=%d'
          % (nbytes, crlf, bare_lf, bare_cr, s.startswith('\ufeff'), s.count('\ufffd')))
    ck('%s 语法可解析' % rel, syn)
    ck('%s 无裸 \\r 混入' % rel, bare_cr == 0, 'bare_cr=%d' % bare_cr)
    ck('%s 无 UTF-8 BOM' % rel, not s.startswith('\ufeff'))
    ck('%s 无 U+FFFD（编码损坏痕迹）' % rel, s.count('\ufffd') == 0)
    if style == 'CRLF':
        ck('%s 保持纯 CRLF（无裸 LF 混入）' % rel, bare_lf == 0, 'bare_lf=%d' % bare_lf)
        if base_crlf:
            ck('%s CRLF 数不低于基线 %d（只增不减 ⇒ 没被整份改写）'
               % (rel, base_crlf), crlf >= base_crlf, 'crlf=%d' % crlf)
    elif style == 'LF':
        ck('%s 保持纯 LF（无 CRLF 混入）' % rel, crlf == 0, 'crlf=%d' % crlf)
    else:
        ck('%s 换行风格自洽（CRLF 与裸 LF 不混）' % rel,
           (crlf == 0) or (bare_lf == 0), 'crlf=%d bare_lf=%d' % (crlf, bare_lf))

print('')
print('=' * 60)
print('verify114_eol  PASS=%d  FAIL=%d' % (ok, fail))
sys.exit(1 if fail else 0)
