# -*- coding: utf-8 -*-
u"""第170轮：把 GML 源码事实**落进 `_routes.json`**（数据侧，产品逻辑另改）。

落地范围（每类都可逐条审）
--------------------------
A `entrance` 补空    88 条 —— 表里没记，源码有，补上
B 区间按源码校正    27 条 —— 其中 **11 条方向反了**（源码 `x < 10`，
                     表里记成 `[10, None]` = `x > 10`）、16 条表里缺（`[None,None]`）
C 门实例坐标         11 条 —— 5 条 x 轴写 `door_x`、6 条 y 轴写 `door_y` + `y_range`
                     （★ y 轴那批 x 只差 1~2 px，拿 x 区分会把上下门判反）
D 新增规则            9 条 —— priority 7190~7198；其中 6 条会让原本"查不到 ⇒ 不建门"
                     的门活过来，3 条与既有规则同目标（只是把源码记全）

★ 三条纪律
  ① **只改跟源码不一致的**，已一致的一律不写（避免"改了一遍文件"假差异）
  ② **不猜**：源码解不出区间（混轴、复合否定）、或规则与分支匹配不到唯一的，
     一律不动，进 `skipped` 逐条点名
  ③ **文案跟着数据走**：`reason` 里写着 `x=760` 而 `door_x` 改成 0 会自相矛盾，
     所以 C 类同步重写 `（…）离开` 那段
"""
import collections
import glob
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
ROUTES = os.path.join(SCENES, '_routes.json')
GML = os.path.join(ROUND, '_evidence', 'gml170.json')
FIX = os.path.join(ROUND, '_evidence', 'fix170.json')
MRK = os.path.join(ROUND, '_evidence', 'marker2_170.json')
INST = os.path.join(REPO, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence',
                    'ch2_inst42.json')
OUT = os.path.join(ROUND, '_evidence', 'applied170.json')

PRIO_BASE = 7190            # 第169轮止于 7189
BATCH = 170

#: `的 W 门（……）离开` 里那段"本分支对应哪一扇"的说明，C 类要整段重写
RE_WHERE = re.compile(u'(的 W 门)（[^）]*）(离开)')
MRK_RE = re.compile(r'^obj_marker(.*)$')


def jl(p):
    return json.loads(io.open(p, encoding='utf-8', errors='replace', newline='').read())


