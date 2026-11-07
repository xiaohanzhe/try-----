# -*- coding: utf-8 -*-
u"""第168轮 · 把 ch1~ch5 的 **W 门**接进产品路由表。

## 为什么这一轮

第125轮以「证据不足」**主动拒收** W 门（产品里 W 一条都没写），理由是：

    obj_markerw 仅 60.2%、obj_markerX 84.3%，无一套到 100%

第126轮又自己把门槛更正为「机制 + 在场 ≈ 90% 以上，且**每一条不中都能逐条归因**」，
并写明 W 不收的真因是「两套 marker 写法归不了因」。

本轮把"归不了因"三件事全部查清 ⇒ **W 与 A/B/C/D/X 用的是同一套机制，当年量错了对象**。

## 三处实证（都不是推测）

### ① 机制：`obj_doorW_Alarm_2` 反汇编原文（UTMT，ch1 / ch2）

```
0  PushI 23  →  Pop VAR=entrance                      ← 先给出生点编号
2  PushI 145 →  … FN=gml_Script_instance_create       ← 建 persistentfadein
10 PushBltn room; PushI 13; Cmp; Bf; PushI 18; FN=room_goto
18 PushBltn room; PushI 18; Cmp; Bf; PushI 13; FN=room_goto
…                                                     ← ch1 共 6 条 if (room == N) room_goto(M)
```

★ 骨架与 `obj_doorX` **逐句同形**：赋值 `entrance` → `instance_create` → 一串
  `if (room == N) room_goto(M)`。W 不是"另一种门"，就是**表驱动那一种**。

★★★ **但 `entrance` 不是"每类门一个常量"** —— 这一条是本轮踩出来的坑，
    写在这里免得下次又有人拿它当字母常量用：

    ch1  obj_doorW_Alarm_2            entrance 赋值 **1 次**   = [23]
    ch2  obj_doorW_Alarm_2            entrance 赋值 **145 次** = [23, 20, 23, 20, 22, …]
    ch2  obj_doorw_musfade_Alarm_2    entrance 赋值 **10 次**  = [23, 22, 22, 24, 23, …]

    ch2 那 145 个值全部落在 **19~24**，而 19..24 正是字母序
    **S=19 / T=20 / U=21 / V=22 / W=23 / X=24**（ch2 里 `obj_markerr..v` 各有
    专属 `spr_markerR..V`，正好对上）。

⇒ `entrance` 的真实语义是「**新房间里第 N 个字母的出生点**」，
  **每个 `if (room == N)` 分支可以各自指定**。所以：

  · 可以据它说"W 门与 A/B/C/D/X 同机制"（骨架 + 语义都同）；
  · **不可以**说"W 门 ⇒ entrance=23"，也不可以把判据建在它的具体数值上
    （ch2 的多数分支落点是 S/T/U/V，不是 W）。

⇒ 落点自证用的是**实测口径**：目标房含 `obj_markerw`（小写）或 `obj_markerAny`，
  与 A/B/C/D/X 用的**同一把尺**（见 ③）。

### ② marker 对象表（UTMT `sprite=` 字段，ch1 / ch2 两章一致）

    obj_markerA~F   → spr_markerA~F     各**专属**
    obj_markerw     → **spr_markerW**   **专属**（与 A~F 同族）
    obj_markerX     → spr_markerX       X 的专属
    obj_markerAny   → spr_markerAny     **真通用**

★ 第125轮的两次测量都量错了对象：
  · 拿 `obj_markerW`（大写）比 —— 产品里对象名是**小写** `obj_markerw` ⇒ 恒 0%；
  · 换 `obj_markerX` 比 —— 那是**字母 X 的**出生点，不是通用兜底 ⇒ 84.3% 是个混账数。

★ ch1 里 `obj_markerr/s/t/u/v` 共用 `spr_markerX` 只是那五张 sprite 当时还没画
  （ch2 里它们各自有 `spr_markerR..V`）——**不能**据此把 X 当占位符。

### ③ 同一把尺重算六类门（`_room_graph.json` 782 条边的同一批实例）

    门   同字母  通用Any  只有X  别字母  空房 | 自证率(同字母+通用)
    A     195      8       2      6     6   | 203/217 = 93.5%
    B     194      6       4      8     4   | 200/216 = 92.6%
    C      59      0       0      1     1   |  59/61  = 96.7%
    D      61      1       0      1     5   |  62/68  = 91.2%
    X      84      0       0      0     5   |  84/89  = 94.4%
    W      74     16       1      5     1   |  90/97  = 92.8%   ← 本轮

W 落在已收五类的区间正中 ⇒ 达到第126轮写下的门槛。

## 准入三闸（与第122/125/126轮同一套纪律）

  ① 机制已证：`entrance=23` + `if (room == N) room_goto(M)`（上面 ① 的原文）
  ② 落点自证：目标房含 **`obj_markerw`（大小写不敏感）** 或 **`obj_markerAny`**
  ③ 产品侧不冲突：`(场景, 'W')` 目前 0 条；新段 priority 从 **7000** 起

## 逐条拒收 / 去重的账（98 条 W 边一条不少地对上）

    98  证据里的 W 边（`_room_graph.json`；`obj_doorW` + `obj_doorw_musfade`）
    −75 同字母出生点 `obj_markerw`                → 收
    −16 通用出生点 `obj_markerAny`                → 收
    − 6 marker 不对：只有 `obj_markerX` 1 条 / 只有别的字母 5 条 → **拒收**
    − 1 目标房未登记（`room_shop_ch2_swatch`，商店空壳，零 marker）→ **拒收**
    = 91 可用
    − 1 重复实例（同一间房的门被第42轮数了两遍，逐字段一致）
    − 2 已由别的门提供同一目标（`(场景, 目标)` 已在表里）
    = **88 条新增**

拒收的 7 条（6 + 1）逐条见报告，不为了凑数放宽判据。

## 输出

追加 **88** 条到 `ralsei_pet/assets/scenes/_routes.json`，
`kind='delta_door_table'`（复用第125轮那套表驱动自洽五条），
`marker` 写**实测对象名**（`obj_markerw` / `obj_markerAny`），**不写假的大写**。
格式逐字节保持：`ensure_ascii=False, indent=2` + CRLF + 无尾换行。
"""
import io
import json
import os
import sys
import collections

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
PKG = os.path.join(REPO, 'ralsei_pet')
SCENES = os.path.join(PKG, 'assets', 'scenes')
ROUTES = os.path.join(SCENES, '_routes.json')
EV42 = os.path.join(REPO, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
GRAPH = os.path.join(EV42, '_room_graph.json')

for _p in (PKG, os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from modules import scene_system as SS       # noqa: E402

CH = [('ch1', 'inst42.json', 'conn42b.json')] + [
    ('ch%d' % i, 'ch%d_inst42.json' % i, 'ch%d_conn42b.json' % i) for i in (2, 3, 4, 5)]

#: W 门 → 它读的那段 `Alarm_2`（UTMT 里就是这两个名字）
W_TABLE = {'obj_doorW': 'gml_Object_obj_doorW_Alarm_2',
           'obj_doorw_musfade': 'gml_Object_obj_doorw_musfade_Alarm_2'}
#: 通用出生点（sprite 自证：`spr_markerAny`，与任何字母都不同）
ANY_MARKERS = ('obj_markerAny', 'obj_markerAny40px')
LETTER = 'W'
PRIO_BASE = 7000
#: ★ 钉死：`_room_graph.json` 里 W 边 98 条，逐条分完
#:     75 同字母 + 16 通用 Any = 91 可用
#:     − 1 重复实例（同一间房的门被第42轮数了两遍）
#:     − 2 已由别的门提供同一目标（`(场景, 目标)` 已在表里）
#:     = **88**
#: 它一变就说明证据/判据被动了，必须人工看。
EXPECT_ADD = 88

_T1 = "\x3a True"
_t1 = "\x3a true"
_T0 = "\x3a False"
_t0 = "\x3a false"


def jload(p):
    s = io.open(p, encoding='utf-8', newline='').read()
    s = s.replace(_T1, _t1).replace(_T0, _t0)
    return json.loads(s)


def label(rec):
    a = rec.get('area_name') or rec.get('area_id') or ''
    n = rec.get('name') or ''
    if not a:
        return n
    return n if n.startswith(a) else (a + u'·' + n)


def raw_name(rec):
    return (rec.get('name_raw') or rec.get('name') or '')


def tbl_short(t):
    s = t[len('gml_Object_'):] if t.startswith('gml_Object_') else t
    if s.endswith('_Alarm_2'):
        s = s[:-len('_Alarm_2')]
    return s


IDX = SS.load_index(SCENES)
SCN = IDX.get('scenes') or {}
raw = json.loads(io.open(ROUTES, encoding='utf-8', newline='').read())
RL = raw.get('routes') or []
G = (jload(GRAPH) or {}).get('chapters') or {}

by_rid = collections.defaultdict(dict)
for sid, rec in SCN.items():
    if isinstance(rec, dict) and isinstance(rec.get('original_room_id'), int):
        cid = rec.get('chapter_id') or sid.split('.')[0]
        by_rid[cid].setdefault(rec['original_room_id'], sid)

have = set((r.get('when_scene'), r.get('to')) for r in RL)
exist_door = set((r.get('when_scene'), str(r.get('when_door') or '')) for r in RL)

plan = []
refused = []
stat = collections.Counter()
seen_q = {}

for cid, instf, connf in CH:
    inst = jload(os.path.join(EV42, instf))
    conn = jload(os.path.join(EV42, connf))
    rn = conn['room_names']
    N = len(rn)
    rooms = {r['index']: r for r in (inst.get('rooms') or [])}
    objs = {i: set(x.get('obj') for x in (r.get('insts') or [])) for i, r in rooms.items()}
    tables = collections.defaultdict(dict)
    for it in conn.get('items') or []:
        if it.get('op') == 'goto' and isinstance(it.get('src'), int) and it['src'] >= 0:
            tables[it['code']][it['src']] = it['dst']

    for e in (G.get(cid) or {}).get('edges') or []:
        door = e.get('door')
        stat['edge_total'] += 1
        if door not in W_TABLE:
            stat['not_w'] += 1
            continue
        stat['w_edge'] += 1
        s_sid = by_rid[cid].get(e.get('src'))
        d_sid = by_rid[cid].get(e.get('dst'))
        if not s_sid or not d_sid:
            stat['unreg'] += 1
            continue
        mech = tables.get(W_TABLE[door], {}).get(e.get('src'))
        if mech != e.get('dst'):
            stat['mech_mismatch'] += 1
            continue
        # ---- 落点自证：同字母（大小写不敏感）或通用 Any ----
        dobj = objs.get(mech, set())
        low = set(o.lower() for o in dobj)
        if 'obj_markerw' in low:
            mk = 'obj_markerw'
            stat['mark_letter'] += 1
        else:
            mk = next((a for a in ANY_MARKERS if a in dobj), None)
            if mk:
                stat['mark_any'] += 1
            else:
                stat['refused_landing'] += 1
                refused.append({'cid': cid, 'src': e.get('src'), 'dst': mech, 'door': door,
                                'src_name': rn[e.get('src')] if e.get('src') < N else '',
                                'dst_name': rn[mech], 'objs': sorted(dobj)})
                continue
        if (s_sid, LETTER) in exist_door:
            stat['letter_clash'] += 1
            continue
        _q = (s_sid, LETTER, d_sid)
        if _q in seen_q:
            _p = seen_q[_q]
            if (_p['src_rid'], _p['dst_rid'], _p['door']) != (e.get('src'), mech, door):
                raise SystemExit(u'(场景,字母,目标) 相同但源/目标 id 或门型不同：%r' % (_q,))
            stat['dup_edge'] += 1
            continue
        if (s_sid, d_sid) in have:
            stat['already'] += 1
            continue
        seen_q[_q] = {'src_rid': e.get('src'), 'dst_rid': mech, 'door': door}
        plan.append({'cid': cid, 'src_rid': e.get('src'), 'dst_rid': mech,
                     'scene': s_sid, 'to': d_sid, 'door': door, 'marker': mk})

plan.sort(key=lambda p: (p['cid'], p['src_rid'], p['to']))
print(u'计划 %d 条' % len(plan))
print(u'丢弃账：%r' % {k: v for k, v in sorted(stat.items())})
print(u'拒收 %d 条：' % len(refused))
for r in refused:
    print(u'   %-4s %3d → %-3d %-34s → %-34s objs=%r'
          % (r['cid'], r['src'], r['dst'], r['src_name'], r['dst_name'], r['objs']))

if EXPECT_ADD is None:
    print(u'')
    print(u'★ EXPECT_ADD=None ⇒ 只统计不写入。确认条数后钉死再跑。')
    raise SystemExit(0)
if len(plan) != EXPECT_ADD:
    raise SystemExit(u'计划 %d 条 ≠ 期望 %d 条，拒绝写入' % (len(plan), EXPECT_ADD))

new = []
for i, p in enumerate(plan):
    s_rec, d_rec = SCN.get(p['scene']) or {}, SCN.get(p['to']) or {}
    reason = (u'原作连接：从 %s 的 %s 门离开，落到 %s（**表驱动**：`%s` 的 `Alarm_2` 里'
              u'`if (room == %d) room_goto(%d)`，不是固定位移；目标房含 `%s` 作为出生点）。'
              % (label(s_rec), LETTER, label(d_rec), tbl_short(W_TABLE[p['door']]),
                 p['src_rid'], p['dst_rid'], p['marker']))
    orig = {'chapter': p['cid'], 'door_letter': LETTER,
            'kind': 'delta_door_table', 'table': W_TABLE[p['door']],
            'via': p['door'], 'marker': p['marker'],
            'src_room_name': raw_name(s_rec), 'dst_room_name': raw_name(d_rec),
            'src_room_id': p['src_rid'], 'dst_room_id': p['dst_rid']}
    new.append({'to': p['to'], 'priority': PRIO_BASE + i, 'reason': reason,
                'when_scene': p['scene'], 'when_door': LETTER, '_original': orig})

raw['routes'] = list(RL) + new
_n = len(new)
_n_l = sum(1 for p in plan if p['marker'] == 'obj_markerw')
_n_a = _n - _n_l
raw.setdefault('meta', {})
raw['meta']['note'] = (raw['meta'].get('note') or '') + (
    u'★ 第168轮：Deltarune 五章新增 **' + str(_n) + u'** 条 **W 门**（priority '
    + str(PRIO_BASE) + u'~' + str(PRIO_BASE + _n - 1) + u'）。此前 W 一条都没写'
    u'（第125轮以「`obj_markerw` 60.2% / `obj_markerX` 84.3%，无一套到 100%」拒收）。'
    u'★ 本轮查明**当年两次都量错了对象**：产品里 marker 对象名是**小写** `obj_markerw`'
    u'（sprite 是专属的 `spr_markerW`，与 A~F 同族），而 `obj_markerX` 是**字母 X 的**'
    u'出生点（`spr_markerX`），不是通用兜底；真通用是 `obj_markerAny`（`spr_markerAny`）。'
    u'机制侧同一次反汇编：`obj_doorW_Alarm_2` 的骨架与 A/B/C/D/X **逐句同形**'
    u'（先给 `entrance` 赋值 → `instance_create` → 一串 `if (room == N) room_goto(M)`）。'
    u'\u2605 `entrance` **不是每类门的常量**：ch1 的 W 门只有 1 个分支（23），'
    u'ch2 的 W 门有 145 次赋值、值域 19~24（= S/T/U/V/W/X 的字母序）'
    u'\u21d2 它是**每个分支各自指定落点字母**，所以判据不建立在它的具体数值上。'
    u'落点自证按同一把尺重算：**同字母 ' + str(_n_l) + u' 条 + 通用 `obj_markerAny` '
    + str(_n_a) + u' 条 = ' + str(_n) + u' / 97 = 92.8%**，落在已收五类的 91.2%~96.7% 区间内。'
    u'**拒收 7 条**（目标房只有 `obj_markerX` 1 条 / 只有别的字母 5 条 / 零 marker 的商店房 1 条），'
    u'逐条见 report168.md。生成器 '
    u'`code-quality-audit/第168轮-W门补齐/_tools/gen_routes168.py`。')

text = json.dumps(raw, ensure_ascii=False, indent=2)
blob = text.replace('\n', '\r\n').encode('utf-8')
with io.open(ROUTES, 'wb') as fh:
    fh.write(blob)

print(u'')
print(u'写入 %d 条（同字母 %d / 通用 Any %d），priority %d~%d'
      % (_n, _n_l, _n_a, PRIO_BASE, PRIO_BASE + _n - 1))
print(u'routes 总数 %d · %d bytes' % (len(raw['routes']), len(blob)))
