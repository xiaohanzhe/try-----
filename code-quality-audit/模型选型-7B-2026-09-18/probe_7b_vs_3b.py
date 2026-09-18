# -*- coding: utf-8 -*-
"""7B 换型可行性实测：`ralsei:v2`(3B) vs `qwen2.5:7b-instruct`(7B)。

要回答的问题（用户原话）
------------------------
「把模型换成 7B 能用吗？前提是**回应速度和其他性能的变化基本可忽略不计**，
并且**明显更生动**（没太大坏处、但有明显好处）。」

所以本探针只测两类东西，别的都不测：

  P1 **速度**（这是"能不能用"的硬门槛）
     ① 冷加载：用户点开对话第一次要等多久（模型从磁盘进内存）
     ② 首字延迟：用户感知的"它反应快不快" —— S8/事件台词都靠它
     ③ 生成速度 tok/s：决定"一句话要吐多久"
     ④ 整句耗时：首字 + N/tok_s
  P2 **质量**（这是"值不值得"）
     同一批提示词两模型并排输出 + 出戏率（"作为AI/我没有触觉"这类自毁角色句）

为什么必须在这台机器上真跑，不能查规格表
--------------------------------------
本机是 **Intel Core Ultra 5 125H + Intel Arc 核显 + 32G 内存（无独显）**，
Ollama 只能用 CPU 推理（Arc 不在 Ollama 官方加速列表里）。
3B 在这台机器上"够快"是实测结论，7B 的倍数放缩**必须实测**，外推不算。

通路：**复刻 App 的真实链路**
---------------------------
不是裸 HTTP，而是照 `api_client.HTTPLocalAI._chat_payload()` 那份请求体：
    POST {base_url}/v1/chat/completions
    {"model":…, "messages":[system, user], "temperature":0.85,
     "max_tokens":256, "stream":true}
system = `ralsei_pet/assets/ralsei_persona.md`（单一真源，与线上同一份）。

另外用 Ollama 原生 `/api/chat` 拿它**自己报的分项耗时**
（`load_duration` / `prompt_eval_duration` / `eval_duration` / `eval_count`），
用来拆"慢在哪" —— 是加载慢、读提示词慢、还是吐字慢。
这两个端点都要测：`/v1` 是线上真实通路，`/api` 是唯一能拿分项数据的地方。

用法
----
    & C:\\Python311\\python.exe probe_7b_vs_3b.py
产物：同目录 `probe_7b_vs_3b.txt`（UTF-8，由 Python 自己写，避开 GBK 乱码）
"""
import io
import json
import os
import statistics
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PERSONA = os.path.join(ROOT, 'ralsei_pet', 'assets', 'ralsei_persona.md')

BASE = 'http://localhost:11434'
TIMEOUT = 600

MODELS = [
    ('ralsei:v2', '3B (当前)'),
    ('qwen2.5:7b-instruct', '7B (候选)'),
]

# 与线上一致的采样参数（ralsei:v2 已把这几项烘进 Modelfile，
# 这里显式再传一份，让 7B 不吃亏 —— 否则对比的是"模型"而不是"配置"）
GEN = {'temperature': 0.85, 'top_p': 0.92, 'repeat_penalty': 1.15}
NUM_CTX = 8192
LAT_MAX_TOKENS = 96          # 延迟探针的输出上限（宠物回复本来就短，96 足够）

PERSONA_TEXT = io.open(PERSONA, encoding='utf-8').read()
NOW = '【此刻】现在是深夜，主人还坐在电脑前'

# 5 个提示词：前 4 个是日常闲聊（考"接住情绪"），最后 1 个考角色深度
CHAT_PROMPTS = [
    '今天上班好累啊',
    '你觉得自己可爱吗？',
    '我刚被老板骂了一顿，心里好烦',
    '陪我聊聊天呗，随便说点什么',
]
LORE_PROMPT = '你还记得黑暗世界的事吗？'


def log(f, s=''):
    print(s)
    f.write(s + '\n')


def unload(model):
    """把模型从内存里踢出去，好让下一次调用真的是"冷"的。"""
    try:
        requests.post(BASE + '/api/generate',
                      json={'model': model, 'keep_alive': 0}, timeout=60)
    except Exception as e:
        print('  (unload 失败，忽略: %s)' % e)


def ps():
    try:
        r = requests.get(BASE + '/api/ps', timeout=30)
        return r.json().get('models') or []
    except Exception:
        return []


