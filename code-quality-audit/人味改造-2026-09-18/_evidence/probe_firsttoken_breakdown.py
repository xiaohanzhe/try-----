# -*- coding: utf-8 -*-
"""微探针：App 链路的首字为什么比纯链路慢 3.5 倍？

现象（`s7_e2e_event.txt`）：
  纯链路（同一 system、连打 8 次）           首字 0.79~0.93s
  App 链路（真 RalseiPet → chat_with_ai）    首字 2.86~2.92s
两者差在**请求体**上：App 的 system 更长（persona + 【此刻】 + 话题锚 + 记忆召回），
history 非空。本探针逐个变量对照，把"慢在哪"钉死。

为什么必须钉：这个数字直接决定 `EVENT_SPEAK_FIRST_TOKEN_MS` 该定多少 ——
如果 App 链路真的稳定 2.9s，那么 1200ms 的兜底等于**永远命中**，
S7 的 AI 档就是死的（与之前"整句 1200ms 时限"是同一个死法）。

三个变量，各跑 2 次（第 1 次冷前缀 / 第 2 次复用 KV 前缀）：
  A 迷你 system（~30 字）
  B persona（1591 字）
  C persona + 230 字上下文（≈ App 的 system 长度）
  D C + 2 条 history（≈ App 的完整请求体）

用法：& C:\\Python311\\python.exe probe_firsttoken_breakdown.py
"""
import io
import json
import os
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
# _evidence → 人味改造-2026-09-18 → code-quality-audit → 仓库根
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
BASE = 'http://localhost:11434'
MODEL = 'ralsei:v2'
TIMEOUT = 600

PERSONA = io.open(os.path.join(ROOT, 'ralsei_pet', 'assets', 'ralsei_persona.md'),
                  encoding='utf-8').read()
NOW = '【此刻】现在是深夜，天气晴，心情平静，有点疲惫，主人的名字是小豆'
FOCUS = ('【我们正在聊】关于"被主人抚摸头发"这件事；这是第 1 轮；'
         '没有悬置的问题。除非主人自己换话题，否则别跳。')
RECALL = ('【零星想起】主人曾经说过自己最近在加班，那天的感觉很疲惫；'
          '他也提过喜欢喝热牛奶。')
HIST = [('user', '在吗？'), ('assistant', '嗯，我在的呀。')]
PROMPT = '（主人轻轻抚摸你的头发。）用一句话很短地回应（最多 24 个字），只输出这一句话本身。'
OPTS = {'temperature': 0.85, 'max_tokens': 96}

CASES = [
    ('A 迷你 system', '你是 Ralsei，一只住在电脑桌面上的桌宠。', [], 0),
    ('B persona', PERSONA + '\n\n' + NOW, [], 0),
    ('C persona+上下文', PERSONA + '\n\n' + NOW + '\n\n' + FOCUS + '\n\n' + RECALL, [], 0),
    ('D C + 2 条 history', PERSONA + '\n\n' + NOW + '\n\n' + FOCUS + '\n\n' + RECALL, HIST, 0),
]


def first_token_ms(system, history):
    messages = [{'role': 'system', 'content': system}]
    for r, c in history:
        messages.append({'role': r, 'content': c})
    messages.append({'role': 'user', 'content': PROMPT})
    payload = {'model': MODEL, 'messages': messages, 'stream': True, **OPTS}
    t0 = time.time()
    first = None
    n = 0
    with requests.post(BASE + '/v1/chat/completions', json=payload,
                       timeout=TIMEOUT, stream=True) as resp:
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
                piece = (json.loads(body).get('choices') or [{}])[0].get('delta', {}).get('content')
            except Exception:
                continue
            if piece:
                if first is None:
                    first = time.time() - t0
                n += 1
    return (None if first is None else first * 1000.0), (time.time() - t0) * 1000.0, n


def prompt_tokens(system, history):
    """用 Ollama 原生端点问一次真实 prompt_eval_count（/v1 不返回这个数）。"""
    messages = [{'role': 'system', 'content': system}]
    for r, c in history:
        messages.append({'role': r, 'content': c})
    messages.append({'role': 'user', 'content': PROMPT})
    try:
        r = requests.post(BASE + '/api/chat',
                          json={'model': MODEL, 'messages': messages, 'stream': False,
                                'options': dict(OPTS, num_ctx=8192)},
                          timeout=TIMEOUT)
        d = r.json()
        return d.get('prompt_eval_count'), d.get('prompt_eval_duration', 0) / 1e6
    except Exception as e:
        return ('err:%s' % e), None


def main():
    out = io.open(os.path.join(HERE, 'probe_firsttoken_breakdown.txt'), 'w',
                  encoding='utf-8', newline='\n')
    out.write('=' * 78 + '\n')
    out.write('App 链路首字拆解：system 长度 / history 各自贡献多少\n')
    out.write('model=%s  端点=/v1/chat/completions（流式，与线上同参）\n' % MODEL)
    out.write('时间：%s\n' % time.strftime('%Y-%m-%d %H:%M:%S'))
    out.write('=' * 78 + '\n\n')
    out.write('%-22s %10s %14s %12s %10s %10s\n'
              % ('用例', 'system字数', 'prompt tokens', 'prompt读入ms', '首字#1ms', '首字#2ms'))
    for name, system, hist, _ in CASES:
        ptok, pms = prompt_tokens(system, hist)
        f1, _, _ = first_token_ms(system, hist)
        f2, t2, n2 = first_token_ms(system, hist)
        line = ('%-22s %10d %14s %12s %10.0f %10.0f'
                % (name, len(system), ptok,
                   ('%.0f' % pms) if isinstance(pms, float) else str(pms), f1, f2))
        print(line)
        out.write(line + '\n')
    out.write('\n说明：\n')
    out.write('  · "首字#1" 是**冷前缀**（KV 缓存里没有这段 system）→ 付全额 prompt eval\n')
    out.write('  · "首字#2" 是**同一个请求再打一次** → 前缀命中，能看出 prompt eval 占多少\n')
    out.write('  · 纯链路 8 次事件之所以都是 0.8s，是因为它们**共用同一段 system**，\n')
    out.write('    且预热时已经建过那段前缀的 KV 缓存 —— 不代表真实用户场景。\n')
    out.close()
    print('\n-> %s' % os.path.join(HERE, 'probe_firsttoken_breakdown.txt'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
