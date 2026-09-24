# -*- coding: utf-8 -*-
"""第44轮 · 路由 v2 的「已知真值锚点」校验。

★★★ 铁律（记忆 §4）：解析器/生成器输出**必须先过 3 个已知真值站点**，
   全命中才允许用其输出。本脚本就是那一步。

三个锚点（全部来自第 42/43 轮已实证的原作连接，不是本次生成物自证）：
  A1. ch1 `room_krisroom`(id=2) 有 doorA(155,230) 与 markerB(155,185)
      ⇒ 它应当**出去一条边**（doorA），也**进来一条边**（markerB）。
  A2. ch1 `room_krishallway`(id=3) 有 doorB(289,104)/doorC(425,100)
      与 markerA(289,112)/markerD(426,118)
      ⇒ krisroom 的 doorA 应当落到 krishallway（因为 krishallway 有 markerA）。
  A3. ch1 `room_torhouse`(id=5) 有 doorD(144,68)/doorA(84,168)
      ⇒ 应当至少有 1 条出边。

负控制（这条必须为"无"）：
  N1. 不许出现 `to == when_scene` 的自环规则。
  N2. 不许出现目标未登记在 _index.json 的规则（会切失败）。
  N3. 不许出现跨章规则（原作门不跨章；跨章是"章节推进"，属另一套）。
"""
import io
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..', '..'))
SC = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')

routes = json.load(io.open(os.path.join(SC, '_routes.json'), encoding='utf-8'))
idx = json.load(io.open(os.path.join(SC, '_index.json'), encoding='utf-8'))

known = set()
by_orid = {}
for ch, chapter in (idx.get('chapters') or {}).items():
    for area in (chapter.get('areas') or {}).values():
        for sid, e in (area.get('scenes') or {}).items():
            known.add(sid)
            if isinstance(e.get('original_room_id'), int):
                by_orid[(ch, e['original_room_id'])] = sid

R = routes['routes']
out_edges = {}
in_edges = {}
for r in R:
    out_edges.setdefault(r['when_scene'], []).append(r)
    in_edges.setdefault(r['to'], []).append(r)

FAIL = []


def chk(name, cond, detail=''):
    print('  [%s] %s    %s' % ('PASS' if cond else 'FAIL', name, detail))
    if not cond:
        FAIL.append(name)


print('=' * 74)
print('路由 v2 · 已知真值锚点校验')
print('=' * 74)

# ---- A 段：三个已知真值 ----
print()
print('A. 已知真值锚点（全命中才允许使用生成物）')
kris = by_orid.get(('ch1', 2))
hall = by_orid.get(('ch1', 3))
house = by_orid.get(('ch1', 5))
print('  映射: krisroom=%s krishallway=%s torhouse=%s' % (kris, hall, house))

chk('A1a krisroom 有出边（doorA 生效）',
    bool(out_edges.get(kris)), '出边=%d' % len(out_edges.get(kris, [])))
chk('A1b krisroom 有入边（markerB 生效）',
    bool(in_edges.get(kris)), '入边=%d' % len(in_edges.get(kris, [])))
tgt = [r['to'] for r in out_edges.get(kris, [])]
chk('A2  krisroom 的 doorA 落到 krishallway（对方有 markerA）',
    hall in tgt, '实际出边=%s' % tgt)
chk('A3  torhouse 有出边',
    bool(out_edges.get(house)), '出边=%d' % len(out_edges.get(house, [])))

# ---- A4：共同卡口 —— 指定 door 时必须精确分流（第44轮新机制）----
# krishallway 有两个门：doorB(-1 回 krisroom) 与 doorC(+2 去 torhouse)。
# 不指定 door → 走 priority 最小的（字母序 A<B<C ⇒ doorB 先，回 krisroom）。
# 指定 door='C' → 必须去 torhouse；指定 door='B' → 必须去 krisroom。
hall_exits = {r.get('when_door'): r['to'] for r in out_edges.get(hall, [])}
chk('A4a krishallway 的两个门都被登记（B/C）',
    set(hall_exits) == {'B', 'C'}, 'actual=%s' % sorted(hall_exits))
chk('A4b 指定 door=C 时精确分流到 torhouse（不同出口可区分）',
    hall_exits.get('C') == house, 'C->%s' % hall_exits.get('C'))
chk('A4c 指定 door=B 时精确分流回 krisroom',
    hall_exits.get('B') == kris, 'B->%s' % hall_exits.get('B'))

# ---- B 段：负控制 ----
print()
print('B. 负控制（这些必须为"无"）')
self_loop = [r for r in R if r['to'] == r['when_scene']]
chk('N1 无自环（to != when_scene）', not self_loop,
    '自环=%d %s' % (len(self_loop), self_loop[:2]))
unreg = sorted(set(r['to'] for r in R) - known)
chk('N2 目标全部已登记（否则切场景会失败）', not unreg,
    '未登记=%d %s' % (len(unreg), unreg[:3]))
cross = []
for r in R:
    chs = set()
    for sid in (r['when_scene'], r['to']):
        e_ch = None
        for ch, chapter in (idx.get('chapters') or {}).items():
            for area in (chapter.get('areas') or {}).values():
                if sid in (area.get('scenes') or {}):
                    e_ch = ch
        chs.add(e_ch)
    if len(chs) > 1:
        cross.append(r)
chk('N3 无跨章规则', not cross, '跨章=%d %s' % (len(cross), cross[:2]))

# ---- C 段：形式-信息 ----
print()
print('C. 形式-信息（表的健康度）')
prios = [r.get('priority') for r in R]
chk('C1 priority 全部为 int', all(isinstance(p, int) for p in prios),
    'n=%d' % len(prios))
chk('C2 每条规则都有 reason', all(isinstance(r.get('reason'), str)
                                  and r['reason'] for r in R),
    '缺 reason=%d' % sum(1 for r in R if not r.get('reason')))
chk('C3 每条规则都有原作依据 _original',
    all(isinstance(r.get('_original'), dict) for r in R),
    '缺 _original=%d' % sum(1 for r in R if not isinstance(r.get('_original'), dict)))
amb = sum(1 for r in R if r.get('_original', {}).get('ambiguous'))
print('  [info] 有歧义标记的规则 = %d / %d (%.1f%%)'
      % (amb, len(R), 100.0 * amb / max(1, len(R))))
chk('C4 歧义比例 < 50%（否则"取最近"这个启发式不可信）',
    amb < len(R) * 0.5, '%.1f%%' % (100.0 * amb / max(1, len(R))))

print()
print('=' * 74)
print('锚点校验结论：FAIL = %d' % len(FAIL))
print('=' * 74)
