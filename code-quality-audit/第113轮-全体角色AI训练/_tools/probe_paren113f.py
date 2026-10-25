# -*- coding: utf-8 -*-
"""第113轮f 探针：括号旁白到底该从哪治 —— 规则 vs 人设范例，做个受控 A/B。

背景
----
`SPEAK_RULES` 里**早就有**「也不要用括号描写动作」，可 susie 48 轮里 45 轮照写。
猜测是 **76 份人设共 1262 处括号范例**把这条规则压过去了（少样本模仿 > 一句指令）。

做法（夹具与训练器同源：同一个 `system_for` / `chat` / `seed` / `temperature`）
  P0 base     ：现在的 prompt（基线）
  P1 rule     ：末尾追加「不要写旁白」硬规则 + 一条正例（**不给反例**，怕反向教学）
  P2 persona  ：人设正文**去掉全部括号范例**，其余不变
  P3 both     ：P1 + P2
每个变体跑 6 轮连续对话（多轮必要 —— 模型会**抄自己上一轮**的括号，单轮测不出来），
2 个角色（susie / asgore），seed 逐轮固定 ⇒ 变体之间可比。

判据：`common113._PAREN_RE`（已修好，{1,200}）命中轮数 / 6。
"""
import io
import json
import os
import re
import sys
import time

HERE = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, HERE)

import common113 as C      # noqa: E402
import dialogue113 as D    # noqa: E402
import train30 as T        # noqa: E402

OUT = os.path.join(HERE, '..', '_evidence', 'probe_paren113f.jsonl')

RULE_BLOCK = (
    "【这一条最要紧：只写你说出口的话】\n"
    "玩家在对话框里看到的那一行字，就是你**说出口的台词**，不是旁白、不是小说。\n"
    "所以不要用括号写动作、表情、心理，也不要写「你皱了皱眉」这种从外面看自己的句子；\n"
    "想说语气，就靠用词和标点本身。\n"
    "正例：烦死了。你别这么盯着我看，我又不会跑。\n"
)

_P_ANY = re.compile(r'[（(][^（()）]{0,400}[)）]')


def strip_all_parens(text):
    """人设正文去掉全部括号范例（P2 用）。"""
    if not isinstance(text, str):
        return ''
    return _P_ANY.sub('', text)


def cn_ratio(text):
    s = re.sub(r'\s+', '', text or '')
    if not s:
        return 0.0
    cn = len(re.findall(r'[\u4e00-\u9fff]', s))
    return cn / float(len(s))


def run_variant(card, turns_n, system, tag):
    """跑 turns_n 轮连续对话，返回逐轮结果。"""
    msgs = [{'role': 'system', 'content': system}]
    turns = []
    for i in range(1, turns_n + 1):
        raw = T.SCRIPT30[(i - 1) % len(T.SCRIPT30)]
        user = T.fill_dynamic(card, turns, i, raw)
        msgs.append({'role': 'user', 'content': user})
        seed = C.stable_seed(card['id'], 'probe113f', i, 0)   # ★ 变体间同 seed
        err = ''
        t0 = time.time()
        try:
            D.wait_for_memory()          # ★ 在 dialogue113，不在 common113
            text, st = C.chat(msgs, seed=seed, temperature=C.TEMPERATURE,
                              num_ctx=20480, num_predict=T.PREDICT30,
                              timeout=240)   # ★ 必须显式给：挂死时 errno 会一直等
        except Exception as e:
            text, st = '', {}
            err = repr(e)[:200]
        print(' %d(%.0fs)' % (i, time.time() - t0), end='', flush=True)
        msgs.append({'role': 'assistant', 'content': text})
        m = C._PAREN_RE.search(text or '')
        q = re.search(r'[（(][^）)]{0,200}["\u201c\u201d\u300c\u300d]', text or '')
        turns.append({'i': i, 'user': user, 'text': text,
                      'paren': bool(m), 'paren_sample': (m.group(0)[:60] if m else ''),
                      'quoted_in_paren': bool(q), 'chars': len(text or ''),
                      'cn': round(cn_ratio(text), 2), 'error': err,
                      'truncated': st.get('truncated')})
    return turns


