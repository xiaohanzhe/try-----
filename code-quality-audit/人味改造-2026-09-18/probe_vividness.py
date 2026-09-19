# -*- coding: utf-8 -*-
"""生动度抽查：把「准备全权交给 AI」的那批场景，按**生产同形请求**各抽 3 条看原文。

为什么单独跑这一发
------------------
用户 2026-09-19 的决定是：「所有对话全权交给 AI，不给内置台词了」——
但同一句话里带了个前提：「**如果 AI 能足够生动**」。
这个前提是要证据的：如果 3B 出的句子本身寡淡/复读/出戏，那"去掉内置台词"不是升级，
是把每句话都换成一句平庸的 3B 句子 —— 比内置台词还差。

请求形状与生产**逐字对齐**（不自己发明参数）
------------------------------------------
· system = `assets/ralsei_persona.md` 原文（= `RalseiPet._build_persona_prompt()`）
· user   = `event_speech.build_prompt(kind)`（旁白 + 形状约束），**不带**上下文/历史（lean）
· options = temperature 0.85 / top_p 0.92 / repeat_penalty 1.15 / num_ctx 8192
  （与 `模型选型-4B-2026-09-18/probe_4b_vs_3b.py` 记录一致）
· 事件类台词再过**生产的两道后处理**：`first_sentence(text, 24)` → `guard_reaction(...)`，
  所以打印的"上线后长这样"就是真机会长这样，而不是裸回复。

只读、不写仓库、不改任何配置；产物写 `_evidence/probe_vividness.txt`。
必须用 `C:\\Python311\\python.exe` 跑（要 import 项目模块）。
"""
import json
import os
import sys
import time
import urllib.request

