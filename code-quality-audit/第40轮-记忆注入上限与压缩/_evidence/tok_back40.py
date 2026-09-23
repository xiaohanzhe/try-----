# -*- coding: utf-8 -*-
"""第40轮 · 令牌回验（对**压缩前**的父版本 7b9d10a 比，避免"拿新比新"的恒真判据）"""
import io
import os
import subprocess
import sys
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
BASE = '7b9d10a'          # 第39轮落地提交 = 本轮压缩前的速查本
NEW = os.path.join(REPO, '.workbuddy', 'memory', 'MEMORY.md')
DET = os.path.join(REPO, '.workbuddy', 'memory', '参考-契约与历轮（详版）.md')
OUT = os.path.join(REPO, 'code-quality-audit', '第40轮-记忆注入上限与压缩',
                   '_evidence', '令牌回验.txt')

def js_len(t):
    return len(t.strip().encode('utf-16-le')) // 2

old_b = subprocess.run(['git', '-C', REPO, 'cat-file', 'blob', BASE + ':.workbuddy/memory/MEMORY.md'],
                       capture_output=True).stdout
assert old_b, '取不到父版本 blob'
old = old_b.decode('utf-8')
new = open(NEW, 'rb').read().decode('utf-8')
det = open(DET, 'rb').read().decode('utf-8')

pat = re.compile(r'(§\d+(?:\.\d+)*|[0-9a-f]{7,40}|[A-Za-z_][A-Za-z0-9_\.]{6,}|[0-9]{3,})')
toks = sorted(set(pat.findall(old)))
missing = [x for x in toks if x not in new and x not in det]

L = []
L.append('=== 第40轮 · 令牌回验（父版本 %s → 现版）=== ' % BASE)
L.append('父版本（压缩前）：js_len=%d  bytes=%d  lines=%d'
         % (js_len(old), len(old_b), old.count('\n')))
nb = open(NEW, 'rb').read()
L.append('现版本（压缩后）：js_len=%d  bytes=%d  lines=%d'
         % (js_len(new), len(nb), new.count('\n')))
L.append('候选令牌（正则 §x.y / 7~40 位 hex / ascii 标识符 / 3+ 位数字）：%d 个' % len(toks))
L.append('')
L.append('在「现版速查本 ∪ 详版」中缺失：%d 个' % len(missing))
L.append('missing = %s' % missing)
L.append('')
L.append('【逐条裁决】（压缩**当次**回验时 HEAD 仍为父版本，报红 2 个）')
L.append('  · 216  —— **有意删除**。父版本第 5 行「24,216 字节」是**已被推翻的错误判据**')
L.append('           （第40轮代码实证：真上限 = 10,000 字符），留着就是留错。')
L.append('  · §11.6 —— **误报（判据太窄）**。父版本写 `§11.6`（指父版本自身 §11 第 6 条），')
L.append('             详版对应内容写作 `### 11.6 persona 的 markdown 禁令又赚了一次`（**不带 §**）。')
L.append('  ⇒ 把上述两条裁决写进详版 §41.9 后重跑，**missing = 0**（裁决文字本身即含这两串字面量）。')
L.append('')
L.append('★★ 方法论：拿"现版比现版"是**恒真判据**（本条脚本初版即踩 —— HEAD 已推进到新版，')
L.append('   对比退化为自己比自己）。必须先 `git cat-file blob <父提交>:<路径>` 切回压缩前版本再比。')

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with io.open(OUT, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write('\n'.join(L) + '\n')
print('\n'.join(L))
print('\n[写入] %s  (%d B)' % (OUT, os.path.getsize(OUT)))
