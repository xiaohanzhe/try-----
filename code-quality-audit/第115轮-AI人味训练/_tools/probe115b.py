# -*- coding: utf-8 -*-
"""第115轮 · 只读探针 B：**绕过代理**直连 Ollama + 模型元信息。

★ 探针 A 的 502 Bad Gateway 不是"Ollama 没起"，而是 `urllib` 默认吃 `HTTP_PROXY`
  环境变量 ⇒ 连 127.0.0.1 也被丢给代理。本探针用 `ProxyHandler({})` 显式直连。
★ 仍只读：只发 HTTP 请求 / 只读文件。
"""
import io
import json
import os
import socket
import urllib.request

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'probe115b_out.txt')
LINES = []


def w(s):
    LINES.append(s)
    print(s)


w(u'=== 0. 环境里的代理变量（为什么 A 会 502）===')
for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY',
          'http_proxy', 'https_proxy', 'all_proxy', 'no_proxy'):
    v = os.environ.get(k)
    if v:
        w(u'   %-14s = %s' % (k, v))

w(u'')
w(u'=== 1. TCP 直连 127.0.0.1:11434 ===')
for port in (11434, 11435):
    s = socket.socket()
    s.settimeout(2.0)
    try:
        s.connect(('127.0.0.1', port))
        w(u'   [OPEN]  127.0.0.1:%d' % port)
    except Exception as e:
        w(u'   [CLOSED] 127.0.0.1:%d  (%r)' % (port, e))
    finally:
        s.close()

# ★ 关键：显式绕代理
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def req(path, payload=None, timeout=30):
    url = 'http://127.0.0.1:11434' + path
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    headers = {'Content-Type': 'application/json'} if data else {}
    r = urllib.request.Request(url, data=data, headers=headers)
    with _OPENER.open(r, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


w(u'')
w(u'=== 2. /api/tags（绕代理）===')
names = []
try:
    tags = req('/api/tags', timeout=10)
    models = tags.get('models', [])
    names = [m.get('name') for m in models]
    w(u'[OK] 模型 %d 个' % len(models))
    for m in models:
        det = m.get('details') or {}
        w(u'   - %-32s size=%-12s %-10s %s'
          % (m.get('name'), m.get('size'),
             det.get('parameter_size'), det.get('quantization_level')))
except Exception as e:
    w(u'[FAIL] %r' % (e,))

w(u'')
w(u'=== 3. 重点模型元信息（/api/show，绕代理）===')
cands = [n for n in names if 'ralsei' in (n or '').lower()]
if not cands:
    cands = names[:3]
for n in cands:
    try:
        d = req('/api/show', {'name': n}, timeout=25)
    except Exception as e:
        w(u'[FAIL] show(%s) %r' % (n, e))
        continue
    det = d.get('details') or {}
    mi = d.get('model_info') or {}
    w(u'--- %s ---' % n)
    w(u'   parent=%s  family=%s  size=%s  quant=%s'
      % (det.get('parent_model'), det.get('family'),
         det.get('parameter_size'), det.get('quantization_level')))
    for k in sorted(mi):
        if any(t in k for t in ('context_length', 'embedding_length',
                                'block_count', 'head_count')):
            w(u'   %-46s %s' % (k, mi[k]))
    w(u'   parameters = %r' % (d.get('parameters'),))
    sysmsg = d.get('system')
    w(u'   system.len = %s' % (len(sysmsg) if sysmsg else 0))
    if sysmsg:
        w(u'   system[0:200] = %r' % (sysmsg[:200],))
    w(u'   template.len = %d' % len(d.get('template') or u''))

w(u'')
w(u'=== 4. 显存/内存相关（能不能跑 7B）===')
try:
    import subprocess
    r = subprocess.run(['wmic', 'path', 'win32_videocontroller', 'get',
                        'name,AdapterRAM'],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    w(u'   wmic: %s' % r.stdout.decode('utf-8', 'replace').strip()[:400])
except Exception as e:
    w(u'   （跳过：%r）' % (e,))

with io.open(OUT, 'w', encoding='utf-8', newline='') as fh:
    fh.write(u'\n'.join(LINES) + u'\n')
print(u'\n报告 = %s' % OUT)
