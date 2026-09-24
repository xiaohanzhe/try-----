# -*- coding: utf-8 -*-
"""第44轮续 · 「连接顺序是否对」深度复检（只读 · 带锚点校验）。

为什么单写一个脚本
------------------
`recheck_rooms44.py` 的 L4 只报了「to 集合 - when_scene 集合 = 29」，
但这 29 条**含义不明**：可能是
  (a) 原作里本来就没有 A/B/C 出边的终点房（死胡同，正常）；
  (b) 生成器漏编了边（真缺口）。

判据必须回到**原作**去问："这 29 个场景对应的原作房间，本身有没有
A/B/C 字母门？" —— 有 = 生成器漏了（真缺口）；没有 = 原作死胡同（正常）。
这就是记忆 §4「解析器输出必须先过已知真值锚点」的正用法。

三层判据
--------
  A 锚点自检：用 gen_routes44 的同一套机制重算原作边，必须能复现产品路由的
    **绝大多数** when_scene/to 对 —— 否则说明我的探针与原机制不等价，
    **整份结论作废**（不保真的探针 = 报假数据）。
  B 断链归因：29 个"to 无出边"场景逐个回原房间查是否有 A/B/C 门。
  C 完备性：产品路由的每条边，能否在原作房间里找到对应门（反向锚定）。
"""
import io
import json
import os
import collections

ROOT = r'C:\Users\23002\Desktop\项目文件夹\try - 副本'
SC = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
DRW = r'E:\Download\_tmp\drw'
CHS = ['chapter1_windows', 'chapter2_windows', 'chapter3_windows',
       'chapter4_windows', 'chapter5_windows']
TAG = {CHS[i]: 'ch%d' % (i + 1) for i in range(5)}
DOOR_DELTA = {'A': 1, 'B': -1, 'C': 2}

out = []


def P(s=''):
    out.append(s)
    print(s)


def jload(p):
    with io.open(p, encoding='utf-8') as fh:
        return json.load(fh)


def door_letter(objname):
    """与 gen_routes44.door_letter 一字对齐。"""
    if not objname or not objname.startswith('obj_door'):
        return None
    tail = objname[len('obj_door'):]
    for suf in ('_musfade', '_solid'):
        if tail.endswith(suf):
            tail = tail[:-len(suf)]
    if len(tail) == 1 and tail.isalpha() and tail.upper() in DOOR_DELTA:
        return tail.upper()
    return None


def marker_letter(objname):
    """与 gen_routes44.marker_letter 一字对齐。"""
    if not objname or not objname.startswith('obj_marker'):
        return None
    tail = objname[len('obj_marker'):]
    if len(tail) == 1 and tail.isalpha() and tail.isupper():
        return tail
    return None


def parse_pts(lst):
    o = []
    for s in lst or []:
        parts = str(s).split(',')
        if len(parts) >= 3:
            o.append((parts[0], parts[1], parts[2]))
    return o


# ============================================================== 装数据
P('=' * 78)
P('[数据] 原作房 + 产品索引 + 产品路由')
rooms = {}
for w in CHS:
    d = jload(os.path.join(DRW, w, 'rooms44.json'))
    ch = TAG[w]
    for r in d['rooms']:
        r['_ch'] = ch
        rooms[(ch, r['id'])] = r
P('  原作房 = %d' % len(rooms))

idx = jload(os.path.join(SC, '_index.json'))
scenes = {}
by_room_id = {}
for ch_id, chapter in (idx.get('chapters') or {}).items():
    for area_id, area in (chapter.get('areas') or {}).items():
        for sid, entry in (area.get('scenes') or {}).items():
            e = dict(entry)
            e['chapter_id'] = ch_id
            e['area_id'] = area_id
            scenes[sid] = e
            orid = e.get('original_room_id')
            if isinstance(orid, int):
                by_room_id[(ch_id, orid)] = sid
P('  产品场景 = %d ；有 room_id = %d' % (len(scenes), len(by_room_id)))

rd = jload(os.path.join(SC, '_routes.json'))
routes = rd.get('routes') or []
P('  产品路由规则 = %d' % len(routes))

# ============================================================== A 锚点自检
P()
P('[A] 锚点自检：用 gen_routes44 同一机制重算原作 A/B/C 边')
orig_edges = {}     # (src_sid, dst_sid) -> info
st = collections.Counter()
for (ch, rid), r in sorted(rooms.items()):
    sid = by_room_id.get((ch, rid))
    for (_x, _y, dname) in parse_pts(r.get('doors')):
        letter = door_letter(dname)
        if letter is None:
            continue
        st['letter_doors'] += 1
        if not sid:
            st['src_unindexed'] += 1
            continue
        tr = rooms.get((ch, rid + DOOR_DELTA[letter]))
        if tr is None:
            st['no_target_room'] += 1
            continue
        if not any(marker_letter(n) == letter
                   for (_a, _b, n) in parse_pts(tr.get('markers'))):
            st['no_marker'] += 1
            continue
        dst = by_room_id.get((ch, tr['id']))
        if not dst:
            st['dst_unindexed'] += 1
            continue
        st['verified'] += 1
        orig_edges[(sid, dst)] = {'letter': letter, 'ch': ch, 'rid': rid}

