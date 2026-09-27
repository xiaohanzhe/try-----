# -*- coding: utf-8 -*-
"""第57轮：Ollama 前缀（KV）缓存容量实测 —— 「多个 NPC 能不能同时"热"着」。

为什么必须测这个
----------------
`bench_ollama_concurrency.py` 测出：**冷 prefill 27.7 ms/token，命中缓存 0.06 ms/token**
（差 460 倍），而**并发数完全不影响单请求速率**（N=2..6 的 prefill 速率逐条吻合）
⇒ Ollama 在纯 CPU 上是**串行**处理请求的，所谓"并发"其实是排队。

于是真正决定"多个 NPC 同时活跃"体验的，不是 CPU 并行度，而是：
  **Ollama 到底能同时保留几个不同的 KV 前缀？**
    · 每个 NPC 的人设不同 ⇒ 前缀不同；
    · 若容量 ≥ NPC 数 ⇒ 每个 NPC 第二次开口都命中缓存（首字 ~0.3s）；
    · 若容量 < NPC 数 ⇒ 轮流说话时互相驱逐，**每个 NPC 每次开口都是冷 prefill（70~110s）**。

方法：顺时针把 N 个不同人设各发一次（第 1 轮，全冷），**再按同样顺序发一轮**（第 2 轮）。
      第 2 轮里出现"热"的条目，说明那个前缀被保住了；出现"冷"的，说明已被驱逐。
      由此直接读出容量（= 最后一个还能命中的下标 + 1）。

用法：
    python bench_prefix_cache.py --n 6 --rounds 2
"""
import argparse
import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bench_ollama_concurrency import (                                   # noqa: E402
    SPEAK_RULES, load_personas, _post_json)

#: 冷/热分界（ms/token）。实测冷 ≈ 27.7、热 ≈ 0.06~1.2 ⇒ 5.0 是安全的分界。
HOT_MS_PER_TOKEN = 5.0


def one(system, user_msg, model, num_predict):
    """同步发一次（非流式，只为拿全指标）。返回指标 dict。"""
    payload = {
        'model': model,
        'messages': [{'role': 'system', 'content': system},
                     {'role': 'user', 'content': user_msg}],
        'stream': False,
        'options': {'temperature': 0.85, 'num_predict': num_predict},
    }
    t0 = time.time()
    try:
        resp = _post_json('/api/chat', payload)
        obj = json.loads(resp.read().decode('utf-8'))
        resp.close()
    except Exception as e:                                               # noqa: BLE001
        return {'err': '%s: %s' % (type(e).__name__, e), 'wall': time.time() - t0}
    return {
        'wall': time.time() - t0,
        'pr_tok': obj.get('prompt_eval_count'),
        'pr_ns': obj.get('prompt_eval_duration'),
        'ev_tok': obj.get('eval_count'),
        'ev_ns': obj.get('eval_duration'),
        'load_ns': obj.get('load_duration'),
        'err': None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=6, help='用几个人设轮流')
    ap.add_argument('--rounds', type=int, default=2)
    ap.add_argument('--model', default='ralsei:v4')
    ap.add_argument('--num-predict', type=int, default=8,
                    help='只为看 prefill：解码越短越快，8 足够')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    personas = load_personas()[:args.n]
    if not personas:
        print('读不到人设')
        return 2
    print('人设 %d 份（%s）  模型 %s  num_predict=%d' % (
        len(personas), '、'.join(p[0] for p in personas), args.model,
        args.num_predict))
    print('%s' % ('=' * 78))
    print('%-4s %-8s %-20s %10s %12s %12s %8s' % (
        '轮', '人设', 'idx', 'pr_tok', 'pr_eval(s)', 'ms/token', '判定'))
    print('-' * 78)

    report = {'model': args.model, 'n': args.n, 'rounds': [], 'personas':
              [p[0] for p in personas]}
    for rd in range(args.rounds):
        rows = []
        for i, (name, persona) in enumerate(personas):
            system = persona.rstrip() + '\n\n' + SPEAK_RULES
            r = one(system, '你好呀，%s。' % name, args.model, args.num_predict)
            if r.get('err'):
                print('%-4d %-8s %-20s  失败：%s' % (rd + 1, name, i, r['err']))
                rows.append({'rd': rd + 1, 'name': name, 'idx': i, 'err': r['err']})
                continue
            pr_tok = r.get('pr_tok') or 0
            pr_s = (r.get('pr_ns') or 0) / 1e9
            mst = (r.get('pr_ns') or 0) / 1e6 / pr_tok if pr_tok else -1
            hot = 0 <= mst < HOT_MS_PER_TOKEN
            print('%-4d %-8s %-20d %10d %12.2f %12.3f %8s' % (
                rd + 1, name, i, pr_tok, pr_s, mst, '热(命中)' if hot else '冷(重算)'))
            rows.append({'rd': rd + 1, 'name': name, 'idx': i, 'pr_tok': pr_tok,
                         'pr_ns': r.get('pr_ns'), 'ms_per_token': mst,
                         'hot': hot, 'ev_tok': r.get('ev_tok'),
                         'wall': r.get('wall')})
        report['rounds'].append(rows)

    # ---- 容量判读：第 2 轮里"热"的最大下标 + 1 ----
    if len(report['rounds']) >= 2:
        r2 = report['rounds'][1]
        hot_idx = [x['idx'] for x in r2 if x.get('hot')]
        print('\n%s' % ('=' * 78))
        if hot_idx:
            print('第 2 轮命中缓存的：%s' % hot_idx)
            print('⇒ 前缀缓存容量 ≥ %d（保留住了第 %d 个不同前缀）'
                  % (len(hot_idx), max(hot_idx) + 1))
        else:
            print('第 2 轮一个都没命中 ⇒ 容量 < %d（每换一个人设就驱逐）' % args.n)
        lost = [x['idx'] for x in r2 if not x.get('hot')]
        if lost:
            print('  被驱逐的：%s（说明容量不是无限，超出即互相顶掉）' % lost)
    if args.out:
        with io.open(args.out, 'w', encoding='utf-8') as fh:
            fh.write(json.dumps(report, ensure_ascii=False, indent=1))
        print('\n结果已落盘：%s' % args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
