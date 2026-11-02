# -*- coding: utf-8 -*-
"""第141轮 · 第三问：`……` 是不是被当逗号在用？

`measure141b` 排除了英文污染后，中文层最长句还是出现 186 字一条，形态是：
    oh…… 松下来的那种氛围就是我空间站里那些星尘蜗牛慢爬行的声音吧……
    还有那首 Spooktune 轻柔地播放着…… 那种宁静而美好的感觉让我不由自主放松下来。
⇒ 不是一个真长句，是 **`…` 当连接符串起来的碎句**。

这正好撞上人设第 57 行的原话：「句子说一半停住、用省略号让声音软下来：
**很少用，别拿它当句号**」。

本脚本量四件事（全语料 + 中文层 + ralsei 单列）：
  1. 每条回复里的「省略号记号」个数（连续 `…` / `...` 记 1 个）
  2. 每 100 字的省略号密度
  3. **连接符形态**：`…` 后面紧跟的是汉字/字母（不是标点、不是空白）
     —— 这就是"拿它当逗号"，与"拿它当句号"是两件事
  4. 次数 ≥3 / ≥5 的回复占比（"很少用"该落在哪）

口径：`…`（U+2026）连写、以及 ASCII `...` / `..` 都算一个记号。
"""
import glob
import io
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
RAW = os.path.join(ROOT, 'code-quality-audit', '第113轮-全体角色AI训练',
                   '_evidence', 'raw30')

MARK = re.compile(u'\u2026{1,}|\\.{2,}')
# 记号后面第一个非空白字符：是"字"就说明被当连接符，不是句末
STRONG_END = u'\u3002\uff01\uff1f!?\n'


def marks(t):
    return [m.group(0) for m in MARK.finditer(t)]


def is_connector(t, end_pos):
    """`…` 结束后第一个非空白字符是不是"话还在继续"""
    for ch in t[end_pos:]:
        if ch.isspace():
            continue
        return not (ch in STRONG_END)
    return False


def han_ratio(t):
    word = [ch for ch in t if not ch.isspace()]
    if not word:
        return 0.0
    return float(sum(1 for ch in word if u'\u4e00' <= ch <= u'\u9fff')) / len(word)


def pct(vals, p):
    if not vals:
        return 0
    s = sorted(vals)
    return s[int(round((len(s) - 1) * p / 100.0))]


def summarise(rows, label):
    """rows: [(npc, text)] → dict"""
    cnt, dens, conn_rate = [], [], []
    conn_tot = 0
    mark_tot = 0
    for _npc, t in rows:
        ms = marks(t)
        cnt.append(len(ms))
        dens.append(100.0 * len(ms) / max(1, len(t)))
        mark_tot += len(ms)
        if ms:
            c = 0
            for m in MARK.finditer(t):
                if is_connector(t, m.end()):
                    c += 1
            conn_tot += c
            conn_rate.append(float(c) / len(ms))
    n = len(cnt)
    if not n:
        return None
    s = {
        'n': n, 'marks': mark_tot,
        'per_reply': {'p50': pct(cnt, 50), 'p90': pct(cnt, 90),
                      'p99': pct(cnt, 99), 'max': max(cnt),
                      'ge1_pct': round(100.0 * sum(1 for v in cnt if v >= 1) / n, 1),
                      'ge3_pct': round(100.0 * sum(1 for v in cnt if v >= 3) / n, 1),
                      'ge5_pct': round(100.0 * sum(1 for v in cnt if v >= 5) / n, 1)},
        'density_per100': {'p50': round(pct(dens, 50), 2), 'p90': round(pct(dens, 90), 2),
                           'max': round(max(dens), 2)},
        'connector': {'marks': mark_tot, 'as_connector': conn_tot,
                      'rate_pct': round(100.0 * conn_tot / max(1, mark_tot), 1)},
    }
    print(u'  %-8s n=%-5d 记号 %-5d | 每条 P50=%d P90=%d P99=%d max=%d'
          u' | ≥1 %.1f%% ≥3 %.1f%% ≥5 %.1f%% | 密度/100字 P50=%.2f P90=%.2f'
          u' | **当连接符 %.1f%%**'
          % (label, s['n'], mark_tot, s['per_reply']['p50'], s['per_reply']['p90'],
             s['per_reply']['p99'], s['per_reply']['max'],
             s['per_reply']['ge1_pct'], s['per_reply']['ge3_pct'],
             s['per_reply']['ge5_pct'], s['density_per100']['p50'],
             s['density_per100']['p90'], s['connector']['rate_pct']))
    return s


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

    allrows = [(k, t) for k, v in by_npc.items() for t in v]
    zhrows = [(k, t) for k, t in allrows if han_ratio(t) >= 0.5]
    print(u'语料：%d 条 / %d 角色' % (len(allrows), len(by_npc)))
    print(u'')
    print(u'--- 省略号使用 ---')
    ev = {'corpus': {'n': len(allrows), 'npcs': len(by_npc)}}
    ev['all'] = summarise(allrows, u'全部')
    ev['zh'] = summarise(zhrows, u'zh')

    # ralsei 单列（第139/140 轮都是拿它当主宠靶子）
    if 'ralsei' in by_npc:
        ev['ralsei'] = summarise([('ralsei', t) for t in by_npc['ralsei']], u'ralsei')
    print(u'')

    # 谁最密
    per = []
    for k, v in by_npc.items():
        ms = sum(len(marks(t)) for t in v)
        ch = sum(len(t) for t in v)
        per.append((100.0 * ms / max(1, ch), k, len(v), ms))
    per.sort(reverse=True)
    print(u'--- 密度最高 10 个角色（省略号/100 字）---')
    for d, k, n, ms in per[:10]:
        print(u'  %-20s %6.2f  (n=%d, 记号 %d)' % (k, d, n, ms))
    print(u'--- 密度最低 5 个 ---')
    for d, k, n, ms in per[-5:]:
        print(u'  %-20s %6.2f  (n=%d, 记号 %d)' % (k, d, n, ms))
    ev['npc_density_top10'] = [{'npc': k, 'per100': round(d, 2), 'n': n, 'marks': ms}
                               for d, k, n, ms in per[:10]]
    ev['npc_density_bottom5'] = [{'npc': k, 'per100': round(d, 2), 'n': n, 'marks': ms}
                                 for d, k, n, ms in per[-5:]]
    print(u'')

    # 拿它当连接符最多的样本
    worst = []
    for k, t in allrows:
        ms = list(MARK.finditer(t))
        if len(ms) < 3:
            continue
        c = sum(1 for m in ms if is_connector(t, m.end()))
        if c >= 3:
            worst.append((c, len(t), k, t))
    print(u'--- 「≥3 个省略号都当连接符」的样本（最多 8 条）---')
    for c, ln, k, t in sorted(worst, reverse=True)[:8]:
        print(u'  [%d 个连接 / %d 字] %-16s %s'
              % (c, ln, k, t.replace(u'\n', u' ')[:80]))
    ev['connector_samples'] = [{'connectors': c, 'chars': ln, 'npc': k, 'text': t}
                               for c, ln, k, t in sorted(worst, reverse=True)[:8]]

    evd = os.path.join(ROUND, '_evidence')
    if not os.path.isdir(evd):
        os.makedirs(evd)
    out = os.path.join(evd, 'ellipsis141.json')
    with io.open(out, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(ev, ensure_ascii=False, indent=1))
    print(u'')
    print(u'已落盘：', out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
