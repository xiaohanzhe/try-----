# -*- coding: utf-8 -*-
"""第133轮 · 事件台词链（`guard_reaction`）到底会不会念提示词？

为什么单测这条链
----
第132轮给**对话**链（`_clean_ai_reply` 第 0c 道）加了 `looks_like_meta_leak`。
事件台词走的是另一条链：

    chat_with_ai(..., lean=True) → system = **整份人设**（不加任何上下文）
    → guard_reaction(first_sentence(reply, 24))
    → guard_reaction 里**没有** looks_like_meta_leak

`lean=True` 的语义是"只发 persona，一个字节都不变"（main.py 14171 行注释），
而第132轮抓到的泄漏源正是人设「语气示范」那几行 ⇒ **结构上这条链同样暴露**。
但这只是推断，本轮先按"实测优先"把语料打出来。

★ 三处刻意安排（写下来，免得下一轮的人以为是随手写的）
  1. **不过滤、不预判**：模型原样输出全部落盘（`raw`），再分别记 `first`（产品截断后）
     与 `final`（过完 guard_reaction）——因为**泄漏常在后段**，只看截断结果会把
     "被截断掉了" 当成 "没发生"。
  2. **判据用产品真源**：`event_speech`（build_prompt / first_sentence / guard_reaction /
     looks_like_meta_leak）直接 import，不抄第二份；OOC / BANNED 两张表走
     `probe115ab.load_guard_patterns()`（与第115/131轮同一份）。
  3. **事件按档位表取**：不用手写字符串，从 `EVENT_TIERS` 里挑 TIER_AI 的事件，
     保证探针问的就是产品会问的。

只读产品文件 + 发本机 HTTP；产物全落本目录的 `_evidence/`。
"""
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EV = os.path.join(ROUND, '_evidence')
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PET = os.path.join(ROOT, 'ralsei_pet')
MODULES = os.path.join(PET, 'modules')
PERSONA = os.path.join(PET, 'assets', 'ralsei_persona.md')
T115 = os.path.join(ROOT, 'code-quality-audit', '第115轮-AI人味训练', '_tools')

SAMPLES = int(os.environ.get('S133_SAMPLES', '3'))
WARMUP = 1

# 覆盖三类事件：鼠标体感（poke/pet）、菜单动作（feed/rest_start）、状态播报（精力/饥饿）
# —— 不挑"看起来会泄漏"的，按登记表顺序取样，避免选择偏差。
EVENTS = [
    'poke_body', 'poke_default', 'pinch_ear', 'double_hair',
    'pet_hair', 'pet_face', 'pet_body',
    'feed', 'pet_menu', 'rest_start', 'eat_start',
    'energy_low', 'hunger_low', 'wake_up',
]

if not os.path.isdir(EV):
    os.makedirs(EV)
for p in (T115, MODULES):
    if p not in sys.path:
        sys.path.insert(0, p)

import probe115ab as AB                    # noqa: E402
import event_speech as ES                  # noqa: E402  产品真源

BUF = io.StringIO()


def say(m=''):
    print(m)
    BUF.write(str(m) + "\n")


