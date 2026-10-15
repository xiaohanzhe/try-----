# -*- coding: utf-8 -*-
"""第115轮 · 只读探针 A：Ollama 环境 + 模型元信息 + persona 资产清单。

★ 只读：只发 HTTP 请求 / 只读文件，不改任何工程文件。
★ 一律走 REST API + 显式 UTF-8 解码（CLI 管道会把中文变 GBK 乱码 ⇒ 误判"设定已损坏"）。
输出落文件，不依赖 shell stdout 回传。
"""
import io
import json
import os
import urllib.request

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'probe115a_out.txt')
LINES = []


def w(s):
    LINES.append(s)
    print(s)


def req(path, payload=None, timeout=30, method=None):
    url = 'http://127.0.0.1:11434' + path
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    r = urllib.request.Request(url, data=data, headers=headers,
                               method=method or ('POST' if data else 'GET'))
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


w(u'=== 1. Ollama 是否在跑 ===')
try:
    tags = req('/api/tags', timeout=8)
    names = [m.get('name') for m in tags.get('models', [])]
    w(u'[OK] /api/tags 可达；模型 %d 个' % len(names))
    for m in tags.get('models', []):
        w(u'   - %-34s %10s  %s' % (m.get('name'),
                                    m.get('size'),
                                    (m.get('details') or {}).get('parameter_size')))
except Exception as e:
    names = []
    w(u'[FAIL] /api/tags 不可达：%r' % (e,))
    w(u'   ⇒ 说明 Ollama 服务没起（或换了端口）。需要用户先启动 Ollama。')

w(u'')
w(u'=== 2. 候选模型元信息（/api/show）===')
cands = [n for n in names if 'ralsei' in (n or '').lower()] or names[:4]
for n in cands:
    try:
        d = req('/api/show', {'name': n}, timeout=20)
    except Exception as e:
        w(u'[FAIL] show(%s): %r' % (n, e))
        continue
    det = d.get('details') or {}
    w(u'--- %s ---' % n)
    for k in ('parent_model', 'format', 'family', 'families',
              'parameter_size', 'quantization_level'):
        w(u'   %-20s %s' % (k, det.get(k)))
    for k in ('context_length', 'embedding_length'):
        if k in (d.get('model_info') or {}):
            w(u'   %-20s %s' % (k, (d['model_info'] or {}).get(k)))
    params = d.get('parameters')
    w(u'   parameters          %r' % (params,))
    w(u'   ★ parameters=None ⇒ Modelfile 里没有任何 PARAMETER 覆盖'
      u'（采样/num_ctx 全走服务端默认）'
      if params is None else u'   ★ parameters 非空 ⇒ 有覆盖')
    sysmsg = d.get('system')
    w(u'   system              len=%s' % (len(sysmsg) if sysmsg else 0))
    if sysmsg:
        w(u'   system[0:160]       %r' % (sysmsg[:160],))
    tmpl = d.get('template') or ''
    w(u'   template            len=%d' % len(tmpl))

w(u'')
w(u'=== 3. persona / 人设资产清单 ===')
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..', '..'))
ASSETS = os.path.join(ROOT, 'ralsei_pet', 'assets')
for rel in ('ralsei_persona.md',):
    p = os.path.join(ASSETS, rel)
    if os.path.isfile(p):
        s = io.open(p, encoding='utf-8', newline='').read()
        w(u'[OK] %-28s chars=%d  CRLF=%d' % (rel, len(s), s.count(u'\r\n')))
    else:
        w(u'[MISS] %s' % rel)
pdir = os.path.join(ASSETS, 'npc', 'persona')
if os.path.isdir(pdir):
    fs = sorted(f for f in os.listdir(pdir) if f.endswith('.txt'))
    w(u'[OK] npc/persona/*.txt  %d 个' % len(fs))
    tot = 0
    for f in fs:
        s = io.open(os.path.join(pdir, f), encoding='utf-8', newline='').read()
        tot += len(s)
    w(u'     合计 %d 字符，均 %.0f 字/个' % (tot, tot / max(1, len(fs))))
    w(u'     样例：%s' % ', '.join(fs[:10]))
else:
    w(u'[MISS] npc/persona 目录')
for rel in (('npc', '_registry.json'),):
    p = os.path.join(ASSETS, *rel)
    w(u'[%s] %s' % ('OK' if os.path.isfile(p) else 'MISS', os.path.join(*rel)))

w(u'')
w(u'=== 4. 生成链路的"权重"落点（只读 grep）===')
SRC = os.path.join(ROOT, 'ralsei_pet')
import re
pats = [u'temperature', u'top_p', u'num_ctx', u'repeat_penalty', u'num_predict',
        u'keep_alive', u'/api/chat', u'v1/chat/completions', u'max_tokens']
hits = {}
for dp, dn, fn in os.walk(SRC):
    for f in fn:
        if not f.endswith('.py'):
            continue
        p = os.path.join(dp, f)
        try:
            s = io.open(p, encoding='utf-8', newline='').read()
        except Exception:
            continue
        for pat in pats:
            if pat in s:
                hits.setdefault(pat, []).append(os.path.relpath(p, ROOT))
for pat in pats:
    v = sorted(hits.get(pat, []))
    w(u'   %-22s %s' % (pat, u', '.join(v) if v else u'（无）'))

with io.open(OUT, 'w', encoding='utf-8', newline='') as fh:
    fh.write(u'\n'.join(LINES) + u'\n')
print(u'\n报告 = %s' % OUT)
