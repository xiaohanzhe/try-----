# -*- coding: utf-8 -*-
"""第44轮续 · 原作「连接顺序」全量分析（只读）。

原料 = E:\\Download\\_tmp\\drw\\chapter{1..5}_windows\\rooms44.json
      （UTMT 实测：1,251 间 / 1,840 门实例 / 1,936 落点实例）

做四件事：
  [A] 门 ↔ 落点**配对**（同一间房里按字母后缀配对：obj_doorA ↔ obj_markerA）
  [B] 门的类型普查（obj_doorA..F / obj_doorX / obj_doorW / obj_doorAny …）
  [C] 从房间名推断**区域**，与产品 scene_id 的 area 对照
  [D] 产品路由连通性：26 条规则 vs 1,013 场景可达面
"""
import io
import json
import os
import re
import collections

DRW = r'E:\Download\_tmp\drw'
SC = r'C:\Users\23002\Desktop\项目文件夹\try - 副本\ralsei_pet\assets\scenes'
OUT = []


def P(s=''):
    OUT.append(s)
    print(s)


def jload(p):
    with io.open(p, encoding='utf-8') as fh:
        return json.load(fh)


rooms = {}
for i in range(1, 6):
    d = jload(os.path.join(DRW, 'chapter%d_windows' % i, 'rooms44.json'))
    rooms['ch%d' % i] = d['rooms']

# ---------------------------------------------------------------- [A] 配对
P('=' * 78)
P('[A] 门 ↔ 落点配对（按同房内的字母后缀）')
SUF = re.compile(r'obj_(?:door|marker)([A-Za-z]*)$')


def suffix(name):
    m = SUF.match(name or '')
    return m.group(1) if m else None


tot_pair = tot_door = tot_mark = 0
paired_ok = 0
unpaired = collections.Counter()
per_ch = {}
for ch, rs in rooms.items():
    pd_ = pm_ = pp_ = 0
    for r in rs:
        D = collections.defaultdict(list)
        M = collections.defaultdict(list)
        for d in r['doors']:
            x, y, nm = d.split(',', 2)
            D[suffix(nm) or ('?', nm)].append((x, y, nm))
        for m in r['markers']:
            x, y, nm = m.split(',', 2)
            M[suffix(nm) or ('?', nm)].append((x, y, nm))
        pd_ += len(r['doors'])
        pm_ += len(r['markers'])
        for s in set(D) | set(M):
            if s in D and s in M:
                pp_ += min(len(D[s]), len(M[s]))
            else:
                for _ in (D.get(s) or []):
                    unpaired['门无落点:' + str(s)] += 1
                for _ in (M.get(s) or []):
                    unpaired['落点无门:' + str(s)] += 1
    per_ch[ch] = (pd_, pm_, pp_)
    tot_door += pd_
    tot_mark += pm_
    paired_ok += pp_
    P('  %-5s 门=%-5d 落点=%-5d 同字母配对=%-5d (%.1f%%)'
      % (ch, pd_, pm_, pp_, 100.0 * pp_ / max(1, pd_)))
P('  ---- 合计 门=%d 落点=%d 配对=%d (%.1f%%)'
  % (tot_door, tot_mark, paired_ok, 100.0 * paired_ok / max(1, tot_door)))
P('  未配对 top15: %s' % unpaired.most_common(15))

# ---------------------------------------------------------------- [B] 门类型
P()
P('[B] 门的类型普查（跨五章）')
dc = collections.Counter()
mc = collections.Counter()
for ch, rs in rooms.items():
    for r in rs:
        for d in r['doors']:
            dc[d.rsplit(',', 1)[1]] += 1
        for m in r['markers']:
            mc[m.rsplit(',', 1)[1]] += 1
P('  门对象 %d 种，top25:' % len(dc))
for k, v in dc.most_common(25):
    P('    %-28s %d' % (k, v))
P('  落点对象 %d 种，top20:' % len(mc))
for k, v in mc.most_common(20):
    P('    %-28s %d' % (k, v))

# ---------------------------------------------------------------- [C] 区域
P()
P('[C] 房间名前缀 → 区域（与产品 area 对照）')


def area_of(name, ch):
    """原作房间名形如 room_town_north / room_castle_* / room_dw_*，
    产品 area 由第 36 轮从显示名的 ' - ' 前缀推出。这里给一个粗归类，
    只看**是否可机械推导**，不追求与产品逐字一致。"""
    n = (name or '')
    if n.startswith('room_'):
        n = n[5:]
    return n.split('_')[0] if n else '?'


pc = collections.Counter()
for ch, rs in rooms.items():
    for r in rs:
        pc[area_of(r['name'], ch)] += 1
P('  房间名首段 top25: %s' % pc.most_common(25))

# ---------------------------------------------------------------- [D] 路由
P()
idx = jload(os.path.join(SC, '_index.json'))
scenes = {}
for ch, cv in (idx.get('chapters') or {}).items():
    for area, av in (cv.get('areas') or {}).items():
        for sid, e in (av.get('scenes') or {}).items():
            scenes[sid] = dict(e, _ch=ch, _area=area)
routes = jload(os.path.join(SC, '_routes.json'))
rl = routes.get('routes') or []

P('[D] 产品路由连通性')
P('  场景总数 = %d ；路由规则 = %d' % (len(scenes), len(rl)))
tos = {r['to'] for r in rl if r.get('to')}
P('  规则能到达的场景 = %d / %d (%.1f%%)'
  % (len(tos), len(scenes), 100.0 * len(tos) / len(scenes)))
P('  ★ 未纳入任何规则的场景 = %d' % (len(scenes) - len(tos)))
# 每章被线路覆盖的数
per = collections.Counter()
for s in tos:
    per[scenes[s]['_ch']] += 1
allc = collections.Counter(s['_ch'] for s in scenes.values())
P('  逐章覆盖: %s'
  % {ch: '%d/%d' % (per.get(ch, 0), allc[ch]) for ch in sorted(allc)})

# 原作可推导的连接数：门实例数 ~ 边数上界
P()
P('[D2] 原作侧 vs 产品侧的连接规模')
P('  原作门实例 = %d（每条门 ≈ 一条连接；含可见性/门控变体）' % tot_door)
P('  产品路由规则 = %d' % len(rl))
P('  ⇒ 缺口 ≈ %d 条' % (tot_door - len(rl)))

# 写落盘
outp = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    '..', '_evidence', '连接顺序分析.txt')
with io.open(outp, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write('\n'.join(OUT) + '\n')
print()
print('[done] -> %s' % os.path.abspath(outp))
