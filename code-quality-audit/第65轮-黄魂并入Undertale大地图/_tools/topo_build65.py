# -*- coding: utf-8 -*-
u"""第65轮 · 拓扑构建器（Undertale / 黄魂 通用）。

输入 = rooms json + doorinst json + gml 目录
输出 = topology json：rooms / edges / stats

边来源（按证据强度排序，逐条带出处）：
  E0 cc      : 实例创建代码里显式声明 `nextroom = N; xx = ..; yy = ..`
               —— **黄魂（UTY）的主机制**：目标房索引 + 落点坐标全部写死
  E1 explicit: if (room == X) { ... room_goto(Y) }   —— Undertale 的 obj_door_t/u/v/w 等
  E2 struct  : room_goto(room_next(room)) 系列        —— A=+1 / B=-1 / C=+2 / D=-2（本轮代码实证）
  E3 uncond  : 不在 room 条件块内的 room_goto(Y)      —— 标 suspected，需人工确认
  E4 special : 硬编码例外（room_castle_prebarrier）

★ 纪律：走不到就留空，不按几何就近凑；每条边必须能指回 GML/cc 出处。
★ 实例去重：csx 同时从 room.GameObjects（展平表）与 layer.Instances 取，
  两者是同一批实例的两个视图 ⇒ 必须按 (obj,x,y,cc) 去重，否则边数翻倍（假数据）。
"""
from __future__ import print_function
import io, json, os, re, sys, collections

RE_COND = re.compile(r'if\s*\(\s*room\s*==\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)')
RE_NEG = re.compile(r'if\s*\(\s*room\s*!=\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)')
RE_GOTO_NEXT = re.compile(r'room_goto_next\s*\(\s*\)')
RE_NEXT2 = re.compile(r'room_goto\(\s*room_next\(\s*room_next\(\s*room\s*\)\s*\)\s*\)')
RE_PREV2 = re.compile(r'room_goto\(\s*room_previous\(\s*room_previous\(\s*room\s*\)\s*\)\s*\)')
RE_NEXT1 = re.compile(r'room_goto\(\s*room_next\(\s*room\s*\)\s*\)')
RE_PREV1 = re.compile(r'room_goto\(\s*room_previous\(\s*room\s*\)\s*\)')
RE_GOTO = re.compile(r'room_goto\(\s*(?!room_(?:next|previous)\()([A-Za-z_][A-Za-z0-9_]*)\s*\)')
RE_ASSIGN = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(-?\d+)\s*;\s*$')

STRUCT_RULES = {'obj_doorA': +1, 'obj_doorB': -1, 'obj_doorC': +2, 'obj_doorD': -2}
STRUCT_ALIAS = {'obj_doorAmusicfade': 'obj_doorA', 'obj_doorBmusicfade': 'obj_doorB',
                'obj_doorCmusicfade': 'obj_doorC', 'obj_doorDmusicfade': 'obj_doorD'}
SPECIAL = {('room_castle_prebarrier', 'obj_doorA'): 'room_castle_trueexit'}
#: 实例创建代码里表示"目标房索引 / 落点"的变量名（本轮从 UTY 实测）
CC_TARGET_KEYS = ('nextroom', 'nextroomid', 'next_room')
CC_LANDING_KEYS = (('xx', 'yy'), ('landx', 'landy'))


def strip_comments(s):
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    return re.sub(r'//[^\n]*', '', s)


def parse_cc(text):
    u"""实例创建代码 → {变量: 整数}（只认 `name = 整数;` 这种简单赋值）。"""
    out = {}
    if not text:
        return out
    for ln in strip_comments(text).split('\n'):
        m = RE_ASSIGN.match(ln)
        if m:
            try:
                out[m.group(1)] = int(m.group(2))
            except ValueError:
                pass
    return out


def cc_target(ccmap):
    for k in CC_TARGET_KEYS:
        if k in ccmap:
            return ccmap[k]
    return None


def cc_landing(ccmap):
    for kx, ky in CC_LANDING_KEYS:
        if kx in ccmap and ky in ccmap:
            return [ccmap[kx], ccmap[ky]]
    return None


