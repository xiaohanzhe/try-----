# -*- coding: utf-8 -*-
"""第58轮：`keep_alive` 到底在哪条通路上生效 —— **实测，不靠猜**。

要回答三个问题（回答不了就别改产品代码）：
  Q1  OpenAI 兼容端点 `/v1/chat/completions` 吃 `keep_alive` 吗？   ← 产品走的就是这条
  Q2  原生端点 `/api/chat` 吃吗？（**正控制**：已知它吃，用来证明判据有鉴别力）
  Q3  `keep_alive` = "30m" / -1 / 0 分别对应什么 `expires_at`？      ← 读数口径

判据设计（防三种"看着成功"）：
  · **不能只看 HTTP 200** —— 200 只证明请求成功，不证明参数被采纳；
    真正的判据是 `ollama ps` 里的 `expires_at` **增量 ≈ 我要求的秒数**。
  · **必须有正控制** —— 原生端点若也读不到增量，说明是**我的读数口径错了**，
    而不是"兼容端点不支持"（否则会得出假结论）。
  · **卸载档（keep_alive=0）必须真的把模型卸掉**，否则说明 ps 读数不可信。

只读外部状态（发请求 / 读 /api/ps），不改产品代码，不改服务配置。
"""

import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = 'http://127.0.0.1:11434'
MODEL = 'ralsei:v4'
RDIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVID = os.path.join(RDIR, '_evidence')
os.makedirs(EVID, exist_ok=True)

_LOG = []


def say(s=''):
    print(s)
    _LOG.append(s)


def post(path, body, timeout=420):
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={'Content-Type': 'application/json'})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode('utf-8', 'replace')
            return r.status, raw, time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace'), time.time() - t0
    except Exception as e:                                        # noqa: BLE001
        return -1, repr(e), time.time() - t0


def ps():
    try:
        with urllib.request.urlopen(BASE + '/api/ps', timeout=15) as r:
            return json.loads(r.read().decode('utf-8', 'replace')).get('models') or []
    except Exception as e:                                        # noqa: BLE001
        say('  !! /api/ps 读取失败 %r' % (e,))
        return []


def show_ps(tag):
    ms = ps()
    if not ms:
        say('  [%s] ps = （空，无模型载入）' % tag)
        return None
    now = datetime.now(timezone.utc)
    for m in ms:
        exp = m.get('expires_at') or ''
        delta = None
        try:
            # ★★ 第58轮踩过的坑：**只截掉小数秒，绝不能重写时区**
            #    （旧写法 `.split('.')[0] + '+00:00'` 把 `+08:00` 换成 UTC，
            #      于是每个 Δ 都被抬高 8 小时 ⇒ 真假结论直接反转，且**报的是绿**）。
            s = re.sub(r'\.\d+', '', exp.replace('Z', '+00:00').strip())
            delta = (datetime.fromisoformat(s) - now).total_seconds()
        except Exception:                                         # noqa: BLE001
            pass
        say('  [%s] name=%s size=%.2fGB vram=%.2fGB expires_at=%s  ⇒ 还剩 %s'
            % (tag, m.get('name'), (m.get('size') or 0) / 2**30,
               (m.get('size_vram') or 0) / 2**30, exp,
               ('%.0fs' % delta) if delta is not None else '?'))
        m['_delta_s'] = delta
    return ms[0]


