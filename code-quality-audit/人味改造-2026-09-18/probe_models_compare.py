# -*- coding: utf-8 -*-
"""三向对比：3B(现用) / 4B(qwen3-4b-instruct-2507，新拉) / 7B(qwen2.5-7b，本地已有)

用户 2026-09-19 的决定是「所有对话全权交给 AI，不给内置台词了」，
同一句话里带前提「**如果 AI 能足够生动**」，并**授权换模型**。
这个脚本就是为"换不换、换谁"出证据的。

公平性
------
三个模型都吃**同一份** system（`assets/ralsei_persona.md` —— 生产里的单一真源），
都走 /api/chat + 同一套 options，都过**同一道**后处理
（`first_sentence(24)` → `guard_reaction`，即 2026-09-19 扩过的出戏/客服腔/旁白三闸）。
所以差异只来自模型本身。（生产里 system 由 App 发过去、会整体替换 Modelfile 的 SYSTEM，
所以 ralsei:v2 的 Modelfile 微调**不会**在这里占便宜 —— 这正是线上真实情形。）

看的四件事
----------
1. **判退率** —— 出了禁语/出戏/旁白（判退 = 该次没有可用台词；去掉罐头后就是"这次没说话"）
2. **整句耗时**（CPU 推理，本机无独显）—— 直接决定"打字机要打多久"
3. **平均字数** —— 事件反应上限 24 字，太长说明它不听形状约束
4. **原文** —— 生动度只能人眼看，所以整段落盘，不只在终端里给个分数

用法：python probe_models_compare.py
产物：_evidence/probe_models_compare.txt（只读，不改仓库其它东西）
"""
import json
import os
import statistics
import sys
import time
import urllib.request

