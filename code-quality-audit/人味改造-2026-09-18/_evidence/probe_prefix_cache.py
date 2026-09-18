# -*- coding: utf-8 -*-
"""钉死"App 链路首字 3s"的机制：是 **前缀缓存失效** 还是 **system 太长**？

背景（`s7_e2e_event.txt`，两次独立复现）
---------------------------------------
  纯链路 P1：system = persona 全文（1591 字），**8 次请求 system 一字不变**
              → 首字 中位 0.88s（0.81~0.91s，极稳）
  App 链路 ：system = persona + 【此刻】 + 话题锚 + 记忆召回（1825 字），
              **每次请求尾部都在变**（时段/精力/话题/回忆都会变）
              → 首字 3.02s / 2.53s（远超 1200ms 兜底时限 → 事件 AI 永远走罐头）

两者只差 230 字，却差 2~3 倍。230 字 ≈ 150 token，按 1000+ tok/s 的 prefill
算只要 0.15s —— 所以"长"解释不了。真正的嫌疑是 **Ollama 的 KV 前缀缓存**：
它只复用"从头开始逐字相同"的那一段。system 尾部一变，那 150 字就得重算，
而本机（无独显、纯 CPU）**未命中缓存的 prefill 实测只有 40~100 tok/s**
（见 _evidence/../模型选型-7B-2026-09-18/probe_7b_vs_3b.txt：冷读 1032 token 要 10.9s / 26.9s）。
150 token ÷ 90 tok/s ≈ 1.7s —— 正好补上差额。

本探针就测这一件事：把"变的量"分别放在 **system 尾部** 与 **history** 里，
看首字各自涨多少。三组各打 4 次（user 消息每次都不一样）：

  A 稳定 system（persona）                  —— 基线，等同纯链路 P1
  B 变化 system（persona + 230 字变化的尾部）—— 等同 App 链路
  C 稳定 system + 2 条变化的 history         —— 变化的量放在 system 之后

判据：
  · B 显著慢于 A   → 机制＝system 尾部变化让前缀缓存失效（唯一解＝让事件请求的
                     system **保持稳定**，即事件别再带【此刻】/话题锚/记忆召回）
  · C 也显著慢     → 机制不成立，得另找（history 变化同样致命，那 App 无解）

用法：& C:\\Python311\\python.exe probe_prefix_cache.py
"""

import io
import json
import os
import statistics
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))   # _evidence → 轮次 → 审计 → 仓库
BASE = 'http://localhost:11434'
MODEL = 'ralsei:v2'
TIMEOUT = 600

PERSONA = io.open(os.path.join(ROOT, 'ralsei_pet', 'assets', 'ralsei_persona.md'),
                  encoding='utf-8').read()

# App 真实请求里的那条"变化的尾巴"（`_build_ai_context` + `brief()` + `recall_text`），
# 长度按线上实测 1825 - 1591 ≈ 234 字复刻。
TAIL_TPL = ('【此刻】现在是凌晨{i}点，天气晴，心情平静，有点疲惫，'
            '肚子有点饿，主人的名字是小豆，记得你最近喜欢聊第{i}个话题\n\n'
            '【我们正在聊】关于"第{i}件事"的讨论；这是第{i}轮；没有悬置的问题。'
            '除非主人自己换话题，否则别跳。\n\n'
            '【零星想起】主人曾经说过第{i}句心事，那天的感觉很疲惫；'
            '他也提过第{i}种喜欢的东西。')

# 事件式提示词：短、口语、每次不同（复刻事件台词的真实形态）
PROMPTS = [
    '（主人用手指戳了戳你的身体。）用一句话很短地回应（最多 24 个字），只输出这一句话本身。',
    '（主人捏着你的耳朵捏了一会儿。）用一句话很短地回应（最多 24 个字），只输出这一句话本身。',
    '（主人轻轻抚摸你的头发。）用一句话很短地回应（最多 24 个字），只输出这一句话本身。',
    '（主人拍了拍你的肚子。）用一句话很短地回应（最多 24 个字），只输出这一句话本身。',
]
OPTS = {'temperature': 0.85, 'max_tokens': 96}


