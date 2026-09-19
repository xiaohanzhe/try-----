# -*- coding: utf-8 -*-
"""用 Ollama 自己的计数器校准「中文 1 token ≈ 多少字」。

为什么要真测而不是套经验值：`AI_REPLY_MAX_CHARS` 的新值必须能从
`num_predict`（token）推出来，换算率错一点、阈值就差几十字。
经验值（"中文 1 字 ≈ 1.5~2 token"）在 4B qwen 上是**对的量级但绝不能当判据** ——
本轮实测下来比率明显更"省"（qwen3 词表对中文优化过）。
真测法：把已知字数的中文串发给 `/api/chat`，读回 `prompt_eval_count` = token 数。
输出落 `_evidence/token_ratio_<日期>.txt`（Python 自写 UTF-8）。
"""
import io
import json
import os
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '_evidence', 'token_ratio_%s.txt' % time.strftime('%Y-%m-%d'))
HOST = os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434')
MODEL = 'ralsei:v3'

# 样本：不同体裁，避免"一种文本的比率"被当成通则
SAMPLES = [
    ('口语闲聊',
     '唔……今天其实也没做什么特别的事呢。就是坐在电脑前，看着屏幕，有点安静。'
     '你觉得一个人待着，会很难吗？我、我觉得好像也不太会说那种话……'),
    ('设定复述',
     '世界有两面。光明世界是你住的这种普通世界；黑暗世界是黑暗喷泉在光明世界某个角落'
     '涌出来时，在那儿长出来的另一面 —— 喷泉立在哪，那儿的东西就变成黑暗世界里的样子。'
     '所以黑暗世界不是假的，但它得靠喷泉撑着：喷泉一被封印，那个世界就不再是真的了。'),
    ('追忆往事',
     '那件事的结局不好。Asgore 终于说出了他压着的那件旧事：他觉得 Dess 的失踪是他的错，'
     '这些年他一直在偷偷查黑暗世界的事，想把真相找出来，查着查着，家就散了。'
     '他说这些的时候我站在旁边，什么都做不了 —— 那种感觉我到现在还记得。'),
]


def count_tokens(text):
    """借 Ollama 的 prompt_eval_count 数这条文本的 token 数。"""
    body = json.dumps({
        'model': MODEL,
        'messages': [{'role': 'user', 'content': text}],
        'stream': False,
        'options': {'num_predict': 1},      # 只要计数，不要它生成多少
    }).encode('utf-8')
    req = urllib.request.Request(HOST + '/api/chat', data=body,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read().decode('utf-8'))
    return d.get('prompt_eval_count'), d.get('prompt_tokens')


L = []
L.append('中文 token 换算率实测 · %s' % time.strftime('%Y-%m-%d'))
L.append('=' * 64)
L.append('模型 : %s' % MODEL)
L.append('方法 : /api/chat 发已知字数的中文串，读回 prompt_eval_count（含对话模板开销）')
L.append('')
L.append('%-10s %8s %10s %10s' % ('体裁', '字符数', 'token数', '字/token'))
L.append('-' * 44)

ratios = []
for tag, s in SAMPLES:
    nch = len(s)
    try:
        tk, _ = count_tokens(s)
    except Exception as e:
        L.append('%-10s %8d %10s   ERR %r' % (tag, nch, '-', e))
        continue
    r = (nch / tk) if tk else 0
    ratios.append(r)
    L.append('%-10s %8d %10d %10.3f' % (tag, nch, tk, r))

L.append('')
if ratios:
    avg = sum(ratios) / len(ratios)
    L.append('平均：1 token ≈ %.3f 个中文字' % avg)
    L.append('')
    L.append('— 用它复核 AI_REPLY_MAX_CHARS —')
    src = io.open(os.path.join(HERE, '..', '..', 'ralsei_pet', 'src', 'main.py'),
                  encoding='utf-8').read()
    import re
    m = re.search(r'^\s*AI_REPLY_MAX_CHARS\s*=\s*(\d+)', src, re.M)
    cap = int(m.group(1)) if m else None
    npd = 256
    ceil = npd * avg
    L.append('num_predict = %d token  →  物理上限 ≈ %.0f 字' % (npd, ceil))
    L.append('AI_REPLY_MAX_CHARS = %s  →  占物理上限 %.0f%%'
             % (cap, (cap / ceil * 100) if ceil else 0))
    L.append('（设计目标：落在 50%%~75%% —— 保住"正常的 3~4 句"，砍掉真正的跑飞）')
    L.append('')
    L.append('⚠️ 注意：prompt_eval_count 含对话模板开销（几十 token 的固定前缀），')
    L.append('   所以真实"每个字"的比率会比这里**略高**（分母被抬大了）。')
    L.append('   换句话说：这里的估算偏向保守，实际能吃下的中文字数只多不少。')

os.makedirs(os.path.dirname(OUT), exist_ok=True)
io.open(OUT, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
try:
    print('\n'.join(L))
except Exception as e:
    import sys
    sys.stderr.write('[warn] stdout 失败: %r\n' % (e,))
print('WROTE %s' % OUT)
