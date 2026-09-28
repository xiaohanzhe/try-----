# -*- coding: utf-8 -*-
"""第58轮（旁证）：`/v1/chat/completions` 是否**截断**长提示词 —— 直接读 usage 里的 token 数。

来源：`main.py:_ai_chat_options` 的注释声称
  "长提示词都恒定截断在 ~2050 tokens（对照组：/api/chat 的 options.num_ctx 才生效，5032 tokens）"。
若为真，则 `assets/ralsei_persona.md`（实测 2372 token）**经产品通路送进去是被砍过的** ——
那"冷 prefll 56s"这个数、以及"缓存里到底缓存了多长的前缀"，都要按真实长度重算。

判据（**同一段文本、两条通路对比**，不看 HTTP 码）：
  · 兼容端点：读 OpenAI 响应里的 `usage.prompt_tokens`
  · 原生端点：读 `prompt_eval_count`
  两者若差出上千 token ⇒ 截断成立；若相等 ⇒ 该注释是**过时/错误**的，须一并更正。
"""

import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = 'http://127.0.0.1:11434'
MODEL = 'ralsei:v4'
RT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
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
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8', 'replace')), time.time() - t0
    except urllib.error.HTTPError as e:
        return {'_err': 'HTTP %s %s' % (e.code, e.read()[:300])}, 0.0
    except Exception as e:                                        # noqa: BLE001
        return {'_err': repr(e)}, 0.0


persona = io.open(os.path.join(RT, 'ralsei_pet', 'assets', 'ralsei_persona.md'),
                  encoding='utf-8').read()
say('=' * 76)
say('第58轮旁证：兼容端点是否截断长提示词   %s' % time.strftime('%Y-%m-%d %H:%M:%S'))
say('=' * 76)
say('人设文件 %d 字符 / %d 字节' % (len(persona), len(persona.encode('utf-8'))))

# 原生端点先卸掉，保证两条通路都是"从零开始算"
post('/api/chat', {'model': MODEL, 'stream': False,
                   'messages': [{'role': 'user', 'content': 'x'}],
                   'keep_alive': 0, 'options': {'num_predict': 1}})
time.sleep(2)

R = {}
say()
say('A) 兼容端点 `/v1/chat/completions`（产品走的就是这条）')
j, el = post('/v1/chat/completions', {
    'model': MODEL, 'stream': False, 'max_tokens': 1,
    'messages': [{'role': 'system', 'content': persona},
                 {'role': 'user', 'content': '好'}]})
u = (j or {}).get('usage') or {}
say('   usage = %s   用时 %.1fs' % (json.dumps(u, ensure_ascii=False), el))
R['compat_usage'] = u
R['compat_wall_s'] = round(el, 1)

say()
say('B) 原生端点 `/api/chat`（正控制：它能读 prompt_eval_count）')
j, el = post('/api/chat', {
    'model': MODEL, 'stream': False, 'keep_alive': '10m',
    'messages': [{'role': 'system', 'content': persona},
                 {'role': 'user', 'content': '好'}],
    'options': {'num_predict': 1}})
say('   prompt_eval_count = %s   prompt_eval = %.2fs   %s tok/s 错？'
    % (j.get('prompt_eval_count'),
       (j.get('prompt_eval_duration') or 0) / 1e9,
       ('%.2f ms/tok' % ((j.get('prompt_eval_duration') or 0) / 1e6
                         / max(1, j.get('prompt_eval_count') or 1)))))
R['native_prompt_eval_count'] = j.get('prompt_eval_count')
R['native_prompt_eval_s'] = round((j.get('prompt_eval_duration') or 0) / 1e9, 2)
R['native_context_length'] = None

say()
say('C) 看模型自身声明的 num_ctx（来自 /api/show）')
try:
    req = urllib.request.Request(BASE + '/api/show',
                                 data=json.dumps({'model': MODEL}).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        sh = json.loads(r.read().decode('utf-8', 'replace'))
    info = sh.get('model_info') or {}
    R['model_info_ctx'] = {k: v for k, v in info.items() if 'context' in k.lower()}
    say('   context 相关: %s' % json.dumps(R['model_info_ctx'], ensure_ascii=False))
    R['parameters'] = sh.get('parameters')
    say('   parameters  : %s' % (sh.get('parameters') or '').strip().replace('\n', ' | '))
except Exception as e:                                            # noqa: BLE001
    say('   /api/show 失败 %r' % (e,))

say()
say('D) 再试一次：兼容端点 + 显式 num_ctx（顶层与 options 两种放法）')
say('   ★ 同时采集**热**调用的 usage —— 冷/热两次的 cached_tokens 成对才有意义：')
say('     A 步是卸载后的**冷**调用，这里已经是热的，两者一对比就知道该字段')
say('     是"真的反映缓存状态"还是"恒 0 / 恒满"（判据的鉴别力全靠这一对）。')
R['compat_usage_warm'] = []
for tag, extra in (('顶层 num_ctx=8192', {'num_ctx': 8192}),
                   ('options.num_ctx=8192', {'options': {'num_ctx': 8192}})):
    body = {'model': MODEL, 'stream': False, 'max_tokens': 1,
            'messages': [{'role': 'system', 'content': persona},
                         {'role': 'user', 'content': '好'}]}
    body.update(extra)
    j, el = post('/v1/chat/completions', body)
    _u = (j or {}).get('usage') or {}
    R['compat_usage_warm'].append(_u)
    say('   %-24s usage=%s' % (tag, json.dumps(_u, ensure_ascii=False)))

say()
say('=' * 76)
say('判定')
say('=' * 76)
cu = (R['compat_usage'] or {}).get('prompt_tokens')
nu = R['native_prompt_eval_count']
say('  兼容端点报的 prompt_tokens = %s' % cu)
say('  原生端点报的 prompt_eval_count = %s' % nu)
if cu and nu:
    if abs(cu - nu) > 200:
        say('  ⇒ **截断成立**：产品通路下模型只看到 %d 个 token（原生能看到 %d 个）。'
            % (cu, nu))
        R['truncated'] = True
    else:
        say('  ⇒ 两条通路看到的一样多 ⇒ **不截断**；`_ai_chat_options` 里那段注释'
            '（"恒定截断在 ~2050"）与当前 Ollama 0.34.4 的实测**不符**，须更正。')
        R['truncated'] = False
else:
    say('  ⇒ 读数不全（兼容端点没回 usage）⇒ 结论未确立，不许据此改任何东西。')
    R['truncated'] = None

post('/api/chat', {'model': MODEL, 'stream': False,
                   'messages': [{'role': 'user', 'content': 'x'}],
                   'keep_alive': 0, 'options': {'num_predict': 1}})

io.open(os.path.join(EVID, 'compat_truncation.json'), 'w', encoding='utf-8').write(
    json.dumps(R, ensure_ascii=False, indent=2))
io.open(os.path.join(EVID, 'compat_truncation.log'), 'w',
        encoding='utf-8').write('\n'.join(_LOG) + '\n')
say('[写入] %s' % os.path.join(EVID, 'compat_truncation.json'))