def parse_text(txt):
    rules = collections.OrderedDict()
    for name, rx in (('next2', RE_NEXT2), ('prev2', RE_PREV2),
                     ('next1', RE_NEXT1), ('prev1', RE_PREV1)):
        if rx.search(txt):
            rules[name] = True
    if RE_GOTO_NEXT.search(txt):
        rules['goto_next'] = True
    cond, neg, uncond = collections.OrderedDict(), collections.OrderedDict(), []
    depth, frame, pending = 0, None, None
    PAT = re.compile(r'\{\s*|\s*\}|' + RE_COND.pattern + r'|' + RE_NEG.pattern + r'|'
                     + RE_GOTO.pattern + r'|room_goto_next\s*\(\s*\)')
    for m in PAT.finditer(txt):
        tok = m.group(0)
        if tok.strip() == '{':
            depth += 1
            if pending is not None:
                frame = (pending[0], pending[1], depth)
                pending = None
            continue
        if tok.strip() == '}':
            if frame is not None and depth == frame[2]:
                frame = None
            depth -= 1
            continue
        mc = RE_COND.search(tok)
        if mc:
            pending = ('cond', mc.group(1))
            continue
        mn = RE_NEG.search(tok)
        if mn:
            pending = ('neg', mn.group(1))
            continue
        mg = RE_GOTO.match(tok)
        if mg:
            tgt = mg.group(1)
            if frame is not None:
                kind, room, _ = frame
                if room == tgt:
                    continue
                (cond if kind == 'cond' else neg).setdefault(room, []).append(tgt)
            else:
                uncond.append(tgt)
    dd = lambda d: collections.OrderedDict(
        (k, list(collections.OrderedDict.fromkeys(v))) for k, v in d.items() if v)
    return rules, dd(cond), dd(neg), list(collections.OrderedDict.fromkeys(uncond))


def load_gml_dir(d):
    per = {}
    if not os.path.isdir(d):
        return per
    for n in sorted(os.listdir(d)):
        if not n.endswith('.gml'):
            continue
        txt = strip_comments(io.open(os.path.join(d, n), encoding='utf-8',
                                     errors='replace').read())
        r, c, ng, u = parse_text(txt)
        if r or c or ng or u:
            per[n] = {'rules': r, 'cond': c, 'neg': ng, 'uncond': u}
    return per


def owner_of(fname, objnames):
    if not fname.startswith('gml_Object_'):
        return None
    rest = fname[len('gml_Object_'):]
    best = None
    for o in objnames:
        if rest.startswith(o + '_') or rest == o:
            if best is None or len(o) > len(best):
                best = o
    return best


def dedupe_instances(inst):
    u"""按 (obj,x,y,cc) 去重（GameObjects 与 layer.Instances 是同一批的两个视图）。"""
    srcs = collections.Counter()
    out = []
    for r in inst:
        seen = collections.OrderedDict()
        for d in r.get('doors', []):
            srcs[d.get('src')] += 1
            key = (d.get('obj'), d.get('x'), d.get('y'), (d.get('cc') or '').strip())
            if key not in seen:
                seen[key] = d
        r2 = dict(r)
        r2['doors'] = list(seen.values())
        out.append(r2)
    return out, srcs


def mk(i, rn, j, tn, o, kind, ev, landing=None):
    e = {'from': i, 'from_name': rn, 'to': j, 'to_name': tn, 'via': o,
         'rule': kind, 'evidence_file': ev.get('file'), 'evidence_kind': ev.get('kind')}
    if landing:
        e['landing'] = landing
    if ev.get('note'):
        e['note'] = ev['note']
    return e


