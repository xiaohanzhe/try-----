# -*- coding: utf-8 -*-
"""第43轮 · 交叉核对脚本（把本轮内联做的三类校验固化，可复现）

用法: python mx43.py [drw根目录]

校验：
  [A] 关键对象索引的五章一致性（用 objmap43.txt）
  [B] ch1 每房间 view[0] 尺寸分布 + 房间尺寸分布 + 超宽房间（用 view43.json）
  [C] ch1 层几何非零 / 视差非零 / EffectType 非空 的统计（用 view43.json）
  [D] func43_all.txt 里的 Top 函数
"""
import io
import json
import os
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT = sys.argv[1] if len(sys.argv) > 1 else r'E:\Download\_tmp\drw'
CHS = ['chapter1_windows', 'chapter2_windows', 'chapter3_windows',
       'chapter4_windows', 'chapter5_windows']
KEY = ['obj_fadeout', 'obj_fadein', 'obj_persistentfadein', 'obj_shake', 'obj_panner',
       'obj_marker', 'obj_doorA', 'obj_doorX', 'obj_markerX', 'obj_mainchara',
       'obj_backgrounder_standard', 'obj_backgrounder_sprite', 'obj_screen_loading',
       'obj_darkfountain', 'obj_shakeobj', 'obj_oflash']


def objmap(ch):
    p = os.path.join(ROOT, ch, 'objmap43.txt')
    idx, n = {}, 0
    if not os.path.isfile(p):
        return idx, -1
    for ln in open(p, encoding='utf-8'):
        c = ln.rstrip('\n').split('\t')
        if c and c[0].isdigit():
            idx[c[1]] = int(c[0])
            n = max(n, int(c[0]) + 1)
    return idx, n


print('=' * 70)
print('[A] 对象索引跨章一致性')
print('=' * 70)
tab, cnt = {}, {}
for ch in CHS:
    tab[ch], cnt[ch] = objmap(ch)
    print('  %-18s objects=%-6d' % (ch, cnt[ch]))
print()
print('  %-28s %s' % ('对象', '  '.join('ch%d' % i for i in range(1, 6))))
diff = 0
for k in KEY:
    row = [tab[ch].get(k) for ch in CHS]
    s = ['%-5s' % (v if v is not None else '--') for v in row]
    vals = [v for v in row if v is not None]
    same = len(vals) == len(CHS) and len(set(vals)) == 1
    if not same:
        diff += 1
    print('  %-28s %-32s %s' % (k, '  '.join(s), '一致' if same else '★不一致'))
print()
print('  ⇒ 索引不一致数 = %d / %d ⇒ 结论：对象索引【跨章不稳定】，跨章引用必须按【名字】'
      % (diff, len(KEY)))
print()

ch1 = os.path.join(ROOT, CHS[0])
vj = os.path.join(ch1, 'view43.json')
if not os.path.isfile(vj):
    print('缺 %s，跳过 [B][C]' % vj)
    sys.exit(0)
d = json.loads(open(vj, encoding='utf-8').read())

print('=' * 70)
print('[B] ch1 view[0] / 房间尺寸')
print('=' * 70)
c0, co = Counter(), Counter()
for r in d['rooms']:
    if not r['views']:
        continue
    v = r['views'][0]
    c0[(v['vw'], v['vh'], v['pw'], v['ph'])] += 1
    co[v.get('obj') or '(无)'] += 1
print('  view[0] (w,h,port_w,port_h) 分布:')
for k, n in c0.most_common():
    print('    %sx%s port %sx%s : %d 间' % (k[0], k[1], k[2], k[3], n))
print('  view[0].obj 分布:')
for k, n in co.most_common():
    print('    %-16s : %d' % (k, n))
wide = [r for r in d['rooms'] if int(r['w']) > 320]
print('  房间宽 > 320 的 = %d / %d  （需要相机横向滑动）' % (len(wide), len(d['rooms'])))
for x in sorted(((int(r['w']), r['name']) for r in d['rooms']), reverse=True)[:5]:
    print('    最宽: %sx? %s' % x)
print()

print('=' * 70)
print('[C] ch1 层几何 / 视差 / 层特效')
print('=' * 70)
tot = geo = par = eff = 0
for r in d['rooms']:
    for ly in r['layers']:
        tot += 1
        if ly['x'] != 0 or ly['y'] != 0 or ly['hs'] != 0 or ly['vs'] != 0:
            geo += 1
        if ly['hs'] != 0 or ly['vs'] != 0:
            par += 1
        if ly.get('effType'):
            eff += 1
print('  层总数 = %d' % tot)
print('  几何非零(XOffset/YOffset/HSpeed/VSpeed) = %d' % geo)
print('  ★ 视差非零(HSpeed/VSpeed) = %d  ⇒ 结论：%s' % (par, '无视差，背景靠相机滚动' if par == 0 else '存在视差'))
print('  ★ EffectType 非空 = %d  ⇒ 结论：%s' % (eff, '无 GMS2 层特效' if eff == 0 else '存在层特效'))
print()

fa = os.path.join(ch1, 'func43_all.txt')
if os.path.isfile(fa):
    print('=' * 70)
    print('[D] func43_all.txt Top 函数')
    print('=' * 70)
    rows = []
    for ln in open(fa, encoding='utf-8'):
        if '\t' in ln:
            a, b = ln.rstrip('\n').split('\t', 1)
            if a.isdigit():
                rows.append((int(a), b))
    for n, nm in sorted(rows, reverse=True)[:25]:
        print('  %6d  %s' % (n, nm))
