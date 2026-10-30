# -*- coding: utf-8 -*-
u"""第123轮侦察：ut 的门到底怎么换房 —— 逐对象解析 `Alarm_2` 的**位移机制**（含继承）。

## 为什么第122轮少了 751 个实例

`conn_ut.csx` 的扫描只认两种写法：
  · `room_goto(<常量>)`
  · 函数名**字面**是 `room_goto_next` / `room_goto_previous`

而 ut 的门写的是：

```gml
// obj_doorB_Alarm_2
global.entrance = 2;
instance_create(0, 0, obj_persistentfader);
room_goto(room_previous(room));          // ← 目标是**函数调用**，不是常量
```

⇒ 目标非常量 ⇒ 落进 `n_nonconst_target: 30`，**永远变不成边**。

## 本轮机制表（GML 原文，逐字）

| 对象 | `Alarm_2` | 位移 |
|---|---|---|
| `obj_doorA` | `room_goto(room_next(room))` + `room_castle_prebarrier` 特例 | +1（**有条件分支**） |
| `obj_doorB` | `room_goto(room_previous(room))` | **−1** |
| `obj_doorC` / `obj_doorCmusicfade` | `room_goto(room_next(room_next(room)))` | **+2** |
| `obj_doorD` / `obj_doorDmusicfade` | `room_goto(room_previous(room_previous(room)))` | **−2** |
| `obj_doorAmusicfade` / `obj_doorBmusicfade` | **自己没有 Alarm_2** ⇒ 从父对象继承 | 同 A / B |
| `obj_elevatordoor` | 电梯 UI（`event_user(0)`），不是门位移 | 不适用 |

⇒ 与 Deltarune 的「A+1 / B−1 / C+2」**同一套约定**（同一个作者的两部作品）。

用法：python probe_doors123.py
"""
import collections
import io
import json
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
RAW = os.path.join(ROUND, '_evidence', 'raw', 'ut')
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
RAW115 = os.path.join(os.path.dirname(ROUND), '第115轮-跨作品物件普查', '_evidence', 'raw', 'ut')

CODES = os.path.join(RAW, 'door_codes123.json')
OBJECTS = os.path.join(RAW, 'door_objects123.json')
ZONE = os.path.join(SCENES, '_zone.ut.rooms.json')
INST = os.path.join(RAW115, 'inst_full.tsv')
OBJMAP = os.path.join(RAW115, 'objmap_ut.txt')

#: `room_goto(room_next(room))` 这类**以调用为参数**的写法，逐个显式匹配（不猜）
SHIFT_PATTERNS = [
    (re.compile(r'room_goto\s*\(\s*room_next\s*\(\s*room\s*\)\s*\)\s*;'), 1, u'room_next(room)'),
    (re.compile(r'room_goto\s*\(\s*room_previous\s*\(\s*room\s*\)\s*\)\s*;'), -1,
     u'room_previous(room)'),
    (re.compile(r'room_goto\s*\(\s*room_next\s*\(\s*room_next\s*\(\s*room\s*\)\s*\)\s*\)\s*;'), 2,
     u'room_next(room_next(room))'),
    (re.compile(r'room_goto\s*\(\s*room_previous\s*\(\s*room_previous\s*\(\s*room\s*\)\s*\)\s*\)\s*;'),
     -2, u'room_previous(room_previous(room))'),
    (re.compile(r'room_goto_next\s*\(\s*\)\s*;'), 1, u'room_goto_next()'),
    (re.compile(r'room_goto_previous\s*\(\s*\)\s*;'), -1, u'room_goto_previous()'),
]

#: `if (<条件>)` 里提到房间名的，那个房间**不许套通用位移**（分支会改目标）
RE_IFCOND = re.compile(r'if\s*\(([^)]*)\)')