def build(rooms_path, inst_path, gml_dir, work, probe_only=False):
    rooms = json.load(io.open(rooms_path, encoding='utf-8'))['rooms']
    inst_raw = json.load(io.open(inst_path, encoding='utf-8'))['rooms']
    inst, srcs = dedupe_instances(inst_raw)
    n_raw = sum(len(r.get('doors', [])) for r in inst_raw)
    n_ded = sum(len(r.get('doors', [])) for r in inst)
    name2idx, idx2name = {}, {}
    for r in rooms:
        name2idx.setdefault(r['name'], r['index'])
        idx2name[r['index']] = r['name']

    per = load_gml_dir(gml_dir)
    objset = set(STRUCT_RULES) | set(STRUCT_ALIAS)
    for r in inst:
        for d in r.get('doors', []):
            objset.add(d['obj'])
    per_by_obj = {}
    for n, v in per.items():
        o = owner_of(n, objset)
        if o:
            per_by_obj.setdefault(o, []).append((n, v))
    # --- P1 落点（obj_marker*）不是门：单独收集 ---
    marks = {}
    for r in inst:
        for d in r.get('doors', []):
            o = d['obj']
            if not o.startswith('obj_marker'):
                continue
            let = o[len('obj_marker'):]
            marks.setdefault(r['index'], {}).setdefault(let, []).append([d['x'], d['y']])
    markers_total = sum(len(v) for v in marks.values())

    struct = {}
    for o, files in per_by_obj.items():
        for n, v in files:
            for k, off in (('next1', +1), ('prev1', -1), ('next2', +2), ('prev2', -2)):
                if v['rules'].get(k):
                    struct.setdefault(o, set()).add(off)
    struct_ok = dict((o, sorted(s)[0]) for o, s in struct.items() if len(s) == 1)

    if probe_only:
        ncc = sum(1 for r in inst for d in r.get('doors', []) if d.get('cc'))
        ntgt = sum(1 for r in inst for d in r.get('doors', [])
                   if cc_target(parse_cc(d.get('cc'))) is not None)
        print('== %s ==' % work)
        print('  rooms=%d  door_objs=%d  objs_with_gml=%d' % (len(rooms), len(objset), len(per_by_obj)))
        print('  实例：原始 %d → 去重后 %d（按 src %s）' % (n_raw, n_ded, dict(srcs)))
        print('  带 cc 的实例 %d，其中写有目标房 %d' % (ncc, ntgt))
        print('  struct:')
        for o in sorted(struct_ok):
            print('     %-32s offset=%+d' % (o, struct_ok[o]))
        print('  explicit:')
        for o in sorted(per_by_obj):
            cc = sum(len(v['cond']) for _, v in per_by_obj[o])
            uu = sum(len(v['uncond']) for _, v in per_by_obj[o])
            if cc or uu:
                print('     %-32s cond=%d uncond=%d' % (o, cc, uu))
        return None

    edges = []
    for r in inst:
        i = r['index']
        rn = r.get('name') or idx2name.get(i, '')
        for d in r.get('doors', []):
            o = d['obj']
            if o.startswith('obj_marker'):
                continue  # P1
            ccm = parse_cc(d.get('cc'))
            tgt_idx = cc_target(ccm)
            land = cc_landing(ccm)
            if tgt_idx is not None:
                edges.append(mk(i, rn, tgt_idx, idx2name.get(tgt_idx), o, 'cc-nextroom',
                                {'file': 'instance_creation_code', 'kind': 'cc-nextroom'},
                                land))
                continue
            canon = STRUCT_ALIAS.get(o, o)
            off = struct_ok.get(canon, STRUCT_RULES.get(canon))
            # P2：对象若已有 struct 规则或 SPECIAL 例外，其 uncond 属'例外分支'，不得全局套用
            skip_uncond = (off is not None) or ((rn, canon) in SPECIAL)
            made = False
            for n, v in per_by_obj.get(o, []):
                if rn in v['cond']:
                    for t in v['cond'][rn]:
                        edges.append(mk(i, rn, name2idx.get(t), t, o, 'explicit',
                                        {'file': n, 'kind': 'cond'}))
                        made = True
                if rn in v['neg']:
                    for t in v['neg'][rn]:
                        edges.append(mk(i, rn, name2idx.get(t), t, o, 'explicit-neg',
                                        {'file': n, 'kind': 'neg'}))
                        made = True
                if v['uncond'] and rn not in v['cond'] and not skip_uncond:
                    for t in v['uncond']:
                        edges.append(mk(i, rn, name2idx.get(t), t, o, 'uncond',
                                        {'file': n, 'kind': 'uncond',
                                         'note': 'unconditional/positional/flag branch'}))
                        made = True
            if made:
                continue
            sp = SPECIAL.get((rn, canon))
            if sp:
                edges.append(mk(i, rn, name2idx.get(sp), sp, o, 'special',
                                {'file': 'obj_doorA_Alarm_2', 'kind': 'special'}))
                continue
            if off is not None:
                j = i + off
                if 0 <= j < len(rooms):
                    edges.append(mk(i, rn, j, idx2name.get(j), o, 'struct',
                                    {'file': None, 'kind': 'offset=%+d' % off}))
                else:
                    edges.append(mk(i, rn, None, None, o, 'out-of-range',
                                    {'file': None, 'kind': 'offset=%+d' % off}))
                continue
            edges.append(mk(i, rn, None, None, o, 'unresolved',
                            {'file': None, 'kind': 'no-rule'}))

    # --- P3 落点回填：目标房若有同字母 obj_marker，补 landing ---
    for e in edges:
        if e['to'] is None or e.get('landing'):
            continue
        via = e['via']
        let = via[len('obj_door'):] if via.startswith('obj_door') else None
        if not let:
            continue
        lm = marks.get(e['to'], {}).get(let)
        if lm:
            e['landing'] = lm[0]
            e['landing_ok'] = True

    # 按 (from,to,via) 去重（同一房间里多个同类门可能指向同一目标）
    uniq, seenk = [], set()
    for e in edges:
        k = (e['from'], e['to'], e['via'], e['rule'])
        if k in seenk:
            continue
        seenk.add(k)
        uniq.append(e)
    edges = uniq

    resolved = [e for e in edges if e['to'] is not None]
    unr = [e for e in edges if e['to'] is None]
    bad = [e for e in resolved if not (0 <= e['to'] < len(rooms))]
    und = collections.defaultdict(set)
    for e in resolved:
        if e['to'] in bad:
            continue
        und[e['from']].add(e['to'])
        und[e['to']].add(e['from'])
    comp, cid = {}, 0
    for i in range(len(rooms)):
        if i in comp:
            continue
        cid += 1
        seen, stack = {i}, [i]
        while stack:
            u = stack.pop()
            for v in und[u]:
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        for v in seen:
            comp[v] = cid
    sizes = collections.Counter(comp.values())
    return {
        'work': work,
        'source': {'rooms': rooms_path, 'instances': inst_path, 'gml': gml_dir},
        'room_count': len(rooms),
        'rooms': [{'index': r['index'], 'name': r['name'], 'w': r['w'], 'h': r['h']} for r in rooms],
        'struct_rules': dict((o, struct_ok[o]) for o in sorted(struct_ok)),
        'edges': edges,
        'stats': {
            'instances_raw': n_raw, 'instances_dedup': n_ded, 'instances_by_src': dict(srcs),
            'markers': markers_total, 'landing_ok': sum(1 for e in edges if e.get('landing_ok')),
            'edges': len(edges), 'resolved': len(resolved), 'unresolved': len(unr),
            'to_out_of_range': len(bad),
            'by_via': dict(collections.Counter(e['via'] for e in edges)),
            'by_evidence': dict(collections.Counter(e['evidence_kind'] for e in edges)),
            'components': len(sizes),
            'largest_component': sizes.most_common(1)[0][1] if sizes else 0,
            'top_sizes': sizes.most_common(8),
        },
    }


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', required=True)
    ap.add_argument('--rooms', required=True)
    ap.add_argument('--inst', required=True)
    ap.add_argument('--gml', required=True)
    ap.add_argument('--out', default=None)
    ap.add_argument('--probe', action='store_true')
    a = ap.parse_args()
    art = build(a.rooms, a.inst, a.gml, a.work, a.probe)
    if a.probe or art is None:
        return 0
    if not a.out:
        print('missing --out')
        return 2
    io.open(a.out, 'w', encoding='utf-8').write(json.dumps(art, ensure_ascii=False, indent=1))
    s = art['stats']
    print('%s: rooms=%d edges=%d resolved=%d unresolved=%d oob=%d components=%d largest=%d'
          % (a.work, art['room_count'], s['edges'], s['resolved'], s['unresolved'],
             s['to_out_of_range'], s['components'], s['largest_component']))
    print('  inst raw=%d dedup=%d ; by_via=%s' % (s['instances_raw'], s['instances_dedup'], s['by_via']))
    print('  by_evidence=%s' % s['by_evidence'])
    print('  -> %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
