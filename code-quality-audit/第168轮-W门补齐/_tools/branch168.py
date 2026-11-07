# -*- coding: utf-8 -*-
u"""第168轮 · 分支级解析：把 `room_goto` 与**它所在分支的 `entrance`** 配起来。

## 为什么必须按分支

`obj_doorW_Alarm_2` 不是"一扇门一个常量"：

    ch1   assigns=[23]                          ← 单分支
    ch2   assigns=[23, 20, 23, 20, 22, …]       ← **145 次**，值域 19~24

而 19~24 正好是字母序 `S=19 / T=20 / U=21 / V=22 / W=23 / X=24`。
⇒ `entrance = N` 的含义是"在新房间的**第 N 个字母**出生点出现"，
   每个 `room_goto` 分支可以各自指定。

## 所以判据可以是**逐条**的

    对每条 `if (room == N) { entrance = E; room_goto(M) }`：
        目标房 M 必须含 `obj_marker<letter(E)>`
⇒ 不再是"整类门 92.8%"，而是**一条一条**对得上。

## 输出

`branch168.json`：`{章: [{src, dst, entrance, letter, code}]}`，
以及一份对不上目标的清单（供报告逐条写）。
"""
import io
import json
import os
import re
import sys
import collections

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence')
OUT = os.path.join(EV, 'branch168.json')

INS = re.compile(r'^\s*(\d+)\s+(Push\w*|Pop\w*|Cmp|Bf|B|Call|Conv|Dup|Ret|Exit|Popz|Bltn)\s+'
                 r'(\S+)\s+(\S+)\s*(.*)$')
LASTI = re.compile(r'^\s*(-?\d+)\s*$')


def parse_ins(block):
    u"""把一段指令文本解析成 [(idx, kind, t1, tail)]。"""
    rows = []
    for ln in block:
        m = INS.match(ln)
        if not m:
            continue
        rows.append((int(m.group(1)), m.group(2), m.group(3), m.group(5).strip()))
    rows.sort()
    return rows


def letter_of_n(n):
    u"""1 → 'A'、23 → 'W'、24 → 'X'（超出 A~Z 返 None）。"""
    if not isinstance(n, int) or not (1 <= n <= 26):
        return None
    return chr(ord('A') + n - 1)


def scan(block):
    u"""线性扫一遍，产出 (room_guard, entrance, dst) 三元组。

    ★ 这是**近似**（不建 CFG）：`Bf` 的跳转目标没跟，只维护"最近一次
      `PushBltn room / PushI N / Cmp / Bf` 的 N"。对本作这种
      "一串并列 `if (room == N)`" 的写法足够；嵌套 `if (x …)` 不改 N，
      所以嵌套分支仍归到正确的房间。
    ★ 也必须承认它的局限：`else` 分支会被算进上一个 N（见报告 §踩坑）。
    """
    out = []
    guard = None
    entrance = None
    last = None
    for idx, kind, t1, tail in block:
        if kind.startswith('Push'):
            m = LASTI.search(tail)
            val = int(m.group(1)) if m else None
            if kind == 'PushBltn' and 'VAR=room' in tail:
                guard = ('room', None)
                last = None
                continue
            last = val
        if kind == 'Cmp' and guard == ('room', None) and last is not None:
            guard = ('room', last)
            continue
        if kind == 'Pop' and 'VAR=entrance' in tail and last is not None:
            entrance = last
            continue
        if kind == 'Call' and 'FN=room_goto' in tail and last is not None:
            if guard and guard[0] == 'room' and isinstance(guard[1], int):
                out.append((guard[1], entrance, last, idx))
            continue
    return out


def main():
    packs = {}
    for ch in ('ch1', 'ch2'):
        p = os.path.join(EV, 'probe168_%s.txt' % ch)
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
        packs[ch] = blocks

    out = {'note': (u'第168轮 分支级解析：`entrance` 与 `room_goto` 按分支配对。'
                    u'`letter` = 字母序（1=A … 23=W 24=X）。'),
           'chapters': {}}
    for ch, blocks in packs.items():
        rows = []
        for name in sorted(blocks):
            if 'doorW_Alarm_2' not in name and 'doorw_musfade_Alarm_2' not in name:
                continue
            for src, ent, dst, idx in scan(parse_ins(blocks[name])):
                rows.append({'src': src, 'dst': dst, 'entrance': ent,
                             'letter': letter_of_n(ent), 'code': name, 'ins': idx})
        out['chapters'][ch] = rows
        c = collections.Counter(r['letter'] for r in rows)
        print(u'%s：%d 条 (src,dst,entrance) 三元组  字母分布 %r' % (ch, len(rows), dict(c)))
        print(u'   entrance 值缺失 %d 条' % sum(1 for r in rows if r['entrance'] is None))

    text = json.dumps(out, ensure_ascii=False, indent=1)
    io.open(OUT, 'wb').write(text.replace('\n', '\r\n').encode('utf-8'))
    print(u'落盘 %s (%d B)' % (OUT, os.path.getsize(OUT)))


if __name__ == '__main__':
    main()
