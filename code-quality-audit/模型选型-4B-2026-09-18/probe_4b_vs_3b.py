# -*- coding: utf-8 -*-
"""
模型选型探针（第十三轮）：ralsei:v2(3B) vs qwen3:4b-instruct-2507(4B) vs qwen2.5:7b-instruct(7B)

目的：回答"有没有一个底座，既不太慢、又比现在的 3B 更真实"。

设计上刻意避开上一轮（7B 评估）踩过的三个坑：
  1. 【缓存真假】每次测 TTFT 前先明确"这一发的前缀为什么算热"——
     本探针用「同一 system + 同一 user 连发」把前缀缓存打满，再量；
     另设「同一 system + 变 user」模拟真实 lean 请求（缓存只覆盖 system 段）。
     两种都报，不混为一谈。
  2. 【对照组次数/位置不一致】三模型走完全相同的流程：unload → 冷发 → 预热 → 计时。
     计时一律丢第 1 发、取后 N-1 发的中位数。
  3. 【只信计数】质量部分把原始回复整段落盘，计数只作索引，判定以原文为准。

走 Ollama 原生 /api/chat（只有它认 options.num_ctx / repeat_penalty），
参数与线上一致：temperature 0.85 / top_p 0.92 / repeat_penalty 1.15 /
num_ctx 8192 / num_predict 256。system 用线上真源 assets/ralsei_persona.md。
"""

import json
import os
import re
import statistics
import sys
import time
import urllib.request

