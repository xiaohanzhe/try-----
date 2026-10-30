# -*- coding: utf-8 -*-
"""第115轮 · 只读探针 C：找 ollama.exe / 模型 blobs / 配置。"""
import io
import os
import shutil
import glob

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'probe115c_out.txt')
LINES = []


def w(s):
    LINES.append(s)
    print(s)


w(u'=== 1. ollama 可执行文件 ===')
p = shutil.which('ollama')
w(u'   shutil.which(ollama) = %r' % (p,))
cands = [
    os.path.expandvars(r'%LOCALAPPDATA%\Programs\Ollama\ollama.exe'),
    os.path.expandvars(r'%LOCALAPPDATA%\Ollama\ollama.exe'),
    r'C:\Program Files\Ollama\ollama.exe',
    os.path.expandvars(r'%USERPROFILE%\AppData\Local\Programs\Ollama\ollama.exe'),
]
for c in cands:
    w(u'   [%s] %s' % ('OK  ' if os.path.isfile(c) else 'MISS', c))

w(u'')
w(u'=== 2. ollama 模型目录 ===')
md = os.path.expandvars(r'%USERPROFILE%\.ollama')
for sub in ('', 'models', 'models\\blobs', 'models\\manifests'):
    d = os.path.join(md, sub) if sub else md
    w(u'   [%s] %s' % ('OK  ' if os.path.isdir(d) else 'MISS', d))
bd = os.path.join(md, 'models', 'blobs')
if os.path.isdir(bd):
    fs = os.listdir(bd)
    w(u'   blobs 文件数 = %d' % len(fs))
    # 只统计 >100MB 的（真权重）
    big = []
    for f in fs:
        fp = os.path.join(bd, f)
        try:
            sz = os.path.getsize(fp)
        except Exception:
            continue
        if sz > 100 * 1024 * 1024:
            big.append((sz, f))
    big.sort(reverse=True)
    w(u'   大文件（>100MB）%d 个：' % len(big))
    for sz, f in big[:12]:
        w(u'      %8.2f GB  %s' % (sz / 1024 ** 3, f))

w(u'')
w(u'=== 3. manifests（看有哪些模型被注册）===')
mroot = os.path.join(md, 'models', 'manifests')
if os.path.isdir(mroot):
    for dp, dn, fn in os.walk(mroot):
        for f in fn:
            rel = os.path.relpath(os.path.join(dp, f), mroot)
            w(u'   %s' % rel)

w(u'')
w(u'=== 4. Ollama 环境变量 / 日志 ===')
for k in ('OLLAMA_MODELS', 'OLLAMA_HOST', 'OLLAMA_NUM_PARALLEL',
          'OLLAMA_KEEP_ALIVE', 'OLLAMA_MAX_LOADED_MODELS'):
    v = os.environ.get(k)
    if v:
        w(u'   %-24s = %s' % (k, v))
log = os.path.join(os.path.expandvars(r'%LOCALAPPDATA%'), 'Ollama', 'server.log')
w(u'   server.log [%s] %s' % ('OK' if os.path.isfile(log) else 'MISS', log))
if os.path.isfile(log):
    sz = os.path.getsize(log)
    w(u'   server.log 大小 = %.2f MB' % (sz / 1024 ** 2))
    try:
        with io.open(log, encoding='utf-8', errors='replace') as fh:
            tail = fh.readlines()[-25:]
        for t in tail:
            w(u'      | %s' % t.rstrip()[:180])
    except Exception as e:
        w(u'   （读尾失败：%r）' % (e,))

with io.open(OUT, 'w', encoding='utf-8', newline='') as fh:
    fh.write(u'\n'.join(LINES) + u'\n')
print(u'\n报告 = %s' % OUT)