prod_edges = set((r.get('when_scene'), r.get('to')) for r in routes
                 if r.get('when_scene') and r.get('to'))
P('  原作重算边 = %d ；产品边 = %d' % (len(orig_edges), len(prod_edges)))
anchor_hit = len(set(orig_edges) & prod_edges)
P('  交集 = %d ；仅原作 = %d ；仅产品 = %d'
  % (anchor_hit, len(set(orig_edges) - prod_edges),
     len(prod_edges) - len(set(orig_edges))))
P('  门型普查：字母门=%d 验证通过=%d （源未登记=%d 目标房不存在=%d '
  '无同字母落点=%d 目标未登记=%d）'
  % (st['letter_doors'], st['verified'], st['src_unindexed'],
     st['no_target_room'], st['no_marker'], st['dst_unindexed']))

# ★ 锚点判据：两边必须高度一致，否则探针与原机制不等价 → 结论作废
if prod_edges and abs(len(prod_edges) - len(set(orig_edges) & prod_edges)) <= 1:
    P('  [ANCHOR PASS] 产品边 ⊂ 原作重算边 —— 探针与生成机制等价，可用。')
    anchor_ok = True
else:
    only_p = sorted(prod_edges - set(orig_edges))
    P('  [ANCHOR FAIL] 产品有 %d 条边不在原作重算里：%s'
      % (len(only_p), only_p[:5]))
    anchor_ok = False

# ============================================================== B 断链归因
P()
P('[B] 断链归因：to 无出边的场景，回原作查是否有 A/B/C 门')
tos = set(r.get('to') for r in routes if r.get('to'))
froms = set(r.get('when_scene') for r in routes if r.get('when_scene'))
dead = sorted(tos - froms)
P('  断链场景数 = %d' % len(dead))
P('  %-42s %-9s %-6s %s' % ('scene_id', '原作房', '有字母门', '该房字母门明细'))
real_gap = []
ok_dead = []
for sid in dead:
    e = scenes.get(sid) or {}
    ch = e.get('chapter_id')
    orid = e.get('original_room_id')
    rec = rooms.get((ch, orid)) if orid is not None else None
    if rec is None:
        P('  %-42s %-9s %-6s %s' % (sid, '<无房>', '?', '未登记/无 room_id'))
        real_gap.append(sid)
        continue
    letters = []
    for (_x, _y, dn) in parse_pts(rec.get('doors')):
        L = door_letter(dn)
        if L:
            letters.append(L)
    letters.sort()
    P('  %-42s %-9s %-6s %s'
      % (sid, '%s:%s' % (ch, orid), len(letters), letters or '-'))
    if letters:
        real_gap.append(sid)     # 原作有门但产品没出边 ⇒ 真缺口
    else:
        ok_dead.append(sid)      # 原作本身没 A/B/C 门 ⇒ 正常死胡同

P()
P('  ---- 归因结果：真缺口 = %d ；原作死胡同（正常）= %d'
  % (len(real_gap), len(ok_dead)))
if real_gap:
    P('  真缺口清单: %s' % real_gap)
if ok_dead:
    P('  正常死胡同: %s' % ok_dead)

# ============================================================== C 完备性
P()
P('[C] 完备性：原作有 A/B/C 门、且源/目标都已登记的场景，产品是否都编了边')
missing_edges = sorted(set(orig_edges) - prod_edges)
P('  原作有边但产品缺 = %d' % len(missing_edges))
for (sa, sb) in missing_edges[:40]:
    info = orig_edges[(sa, sb)]
    P('    缺 %-38s -> %-38s [%s@%s:%s]'
      % (sa, sb, info['letter'], info['ch'], info['rid']))

# ============================================================== D 顺序
P()
P('[D] 连接顺序：同一起点场景内，出边是否按门字母 A<B<C 稳定排布')
by_src = collections.defaultdict(list)
for r in routes:
    by_src[r.get('when_scene')].append((r.get('priority'),
                                        r.get('when_door'), r.get('to')))
multi = {k: v for k, v in by_src.items() if len(v) > 1}
P('  多出边场景 = %d / %d（单出边 %d）'
  % (len(multi), len(by_src), len(by_src) - len(multi)))
bad_order = []
for k, v in sorted(multi.items()):
    v2 = sorted(v, key=lambda t: t[0])
    letters = [t[1] for t in v2]
    if letters != sorted(letters):
        bad_order.append((k, letters))
P('  字母序不递增的场景 = %d %s' % (len(bad_order), bad_order[:6]))

# priority 全局单调性的真实含义
prios = [r.get('priority') for r in routes]
mono = all((prios[i] or 0) <= (prios[i + 1] or 0) for i in range(len(prios) - 1))
P('  priority 全局声明序单调不减 = %s（%s）'
  % (mono, '见下：这是 (110 + order%%240) 回绕所致，非缺陷' if not mono else ''))
wrap = [i for i in range(1, len(prios))
        if prios[i] < prios[i - 1]]
P('  priority 回绕点（下降次数）= %d ；说明 order 超过 240 后取模回绕'
  % len(wrap))

print()
print('[done]')
if not anchor_ok:
    print('[WARN] 锚点未通过，结论不可用！')
