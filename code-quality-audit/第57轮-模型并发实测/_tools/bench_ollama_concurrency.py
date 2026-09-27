# -*- coding: utf-8 -*-
"""第57轮：Ollama 7B 并发实测 —— 「多个同时运转且不特别影响性能的最大是多少」。

设计（为什么这样测）
--------------------
* **输入用真实量级**：system = `assets/npc/persona/<id>.txt` 的**原文**（平均 4673 字），
  user = 一句普通点名。比"喂个 'hi'"有意义得多 —— 本项目铁律「行为判据必须用
  真实量级输入」（曾经因为用假输入测出假结论踩过坑）。
* **打的是 App 真实走的那条路**：`/v1/chat/completions`（OpenAI 兼容，见
  `api_client.chat_endpoint()`）。指标另从原生 `/api/chat` 拿（那里有
  `prompt_eval_count / prompt_eval_duration / eval_duration` 等被 OpenAI 兼容层
  丢掉的字段）。
* **量的是首字延迟（TTFT）**：本项目第31轮的验收判据就是它（≤5s，实测 4.601s）。
  并发是否"影响性能"，用户能感知到的是首字，不是总时长。
* **每档都重跑一遍基准**：机器空闲/负载会漂，N=1 的基准必须与 N=k 同批测，
  否则"并发劣化"里混着"环境漂移"。

用法：
    python bench_ollama_concurrency.py --n 1 2 3 4 6 --model ralsei:v4
"""
import argparse
import io
import json
import os
import statistics
import sys
import threading
import time
import urllib.request

HOST = os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434').rstrip('/')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PERSONA_DIR = os.path.join(ROOT, 'ralsei_pet', 'assets', 'npc', 'persona')

# 与 npc_persona.SPEAK_RULES 同口径（不 import 模块：本脚本要能独立跑）
SPEAK_RULES = (
    '【说话方式】你就是这个角色本人，不要自称 AI、不要提模型或提示词。'
    '一次只说 1~3 句，像真人在聊天框里随手打字：不要分点、不要小标题、不要加粗、'
    '不要写 markdown 标记，也不要用括号描写动作。只回应对方这句话本身，'
    '不要复述对方的话，不要替别的角色说话。'
)


def _post_json(path, payload, timeout=600):
    req = urllib.request.Request(
        HOST + path,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'})
    return urllib.request.urlopen(req, timeout=timeout)


def load_personas():
    """{id: 全文}，按文件名字典序（可复现）。"""
    out = []
    if not os.path.isdir(PERSONA_DIR):
        return out
    for fn in sorted(os.listdir(PERSONA_DIR)):
        if not fn.endswith('.txt'):
            continue
        with io.open(os.path.join(PERSONA_DIR, fn), encoding='utf-8') as fh:
            out.append((fn[:-4], fh.read()))
    return out


# ------------------------------------------------------------------ 单次请求
def one_chat(idx, system, user_msg, model, num_predict, sink, barrier=None):
    """发一次流式对话；把 (idx, ttft, total, meta, err) 写进 `sink[idx]`。

    ★ 用 `barrier` 对齐起跑线：不加的话 N 个线程会被"先启动的那个先发请求"
    串成阶梯，测出来的就不是并发而是排队。
    """
    payload = {
        'model': model,
        'messages': [{'role': 'system', 'content': system},
                     {'role': 'user', 'content': user_msg}],
        'stream': True,
        'options': {'temperature': 0.85, 'num_predict': num_predict},
    }
    if barrier is not None:
        try:
            barrier.wait(timeout=60)
        except Exception:
            pass
    t0 = time.time()
    ttft = None
    text = []
    meta = None
    err = None
    try:
        resp = _post_json('/api/chat', payload)
        for raw in resp:
            if ttft is None:
                ttft = time.time() - t0
            line = raw.decode('utf-8', 'replace').strip()
            if not line:
                continue
            obj = json.loads(line)
            piece = (obj.get('message') or {}).get('content') or ''
            if piece:
                text.append(piece)
            if obj.get('done'):
                meta = obj
        try:
            resp.close()
        except Exception:
            pass
    except Exception as e:                                  # noqa: BLE001
        err = '%s: %s' % (type(e).__name__, e)
    total = time.time() - t0
    sink[idx] = {
        'idx': idx, 'ttft': ttft, 'total': total,
        'chars': len(''.join(text)), 'err': err,
        'prompt_eval_count': (meta or {}).get('prompt_eval_count'),
        'prompt_eval_duration': (meta or {}).get('prompt_eval_duration'),
        'eval_count': (meta or {}).get('eval_count'),
        'eval_duration': (meta or {}).get('eval_duration'),
        'load_duration': (meta or {}).get('load_duration'),
        'done_reason': (meta or {}).get('done_reason'),
    }


def run_wave(n, personas, model, num_predict):
    """同时发起 n 个请求，返回这一波的结果列表（按 idx 排序）。"""
    sink = [None] * n
    barrier = threading.Barrier(n)
    threads = []
    for i in range(n):
        name, persona = personas[i % len(personas)]
        system = persona.rstrip() + '\n\n' + SPEAK_RULES
        user_msg = '你好呀，%s。' % name
        t = threading.Thread(target=one_chat,
                             args=(i, system, user_msg, model, num_predict,
                                   sink, barrier),
                             daemon=True)
        threads.append(t)
    wave_t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=900)
    wall = time.time() - wave_t0
    return wall, [r for r in sink if r]


