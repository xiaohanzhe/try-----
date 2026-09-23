# -*- coding: utf-8 -*-
"""探针 2：856 个"近似"场景的房间，到底靠什么显形（瓦片？实例？）——只读。"""
import io, os, sys, json, collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
REPO = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
EV = os.path.join(REPO, 'code-quality-audit', '第39轮-全量场景背景', '_evidence')
DR_OUT = r'E:\Download\_tmp\dr_out'
CH_DIR = {'ch1': 'chapter1_windows', 'ch2': 'chapter2_windows', 'ch3': 'chapter3_windows',
          'ch4': 'chapter4_windows', 'ch5': 'chapter5_windows'}

rooms = {}
for ch, d in CH_DIR.items():
    p = os.path.join(DR_OUT, d, 'rooms_map.json')
    dd = json.load(open(p, encoding='utf-8'))
    rooms[ch] = {r['index']: r for r in dd['rooms']}

print('=' * 76)
print('A. 全 1,251 房间的"显形来源"分层')
print('=' * 76)
print('   %-6s %6s %8s %8s %8s %8s %8s' % ('章', '房间', '有bg层', '有瓦片', '有实例', '有asset', '全空'))
allcnt = collections.Counter()
for ch in CH_DIR:
    c = collections.Counter()
    for rid, r in rooms[ch].items():
        lys = r.get('layers') or []
        if any(ly.get('bg_sprite') for ly in lys):
            c['bg'] += 1
        if any(ly.get('tiles') for ly in lys):
            c['tiles'] += 1
        if any(ly.get('instances') for ly in lys):
            c['inst'] += 1
        if any(ly.get('asset_sprites') or ly.get('asset_sequences') or ly.get('asset_nineslices')
               for ly in lys):
            c['asset'] += 1
        if not any(ly.get('bg_sprite') or ly.get('tiles') or ly.get('instances')
                   or ly.get('asset_sprites') for ly in lys):
            c['empty'] += 1
    allcnt.update(c)
    print('   %-6s %6d %8d %8d %8d %8d %8d' % (ch, len(rooms[ch]), c['bg'], c['tiles'],
                                                c['inst'], c['asset'], c['empty']))
print('   %-6s %6d %8d %8d %8d %8d %8d' % ('合计', sum(len(v) for v in rooms.values()),
                                            allcnt['bg'], allcnt['tiles'], allcnt['inst'],
                                            allcnt['asset'], allcnt['empty']))

print('\n' + '=' * 76)
print('B. 856 个"近似"场景的房间分层（按房间去重）')
print('=' * 76)
det = json.load(open(os.path.join(EV, '真背景可达清单.json'), encoding='utf-8'))
ap = det['approx']
seen = {}
for e in ap:
    key = (e['chapter'], e['room_id'])
    seen.setdefault(key, []).append(e['scene_id'])
c2 = collections.Counter()
for (ch, rid) in seen:
    r = rooms[ch].get(rid)
    if r is None:
        c2['room_missing'] += 1
        continue
    lys = r.get('layers') or []
    has_t = any(ly.get('tiles') for ly in lys)
    has_i = any(ly.get('instances') for ly in lys)
    if has_t and has_i:
        c2['tiles+inst'] += 1
    elif has_t:
        c2['only_tiles'] += 1
    elif has_i:
        c2['only_inst'] += 1
    else:
        c2['neither'] += 1
print('   近似场景 %d 个，涉及房间 %d 间' % (len(ap), len(seen)))
for k, v in sorted(c2.items(), key=lambda kv: -kv[1]):
    print('     %-12s %4d' % (k, v))

print('\n' + '=' * 76)
print('C. 样例：近似场景里"有瓦片层的房间"各自瓦片数量前 12')
print('=' * 76)
rows = []
for (ch, rid), sids in seen.items():
    r = rooms[ch].get(rid)
    if not r:
        continue
    n = sum(len(ly.get('tiles') or []) for ly in (r.get('layers') or []))
    rows.append((n, ch, rid, r.get('name'), r.get('width'), r.get('height'), sids[0]))
rows.sort(reverse=True)
for n, ch, rid, name, w, h, sid in rows[:12]:
    print('   tiles=%5d  %-4s rid=%-4s %-34s room=%sx%s  e.g. %s'
          % (n, ch, rid, str(name)[:34], w, h, sid))

print('\n' + '=' * 76)
print('D. asset/sprites 目录里是否有瓦片图集（Tilesets）')
print('=' * 76)
for ch, d in CH_DIR.items():
    for sub in os.listdir(os.path.join(DR_OUT, d)):
        p = os.path.join(DR_OUT, d, sub)
        if os.path.isdir(p):
            print('   %-6s %-20s %d 项' % (ch, sub, len(os.listdir(p))))
