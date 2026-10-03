# -*- coding: utf-8 -*-
"""压缩后逐令牌回验：删/改过的关键令牌必须仍可检索（速查本 或 详版里在）。"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
MEM = os.path.join(ROOT, '.workbuddy', 'memory', 'MEMORY.md')
DET = os.path.join(ROOT, '.workbuddy', 'memory', '参考-契约与历轮（详版）.md')

mem = io.open(MEM, encoding='utf-8').read()
det = io.open(DET, encoding='utf-8').read()

# 本轮压缩期间被"动过/删过"的可检索令牌（宽松匹配：§ 可选）
tokens = [
    'js_len', 'utf-16-le', 'core-file-recheck',
    'E:\\Download\\_tmp', 'numstat', 'surrogateescape',
    'helper-selector', 'wincredman',
    'AI_REPLY_MAX_CHARS', 'A12d', '_clean_ai_reply',
    'PENDING_UPDATE', 'check81', 'G5n',
    'POSSESSION_KINDS', 'possession.py', 'ConsentState',
    '§73.7', 'R6', 'os_niko',
    'BEDTIME_HOME_SCENE', 'NPC_AUTONOMOUS_MOVE',
    'pet_interaction', 'NUM_PARALLEL',
]
P = F = 0
lines = ['=== 第82轮记忆压缩：逐令牌回验 ===', '']
for tk in tokens:
    in_mem = tk in mem
    in_det = tk in det
    ok = in_mem or in_det          # 只要速查本或详版有一处可检索即可
    lines.append('[%s] %-26s 速查本=%s 详版=%s' % (
        'PASS' if ok else 'FAIL', tk, in_mem, in_det))
    P += 1 if ok else 0
    F += 0 if ok else 1

# 结构性守恒：速查本里的 11 个章节标题必须都在
for h in ['## 0.', '## 1.', '## 2.', '## 3.', '## 4.', '## 5.', '## 6.',
          '## 7.', '## 8.', '## 9.', '## 10.', '## 11.']:
    ok = h in mem
    lines.append('[%s] 章节 %s' % ('PASS' if ok else 'FAIL', h))
    P += 1 if ok else 0
    F += 0 if ok else 1

lines += ['', '结果：PASS=%d FAIL=%d' % (P, F)]
OUT = os.path.join(HERE, '..', '_evidence', 'recheck82_memtokens.txt')
OUT = os.path.normpath(OUT)
io.open(OUT, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
print('\n'.join(lines))
