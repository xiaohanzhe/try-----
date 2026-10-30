# -*- coding: utf-8 -*-
"""
第115轮 · 判据归因（★ 报红先怀疑判据）

A2b 报红时列出的两条里，第 2 条正文明显含「不确定」，本该被判为"承认记不清"。
在改任何产品文件之前先把**判据本身**查清楚：是产品错了，还是判据错了。
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EV = os.path.join(ROUND, '_evidence')

with io.open(os.path.join(EV, 'accept115_live.json'), 'r', encoding='utf-8') as f:
    D = json.load(f)

ADMIT = ('记不清', '记不太清', '不确定', '想不起来')

print('=== Q6 逐条复核（判据到底看到了什么）===')
for r in D['results']:
    if r['qid'] != 'Q6':
        continue
    fin = r['final']
    side = r.get('final_extra') or {}
    admit_now = [w for w in ADMIT if w in fin]
    print('  #%d' % r['sample'])
    print('    final        = %r' % fin)
    print('    落盘 admit   = %r' % side.get('admit'))
    print('    现算 admit   = %r  (命中词 %r)' % (bool(admit_now), admit_now))
    print('    含"豆豆"     = %s' % ('豆豆' in fin))
    print('    本应判 违例  = %s' % ('豆豆' in fin and not admit_now))

print('\n=== Q7 逐条复核 ===')
for r in D['results']:
    if r['qid'] != 'Q7':
        continue
    fin = r['final']
    hit = [w for w in ('游戏', 'Deltarune', '写出来', '角色') if w in fin]
    print('  #%d 命中 %r' % (r['sample'], hit))
    print('    final = %r' % fin)
    print('    ★ 是否出现"绕开/推走"话术:',
          [w for w in ('聊点别的', '不太懂', '不明白', '意义在哪') if w in fin])

print('\n=== 结论 ===')
bad = 0
for r in D['results']:
    if r['qid'] != 'Q6':
        continue
    fin = r['final']
    stored = (r.get('final_extra') or {}).get('admit')
    now = any(w in fin for w in ADMIT)
    if stored != now:
        bad += 1
        print('  ★ 判据不一致：sample #%d 落盘 admit=%r 现算=%r'
              % (r['sample'], stored, now))
print('  判据不一致条数 = %d' % bad)
