# -*- coding: utf-8 -*-
"""第199轮 · 口癖普查 v2（只读）

v1 抓出两个判据缺陷，必须在统计前修掉：
  ① **过宽 = 误报**：正确的限频写法本身含"每句""每一句"
     （「不是每句都带」「不必每一句都塞」）⇒ 被当成强化语。
     修法：命中强化语时看**前 4 个字符**里有没有否定词（不/别/无需/不必/不用/没/非/并非）。
  ② **过窄 = 漏报**：v1 只认「比如普通/普通接话/平常就」，漏掉 asgore 的「比如：…」。
     修法：中性正例按**结构**认 —— 该条不含任何口癖候选、且是"普通说话"的例句
     （含 比如/比方说/普通/平常/一般 且后面跟引号）。

★ 本脚本只读，不改任何人设。输出 `_evidence/quirks_hits199.txt` 供逐条肉眼复核。
"""
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'ralsei_pet'))
PDIR = os.path.join(ROOT, 'assets', 'npc', 'persona')

SEC_RE = re.compile(u'^【[^】]+】')
QUOTE_RE = re.compile(u'[“"]([^”"]{1,40})[”"]')
PUNCT_RE = re.compile(u'[，。！？、；：,.!?]')
ITEM_RE = re.compile(u'^[·•\\-\\*]\\s*')

BOOST = [
    u'总是', u'一直', u'永远', u'每次', u'每一句', u'每句话', u'每句',
    u'几乎', u'标志', u'不要忘记', u'始终', u'一律', u'全都', u'都会',
    u'一定', u'必然', u'反复', u'不断', u'习惯性地', u'不停地',
]
NEG = (u'不', u'别', u'无需', u'没', u'非')
NEUTRAL_CUE = (u'比如', u'比方', u'普通', u'平常', u'一般', u'大多数时候')

DESC_BLACK = set([
    u'毛边', u'结巴', u'省略号', u'口癖', u'口头禅', u'语气', u'标志', u'特征',
    u'笑声', u'幽默', u'双关语', u'冷笑话', u'感叹号', u'问号', u'标点',
    u'小写', u'大写', u'全大写', u'第三人称', u'第一人称', u'书面语', u'口语',
])


def rd(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def sections(t):
    out = []
    for ln in t.splitlines():
        s = ln.strip()
        if SEC_RE.match(s):
            out.append([s, []])
        elif out:
            out[-1][1].append(ln)
    return [(h, u'\n'.join(b)) for h, b in out]


def items(body):
    buf, out = [], []
    for ln in body.splitlines():
        if not ln.strip():
            continue
        if ITEM_RE.match(ln.strip()):
            if buf:
                out.append(u'\n'.join(buf))
            buf = [ln.strip()]
        else:
            buf.append(ln.strip())
    if buf:
        out.append(u'\n'.join(buf))
    return out


def markers_of(text):
    out, seen = [], set()
    for m in QUOTE_RE.finditer(text):
        q = m.group(1).strip()
        if not (1 <= len(q) <= 8) or PUNCT_RE.search(q):
            continue
        if q in DESC_BLACK or q in seen:
            continue
        seen.add(q)
        out.append(q)
    return out


def boost_hits(item):
    """返回**真**强化语命中（排除"不是每句"这类否定语境）。"""
    hits = []
    for w in BOOST:
        start = 0
        while True:
            i = item.find(w, start)
            if i < 0:
                break
            pre = item[max(0, i - 4):i]
            if any(x in pre for x in NEG):
                start = i + len(w)
                continue          # 否定语境，不算
            hits.append((w, item[max(0, i - 10):i + len(w) + 10]))
            start = i + len(w)
    return hits


def main():
    names = sorted(n for n in os.listdir(PDIR) if n.endswith('.txt'))
    rows = []
    detail = []
    for n in names:
        t = rd(os.path.join(PDIR, n))
        style = u''
        for h, b in sections(t):
            if u'语言风格' in h:
                style = b
                break
        its = items(style)
        mk = markers_of(style)
        real = []
        for it in its:
            for w, ctx in boost_hits(it):
                real.append((w, ctx, it))
        # 中性正例：该条含"普通/比如…"且**不含**任何口癖候选
        neutral = []
        for it in its:
            if not any(c in it for c in NEUTRAL_CUE):
                continue
            qs = markers_of(it)
            if qs:
                continue
            neutral.append(it)
        rows.append(dict(f=n, style_b=len(style.encode('utf-8')), items=len(its),
                         boost=sorted(set(w for w, _, _ in real)), n_boost=len(real),
                         n_mk=len(mk), mk=mk, neutral=neutral))
        for w, ctx, it in real:
            detail.append((n, w, it))

    print('=== 总览（%d 份） ===' % len(rows))
    print('%-30s %5s %3s %4s %4s %4s' % ('file', 'styleB', '条', '强化', '候选', '正例'))
    for r in rows:
        flag = ('强化:' + '/'.join(r['boost'])) if r['boost'] else ''
        print('%-30s %5d %3d %4d %4d %4d  %s' % (
            r['f'], r['style_b'], r['items'], r['n_boost'], r['n_mk'],
            len(r['neutral']), flag))

    A = [r for r in rows if r['n_boost'] > 0]
    B = [r for r in rows if r['n_boost'] == 0 and r['n_mk'] >= 3]
    C = [r for r in rows if r['n_boost'] == 0 and r['n_mk'] < 3]

    print('\n=== 分级（v2，已排除否定语境） ===')
    print('A 有真强化语        %2d 份' % len(A))
    print('B 有口癖无强化语    %2d 份' % len(B))
    print('C 候选<3            %2d 份' % len(C))
    print('已有中性正例        %2d 份：%s' % (
        len([r for r in rows if r['neutral']]),
        ', '.join(r['f'] for r in rows if r['neutral'])))

    ev = os.path.abspath(os.path.join(HERE, '..', '_evidence'))
    if not os.path.isdir(ev):
        os.makedirs(ev)

    # 逐条明细（肉眼复核用）
    lines = [u'第199轮 · 真强化语逐条明细（已排除"不是每句"这类否定语境）', u'']
    for n, w, it in detail:
        lines.append(u'[%s] (%s)' % (n, w))
        lines.append(u'    %s' % it.replace(u'\n', u' '))
    lines.append(u'')
    lines.append(u'合计 %d 条，涉及 %d 份' % (len(detail), len(set(d[0] for d in detail))))
    p1 = os.path.join(ev, 'quirks_hits199.txt')
    with io.open(p1, 'w', encoding='utf-8', newline='\n') as f:
        f.write(u'\n'.join(lines) + u'\n')

    p2 = os.path.join(ev, 'quirks_survey199.json')
    with io.open(p2, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(rows, ensure_ascii=False, indent=1))

    print('\n[写出] %s' % p1)
    print('[写出] %s' % p2)
    print('真强化语合计 %d 条 / %d 份' % (len(detail), len(set(d[0] for d in detail))))


if __name__ == '__main__':
    main()
