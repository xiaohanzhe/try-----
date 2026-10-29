# -*- coding: utf-8 -*-
u"""第119轮 · 把 GML 里的每个候选键标注「守卫类型」，并算出**能多读多少**

## 起因（本轮实测）

`audit119.py` 对账结果：现有正文表 **0 组污染**（117 轮的映射没错），但
**ut 少 105 组 / outertale 少 78 组**候选键。缺的这批正是第117轮用「指令流里
`PushBltn room` 后紧跟的 `PushI`」当守卫时被丢掉的 —— 那个 `pending` 只被
**下一个字符串 push** 消费一次，同一房间块里第 2 个及以后的键就拿不到房间，
被记成 `-1`（无守卫）后跳过。GML 解析（118 轮）没有这个限制。

## 本脚本产出什么

对每个 `(场景, 对象, 键)` 给出**守卫类型**：
    base   除 `room == X` 外**没有其它条件** ⇒ 只要进这间房就会显示
    pos    只多出 `x` / `y` 的比较 ⇒ **能按实例坐标静态判**
    state  还有剧情/全局变量/函数调用 ⇒ 只能运行时判，产品侧只能取默认并标注
    else   `ELSE_IF:` / `ELSE_OF:` 之类的派生条件 ⇒ 归 state（不猜）

★ 为什么必须先分这三类：`base` 是"这间房一定有正文"，`pos` 是"按 x 选"，
  `state` 是"没有状态就没法选"。混在一起谈"覆盖率"就是拿数字骗自己。

产物：`_evidence/readable_plan119.<game>.tsv`
     scene \t obj \t key \t guard \t guard_text \t instances
     另：`_evidence/readable_plan119.<game>.unresolved.tsv`
     room \t obj \t key \t why   —— 没房间条件 / 房间在产品里没有场景（**如实登记，不丢**）
"""
import collections
import glob
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
ROOT = os.path.normpath(os.path.join(ROUND, '..', '..'))
EV = os.path.join(ROUND, '_evidence')
RAW = os.path.join(EV, 'raw')
SCENES = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')

GAMES = ('ut', 'outertale')
ALARM_OBJ = re.compile(r'^gml_Object_(.+)_Alarm_0$')
RE_ROOM = re.compile(r'^room\s*==\s*(\w+)$')
RE_POS = re.compile(r'^(x|y)\s*(<=|>=|==|!=|<|>)\s*(-?\d+)$')


def classify_guard(conds):
    """→ (guard, 其余条件的原文)"""
    rest = []
    for tok in conds:
        t = tok.strip()
        if not t:
            continue
        if RE_ROOM.match(t):
            continue
        rest.append(t)
    if not rest:
        return 'base', ''
    if all(RE_POS.match(t) for t in rest):
        return 'pos', ' && '.join(rest)
    return 'state', ' && '.join(rest)


