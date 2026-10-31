# -*- coding: utf-8 -*-
u"""第126轮取证探针 E：outertale 的**原始提取**（`conn_ut.json`，301 条 goto 记录）
按对象分组，判定"这个对象是不是门"，并给出它在**实例表**里的分布。

这一步回答的是「能不能把 outertale 从 0 条边做成有边」，所以先把账算清：
  · 哪些对象是门（名字 + 实例分布 + op 类型三者互证）
  · `goto_const_src`（源码里有 `if (room == N)`）→ 直接得 (src,dst)
  · `room_goto_next/previous` → 位移门（src 由实例位置决定）
  · `goto_const_nosrc`（无条件 `room_goto(CONST)`）→ src 由**实例所在房**决定
只读。
"""
import io
import os
import json
import collections

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
EV115 = os.path.join(REPO, 'code-quality-audit', '第115轮-跨作品物件普查', '_evidence')
RAW = os.path.join(EV115, 'raw', 'outertale')
CONN = os.path.join(RAW, 'conn_ut.json')
INST = os.path.join(RAW, 'inst_full.tsv')


def jload(p):
    s = io.open(p, encoding='utf-8', newline='').read()
    return json.loads(s.replace(': True', ': true').replace(': False', ': false'))


def obj_of(code):
    if not isinstance(code, str) or not code.startswith('gml_Object_'):
        return None
    s = code[len('gml_Object_'):]
    for suf in ('_Alarm_', '_Step_', '_Create_', '_Collision_', '_Draw_', '_Destroy_',
                '_Other_', '_KeyPress_', '_KeyRelease_', '_Mouse_'):
        i = s.find(suf)
        if i > 0:
            return s[:i]
    return s


rooms, inst = {}, collections.defaultdict(set)
cur = None
with io.open(INST, encoding='utf-8', errors='replace', newline='') as fh:
    for ln in fh:
        p = ln.rstrip('\r\n').split('\t')
        if p[0] == 'R' and len(p) >= 3:
            cur = int(p[1])
            rooms[cur] = p[2]
        elif p[0] == 'I' and len(p) >= 2 and cur is not None:
            inst[cur].add(p[1])
by_obj = collections.defaultdict(list)
for i, s in inst.items():
    for o in s:
        by_obj[o].append(i)

D = jload(CONN)
items = D['items']
print(u'items %d · op_counts %r' % (len(items), D.get('op_counts')))
print(u'样例 item：%s' % json.dumps(items[0], ensure_ascii=False))
print(u'')
grp = collections.defaultdict(lambda: collections.Counter())
for it in items:
    o = obj_of(it.get('code')) or '?'
    grp[o][it.get('op')] += 1
print(u'===== 按对象分组（%d 个对象）=====' % len(grp))
for o, c in sorted(grp.items(), key=lambda kv: -sum(kv[1].values())):
    locs = sorted(by_obj.get(o, []))
    door = (u'门' if (o.startswith('obj_door') or o.startswith('obj_demodoor')) else u'非门')
    print(u'  %-28s %-4s %-46s 实例房 %d 间 %s'
          % (o, door, dict(c), len(locs), (locs[:8] if len(locs) <= 8 else locs[:8] + ['...'])))
