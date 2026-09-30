# -*- coding: utf-8 -*-
u"""第66轮 · 诊断：60 条 `no-rule` 边到底卡在哪。

对每个产生 unresolved 边的门对象，扫描它**全部事件**的 GML，回答：
  · 有没有 room_goto / room_next / room_previous / room_goto_next？
  · 有没有写 room = X / global.room / global.<某变量>（转场由别处读取）？
  · 事件类型分布如何？
只读，不改任何被测状态。
"""
from __future__ import print_function
import collections, io, json, os, re, sys

R = u'code-quality-audit/第65轮-黄魂并入Undertale大地图/_evidence'
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..',
                    u'第65轮-黄魂并入Undertale大地图', '_evidence')

WORKS = {
    'ut': ('ut_topology65.json', r'E:\Download\_extract61\_data\undertale\u65\gml65ut'),
    'uty': ('uty_topology65.json', r'E:\Download\_extract61\_data\undertale_yellow\uty65\gml65'),
}

PAT = {
    'room_goto': re.compile(r'room_goto\s*\('),
    'room_goto_next': re.compile(r'room_goto_next\s*\('),
    'room_next': re.compile(r'room_next\s*\('),
    'room_previous': re.compile(r'room_previous\s*\('),
    'set_room': re.compile(r'(?<![A-Za-z0-9_.])room\s*=[^=]'),
    'global_room': re.compile(r'global\.room\b'),
    'global_flag': re.compile(r'global\.flag\s*\['),
    'instance_create': re.compile(r'instance_create\s*\('),
    'room_set': re.compile(r'room\s*='),
}


def strip_c(s):
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    return re.sub(r'//[^\n]*', '', s)


def ev_of(fn):
    u"""gml_Object_<obj>_<Event>_<num>.gml → (obj, Event_Num)。"""
    if not fn.startswith('gml_Object_') or not fn.endswith('.gml'):
        return None, None
    rest = fn[len('gml_Object_'):-4]
    m = re.match(r'^(.+?)_((?:Alarm|Create|Destroy|Step|Draw|Other|PreCreate|'
                 r'Collision|Keyboard|Mouse|KeyPress|KeyRelease|User|Async|'
                 r'Gesture|CleanUp)_\d+)$', rest)
    if m:
        return m.group(1), m.group(2)
    return rest, '?'


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    out = {}
    for work, (topo, gmldir) in WORKS.items():
        t = json.load(io.open(os.path.join(BASE, topo), encoding='utf-8'))
        # 该作品所有 unresolved 边的 via 对象
        bad = collections.Counter(e['via'] for e in t['edges'] if e['to'] is None)
        print('=' * 20, work, u'no-rule 边 %d 条，涉及 %d 个对象' % (sum(bad.values()), len(bad)))
        # 建 obj -> [files]
        byobj = collections.defaultdict(list)
        for fn in sorted(os.listdir(gmldir)):
            o, ev = ev_of(fn)
            if o:
                byobj[o].append((fn, ev))
        rec = {}
        for obj, cnt in bad.most_common():
            files = byobj.get(obj, [])
            hits = collections.Counter()
            evs = []
            for fn, ev in files:
                evs.append(ev)
                txt = strip_c(io.open(os.path.join(gmldir, fn), encoding='utf-8',
                                      errors='replace').read())
                for k, rx in PAT.items():
                    if rx.search(txt):
                        hits[k] += 1
            rec[obj] = {'no_rule_edges': cnt, 'files': len(files),
                        'events': sorted(set(e for e in evs if e)),
                        'pattern_hits': dict(hits)}
            flag = 'GOTO' if hits.get('room_goto') or hits.get('room_goto_next') else (
                'SET-room' if hits.get('room_set') else 'NOTHING')
            print('  %-38s edges=%-3d files=%-2d %-8s %s' %
                  (obj, cnt, len(files), flag,
                   ','.join(sorted(set(e for e in evs if e)))[:70]))
            # 若有 room_goto，打印一行样例
            if flag == 'GOTO':
                for fn, ev in files:
                    txt = strip_c(io.open(os.path.join(gmldir, fn), encoding='utf-8',
                                          errors='replace').read())
                    for ln in txt.split('\n'):
                        if 'room_goto' in ln or 'room_next' in ln or 'room_previous' in ln:
                            print('        %-46s | %s' % (fn.replace('gml_Object_', '')[:44],
                                                          ln.strip()[:90]))
                            break
                    else:
                        continue
                    break
        out[work] = rec
    dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '_evidence',
                       'norule_probe66.json')
    io.open(dst, 'w', encoding='utf-8').write(
        json.dumps(out, ensure_ascii=False, indent=1))
    print('\n-> %s' % os.path.normpath(dst))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
