# -*- coding: utf-8 -*-
"""找「可落地」的方案：在**变化段每轮真的会变**的前提下，怎么把首字压进 5s。

上一轮分层实验（ttf_layers_7b.txt）证明了：只要前缀连续，2509 token 也只要 0.2s。
但那是"人为保持逐字稳定"，现实里【此刻】/焦点/记忆每轮都会变。

本实验模拟**真实轮次**（每轮内容真的变了），对照三种排布：

  方案 1 现状：persona → 关系 → 【此刻】 → 焦点 → 记忆 → 历史
              （变化段在**中部**，一旦变，后面全废）

  方案 2 末尾：persona → 关系 → 历史 → 【此刻】 → 焦点 → 记忆
              （把"每轮必变"的全部压到 system **最末尾**）
              ⚠️ 但历史也在变 → 必须验证历史变时是否也打断

  方案 3 三明治：persona（稳定）作 system，**变化段挪进 user 消息**
              （system 恒为 persona → 缓存永远命中；变化段跟 user 一起送）
              ★ 代价：模型对"贴在 user 消息里的状态"理解可能变差 → 必须真机验人味

每轮都真实改变内容，连跑 4 轮，记录首字。
"""
import io
import json
import os
import time
import urllib.request

REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
PET = os.path.join(REPO, 'ralsei_pet')
OUT = os.path.join(REPO, 'code-quality-audit', '场景系统-P0', '_evidence',
                   'ttf_strategy_7b.txt')
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
REL = '【我和你】\n我们认识有一阵子了，还算聊得来。'

# 4 轮真实对话，每轮状态都不同
ROUNDS = [
    ('你在做什么呢？', '', ''),
    ('听起来你也有心事。', '【此刻】现在是傍晚，窗外下着小雨。', '【话题】他好像察觉到我在走神'),
    ('最近工作特别累。', '【此刻】现在是夜里，雨停了。', '【话题】他今天工作很累'),
    ('事情一桩接一桩的，感觉喘不过气。', '【此刻】现在是深夜十点，有点凉。', '【话题】他快撑不住了'),
]


def call(sys_txt, hist, user_text, num_predict=20):
    msgs = [{'role': 'system', 'content': sys_txt}]
    for h in hist:
        msgs.append({'role': h[0], 'content': h[1]})
    msgs.append({'role': 'user', 'content': user_text})
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
        'reply': (d.get('message') or {}).get('content', '')[:60],
    }


def run_scheme(tag, build):
    """build(round_idx) -> (system, history, user)"""
    w('--- %s ---' % tag)
    hist = []
    res = []
    for i, (user_text, ctx, focus) in enumerate(ROUNDS):
        sys_txt, h, u = build(i, hist, user_text, ctx, focus)
        r = call(sys_txt, h, u)
        res.append(r)
        w('  第%d轮 prompt=%5s 首字=%8.3fs  | %s'
          % (i + 1, r['prompt_tokens'], r['ttf_s'], r['reply'].replace('\n', ' ')))
        # 维护真实历史
        hist.append(('user', user_text))
        hist.append(('assistant', r['reply'] or '（略）'))
    warm = [x['ttf_s'] for x in res[1:]]
    avg = sum(warm) / len(warm) if warm else 0
    w('  ★ 第2轮起平均首字 = %.3fs' % avg)
    w()
    return avg, res


# 方案 1：现状（变化段在中部）
def s1(i, hist, u, ctx, focus):
    sysx = persona + '\n\n' + REL
    if ctx:
        sysx += '\n\n' + ctx
    if focus:
        sysx += '\n\n' + focus
    return sysx, hist[-6:], u


# 方案 2：变化段压到 system 最末尾
def s2(i, hist, u, ctx, focus):
    sysx = persona + '\n\n' + REL
    h = hist[-6:]
    for r_, c_ in h:
        sysx += '\n\n[%s] %s' % (r_, c_)   # 历史塞进 system（尾部）
    if ctx:
        sysx += '\n\n' + ctx
    if focus:
        sysx += '\n\n' + focus
    return sysx, [], u


# 方案 3：system 恒为 persona，变化段跟 user 一起送
def s3(i, hist, u, ctx, focus):
    extra = []
    if ctx:
        extra.append(ctx)
    if focus:
        extra.append(focus)
    user_block = ('\n\n'.join(extra) + '\n\n' + u) if extra else u
    return persona, hist[-6:], user_block


w('模型 = %s   persona = %d chars' % (MODEL, len(persona)))
w('★ 每轮的状态内容都真的变了，模拟真实使用')
w()

a1, r1 = run_scheme('方案 1：现状（变化段在中部）', s1)
a2, r2 = run_scheme('方案 2：变化段压到 system 最末尾（历史也进 system）', s2)
a3, r3 = run_scheme('方案 3：system 恒为 persona，变化段随 user 送', s3)

w('=' * 72)
w('=== 汇总（第 2 轮起平均首字，用户目标 < 5s）===')
w()
w('| 方案 | 平均首字 | 判定 |')
w('|---|---|---|')
for tag, a in (('1 现状（中部）', a1), ('2 变化段挪末尾', a2), ('3 system 恒 persona', a3)):
    w('| %s | **%.3fs** | %s |' % (tag, a, '[OK]' if a <= 5.0 else '[OVER]'))
w()

with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(lines) + '\n')
w('WROTE ' + OUT)
