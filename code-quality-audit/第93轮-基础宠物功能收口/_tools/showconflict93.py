# -*- coding: utf-8 -*-
u"""只读：打印三方合并产物里的冲突块（OURS / BASE / THEIRS 三段），供人工裁定。

用法： C:\\Python311\\python.exe showconflict93.py <merged_file>
"""
import sys


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else r'E:\Download\_tmp\m88\merged.lf.py'
    lines = open(path, 'rb').read().decode('utf-8', 'replace').split('\n')
    starts = [i for i, l in enumerate(lines) if l.startswith('<<<<<<< ')]
    print('冲突块数: %d' % len(starts))
    for n, s in enumerate(starts, 1):
        e = next(i for i in range(s, len(lines)) if lines[i].startswith('>>>>>>> '))
        mid = next(i for i in range(s, e) if lines[i].startswith('||||||| '))
        sep = next(i for i in range(mid, e) if lines[i].startswith('======='))
        print('\n' + '=' * 96)
        print('### 冲突 %d：行 %d..%d   OURS=%d行  BASE=%d行  THEIRS=%d行'
              % (n, s + 1, e + 1, mid - s - 1, sep - mid - 1, e - sep - 1))
        for tag, a, b in (('OURS(93)', s + 1, mid), ('BASE', mid + 1, sep),
                          ('THEIRS(88_89)', sep + 1, e)):
            print('  ---- %s ----' % tag)
            for i in range(a, b):
                print('  %6d| %s' % (i + 1, lines[i]))


if __name__ == '__main__':
    main()
