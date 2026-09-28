# -*- coding: utf-8 -*-
"""第58轮：**保温窗口会不会被后续请求重置回默认 5 分钟** —— 决定"设置一次"够不够。

已经证实（probe_keepalive.py）：
  · 兼容端点 `/v1/chat/completions` **静默丢弃** `keep_alive`；
  · 原生端点 `/api/chat` **采纳** `keep_alive`。

于是产品只有两条路：改走原生端点，或**在应用侧定期给原生端点发一次心跳**。
但后者值不值得做，取决于一个问题：

  Q  「先用 keep_alive=30m 把窗口撑到 30 分钟」之后，
      中间来一次**不带 keep_alive 的兼容端点请求**，窗口会不会**被打回 5 分钟**？

  会  ⇒ 心跳**必需**（每次正常对话都会把窗口缩回 5 分钟）；
  不会 ⇒ 启动时设一次就够，心跳是多余的复杂度。

判据：**只看 `ollama ps` 的 expires_at 增量**，不看 HTTP 码（200 不证明任何事）。
每一步都设正/负对照：30m 档必须读 ≈1800s、默认档必须读 ≈300s，两个读数都能复现才敢用它判 Q。
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

_LOG = []


def say(s=''):
    print(s)
    _LOG.append(s)


def post(path, body, timeout=180):
    req = urllib.request.Request(BASE + path,
                                 data=json.dumps(body).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode('utf-8', 'replace')[:120]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')[:120]
    except Exception as e:                                        # noqa: BLE001
        return -1, repr(e)


def delta():
    try:
        with urllib.request.urlopen(BASE + '/api/ps', timeout=15) as r:
            ms = json.loads(r.read().decode('utf-8', 'replace')).get('models') or []
    except Exception:                                             # noqa: BLE001
        return None, None
    if not ms:
        return None, None
    exp = ms[0].get('expires_at') or ''
    now = datetime.now(timezone.utc)
    try:
        s = re.sub(r'\.\d+', '', exp.replace('Z', '+00:00').strip())
        return (datetime.fromisoformat(s) - now).total_seconds(), exp
    except Exception:                                             # noqa: BLE001
        return None, exp


def native_30m():
    return post('/api/chat', {'model': MODEL, 'stream': False,
                              'messages': [{'role': 'user', 'content': '好'}],
                              'keep_alive': '30m',
                              'options': {'num_predict': 1}})


def compat_no_ka():
    return post('/v1/chat/completions', {'model': MODEL, 'stream': False,
                                         'messages': [{'role': 'user', 'content': '好'}],
                                         'max_tokens': 1})


def compat_30m():
    return post('/v1/chat/completions', {'model': MODEL, 'stream': False,
                                         'messages': [{'role': 'user', 'content': '好'}],
                                         'max_tokens': 1, 'keep_alive': '30m'})


def unload():
    return post('/api/chat', {'model': MODEL, 'stream': False,
                              'messages': [{'role': 'user', 'content': '好'}],
                              'keep_alive': 0, 'options': {'num_predict': 1}})


say('=' * 74)
say('第58轮：保温窗口是否会被后续请求重置   %s' % time.strftime('%Y-%m-%d %H:%M:%S'))
say('=' * 74)

R = {}
seq = [
    ('A 原生 keep_alive=30m（撑到 30 分钟）', native_30m, 1800),
    ('B 兼容端点**不带** keep_alive', compat_no_ka, 300),
    ('C 原生 keep_alive=30m（再撑一次）', native_30m, 1800),
    ('D 兼容端点**带上** keep_alive=30m', compat_30m, 300),
    ('E 原生 keep_alive=30m（收尾恢复）', native_30m, 1800),
]
for name, fn, expect in seq:
    rc, body = fn()
    time.sleep(1.0)
    d, exp = delta()
    R[name] = {'rc': rc, 'delta_s': d, 'expect_s': expect, 'expires_at': exp}
    say('  %-36s rc=%-3s Δ=%7s s  （期望 ≈%ds）  expires=%s'
        % (name, rc, ('%.0f' % d) if d is not None else '?', expect, exp))

say()
say('=' * 74)
say('判定')
say('=' * 74)
dB = R['B 兼容端点**不带** keep_alive']['delta_s']
dC = R['C 原生 keep_alive=30m（再撑一次）']['delta_s']
dD = R['D 兼容端点**带上** keep_alive=30m']['delta_s']
ok = True


def chk(n, c, detail):
    global ok
    ok = ok and bool(c)
    say('  [%s] %-42s %s' % ('PASS' if c else 'FAIL', n, detail))


chk('KR1 原生 30m 档读得到 ≈1800s（正控制）',
    dC is not None and 1700 < dC < 1900, 'C → %s s' % dC)
chk('KR2 兼容端点请求把窗口**打回 5 分钟**',
    dB is not None and dB < 600, 'B → %s s（被打回则 <600）' % dB)
chk('KR3 兼容端点仍丢弃 keep_alive（与默认档同档）',
    dD is not None and dD < 600, 'D → %s s' % dD)
RESULT = {'steps': R, 'needs_heartbeat': bool(dB is not None and dB < 600),
          'all_pass': ok}

say()
if ok and RESULT['needs_heartbeat']:
    say('  ⇒ 结论：**每隔一次正常对话，窗口就被缩回 5 分钟** ⇒')
    say('     应用侧保温心跳是**必需**的，不是锦上添花。')
    say('     ★ 反过来说：心跳本身就能把模型一直摁在内存里，')
    say('       所以**不需要**去改机器级 `OLLAMA_KEEP_ALIVE` 环境变量。')
else:
    say('  ⇒ 结论未确立 ⇒ 不许据此改产品代码（先查判据/环境）')

unload()
time.sleep(2)
d, _ = delta()
say()
say('  收尾：已卸载（Δ=%s，None 表示 ps 为空）' % d)
RESULT['final_delta'] = d

io.open(os.path.join(EVID, 'keepalive_reset.json'), 'w', encoding='utf-8').write(
    json.dumps(RESULT, ensure_ascii=False, indent=2))
io.open(os.path.join(EVID, 'keepalive_reset.log'), 'w',
        encoding='utf-8').write('\n'.join(_LOG) + '\n')
say('[写入] %s' % os.path.join(EVID, 'keepalive_reset.json'))