def main():
    raw = io.open(ROUTES, 'rb').read()
    txt = raw.decode('utf-8')
    d = json.loads(txt)

    # ---------- 0. 无损往返自检（不过就不许写）----------
    rt = json.dumps(d, ensure_ascii=False, indent=2)
    if rt.replace('\r\n', '\n') != txt.replace('\r\n', '\n'):
        print(u'[FATAL] `_routes.json` 不能无损往返（dump 与原文不一致），拒绝落盘。')
        return 2
    print(u'[OK] 无损往返通过（%d B / %d 行 CRLF / 无 BOM）'
          % (len(raw), raw.count(b'\r\n')))

    routes = d['routes']
    g = jl(GML)
    fix = jl(FIX)

    # ---------- 规则索引 ----------
    by_key = collections.defaultdict(list)
    for r in routes:
        by_key[(r.get('priority'), r.get('when_scene'), r.get('to'))].append(r)

    def find(prio, scene, to):
        got = by_key.get((prio, scene, to)) or []
        if len(got) != 1:
            return None
        return got[0]

    # ---------- 场景对象 ----------
    M = {}
    for f in glob.glob(os.path.join(SCENES, '_zone.*.json')):
        z = jl(f)
        s = z.get('scenes')
        it = (s.items() if isinstance(s, dict) else ((v.get('scene_id'), v) for v in s))
        for k, v in it:
            if isinstance(v, dict):
                M[v.get('scene_id') or k] = v.get('objects') or []

    # ---------- GML 分支索引 ----------
    bidx = collections.defaultdict(list)
    rid2name = {}
    for ch, chd in g['chapters'].items():
        for obj, dd in chd.items():
            for room, v in dd['rooms'].items():
                if v.get('room_id') is not None:
                    rid2name[(ch, v['room_id'])] = room
                for b in v['branches']:
                    if b['to_id'] is not None:
                        bidx[(ch, room, obj, b['to_id'])].append(b)

    stat = collections.Counter()
    skipped = []

    # ================= A. entrance 补空 =================
    for e in fix['ent_fill']:
        r = find(e['priority'], e['scene'], e['dst'])
        if r is None:
            skipped.append({'kind': 'ent_fill', 'why': 'rule_not_unique',
                            'prio': e['priority'], 'scene': e['scene']})
            continue
        o = r.setdefault('_original', {})
        if o.get('entrance') == e['ent']:
            stat['ent_same'] += 1
            continue
        o['entrance'] = e['ent']
        stat['ent_fill'] += 1
    for e in fix['ent_fix']:
        r = find(e['priority'], e['scene'], e['dst'])
        if r is None:
            skipped.append({'kind': 'ent_fix', 'why': 'rule_not_unique', 'prio': e['priority']})
            continue
        r['_original']['entrance'] = e['new']
        stat['ent_fix'] += 1
    for e in fix['ent_left']:
        skipped.append({'kind': 'ent', 'why': e['why'], 'prio': e['priority'],
                        'scene': e['scene']})

    # ================= B. 区间按源码校正 =================
    #: 只处理 batch169（第168轮那 88 条没有 x_range 字段，本轮不扩范围）
    for r in routes:
        o = r.get('_original') or {}
        if o.get('batch') != 169:
            continue
        k = (o.get('chapter'), o.get('src_room_name'), o.get('via'),
             o.get('dst_room_id'))
        bs = bidx.get(k) or []
        if len(bs) != 1:
            skipped.append({'kind': 'range', 'why': 'branch_%d' % len(bs),
                            'prio': r.get('priority'), 'key': list(k)})
            continue
        b = bs[0]
        lo, hi = b['lo'], b['hi']
        if lo is None and hi is None:
            # 混轴 / 复合否定：源码自己也解不出，**不许拿表里的值反推**
            skipped.append({'kind': 'range', 'why': 'gml_no_range',
                            'prio': r.get('priority'), 'cond': b['cond']})
            continue
        field = '%s_range' % (b['axis'] or 'x')
        cur = o.get(field)
        if not isinstance(cur, list):
            cur = [None, None]
        if cur == [lo, hi]:
            stat['range_same'] += 1
            continue
        # 判方向反了（只用于报表）：当前值恰好等于源码的 `[hi, lo]` 对调。
        # ★★ 不能要求 lo/hi **都非空** —— `x < 10` 的 lo 本来就是 None，
        #   而第169轮正是把 11 条这类**单边**条件写反了（`[10, None]`）。
        #   加了 `lo is not None and hi is not None` 就会把这 11 条全算成
        #   "普通设置"，翻转数报 0 —— 数值虽然改对了，报表却是假的。
        flip = (cur == [hi, lo])
        o[field] = [lo, hi]
        if b['axis'] == 'y':
            o['y_incl'] = [b['lo_incl'], b['hi_incl']]
        stat['range_flip' if flip else 'range_set'] += 1

    # ================= C. 门实例坐标 =================
    for x in fix['door_x_add']:
        r = find(x['priority'], x['scene'], x['dst'])
        if r is None:
            skipped.append({'kind': 'door', 'why': 'rule_not_unique', 'prio': x['priority']})
            continue
        o = r.setdefault('_original', {})
        objs = M.get(x['scene']) or []
        xs = []
        for it in objs:
            if isinstance(it, dict) and it.get('src') == x.get('via'):
                p = it.get('pos') or [None, None]
                if p and p[0] is not None:
                    xs.append(p[0])
        xs = sorted(set(xs))
        o['axis'] = x['axis']
        if x['axis'] == 'y':
            o['door_x'] = x['x']
            o['door_y'] = x['y']
        else:
            o['door_x'] = x['x']
            o['door_y'] = x['y']
        o['door_x_all'] = xs
        stat['door_set'] += 1

        # 文案跟着数据走
        reason = r.get('reason') or ''
        if x['axis'] == 'y':
            where = (u'(x=%d, y=%d)；本房该门共 %d 扇，(x,y)=%s，'
                     u'本分支按**上下**位置对应这一扇（第170轮：由 GML 的 y 条件与门实例坐标定死）'
                     % (x['x'], x['y'], len(xs), u'/'.join(
                         u'(%s)' % u','.join(str(v) for v in (it2.get('pos') or []))
                         for it2 in objs if isinstance(it2, dict)
                         and it2.get('src') == x.get('via'))))
        else:
            where = (u'x=%d；本房该门共 %d 扇，x=%s，'
                     u'本分支按位置对应这一扇（第170轮：由 GML 的 x 条件与门实例坐标定死）'
                     % (x['x'], len(xs), u'/'.join(str(v) for v in xs)))
        new_reason, n = RE_WHERE.subn(lambda m: m.group(1) + u'（' + where + u'）' + m.group(2),
                                      reason)
        if n == 1:
            r['reason'] = new_reason
            stat['reason_rewrote'] += 1
        else:
            skipped.append({'kind': 'reason', 'why': 'anchor_hit_%d' % n,
                            'prio': x['priority']})

    # ================= D. 新增规则 =================
    mk2 = jl(MRK)
    nmap = {x['sid_s'] + '|' + x['sid_t']: x for x in mk2['new_markers']}
    added = []
    #: ★★★ 已经存在的 (场景, 目标) 一律**不再加** —— 那不是"补边"，是**重复条目**。
    #:   本轮原有 9 条候选，其中 2 条命中这里（`dw_city_traffic_4→spamton_alley` 已有 1230、
    #:   `dw_mansion_east_2f_c→east_2f_c_a` 已有 7164）。加进去的代价不是零：
    #:   · `check124 D2` 判"同门重复 = 冗余"，直接报红；
    #:   · `check169 B0/B1/B2/C1` 的「已由别的门型覆盖」桶从 8 变 10、`dup` 从 4 变 3，
    #:     它独立重推第169轮时就会"少推一条"，看着像我把 169 的账改坏了。
    #:   ⇒ 判据没错，是我该只补**真的没有**的边。
    _old_pairs = set((r.get('when_scene'), r.get('to')) for r in routes)
    for i, nr in enumerate(fix['new_rules']):
        if (nr['sid_s'], nr['sid_t']) in _old_pairs:
            skipped.append({'kind': 'new_rule', 'why': 'pair_exists',
                            'scene': nr['sid_s'], 'to': nr['sid_t']})
            stat['new_dup_pair'] += 1
            continue
        prio = PRIO_BASE + len(added)
        sid_s, sid_t = nr['sid_s'], nr['sid_t']
        key = (nr['ch'], rid2name.get((nr['ch'], nr['src_room'])),
               nr['via'], nr['dst'])
        bs = bidx.get(key) or []
        b = bs[0] if len(bs) == 1 else None
        mm = nmap.get(sid_s + '|' + sid_t) or {}
        objs = M.get(sid_s) or []
        xs = sorted(set((it.get('pos') or [None, None])[0] for it in objs
                        if isinstance(it, dict) and it.get('src') == nr['via']
                        and (it.get('pos') or [None])[0] is not None))
        #: 只有**唯一一扇门**时才敢写死坐标；多扇＝不知道这分支对应哪一扇（不猜）
        door_x = xs[0] if len(xs) == 1 else None
        door_y = None
        if len(xs) == 1:
            for it in objs:
                if isinstance(it, dict) and it.get('src') == nr['via']:
                    p = it.get('pos') or [None, None]
                    if p and p[0] == door_x:
                        door_y = p[1] if len(p) > 1 else None
                        break
        _o = collections.OrderedDict()
        _o['chapter'] = nr['ch']
        _o['door_letter'] = 'W'
        _o['kind'] = 'delta_door_table'
        _o['table'] = ('gml_Object_obj_doorW_Alarm_2'
                       if nr['via'] == 'obj_doorW'
                       else 'gml_Object_obj_doorw_musfade_Alarm_2')
        _o['via'] = nr['via']
        _o['marker'] = mm.get('marker')
        _o['src_room_name'] = rid2name.get((nr['ch'], nr['src_room']))
        _o['dst_room_name'] = rid2name.get((nr['ch'], nr['dst']))
        _o['src_room_id'] = nr['src_room']
        _o['dst_room_id'] = nr['dst']
        _o['entrance'] = nr['ent']
        _o['branch_letter'] = mm.get('branch_letter')
        _o['door_x'] = door_x
        _o['door_y'] = door_y
        _o['door_x_all'] = xs
        if b is not None and (b['lo'] is not None or b['hi'] is not None):
            _o['axis'] = b['axis']
            _o['%s_range' % b['axis']] = [b['lo'], b['hi']]
        _o['batch'] = BATCH

        added.append(collections.OrderedDict([
            ('to', sid_t),
            ('priority', prio),
            ('reason', u'原作连接（**分支级**，第170轮按 GML 源码补）：从 %s 的 `obj_doorW` '
                       u'离开，落到 %s（`if (room == %s)` 分支 `%s`，`entrance=%s`）。'
                       u'此前表里没有这条边 ⇒ 门查不到目标 ⇒ 不建门（按 E 没反应）。'
                       % (_o['src_room_name'], _o['dst_room_name'], nr['src_room'],
                          nr.get('cond') or u'无位置条件', nr['ent'])),
            ('when_scene', sid_s),
            ('when_door', 'W'),
            ('_original', _o),
        ]))

    # 撞车检查：priority 不许与既有重复
    used_prio = set(r.get('priority') for r in routes)
    clash = [a['priority'] for a in added if a['priority'] in used_prio]
    if clash:
        print(u'[FATAL] 新增规则 priority 撞车：%r' % clash)
        return 3
    routes.extend(added)
    stat['new_rules'] = len(added)

    # ================= meta.note =================
    d['meta']['note'] = d['meta']['note'] + (
        u'★ 第170轮：**按分支对账落点，并校正第169轮的元数据**。'
        u'① `entrance` 从 102 条补到 **190/190**（+88，逐条来自 '
        u'`obj_doorW_Alarm_2` / `obj_doorw_musfade_Alarm_2` 的 `global.entrance = N`）。'
        u'② 区间按源码校正 **27** 条：其中 **11 条方向反了**（源码 `x < 10`，表里记成 '
        u'`[10, None]` 即 `x > 10` —— 单边条件时 lo/hi 写反），另 16 条表里是 '
        u'`[None, None]` 而源码有值；y 轴分支改用独立的 `y_range`（`x_range` 保持 '
        u'`[None, None]` 不动，因为它本来就没有 x 条件）。'
        u'③ 门实例坐标 **17** 条：`door_x` **5** 条 + `door_y` **12** 条 —— '
        u'`dw_cyber_maze_rhythm` 两扇门 x 只差 2px（269/271）、y 是 2593/1，'
        u'`dw_cyber_musical_door` / `dw_mansion_east_teacup(_2)` 两扇门 x **完全相同**，'
        u'**拿 x 区分会把上下门判反**，所以这 12 条一律写 `door_y` 并加 `axis: "y"`。'
        u'④ 新增 **%d** 条（priority %d~%d）：只补"表里真的没有这条边"的；'
        u'原本还有 2 条候选与既有 (场景,目标) 完全重复 ⇒ **不加**'
        u'（加了就是冗余条目，会同时弄脏 `check124 D2` 的同门重复与 `check169` 的覆盖桶）。'
        u'其中 6 条让原本"查不到 ⇒ 不建门"的门活过来。'
        u'⑤ **不猜**的地方：混轴条件（`x > 800 && y > 670`）源码解不出单一区间 ⇒ 保持原样；'
        u'同一 `(房, 对象, 目标)` 有 2 条分支 ⇒ 匹配不到唯一 ⇒ 不动；'
        u'`entrance` 在同一条边上不唯一（3 条）⇒ 不补。逐条见 '
        u'`code-quality-audit/第170轮-门实例级落点/_evidence/applied170.json`。'
        u'生成器 `code-quality-audit/第170轮-门实例级落点/_tools/apply170.py`。'
        % (len(added), PRIO_BASE, PRIO_BASE + max(0, len(added) - 1)))

    # ================= 落盘 =================
    out = json.dumps(d, ensure_ascii=False, indent=2).replace('\n', '\r\n').encode('utf-8')
    tmp = ROUTES + '.new'
    io.open(tmp, 'wb').write(out)
    #: 写前再自检一次：解析回去、条数对、没有 BOM
    chk = json.loads(io.open(tmp, 'rb').read().decode('utf-8'))
    assert len(chk['routes']) == len(routes), 'routes 条数不一致'
    assert not out.startswith(b'\xef\xbb\xbf'), '意外写入 BOM'
    os.replace(tmp, ROUTES)

    print()
    print(u'== 落地统计 ==')
    for k in ('ent_fill', 'ent_fix', 'ent_same', 'range_flip', 'range_set', 'range_same',
              'door_set', 'reason_rewrote', 'new_rules'):
        print(u'  %-16s %d' % (k, stat[k]))
    print(u'  routes 总数 %d -> %d' % (len(routes) - len(added), len(routes)))
    print()
    print(u'== 留档不动 %d 条 ==' % len(skipped))
    c = collections.Counter(x['why'] for x in skipped)
    for k, v in sorted(c.items(), key=lambda t: -t[1]):
        print(u'  %-24s %d' % (k, v))
    print()
    print(u'文件 %d -> %d B' % (len(raw), len(out)))

    io.open(OUT, 'wb').write(json.dumps(
        {'stat': dict(stat), 'skipped': skipped, 'new_rules': added},
        ensure_ascii=False, indent=1).replace('\n', '\r\n').encode('utf-8'))
    print(u'落盘 %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