HERE = os.path.abspath(os.path.dirname(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
PET = os.path.join(REPO, 'ralsei_pet')
sys.path.insert(0, os.path.join(PET, 'modules'))

from event_speech import build_prompt, first_sentence, guard_reaction, EVENT_MAX_CHARS  # noqa: E402

PERSONA = os.path.join(PET, 'assets', 'ralsei_persona.md')
HOST = 'http://localhost:11434'
MODEL = 'ralsei:v2'
OPTS = {'temperature': 0.85, 'top_p': 0.92, 'repeat_penalty': 1.15,
        'num_ctx': 8192, 'num_predict': 256}
REPS = 3

TAIL = ('用一句话很短地回应（最多 %d 个字），只输出这一句话本身。'
        '不要提问，不要解释，不要加任何标记或旁白。') % EVENT_MAX_CHARS


def _post(path, payload, timeout=300):
    req = urllib.request.Request(
        HOST + path,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'})
    return urllib.request.urlopen(req, timeout=timeout)


def chat_once(system, user):
    """流式发一发，返回 (ttft_ms, total_ms, text)。"""
    payload = {'model': MODEL,
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


# ---------------------------------------------------------------- 场景表
# kind 要么是已登记事件（直接 build_prompt），要么给一段旁白（模拟"将要迁的"那一批）。
# 分类标签只用于人眼阅读：E=事件反应(≤24字)  D=自由对话(≤80字，走 _clean_ai_reply)
SCENES = [
    # ---- 已经迁走的（对照基线）----
    ('E', 'poke_body',    '对照·戳身体',        'poke_body'),
    ('E', 'pet_hair',     '对照·摸头',          'pet_hair'),
    ('E', 'rest_start',   '对照·开始休息',      'rest_start'),
    # ---- §三 环境/时间触发（本轮候选）----
    ('E', 'tired_low',    '累·低档播报',        '（你现在有点累了。跟主人说一句。）'),
    ('E', 'tired_crit',   '累·快撑不住',        '（你累得快走不动了。跟主人说一句。）'),
    ('E', 'hungry_low',   '饿·有点饿',          '（你有点饿了。跟主人说一句。）'),
    ('E', 'greet_morning', '问候·早上',         '（现在是早上，主人刚打开电脑。跟主人打个招呼。）'),
    ('E', 'greet_noon',   '问候·中午',          '（现在是中午。跟主人说一句。）'),
    ('E', 'greet_night',  '问候·深夜',          '（已经很晚了，主人还在忙。跟主人说一句。）'),
    ('E', 'fall_recover', '摔下来爬起',         '（你刚从高处摔了下来，现在自己爬起来了。）'),
    ('E', 'refuse_full',  '拒绝·已经吃饱',      '（主人又想喂你东西，但你已经吃得饱饱的了，只好拒绝。）'),
    # ---- §四 功能回执：测"会不会丢信息"（本轮要拍的重点）----
    ('E', 'ppt_page',     '回执·翻到第3页',     '（主人让你翻页。你已经把幻灯片翻到第 3 页，一共 12 页。用一句话告诉他。）'),
    ('E', 'file_count',   '回执·桌面文件数',    '（主人问桌面上有多少文件。你数出来是 27 个。用一句话告诉他。）'),
    ('E', 'game_rule',    '回执·游戏规则',      '（主人想玩猜数字。你要告诉他：请输入 1 到 100 之间的数字。）'),
    # ---- 自由对话（对照，走 80 字口径）----
    ('D', 'q_tired',      '对话·上班被骂',      '今天上班好累啊，被领导骂了一顿'),
    ('D', 'q_short',      '对话·极短输入',      '在吗'),
]


def main():
    with open(PERSONA, 'r', encoding='utf-8') as f:
        persona = f.read().strip()

    L = []
    L.append('生动度抽查 —— 结论用：把「所有对话交给 AI」这件事能不能做')
    L.append('模型 %s @ %s' % (MODEL, HOST))
    L.append('system = assets/ralsei_persona.md（%d 字）；user = 旁白 + 形状约束；不带上下文/历史（lean）' % len(persona))
    L.append('options = %s' % json.dumps(OPTS, ensure_ascii=False))
    L.append('每个场景抽 %d 条；事件类额外过 first_sentence(%d) + guard_reaction' % (REPS, EVENT_MAX_CHARS))
    L.append('=' * 78)

    # 预热：把 system 前缀灌进 KV 缓存，之后测到的才是生产里的"缓存命中"首字。
    try:
        ttft, total, _ = chat_once(persona, '（热身）')
        L.append('预热完成：首字 %.0fms / 整句 %.0fms' % (ttft or -1, total))
    except Exception as e:
        L.append('预热失败：%s' % e)
        print('\n'.join(L))
        return
    L.append('=' * 78)

    for tag, name, label, payload in SCENES:
        user = build_prompt(payload) if payload in (
            'poke_body', 'pet_hair', 'rest_start') else (payload + TAIL)
        L.append('')
        L.append('### [%s] %-14s  kind=%s' % (tag, label, name))
        L.append('  user▸ %s' % user)
        for i in range(REPS):
            try:
                ttft, total, raw = chat_once(persona, user)
            except Exception as e:
                L.append('  #%d 请求失败：%s' % (i + 1, e))
                continue
            if tag == 'E':
                shown = guard_reaction(first_sentence(raw, EVENT_MAX_CHARS))
                extra = '' if shown else '   ← 被判退/为空（生产里会回落罐头）'
                L.append('  #%d 首字%5.0fms 整句%5.0fms 上线后▸「%s」%s' % (i + 1, ttft or -1, total, shown, extra))
                L.append('       裸回复▸ %s' % raw.replace('\n', ' ⏎ ')[:160])
            else:
                L.append('  #%d 首字%5.0fms 整句%5.0fms 裸回复▸ %s' % (i + 1, ttft or -1, total,
                                                                    raw.replace('\n', ' ⏎ ')[:200]))

    out = os.path.join(HERE, '_evidence', 'probe_vividness.txt')
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(L) + '\n')
    print('written: %s' % out)
    print('lines: %d' % len(L))


if __name__ == '__main__':
    main()