def main():
    name_oid = {}
    oid_sid = {}
    inst_cnt = collections.Counter()
    grand = collections.Counter()
    for game in GAMES:
        cur = None
        for ln in io.open(os.path.join(RAW, game, 'inst_full.tsv'), encoding='utf-8'):
            q = ln.rstrip('\n').split('\t')
            if q[0] == 'R':
                cur = q[2]
                name_oid[(game, q[2])] = int(q[1])
            elif q[0] == 'I':
                inst_cnt[(game, cur, q[1])] += 1
        for p in sorted(glob.glob(os.path.join(SCENES, '_zone.%s.*.json' % game))):
            try:
                d = json.load(io.open(p, encoding='utf-8'))['scenes']
            except Exception:
                continue
            for sid, s in d.items():
                oid = s.get('original_room_id')
                if isinstance(oid, int):
                    oid_sid[(game, oid)] = sid

        p = os.path.join(EV, 'readable_conds118.%s.tsv' % game)
        rows = []
        unresolved = []
        c = collections.Counter()
        for ln in io.open(p, encoding='utf-8'):
            q = ln.rstrip('\n').split('\t')
            if len(q) != 5 or q[0] == 'alarm':
                continue
            alarm, _d, cond, target, key = q
            if not target.startswith('msg['):
                continue                     # msc 交给脚本，另行处理
            m = ALARM_OBJ.match(alarm)
            if not m:
                continue
            obj = m.group(1)
            conds = [t.strip() for t in cond.split(' && ')] if cond else []
            room = None
            for t in conds:
                mr = RE_ROOM.match(t)
                if mr:
                    room = mr.group(1)
                    break
            if not room:
                c['no_room'] += 1
                unresolved.append(('', obj, key, 'no_room_guard'))
                continue
            oid = name_oid.get((game, room))
            sid = oid_sid.get((game, oid)) if oid is not None else None
            if sid is None:
                c['no_scene'] += 1
                unresolved.append((room, obj, key, 'room_without_scene'))
                continue
            guard, gtxt = classify_guard(conds)
            c['guard_' + guard] += 1
            rows.append((sid, obj, key, guard, gtxt, target, room))

        if not rows:
            print(u'[FAIL] %s 一行都没产出 —— 本脚本什么也没证明' % game)
            return 1

        # 同一 (scene,obj,key) 可能因多个 target（msg[0]/msg[1]）出现多次 ⇒ 去重保序
        seen = set()
        uniq = []
        for r in rows:
            k = (r[0], r[1], r[2], r[3], r[4])
            if k in seen:
                continue
            seen.add(k)
            uniq.append(r)

        out = os.path.join(EV, 'readable_plan119.%s.tsv' % game)
        with io.open(out, 'w', encoding='utf-8', newline='\n') as f:
            f.write(u'scene\tobj\tkey\tguard\tguard_text\tinstances\n')
            for r in uniq:
                n = inst_cnt.get((game, r[6], r[1]), 0)
                f.write(u'%s\t%s\t%s\t%s\t%s\t%d\n' % (r[:5] + (n,)))
        up = os.path.join(EV, 'readable_plan119.%s.unresolved.tsv' % game)
        with io.open(up, 'w', encoding='utf-8', newline='\n') as f:
            f.write(u'room\tobj\tkey\twhy\n')
            for r in unresolved:
                f.write(u'%s\t%s\t%s\t%s\n' % r)

        # 每组的"有没有 base / 只有 state"统计
        per = collections.defaultdict(set)
        for r in uniq:
            per[(r[0], r[1])].add(r[3])
        only_state = sum(1 for v in per.values() if v == {'state'})
        has_base = sum(1 for v in per.values() if 'base' in v)
        has_pos = sum(1 for v in per.values() if 'pos' in v)

        print(u'=== %s：候选 %d 条（去重前 %d）/ %d 组' % (game, len(uniq), len(rows), len(per)))
        print(u'    base %d / pos %d / state %d 条；无房间条件 %d，无场景 %d'
              % (c['guard_base'], c['guard_pos'], c['guard_state'],
                 c['no_room'], c['no_scene']))
        print(u'    有 base 的组合 %d / 有 pos %d / **只有 state**（无状态就读不到） %d'
              % (has_base, has_pos, only_state))
        _dead = sum(1 for r in uniq if inst_cnt.get((game, r[6], r[1]), 0) == 0)
        print(u'    ★ 该房间**没摆**这个可读物（实例 0）的候选 %d 条 —— 是死代码，'
              u'不进产品资产（第117轮的纪律：只收真的摆了的组合）' % _dead)
        grand.update(c)
        grand['groups_' + game] = len(per)
        grand['dead'] += _dead

    print(u'\n合计 base %d / pos %d / state %d；死代码候选 %d'
          % (grand['guard_base'], grand['guard_pos'], grand['guard_state'], grand['dead']))
    print(u'落盘：_evidence/readable_plan119.<game>.tsv (+ .unresolved.tsv)')
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
