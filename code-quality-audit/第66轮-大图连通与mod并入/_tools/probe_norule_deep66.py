# -*- coding: utf-8 -*-
u"""第66轮 · 对 60 条 no-rule 边做「全部事件」的深度扫描，找第 4/5 种载体。

载体 4 `cc-runtime`：事件里 `instance_create(..., obj_doorway)` + `with (..) { nextroom = N; }`
载体 5 `inherit`    ：事件里只有 `event_inherited()` ⇒ 真逻辑在父对象（本轮不猜父对象）
另扫 `room = <room_xxx>`（带后视，排除 `nextroom`/`global.room`）与 `nextroom = N`。
"""
from __future__ import print_function
import collections, io, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, '..', '..', u'第65轮-黄魂并入Undertale大地图', '_evidence')

WORKS = {
    'ut': ('ut_topology65.json', r'E:\Download\_extract61\_data\undertale\u65\gml65ut'),
    'uty': ('uty_topology65.json', r'E:\Download\_extract61\_data\undertale_yellow\uty65\gml65'),
}

RX = {
    'room_assign': re.compile(r'(?<![A-Za-z0-9_.])room\s*=\s*([A-Za-z_][A-Za-z0-9_]*)'),
    'nextroom_int': re.compile(r'(?<![A-Za-z0-9_.])nextroom\s*=\s*(-?\d+)'),
    'nextroom_var': re.compile(r'(?<![A-Za-z0-9_.])nextroom\s*=\s*([^;\n]+)'),
    'room_goto_txt': re.compile(r'room_goto\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)'),
    'goto_next': re.compile(r'room_goto_next\s*\(\s*\)'),
    'inherit': re.compile(r'event_inherited\s*\(\s*\)'),
    'inst_create': re.compile(r'instance_create\s*\(\s*[^,]*,\s*[^,]*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)'),
    'with_block': re.compile(r'with\s*\('),
}


def strip_c(s):
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    return re.sub(r'//[^\n]*', '', s)


def ev_of(fn):
    if not fn.startswith('gml_Object_') or not fn.endswith('.gml'):
        return None
    rest = fn[len('gml_Object_'):-4]
    m = re.match(r'^(.+?)_((?:Alarm|Create|Destroy|Step|Draw|Other|PreCreate|'
                 r'Collision|Keyboard|Mouse|KeyPress|KeyRelease|User|Async|'
                 r'Gesture|CleanUp)_\d+)$', rest)
    return m.group(1) if m else rest


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    out = {}
    for work, (topo, gmldir) in WORKS.items():
        t = json.load(io.open(os.path.join(BASE, topo), encoding='utf-8'))
        name2idx = {}
        for r in t['rooms']:
            name2idx.setdefault(r['name'], r['index'])
        rooms_with_edge = collections.defaultdict(set)
        for e in t['edges']:
            if e['to'] is not None:
                rooms_with_edge[e['via']].add(e['from'])
        bad = collections.defaultdict(list)
        for e in t['edges']:
            if e['to'] is None:
                bad[e['via']].append(e['from'])
        byobj = collections.defaultdict(list)
        for fn in sorted(os.listdir(gmldir)):
            o = ev_of(fn)
            if o:
                byobj[o].append(fn)
        print('=' * 22, work)
        rec = {}
        for obj, srcs in sorted(bad.items(), key=lambda kv: -len(kv[1])):
            hits = collections.Counter()
            samples = {}
            for fn in byobj.get(obj, []):
                txt = strip_c(io.open(os.path.join(gmldir, fn), encoding='utf-8',
                                      errors='replace').read())
                for k, rx in RX.items():
                    ms = list(rx.finditer(txt))
                    if not ms:
                        continue
                    hits[k] += len(ms)
                    samples.setdefault(k, (fn, [m.group(0) for m in ms[:3]]))
            verdict = []
            if hits.get('nextroom_int'):
                verdict.append('RT-CC(%s)' % samples['nextroom_int'][1])
            if hits.get('room_assign'):
                verdict.append('ROOM=(%s)' % samples['room_assign'][1])
            if hits.get('goto_next'):
                verdict.append('NEXT')
            if hits.get('inherit'):
                verdict.append('INHERIT')
            if hits.get('inst_create'):
                verdict.append('CREATE(%s)' % samples['inst_create'][1])
            if not verdict:
                verdict = ['--visual/none--']
            n_new = 0
            if hits.get('nextroom_int'):
                for m in samples['nextroom_int'][1]:
                    v = int(re.search(r'(-?\d+)', m).group(1))
                    if v in name2idx.values():
                        n_new += 1
            print('  %-36s edges=%d rooms=%s' % (obj, len(srcs), srcs[:4]))
            print('        files=%d  %s' % (len(byobj.get(obj, [])), ' | '.join(verdict)))
            rec[obj] = {'no_rule_edges': len(srcs), 'rooms': srcs,
                        'files': len(byobj.get(obj, [])),
                        'pattern_hits': dict(hits),
                        'samples': dict((k, {'file': v[0], 'text': v[1]})
                                        for k, v in samples.items()),
                        'verdict': verdict}
        out[work] = rec
    dst = os.path.join(HERE, '..', '_evidence', 'norule_deep66.json')
    io.open(dst, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=1))
    print('\n-> %s' % os.path.normpath(dst))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
