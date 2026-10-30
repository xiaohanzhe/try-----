# -*- coding: utf-8 -*-
u"""第125轮 · 把 ch1~ch5 的 **D 门（−2）** 与 **X 门（表驱动）** 接进产品路由表。

## 为什么这一轮

第124轮末的可达账暴露：ch1~ch5 有出边的场景只有 105/127/23/22/20，
而场景数 128/236/187/261/201。查根因（**不是"没数据"**）：

`_room_graph.json`（第42轮反编译合成）里 ch1~ch5 共有 **782** 条边，
而产品 `_routes.json` 只转出 **443** 条 —— 差在**门型**：

第44轮的生成器只编三种位移门：
    obj_doorA +1 · obj_doorB −1 · obj_doorC +2
并**明确拒绝**了 `obj_doorD`（"位移未定，实测 +2 只有 33%，证据不足，不猜"）
与 `obj_doorW`/`obj_doorX`（"表驱动双向，需读对象代码"）。

而 `graph42.py` 的机制表（同样来自 Alarm 反汇编）写的是：
    obj_doorD → **−2** ｜ obj_doorX / obj_doorX_musfade → **表驱动** `{src: dst}`

⇒ 这一轮把这两种门补上，**前提是先独立验证**（见 §验证）。

## 验证（判据沿用第44轮对 A/B/C 用过的同一条）

★ **目标房必须含 `obj_marker<同字母>`** —— 位移只是先验，落点是独立验证。

    组  实例  有目标  命中 marker   命中率
    D     78     74        71       95.9%
    X    129     94        94      100.0%
    W    234     97         0        0.0%（marker 名是**小写** `obj_markerw`；
                                      换成 `obj_markerX` 也只有 84.3%）

⇒ **D 与 X 收，W 不收**（W 的两套 marker 都到不了 100%，"证据不足不猜"这条纪律照旧）。
⇒ D 的 3 个例外全部落在 **backup / test 房**
   （`room_dw_city_traffic_3_backup` / `room_test_climb_new` / `room_hospital_room2`），
   如实不写。

## 准入三闸

  ① 机制已证：D = −2（第42轮 Alarm + 第123轮 ut 同型互证）；X = 表驱动（读 `Alarm_2`）
  ② 落点自证：目标房含 `obj_marker<同字母>`
  ③ 产品侧不冲突：同场景同 `when_door` 只一条；新段 priority 从 **5000** 起
     （既有段 110~2478 / OneShot 3000+ / ut 4000+，5000 是干净区间）

## 输出

追加 **139** 条（D 56 / X 83）到 `ralsei_pet/assets/scenes/_routes.json`，
并在 `meta.note` 追加一段说明。**格式逐字节保持**：CRLF + indent=2 + 无尾换行。

★ 139 而不是 159：证据里有 **20 条重复边**（同一扇门被第42轮数了 N 遍，12 组、
最多一组 4 行，逐字段一致）。去重键是**三元** `(场景, 字母, 目标)` ——
不能只用 `(场景, 目标)`：同房间两扇**不同的门**指向同一目标是原作事实
（第123轮 `room_water12` 已裁定），按二元去重会砍掉 4 条真连接（第一版就砍到 155）。
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

#: 已证位移门（第42轮 Alarm 反汇编；`obj_doorD` 与第123轮 ut 的 −2 同型）
DOOR_DELTA = {'obj_doorD': -2, 'obj_doorD_musfade': -2}
#: 表驱动门 → 它读的那段 Alarm_2
DOOR_TABLE = {'obj_doorX': 'gml_Object_obj_doorX_Alarm_2',
              'obj_doorX_musfade': 'gml_Object_obj_doorX_musfade_Alarm_2'}
#: ★ 证据不足、**本轮明确不写**的门型（写进 reason 之外的统计里，供 check 对账）
REFUSED = {'obj_doorW': 'obj_markerw 仅 60.2%、obj_markerX 84.3%，无一套到 100%',
           'obj_doorw_musfade': '同上'}
PRIO_BASE = 5000
EXPECT_ADD = 139


def letter_of(o):
    for k in ('obj_doorD', 'obj_doorD_musfade', 'obj_doorX', 'obj_doorX_musfade'):
        if o == k:
            return k[len('obj_door'):][:1].upper()
    return None


def tbl_short(t):
    u"""`gml_Object_obj_doorX_musfade_Alarm_2` → `obj_doorX_musfade`（只给 reason 读）。"""
    s = t[len('gml_Object_'):] if t.startswith('gml_Object_') else t
    if s.endswith('_Alarm_2'):
        s = s[:-len('_Alarm_2')]
    return s


def jload(p):
    s = io.open(p, encoding='utf-8', newline='').read()
    return json.loads(s.replace(': True', ': true').replace(': False', ': false'))


def label(rec):
    u"""人读标签（只给 `reason` 用）。

    ★ 坑：Deltarune 五章的 `name` **本身已经含区名**（`我的城堡镇·area_1`），
    区名又在 `area_name`（`我的城堡镇`）⇒ 无脑拼 `area_name + '·' + name`
    会产出「我的城堡镇·我的城堡镇·area_1」。实测 2,166 个场景里 **1,002** 个
    `name.startswith(area_name)`，所以先判前缀再决定拼不拼。
    """
    a = rec.get('area_name') or rec.get('area_id') or ''
    n = rec.get('name') or ''
    if not a:
        return n
    if n.startswith(a):
        return n
    return a + u'·' + n


def raw_name(rec):
    u"""★ 原作房名（`_original.src_room_name` 要的是这个，不是显示名）。

    `name` 已被改写成**人读标签**（`我的城堡镇·area_1`），原作房名在 `name_raw`
    （`room_dw_castle_area_1`）。第124轮已实测：`name_raw` 与 `_room_graph.json`
    的 `src_name` **相同 686 / 不同 0**；另有 89 个锚点场景 `name_raw` 为 None。
    ⇒ 缺 `name_raw` 时回落 `name`（锚点场景本来就不在原作房间数组里）。
    """
    return (rec.get('name_raw') or rec.get('name') or '')


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
stat = collections.Counter()
#: ★ 同一 (场景, 字母) 在 `_room_graph.json` 里会**重复若干次**（同 src 同 dst 同 via，
#:   逐字段一致）——那是第42轮合成时同一扇门被数了 N 遍，不是不同的门。
#:   实测 12 组、多出 20 行（最大一组 4 行）。这里做**严格去重**：只打平完全一致的，
#:   一旦 (scene,字母,to) 相同但 src/dst id 不同 ⇒ 直接报错（那是真冲突，必须人工看）。
seen_q = {}
for cid, instf, connf in CH:
    ip, cp = os.path.join(EV42, instf), os.path.join(EV42, connf)
    if not os.path.isfile(ip):
        raise SystemExit(u'缺证据 %s' % ip)
    inst, conn = jload(ip), jload(cp)
    rooms = {r['index']: r for r in (inst.get('rooms') or [])}
    objs = {i: {x.get('obj') for x in (r.get('insts') or [])} for i, r in rooms.items()}
    tables = collections.defaultdict(dict)
    for it in conn.get('items') or []:
        if it.get('op') == 'goto' and isinstance(it.get('src'), int) and it['src'] >= 0:
            tables[it['code']][it['src']] = it['dst']

    for e in (G.get(cid) or {}).get('edges') or []:
        door = e.get('door')
        stat['edge_total'] += 1
        if door in REFUSED:
            stat['refused_W'] += 1
            continue
        if door not in DOOR_DELTA and door not in DOOR_TABLE:
            stat['other'] += 1
            continue
        s_sid = by_rid[cid].get(e.get('src'))
        d_sid = by_rid[cid].get(e.get('dst'))
        if not s_sid or not d_sid:
            stat['unreg'] += 1
            continue
        if door in DOOR_DELTA:
            mech_tgt, how = e.get('src') + DOOR_DELTA[door], 'delta'
        else:
            mech_tgt, how = tables.get(DOOR_TABLE[door], {}).get(e.get('src')), 'table'
        if mech_tgt != e.get('dst'):
            stat['mech_mismatch'] += 1
            continue
        # ★ 注意：**不按 (scene, to) 去重**。同一房间两扇**不同的门**指向同一目标
        #   是合法的（第123轮 `room_water12` 两扇门同指 `room_water11` 已裁定并存，
        #   去重键因此升为三元）。第一版加了这道闸 ⇒ 159 被砍到 155，
        #   砍掉的 4 条全是"另一扇门也去那"的真连接。挡重用的是**同字母**，见下。
        L = door[len('obj_door'):][:1].upper()
        if 'obj_marker' + L not in objs.get(mech_tgt, set()):
            stat['no_marker'] += 1
            continue
        if (s_sid, L) in exist_door:
            stat['letter_clash'] += 1
            continue
        _q = (s_sid, L, d_sid)
        if _q in seen_q:
            _prev = seen_q[_q]
            if (_prev['src_rid'], _prev['dst_rid'], _prev['door']) != (
                    e.get('src'), e.get('dst'), door):
                raise SystemExit(u'(场景,字母,目标) 相同但源/目标 id 或门型不同：%r' % (_q,))
            stat['dup_edge'] += 1
            continue
        seen_q[_q] = {'src_rid': e.get('src'), 'dst_rid': e.get('dst'), 'door': door}
        plan.append({'cid': cid, 'src_rid': e.get('src'), 'dst_rid': e.get('dst'),
                     'scene': s_sid, 'to': d_sid, 'letter': L, 'door': door,
                     'how': how})

plan.sort(key=lambda p: (p['cid'], p['src_rid'], p['letter'], p['to']))
if len(plan) != EXPECT_ADD:
    raise SystemExit(u'计划 %d 条 ≠ 期望 %d 条，拒绝写入' % (len(plan), EXPECT_ADD))

new = []
for i, p in enumerate(plan):
    s_rec, d_rec = SCN.get(p['scene']) or {}, SCN.get(p['to']) or {}
    if p['how'] == 'delta':
        reason = (u'原作连接：从 %s 的 %s 门离开，落到 %s 的 %s 落点'
                  u'（房间数组下标 %+d；目标房含 `obj_marker%s`）。'
                  % (label(s_rec), p['letter'], label(d_rec), p['letter'],
                     DOOR_DELTA[p['door']], p['letter']))
        orig = {'chapter': p['cid'], 'door_letter': p['letter'],
                'room_delta': DOOR_DELTA[p['door']],
                'src_room_name': raw_name(s_rec),
                'dst_room_name': raw_name(d_rec),
                'src_room_id': p['src_rid'], 'dst_room_id': p['dst_rid'],
                'via': p['door'], 'marker': 'obj_marker' + p['letter']}
    else:
        reason = (u'原作连接：从 %s 的 %s 门离开，落到 %s（**表驱动**：`%s` 的 `Alarm_2` '
                  u'里按源房查 `{房间→目标}`，不是固定位移；目标房含 `obj_marker%s`）。'
                  % (label(s_rec), p['letter'], label(d_rec),
                     tbl_short(DOOR_TABLE[p['door']]), p['letter']))
        orig = {'chapter': p['cid'], 'door_letter': p['letter'],
                'kind': 'delta_door_table', 'table': DOOR_TABLE[p['door']],
                'via': p['door'], 'marker': 'obj_marker' + p['letter'],
                'src_room_name': raw_name(s_rec),
                'dst_room_name': raw_name(d_rec),
                'src_room_id': p['src_rid'], 'dst_room_id': p['dst_rid']}
    new.append({'to': p['to'], 'priority': PRIO_BASE + i, 'reason': reason,
                'when_scene': p['scene'], 'when_door': p['letter'], '_original': orig})

raw['routes'] = list(RL) + new
_n_add = len(new)
_n_d = sum(1 for n in new if n['when_door'] == 'D')
_n_x = sum(1 for n in new if n['when_door'] == 'X')
_note_add = (u'★ 第125轮：Deltarune 五章新增 **' + str(_n_add) + u'** 条（D 门 '
             + str(_n_d) + u' / X 门 ' + str(_n_x) + u'，priority '
             + str(PRIO_BASE) + u'~' + str(PRIO_BASE + _n_add - 1) + u'）。'
             u'此前只有 A(+1)/B(−1)/C(+2)，`obj_doorD` 与 `obj_doorX` 被第44轮以"证据不足"拒收。'
             u'本轮把两种门补齐，并**先独立验证**再写：D 的位移 = −2（第42轮 Alarm 反编译，'
             u'与第123轮 ut 的 `obj_doorD` 同型），X 走表驱动（读 `Alarm_2` 的 `{房间→目标}`）；'
             u'两者都要求**目标房含 `obj_marker<同字母>`**（D 71/74、X 94/94 命中）。'
             u'★ **W 门不收**：`obj_markerw` 仅 60.2%、`obj_markerX` 84.3%，无一套到 100%，'
             u'"证据不足不猜"这条纪律照旧。D 的 3 个例外全落在 backup/test 房，如实不写。'
             u'生成器 `code-quality-audit/第125轮-D门与X门补齐/_tools/gen_routes125.py`。')
n0 = raw['meta'].get('note') or ''
raw['meta']['note'] = n0 + _note_add

text = json.dumps(raw, ensure_ascii=False, indent=2)
blob = text.replace('\n', '\r\n').encode('utf-8')
with io.open(ROUTES, 'wb') as fh:
    fh.write(blob)

print(u'写入 %d 条（D %d / X %d），priority %d~%d'
      % (len(new), sum(1 for n in new if n['when_door'] == 'D'),
         sum(1 for n in new if n['when_door'] == 'X'),
         PRIO_BASE, PRIO_BASE + len(new) - 1))
print(u'routes 总数 %d' % len(raw['routes']))
print(u'丢弃账：', {k: v for k, v in sorted(stat.items())})
