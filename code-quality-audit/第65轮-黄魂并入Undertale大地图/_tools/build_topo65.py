# -*- coding: utf-8 -*-
u"""第65轮 · 拓扑构建器（Undertale / 黄魂 通用）。

输入 = 三件套：rooms json + doorinst json + gml 目录
输出 = topology json：rooms / edges / stats / evidence

边来源（按"证据强度"排序，逐条带出处）：
  E1 explicit : `if (room == X) { … room_goto(Y) }`            —— 代码里写死的房间名
  E2 struct   : `room_goto(room_next(room))` 系列               —— 结构式偏移（第65轮已证 A=+1/B=-1/C=+2/D=-2）
  E3 uncond   : 不在 room 条件块内的 `room_goto(Y)`             —— 可能是坐标/flag 分支，标 suspected 并列出
  E4 special  : 代码里带例外分支的（如 room_castle_prebarrier） —— 显式硬编码，注明出处

★ 纪律：**走不到就留空，不按几何就近凑**；每条边必须能指回 GML 出处。
"""
from __future__ import print_function
import io, json, os, re, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
RE_COND = re.compile(r'if\s*\(\s*room\s*==\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)')
RE_NEG = re.compile(r'if\s*\(\s*room\s*!=\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)')
RE_GOTO_NEXT = re.compile(r'room_goto_next\s*\(\s*\)')
RE_NEXT2 = re.compile(r'room_goto\(\s*room_next\(\s*room_next\(\s*room\s*\)\s*\)\s*\)')
RE_PREV2 = re.compile(r'room_goto\(\s*room_previous\(\s*room_previous\(\s*room\s*\)\s*\)\s*\)')
RE_NEXT1 = re.compile(r'room_goto\(\s*room_next\(\s*room\s*\)\s*\)')
RE_PREV1 = re.compile(r'room_goto\(\s*room_previous\(\s*room\s*\)\s*\)')
RE_GOTO = re.compile(r'room_goto\(\s*(?!room_(?:next|previous)\()([A-Za-z_][A-Za-z0-9_]*)\s*\)')

#: 门对象名 → 结构式偏移（由 GML 实测得出；未列出的对象一律走 explicit/uncond）
STRUCT_RULES = {'obj_doorA': +1, 'obj_doorB': -1, 'obj_doorC': +2, 'obj_doorD': -2}
#: 与上面同义的变体（音乐淡出类），语义相同
STRUCT_ALIAS = {'obj_doorAmusicfade': 'obj_doorA', 'obj_doorBmusicfade': 'obj_doorB',
                'obj_doorCmusicfade': 'obj_doorC', 'obj_doorDmusicfade': 'obj_doorD'}
#: 已知的硬编码例外（出处：obj_doorA_Alarm_2）
SPECIAL = {('room_castle_prebarrier', 'obj_doorA'): 'room_castle_trueexit'}


def strip_comments(s):
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    s = re.sub(r'//[^\n]*', '', s)
    return s


def parse_text(txt):
    u"""大括号感知：返回 rules / cond / neg / uncond。"""
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
            per[n] = {'rules': r, 'cond': c, 'neg': ng, 'uncond': u, 'text': txt}
    return per


def owner_of(fname, objnames):
    u"""gml_Object_<obj>_<Evt>_<n>.gml → <obj>（取最长匹配，避免 obj_door 抢 obj_doorA）"""
    base = fname
    if not base.startswith('gml_Object_'):
        return None
    rest = base[len('gml_Object_'):]
    best = None
    for o in objnames:
        if rest.startswith(o + '_') or rest == o:
            if best is None or len(o) > len(best):
                best = o
    return best


