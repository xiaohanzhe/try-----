# -*- coding: utf-8 -*-
"""第171轮 · 把 `verdict171.json` 里 R6_ADD 的边落进 `_routes.json`。

与第170轮 `apply170.py` 同规矩：
  1. **无损往返自检**：`json.dumps(indent=2)` 归一 CRLF 后必须与原文逐字相同，否则拒写；
  2. **重复边不加**：与既有 `(when_scene, to)` 相同的候选直接剔除（写进 skipped）；
  3. 写 `.new` → 复读 → 断言条数/无 BOM → `os.replace`；EOL 保持 CRLF。

字段口径（对齐第168~170轮已落地的 196 条）：
  `_original` = chapter / door_letter / kind / table / via / marker /
                src_room_name / dst_room_name / src_room_id / dst_room_id /
                entrance / branch_letter / door_x / door_y / axis(可选) /
                door_x_all / x_range|y_range / batch
  `marker` 的选取尺＝落点字母（`chr(entrance+64)`）小写命中 → 否则 `obj_markerany`
            → 否则 `obj_markerany40px` → 否则 None（**不猜**）
用法: python apply171.py [--dry]
"""
import collections
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
EV = os.path.join(ROUND, '_evidence')
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
ROUTES = os.path.join(SCENES, '_routes.json')

PRIO_BASE = 7200
BATCH = 171
CHS = ['ch1', 'ch2', 'ch3', 'ch4', 'ch5']
TABLE = {'obj_doorw': 'gml_Object_obj_doorW_Alarm_2',
         'obj_doorw_musfade': 'gml_Object_obj_doorw_musfade_Alarm_2'}


def load(p):
    with io.open(p, encoding='utf-8') as fh:
        return json.load(fh)


def marker_of(mk_names, ent):
    u"""mk_names: {lower: 真名}。按落点字母取 marker，取不到就 any，再取不到 None。"""
    letter = chr(ent + 64).lower() if isinstance(ent, int) and 1 <= ent <= 26 else None
    if letter and ('obj_marker' + letter) in mk_names:
        return mk_names['obj_marker' + letter]
    for k in ('obj_markerany', 'obj_markerany40px'):
        if k in mk_names:
            return mk_names[k]
    return None


