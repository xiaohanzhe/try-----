# -*- coding: utf-8 -*-
"""第113轮g 探针：括号旁白 —— 重做 A/B，把上一版被污染的「角色正例」拆开。

背景
----
`probe_paren113f.py` 的 `RULE_BLOCK` 里塞了一条 **susie 口吻**的正例
「烦死了。你别这么盯着我看，我又不会跑。」，却用在所有角色身上。
asgore 是温和的花店老板 ⇒ 成了唯一「加了规则反而更糟」的角色（1/6 → 6/6）。
⇒ 上一版「规则无效」的结论**不成立**：是夹具让 A 组背了不属于它的因果。

本版把两个假说分开测：
  H1  例子本身有害 —— 任何例句都会被当成「格式样本」去模仿
  H2  例子的**角色口吻**与目标角色冲突才坏事

三个变体（同一批角色、逐轮同 seed ⇒ 变体间可比）
  P0  base             现状 prompt
  P1P principle        只讲原则；**零例句，且全文不出现「括号」二字**
  P1N principle+neutral 同 P1P，但加一条**中性正例**「嗯。我明白了。」（不带任何角色口吻）

判读
  P1N ≈ P1P            ⇒ H2：是口吻冲突的锅，规则本身可用
  P1N ≈ P0 且 P1P 变好 ⇒ H1：例句本身有害，规则里一律不许放例子
  P1P ≈ P0             ⇒ 纯原则规则**没用**，才轮到「动人设」这条路

为什么「不提括号」：上一版的规则里「括号」出现两次，若模型把词面复述当格式提示，
就分不清是「规则没用」还是「规则在反向示范」—— 这也是要一起排除的干扰项。

每个变体跑 10 轮连续对话（多轮必要：模型会抄自己上一轮的写法，单轮测不出来）。
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

# ★ 独立输出文件（教训：负控制/其他脚本写入会污染同一份产物）
OUT = os.path.join(HERE, '..', '_evidence', 'probe_paren113g.jsonl')

TARGETS = ['susie', 'asgore', 'toriel']
TURNS_N = 10

# 原则块：只说"写什么"，不举例、不提"括号"
PRINCIPLE = (
    "【只写你说出口的那一行】\n"
    "玩家在对话框里看到的字，就是你说出口的台词，不是旁白、不是小说。\n"
    "不要写动作、表情、心理活动，也不要写从外面看自己的句子（比如描述自己的神态）。\n"
    "想说语气，就靠用词和标点本身。\n"
)

# 中性正例：不带任何角色口吻，用来区分 H1 / H2
NEUTRAL_EXAMPLE = "例如：嗯。我明白了。\n"

# 上一版那条被污染的正例（保留在此仅作对照说明，**不进入任何变体**）
POLLUTED_EXAMPLE = "烦死了。你别这么盯着我看，我又不会跑。"


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
        seed = C.stable_seed(card['id'], 'probe113g', i, 0)   # ★ 变体间同 seed
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
    roster, _gaps = C.load_roster()
    by_id = {r['id']: r for r in roster}
    idx = C.load_json(os.path.join(C.TRAIN_DIR, '_index.json'), {}) or {}
    patch_map = idx.get('patches') or {}

    # ★★★ 不要在这里 `C.warmup()`！
    #   它是按 NUM_CTX=**8192** 预热的，紧接着第一次 chat 用 **20480** ⇒ Ollama 要重载
    #   模型，请求会卡在"切实例"的窗口里**无限等**（第113轮f 实测挂了 24 分钟、CPU 0%）。
    #   ⇒ 直接让第一次 chat 冷加载（约 40s），全程只出现 20480 一个值。
    print('不预热，第一次调用会冷加载模型（约 40s）…', flush=True)
    print('本版已弃用的污染正例：%r' % POLLUTED_EXAMPLE, flush=True)

    results = []
    for nid in TARGETS:
        card = D.load_card(nid, by_id)
        patch = patch_map.get(nid, '') or ''
        base_sys = D.system_for(card, patch)
        variants = [
            ('P0 base', base_sys),
            ('P1P principle', base_sys + '\n\n' + PRINCIPLE),
            ('P1N neutral', base_sys + '\n\n' + PRINCIPLE + NEUTRAL_EXAMPLE),
        ]
        print('\n===== %s（人设 %d 字 / patch %d 字）====='
              % (nid, len(card['_persona_text']), len(patch)), flush=True)
        for tag, system in variants:
            t0 = time.time()
            turns = run_variant(card, TURNS_N, system, tag)
            s = summarize(turns)
            s.update({'id': nid, 'variant': tag,
                      'cost_s': round(time.time() - t0, 1)})
            results.append({'summary': s, 'turns': turns})
            print('  %-14s 括号 %d/%d  含引号 %d  均长 %5.1f  中文 %.2f  %5.1fs%s'
                  % (tag, s['paren_turns'], s['turns'], s['quoted_turns'],
                     s['avg_chars'], s['avg_cn'], s['cost_s'],
                     ('  !! 失败 %d 轮：%s' % (s['errors'], s['error_sample']))
                     if s['errors'] else ''), flush=True)
            with io.open(OUT, 'a', encoding='utf-8') as f:
                f.write(json.dumps({'summary': s, 'turns': turns},
                                   ensure_ascii=False) + '\n')

    # ★★★ 夹具保真闸：全空/全错必须**报红退出**，不许静默产出「括号率 0.00」的假结论
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
    print('%-9s %-15s %-7s %-7s %-7s %s'
          % ('角色', '变体', '括号率', '含引号', '均长', '中文'))
    for r in results:
        s = r['summary']
        print('%-9s %-15s %5.2f   %5.2f   %6.1f   %5.2f'
              % (s['id'], s['variant'], s['paren_rate'],
                 s['quoted_turns'] / float(s['turns']), s['avg_chars'], s['avg_cn']))

    # 按角色汇总三档（判读 H1 / H2）
    print('\n===== 按变体汇总（3 角色 × %d 轮）=====' % TURNS_N)
    agg = {}
    for r in results:
        s = r['summary']
        a = agg.setdefault(s['variant'], [0, 0, 0, 0.0])
        a[0] += s['paren_turns']
        a[1] += s['turns']
        a[2] += s['quoted_turns']
        a[3] += s['avg_chars']
    for tag in ('P0 base', 'P1P principle', 'P1N neutral'):
        if tag in agg:
            p, n, q, ch = agg[tag]
            print('  %-15s 括号 %3d/%3d = %.2f   含引号 %2d   均长 %5.1f'
                  % (tag, p, n, p / float(n), q, ch / 3.0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
