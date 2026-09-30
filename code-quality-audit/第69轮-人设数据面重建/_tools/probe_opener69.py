# -*- coding: utf-8 -*-
"""第69轮 · 探针：76 份 persona 的首行开场白形状（判据设计用，不落任何产品文件）。

为什么写这个
------------
`update_index69.py` 的旧 `OPENER` 正则只认「以《A》中的 X 的身份」，
对 `ut_chara` 的新写法「以《A》**与**《B》中的 X 的身份」解析失败。
★ 这是**判据过窄**（第64轮老教训：24 字名字上限漏掉 `The World Machine`）。
先量出全部 76 份首行的真实形状，再决定放宽到什么程度 —— 不要凭猜改正则。
"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
PER = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', 'persona')

OLD = re.compile(r'你是一个角色扮演 AI，你将完全以《([^》]+)》中的\s*'
                 r'(.{1,60}?)\s*的(?:双重)?身份进行对话')
NEW = re.compile(r'你是一个角色扮演 AI，你将完全以\s*'
                 r'(?P<works>《[^》]+》(?:\s*[与和、]\s*《[^》]+》)*)\s*'
                 r'中的\s*(?P<name>.{1,60}?)\s*的(?:双重)?身份进行对话')
WORK_RE = re.compile(r'《([^》]+)》')

files = sorted(f for f in os.listdir(PER) if f.endswith('.txt'))
n_old_nomatch = 0
multi = []
for f in files:
    pid = f[:-4]
    txt = open(os.path.join(PER, f), 'rb').read().decode('utf-8', 'replace')
    head = txt.replace('\r\n', '\n').replace('\r', '\n').split('\n', 1)[0]
    mo, mn = OLD.search(head), NEW.search(head)
    if not mo:
        n_old_nomatch += 1
    if not mn:
        print('[FAIL] %-24s 连新正则都解析不了：%r' % (pid, head[:120]))
        continue
    works = [w.strip() for w in WORK_RE.findall(mn.group('works'))]
    if len(works) > 1:
        multi.append((pid, works, mn.group('name').strip()))
    if not mo:
        print('[OLD-MISS] %-22s works=%s name=%r' % (pid, works, mn.group('name').strip()))

print('')
print('总数 = %d' % len(files))
print('旧正则解析不了的 = %d' % n_old_nomatch)
print('多作品开场白（>1 个《》）= %d' % len(multi))
for pid, works, name in multi:
    print('  %-22s %-46s name=%r' % (pid, ' + '.join(works), name))