say('=' * 70)
say('第58轮 keep_alive 实测   %s' % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
say('=' * 70)
show_ps('起跑')

RESULT = {}

# ---------------------------------------------------------------- 0) 冷载
say()
say('0) 冷载一次（确保后面读到的 expires_at 都是本次请求造成的）')
st, raw, el = post('/v1/chat/completions', {
    'model': MODEL, 'messages': [{'role': 'user', 'content': '你好'}],
    'max_tokens': 1, 'stream': False})
say('   rc=%s  用时 %.1fs  body=%s' % (st, el, raw[:160]))
RESULT['cold_load_s'] = round(el, 1)
m = show_ps('冷载后（未指定 keep_alive ⇒ 应是默认 5 分钟）')
RESULT['default_delta_s'] = m and m.get('_delta_s')

# ------------------------------------------------- 1) 兼容端点 + keep_alive
say()
say('1) ★ Q1：OpenAI 兼容端点 `/v1/chat/completions` + keep_alive="30m"')
st, raw, el = post('/v1/chat/completions', {
    'model': MODEL, 'messages': [{'role': 'user', 'content': '你好'}],
    'max_tokens': 1, 'stream': False, 'keep_alive': '30m'})
say('   rc=%s  用时 %.1fs  body=%s' % (st, el, raw[:160]))
m = show_ps('兼容端点 keep_alive=30m 之后')
RESULT['compat_delta_s'] = m and m.get('_delta_s')
RESULT['compat_accepted'] = bool(m and (m.get('_delta_s') or 0) > 1500)

# ------------------------------------------------------ 2) 原生端点（正控制）
say()
say('2) Q2 正控制：原生端点 `/api/chat` + keep_alive="10m"')
st, raw, el = post('/api/chat', {
    'model': MODEL, 'messages': [{'role': 'user', 'content': '你好'}],
    'stream': False, 'keep_alive': '10m', 'options': {'num_predict': 1}})
say('   rc=%s  用时 %.1fs  body=%s' % (st, el, raw[:200]))
m = show_ps('原生端点 keep_alive=10m 之后')
RESULT['native_delta_s'] = m and m.get('_delta_s')
RESULT['native_accepted'] = bool(m and 480 < (m.get('_delta_s') or 0) < 900)
try:
    j = json.loads(raw)
    RESULT['native_load_duration_s'] = round((j.get('load_duration') or 0) / 1e9, 2)
    RESULT['native_total_duration_s'] = round((j.get('total_duration') or 0) / 1e9, 2)
    RESULT['native_prompt_eval_s'] = round((j.get('prompt_eval_duration') or 0) / 1e9, 2)
except Exception:                                                 # noqa: BLE001
    pass

# ------------------------------------------------------- 3) 卸载档（负控制）
say()
say('3) 负控制：`keep_alive=0` 必须真的卸掉（否则 ps 读数不可信）')
st, raw, el = post('/api/chat', {
    'model': MODEL, 'messages': [{'role': 'user', 'content': '你好'}],
    'stream': False, 'keep_alive': 0, 'options': {'num_predict': 1}})
say('   rc=%s  用时 %.1fs' % (st, el))
time.sleep(3)
ms = ps()
RESULT['unload_worked'] = (len(ms) == 0)
show_ps('keep_alive=0 之后')

# ------------------------------------------------------------------- 判定
say()
say('=' * 70)
say('判定')
say('=' * 70)
_dd = RESULT.get('default_delta_s')
_cd = RESULT.get('compat_delta_s')
_nd = RESULT.get('native_delta_s')
# ★★ Q1b：**相对判据** —— 跟"不传 keep_alive 的默认档"比。
#    绝对阈值会被时钟/口径的错影响；"和默认档没差别"才是"字段被丢掉"的直接证据。
RESULT['compat_same_as_default'] = bool(
    _dd is not None and _cd is not None and abs(_cd - _dd) < 60)
say('  基准：不传 keep_alive 的默认档 Δ ≈ %s s（官方默认 300s）' % _dd)
say('  Q1  兼容端点吃 keep_alive ?  %s   （要求 Δ>1500，实得 %s）'
    % ('是' if RESULT.get('compat_accepted') else '**否**', _cd))
say('  Q1b 更进一步：它与默认档**无差别** ? %s（|Δ差| = %s s < 60）'
    % ('是 ⇒ 字段被静默丢弃' if RESULT['compat_same_as_default'] else '否',
       None if (_dd is None or _cd is None) else round(abs(_cd - _dd))))
say('  Q2  原生端点吃 keep_alive ?  %s   （要求 480<Δ<900，实得 %s）  ← 正控制'
    % ('是' if RESULT.get('native_accepted') else '**否**', _nd))
say('  Q3  keep_alive=0 真卸载 ?    %s' % ('是' if RESULT.get('unload_worked') else '**否**'))
say('  冷载耗时 %.1fs（模型不在内存时的首次加载）' % (RESULT.get('cold_load_s') or 0))
say()
if RESULT.get('native_accepted') and not RESULT.get('compat_accepted'):
    say('  ⇒ 结论：兼容端点**丢字段**，产品要么换走 `/api/chat`，')
    say('     要么在请求里无条件带上——先证实再动手。')
elif RESULT.get('compat_accepted'):
    say('  ⇒ 结论：兼容端点**照收** ⇒ 产品只需在 payload 里带上 `keep_alive` 即可。')
else:
    say('  ⇒ 两个端点都读不到增量 ⇒ **先怀疑我的读数口径**（正控制没通过），')
    say('     不许据此下"不支持"的结论。')

out = os.path.join(EVID, 'keep_alive_probe.json')
io.open(out, 'w', encoding='utf-8').write(
    json.dumps(RESULT, ensure_ascii=False, indent=2))
io.open(os.path.join(EVID, 'keep_alive_probe.log'), 'w',
        encoding='utf-8').write('\n'.join(_LOG) + '\n')
say()
say('[写入] %s' % out)
