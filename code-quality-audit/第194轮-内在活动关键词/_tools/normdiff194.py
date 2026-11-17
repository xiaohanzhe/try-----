# -*- coding: utf-8 -*-
r"""normdiff194.py —— diff 归一化核对（§168.4 铁序 ①②）

用法：python normdiff194.py <diff1> [diff2 ...]

做法（不看语义，纯机械）：
  1. 丢掉 `---`/`+++` 文件头与 `@@` 块头；
  2. 取 `-` 开头的行（去掉前导 `-`）与 `+` 开头的行（去掉前导 `+`）；
  3. 归一化：长 hex 串（>=8 位 [0-9a-f]）→ <HEX>；其余数字 → <N>；
  4. 逐份要求：两侧行数相等 且 逐行归一化后**全等**。

任何一行归一化后仍不等 ⇒ "意外差异"，脚本退出码 1（禁止 --update）。
"""
import io
import os
import re
import sys

_HEX = re.compile(r'[0-9a-f]{8,}')
_NUM = re.compile(r'\d+')


def norm(line):
    s = _HEX.sub(u'<HEX>', line)
    s = _NUM.sub(u'<N>', s)
    return s.rstrip()


def parse(path):
    minus, plus = [], []
    with io.open(path, 'r', encoding='utf-8', errors='replace', newline='') as f:
        for raw in f:
            line = raw.rstrip(u'\r\n')
            if line.startswith(u'---') or line.startswith(u'+++'):
                continue
            if line.startswith(u'@@'):
                continue
            if line.startswith(u'-'):
                minus.append(line[1:])
            elif line.startswith(u'+'):
                plus.append(line[1:])
    return minus, plus


def main(argv):
    if not argv:
        sys.stdout.write(u'用法：normdiff194.py <diff1> [diff2 ...]\n')
        return 2
    bad_files = 0
    for path in argv:
        name = os.path.basename(path)
        if not os.path.isfile(path):
            sys.stdout.write(u'[FAIL] %s 不存在\n' % name)
            bad_files += 1
            continue
        minus, plus = parse(path)
        n = len(minus)
        sys.stdout.write(u'===== %s =====\n' % name)
        sys.stdout.write(u'  -  行数=%d   + 行数=%d\n' % (n, len(plus)))
        if n == 0 and not plus:
            # 分母闸：一行差异都没解析出来 ⇒ 这次核对没有任何证据，不许当"通过"
            sys.stdout.write(u'  [FAIL] 解析不出任何 +/- 行（分母为 0）⇒ 本次核对无证据，不算通过\n')
            bad_files += 1
            continue
        if n != len(plus):
            sys.stdout.write(u'  [FAIL] 两侧行数不等 ⇒ 有增删行，不是纯取值位移\n')
            bad_files += 1
            continue
        bad = 0
        for i in range(n):
            a, b = norm(minus[i]), norm(plus[i])
            if a != b:
                bad += 1
                sys.stdout.write(u'  [DIFF] 第%d对\n    - %s\n    + %s\n    ~ %s\n    ~ %s\n'
                                 % (i + 1, minus[i][:160], plus[i][:160], a[:160], b[:160]))
        if bad == 0:
            sys.stdout.write(u'  [OK] 归一化后 %d/%d 对全等 ⇒ 差异只剩数字\n' % (n, n))
        else:
            sys.stdout.write(u'  [FAIL] 意外差异 %d 行\n' % bad)
            bad_files += 1
    sys.stdout.write(u'\n合计：%d 份，意外差异文件 %d 份\n' % (len(argv), bad_files))
    return 0 if bad_files == 0 else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
