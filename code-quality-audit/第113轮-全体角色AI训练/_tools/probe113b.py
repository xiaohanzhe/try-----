# -*- coding: utf-8 -*-
"""第113轮b · 单轮成本分解探针（为了把"每人 30 轮"的时间表算准）

## 为什么需要它
昨晚 baseline 实测 **154 秒/角色（4 轮）⇒ 38.5 秒/轮**，但账算不平：
  · 生成 `eval_count` 中位仅 **37 token**，6 tok/s ⇒ **约 6.2 秒**
  · `ttft` 中位 **1.31s** ⇒ prefill 明显有缓存命中（不是全量重算）
  ⇒ 一轮"应该"只要 7~8 秒，**剩下 30 秒去哪了？**
不把这一项查出来，就直接把 4 轮改成 30 轮，等于在一个未知瓶颈上乘 7.5 倍。

## 本探针量什么
同一进程内**连续**跑 N 轮（真正带上下文累积），逐轮打印：
  · `wait_mem_s`  内存闸等待了多少秒（怀疑主因）
  · `ttft_s`      首 token 延迟
  · `gen_s`       首 token 之后到结束（≈ eval_count / 吞吐）
  · `total_s`     该轮墙钟
  · `avail_mb`    发请求前可用内存
  · `eval_count` / `prompt_eval_count`
最后给出"每轮实测成本"与"77 人 × 30 轮"的预估。

用法：python probe113b.py [--turns 6] [--id susie]
"""
import json
import os
import sys
import time

import psutil

import common113 as C

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), '_evidence', 'cost_probe113b.json')


def main(argv):
    turns = int(argv[argv.index('--turns') + 1]) if '--turns' in argv else 6
    nid = argv[argv.index('--id') + 1] if '--id' in argv else 'susie'

    roster, _ = C.load_roster()
    by_id = {r['id']: r for r in roster}
    import dialogue113 as D
    card = D.load_card(nid, by_id)
    if card is None:
        print('!! 找不到训练卡：%s' % nid)
        return 2
    system = D.system_for(card, '')
    print('角色=%s system=%d 字' % (nid, len(system)))

    if not C.model_loaded():
        print('预热中（冷加载约 40s）…', flush=True)
        print('  =>', C.warmup())

    msgs = [{'role': 'system', 'content': system}]
    rows = []
    for i in range(1, turns + 1):
        user = D.script_for(card)[min(i - 1, 3)] if i <= 4 else '接着刚才的说吧，你还记得我前面问过你什么吗？'
        msgs.append({'role': 'user', 'content': user})

        avail = psutil.virtual_memory().available / 1e6
        t_wait0 = time.time()
        waited = D.wait_for_memory()
        t_wait = time.time() - t_wait0

        t0 = time.time()
        text, st = C.chat(msgs, seed=C.stable_seed(nid, 'probe', i, 0))
        total = time.time() - t0

        ttft = st.get('ttft_s') or 0.0
        gen = max(0.0, total - ttft)
        rows.append({'turn': i, 'avail_mb': round(avail, 0), 'wait_mem_s': round(t_wait, 1),
                     'ttft_s': round(ttft, 2), 'gen_s': round(gen, 1),
                     'total_s': round(total, 1),
                     'eval_count': st.get('eval_count'),
                     'prompt_eval_count': st.get('prompt_eval_count'),
                     'chars': len(text),
                     'truncated': bool(st.get('truncated'))})
        print('  第%2d轮  avail=%4.0fMB 等%4.1fs | ttft %5.2fs 生成 %5.1fs 合计 %5.1fs'
              ' | 出 %3s tok / prompt %5s tok / %3d 字%s'
              % (i, avail, t_wait, ttft, gen, total,
                 st.get('eval_count'), st.get('prompt_eval_count'), len(text),
                 '  ⚠️截断' if st.get('truncated') else ''), flush=True)

        msgs.append({'role': 'assistant', 'content': text})

    tot = sum(r['total_s'] + r['wait_mem_s'] for r in rows)
    per = tot / len(rows)
    gen_only = sum(r['gen_s'] for r in rows) / len(rows)
    wait_only = sum(r['wait_mem_s'] for r in rows) / len(rows)
    print()
    print('每轮实测：合计 %.1fs = 生成 %.1fs + 等待内存 %.1fs + 其它 %.1fs'
          % (per, gen_only, wait_only, per - gen_only - wait_only))
    print('77 人 × 30 轮 = 2310 轮 ⇒ 预估 %.1f 小时' % (per * 2310 / 3600))
    print('（若等待内存为 0 ⇒ 预估 %.1f 小时）' % ((per - wait_only) * 2310 / 3600))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    payload = {'npc': nid, 'turns': turns, 'rows': rows,
               'per_turn_s': round(per, 1), 'gen_s': round(gen_only, 1),
               'wait_mem_s': round(wait_only, 1),
               'est_hours_2310': round(per * 2310 / 3600, 1)}
    with open(OUT, 'w', encoding='utf-8', newline='') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print('落盘：%s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
