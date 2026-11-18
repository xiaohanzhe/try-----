# -*- coding: utf-8 -*-
"""第199轮 · 人设文件摸底 v2（只读）

v1 用 `^#{1,3}` 找章节 ⇒ 全部 0 节（人设用的是【】，不是 markdown 标题）。
恒空 = 恒真的反面，改按【】切。
"""
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'ralsei_pet'))
PDIR = os.path.join(ROOT, 'assets', 'npc', 'persona')
REG = os.path.join(ROOT, 'assets', 'npc', '_registry.json')

SEC_RE = re.compile(u'^【[^】]+】')


def rd(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def sections(t):
    out = []
    cur = None
    for ln in t.splitlines():
        s = ln.strip()
        m = SEC_RE.match(s)
        if m:
            cur = s
            out.append([cur, []])
        elif out:
            out[-1][1].append(ln)
    return [(h, u'\n'.join(b)) for h, b in out]


def main():
    names = sorted(n for n in os.listdir(PDIR) if n.endswith('.txt'))
    print('=== 人设文件 %d 个 ===' % len(names))

    cnt = {}
    per = {}
    for n in names:
        t = rd(os.path.join(PDIR, n))
        ss = sections(t)
        per[n] = [h for h, _ in ss]
        for h, _ in ss:
            cnt[h] = cnt.get(h, 0) + 1

    print('\n=== 章节名频次 ===')
    for h, c in sorted(cnt.items(), key=lambda x: -x[1]):
        print('%3d  %s' % (c, h))

    print('\n=== 缺「语言风格」的人设 ===')
    miss = [n for n in names if not any(u'语言风格' in h for h in per[n])]
    print('共 %d 个：%s' % (len(miss), ', '.join(miss) if miss else '（无）'))

    print('\n=== 「语言风格」节字节数分布 ===')
    sizes = []
    for n in names:
        t = rd(os.path.join(PDIR, n))
        for h, body in sections(t):
            if u'语言风格' in h:
                sizes.append((len(body.encode('utf-8')), n, h))
    sizes.sort()
    print('最小 5：%s' % [(s, n) for s, n, _ in sizes[:5]])
    print('最大 5：%s' % [(s, n) for s, n, _ in sizes[-5:]])
    print('中位 %d B' % sizes[len(sizes) // 2][0])

    # 口癖线索词：看语言风格节里有没有明确写"口癖"或具体反复标记
    print('\n=== 「语言风格」里显式写了「口癖」的人设 ===')
    hit = []
    for n in names:
        t = rd(os.path.join(PDIR, n))
        for h, body in sections(t):
            if u'语言风格' in h:
                if u'口癖' in body:
                    hit.append(n)
    print('%d 个：%s' % (len(hit), ', '.join(hit)))

    # registry
    print('\n=== _registry.json ===')
    d = json.loads(rd(REG))
    print('顶层类型=%s 键数=%d' % (type(d).__name__, len(d)))
    if isinstance(d, dict):
        k0 = list(d.keys())[0]
        print('样例键 %s -> %s' % (k0, json.dumps(d[k0], ensure_ascii=False)[:400]))
        tot = 0
        per_p = []
        for k, v in d.items():
            if isinstance(v, dict) and isinstance(v.get('patches'), list):
                per_p.append((k, len(v['patches'])))
                tot += len(v['patches'])
        per_p.sort(key=lambda x: x[1])
        print('patch 总条数=%d 条目=%d' % (tot, len(per_p)))
        print('最少 6：%s' % per_p[:6])
        print('最多 6：%s' % per_p[-6:])


if __name__ == '__main__':
    main()
