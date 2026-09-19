# -*- coding: utf-8 -*-
"""P3-00：探针前置检查 —— Ollama 是否真能推理 + ralsei:v3 是否在 + 召回链路是否通。"""
import io, json, os, sys, urllib.request, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
# ⚠️ `modules` 是 ralsei_pet 下的包 → 必须把 **ralsei_pet 自己** 放进 path，
# 放仓库根（ROOT）会 ModuleNotFoundError: modules（本轮踩过）。
PET = os.path.join(ROOT, 'ralsei_pet')
OUT = os.path.join(HERE, '_evidence', 'P3_probe_precheck.txt')
BUF = []


def log(s):
    BUF.append(str(s))


def http(url, data=None, timeout=30):
    req = urllib.request.Request(url, data=data,
                                 headers={'Content-Type': 'application/json'} if data else {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


log('探针前置检查 · %s' % time.strftime('%Y-%m-%d %H:%M:%S'))
log('=' * 60)

# 1) Ollama 存活 + tags
try:
    tags = http('http://127.0.0.1:11434/api/tags')
    names = [m.get('name') for m in tags.get('models', [])]
    log('[1] /api/tags OK  模型=%r' % (names,))
except Exception as e:
    log('[1] /api/tags 失败 %r' % (e,))
    names = []

# 2) 真发一次 /api/chat（判"能不能推理"必须真发，tags 通 != 能推理）
model = 'ralsei:v3'
if model not in (names or []):
    cands = [n for n in (names or []) if n and n.startswith('ralsei')]
    if cands:
        model = cands[0]
        log('[2] ralsei:v3 不在，改用 %s' % model)
try:
    body = json.dumps({'model': model, 'stream': False,
                       'messages': [{'role': 'user', 'content': '说一个字：好'}]}).encode('utf-8')
    t0 = time.time()
    d = http('http://127.0.0.1:11434/api/chat', data=body, timeout=180)
    dt = time.time() - t0
    txt = (d.get('message') or {}).get('content', '')
    log('[2] /api/chat OK (%.1fs) 模型=%s 回复=%r' % (dt, model, txt[:80]))
    CAN = True
except Exception as e:
    log('[2] /api/chat 失败 %r' % (e,))
    CAN = False

# 3) 召回链路（不依赖 Ollama，纯本地）
sys.path.insert(0, PET)
try:
    import modules.worldview_recall as WR
    blocks = WR.load_blocks()
    log('[3] 召回模块 OK  块数=%d' % len(blocks))
    for q in ('黑暗喷泉是啥', '你还记得 Dess 吗', '我最近好累啊'):
        got = [b.label for b in WR.recall(q, limit=2)]
        log('    %-14s -> %r' % (q, got))
except Exception as e:
    log('[3] 召回模块失败 %r' % (e,))

log('')
log('结论：Ollama 可推理 = %s ; 可用模型 = %s' % (CAN, model))

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(BUF) + '\n')
print('WROTE', OUT)
