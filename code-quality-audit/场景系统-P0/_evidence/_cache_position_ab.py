# -*- coding: utf-8 -*-
"""对照实验：**变化段的位置**如何决定 KV 缓存能复用多长。

机制假设：Ollama（llama.cpp）只复用「从 prompt 开头起、逐字相同」的最长前缀。
  ⇒ 若「每轮都变」的段落在 system **靠前**，缓存从那一点起全部失效，后面所有
     token 都要重算（prefill 爆炸）；
  ⇒ 若把变化段挪到 system **最末尾**，缓存能盖住前面整段（persona 等固定内容）。

本实验固定 prompt 总长度与变化内容，**只改变化段的位置**，看首字延迟差多少。
这是纯 A/B 对照，唯一变量 = 位置。
"""
import io
import json
import os
import time
import urllib.request

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
PET = os.path.join(REPO, 'ralsei_pet')
OUT = os.path.join(REPO, 'code-quality-audit', '场景系统-P0', '_evidence',
                   'cache_position_ab.txt')
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

# 一个足够长的"固定中段"（用来证明缓存能盖过它）
FIXED_MID = worldview[:3000]
# 每轮都变的小段（模拟【此刻】）
CHANGING_A = '【此刻】现在是傍晚，窗外下着小雨。'
CHANGING_B = '【此刻】现在是夜里，窗外雨已经停了。'
USER = '事情一桩接一桩的，感觉喘不过气。'


def call(messages, num_predict=24):
    body = json.dumps({'model': MODEL, 'messages': messages, 'stream': False,
                       'options': {'num_predict': num_predict, 'temperature': 0.85}}).encode()
    req = urllib.request.Request(HOST + '/api/chat', data=body,
                                 headers={'Content-Type': 'application/json'})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.loads(r.read().decode())
    return {
        'prompt_tokens': d.get('prompt_eval_count'),
        'ttf_s': round((d.get('prompt_eval_duration') or 0) / 1e9, 3),
        'wall_s': round(time.time() - t0, 2),
    }


def build(order, changing):
    """order: 'changing-first' | 'changing-last'"""
    if order == 'changing-first':
        return persona + '\n\n' + changing + '\n\n' + FIXED_MID
    return persona + '\n\n' + FIXED_MID + '\n\n' + changing


w('模型 = %s' % MODEL)
w('persona=%d chars  fixed_mid=%d chars  changing段=%d chars'
  % (len(persona), len(FIXED_MID), len(CHANGING_A)))
w()
w('★ 机制假设：缓存只复用「从头逐字相同」的最长前缀')
w('  变化段靠前 → 它之后全部重算；变化段在末尾 → 前面整段可复用')
w()

stage = {}

# —— 阶段 1：变化段【靠前】——
w('--- 阶段 1：变化段在 system 中部/靠前 ---')
for tag_ch, ch in (('A', CHANGING_A), ('B', CHANGING_B)):
    msgs = [{'role': 'system', 'content': build('changing-first', ch)},
            {'role': 'user', 'content': USER}]
    r = call(msgs)
    stage[('first', tag_ch)] = r
    w('  变化=%s  prompt=%5s  首字=%8.3fs  wall=%.2fs'
      % (tag_ch, r['prompt_tokens'], r['ttf_s'], r['wall_s']))
w()

# —— 阶段 2：变化段【挪到末尾】——
w('--- 阶段 2：变化段挪到 system 最末尾 ---')
for tag_ch, ch in (('A', CHANGING_A), ('B', CHANGING_B)):
    msgs = [{'role': 'system', 'content': build('changing-last', ch)},
            {'role': 'user', 'content': USER}]
    r = call(msgs)
    stage[('last', tag_ch)] = r
    w('  变化=%s  prompt=%5s  首字=%8.3fs  wall=%.2fs'
      % (tag_ch, r['prompt_tokens'], r['ttf_s'], r['wall_s']))
w()

w('=' * 70)
w('=== 对照结论 ===')
w()
fa, fb = stage[('first', 'A')], stage[('first', 'B')]
la, lb = stage[('last', 'A')], stage[('last', 'B')]
w('变化段靠前：A→B 变化一次，首字 %.3fs → %.3fs（差 %.3fs）'
  % (fa['ttf_s'], fb['ttf_s'], abs(fb['ttf_s'] - fa['ttf_s'])))
w('变化段末尾：A→B 变化一次，首字 %.3fs → %.3fs（差 %.3fs）'
  % (la['ttf_s'], lb['ttf_s'], abs(lb['ttf_s'] - la['ttf_s'])))
w()
w('⇒ 相同的变化量、相同的 prompt 长度，仅位置不同：')
w('   靠前首字 %.3fs  vs  末尾 %.3fs' % (fb['ttf_s'], lb['ttf_s']))
if fb['ttf_s'] > 0 and lb['ttf_s'] > 0:
    w('   倍数 = %.1f×' % (fb['ttf_s'] / lb['ttf_s']))

with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(lines) + '\n')
w()
w('WROTE ' + OUT)
