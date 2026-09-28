# -*- coding: utf-8 -*-
"""第58轮：`keep_alive` 的**真实语义** —— 黏住？每次重置？普通请求会不会续期？

这条决定整个方案（要不要做心跳线程），必须钉死，不能靠推断。

从 probe_keepalive / probe_keepalive_reset 已看到的两个事实：
  · 兼容端点**不能改** keep_alive（设 30m 无效，窗口仍是 300s）；
  · 但设过 30m 之后，后续兼容端点请求**也没有**把它打回 300s。

⇒ 假说 H：**keep_alive 是"按模型载入实例"黏住的设置量；每个请求都用这个量刷新截止时刻。**
   H 若成立 ⇒ 只需在"模型新载入"时设一次，**不需要心跳**。
   H 若不成立（例如普通请求根本不给续期）⇒ 必须定期发心跳。

四问，逐条用 `ollama ps` 的 expires_at 增量判定（全程不看 HTTP 码）：

  Q1  冷载（不带 keep_alive）⇒ 窗口 = 服务器默认 300s？        【基准】
  Q2  原生设 10m 后 ⇒ 600s？                                   【正控制：证明能改】
  Q3  随后一个**兼容端点**请求 ⇒ 是 600s（沿用黏住值）还是 300s？  【关键①】
  Q4  **不发任何请求**静置 70s ⇒ 窗口是否随时间递减（≈530s）？     【关键②：证明确实是"刷新"而非我读错】
  Q5  再一个兼容端点请求 ⇒ 是否**跳回 ≈600s**（被续期）？          【关键③：决定心跳是否必需】
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
    print(s, flush=True)
    _LOG.append(s)


def post(path, body, timeout=420):
    req = urllib.request.Request(BASE + path,
                                 data=json.dumps(body).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception as e:                                        # noqa: BLE001
        return repr(e)


def compat():
    return post('/v1/chat/completions', {
        'model': MODEL, 'stream': False,
        'messages': [{'role': 'user', 'content': '好'}], 'max_tokens': 1})


def native(ka):
    return post('/api/chat', {
        'model': MODEL, 'stream': False,
        'messages': [{'role': 'user', 'content': '好'}],
        'keep_alive': ka, 'options': {'num_predict': 1}})


def ps_delta():
    """★ 注意：`/api/ps` **不是推理请求**，它不该刷新窗口 —— 这正是 Q4 的鉴别力来源。"""
    try:
        with urllib.request.urlopen(BASE + '/api/ps', timeout=15) as r:
            ms = json.loads(r.read().decode('utf-8', 'replace')).get('models') or []
    except Exception:                                             # noqa: BLE001
        return None
    if not ms:
        return None
    try:
        s = re.sub(r'\.\d+', '', (ms[0].get('expires_at') or '')
                   .replace('Z', '+00:00').strip())
        return (datetime.fromisoformat(s) - datetime.now(timezone.utc)).total_seconds()
    except Exception:                                             # noqa: BLE001
        return None


def mark(tag, expect, note=''):
    d = ps_delta()
    say('  %-42s Δ = %7s s   期望 %-10s %s'
        % (tag, ('%.0f' % d) if d is not None else '?', expect, note))
    return d


say('=' * 78)
say('第58轮：keep_alive 真实语义   %s' % time.strftime('%Y-%m-%d %H:%M:%S'))
say('=' * 78)

R = {}
native(0)                      # 先卸干净
time.sleep(2)
say('  （已卸载，ps 应为空）Δ=%s' % ps_delta())
say()

say('Q1  冷载：兼容端点，**不带** keep_alive')
compat()
R['Q1_default'] = mark('冷载后', '≈300（服务器默认）')
say()
say('Q2  原生端点设 keep_alive="10m"')
native('10m')
R['Q2_set_10m'] = mark('原生 10m 之后', '≈600')
say()
say('Q3  ★ 再来一个**兼容端点**请求（不带 keep_alive）')
compat()
R['Q3_compat_after'] = mark('兼容请求之后', '600=黏住 / 300=被打回')
say()
say('Q4  ★ **不发任何请求**静置 70s（只读 /api/ps）')
say('    （/api/ps 不是推理请求 ⇒ 若窗口真在倒计时，它应当减少而不是被顶住）')
time.sleep(70)
R['Q4_after_idle70'] = mark('静置 70s 后', '≈530（倒计时）')
say()
say('Q5  ★ 再发一个兼容端点请求')
compat()
R['Q5_compat_refresh'] = mark('兼容请求之后', '≈600=被续期 / ≈530=不续期')
say()

d1, d2, d3, d4, d5 = (R['Q1_default'], R['Q2_set_10m'], R['Q3_compat_after'],
                      R['Q4_after_idle70'], R['Q5_compat_refresh'])
ok = True


def chk(n, c, detail):
    global ok
    ok = ok and bool(c)
    say('  [%s] %-44s %s' % ('PASS' if c else 'FAIL', n, detail))


chk('KS1 冷载默认窗口 ≈300s', d1 is not None and 250 < d1 < 360, 'Δ=%s' % d1)
chk('KS2 原生可改窗口 10m ⇒ ≈600s（正控制）',
    d2 is not None and 540 < d2 < 660, 'Δ=%s' % d2)
chk('KS3 兼容请求**沿用**黏住值（不被改也不被打回）',
    d3 is not None and 540 < d3 < 660, 'Δ=%s（若 ≈300 则被打回）' % d3)
chk('KS4 静置时窗口**真的在倒计时**（鉴别力：排除"读数恒 600"）',
    d4 is not None and d4 < d3 - 30, 'Δ=%s → %s' % (d3, d4))
chk('KS5 ★ 普通请求**会给续期**（一跳回 ≈600s）',
    d5 is not None and d5 > d4 + 30, 'Δ=%s → %s' % (d4, d5))

RESULT = {'steps': R, 'all_pass': ok,
          'sticky_true': bool(d3 is not None and 540 < d3 < 660),
          'refresh_by_normal_request': bool(d4 is not None and d5 is not None
                                            and d5 > d4 + 30)}
say()
say('=' * 78)
say('结论')
say('=' * 78)
if RESULT['sticky_true'] and RESULT['refresh_by_normal_request']:
    say('  ⇒ **keep_alive 黏在模型载入实例上；每个请求（普通请求也算）都用它续期。**')
    say('     ⇒ 只需在"模型新载入"时设一次 ⇒ **不需要周期性心跳**；')
    say('       只需要一个**廉价的看门狗**（轮询 /api/ps，发现新载入就补设一次）。')
    say('     ⇒ 用户走开后不再有请求 ⇒ 窗口自然过期 ⇒ 内存自动归还（无需额外策略）。')
elif RESULT['sticky_true']:
    say('  ⇒ 黏住成立，但普通请求**不给续期** ⇒ 必须自己发心跳续期。')
else:
    say('  ⇒ 结论未确立 ⇒ 不许据此改产品代码。')

native(0)
time.sleep(2)
say()
say('  收尾：已卸载（Δ=%s）' % ps_delta())

io.open(os.path.join(EVID, 'keepalive_semantics.json'), 'w', encoding='utf-8').write(
    json.dumps(RESULT, ensure_ascii=False, indent=2))
io.open(os.path.join(EVID, 'keepalive_semantics.log'), 'w',
        encoding='utf-8').write('\n'.join(_LOG) + '\n')
say('[写入] %s' % os.path.join(EVID, 'keepalive_semantics.json'))
