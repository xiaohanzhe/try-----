# -*- coding: utf-8 -*-
"""逐令牌回验：把"压缩时删掉的可检索令牌"逐个去详版 `in` 一次。

判据（第 37 轮沉淀）：
  「指针指向的章节存在」!= 「被删的内容在里面」。
  前者靠正则查标题就能过，后者必须逐令牌比对。
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
MEM_DIR = os.path.join(REPO, '.workbuddy', 'memory')
QUICK = os.path.join(MEM_DIR, 'MEMORY.md')
FULL = os.path.join(MEM_DIR, '参考-契约与历轮（详版）.md')

# 真令牌：压缩前在速查本里、压缩后可能被删。必须能在"速查本 或 详版"里找到。
REAL_TOKENS = [
    '真机打点落 CSV',
    '真背景原样提取',
    'chapter*10000',
    'prefill 远慢于 decode',
]
# 负面控制：预期查不到（验证判据有鉴别力，不是无脑 True）
FAKE_TOKENS = [
    'ai.github',
    'CLOSED_NONE_PLACEHOLDER_X',
]


def read(path):
    with open(path, 'r', encoding='utf-8') as fh:
        return fh.read()


def main():
    quick = read(QUICK)
    full = read(FULL)
    print('MEMORY.md chars=%d bytes=%d' % (len(quick), len(QUICK.encode('utf-8')) if False else os.path.getsize(QUICK)))
    print('详版   chars=%d bytes=%d' % (len(full), os.path.getsize(FULL)))
    print('-' * 50)

    bad = 0
    for tok in REAL_TOKENS:
        q = tok in quick
        f = tok in full
        ok = q or f
        if not ok:
            bad += 1
        print('%s %-28s 速查本=%-5s 详版=%-5s' % ('OK ' if ok else '!! ', tok, q, f))

    print('-' * 50)
    ctrl_bad = 0
    for tok in FAKE_TOKENS:
        q = tok in quick
        f = tok in full
        if q or f:
            ctrl_bad += 1
        print('CTL %-28s 速查本=%-5s 详版=%-5s %s'
              % (tok, q, f, '<-- 假令牌竟命中，判据有洞！' if (q or f) else '(预期查不到)'))

    print('-' * 50)
    print('真令牌缺失 %d 个；假令牌误命中 %d 个' % (bad, ctrl_bad))

    # 指针章节存在性（用详版真实标题）
    print('-' * 50)
    print('指针章节：')
    for title in ['## 2. git push', '## 5. 验证脚本教训', '## 39.', '## 38.', '## 37.']:
        print('  %-24s 详版=%s' % (title, title in full))

    return 0 if (bad == 0 and ctrl_bad == 0) else 1


if __name__ == '__main__':
    sys.exit(main())