HERE = os.path.abspath(os.path.dirname(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(REPO, 'ralsei_pet')
sys.path.insert(0, os.path.join(PET, 'modules'))
sys.path.insert(0, HERE)

import event_speech as E                                          # noqa: E402
from probe_vividness import SCENES, TAIL                          # noqa: E402

PERSONA = os.path.join(PET, 'assets', 'ralsei_persona.md')
HOST = 'http://localhost:11434'
OPTS = {'temperature': 0.85, 'top_p': 0.92, 'repeat_penalty': 1.15,
        'num_ctx': 8192, 'num_predict': 256}
REPS = 2

MODELS = [
    ('ralsei:v2', '3B ralsei:v2（现用）'),
    ('qwen3:4b-instruct-2507-q4_K_M', '4B qwen3-instruct-2507（新拉）'),
    ('qwen2.5:7b-instruct', '7B qwen2.5（参照）'),
]


def _post(path, payload, timeout=600):
    req = urllib.request.Request(
        HOST + path, data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'})
    return urllib.request.urlopen(req, timeout=timeout)


def unload(model):
    try:
        _post('/api/chat', {'model': model, 'messages': [], 'keep_alive': 0}).read()
    except Exception:
        pass
    time.sleep(1.0)


def chat_once(model, system, user):
    payload = {'model': model,
               'messages': [{'role': 'system', 'content': system},
                            {'role': 'user', 'content': user}],
               'stream': True, 'options': OPTS}
    t0 = time.perf_counter()
    ttft, text = None, ''
    for raw in _post('/api/chat', payload):
        raw = raw.decode('utf-8', 'replace').strip()
        if not raw:
            continue
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        piece = (d.get('message') or {}).get('content') or ''
        if piece:
            if ttft is None:
                ttft = (time.perf_counter() - t0) * 1000.0
            text += piece
        if d.get('done'):
            break
    return ttft, (time.perf_counter() - t0) * 1000.0, text


def reason_of(shown_raw, shown):
    """判退原因（用于统计）。"""
    if not shown:
        if E.looks_out_of_character(shown_raw):
            return 'ooc'
        if E.looks_like_assistant_speak(shown_raw):
            return 'banned'
        if E.looks_like_narration(shown_raw):
            return 'narration'
        return 'empty'
    return ''


def main():
    with open(PERSONA, 'r', encoding='utf-8') as f:
        persona = f.read().strip()

    have = set()
    try:
        with urllib.request.urlopen(HOST + '/api/tags', timeout=20) as r:
            have = set(m.get('name') for m in json.loads(r.read().decode('utf-8')).get('models', []))
    except Exception as e:
        print('读不到 /api/tags: %s' % e)

    L = []
    L.append('三向对比 —— 为「所有对话全权交给 AI」选底座（2026-09-19）')
    L.append('system = assets/ralsei_persona.md（%d 字，三模型同源）' % len(persona))
    L.append('options = %s' % json.dumps(OPTS, ensure_ascii=False))
    L.append('每个场景 %d 条；事件类过 first_sentence(%d) + guard_reaction（出戏/客服腔/旁白）'
             % (REPS, E.EVENT_MAX_CHARS))
    L.append('本地已有：%s' % ', '.join(sorted(have)))
    L.append('=' * 78)

    summary = {}
    for model, label in MODELS:
        if have and model not in have:
            L.append('')
            L.append('SKIP %s （本地不存在）' % model)
            continue
        L.append('')
        L.append('#' * 78)
        L.append('## %s   (%s)' % (label, model))
        L.append('#' * 78)
        unload(model)
        try:
            ttft, total, _ = chat_once(model, persona, '（热身）')
            L.append('预热（含冷加载）：首字 %.0fms / 整句 %.0fms' % (ttft or -1, total))
        except Exception as e:
            L.append('预热失败，跳过该模型：%s' % e)
            continue

        rows, rejects = [], {}
        for tag, name, slabel, payload in SCENES:
            user = (E.build_prompt(payload) if payload in ('poke_body', 'pet_hair', 'rest_start')
                    else payload + TAIL)
            L.append('')
            L.append('  --- [%s] %s  (%s)' % (tag, slabel, name))
            for i in range(REPS):
                try:
                    ttft, total, raw = chat_once(model, persona, user)
                except Exception as e:
                    L.append('    #%d 请求失败 %s' % (i + 1, e))
                    continue
                if tag == 'E':
                    shown = E.guard_reaction(E.first_sentence(raw, E.EVENT_MAX_CHARS))
                    r = reason_of(raw, shown)
                    if r:
                        rejects[r] = rejects.get(r, 0) + 1
                    mark = '' if shown else '   ←判退(%s)' % r
                    L.append('    #%d %5.0fms/%5.0fms ▸「%s」%s' % (i + 1, ttft or -1, total, shown, mark))
                    if not shown:
                        L.append('        裸回复▸ %s' % raw.replace('\n', ' ⏎ ')[:150])
                else:
                    L.append('    #%d %5.0fms/%5.0fms ▸ %s' % (i + 1, ttft or -1, total,
                                                              raw.replace('\n', ' ⏎ ')[:170]))
                rows.append((tag, ttft or 0, total, len(raw)))

        ev = [r for r in rows if r[0] == 'E']
        if ev:
            summary[label] = {
                'model': model,
                'n': len(ev),
                'judged': sum(rejects.values()),
                'rejects': dict(rejects),
                'ev_total_med': statistics.median([r[2] for r in ev]),
                'ev_ttft_med': statistics.median([r[1] for r in ev]),
                'all_total_med': statistics.median([r[2] for r in rows]),
            }
        unload(model)

    L.append('')
    L.append('=' * 78)
    L.append('## 汇总（事件类口径；耗时单位 ms，取中位数）')
    L.append('%-30s %5s %8s %10s %10s %10s' % ('模型', '样本', '判退', '事件首字', '事件整句', '全部整句'))
    for label, s in summary.items():
        L.append('%-30s %5d %8d %10.0f %10.0f %10.0f'
                 % (label, s['n'], s['judged'], s['ev_ttft_med'], s['ev_total_med'], s['all_total_med']))
    L.append('')
    for label, s in summary.items():
        if s['rejects']:
            L.append('  %s 判退构成：%s' % (label, json.dumps(s['rejects'], ensure_ascii=False)))

    out = os.path.join(HERE, '_evidence', 'probe_models_compare.txt')
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(L) + '\n')
    print('written: %s' % out)
    print('\n'.join(L[-12:]))


if __name__ == '__main__':
    main()
