# -*- coding: utf-8 -*-
"""第141轮 · 排除假象：长句是不是被英文样本污染的？

`measure141.py` 跑出来「最长句 P90=83 / ≥60 字占 27.1%」，样本榜前四名全是
英文 NPC（hy_bowll 478 / ut_sans 401 / hy_dalv 394 / hy_guardener 370）。

**怀疑点**：切句尺 `END = '。！？!?\n'` **不含 ASCII `.`**（中文产品现状，是对的），
英文回复的句子根本切不开 ⇒ 整段算"一句" ⇒ 长句分布被英文样本顶高。

这份脚本干三件事：
  1. 按汉字占比把回复分三层（zh / mixed / en），分别重算三个指标
  2. 再跑一把"把 `.` 也当句末"的诊断切句器（**只用于归因，不进产品**），
     看英文样本的长句是否就此塌掉
  3. 中文层的分布单独落盘 —— 后面定阈值只能用这个数

判据：若 `en` 层最长句远高于 `zh` 层、且加 `.` 后 `en` 层塌到 zh 层水平，
则「长句」是切句口径的产物，不是"念说明"的形态。
"""
import glob
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
RAW = os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练',
                   '_evidence', 'raw30')

END_ZH = u'\u3002\uff01\uff1f!?\n'                    # 产品口径：不含 `.` / 不含 `…`
END_DIAG = u'\u3002\uff01\uff1f!?\n.'                 # 诊断口径：补 ASCII `.`
COMMAS = u'\uff0c\u3001,;；'


def split(text, ends):
    out, buf, has_word, started, in_end = [], [], False, False, False
    for ch in text:
        buf.append(ch)
        if ch in ends:
            if not in_end:
                if started and has_word:
                    out.append(u''.join(buf))
                    buf = []
                started = True
                in_end = True
                has_word = False
            continue
        in_end = False
        if not ch.isspace():
            has_word = True
    if buf and has_word:
        out.append(u''.join(buf))
    return out


def han_ratio(t):
    word = [ch for ch in t if not ch.isspace()]
    if not word:
        return 0.0
    han = sum(1 for ch in word if u'\u4e00' <= ch <= u'\u9fff')
    return float(han) / len(word)


def pct(vals, p):
    if not vals:
        return 0
    s = sorted(vals)
    return s[int(round((len(s) - 1) * p / 100.0))]


def stats(rows, ends):
    """→ dict：条数 / 最长句分位 / 占比分位 / 逗号链"""
    maxlen, ratios, chains = [], [], []
    for t in rows:
        ss = split(t, ends)
        if not ss:
            continue
        lens = [len(s) for s in ss]
        maxlen.append(max(lens))
        ratios.append(float(max(lens)) / max(1, len(t)))
        for s in ss:
            chains.append(sum(1 for ch in s if ch in COMMAS))
    if not maxlen:
        return None
    n = len(maxlen)
    return {
        'n': n,
        'max_sent': {'p50': pct(maxlen, 50), 'p90': pct(maxlen, 90),
                     'p95': pct(maxlen, 95), 'p99': pct(maxlen, 99),
                     'max': max(maxlen),
                     'ge60_pct': round(100.0 * sum(1 for v in maxlen if v >= 60) / n, 1),
                     'ge80_pct': round(100.0 * sum(1 for v in maxlen if v >= 80) / n, 1)},
        'ratio': {'p50': round(pct(ratios, 50), 2), 'p90': round(pct(ratios, 90), 2),
                  'ge80_pct': round(100.0 * sum(1 for r in ratios if r >= 0.8) / n, 1)},
        'comma': {'p90': pct(chains, 90), 'p99': pct(chains, 99), 'max': max(chains),
                  'ge3_pct': round(100.0 * sum(1 for c in chains if c >= 3) / max(1, len(chains)), 1)},
        'sent_total': len(chains),
    }


def show(tag, s):
    if not s:
        print(u'  %s：空集' % tag)
        return
    print(u'  %-6s n=%-5d 最长句 P50=%-4d P90=%-4d P95=%-4d P99=%-4d max=%-4d'
          u' | ≥60字 %.1f%% ≥80字 %.1f%% | 占比≥0.80 %.1f%% | 逗号≥3 %.1f%%'
          % (tag, s['n'], s['max_sent']['p50'], s['max_sent']['p90'],
             s['max_sent']['p95'], s['max_sent']['p99'], s['max_sent']['max'],
             s['max_sent']['ge60_pct'], s['max_sent']['ge80_pct'],
             s['ratio']['ge80_pct'], s['comma']['ge3_pct']))