def call(system, prompt, history):
    """走线上真实通路 /v1/chat/completions 流式，返回 (首字ms, 整句ms, 分片数, 文本)。"""
    messages = [{'role': 'system', 'content': system}]
    for r, c in history:
        messages.append({'role': r, 'content': c})
    messages.append({'role': 'user', 'content': prompt})
    payload = {'model': MODEL, 'messages': messages, 'stream': True, **OPTS}
    t0 = time.time()
    first = None
    parts = []
    with requests.post(BASE + '/v1/chat/completions', json=payload,
                       timeout=TIMEOUT, stream=True) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines(chunk_size=1):
            if not line:
                continue
            s = line.decode('utf-8', 'replace')
            if not s.startswith('data:'):
                continue
            body = s[5:].strip()
            if body == '[DONE]':
                break
            try:
                piece = (json.loads(body).get('choices') or [{}])[0].get(
                    'delta', {}).get('content')
            except Exception:
                continue
            if piece:
                if first is None:
                    first = time.time() - t0
                parts.append(piece)
    total = time.time() - t0
    return (None if first is None else first * 1000.0), total * 1000.0, len(parts), ''.join(parts)


def main():
    out = io.open(os.path.join(HERE, 'probe_prefix_cache.txt'), 'w',
                  encoding='utf-8', newline='\n')
    L = []

    def w(s=''):
        L.append(s)
        print(s)

    w('=' * 78)
    w('钉机制：App 链路首字 3s 是"前缀缓存失效"还是"system 太长"？')
    w('model=%s（已预热，全程不 unload，模拟稳态）  端点=/v1/chat/completions' % MODEL)
    w('persona = %d 字   变化尾巴 = %d 字（复刻线上 1825-1591）'
      % (len(PERSONA), len(TAIL_TPL.format(i=1))))
    w('时间：%s' % time.strftime('%Y-%m-%d %H:%M:%S'))
    w('=' * 78)

    # 预热：把 persona 前缀先灌进 KV（事件请求迟早会用到这段）
    w('')
    w('[预热] 先打一次 persona-only 请求，让 persona 前缀进 KV 缓存…')
    f, t, n, _ = call(PERSONA, PROMPTS[0], [])
    w('  预热：首字 %.0fms / 整句 %.0fms（这一次贵是正常的）' % (f, t))

    cases = [
        ('A 稳定 system', lambda i: (PERSONA, PROMPTS[i], [])),
        ('B 变化 system', lambda i: (PERSONA + '\n\n' + TAIL_TPL.format(i=i), PROMPTS[i], [])),
        ('C 稳定system+变history',
         lambda i: (PERSONA, PROMPTS[i],
                    [('user', '在吗？这是第 %d 次' % i),
                     ('assistant', '嗯，我在的呀。第 %d 次也还在。' % i)])),
    ]

    w('')
    w('%-24s %8s %10s %10s %10s %8s' % ('用例', '第几次', '首字ms', '整句ms', '分片', '输出字'))
    results = {}
    for name, build in cases:
        firsts = []
        for i in range(4):
            system, prompt, hist = build(i)
            f, t, n, text = call(system, prompt, hist)
            firsts.append(f)
            w('%-24s %8d %10.0f %10.0f %10d %8d'
              % (name, i + 1, f, t, n, len(text.strip())))
            time.sleep(0.3)
        results[name] = firsts

    w('')
    w('=' * 78)
    w('小结（首字中位数）')
    w('=' * 78)
    for name, _ in cases:
        f = results[name]
        w('  %-24s 中位 %7.0f ms   最快 %7.0f   最慢 %7.0f'
          % (name, statistics.median(f), min(f), max(f)))
    base = statistics.median(results['A 稳定 system'])
    for name in ('B 变化 system', 'C 稳定system+变history'):
        m = statistics.median(results[name])
        w('  %-24s 相对 A 慢 %+.0f ms（%.2f×）' % (name, m - base, m / base))
    w('')
    w('判据：B 明显慢于 A、C 接近 A  →  机制＝system 尾部变化让 KV 前缀缓存失效；')
    w('      那么"事件请求不发变化上下文（只发 persona）"就能把首字拉回 ~0.9s。')
    out.write('\n'.join(L) + '\n')
    out.close()
    print('\nOK -> %s' % os.path.join(HERE, 'probe_prefix_cache.txt'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