def cond_rooms_of(src):
    u"""从 Alarm 源码里取出「出现在 if 条件里的房间名」。

    ★ 只用 `if (...)` 的**条件文本**，不扫整段（第一版拿"房间名后面 400 字"当窗口，
      会把相邻分支的目标也算进来 —— 实测 `obj_doorXmusicfade` 一个房间冒出 5 个目标，
      那不是原作，是我的窗口太宽）。
    ★ `room != room_x` 同样算 —— `obj_doorA` 就是 `if (room != room_castle_prebarrier)`
      走 +1、`else` 里按 `global.flag[7]` 分叉 ⇒ prebarrier **必须排除**。
    """
    out = set()
    for m in RE_IFCOND.finditer(src):
        cond = m.group(1)
        if 'room' not in cond:
            continue
        for rn in re.findall(r'room_(\w+)', cond):
            out.add(rn)
    return out


def _json(p):
    with io.open(p, encoding='utf-8', newline='') as f:
        return json.load(f)


def _rows(p):
    for ln in io.open(p, encoding='utf-8', newline='').read().split('\n'):
        if ln:
            yield ln.split('\t')


def obj_of_code(code, names):
    u"""`gml_Object_obj_door_ruins13_Alarm_2` → `obj_door_ruins13`（最长前缀匹配）。"""
    if not code.startswith('gml_Object_'):
        return None
    tail = code[len('gml_Object_'):]
    best = None
    for nm in names:
        if (tail == nm or tail.startswith(nm + '_')) and (best is None or len(nm) > len(best)):
            best = nm
    return best


def event_of(code):
    u"""`gml_Object_obj_doorB_Alarm_2` → `Alarm_2`。"""
    return code[code.rfind('_', 0, code.rfind('_')) + 1:] if code.count('_') >= 3 else ''


def shift_of(src):
    u"""从一段 Alarm 代码里取位移（返回 (shift, 命中写法) 或 (None, 原因)）。"""
    hits = []
    for rx, off, why in SHIFT_PATTERNS:
        if rx.search(src):
            hits.append((off, why))
    if not hits:
        return None, u'无位移写法'
    offs = set(h[0] for h in hits)
    if len(offs) > 1:
        return None, u'同一段里有多个不同位移 %s' % sorted(offs)
    return hits[0][0], hits[0][1]


