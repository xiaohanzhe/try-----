# -*- coding: utf-8 -*-
"""用产品真实函数验证「prompt 缓存命中」这条路是否成立。

不重写逻辑 —— 直接 import 产品的 HTTPLocalAI._chat_messages，
看它组装出来的 messages 是否满足 Ollama 前缀缓存的条件：
  ① system 永远是第一条（前缀从 system 开头）
  ② system 内容逐字稳定（模型/persona 不变时）
然后走真实 HTTP 打两枪，看第二枪的 prompt_eval_duration 是否塌下来。
"""
import io
import json
import os
import sys
import time
import urllib.request

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
PET = os.path.join(REPO, 'ralsei_pet')
sys.path.insert(0, os.path.join(PET, 'modules'))

OUT = os.path.join(REPO, 'code-quality-audit', '场景系统-P0', '_evidence',
                   'cache_hit_verify.txt')
HOST = 'http://127.0.0.1:11434'
MODEL = 'qwen2.5:7b-instruct-q4_K_M'

lines = []


def w(s=''):
    lines.append(s)
    print(s)


def read(p):
    if not os.path.exists(p):
        return ''
    with io.open(p, 'r', encoding='utf-8', errors='replace') as f:
        return f.read().strip()


persona = read(os.path.join(PET, 'assets', 'ralsei_persona.md'))
worldview = read(os.path.join(PET, 'assets', 'ralsei_worldview.md'))
system = persona + '\n\n' + worldview

w('=== 1. 用产品真实函数组装 messages ===')
try:
    import api_client
    w('import api_client: OK   (%s)' % api_client.__file__)

    class _Probe(api_client.HTTPLocalAI):
        def __init__(self, cfg):
            api_client.LocalAIBase.__init__(self, cfg)

    cfg = {'base_url': HOST, 'model': MODEL, 'api_key': '', 'timeout': 300,
           'api_version': 'v1', 'enabled': True}
    p = _Probe(cfg)
    msgs, temp, mt = p._chat_messages('今天有点累。', system,
                                      {'history': [('user', '你在做什么呢？'),
                                                   ('assistant', '我在整理旧东西。')]})
    w('messages 组装结果（角色序列）：%s' % [m['role'] for m in msgs])
    w('第 1 条是 system 且内容 == 传入的完整 system：%s'
      % (msgs[0]['role'] == 'system' and msgs[0]['content'] == system))
    w('messages[0].content 长度 = %d' % len(msgs[0]['content']))
    w('temperature=%s max_tokens=%s' % (temp, mt))
    u1 = msgs[0]['content']
except Exception as e:
    w('import api_client FAILED: %s: %s' % (type(e).__name__, e))
    u1 = system

w()
w('=== 2. 两次真实请求，看第二次的 prompt_eval 是否塌落 ===')


def call(messages):
    body = json.dumps({'model': MODEL, 'messages': messages, 'stream': False,
                       'options': {'num_predict': 30, 'temperature': 0.85}}).encode()
    req = urllib.request.Request(HOST + '/api/chat', data=body,
                                 headers={'Content-Type': 'application/json'})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.loads(r.read().decode())
    return {
        'prompt_tokens': d.get('prompt_eval_count'),
        'prompt_eval_s': round((d.get('prompt_eval_duration') or 0) / 1e9, 3),
        'out_tokens': d.get('eval_count'),
        'eval_s': round((d.get('eval_duration') or 0) / 1e9, 3),
        'wall_s': round(time.time() - t0, 2),
    }


# 第 1 枪：冷（换一个与之前不同的小尾巴，强制真算一次；前缀仍是 system）
a_msgs = [{'role': 'system', 'content': system},
          {'role': 'user', 'content': 'cache-probe-A'}]
# 第 2 枪：与第 1 枪共享 system 前缀，只在尾部不同
b_msgs = [{'role': 'system', 'content': system},
          {'role': 'user', 'content': 'cache-probe-B'}]
# 第 3 枪：完全复刻上一条 cache-probe-B（真·重复请求）
c_msgs = list(b_msgs)

for tag, m in (('冷启动 A（前缀 = system）', a_msgs),
               ('同前缀 B（只尾巴不同）', b_msgs),
               ('同前缀 B 重复', c_msgs)):
    try:
        r = call(m)
        w('%-24s prompt=%5s  首字=%7.3fs  wall=%.2fs' % (
            tag, r['prompt_tokens'], r['prompt_eval_s'], r['wall_s']))
    except Exception as e:
        w('%-24s ERR %s: %s' % (tag, type(e).__name__, e))

with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(lines) + '\n')
w()
w('WROTE ' + OUT)