def build(rooms_path, inst_path, gml_dir, work, probe_only=False):
    rooms = json.load(io.open(rooms_path, encoding='utf-8'))['rooms']
    inst = json.load(io.open(inst_path, encoding='utf-8'))['rooms']
    name2idx = {}
    for r in rooms:
        name2idx.setdefault(r['name'], r['index'])
    idx2name = dict((r['index'], r['name']) for r in rooms)

    per = load_gml_dir(gml_dir)
    objnames = sorted(set(o for o in (owner_of(n, set()) or '' for n in per) if o))
    # 用文件名反推对象名（不稳），改从 doorinst 的对象名集合来
    objset = set()
    for r in inst:
        for d in r.get('doors', []):
            objset.add(d['obj'])
    objset |= set(STRUCT_RULES) | set(STRUCT_ALIAS)
    per_by_obj = {}
    for n, v in per.items():
        o = owner_of(n, objset)
        if o:
            per_by_obj.setdefault(o, []).append((n, v))

    # ---- 归纳每个对象的"结构规则" ----
    struct = {}
    for o, files in per_by_obj.items():
        for n, v in files:
            for k, off in (('next1', +1), ('prev1', -1), ('next2', +2), ('prev2', -2)):
                if v['rules'].get(k):
                    struct.setdefault(o, set()).add(off)
    # 每个对象最多一个偏移才算"结构式"
    struct_ok = dict((o, sorted(s)[0]) for o, s in struct.items() if len(s) == 1)

    if probe_only:
        print('== %s ==' % work)
        print('  房数 %d ; 门对象 %d' % (len(rooms), len(objset)))
        print('  结构式对象：')
        for o in sorted(struct_ok):
            print('     %-30s offset=%+d' % (o, struct_ok[o]))
        print('  显式式对象（cond 条目数）：')
        for o in sorted(per_by_obj):
            cc = sum(len(v['cond']) for _, v in per_by_obj[o])
            uu = sum(len(v['uncond']) for _, v in per_by_obj[o])
            if cc or uu:
                print('     %-30s cond=%d uncond=%d' % (o, cc, uu))
        return None

    # ---- 建边 ----
    edges = []
    for r in inst:
        i = r['index']
        rn = r.get('name') or idx2name.get(i, '')
        for d in r.get('doors', []):
            o = d['obj']
            canon = STRUCT_ALIAS.get(o, o)
            off = struct_ok.get(canon, STRUCT_RULES.get(canon))
            made = False
            # E1 显式
            for n, v in per_by_obj.get(o, []):
                if rn in v['cond']:
                    for t in v['cond'][rn]:
                        j = name2idx.get(t)
                        edges.append(mk(i, rn, j, t, o, 'explicit',
                                        {'file': n, 'kind': 'cond'}))
                        made = True
                if rn in v['neg']:
                    for t in v['neg'][rn]:
                        j = name2idx.get(t)
                        edges.append(mk(i, rn, j, t, o, 'explicit-neg',
                                        {'file': n, 'kind': 'neg'}))
                        made = True
                if v['uncond'] and rn not in v['cond']:
                    for t in v['uncond']:
                        j = name2idx.get(t)
                        edges.append(mk(i, rn, j, t, o, 'uncond',
                                        {'file': n, 'kind': 'uncond',
                                         'note': '无条件/坐标或 flag 分支，需人工确认'}))
                        made = True
            if made:
                continue
            # E4 硬编码例外
            sp = SPECIAL.get((rn, canon))
            if sp:
                edges.append(mk(i, rn, name2idx.get(sp), sp, o, 'special',
                                {'file': 'obj_doorA_Alarm_2', 'kind': 'special'}))
                continue
            # E2 结构式
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

    # ---- 统计 ----
    resolved = [e for e in edges if e['to'] is not None]
    unr = [e for e in edges if e['to'] is None]
    cnt = collections.Counter(e['via'] for e in edges)
    src = collections.Counter(e['evidence_kind'] for e in edges)

    und = collections.defaultdict(set)
    for e in resolved:
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

    art = {
        'work': work,
        'source': {'rooms': rooms_path, 'instances': inst_path, 'gml': gml_dir},
        'room_count': len(rooms),
        'rooms': [{'index': r['index'], 'name': r['name'], 'w': r['w'], 'h': r['h']}
                  for r in rooms],
        'struct_rules': dict((o, struct_ok[o]) for o in sorted(struct_ok)),
        'edges': edges,
        'stats': {
            'edges': len(edges), 'resolved': len(resolved), 'unresolved': len(unr),
            'by_via': dict(cnt), 'by_evidence': dict(src),
            'components': len(sizes),
            'largest_component': sizes.most_common(1)[0][1] if sizes else 0,
            'top_sizes': sizes.most_common(8),
        },
    }
    return art


def mk(i, rn, j, tn, o, kind, ev):
    return {'from': i, 'from_name': rn, 'to': j, 'to_name': tn,
            'via': o, 'rule': kind, 'evidence_file': ev.get('file'),
            'evidence_kind': ev.get('kind'), 'note': ev.get('note')}


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
        print('缺 --out')
        return 2
    io.open(a.out, 'w', encoding='utf-8').write(json.dumps(art, ensure_ascii=False, indent=1))
    s = art['stats']
    print('%s: rooms=%d edges=%d resolved=%d unresolved=%d components=%d largest=%d'
          % (a.work, art['room_count'], s['edges'], s['resolved'], s['unresolved'],
             s['components'], s['largest_component']))
    print('  by_via=%s' % s['by_via'])
    print('  by_evidence=%s' % s['by_evidence'])
    print('  -> %s' % a.out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