def main():
    by_npc = {}
    for p in sorted(glob.glob(os.path.join(RAW, '*.jsonl'))):
        name = os.path.basename(p)[:-6]
        for line in io.open(p, encoding='utf-8', newline=''):
            if not line.strip():
                continue
            rec = json.loads(line)
            for turn in rec.get('turns') or []:
                t = (turn.get('final') or u'').strip()
                if t:
                    by_npc.setdefault(name, []).append(t)

    zh, mixed, en = [], [], []
    for rows in by_npc.values():
        for t in rows:
            r = han_ratio(t)
            (zh if r >= 0.5 else (en if r < 0.1 else mixed)).append(t)

    total = len(zh) + len(mixed) + len(en)
    print(u'语料：%d 条 / %d 个角色' % (total, len(by_npc)))
    print(u'按汉字占比分层：zh(≥0.50) %d(%.1f%%) · mixed(0.10~0.50) %d(%.1f%%) · en(<0.10) %d(%.1f%%)'
          % (len(zh), 100.0 * len(zh) / total, len(mixed), 100.0 * len(mixed) / total,
             len(en), 100.0 * len(en) / total))

    # 哪些角色贡献了 en 层
    en_by_npc = {}
    for name, rows in by_npc.items():
        c = sum(1 for t in rows if han_ratio(t) < 0.1)
        if c:
            en_by_npc[name] = c
    top_en = sorted(en_by_npc.items(), key=lambda kv: -kv[1])[:8]
    print(u'  en 层主要来自：%s' % u' · '.join(u'%s %d' % (k, v) for k, v in top_en))
    print(u'')

    print(u'--- 口径 A：产品现状（`END` 不含 `.`）---')
    a_all = stats(zh + mixed + en, END_ZH)
    a_zh = stats(zh, END_ZH)
    a_mx = stats(mixed, END_ZH)
    a_en = stats(en, END_ZH)
    show(u'全部', a_all)
    show(u'zh', a_zh)
    show(u'mixed', a_mx)
    show(u'en', a_en)
    print(u'')
    print(u'--- 口径 B：诊断（`END` 补 ASCII `.`，只用于归因）---')
    b_all = stats(zh + mixed + en, END_DIAG)
    b_zh = stats(zh, END_DIAG)
    b_mx = stats(mixed, END_DIAG)
    b_en = stats(en, END_DIAG)
    show(u'全部', b_all)
    show(u'zh', b_zh)
    show(u'mixed', b_mx)
    show(u'en', b_en)
    print(u'')

    # 三个自证：中文层在两种口径下应几乎不变（中文正文本来就不用 `.` 断句）
    print(u'--- 自证 ---')
    dz = (b_zh['max_sent']['p90'] - a_zh['max_sent']['p90']) if (a_zh and b_zh) else None
    de = (b_en['max_sent']['p90'] - a_en['max_sent']['p90']) if (a_en and b_en) else None
    print(u'  zh 层 P90 变化：%+d（应≈0，证明补 `.` 不动中文）' % dz)
    print(u'  en 层 P90 变化：%+d（应大幅为负，证明英文长句是切不开造成的）' % de)
    ok_pollution = (dz is not None and abs(dz) <= 6 and de is not None and de < -40
                    and a_en['max_sent']['p90'] > a_zh['max_sent']['p90'])
    print(u'  结论：长句是切句口径污染英文样本？%s' % (u'是（假象成立）' if ok_pollution else u'不是（需另找原因）'))

    # 中文层里 ≥60 字的样本，看看到底是什么形态
    samples = []
    for t in zh:
        for s in split(t, END_ZH):
            if len(s) >= 60:
                samples.append((len(s), sum(1 for ch in s if ch in COMMAS), s))
    print(u'')
    print(u'--- 中文层最长句 ≥60 字的样本（最多 10 条，按长度倒序）---')
    for ln, c, s in sorted(samples, reverse=True)[:10]:
        print(u'  [%d 字 / %d 逗号] %s' % (ln, c, s.replace(u'\n', u' ')[:86]))

    ev = {
        'corpus': {'total': total, 'npcs': len(by_npc),
                   'zh': len(zh), 'mixed': len(mixed), 'en': len(en),
                   'en_by_npc_top': dict(top_en)},
        'A_no_ascii_dot': {'all': a_all, 'zh': a_zh, 'mixed': a_mx, 'en': a_en},
        'B_with_ascii_dot': {'all': b_all, 'zh': b_zh, 'mixed': b_mx, 'en': b_en},
        'selfcheck': {'zh_p90_delta': dz, 'en_p90_delta': de,
                      'pollution': bool(ok_pollution)},
        'zh_samples_ge60': [{'chars': ln, 'commas': c, 'text': s}
                            for ln, c, s in sorted(samples, reverse=True)[:10]],
    }
    evd = os.path.join(ROUND, '_evidence')
    if not os.path.isdir(evd):
        os.makedirs(evd)
    out = os.path.join(evd, 'sentence_len141b_lang.json')
    with io.open(out, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(ev, ensure_ascii=False, indent=1))
    print(u'')
    print(u'已落盘：', out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
