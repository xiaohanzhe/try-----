# -*- coding: utf-8 -*-
"""第141轮 · 收口：剔掉 `…` 串之后，还剩几条「真·长句」？

前面三步的链条：
  measure141  → 最长句 P90=83，样本榜前四全是英文 NPC
  measure141b → 补 ASCII `.` 后 en 层 P90 塌 180 字，zh 层只动 −2 ⇒ 英文污染
  measure141c → `…` 被当连接符 97.4%；zh 层 186 字那条是 10 个 `…` 串出来的

现在把两种"假长句"都剔掉：
  (a) 英文：汉字占比 < 0.5 的整条剔除
  (b) `…` 串：最长句里省略号记号 ≥2 个的剔除（说明长度是 `…` 撑出来的）

剩下的才是**真·一口气说了很长**。逐条打印，人工判断是"念说明"还是"正常叙述"。
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

END = u'\u3002\uff01\uff1f!?\n'
MARK = re.compile(u'\u2026{1,}|\\.{2,}')


def split(text):
    out, buf, has_word, started, in_end = [], [], False, False, False
    for ch in text:
        buf.append(ch)
        if ch in END:
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
    return float(sum(1 for ch in word if u'\u4e00' <= ch <= u'\u9fff')) / len(word)


def main():
    rows = []
    for p in sorted(glob.glob(os.path.join(RAW, '*.jsonl'))):
        name = os.path.basename(p)[:-6]
        for line in io.open(p, encoding='utf-8', newline=''):
            if not line.strip():
                continue
            rec = json.loads(line)
            for turn in rec.get('turns') or []:
                t = (turn.get('final') or u'').strip()
                if t:
                    rows.append((name, t))

    zh = [(k, t) for k, t in rows if han_ratio(t) >= 0.5]
    pure = []      # (最长句长度, 省略号数, npc, 最长句, 全文)
    for k, t in zh:
        ss = split(t)
        if not ss:
            continue
        s = max(ss, key=len)
        pure.append((len(s), len(MARK.findall(s)), k, s, t))

    for th in (60, 70, 80, 100, 120):
        n80 = sum(1 for v in pure if v[0] >= th)
        n80e = sum(1 for v in pure if v[0] >= th and v[1] <= 1)
        print(u'  阈值 %3d 字：中文层 %d 条(%.1f%%) · 其中省略号≤1 个 %d 条(%.1f%%)'
              % (th, n80, 100.0 * n80 / len(pure), n80e, 100.0 * n80e / len(pure)))
    print(u'  中文层分母 %d' % len(pure))
    print(u'')

    kept = [v for v in sorted(pure, reverse=True) if v[0] >= 80 and v[1] <= 1]
    print(u'--- 真·长句（中文 / 最长句 ≥80 字 / 省略号 ≤1），共 %d 条，全部打印 ---' % len(kept))
    for ln, e, k, s, t in kept[:40]:
        print(u'  [%d 字 / %d 省略号] %-16s %s' % (ln, e, k, s.replace(u'\n', u' ')))
    if len(kept) > 40:
        print(u'  ... 另 %d 条省略' % (len(kept) - 40))
    print(u'')

    # 逗号位置分布：真长句是靠逗号串起来的吗
    chain = []
    for ln, e, k, s, t in kept:
        chain.append(sum(1 for ch in s if ch in u'\uff0c\u3001,;；'))
    if chain:
        chain_sorted = sorted(chain)
        med = chain_sorted[len(chain_sorted) // 2]
        print(u'  这 %d 条真长句的逗号数：中位 %d · max %d · 逗号≤1 的 %d 条'
              % (len(chain), med, max(chain), sum(1 for c in chain if c <= 1)))

    ev = {'zh_replies': len(pure), 'thresholds': {}, 'real_long': [], 'comma_chain': {}}
    for th in (60, 70, 80, 100, 120):
        ev['thresholds'][str(th)] = {
            'all': sum(1 for v in pure if v[0] >= th),
            'no_ellipsis_chain': sum(1 for v in pure if v[0] >= th and v[1] <= 1)}
    ev['real_long'] = [{'chars': ln, 'ellipsis': e, 'npc': k, 'sentence': s, 'full': t}
                       for ln, e, k, s, t in kept]
    if chain:
        ev['comma_chain'] = {'n': len(chain), 'median': med, 'max': max(chain),
                             'le1': sum(1 for c in chain if c <= 1)}
    evd = os.path.join(ROUND, '_evidence')
    if not os.path.isdir(evd):
        os.makedirs(evd)
    out = os.path.join(evd, 'real_long141.json')
    with io.open(out, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(ev, ensure_ascii=False, indent=1))
    print(u'')
    print(u'已落盘：', out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
