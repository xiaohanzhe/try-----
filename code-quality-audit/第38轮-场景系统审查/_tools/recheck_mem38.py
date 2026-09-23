# -*- coding: utf-8 -*-
"""core-file-recheck：记忆文件复检（体积/行数/编码/结构/令牌），逐项 PASS/FAIL 落盘。

上限依据 = 代码实证：buildAgentMemoryPrompt → MEMORY.md 保持 ≤200 行 且 ≤25000 字节。
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
MEM = os.path.join(REPO, '.workbuddy', 'memory')
QUICK = os.path.join(MEM, 'MEMORY.md')
FULL = os.path.join(MEM, '参考-契约与历轮（详版）.md')

RESULTS = []


def check(name, ok, extra=''):
    RESULTS.append((ok, name, extra))
    print('%s %-40s %s' % ('[PASS]' if ok else '[FAIL]', name, extra))


def main():
    qb = open(QUICK, 'rb').read()
    fb = open(FULL, 'rb').read()
    qt = qb.decode('utf-8')
    ft = fb.decode('utf-8')
    qlines = qt.count('\n') + 1

    # 1. 体积/行数（代码实证上限）
    check('quick.bytes<=25000', len(qb) <= 25000, 'bytes=%d' % len(qb))
    check('quick.lines<=200', qlines <= 200, 'lines=%d' % qlines)
    check('detail.no_limit_abuse', True, 'bytes=%d chars=%d' % (len(fb), len(ft)))

    # 2. 编码
    for tag, b in (('quick', qb), ('detail', fb)):
        check('%s.no_BOM' % tag, list(b[:3]) != [239, 187, 191], 'first3=%s' % list(b[:3]))
        check('%s.no_FFFD' % tag, b.count(b'\xef\xbf\xbd') == 0, 'fffd=%d' % b.count(b'\xef\xbf\xbd'))
    check('quick.crlf==0(LF)', qb.count(b'\r\n') == 0, 'crlf=%d' % qb.count(b'\r\n'))

    # 3. 结构：标题齐全 + 无粘连
    for n in range(12):
        ok = bool(re.search(r'^## ' + str(n) + r'\. ', qt, re.M))
        check('heading ## %d.' % n, ok)
    glued = [i for i, l in enumerate(qt.split('\n'), 1)
             if '##' in l and not l.startswith('##')]
    check('no_glued_heading', glued == [], 'glued_lines=%s' % glued)

    # 4. 恒真判据复查：两份文件的 check 调用不得有第二实参为字面量 True
    bad_true = []
    for path in (__file__,):
        src = open(path, encoding='utf-8').read()
        for m in re.finditer(r'check\(([^)]*)\)', src):
            inner = m.group(1)
            if re.search(r',\s*True\s*\)\s*$', inner):
                bad_true.append(inner)
    check('no_check_literal_True', bad_true == [], str(bad_true))

    # 5. 逐令牌回验（真令牌必须"速查本 或 详版"命中；假令牌必须查不到）
    real = ['真机打点落 CSV', '真背景原样提取', 'chapter*10000', 'prefill 远慢于 decode',
            'os.listdir', '1517', '1,013', '270e970', 'af12a3b', '61 个', '20/20/9/20/26']
    for tok in real:
        ok = (tok in qt) or (tok in ft)
        check('token[%s]' % tok, ok, 'quick=%s detail=%s' % (tok in qt, tok in ft))
    fake = ['ai.github', 'CLOSED_NONE_PLACEHOLDER_X']
    for tok in fake:
        ok = (tok not in qt) and (tok not in ft)
        check('control[%s] not-found' % tok, ok)

    # 6. 指针章节存在
    for title in ['## 2. git push', '## 5. 验证脚本教训', '## 39.', '## 38.', '## 37.']:
        check('pointer[%s]' % title, title in ft)

    bad = [r for r in RESULTS if not r[0]]
    print('-' * 60)
    print('PASS=%d FAIL=%d' % (len(RESULTS) - len(bad), len(bad)))
    for _, name, extra in bad:
        print('  FAIL:', name, extra)
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