HERE = os.path.abspath(os.path.dirname(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
PERSONA_PATH = os.path.join(REPO, 'ralsei_pet', 'assets', 'ralsei_persona.md')
OUT_PATH = os.path.join(HERE, 'probe_4b_vs_3b.txt')

HOST = 'http://localhost:11434'
OPTS = {'temperature': 0.85, 'top_p': 0.92, 'repeat_penalty': 1.15, 'num_ctx': 8192}
NUM_PREDICT = 256

# 候选池：4B 是"同量级但更新一代"的正解方向；7B 作为"更大但更慢"的参照点。
# 只有**本地已存在**的模型才会被跑 —— 缺失的（例如 CDN 拉不下来的 4B）
# 会打印一行 SKIP 而不是报错，保证同一份脚本在任何时候都能复现当时的环境。
MODELS = [
    ('ralsei:v2', '3B ralsei:v2', 4),
    ('qwen3:4b-instruct-2507-q4_K_M', '4B qwen3-4b-instruct-2507', 4),
    ('qwen2.5:7b-instruct', '7B qwen2.5-7b (参照)', 4),
]


def available_models():
    try:
        with urllib.request.urlopen(HOST + '/api/tags', timeout=20) as r:
            d = json.loads(r.read().decode('utf-8'))
        return set(m.get('name') for m in d.get('models', []))
    except Exception:
        return set()

# 质量测试输入：前三条是 persona 里的语气示范场景（专门测"照抄示范"），
# 其余是非脚本场景（测迁移能力）。
QUALITY_INPUTS = [
    ('q1', '今天上班好累啊，被领导骂了一顿', '示范场景·挫败'),
    ('q2', '我好喜欢你呀', '示范场景·表白'),
    ('q3', '今天吃了火锅', '示范场景·食物'),
    ('q4', '在吗', '极短输入'),
    ('q5', '我刚把碗摔碎了，好烦', '挫败·新场景'),
    ('q6', '你会不会有一天不想理我了', '情感试探'),
    ('q7', '给我讲讲黑暗世界的事吧', '世界观·测是否把用户卷进剧情'),
    ('q8', '我明天要去面试，有点紧张', '情绪+具体事'),
]

BANNED = ['你还好吗', '要不要休息一下', '我理解你的感受', '我明白你的心情',
          '作为AI', '作为一个语言模型', '有什么可以帮你的', '希望这些能帮到你',
          '让我们一起', '作为人工智能',
          # —— 第一轮运行后补的「变体」（第一轮用旧判据跑出 3B 1/8、7B 4/8，
          #    但人工读原文发现「有什么我可以帮忙的吗」「我都能感受到你的疲惫了」
          #    这类助手/咨询腔其实没被抓住 —— 判据必须覆盖变体，否则计数误导人）——
          '有什么我可以帮忙', '有什么我能帮', '需要我帮忙', '需要我帮', '我可以帮你',
          '我能感受到你的', '我感受到你的', '我能理解你的', '希望你能知道有我在',
          '我在心里给你加油']

# 形状判据（第一轮实测：persona 明写"一次 1~3 句"，两个模型都出现 4~9 句 / 84~161 字）
SENT_MAX = 3            # 超过就算"小作文"
CJK_MAX = 64            # 对话链路上限 80 字，事件链路 24 字；取 64 作"明显过长"线

DEMO_LINES = []


def load_persona():
    with open(PERSONA_PATH, 'r', encoding='utf-8') as f:
        return f.read()


def extract_demo_lines(persona):
    """抽出 persona「语气示范」里的『我：』台词，用于检测整句搬运。"""
    out = []
    for line in persona.splitlines():
        s = line.strip()
        if s.startswith('我：'):
            out.append(s[2:].strip())
    return out


def _post(path, payload, timeout=300):
    req = urllib.request.Request(
        HOST + path,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
    )
    return urllib.request.urlopen(req, timeout=timeout)


def unload(model):
    try:
        _post('/api/chat', {'model': model, 'messages': [], 'keep_alive': 0}).read()
    except Exception:
        pass
    time.sleep(1.0)


def chat_once(model, system, user, num_predict=NUM_PREDICT, opts=None):
    """发一发流式请求，返回 (ttft, total, text, final_dict)。"""
    o = dict(OPTS if opts is None else opts)
    o['num_predict'] = num_predict
    payload = {
        'model': model,
        'messages': [{'role': 'system', 'content': system},
                     {'role': 'user', 'content': user}],
        'stream': True,
        'options': o,
    }
    t0 = time.perf_counter()
    ttft = None
    text = ''
    final = {}
    resp = _post('/api/chat', payload)
    for raw in resp:
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
                ttft = time.perf_counter() - t0
            text += piece
        if d.get('done'):
            final = d
    total = time.perf_counter() - t0
    return ttft, total, text, final


def model_meta(model):
    try:
        with _post('/api/show', {'model': model}) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        return {'error': str(e)}


# ---------------- 质量评分（计数只做索引，原文整段落盘） ----------------

def cjk_len(s):
    return len(re.findall(r'[\u4e00-\u9fff]', s))


def sent_count(s):
    return len([x for x in re.split(r'[。！？…]+', s) if x.strip()])


def copy_len(reply, demos):
    """回复里与任一示范台词重合的最长连续片段长度（10 字滑窗命中即算）。"""
    best = 0
    for d in demos:
        dl = re.sub(r'\s+', '', d)
        rl = re.sub(r'\s+', '', reply)
        for i in range(0, max(0, len(dl) - 9)):
            seg = dl[i:i + 10]
            if seg and seg in rl:
                # 向右扩展
                n = 10
                while i + n < len(dl) and dl[i:i + n + 1] in rl:
                    n += 1
                best = max(best, n)
    return best


def scan_issues(reply, demos):
    issues = []
    for b in BANNED:
        if b in reply:
            issues.append('套话:' + b)
    cl = copy_len(reply, demos)
    if cl >= 10:
        issues.append('照抄示范%d字' % cl)
    md = re.findall(r'[*#`]', reply)
    if md:
        issues.append('markdown残渣%s' % ''.join(sorted(set(md))))
    if 'Kris' in reply or '克瑞斯' in reply:
        issues.append('提到Kris')
    if reply.count('……') > 1:
        issues.append('省略号%d处' % reply.count('……'))
    # 滑字/异常字符：非 CJK/ASCII/常见标点的字符
    weird = re.findall(r'[^\u4e00-\u9fffA-Za-z0-9\s，。！？、：；""''《》（）…—～·\.\,\!\?\:\;\"\'\(\)\-]', reply)
    if weird:
        issues.append('异常字符%s' % ''.join(sorted(set(weird))[:5]))
    if sent_count(reply) > SENT_MAX:
        issues.append('句数%d>%d' % (sent_count(reply), SENT_MAX))
    if cjk_len(reply) > CJK_MAX:
        issues.append('过长%d字' % cjk_len(reply))
    return issues


def main():
    persona = load_persona()
    demos = extract_demo_lines(persona)
    have = available_models()
    plan = []
    L = []
    L.append('模型选型探针（第十三轮）  %s' % time.strftime('%Y-%m-%d %H:%M:%S'))
    L.append('')
    L.append('persona = assets/ralsei_persona.md (%d 字)' % len(persona))
    L.append('示范台词 %d 条，用于检测整句搬运' % len(demos))
    for d in demos:
        L.append('   · %s' % d)
    L.append('参数：temperature 0.85 / top_p 0.92 / repeat_penalty 1.15 / num_ctx 8192 / num_predict 256')
    L.append('')
    L.append('本地已有模型：%s' % ', '.join(sorted(have)) if have else '（读不到 /api/tags）')
    for m, label, reps in MODELS:
        if have and m not in have:
            L.append('SKIP %-34s （本地不存在，未拉取成功）' % m)
            continue
        plan.append((m, label, reps))
    L.append('=' * 72)

    results = {}
    for model, label, repeats in plan:
        L.append('')
        L.append('#' * 72)
        L.append('## %s   (%s)' % (label, model))
        L.append('#' * 72)

        meta = model_meta(model)
        size = (meta.get('details') or {}).get('parameter_size')
        quant = (meta.get('details') or {}).get('quantization_level')
        L.append('parameter_size=%s  quantization=%s' % (size, quant))

        # ---- 延迟 ----
        unload(model)
        t0 = time.perf_counter()
        ttft, total, txt, fin = chat_once(model, persona, '你好呀')
        cold_load = total
        cold_ttft = ttft
        cold_pe = fin.get('prompt_eval_count') or 0
        cold_ped = (fin.get('prompt_eval_duration') or 0) / 1e9
        cold_pps = (cold_pe / cold_ped) if cold_ped > 0 else 0
        L.append('冷发：整句 %.0f ms / 首字 %s ms / prompt_eval=%s eval=%s' % (
            cold_load * 1000,
            '%.0f' % (cold_ttft * 1000) if cold_ttft else 'n/a',
            fin.get('prompt_eval_count'), fin.get('eval_count')))
        L.append('冷 prefill：%d token / %.0f tok/s（**未命中缓存**，这才是真 prefill 速度）'
                 % (cold_pe, cold_pps))

        # 预热（把 persona 这段 system 的前缀缓存打满）
        chat_once(model, persona, '预热一下')
        chat_once(model, persona, '再预热一下')

        # W1：同 system + 同 user（缓存效益上界）
        w1 = []
        for _ in range(repeats):
            ttft, total, txt, fin = chat_once(model, persona, '今天过得怎么样？')
            w1.append((ttft, total, fin))
        # 丢第 1 发
        w1s = w1[1:] if len(w1) > 1 else w1
        med_ttft1 = statistics.median([x[0] for x in w1s])
        med_tot1 = statistics.median([x[1] for x in w1s])

        # W2：同 system + 变 user（贴近真实 lean 请求：只有 system 段命中缓存）
        w2 = []
        for i, u in enumerate(['今天天气不错', '我有点困了', '刚才看了个视频', '外面在下雨']):
            ttft, total, txt, fin = chat_once(model, persona, u)
            w2.append((ttft, total, fin))
        w2s = w2[1:] if len(w2) > 1 else w2
        med_ttft2 = statistics.median([x[0] for x in w2s])
        med_tot2 = statistics.median([x[1] for x in w2s])

        f = w1s[-1][2]
        ev = f.get('eval_count') or 0
        evd = (f.get('eval_duration') or 1) / 1e9
        pe = f.get('prompt_eval_count') or 0
        ped = (f.get('prompt_eval_duration') or 1) / 1e9
        tps = ev / evd if evd > 0 else 0
        pps = pe / ped if ped > 0 else 0

        L.append('W1 同system同user  首字中位 %.0f ms / 整句中位 %.0f ms  (n=%d, 丢第1发)'
                 % (med_ttft1 * 1000, med_tot1 * 1000, len(w1s)))
        L.append('W2 同system变user  首字中位 %.0f ms / 整句中位 %.0f ms  (n=%d, 丢第1发)'
                 % (med_ttft2 * 1000, med_tot2 * 1000, len(w2s)))
        L.append('W2 decode %.2f tok/s   **W2 的 prefill=%.0f tok/s 无意义**：'
                 '前缀缓存命中时 prompt_eval 只剩几个 token，分母≈0 → 数字虚高。'
                 '真 prefill 看上面的「冷 prefill」。' % (tps, pps))

        results[model] = dict(label=label, size=size, quant=quant,
                              cold_load=cold_load * 1000,
                              cold_ttft=(cold_ttft * 1000) if cold_ttft else None,
                              cold_pps=cold_pps, cold_pe=cold_pe,
                              ttft_same=med_ttft1 * 1000, tot_same=med_tot1 * 1000,
                              ttft_vary=med_ttft2 * 1000, tot_vary=med_tot2 * 1000,
                              tps=tps, pps=pps)

        # ---- 质量 ----
        L.append('')
        L.append('--- 质量（同一 persona，temperature 0.85，每条独立、不带历史）---')
        L.append('')
        qrows = []
        prev = None
        for qid, user, tag in QUALITY_INPUTS:
            ttft, total, txt, fin = chat_once(model, persona, user)
            rep = txt.strip()
            issues = scan_issues(rep, demos)
            if prev is not None and rep and rep == prev:
                issues.append('与上条完全重复')
            prev = rep
            qrows.append((qid, tag, user, rep, issues, total))
            L.append('[%s] %s  —— 主人：%s' % (qid, tag, user))
            L.append('    Ralsei：%s' % rep)
            L.append('    字数=%d 句数=%d 耗时=%.0fms  问题=%s'
                     % (cjk_len(rep), sent_count(rep), total * 1000,
                        ('；'.join(issues) if issues else '无')))
            L.append('')

        results[model]['quality'] = qrows

    # ---------------- 汇总 ----------------
    L.append('')
    L.append('=' * 72)
    L.append('## 汇总')
    L.append('')
    hdr = '| 指标 | 3B ralsei:v2 | 4B qwen3-2507 | 7B qwen2.5 |'
    L.append(hdr)
    L.append('|---|---|---|---|')
    a = results.get('ralsei:v2', {})
    b = results.get('qwen3:4b-instruct-2507-q4_K_M', {})
    c = results.get('qwen2.5:7b-instruct', {})

    def g(d, k, fmt='%.0f'):
        v = d.get(k)
        return (fmt % v) if isinstance(v, (int, float)) else 'n/a'

    L.append('| 参数量 | %s | %s | %s |' % (a.get('size'), b.get('size'), c.get('size')))
    L.append('| 冷加载 ms | %s | %s | %s |' % (g(a, 'cold_load'), g(b, 'cold_load'), g(c, 'cold_load')))
    L.append('| 冷首字 ms | %s | %s | %s |' % (g(a, 'cold_ttft'), g(b, 'cold_ttft'), g(c, 'cold_ttft')))
    L.append('| 首字 同system同user ms | %s | %s | %s |' % (g(a, 'ttft_same'), g(b, 'ttft_same'), g(c, 'ttft_same')))
    L.append('| 首字 同system变user ms | %s | %s | %s |' % (g(a, 'ttft_vary'), g(b, 'ttft_vary'), g(c, 'ttft_vary')))
    L.append('| 整句 同system变user ms | %s | %s | %s |' % (g(a, 'tot_vary'), g(b, 'tot_vary'), g(c, 'tot_vary')))
    L.append('| decode tok/s | %s | %s | %s |' % (g(a, 'tps', '%.2f'), g(b, 'tps', '%.2f'), g(c, 'tps', '%.2f')))
    L.append('| 冷 prefill tok/s（缓存未命中） | %s | %s | %s |'
             % (g(a, 'cold_pps', '%.0f'), g(b, 'cold_pps', '%.0f'), g(c, 'cold_pps', '%.0f')))
    L.append('')
    L.append('（W2 的 prefill tok/s 不列：缓存命中时分母≈0，数字虚高无意义。）')

    L.append('')
    L.append('### 质量问题汇总（8 条输入）')
    L.append('')
    L.append('| 模型 | 命中问题的条目数 | 平均字数 | 平均耗时 ms |')
    L.append('|---|---|---|---|')
    for m, _lbl, _r in plan:
        qs = results.get(m, {}).get('quality') or []
        if not qs:
            continue
        bad = sum(1 for x in qs if x[4])
        avgch = sum(cjk_len(x[3]) for x in qs) / len(qs)
        avgt = sum(x[5] for x in qs) / len(qs) * 1000
        L.append('| %s | %d/8 | %.1f | %.0f |' % (results[m]['label'], bad, avgch, avgt))

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')
    print('WROTE ' + OUT_PATH)


if __name__ == '__main__':
    main()