def read_text(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def one(kind, prompt, idx, sample, ooc, banned):
    t0 = time.time()
    try:
        r = AB.post('/api/chat', {
            'model': AB.MODEL, 'stream': False,
            'messages': [{'role': 'system', 'content': SYSTEM},
                         {'role': 'user', 'content': prompt}],
            'options': {'num_ctx': AB.NUM_CTX, 'num_predict': 256,
                        'temperature': AB.TEMP_BASE, 'top_p': 0.92,
                        'repeat_penalty': 1.15}})
        raw = (r.get('message') or {}).get('content', '') or ''
        meta = {'prompt_eval_count': r.get('prompt_eval_count'),
                'eval_count': r.get('eval_count'),
                'total_s': round((r.get('total_duration') or 0) / 1e9, 2)}
    except Exception as exc:               # noqa: BLE001
        return {'kind': kind, 'idx': idx, 'sample': sample, 'prompt': prompt,
                'raw': '', 'error': repr(exc), 'wall_s': round(time.time() - t0, 2)}
    # —— 产品的三道处理，逐段留痕（哪一段吃掉的，下一轮才好解释）——
    first = ES.first_sentence(raw, ES.EVENT_MAX_CHARS)
    final = ES.guard_reaction(first)
    rec = {
        'kind': kind, 'idx': idx, 'sample': sample, 'prompt': prompt,
        'raw': raw, 'first': first, 'final': final,
        'wall_s': round(time.time() - t0, 2),
        # 观察量（不是结论）：泄漏在**哪一段**出现
        'meta_raw': ES.looks_like_meta_leak(raw),
        'meta_first': ES.looks_like_meta_leak(first),
        'meta_final': ES.looks_like_meta_leak(final),
        'ooc_raw': ES.looks_out_of_character(raw),
        'banned_raw': ES.looks_like_assistant_speak(raw),
        'ooc_hits': AB.judge(raw, ooc, banned).get('ooc_hits') or [],
        'banned_hits': AB.judge(raw, ooc, banned).get('banned_hits') or [],
        'narration': ES.looks_like_narration(first),
        'chars_first': len(first),
    }
    rec.update(meta)
    return rec


def main():
    global SYSTEM
    say('第133轮 · 事件台词链元话语核查')
    say('  REPO    = %s' % ROOT)
    say('  PERSONA = %s' % PERSONA)
    say('  MODEL   = %s   temp=%.2f   num_ctx=%d' % (AB.MODEL, AB.TEMP_BASE, AB.NUM_CTX))

    SYSTEM = read_text(PERSONA).strip()
    say('[自证] system = 人设原文 %d 字符（lean=True 时产品就是这个，不拼任何上下文）'
        % len(SYSTEM))
    # ★ 分母闸：探针必须真的问到"会泄漏的那几行"上，否则等于没测
    src_lines = [ln for ln in SYSTEM.splitlines()
                 if ('亮起来的开头' in ln) or ('问一句' in ln) or ('留个' in ln)]
    say('[自证] 人设里泄漏源行数 = %d（必须 >0，不然这条链本来就没暴露面）'
        % len(src_lines))
    for ln in src_lines[:4]:
        say('        · %s' % ln.strip()[:60])
    if not src_lines:
        say('[ABORT] 人设里找不到泄漏源 ⇒ 这轮无从谈起')
        return 3

    # 事件必须真在登记表里（避免探针问一个产品不会问的事件）
    bad = [k for k in EVENTS if ES.tier_of(k) != ES.TIER_AI]
    say('[自证] 选样 %d 个事件，非 AI 档的 = %s（必须空）' % (len(EVENTS), bad or '无'))
    if bad:
        return 3

    if not AB.ensure_server():
        return 2
    try:
        ooc, banned, src = AB.load_guard_patterns()
        say('[真源] 护栏两张表 %s（OOC=%d BANNED=%d）' % (src, len(ooc), len(banned)))
        say('[真源] meta 规则 %d 条（event_speech._META_LEAK_RES）'
            % len(ES._META_LEAK_RES))

        # —— 热身（丢弃）：冷加载 + 第一条的偏置 ——
        say('\n=== 热身 %d 条（不计入）===' % WARMUP)
        for i in range(WARMUP):
            t0 = time.time()
            AB.post('/api/chat', {'model': AB.MODEL, 'stream': False,
                                  'messages': [{'role': 'system', 'content': SYSTEM},
                                               {'role': 'user', 'content': '（被摸了一下头。）'}],
                                  'options': {'num_ctx': AB.NUM_CTX, 'num_predict': 32,
                                              'temperature': 0.0}})
            say('  热身 #%d  %.1fs' % (i + 1, time.time() - t0))

        say('\n=== 正式：%d 事件 × %d 采样 = %d 条 ==='
            % (len(EVENTS), SAMPLES, len(EVENTS) * SAMPLES))
        rows = []
        idx = 0
        for kind in EVENTS:
            prompt = ES.build_prompt(kind)
            for s in range(SAMPLES):
                idx += 1
                rec = one(kind, prompt, idx, s + 1, ooc, banned)
                rows.append(rec)
                tag = []
                if rec.get('meta_raw'):
                    tag.append('META-RAW')
                if rec.get('meta_final'):
                    tag.append('META-FINAL')
                if rec.get('ooc_raw'):
                    tag.append('OOC')
                if rec.get('banned_raw'):
                    tag.append('BANNED')
                say('  #%02d %-12s #%d %.1fs %s' % (idx, kind, s + 1,
                                                    rec.get('wall_s', 0),
                                                    '/'.join(tag) or '-'))
                say('      raw   → %s' % (rec.get('raw') or '<空>').replace('\n', ' ⏎ '))
                say('      first → %s' % (rec.get('first') or '<空>').replace('\n', ' ⏎ '))
                say('      final → %s' % (rec.get('final') or '<空>（判退/守卫）'))

        # —— 汇总：分母 + 各计数一起打，禁止只报分子 ——
        n = len(rows)
        err = sum(1 for r in rows if r.get('error'))
        ok = [r for r in rows if not r.get('error')]
        say('\n=== 汇总（n=%d，失败 %d）===' % (n, err))
        for f in ('meta_raw', 'meta_first', 'meta_final', 'ooc_raw', 'banned_raw'):
            say('  %-11s %d/%d' % (f, sum(1 for r in ok if r.get(f)), len(ok)))
        say('  空 first    %d/%d' % (sum(1 for r in ok if not r.get('first')), len(ok)))
        say('  平均首句字数 %.1f' % (
            sum(r.get('chars_first', 0) for r in ok) / max(1, len(ok))))

        with io.open(os.path.join(EV, 'event133.jsonl'), 'w',
                     encoding='utf-8', newline='') as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        out = {'model': AB.MODEL, 'temperature': AB.TEMP_BASE,
               'num_ctx': AB.NUM_CTX, 'samples': SAMPLES, 'events': EVENTS,
               'system_chars': len(SYSTEM), 'leak_source_lines': len(src_lines),
               'guard_src': src, 'ooc_n': len(ooc), 'banned_n': len(banned),
               'meta_res_n': len(ES._META_LEAK_RES), 'n_rows': len(rows),
               'counts': {f: sum(1 for r in ok if r.get(f))
                          for f in ('meta_raw', 'meta_first', 'meta_final',
                                    'ooc_raw', 'banned_raw')}}
        with io.open(os.path.join(EV, 'event133_summary.json'), 'w',
                     encoding='utf-8', newline='') as f:
            f.write(json.dumps(out, ensure_ascii=False, indent=1))
        say('\n[落盘] event133.jsonl（%d 条） / event133_summary.json' % len(rows))
    finally:
        AB.stop_server()
    return 0


SYSTEM = ''

if __name__ == '__main__':
    rc = 99
    try:
        rc = main()
    except BaseException as _exc:          # noqa: BLE001
        import traceback
        say('[EXCEPTION] %r' % (_exc,))
        say(traceback.format_exc())
        rc = 1
    finally:
        try:
            with io.open(os.path.join(HERE, 'probe133_event_out.txt'), 'w',
                         encoding='utf-8', newline='') as f:
                f.write(BUF.getvalue())
        except BaseException:
            pass
    sys.exit(rc)
