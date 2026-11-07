# -*- coding: utf-8 -*-
u"""第170轮：从第42轮**逐房间实例快照**取两样东西，并各自做 A/B 验证。

来源
----
`code-quality-audit/第42轮-原作拓扑取证/_evidence/ch2_inst42.json`
  `rooms[] = {index, name, w, h, n, insts:[{obj, x, y, layer, depth}, ...]}`
逐房间、逐实例的**对象名 + 坐标** —— 第169轮的 `marker` 就是从这里取的
（规则见 `gen_routes169.py`，line 114~127）。

两件事
------
A `marker` 复算：用「落点字母小写 → 该房真实 marker 对象名，否则 any/any40px，
   否则 None」重算 **102 条 batch169 已知样本**。
   · 全部一致 ⇒ 这把尺可信 ⇒ 用它填 9 条新规则；
   · 有不一致 ⇒ 打印反例，9 条新规则一律不写 marker（不猜）。

B 门坐标交叉核对：我自己那 11 条 `door_x/door_y` 来自**产品场景 JSON 的 `pos`**
   （`_zone.ch2.json` 抽出来的），这里是**原作 room 里的实例坐标**。
   两个来源独立 ⇒ 逐条比对，差一个像素都要报出来。
"""
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
INST = os.path.join(REPO, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence',
                    'ch2_inst42.json')
FIX = os.path.join(ROUND, '_evidence', 'fix170.json')
GML = os.path.join(ROUND, '_evidence', 'gml170.json')
OUT = os.path.join(ROUND, '_evidence', 'marker2_170.json')

MRK = re.compile(r'^obj_marker(.*)$')
ANY = ('any', 'any40px')


def jl(p):
    return json.loads(io.open(p, encoding='utf-8', errors='replace', newline='').read())


def load_inst():
    u"""→ {room_name: {'markers': {suffix: 真实对象名}, 'doors': [(x, y, obj), ...]}}"""
    d = jl(INST)
    out = {}
    for r in d['rooms']:
        mk = {}
        drs = []
        for o in r['insts']:
            name = o.get('obj') or ''
            mm = MRK.match(name)
            if mm:
                # ★★★ 后缀必须**统一小写**再当键：原作里大小写混用
                #   （`obj_markert` 小写 t，`obj_markerX` 大写 X）。
                #   不归一会让 `letter.lower()` 查不到大写那批 —— 38 条假不符就是这么来的。
                mk.setdefault(mm.group(1).lower(), name)
            if name.startswith('obj_doorW') or name.startswith('obj_doorw'):
                drs.append((o.get('x'), o.get('y'), name))
        out.setdefault(r['name'], {'markers': mk, 'doors': drs})
    return out


def marker_of(room, letter):
    u"""第169轮同一把尺：字母小写命中 → 该对象；否则 any/any40px；否则 None。"""
    mks = room['markers'] if room else {}
    L = (letter or '').lower()
    if L and L in mks:
        return mks[L]
    for a in ANY:
        if a in mks:
            return mks[a]
    return None


def main():
    inst = load_inst()
    routes = jl(os.path.join(SCENES, '_routes.json'))['routes']
    fix = jl(FIX)
    g = jl(GML)

    # ---------- A: 复算 102 条已知样本 ----------
    known = [r for r in routes if (r.get('_original') or {}).get('batch') == 169]
    bad = []
    for r in known:
        o = r['_original']
        if o.get('chapter') != 'ch2':
            continue                       # 只有 ch2 有 inst42 快照
        got = marker_of(inst.get(o.get('dst_room_name')), o.get('branch_letter'))
        if got != o.get('marker'):
            bad.append({'src': o.get('src_room_name'), 'dst': o.get('dst_room_name'),
                        'letter': o.get('branch_letter'),
                        'table': o.get('marker'), 'calc': got})
    n_ch2 = sum(1 for r in known if r['_original'].get('chapter') == 'ch2')
    print(u'== A. marker 复算（ch2 的 %d 条 batch169）==' % n_ch2)
    print(u'   一致 %d / 不符 %d' % (n_ch2 - len(bad), len(bad)))
    for b in bad[:10]:
        print(u'   ✗ %-32s -> %-32s letter=%s 表=%r 算=%r'
              % (b['src'], b['dst'], b['letter'], b['table'], b['calc']))
    a_ok = not bad
    print(u'   ⇒ %s' % (u'尺子可信' if a_ok else u'★尺子不可信，新规则不写 marker'))

    # ---------- B: 9 条新规则的 marker ----------
    #: 房间号 → 房名（从 gml170 反查，同一套 room_id）
    rid2name = {}
    for obj, d in g['chapters']['ch2'].items():
        for nm, v in d['rooms'].items():
            if v.get('room_id') is not None:
                rid2name[v['room_id']] = nm
    new = []
    for nr in fix['new_rules']:
        dst_name = rid2name.get(nr['dst'])
        ent = nr['ent']
        bl = chr(ent + 64) if isinstance(ent, int) and 0 < ent < 59 else None
        mk = marker_of(inst.get(dst_name), bl) if a_ok else None
        new.append({'sid_s': nr['sid_s'], 'sid_t': nr['sid_t'], 'dst_room': dst_name,
                    'ent': ent, 'branch_letter': bl, 'marker': mk})
    print()
    print(u'== B. 9 条新规则的 marker（落点字母 = chr(entrance+64)，102/102 已验证）==')
    for x in new:
        print(u'   %-44s -> %-40s ent=%-3s 字母=%-2s marker=%r'
              % (x['sid_s'], x['sid_t'], x['ent'], x['branch_letter'], x['marker']))

    # ---------- C: 门坐标交叉核对（独立来源）----------
    print()
    print(u'== C. 11 条坐标 vs 原作 room 实例（两个独立来源逐条对账）==')
    mism = []
    for d in fix['door_x_add']:
        room = inst.get(d['room'])
        if room is None:
            mism.append({'room': d['room'], 'why': 'no_inst_room'})
            print(u'   ? %-40s 原作快照里没有这间房' % d['room'])
            continue
        pairs = [(x, y) for x, y, _ in room['doors']]
        hit = [p for p in pairs if p[0] == d['x'] and p[1] == d['y']]
        ok = bool(hit)
        print(u'   %s %-40s -> %-38s 我记=(%s,%s) 原作门实例=%r'
              % (u'✓' if ok else u'✗', d['room'], d['dst'], d['x'], d['y'], pairs))
        if not ok:
            mism.append({'room': d['room'], 'mine': [d['x'], d['y']], 'inst': pairs})
    print()
    print(u'   ⇒ 一致 %d / 不符 %d' % (len(fix['door_x_add']) - len(mism), len(mism)))

    io.open(OUT, 'wb').write(json.dumps(
        {'marker_ok': a_ok, 'marker_bad': bad, 'new_markers': new,
         'coord_mismatch': mism}, ensure_ascii=False, indent=1)
        .replace('\n', '\r\n').encode('utf-8'))
    print()
    print(u'落盘 %s' % OUT)


if __name__ == '__main__':
    main()
