# -*- coding: utf-8 -*-
"""第199轮 · 人设文件摸底（只读）

输出：
  1) 76 个人设文件的字节数 / 行数 / 章节标题
  2) `_registry.json` 的键与 patches 计数
  3) 「口癖 / 说话习惯 / 语气」这类章节到底存不存在、叫什么名字
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'ralsei_pet'))
PDIR = os.path.join(ROOT, 'assets', 'npc', 'persona')
REG = os.path.join(ROOT, 'assets', 'npc', '_registry.json')


def rd(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def main():
    names = sorted(n for n in os.listdir(PDIR) if n.endswith('.txt'))
    print('=== 人设文件 %d 个 ===' % len(names))
    total = 0
    heads = {}
    for n in names:
        p = os.path.join(PDIR, n)
        t = rd(p)
        total += len(t.encode('utf-8'))
        hs = [ln.strip() for ln in t.splitlines() if re.match(r'^#{1,3}\s', ln.strip())]
        heads[n] = hs
        print('%-28s %6d B  %4d 行  %2d 节' % (n, len(t.encode('utf-8')), t.count('\n'), len(hs)))
    print('总计 %.1f KB' % (total / 1024.0))

    # 章节名频次
    cnt = {}
    for n, hs in heads.items():
        for h in hs:
            cnt[h] = cnt.get(h, 0) + 1
    print('\n=== 章节名频次（出现 >=3 次） ===')
    for h, c in sorted(cnt.items(), key=lambda x: -x[1]):
        if c >= 3:
            print('%3d  %s' % (c, h))

    print('\n=== 含「口癖/语气/说话」字样的章节 ===')
    KW = (u'口癖', u'语气', u'说话', u'口头', u'腔调')
    for n in names:
        hit = [h for h in heads[n] if any(k in h for k in KW)]
        if hit:
            print('%-28s %s' % (n, ' | '.join(hit)))

    # registry
    print('\n=== _registry.json ===')
    d = json.loads(rd(REG))
    print('顶层类型=%s 键数=%d' % (type(d).__name__, len(d)))
    if isinstance(d, dict):
        for k, v in list(d.items())[:3]:
            print('  %s -> %s' % (k, json.dumps(v, ensure_ascii=False)[:300]))
    # patches 计数
    tot = 0
    per = []
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, dict) and 'patches' in v:
                per.append((k, len(v['patches'])))
                tot += len(v['patches'])
    per.sort(key=lambda x: x[1])
    print('patch 总条数=%d，条目=%d' % (tot, len(per)))
    print('最少的 5 个：%s' % per[:5])
    print('最多的 5 个：%s' % per[-5:])


if __name__ == '__main__':
    main()
