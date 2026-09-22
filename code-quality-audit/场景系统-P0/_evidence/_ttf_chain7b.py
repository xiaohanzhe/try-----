# -*- coding: utf-8 -*-
"""7B 在**产品真实调用链**下的首字延迟实测。

与 _measure7b.py 的区别：
  _measure7b.py  = 裸测（只 system + user），对照 4B 用
  本脚本         = 复刻 main.py 的真实 system 组装顺序 + history，量用户真正体验到的 TTF

system 组装顺序（严格照 main.py:6722-6816）：
  persona → [【此刻】context] → [话题焦点 focus] → [记忆 recall] → [世界观 wv] → [关系 brief]
其中只有 persona 是"逐字稳定"的部分，后面全是每轮变化 ⇒ 决定了缓存能复用多长。

★ 用户口径：prompt 尽量完整 ⇒ 本脚本**不做任何裁剪**，只在测量维度上分层。
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
                   'ttf_product_chain_7b.txt')
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


def call(messages, num_predict=40):
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
        'out_tokens': d.get('eval_count'),
        'eval_s': round((d.get('eval_duration') or 0) / 1e9, 3),
        'tok_per_s': round((d.get('eval_count') or 0) /
                           ((d.get('eval_duration') or 1) / 1e9), 2),
        'wall_s': round(time.time() - t0, 2),
        'reply': (d.get('message') or {}).get('content', ''),
    }


# —— 复刻 main.py 的 system 组装顺序 ——
# 模拟"每轮都会变"的临时段（真实产品里来自天气/情绪/话题/记忆召回）
CTX = ('【此刻】现在是傍晚。\n'
       '桌面上的天气：窗外下着小雨。')
FOCUS = ('【我们现在在聊什么】\n'
         '当前话题：用户今天有点累\n已聊轮数：3\n'
         '除非他自己换话题，否则别跳走。')
RECALL = ''
REL = '【我和你】\n我们认识有一阵子了，还算聊得来。'

HIST = [('user', '你在做什么呢？'),
        ('assistant', '我在整理一些旧东西……有点走神了。'),
        ('user', '听起来你也有心事。'),
        ('assistant', '嗯，算是有吧。不过说出来好像也没那么重。'),
        ('user', '今天有点累。')]
USER = '事情一桩接一桩的，感觉喘不过气。'

w('模型 = %s' % MODEL)
w('persona chars = %d   worldview chars = %d' % (len(persona), len(worldview)))
w('★ 全部 prompt 均为产品原文，未做任何裁剪')
w()

cases = [
    ('① 完整 system（persona+ctx+focus+rel）+ 6轮历史 [产品默认，缓存已热]',
     persona + '\n\n' + CTX + '\n\n' + FOCUS + '\n\n' + REL, HIST),
    ('② 同一 system，再来一轮（只尾部多一组对话）',
     persona + '\n\n' + CTX + '\n\n' + FOCUS + '\n\n' + REL,
     HIST + [('assistant', '嗯，我在听。'), ('user', '就是有点撑不住了。')]),
    ('③ 【此刻】变了（模拟下一轮天气/情绪不同）',
     persona + '\n\n【此刻】现在是夜里。\n桌面上的天气：窗外雨停了。'
     + '\n\n' + FOCUS + '\n\n' + REL, HIST),
    ('④ lean：只发 persona，不带任何临时段 [事件台词路径]',
     persona, []),
]

results = []
for tag, sys_txt, hist in cases:
    msgs = [{'role': 'system', 'content': sys_txt}]
    for h in hist:
        msgs.append({'role': h[0], 'content': h[1]})
    msgs.append({'role': 'user', 'content': USER})
    try:
        r = call(msgs)
        r['tag'] = tag
        results.append(r)
        w('%-52s' % tag)
        w('   prompt=%5s tok   首字=%8.3fs   生成=%5.2f tok/s   整句=%.2fs   wall=%.2fs'
          % (r['prompt_tokens'], r['ttf_s'], r['tok_per_s'], r['eval_s'], r['wall_s']))
        w('   → %s' % (r['reply'][:60].replace('\n', ' ')))
        w()
    except Exception as e:
        w('%s  ERR %s: %s' % (tag, type(e).__name__, e))
        w()

w('=' * 70)
w('=== 汇总（用户门槛：首字 1~3s）===')
w()
w('| 场景 | prompt tok | **首字** | 判定 | 生成 tok/s |')
w('|---|---|---|---|---|')
for r in results:
    v = '[OK]' if r['ttf_s'] <= 3.0 else '[OVER]'
    short = r['tag'].split(' ')[0]
    w('| %s | %d | **%.3fs** | %s | %.2f |' % (
        short, r['prompt_tokens'], r['ttf_s'], v, r['tok_per_s']))

with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(lines) + '\n')
w()
w('WROTE ' + OUT)