def summarize(turns):
    n = len(turns)
    errs = [t['error'] for t in turns if t.get('error')]
    empty = sum(1 for t in turns if not (t['text'] or '').strip())
    return {
        'turns': n,
        'errors': len(errs),
        'error_sample': errs[0] if errs else '',
        'empty_turns': empty,
        'paren_turns': sum(1 for t in turns if t['paren']),
        'paren_rate': round(sum(1 for t in turns if t['paren']) / float(n), 2),
        'quoted_turns': sum(1 for t in turns if t['quoted_in_paren']),
        'avg_chars': round(sum(t['chars'] for t in turns) / float(n), 1),
        'avg_cn': round(sum(t['cn'] for t in turns) / float(n), 2),
        'truncated': sum(1 for t in turns if t['truncated']),
    }


def main():
    targets = ['susie', 'asgore']
    turns_n = 6
    roster, _gaps = C.load_roster()
    by_id = {r['id']: r for r in roster}
    idx = C.load_json(os.path.join(C.TRAIN_DIR, '_index.json'), {}) or {}
    patch_map = idx.get('patches') or {}

    # ★★★ 不要在这里 `C.warmup()`！
    #   它是按 NUM_CTX=**8192** 预热的，紧接着第一次 chat 用 **20480** ⇒ Ollama 要重载
    #   模型，请求会卡在"切实例"的窗口里**无限等**（实测挂了 24 分钟、CPU 0%、
    #   llama-server 空闲；换独立进程单发却 10s 就回 —— 因为没走 warmup）。
    #   这正是本项目"num_ctx 一变就重载 ⇒ 整场只用一个值"那条铁律。
    #   ⇒ 直接让第一次 chat 冷加载（约 40s），全程只出现 20480 一个值。
    print('不预热，第一次调用会冷加载模型（约 40s）…', flush=True)

    results = []
    for nid in targets:
        card = D.load_card(nid, by_id)
        patch = patch_map.get(nid, '') or ''
        base_sys = D.system_for(card, patch)
        # P2：人设去括号后重建（其余参数一致）
        card2 = dict(card)
        card2['_persona_text'] = strip_all_parens(card['_persona_text'])
        p2_sys = D.system_for(card2, patch)
        variants = [
            ('P0 base', base_sys),
            ('P1 rule', base_sys + '\n\n' + RULE_BLOCK),
            ('P2 persona', p2_sys),
            ('P3 both', p2_sys + '\n\n' + RULE_BLOCK),
        ]
        print('\n===== %s（patch %d 字 / 人设 %d 字 → 去括号 %d 字）====='
              % (nid, len(patch), len(card['_persona_text']),
                 len(card2['_persona_text'])), flush=True)
        for tag, system in variants:
            t0 = time.time()
            turns = run_variant(card, turns_n, system, tag)
            s = summarize(turns)
            s.update({'id': nid, 'variant': tag,
                      'cost_s': round(time.time() - t0, 1)})
            results.append({'summary': s, 'turns': turns})
            print('  %-11s 括号 %d/%d  含引号括号 %d  均长 %5.1f  中文 %.2f  %5.1fs%s'
                  % (tag, s['paren_turns'], s['turns'], s['quoted_turns'],
                     s['avg_chars'], s['avg_cn'], s['cost_s'],
                     ('  !! 失败 %d 轮：%s' % (s['errors'], s['error_sample']))
                     if s['errors'] else ''), flush=True)
            with io.open(OUT, 'a', encoding='utf-8') as f:
                f.write(json.dumps({'summary': s, 'turns': turns},
                                   ensure_ascii=False) + '\n')

    # ★★★ 夹具保真闸：全空/全错必须**报红退出**，不许静默产出「括号率 0.00」的假结论
    #    （第一版就是这样：`C.wait_for_memory` 写错模块 ⇒ 48 次调用全抛异常、
    #      被 except 吞掉，四个变体齐刷刷印出 0.00，看着像「大家都很好」）
    broken = [r['summary'] for r in results
              if r['summary']['errors'] or r['summary']['empty_turns'] == r['summary']['turns']]
    if broken:
        print('\n!! 夹具失效：%d 个变体有失败/空回复 —— 本次结论**作废**' % len(broken))
        for s in broken[:4]:
            print('   %s %s  errors=%d empty=%d  %s'
                  % (s['id'], s['variant'], s['errors'], s['empty_turns'],
                     s['error_sample']))
        return 2

    print('\n===== 汇总（括号率越低越好）=====')
    print('%-9s %-11s %-8s %-8s %-8s' % ('角色', '变体', '括号率', '均长', '中文'))
    for r in results:
        s = r['summary']
        print('%-9s %-11s %5.2f    %6.1f   %5.2f'
              % (s['id'], s['variant'], s['paren_rate'], s['avg_chars'], s['avg_cn']))
    print('\n明细：%s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