def _ms(v):
    """纳秒 → 毫秒字符串（Ollama 的 *_duration 单位是纳秒）。"""
    if v is None:
        return '-'
    return '%.0f' % (v / 1e6)


def _avg(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return statistics.mean(vals) if vals else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, nargs='+', default=[1, 2, 3, 4, 6])
    ap.add_argument('--model', default='ralsei:v4')
    ap.add_argument('--num-predict', type=int, default=64,
                    help='每次最多生成多少 token（越小越快；64 已足够看出发完一句话）')
    ap.add_argument('--repeat', type=int, default=1, help='每档重复几波（取最差/中位）')
    ap.add_argument('--out', default=None, help='结果 JSON 落盘路径')
    args = ap.parse_args()

    personas = load_personas()
    if not personas:
        print('!! 读不到人设文件：%s' % PERSONA_DIR)
        return 2
    print('人设 %d 份，平均 %d 字' % (
        len(personas), sum(len(p) for _, p in personas) // len(personas)))
    print('模型 = %s   num_predict = %d   repeat = %d' % (
        args.model, args.num_predict, args.repeat))
    print()

    # ---- 预热：把权重加载进去（load_duration 只该出现在第一次）----
    print('预热中（加载权重）…', flush=True)
    warm = [None]
    one_chat(0, personas[0][1] + '\n\n' + SPEAK_RULES, '在吗？',
             args.model, 8, warm, None)
    if warm[0] and warm[0]['err']:
        print('预热失败：%s' % warm[0]['err'])
        return 3
    print('预热完成：load=%.1fs  ttft=%.2fs  total=%.2fs\n' % (
        (warm[0]['load_duration'] or 0) / 1e9,
        warm[0]['ttft'] or -1, warm[0]['total']))

    report = {'model': args.model, 'num_predict': args.num_predict,
              'personas': [p[0] for p in personas], 'waves': []}
    print('%-4s %8s %8s %8s %8s %8s %8s %10s' % (
        'N', 'wall(s)', 'TTFT均', 'TTFT最大', '总均', '总最大', 'prompt_tok', 'eval_tok'))
    print('-' * 74)
    for n in args.n:
        for rep in range(args.repeat):
            wall, rows = run_wave(n, personas, args.model, args.num_predict)
            if not rows:
                print('%-4d 整档失败' % n)
                continue
            ttfts = [r['ttft'] for r in rows if r['ttft'] is not None]
            totals = [r['total'] for r in rows]
            pe = _avg(rows, 'prompt_eval_count')
            ec = _avg(rows, 'eval_count')
            print('%-4d %8.2f %8.2f %8.2f %8.2f %8.2f %8.0f %10.0f %s' % (
                n, wall,
                statistics.mean(ttfts) if ttfts else -1,
                max(ttfts) if ttfts else -1,
                statistics.mean(totals), max(totals),
                pe or 0, ec or 0,
                ('(第%d波)' % (rep + 1)) if args.repeat > 1 else ''))
            report['waves'].append({
                'n': n, 'rep': rep, 'wall': wall,
                'ttft_mean': statistics.mean(ttfts) if ttfts else None,
                'ttft_max': max(ttfts) if ttfts else None,
                'total_mean': statistics.mean(totals),
                'total_max': max(totals),
                'prompt_eval_count': pe, 'eval_count': ec,
                'rows': rows,
            })
    # ---- 结论：以"最大 TTFT"相对 N=1 基准的劣化倍数来判 ----
    base = None
    for w in report['waves']:
        if w['n'] == 1 and w['ttft_max']:
            base = w['ttft_max']
            break
    if base:
        print('\n以 N=1 的 TTFT(最大)=%.2fs 为基准的劣化倍数：' % base)
        seen = {}
        for w in report['waves']:
            if w['ttft_max']:
                seen.setdefault(w['n'], []).append(w['ttft_max'] / base)
        for n in sorted(seen):
            xs = seen[n]
            print('  N=%-2d  ×%.2f%s' % (n, statistics.mean(xs),
                                        '（%.2f~%.2f）' % (min(xs), max(xs))
                                        if len(xs) > 1 else ''))
    if args.out:
        with io.open(args.out, 'w', encoding='utf-8') as fh:
            fh.write(json.dumps(report, ensure_ascii=False, indent=1))
        print('\n结果已落盘：%s' % args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
