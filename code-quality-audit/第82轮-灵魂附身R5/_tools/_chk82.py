# -*- coding: utf-8 -*-
u"""查 r5_code.json / r5b_code.json 里有多少段是 <DECOMP-FAIL> / <NO-...> 错误串。
★ 不猜，直接统计。"""
import io, json, os, collections

base = r'E:\Download\_tmp\r5_82\_data'
for fn in ['ut_r5_code.json', 'ut_r5b_code.json']:
    p = os.path.join(base, fn)
    if not os.path.exists(p):
        print('[miss] %s' % p); continue
    d = json.load(io.open(p, 'r', encoding='utf-8'))
    codes = d.get('codes', [])
    cnt = collections.Counter()
    errs = []
    empty = []
    for c in codes:
        s = c.get('src') or ''
        if s.startswith('<'):
            key = s.split(':')[0].rstrip('>') + '>'
            cnt[key] += 1
            if len(errs) < 6:
                errs.append((c['name'], s[:200]))
        elif len(s) == 0:
            empty.append(c['name'])
    print('=== %s  count=%d' % (fn, len(codes)))
    print('    错误串统计: %s' % (dict(cnt) if cnt else '无'))
    print('    空段数: %d' % len(empty))
    for n in empty[:12]:
        print('        empty: %s' % n)
    for n, s in errs:
        print('    ERR %s' % n)
        print('        %s' % s)
    # 抽一个正常段看是不是真 GML
    for c in codes:
        s = c.get('src') or ''
        if len(s) > 200 and not s.startswith('<'):
            print('    [样本 %s] 首 300 字:' % c['name'])
            print(s[:300].replace('\n', '\\n'))
            break
    print('')
