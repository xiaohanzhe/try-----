# -*- coding: utf-8 -*-
u"""第122轮侦察：ut 的门**通向哪**？能不能从可信边解出 (房间, 门对象) → 目标房间。

## 为什么不能照抄 Deltarune 那套

Deltarune 的门是**字母门**（`obj_doorA~F`），字母本身就是出口标识，控制器按
「当前房间 + 字母」去 `Data.Rooms` 算**下标位移**（A+1/B-1/C+2）。所以
`door_letter_of(src)` 拿字母、`route_for_door(routes, sid, letter)` 查表就完事。

ut 的门**没有字母**，名字是 `obj_door_ruins13` / `obj_door_s_musfade` / `obj_door` 这种
—— `door_letter_of` 对它们一律返 `None` ⇒ `build_props` 的门分支**根本走不到查表**
⇒ 1,299 个门的实例一个都不会变成 `DoorProp`。这就是本轮要解决的那一层。

## 数据从哪来

第115轮的 `conn115.json`（**可信边**）里 ut 段是
`{code, src, dst, src_name, dst_name}`：
  · `code` 是**反编译出来的 GML 函数名**，形如 `gml_Object_obj_door_ruins13_Alarm_2`
    ⇒ 能从中取出**门对象名**；
  · `src`/`dst` 是房间下标，`src_name`/`dst_name` 是房间名。
⇒ 键 = `(src_name, 门对象名)`，值 = `dst_name`。

## 三条纪律

1. **同名多目标 = 条件分支，一律不猜**。同一个 `obj_door_ruins13` 在多间房复用，
   靠 `if (room == N) room_goto(M)` 分流 ⇒ 「同一 (房间, 对象) 对多个目标」时**丢掉**，
   只留"唯一目标"的那批。
2. **必须落在真实例上**。路由只有当那个场景里**真有**这个对象的实例时才写，
   否则就是"表里有一条、场上没有那扇门"。
3. **目标必须是已登记场景**。`dst_name` 找不到对应 scene_id 的不写（不造场景）。

用法：python probe_doors122.py
"""
import collections
import io
import json
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
RAW115 = os.path.join(os.path.dirname(ROUND), '第115轮-跨作品物件普查', '_evidence')
RAW = os.path.join(RAW115, 'raw', 'ut')

ZONE = os.path.join(SCENES, '_zone.ut.rooms.json')
CONN = os.path.join(RAW115, 'conn115.json')
OBJMAP = os.path.join(RAW, 'objmap_ut.txt')
INST = os.path.join(RAW, 'inst_full.tsv')


def _rows(p):
    for ln in io.open(p, encoding='utf-8', newline='').read().split('\n'):
        if ln:
            yield ln.split('\t')


def _json(p):
    with io.open(p, encoding='utf-8', newline='') as f:
        return json.load(f)


def obj_of_code(code, names):
    u"""`gml_Object_obj_door_ruins13_Alarm_2` → `obj_door_ruins13`（**最长前缀匹配**）。

    ★ 不用"砍掉最后一个 `_xxx`"那种写法：对象名自己就带下划线（`obj_door_s_musfade`），
      砍一刀会得到 `obj_door_s`，那是另一个（或不存在的）对象。
      ⇒ 拿 ut 的 objmap 里的**真实对象名**去匹配最长前缀 = 不会凭空造名字。
    """
    if not isinstance(code, str) or not code.startswith('gml_Object_'):
        return None
    tail = code[len('gml_Object_'):]
    best = None
    for nm in names:
        if tail == nm or tail.startswith(nm + '_'):
            if best is None or len(nm) > len(best):
                best = nm
    return best