def main():
    codes = _json(CODES)['codes']
    objs = _json(OBJECTS)['objects']
    names = set(o['name'] for o in objs)
    parent = {o['name']: (o.get('parent') or '') for o in objs}

    # (对象, 事件) -> 源码
    src_of = {}
    for it in codes:
        o = obj_of_code(it['name'], names)
        if not o:
            continue
        src_of[(o, event_of(it['name']))] = it['src']

    print(u'== 输入 ==')
    print(u'  door 事件代码 %d 条 / door 对象 %d 个 / 有父对象 %d 个'
          % (len(codes), len(objs), sum(1 for v in parent.values() if v)))

    def alarm_of(o, depth=0):
        u"""沿父链找 `Alarm_2`，返回 (源码, 真源对象, 层数)。"""
        seen = set()
        cur = o
        while cur and cur not in seen and depth < 8:
            seen.add(cur)
            s = src_of.get((cur, 'Alarm_2'))
            if s is not None:
                return s, cur, depth
            cur = parent.get(cur, '')
            depth += 1
        return None, None, depth

    print(u'')
    print(u'== 逐对象的有效位移（沿父链解析）==')
    mech = {}          # 对象 -> (shift, 写法, 真源对象, 条件分支列表)
    for o in sorted(names):
        s, srcobj, d = alarm_of(o)
        if s is None:
            mech[o] = (None, u'父链上都没有 Alarm_2', None, [])
            print(u'  %-24s %-28s' % (o, u'—— 无 Alarm_2（父链为空）'))
            continue
        off, why = shift_of(s)
        conds = sorted(cond_rooms_of(s))
        mech[o] = (off, why, srcobj, conds)
        tag = u'继承自 %s' % srcobj if srcobj != o else u'自有'
        print(u'  %-24s %-30s %+d  [%s]%s'
              % (o, why, off if off is not None else 0, tag,
                 (u'  ⚠条件分支 %s' % conds) if conds else u'')
              if off is not None else
              u'  %-24s %s' % (o, why))

    # ---- 条件分支：条件里点名的房间，一律**不套通用位移**（只记账，不猜）----
    print(u'')
    print(u'== 条件分支（条件里点名的房间 ⇒ 排除在通用位移之外）==')
    cond_rooms = {}
    for o, (off, why, srcobj, conds) in sorted(mech.items()):
        if not conds:
            continue
        cond_rooms[o] = [(rn, None) for rn in conds]
        print(u'  %-24s 排除房间 %s' % (o, conds))

    # ---- 覆盖账：拿实例表逐 (房间, 对象) 算 ----
    zone = _json(ZONE)
    scenes = zone['scenes']
    rid2sid, name2sid = {}, {}
    for sid, sc in scenes.items():
        if not isinstance(sc, dict):
            continue
        rid = sc.get('original_room_id')
        if isinstance(rid, int):
            rid2sid[rid] = sid
            name2sid[sc.get('name')] = (sid, rid)
    objs_all = set(r[1] for r in _rows(OBJMAP) if len(r) >= 5 and r[0] != 'GameObjects')
    insts = collections.Counter()
    cur = None
    for r in _rows(INST):
        if r[0] == 'R':
            cur = r[2]
        elif r[0] == 'I' and cur is not None:
            insts[(cur, r[1])] += 1

    door_kinds = set(o for o in objs_all if o in names)
    n_door_inst = sum(n for (rn, o), n in insts.items() if o in door_kinds)
    print(u'')
    print(u'== 覆盖账（分母 = 门实例 %d）==' % n_door_inst)

    # 第122轮已经写了哪些（读它的事实文件，不调它的代码 —— 免得"自己验自己"）
    done = set()
    fp122 = os.path.join(os.path.dirname(ROUND), '第122轮-ut门与房间连接',
                         '_evidence', 'ut_doors122.json')
    if os.path.isfile(fp122):
        for r in _json(fp122).get('routes') or []:
            o = r.get('when_src') or 'obj_doorA'
            done.add(((r.get('_original') or {}).get('src_room_name'), o))

    add = collections.defaultdict(int)      # 新增可写的
    covered122 = 0
    for (rn, o), n in sorted(insts.items()):
        if o not in door_kinds:
            continue
        if (rn, o) in done:
            covered122 += n
            continue
        off = mech.get(o, (None,))[0]
        if off is None:
            continue
        src_pair = name2sid.get(rn)
        if not src_pair:
            continue
        src_sid, rid = src_pair
        # 条件分支房间：通用位移不适用 ⇒ 不写（留账）
        if any(cr == rn for cr, _t in cond_rooms.get(o, [])):
            continue
        dst = rid2sid.get(rid + off)
        if not dst:
            continue
        add[(rn, o, dst, off)] += n

    n_add = sum(add.values())
    print(u'  第122轮已托住 %d（%d 组）' % (covered122, len(done)))
    print(u'  本轮可新增 %d（%d 组）⇒ 合计 %d / %d = %.1f%%'
          % (n_add, len(add), covered122 + n_add, n_door_inst,
             100.0 * (covered122 + n_add) / max(1, n_door_inst)))

    print(u'')
    print(u'== 新增按对象分账 ==')
    byo = collections.Counter()
    for (rn, o, _d, _off), n in add.items():
        byo[o] += n
    for o, n in byo.most_common():
        print(u'  %-24s %4d 组 / %4d 实例  位移 %+d'
              % (o, sum(1 for k in add if k[1] == o), n, mech[o][0]))

    print(u'')
    print(u'== 仍未覆盖（逐类，只列前 12）==')
    left = collections.Counter()
    for (rn, o), n in insts.items():
        if o not in door_kinds or (rn, o) in done:
            continue
        off = mech.get(o, (None,))[0]
        pair = name2sid.get(rn) or (None, -999)
        if off is None or not rid2sid.get(pair[1] + off) \
                or any(cr == rn for cr, _t in cond_rooms.get(o, [])):
            left[o] += n
    for o, n in left.most_common(12):
        m = mech.get(o) or (None, u'?')
        print(u'  %-24s %4d 实例   %s' % (o, n, m[1]))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
