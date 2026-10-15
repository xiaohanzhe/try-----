# -*- coding: utf-8 -*-
"""第115轮 · 只读探针 D：确认 Ollama 进程/端口现状（判"是沙箱拦了"还是"服务没起"）。

判据思路（**成对控制**）：
  · 拿**已知在跑**的本地端口（HTTP_PROXY）做**正控制** —— 若它连通，说明 localhost 可达；
  · 再试 11434 —— 若只有它不通，则结论是"Ollama 没监听"，而不是"沙箱拦网"。
"""
import io
import os
import socket
import subprocess

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'probe115d_out.txt')
LINES = []


def w(s):
    LINES.append(s)
    print(s)


def tcp(host, port, t=2.5):
    s = socket.socket()
    s.settimeout(t)
    try:
        s.connect((host, port))
        return 'OPEN'
    except Exception as e:
        return '%s (%s)' % (type(e).__name__, e)
    finally:
        s.close()


w(u'=== 1. 端口连通性（正控制 + 待测）===')
prox = os.environ.get('HTTP_PROXY', '')
pport = 0
try:
    pport = int(prox.rsplit(':', 1)[1])
except Exception:
    pass
if pport:
    w(u'   [正控制] 127.0.0.1:%d (HTTP_PROXY) -> %s' % (pport, tcp('127.0.0.1', pport)))
    w(u'   [正控制] localhost:%d            -> %s' % (pport, tcp('localhost', pport)))
w(u'   [待测]   127.0.0.1:11434        -> %s' % tcp('127.0.0.1', 11434))
w(u'   [待测]   ::1:11434              -> %s' % tcp('::1', 11434))
w(u'   [待测]   localhost:11434        -> %s' % tcp('localhost', 11434))

w(u'')
w(u'=== 2. 进程表里有没有 ollama ===')
try:
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq ollama*'],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    w(u'   tasklist(ollama*) rc=%d' % r.returncode)
    for ln in r.stdout.decode('utf-8', 'replace').splitlines():
        if ln.strip():
            w(u'      %s' % ln.rstrip())
except Exception as e:
    w(u'   （tasklist 失败：%r）' % (e,))
try:
    r = subprocess.run(['tasklist'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    tot = 0
    oll = []
    for ln in r.stdout.decode('utf-8', 'replace').splitlines():
        low = ln.lower()
        if 'ollama' in low:
            oll.append(ln.strip())
        if low.strip():
            tot += 1
    w(u'   进程总数 ~%d；含 ollama 的行 %d 条' % (tot, len(oll)))
    for ln in oll:
        w(u'      %s' % ln)
except Exception as e:
    w(u'   （全表 tasklist 失败：%r）' % (e,))

w(u'')
w(u'=== 3. server.log 尾部（看有没有 shutdown / 重启）===')
log = os.path.join(os.path.expandvars(r'%LOCALAPPDATA%'), 'Ollama', 'server.log')
if os.path.isfile(log):
    sz = os.path.getsize(log)
    w(u'   大小 = %d 字节' % sz)
    try:
        with io.open(log, encoding='utf-8', errors='replace') as fh:
            tail = fh.readlines()[-18:]
        for t in tail:
            w(u'      | %s' % t.rstrip()[:200])
    except Exception as e:
        w(u'   （读失败：%r）' % (e,))
else:
    w(u'   [MISS] %s' % log)

w(u'')
w(u'=== 4. ollama 客户端版本（不走网络）===')
exe = os.path.expandvars(r'%LOCALAPPDATA%\Programs\Ollama\ollama.exe')
w(u'   exe = %s  exists=%s' % (exe, os.path.isfile(exe)))
try:
    r = subprocess.run([exe, '--version'], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=25)
    w(u'   rc=%d out=%r err=%r' % (r.returncode,
                                  r.stdout.decode('utf-8', 'replace').strip(),
                                  r.stderr.decode('utf-8', 'replace').strip()))
except Exception as e:
    w(u'   （--version 失败：%r）' % (e,))

with io.open(OUT, 'w', encoding='utf-8', newline='') as fh:
    fh.write(u'\n'.join(LINES) + u'\n')
print(u'\n报告 = %s' % OUT)
