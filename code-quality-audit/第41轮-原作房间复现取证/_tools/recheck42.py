# -*- coding: utf-8 -*-
"""第41轮 · 复检（v2：修掉"判据太窄"——详版写 `### 11.5` 而速查本写 `§11.5`，已误报 3 次）
只打印，不落盘（避开写入通道抖动）。"""
import io
import os
import re
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
MEM = os.path.join(REPO, '.workbuddy', 'memory', 'MEMORY.md')
DET = os.path.join(REPO, '.workbuddy', 'memory', '参考-契约与历轮（详版）.md')
BASE = '7b9d10a'          # 压缩前父提交（第39轮落地）= 本轮压缩对照基准


def js_len(t):
    return len(t.strip().encode('utf-16-le')) // 2


def rd(p):
    with open(p, 'rb') as f:
        return f.read()


b = rd(MEM)
t = b.decode('utf-8')
det = rd(DET).decode('utf-8')
cap = 10000
print('=' * 72)
print('【1】体积  js_len=%d  bytes=%d  lines=%d  cap=%d => %s（余量 %d）'
      % (js_len(t), len(b), t.count('\n'), cap,
         'OK' if js_len(t) <= cap else '!!! 超限 %d' % (js_len(t) - cap), cap - js_len(t)))
print('【2】编码  BOM=%s  fffd=%d  CRLF=%d  LF=%d  结尾换行=%s'
      % (b[:3] == b'\xef\xbb\xbf', t.count('\ufffd'), t.count('\r\n'), t.count('\n'), t.endswith('\n')))
print('【3】结构  ## 标题=%s  glued=%s'
      % (','.join(re.findall(r'(?m)^##\s+(\d+)\.', t)),
         re.findall(r'(?m)^##\s+\d+\.[^\n]*\S##', t)))

oldt = subprocess.run(['git', '-C', REPO, 'cat-file', 'blob',
                       BASE + ':.workbuddy/memory/MEMORY.md'],
                      capture_output=True).stdout.decode('utf-8')
pat = re.compile(r'(§\d+(?:\.\d+)*|[0-9a-f]{7,40}|[A-Za-z_][A-Za-z0-9_\.]{6,}|[0-9]{3,})')


def hit(x, text):
    if x in text:
        return True
    bare = x.lstrip('\u00a7')
    return bare != x and bare in text


toks = sorted(set(pat.findall(oldt)))
missing = [x for x in toks if not hit(x, t) and not hit(x, det)]
print('【4】令牌回验（父提交 %s，宽匹配 § 可选）：候选=%d  缺失=%d  %s'
      % (BASE, len(toks), len(missing), missing))
only = [x for x in sorted(set(pat.findall(t))) if not hit(x, det)]
print('【5】速查本独有（详版无，多为自引用指针）：%d 个 %s' % (len(only), only))
st = subprocess.run(['git', '-C', REPO, 'status', '--porcelain'],
                    capture_output=True).stdout.decode('utf-8', 'replace').strip()
print('【6】工作区 = %s' % (st.replace('\n', ' | ') if st else '(干净)'))
