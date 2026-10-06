# -*- coding: utf-8 -*-
u"""对 G2 输出里"输出与基线不一致"的套件逐个分类，方便一次性裁定：

  · `COUNT-ONLY` —— 归一化文本相同、只有计数/退出码不同（通常是**断言数变了**，合法）
  · `CONTENT`    —— 归一化文本有差异（逐行列出 +/- 作为待裁定证据）

用法： python classify_diff93.py <g2_output.txt>
"""
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
OUT = os.path.join(ROOT, 'code-quality-audit', 'regress', '_out')


def main():
    p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ROOT, 'code-quality-audit', '第93轮-基础宠物功能收口', '_evidence',
        'g2_after_8889_restore.txt')
    txt = open(p, 'rb').read().decode('utf-8', 'replace')
    ids = re.findall(r'^\s+- (\w+): 输出与基线不一致', txt, re.M)
    print('DIFF 套件共 %d：%s' % (len(ids), ' '.join(ids)))
    print('G2 行：%s' % ' / '.join(re.findall(r'合计：.*', txt)))
    count_only, content = [], []
    for s in ids:
        f = os.path.join(OUT, s + '.diff.txt')
        if not os.path.exists(f):
            print('  [无 diff 文件] %s' % s)
            continue
        d = open(f, 'rb').read().decode('utf-8', 'replace')
        if '归一化文本相同' in d:
            count_only.append(s)
        else:
            content.append(s)
    print('\n=== COUNT-ONLY（%d）===\n%s' % (len(count_only), ' '.join(count_only)))
    print('\n=== CONTENT（%d）===' % len(content))
    for s in content:
        d = open(os.path.join(OUT, s + '.diff.txt'), 'rb').read().decode('utf-8', 'replace')
        plus = [l for l in d.splitlines() if l.startswith('+') and not l.startswith('+++')]
        minus = [l for l in d.splitlines() if l.startswith('-') and not l.startswith('---')]
        print('\n---- %s：+%d / -%d ----' % (s, len(plus), len(minus)))
        for l in minus[:14]:
            print('   %s' % l)
        for l in plus[:14]:
            print('   %s' % l)
    return 0


if __name__ == '__main__':
    sys.exit(main())