def main():
    dry = '--dry' in sys.argv
    vd = load(os.path.join(EV, 'verdict171.json'))
    adds = [r for r in vd['rows'] if r['verdict'] == 'R6_ADD']
    if not adds:
        print('没有可补的边')
        return 1

    # marker 真名（大小写保真）与**按 via 分开**的 x 分布
    mk_names = collections.defaultdict(dict)
    door_xs = collections.defaultdict(lambda: collections.defaultdict(list))
    for ch in CHS:
        d = load(os.path.join(EV, 'inst171.%s.json' % ch))
        for r in d['rooms']:
            for i in r.get('insts') or []:
                o = (i.get('obj') or '')
                lo = o.lower()
                if lo.startswith('obj_marker'):
                    mk_names[(ch, r['name'])][lo] = o
                if lo in TABLE:
                    door_xs[(ch, r['name'])][lo].append(i.get('x'))

    txt = io.open(ROUTES, encoding='utf-8', newline='').read()
    data = json.loads(txt)
    routes = data['routes'] if isinstance(data, dict) else data

    # ---- 无损往返自检（不通过就不许写）
    rt = json.dumps(data, ensure_ascii=False, indent=2)
    if rt.replace('\r\n', '\n') != txt.replace('\r\n', '\n'):
        print('[FAIL] 无损往返自检不通过：dump 出来的文本与原文不同 ⇒ 拒绝落盘')
        return 2

    old_pairs = set((r.get('when_scene'), r.get('to')) for r in routes)
    added, skipped = [], []
    for r in adds:
        key = (r['sid_s'], r['sid_t'])
        if key in old_pairs:
            skipped.append({'why': 'pair_exists', 'pair': list(key)})
            continue
        via = (r.get('via_fix') or r['via'])
        ent = r.get('ent')
        mk = marker_of(mk_names.get((r['ch'], r['dst_room_name'])) or {}, ent)
        m = r.get('match') or {}
        door = m.get('door') or [None, None]
        rng = m.get('range')
        # ★ `door_x_all` 必须是**这条规则自己那个 via** 的全部 x。
        #   第一版把 obj_doorW 与 obj_doorw_musfade 合在一起算，
        #   town_mid 就记成了 [301,1082,1740]（1082 其实是 musfade 那扇）⇒ 判据 B2 报红。
        xs = (door_xs.get((r['ch'], r['src_room_name'])) or {}).get(via.lower()) or []
        dup_x = len(xs) != len(set(xs))
        orig = collections.OrderedDict()
        orig['chapter'] = r['ch']
        orig['door_letter'] = 'W'
        orig['kind'] = 'delta_door_table'
        orig['table'] = TABLE[via.lower()]
        orig['via'] = via
        orig['marker'] = mk
        orig['src_room_name'] = r['src_room_name']
        orig['dst_room_name'] = r['dst_room_name']
        orig['src_room_id'] = r['src_room']
        orig['dst_room_id'] = r['dst']
        orig['entrance'] = ent
        orig['branch_letter'] = chr(ent + 64) if isinstance(ent, int) else None
        if dup_x and door[1] is not None:
            # 同房多扇门的 x 撞了 ⇒ 必须用 y 消歧（第170轮 §171.5 同一条教训）
            orig['axis'] = 'y'
            orig['door_y'] = door[1]
            orig['door_x'] = None
        else:
            orig['door_x'] = door[0]
            orig['door_y'] = door[1]
        orig['door_x_all'] = sorted(set(x for x in xs if x is not None)) or None
        if rng:
            orig['%s_range' % (m.get('axis') or 'x')] = [rng[0], rng[1]]
        orig['batch'] = BATCH

        reason = (u'原作连接（**分支级**，第171轮按「逐房间实例表」补）：从 %s 的 `%s` '
                  u'离开，落到 %s（`if (room == %d)` 分支 `%s`，`entrance=%s`，'
                  u'门实例在 %r）。此前表里没有这条边 ⇒ 门查不到目标 ⇒ 不建门'
                  u'（按 E 没反应）。' % (
                      r['src_room_name'], via, r['dst_room_name'], r['src_room'],
                      (r.get('cond') or u'无位置条件'), ent, door,
                      )).replace(u'(()', u'(')
        added.append({
            'to': r['sid_t'],
            'priority': PRIO_BASE + len(added),
            'reason': reason,
            'when_scene': r['sid_s'],
            'when_door': 'W',
            '_original': orig,
        })

    print('可落 %d 条，剔除 %d 条' % (len(added), len(skipped)))
    for s in skipped:
        print('   跳过', s)
    if dry:
        print(json.dumps(added[:2], ensure_ascii=False, indent=1))
        return 0

    routes.extend(added)
    out = json.dumps(data, ensure_ascii=False, indent=2)
    if '\r\n' in txt:
        out = out.replace('\n', '\r\n')
    tmp = ROUTES + '.new'
    with io.open(tmp, 'w', encoding='utf-8', newline='') as fh:
        fh.write(out)
    back = json.loads(io.open(tmp, encoding='utf-8').read())
    rb = back['routes'] if isinstance(back, dict) else back
    assert len(rb) == len(routes), '复读条数不符 %d vs %d' % (len(rb), len(routes))
    with open(tmp, 'rb') as fh:
        assert not fh.read(3) == b'\xef\xbb\xbf', '产物不许带 BOM'
    os.replace(tmp, ROUTES)
    print('落盘：%d → %d 条；%d B → %d B' % (
        len(routes) - len(added), len(routes),
        len(txt.encode('utf-8')), len(out.encode('utf-8'))))
    return 0


if __name__ == '__main__':
    sys.exit(main())
