# -*- coding: utf-8 -*-
"""定位 7B 首字 8.3s 的构成 —— 逐段剥离，量每一段的 prefill 代价。

用户目标：压进 5s，且「不影响人物真实性」。
=> 所以优先级是：先砍「每轮都变、但与人设无关」的部分，不碰 persona 本身。

分层（从最稳到最变）：
  A  persona 全文               ← 逐字稳定（缓存之友），**不动**
  B  + 关系 brief               ← 变化极慢
  C  + 【此刻】context          ← 每轮都变
  D  + 话题焦点 focus           ← 每轮都变
  E  + 记忆 recall              ← 命中才拼
  F  + 6 轮历史                 ← 每轮都变（产品默认）
"""
import io
import json
import os
import time
import urllib.request

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
PET = os.path.join(REPO, 'ralsei_pet')
OUT = os.path.join(REPO, 'code-quality-audit', '场景系统-P0', '_evidence',
                   'ttf_layers_7b.txt')
HOST = 'http://127.0.0.1:11434'
MODEL = 'ralsei:v4'

lines = []


def w(s=''):
    lines.append(str(s))
    print(s, flush=True)


def read(p):
    if not os.path.exists(p):
        return ''
    with io.open(p, 'r', encoding='utf-8', errors='replace') as f:
        return f.read().strip()


persona = read(os.path.join(PET, 'assets', 'ralsei_persona.md'))

CTX = ('【此刻】现在是深夜十点，窗外下着小雨。\n'
       '你的精力：有点困了。\n'
       '主人已经有一阵子没跟你说话了。')
FOCUS = ('【我们现在在聊什么】\n'
         '当前话题：用户今天工作很累\n已聊轮数：4\n'
         '除非他自己换话题，否则别跳走。')
RECALL = ('【想起的事】\n'
          '他说过自己最近换了新工作，压力有点大。')
REL = '【我和你】\n我们认识有一阵子了，还算聊得来。'
HIST = [('user', '你在做什么呢？'),
        ('assistant', '我在整理一些旧东西……有点走神了。'),
        ('user', '听起来你也有心事。'),
        ('assistant', '嗯，算是有吧。不过说出来好像也没那么重。'),
        ('user', '最近工作特别累。'),
        ('assistant', '这样啊……那你有好好休息吗？')]
USER = '事情一桩接一桩的，感觉喘不过气。'


def call(sys_txt, hist, num_predict=24):
    msgs = [{'role': 'system', 'content': sys_txt}]
    for h in (hist or []):
        msgs.append({'role': h[0], 'content': h[1]})
    msgs.append({'role': 'user', 'content': USER})
    body = json.dumps({'model': MODEL, 'messages': msgs, 'stream': False,
                       'options': {'num_predict': num_predict}}).encode()
    req = urllib.request.Request(HOST + '/api/chat', data=body,
                                 headers={'Content-Type': 'application/json'})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=1200) as r:
        d = json.loads(r.read().decode())
    return {
        'prompt_tokens': d.get('prompt_eval_count'),
        'ttf_s': round((d.get('prompt_eval_duration') or 0) / 1e9, 3),
        'wall_s': round(time.time() - t0, 2),
        'reply': (d.get('message') or {}).get('content', '')[:70],
    }


w('模型 = %s' % MODEL)
w('persona = %d chars' % len(persona))
w()
w('★ 分层策略：先喂热 A（persona）让缓存建立，再逐层加，看每一层"新加的东西"值多少')
w()

# —— 第 1 步：单独喂热 persona，拿到"稳定基座"的首字 ——
w('--- 层 A：只 persona（稳定基座）---')
for i in range(1, 3):
    r = call(persona, [])
    w('  第%d次：prompt=%5s  首字=%8.3fs' % (i, r['prompt_tokens'], r['ttf_s']))
base_persona = r
w()

# —— 第 2 步：逐层叠加（每次都从"已热的 persona 前缀"出发）——
layers = [
    ('B persona + 关系', persona + '\n\n' + REL, []),
    ('C + 【此刻】', persona + '\n\n' + REL + '\n\n' + CTX, []),
    ('D + 话题焦点', persona + '\n\n' + REL + '\n\n' + CTX + '\n\n' + FOCUS, []),
    ('E + 记忆召回', persona + '\n\n' + REL + '\n\n' + CTX + '\n\n' + FOCUS + '\n\n' + RECALL, []),
    ('F + 6轮历史（产品默认全量）',
     persona + '\n\n' + REL + '\n\n' + CTX + '\n\n' + FOCUS + '\n\n' + RECALL, HIST),
]

w('--- 逐层叠加：每层跑 2 次（第 1 次含"新增段的 prefill"，第 2 次即该层的稳态）---')
w()
w('| 层 | prompt tok | 第1次首字 | 第2次首字(稳态) | 新增代价 |')
w('|---|---|---|---|---|')
prev = base_persona
rows = [('A persona', base_persona)]
for tag, sys_txt, hist in layers:
    r1 = call(sys_txt, hist)
    r2 = call(sys_txt, hist)
    delta = r1['ttf_s'] - prev['ttf_s']
    w('| %s | %d | %.3fs | **%.3fs** | %+.3fs |'
      % (tag, r1['prompt_tokens'], r1['ttf_s'], r2['ttf_s'], delta))
    rows.append((tag, r2))
    prev = r2

w()
w('=' * 72)
w('=== 结论 ===')
w()
full = rows[-1][1]
w('产品默认全量（层 F）稳态首字 = %.3fs' % full['ttf_s'])
w('只 persona（层 A）稳态首字     = %.3fs' % base_persona['ttf_s'])
w()
w('⇒ 每轮必变的部分贡献了 %.3fs 的增量'
  % (full['ttf_s'] - base_persona['ttf_s']))
w()
w('★ 关键判断：若把"每轮都变的三段"（【此刻】/焦点/记忆）从 system 里')
w('  移到 **user 消息里或干脆不发**，缓存能盖住 persona+关系，')
w('  首字就该贴近层 A~B 的稳态 —— 而**人设（persona）一个字都不用改**。')

with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(lines) + '\n')
w()
w('WROTE ' + OUT)