def main():
    scenes = _json(ZONE)['scenes']
    by_name = {}
    for sid, sc in scenes.items():
        if isinstance(sc, dict) and sc.get('name'):
            by_name.setdefault(sc['name'], []).append(sid)

    objs = [r[1] for r in _rows(OBJMAP) if len(r) >= 5 and r[0] != 'GameObjects']
    objset = set(objs)

    # 实例：房间名 → 该房间出现过哪些对象（只要对象名，够判"这扇门真在场"）
    insts = collections.defaultdict(set)
    cur = None
    for r in _rows(INST):
        if r[0] == 'R':
            cur = r[2]
        elif r[0] == 'I' and cur is not None:
            insts[cur].add(r[1])

    edges = _json(CONN)['ut']['edges']
    print(u'== 输入 ==')
    print(u'conn115.ut.edges = %d 条' % len(edges))

    bad_code = [e for e in edges if obj_of_code(e.get('code'), objset) is None]
    print(u'  · code 认不出对象名：%d 条（样本 %s）'
          % (len(bad_code), [e.get('code') for e in bad_code[:3]]))

    grp = collections.defaultdict(set)
    obj_of = {}
    for e in edges:
        o = obj_of_code(e.get('code'), objset)
        if o is None:
            continue
        k = (e.get('src_name'), o)
        grp[k].add(e.get('dst_name'))
        obj_of[k] = e.get('code')

    print(u'  · (房间, 门对象) 组合：%d' % len(grp))
    amb = {k: v for k, v in grp.items() if len(v) > 1}
    print(u'  · 其中多目标（条件分支，**不猜**）：%d' % len(amb))
    for k, v in list(amb.items())[:5]:
        print(u'      %r → %s' % (k, sorted(v)[:4]))

    one = {k: next(iter(v)) for k, v in grp.items() if len(v) == 1}

    # 三层过滤
    no_inst, no_scene, no_dst = [], [], []
    ok_rows = []
    for (rn, o), dn in sorted(one.items()):
        if o not in insts.get(rn, ()):
            no_inst.append((rn, o))
            continue
        if rn not in by_name:
            no_scene.append((rn, o))
            continue
        if dn not in by_name:
            no_dst.append((rn, o, dn))
            continue
        ok_rows.append((rn, o, dn))

    print(u'')
    print(u'== 三层过滤 ==')
    print(u'  · 唯一目标 %d 条' % len(one))
    print(u'  · 该房间没有这个门的实例：%d' % len(no_inst))
    print(u'  · src 房间不在已登记场景里：%d' % len(no_scene))
    print(u'  · dst 房间不在已登记场景里：%d' % len(no_dst))
    print(u'  ⇒ **可用 %d 条**' % len(ok_rows))

    # 每个场景最多几个门对象？（决定 when_src 够不够精确）
    per_scene = collections.defaultdict(set)
    for rn, o, _dn in ok_rows:
        per_scene[rn].add(o)
    dist = collections.Counter(len(v) for v in per_scene.values())
    print(u'')
    print(u'== 粒度 ==')
    print(u'  · 覆盖场景 %d 个；每场景门对象个数分布 %s'
          % (len(per_scene), dict(sorted(dist.items()))))
    print(u'  · 覆盖 ut 场景的比例：%d / %d = %.1f%%'
          % (len(per_scene), len(scenes), 100.0 * len(per_scene) / max(1, len(scenes))))

    # door 实例总数 vs 能被路由托住的实例数
    door_src = set()
    for o in objset:
        rec = None
        try:
            sys.path.insert(0, os.path.join(REPO, 'ralsei_pet', 'modules'))
            import item_interact as II
            rec = II.classify(o)
        except Exception:
            pass
        if rec and rec.get('kind') == 'door':
            door_src.add(o)
    n_door_inst = 0
    n_covered = 0
    for rn, got in insts.items():
        for o in got:
            if o in door_src:
                n_door_inst += 1
                if (rn, o) in one and rn in by_name and one[(rn, o)] in by_name:
                    n_covered += 1
    print(u'')
    print(u'== 覆盖率 ==')
    print(u'  · ut 里 kind=door 的对象 %d 个' % len(door_src))
    # ★★ 两个分母**物种不同**，不许混着算（第122轮自己踩到的第四个"分母换物种"）：
    #   · `insts` 在这里是 **presence 集合**（房间 → 对象名集合）⇒ 数出来的是
    #     **(房间,对象) 站位** 572 个；同一房间摆两个 `obj_doorA` 只算 1 个站位。
    #   · 真·实例数（同房多实例计多次）= **1,299**，由 `gen_routes122` 用
    #     `Counter[(房间,对象)] += 1` 数出来的，产品 `objects` 也是 548 条（每条实例一条）。
    #   · 下面的 `n_covered` **只认 conn115 的对象级边**，不含 133 条 `room_goto_next`
    #     字母级 ⇒ 它是**偏小的下界**，不是最终覆盖率。最终账见报告 §4。
    print(u'  · door **站位**（房间,对象）总数 %d（同一房间多个同种门只算 1）；'
          u'真·实例数 1,299' % n_door_inst)
    print(u'  · 仅按 conn115 对象级边能托住的**站位** %d（%.1f%%；不含 133 条字母级 '
          u'`room_goto_next`，故为下界）'
          % (n_covered, 100.0 * n_covered / max(1, n_door_inst)))

    print(u'')
    print(u'== 样本 10 条 ==')
    for rn, o, dn in ok_rows[:10]:
        print(u'  %-22s %-26s → %s' % (rn, o, dn))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
