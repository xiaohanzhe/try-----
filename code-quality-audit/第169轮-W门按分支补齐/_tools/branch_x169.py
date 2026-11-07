# -*- coding: utf-8 -*-
u"""第169轮 · 分支级 x 区间解析（修正版）。

## 为什么要 x
同一间房可以有多扇 `obj_doorW`（房 184 有 4 扇，x = 0/360/1560/2540）。
原作靠 `if (x >= lo && x <= hi)` 决定走哪扇。把区间解出来，才能说清
「哪扇门 → 哪个目标」，而不是含糊地说"这间房有 4 个出口"。

## 指令形态（GML 编译结果）

    Push VAR=x / PushI lo / Cmp / Bf          ← x >= lo
    Push VAR=x / PushI hi / Cmp / B / PushI 0 / Bf   ← x <= hi（短路）

## 验收
解出的区间必须**恰好包含一扇**门实例的 x（多数分支），否则解析不可信。
"""
import io
import json
import os
import re
import sys
import collections

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
EV168 = os.path.join(REPO, 'code-quality-audit', '第168轮-W门补齐', '_evidence')
EV42 = os.path.join(REPO, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
EV = os.path.join(ROUND, '_evidence')
OUT = os.path.join(EV, 'branch_x169.json')

INS = re.compile(r'^\s*(-?\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s*(.*)$')
CODE = ('gml_Object_obj_doorW_Alarm_2', 'gml_Object_obj_doorw_musfade_Alarm_2')
CH = [('ch1', 'conn42b.json', 'inst42.json'),
      ('ch2', 'ch2_conn42b.json', 'ch2_inst42.json')]


def jl(p):
    s = io.open(p, encoding='utf-8', newline='').read()
    return json.loads(s.replace(': True', ': true').replace(': False', ': false'))


def load_blocks(p):
    L = io.open(p, encoding='utf-8', errors='replace', newline='').read().split('\n')
    cur, buf, blocks = None, [], {}
    for ln in L:
        if ln.startswith('### '):
            if cur:
                blocks[cur] = buf
            cur = ln[4:].split('   ')[0].strip()
            buf = []
        elif cur:
            buf.append(ln)
    if cur:
        blocks[cur] = buf
    return blocks


def parse(block):
    rows = []
    for ln in block:
        m = INS.match(ln)
        if not m:
            continue
        rows.append((int(m.group(1)), m.group(2), m.group(5).strip()))
    rows.sort()
    return rows


def _int_tail(tail):
    m = re.search(r'(-?\d+)\s*$', tail or '')
    return int(m.group(1)) if m else None


def letter_of(n):
    if isinstance(n, int) and 1 <= n <= 26:
        return chr(ord('A') + n - 1)
    return None


def scan(rows):
    u"""=> [(room, entrance, dst, xlo, xhi, idx)]"""
    out = []
    room = None
    entrance = None
    last = None
    want_x = False          # 上一个 Push 是 VAR=x
    xnums = []              # 本次 x 判断里出现过的常量
    #: ★★★ 只在「刚 push 完 `room`」之后的那一个 `Cmp` 才算房间守卫。
    #   否则 x 判断、`if (flag == …)` 之类的杂项 `Cmp` 会把常量写成房间号
    #   —— 第一版就是这么错的：解出 `src=12562 / 18113` 这种越界值。
    room_pending = False
    for idx, kind, tail in rows:
        if kind.startswith('Push'):
            if kind == 'PushBltn' and 'VAR=room' in tail:
                room, last, want_x, xnums = None, None, False, []
                room_pending = True
                continue
            if 'VAR=x' in tail:
                want_x = True
                last = None
                continue
            v = _int_tail(tail)
            if v is not None:
                last = v
                if want_x:
                    xnums.append(v)
                    want_x = False
                continue
            last = None
            continue
        if kind == 'Cmp':
            if xnums:
                pass            # x 比较，不动 room
            elif room_pending and last is not None:
                room = last
                room_pending = False
            continue
        if kind == 'Pop' and 'VAR=entrance' in tail and last is not None:
            entrance = last
            continue
        if kind == 'Call' and 'FN=room_goto' in tail and last is not None:
            if room is not None:
                lo = xnums[0] if xnums else None
                hi = xnums[1] if len(xnums) > 1 else None
                out.append((room, entrance, last, lo, hi, idx))
            xnums = []
            continue
    return out


def main():
    ev = {'note': u'第169轮 · W 门分支级解析（含 x 区间）', 'chapters': {}}
    for ch, cf, inf in CH:
        blocks = load_blocks(os.path.join(EV168, 'probe168_%s.txt' % ch))
        conn = jl(os.path.join(EV42, cf))
        rn = conn['room_names']
        inst = jl(os.path.join(EV42, inf))
        doors = {}
        for r in inst['rooms']:
            doors[r['index']] = sorted(
                int(o.get('x') or 0) for o in r['insts']
                if (o.get('obj') or '') in ('obj_doorW', 'obj_doorw_musfade'))
        rows = []
        for name in sorted(blocks):
            if name not in CODE:
                continue
            for (rm, ent, dst, lo, hi, idx) in scan(parse(blocks[name])):
                xs = doors.get(rm) or []
                if lo is None:
                    #: ★ 没有 x 条件的分支（电梯/剧情开关）**不能**把全部门都算命中
                    #   —— 那是"不知道"冒充"都知道"。
                    hit = None
                else:
                    hit = [x for x in xs if x >= lo and (hi is None or x <= hi)]
                rows.append({'src': rm, 'dst': dst, 'entrance': ent,
                             'letter': letter_of(ent), 'code': name, 'ins': idx,
                             'xlo': lo, 'xhi': hi, 'door_x': xs,
                             'x_hit': hit, 'src_name': rn[rm] if rm < len(rn) else '',
                             'dst_name': rn[dst] if dst < len(rn) else ''})
        ev['chapters'][ch] = rows
        c = collections.Counter(len(r['x_hit']) if r['x_hit'] is not None else -1
                                for r in rows)
        print(u'%s 分支 %d 条；带 x 区间 %d 条；命中门实例数分布 %r（-1 = 该分支无 x 条件）'
              % (ch, len(rows), sum(1 for r in rows if r['xlo'] is not None), dict(c)))

    # ---- 抽样自证：多门房间必须一区间对一门 ----
    print()
    print(u'-- 抽样：多门房间的区间 vs 门 x --')
    for ch, rows in ev['chapters'].items():
        by = collections.defaultdict(list)
        for r in rows:
            by[r['src']].append(r)
        for rm, v in sorted(by.items()):
            xs = v[0]['door_x']
            if len(xs) < 2 or len(v) < 2:
                continue
            print(u'  %s room=%-4d %-40s 门x=%r' % (ch, rm, v[0]['src_name'][:40], xs))
            for r in v:
                print(u'      x=[%s,%s] -> %-44s 命中=%r'
                      % (r['xlo'], r['xhi'], r['dst_name'][:44], r['x_hit']))
            if len(xs) >= 2:
                print()
            break

    os.makedirs(EV, exist_ok=True)
    text = json.dumps(ev, ensure_ascii=False, indent=1)
    io.open(OUT, 'wb').write(text.replace('\n', '\r\n').encode('utf-8'))
    print(u'落盘 %s (%d B)' % (OUT, os.path.getsize(OUT)))


if __name__ == '__main__':
    main()