# --------------------------------------------------------------- 通路一：/v1
def call_v1(model, user_text, max_tokens=LAT_MAX_TOKENS, history=None):
    """复刻 App 的 /v1/chat/completions 流式调用，返回首字/整句耗时与全文。"""
    messages = [{'role': 'system', 'content': PERSONA_TEXT + '\n\n' + NOW}]
    for role, content in (history or []):
        messages.append({'role': role, 'content': content})
    messages.append({'role': 'user', 'content': user_text})
    payload = {'model': model, 'messages': messages, 'temperature': GEN['temperature'],
               'max_tokens': max_tokens, 'stream': True}
    t0 = time.time()
    first = None
    parts = []
    n_chunk = 0
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
                obj = json.loads(body)
                piece = (obj.get('choices') or [{}])[0].get('delta', {}).get('content')
            except Exception:
                continue
            if not piece:
                continue
            if first is None:
                first = time.time() - t0
            parts.append(piece)
            n_chunk += 1
    total = time.time() - t0
    return {'first_ms': None if first is None else first * 1000.0,
            'total_ms': total * 1000.0,
            'text': ''.join(parts), 'n_chunk': n_chunk}


# --------------------------------------------------------------- 通路二：/api
def call_api(model, user_text, max_tokens=LAT_MAX_TOKENS):
    """Ollama 原生 /api/chat，拿它自报的分项耗时。"""
    messages = [{'role': 'system', 'content': PERSONA_TEXT + '\n\n' + NOW},
                {'role': 'user', 'content': user_text}]
    payload = {'model': model, 'messages': messages, 'stream': True,
               'options': dict(GEN, num_ctx=NUM_CTX, num_predict=max_tokens)}
    t0 = time.time()
    first = None
    parts = []
    final = {}
    with requests.post(BASE + '/api/chat', json=payload,
                       timeout=TIMEOUT, stream=True) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines(chunk_size=1):
            if not line:
                continue
            try:
                obj = json.loads(line.decode('utf-8', 'replace'))
            except Exception:
                continue
            piece = (obj.get('message') or {}).get('content')
            if piece:
                if first is None:
                    first = time.time() - t0
                parts.append(piece)
            if obj.get('done'):
                final = obj
    total = time.time() - t0

    def ms(key):
        v = final.get(key)
        return None if v is None else v / 1e6   # ollama 报的是纳秒

    return {'first_ms': None if first is None else first * 1000.0,
            'total_ms': total * 1000.0,
            'load_ms': ms('load_duration'),
            'prompt_eval_n': final.get('prompt_eval_count'),
            'prompt_eval_ms': ms('prompt_eval_duration'),
            'eval_n': final.get('eval_count'),
            'eval_ms': ms('eval_duration'),
            'text': ''.join(parts)}


OOC = ('作为ai', '作为一个ai', '人工智能', '语言模型', '大模型', '没有触觉',
       '无法感受', '感觉不到', '没有身体', '我是一个程序', '机器人', '系统提示',
       '提示词', '作为一个助手', '我理解你的感受', '有什么可以帮你')


def ooc_hit(text):
    low = (text or '').lower()
    return [w for w in OOC if w in low]


def main():
    f = io.open(os.path.join(HERE, 'probe_7b_vs_3b.txt'), 'w',
                encoding='utf-8', newline='\n')
    log(f, '=' * 78)
    log(f, '7B 换型可行性实测  —  ralsei:v2(3B)  vs  qwen2.5:7b-instruct(7B)')
    log(f, '机器：Intel Core Ultra 5 125H（14 核 / 18 线程）+ Intel Arc 核显，无独显 → CPU 推理')
    log(f, '通路：POST /v1/chat/completions（线上真实通路）+ POST /api/chat（拿分项耗时）')
    log(f, 'system：assets/ralsei_persona.md（%d 字）+ %s' % (len(PERSONA_TEXT), NOW))
    log(f, '生成参数：temperature=%.2f top_p=%.2f repeat_penalty=%.2f num_ctx=%d'
        % (GEN['temperature'], GEN['top_p'], GEN['repeat_penalty'], NUM_CTX))
    log(f, '时间：%s' % time.strftime('%Y-%m-%d %H:%M:%S'))
    log(f, '=' * 78)

    summary = {}
    for model, label in MODELS:
        log(f, '')
        log(f, '#' * 78)
        log(f, '# %s  ——  %s' % (model, label))
        log(f, '#' * 78)

        # ---------- P1 速度 ----------
        unload(model)
        time.sleep(1.0)

        log(f, '[冷加载 + 首字] 走 /api/chat 拿分项耗时')
        cold = call_api(model, CHAT_PROMPTS[0], LAT_MAX_TOKENS)
        log(f, '  冷调用：首字 %.0fms / 整句 %.0fms' % (cold['first_ms'], cold['total_ms']))
        log(f, '    模型加载   %.0fms' % (cold['load_ms'] or 0))
        log(f, '    读提示词   %.0fms（%s tokens，%.0f tok/s）'
            % (cold['prompt_eval_ms'] or 0, cold['prompt_eval_n'],
               (cold['prompt_eval_n'] or 0) / max(cold['prompt_eval_ms'] or 1, 1) * 1000))
        log(f, '    吐字       %.0fms（%s tokens，%.2f tok/s）'
            % (cold['eval_ms'] or 0, cold['eval_n'],
               (cold['eval_n'] or 0) / max(cold['eval_ms'] or 1, 1) * 1000))
        log(f, '  冷调用输出：%s' % cold['text'])

        running = ps()
        log(f,  '  ollama ps：%s' % [(m.get('name'), m.get('size_vram')) for m in running])

        log(f, '[热调用 ×2] 走 /v1（线上通路），同一句')
        v1s = []
        for i in range(2):
            r = call_v1(model, CHAT_PROMPTS[0], LAT_MAX_TOKENS)
            v1s.append(r)
            log(f, '  #%d 首字 %.0fms / 整句 %.0fms / 分片 %d / 输出 %d 字'
                % (i + 1, r['first_ms'], r['total_ms'], r['n_chunk'], len(r['text'])))
            time.sleep(0.3)

        warm = call_api(model, CHAT_PROMPTS[0], LAT_MAX_TOKENS)
        tok_s = (warm['eval_n'] or 0) / max((warm['eval_ms'] or 1) / 1000.0, 0.001)
        pre_s = (warm['prompt_eval_n'] or 0) / max((warm['prompt_eval_ms'] or 1) / 1000.0, 0.001)
        log(f, '[热调用 /api 分项] 读提示词 %.0f tok/s，吐字 %.2f tok/s'
            % (pre_s, tok_s))
        log(f, '  → 预测"40 字回复"整句耗时 ≈ 首字 %.1fs + 40字/%.1f字每秒 ≈ %.1fs'
            % (warm['first_ms'] / 1000.0, tok_s * 1.5, warm['first_ms'] / 1000.0 + 40 / max(tok_s * 1.5, 0.1)))

        summary[model] = {
            'cold_first_ms': cold['first_ms'], 'cold_total_ms': cold['total_ms'],
            'load_ms': cold['load_ms'], 'prompt_tok_s': pre_s, 'gen_tok_s': tok_s,
            'warm_first_ms': statistics.median([r['first_ms'] for r in v1s]),
            'warm_total_ms': statistics.median([r['total_ms'] for r in v1s]),
        }

        # ---------- P2 质量 ----------
        log(f, '')
        log(f, '[质量] 同一批提示词并排输出（走 /v1，与线上同参）')
        bad = 0
        for p in CHAT_PROMPTS + [LORE_PROMPT]:
            r = call_v1(model, p, LAT_MAX_TOKENS)
            hit = ooc_hit(r['text'])
            if hit:
                bad += 1
            log(f, '  Q: %s' % p)
            log(f, '  A: %s' % (r['text'].strip() or '(空)'))
            log(f, '     首字 %.0fms / 整句 %.0fms%s'
                % (r['first_ms'], r['total_ms'],
                   '   <<< 出戏词 %s' % hit if hit else ''))
        summary[model]['ooc'] = bad
        summary[model]['ooc_total'] = len(CHAT_PROMPTS) + 1

    # ---------- 收尾：把两个模型都从内存踢出去 ----------
    log(f, '')
    log(f, '=' * 78)
    log(f, '汇总')
    log(f, '=' * 78)
    hdr = '%-22s %10s %10s %10s %10s %9s %9s %8s' % (
        'model', '冷加载ms', '冷首字ms', '热首字ms', '热整句ms', '读词tok/s', '吐字tok/s', '出戏')
    log(f, hdr)
    for model, label in MODELS:
        s = summary[model]
        log(f, '%-22s %10.0f %10.0f %10.0f %10.0f %9.1f %9.2f %5d/%d' % (
            model, s['load_ms'] or 0, s['cold_first_ms'], s['warm_first_ms'],
            s['warm_total_ms'], s['prompt_tok_s'], s['gen_tok_s'],
            s['ooc'], s['ooc_total']))

    a, b = [summary[m] for m, _ in MODELS]
    log(f, '')
    log(f, '倍数（7B / 3B）')
    for key, name in (('load_ms', '冷加载'), ('warm_first_ms', '热首字'),
                      ('warm_total_ms', '热整句'), ('gen_tok_s', '吐字速度(倒数)')):
        if key == 'gen_tok_s':
            ratio = b[key] and (a[key] / b[key])
        else:
            ratio = (b[key] / a[key]) if a.get(key) else None
        log(f, '  %-14s %.2f×' % (name, ratio if ratio else float('nan')))

    for model, _ in MODELS:
        unload(model)
    log(f, '')
    log(f, '已把两个模型都 unload（keep_alive=0），不占用内存。')
    f.close()
    print('\nOK -> %s' % os.path.join(HERE, 'probe_7b_vs_3b.txt'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
