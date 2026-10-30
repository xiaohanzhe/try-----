# -*- coding: utf-8 -*-
u"""第122轮：把 ut 的**门**接进路由表（本轮只写"有原作出处"的那 245 扇）。

## 为什么需要这一步（承接第121轮）

第121轮把 ut 的 `objects` 补上了（422 条可交互物），但**故意没写门**：
`build_props` 建门要 `route_for_door()` 查到目标，而 `_routes.json` 里 ut 段是空的
⇒ 写了也只是"推不开的门"。第121轮 §7 遗留第 1 条就是这件事。

## ut 的门跟 Deltarune 的不是一回事

| | Deltarune | ut |
|---|---|---|
| 名字 | `obj_doorA~F`（字母即出口标识） | 两种：`obj_doorA/B/C/D`（**也是字母**）+ `obj_door_ruins13` / `obj_door_s_musfade` / `obj_door_t/u/v/w` / `obj_doorXmusicfade`（**不带字母**） |
| 目标怎么定 | 控制器按「房间 + 字母」算**下标位移**（A+1/B-1/C+2） | 写在 **GML 里**：每间房一个 `if (room == X) room_goto(Y);`，或者 `room_goto_next()` |

⇒ 第二类（不带字母）用 `when_door` 表达不了，必须按 **(场景, 对象名)** 定位
⇒ 新增 `when_src` 这一路（见 `item_interact.route_for_door` 的 docstring）。

## 只写"有原作出处"的，不猜

本脚本**只用两层证据里的可信那一层**：

1. **`conn115.json` 的 ut 段**（131 条）：`code` 是**反编译出来的函数名**
   （`gml_Object_obj_door_ruins13_Alarm_2`），从中取出门对象名；
   键 = `(src_room, 门对象)` ⇒ 值 = `dst_room`。**同名多目标一律丢掉**（条件分支，不猜），
   再要求「该房间真有这个对象的实例」「两端都已登记为场景」⇒ **112 条**。
   ⇒ 写成 `when_src` 规则。

2. **`obj_doorA` 的 133 条**（来自 `conn_inferred115.json`）：`via=obj_doorA`、
   `off=+1`、`dst == src+1` **133/133** —— 这就是 `room_goto_next()` 的语义
   （下一个房间 = 资源序 +1）。这类**本来就是字母 A**（`door_letter_of('obj_doorA')=='A'`），
   所以走原有的字母机制，**不需要产品改动**。
   ★ 但**只写"那个房间真有 obj_doorA 实例"的**（没有实例就没有那扇门）。

★★ 候选层里 `via=obj_mainchara` 的 420 条**一条都不用**：那是"走到屏幕边缘换房"，
   `rule` 字段自己写着「摆了该对象的房间就存在这条边 **未经验证**」——
   拿它当门的目标就是编造。`obj_doorB/C/D` 在候选层里**没有**边 ⇒ 一条都不写（不猜）。

## 产物

· 就地更新 `ralsei_pet/assets/scenes/_routes.json`（保持 **CRLF / 2 空格缩进 / 无尾换行**）；
· 覆盖式：先删掉所有 `when_scene` 以 `ut.` 开头的条目，再追加 ⇒ **幂等**；
· `priority` 走**独立段 4000+**（原件 110~2478 / 桌面 200 / OneShot 3000~3419），
  追加在声明序末尾 ⇒ `verify_routes_order44.B3`（段内单调不减）仍成立。
· 同时落一份**事实文件** `_evidence/ut_doors122.json`（不含本脚本的决策字段），
  供 `check122` 独立重推期望值。

用法::

    python gen_routes122.py --dry     # 只打印统计
    python gen_routes122.py           # 写盘
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
EVID = os.path.join(ROUND, '_evidence')
RAW115 = os.path.join(os.path.dirname(ROUND), '第115轮-跨作品物件普查', '_evidence')
RAW = os.path.join(RAW115, 'raw', 'ut')

ZONE = os.path.join(SCENES, '_zone.ut.rooms.json')
ROUTES = os.path.join(SCENES, '_routes.json')
FACT = os.path.join(EVID, 'ut_doors122.json')

MODULES = os.path.join(REPO, 'ralsei_pet', 'modules')
sys.path.insert(0, MODULES)
import item_interact as II       # noqa: E402

#: ut 段的 priority 起点（独立段；见 docstring）
UT_PRIO_BASE = 4000

#: 只有这个对象有「room_goto_next」的证据（133/133 dst == src+1）
NEXT_DOOR_OBJ = 'obj_doorA'


def _rows(p):
    u"""逐行切成 tab 字段（**字节忠实**：`newline=''`，行尾不归一）。"""
    for ln in io.open(p, encoding='utf-8', newline='').read().split('\n'):
        if ln:
            yield ln.split('\t')


def _json(p):
    with io.open(p, encoding='utf-8', newline='') as f:
        return json.load(f)


def _write_like_original(path, data):
    u"""按仓库既有排版写回：`indent=2` + **CRLF** + **无尾换行**（实测与原文逐字节同构）。"""
    s = json.dumps(data, ensure_ascii=False, indent=2)
    with io.open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(s.replace('\n', '\r\n'))


def obj_of_code(code, names):
    u"""`gml_Object_obj_door_ruins13_Alarm_2` → `obj_door_ruins13`（**最长前缀匹配**）。

    ★ 不能"砍掉最后一个 `_xxx`"：对象名自己就带下划线（`obj_door_s_musfade`），
      砍一刀会得到 `obj_door_s`，那是另一个（或不存在的）对象。
    """
    if not isinstance(code, str) or not code.startswith('gml_Object_'):
        return None
    tail = code[len('gml_Object_'):]
    best = None
    for nm in names:
        if (tail == nm or tail.startswith(nm + '_')) and (best is None or len(nm) > len(best)):
            best = nm
    return best


def load_world():
    u"""载入 ut 的世界事实：场景表 / 对象表 / 实例表。"""
    zone = _json(ZONE)
    scenes = zone['scenes']
    name2sid, rid2sid = {}, {}
    for sid, sc in scenes.items():
        if not isinstance(sc, dict):
            continue
        if sc.get('name'):
            name2sid[sc['name']] = sid
        rid = sc.get('original_room_id')
        if isinstance(rid, int):
            rid2sid[rid] = sid
    objs = set(r[1] for r in _rows(os.path.join(RAW, 'objmap_ut.txt'))
               if len(r) >= 5 and r[0] != 'GameObjects')

    insts = collections.Counter()          # (room_name, obj) -> 实例数
    cur = None
    for r in _rows(os.path.join(RAW, 'inst_full.tsv')):
        if r[0] == 'R':
            cur = r[2]
        elif r[0] == 'I' and cur is not None:
            insts[(cur, r[1])] += 1
    return scenes, name2sid, rid2sid, objs, insts


def build_routes(name2sid, rid2sid, objs, insts):
    u"""算出两类路由条目 + 未采用账（**每一类丢在哪一步都记下来**）。"""
    stat = collections.Counter()
    drop = collections.defaultdict(list)
    out = []

    # ---- ① 对象级：可信层（反编译函数名 → 门对象）----
    edges = _json(os.path.join(RAW115, 'conn115.json'))['ut']['edges']
    grp = collections.defaultdict(set)
    code_of = {}
    for e in edges:
        o = obj_of_code(e.get('code'), objs)
        if o is None:
            stat['edge_bad_code'] += 1
            continue
        rec = II.classify(o)
        if not rec or rec.get('kind') != 'door':
            stat['edge_not_door'] += 1
            drop['edge_not_door'].append(o)
            continue
        k = (e.get('src_name'), o)
        grp[k].add(e.get('dst_name'))
        code_of[k] = e.get('code')

    for (rn, o), dsts in sorted(grp.items()):
        if len(dsts) != 1:
            stat['src_ambiguous'] += 1
            drop['src_ambiguous'].append((rn, o, sorted(dsts)))
            continue
        dn = next(iter(dsts))
        if not insts.get((rn, o)):
            stat['src_no_instance'] += 1
            drop['src_no_instance'].append((rn, o))
            continue
        sid_src, sid_dst = name2sid.get(rn), name2sid.get(dn)
        if not sid_src or not sid_dst:
            stat['src_unregistered'] += 1
            drop['src_unregistered'].append((rn, o, dn))
            continue
        out.append({
            'to': sid_dst,
            'priority': 0,                       # 下面统一编号
            'reason': u'原作 GML：房间 %s 里的 %s 触发 room_goto(%s)（取证 %s）。'
                      % (rn, o, dn, code_of[(rn, o)]),
            'when_scene': sid_src,
            'when_door': None,
            'when_src': o,
            '_original': {'kind': 'ut_door_src', 'code': code_of[(rn, o)],
                          'src_room_name': rn, 'dst_room_name': dn},
            'work': 'ut',
        })
        stat['src_ok'] += 1

    # ---- ② 字母级：obj_doorA = room_goto_next()（off=+1，133/133 自洽）----
    inf = _json(os.path.join(RAW115, 'conn_inferred115.json'))['ut']['edges']
    for e in inf:
        if e.get('via') != NEXT_DOOR_OBJ:
            continue
        stat['next_seen'] += 1
        rn, dn = e.get('src_name'), e.get('dst_name')
        if e.get('off') != 1 or e.get('dst') != (e.get('src') or 0) + 1:
            stat['next_not_plus1'] += 1
            drop['next_not_plus1'].append((rn, e.get('off'), e.get('src'), e.get('dst')))
            continue
        if not insts.get((rn, NEXT_DOOR_OBJ)):
            stat['next_no_instance'] += 1
            drop['next_no_instance'].append(rn)
            continue
        sid_src, sid_dst = name2sid.get(rn), name2sid.get(dn)
        if not sid_src or not sid_dst:
            stat['next_unregistered'] += 1
            drop['next_unregistered'].append((rn, dn))
            continue
        out.append({
            'to': sid_dst,
            'priority': 0,
            'reason': u'原作 GML：%s 的代码调用 room_goto_next()；房间 %s（下标 %d）'
                      u'→ %s（下标 %d）。' % (NEXT_DOOR_OBJ, rn, e.get('src'), dn, e.get('dst')),
            'when_scene': sid_src,
            'when_door': 'A',
            '_original': {'kind': 'ut_door_next', 'via': NEXT_DOOR_OBJ,
                          'src_room_name': rn, 'dst_room_name': dn,
                          'src_room_id': e.get('src'), 'dst_room_id': e.get('dst'),
                          'off': e.get('off')},
            'work': 'ut',
        })
        stat['next_ok'] += 1

    # 确定性：先对象级再字母级，各自按 (场景, 键) 排序 ⇒ 幂等
    out.sort(key=lambda x: (0 if x.get('when_src') else 1,
                            x['when_scene'], x.get('when_src') or '',
                            x.get('when_door') or ''))
    for i, r in enumerate(out):
        r['priority'] = UT_PRIO_BASE + i
    return out, stat, drop


def main(argv):
    dry = '--dry' in argv
    scenes, name2sid, rid2sid, objs, insts = load_world()
    new, stat, drop = build_routes(name2sid, rid2sid, objs, insts)

    print(u'== 计算 ==')
    print(u'  场景 %d ／ 名字映射 %d ／ 房间号映射 %d ／ 对象 %d ／ (房间,对象) 实例对 %d'
          % (len(scenes), len(name2sid), len(rid2sid), len(objs), len(insts)))
    for k in ('edge_bad_code', 'edge_not_door', 'src_ambiguous', 'src_no_instance',
              'src_unregistered', 'src_ok',
              'next_seen', 'next_not_plus1', 'next_no_instance', 'next_unregistered', 'next_ok'):
        print(u'  %-20s %d' % (k, stat[k]))
    kinds = collections.Counter(r['_original']['kind'] for r in new)
    print(u'  ⇒ 写入 %d 条：%s' % (len(new), dict(kinds)))

    # ---- 覆盖账：1299 个门实例里，能被这 245 条托住多少 ----
    door_objs = set()
    for o in objs:
        rec = II.classify(o)
        if rec and rec.get('kind') == 'door':
            door_objs.add(o)
    n_door_inst = sum(n for (rn, o), n in insts.items() if o in door_objs)
    covered = set()
    for r in new:
        src_name = r['_original'].get('src_room_name')
        obj = r.get('when_src') or NEXT_DOOR_OBJ      # 字母级的那批就是 obj_doorA
        covered.add((src_name, obj))
    n_cov = sum(n for (rn, o), n in insts.items() if (rn, o) in covered)
    print(u'  门实例总数 %d；被本轮路由托住 %d（%.1f%%）'
          % (n_door_inst, n_cov, 100.0 * n_cov / max(1, n_door_inst)))

    print(u'')
    print(u'== 未采用账（丢在哪一步，逐类列前 3）==')
    for k in ('src_ambiguous', 'src_no_instance', 'src_unregistered',
              'next_not_plus1', 'next_no_instance', 'next_unregistered', 'edge_not_door'):
        v = drop.get(k) or []
        print(u'  %-20s %3d  %s' % (k, len(v), v[:3]))

    ev = {
        'schema_version': 1,
        'how': u'第122轮：ut 门 → 目标房间。只取两层证据里的可信层（见 gen_routes122 docstring）。',
        'ut_prio_base': UT_PRIO_BASE,
        'n_routes': len(new),
        'n_door_instances': n_door_inst,
        'n_covered_instances': n_cov,
        'stat': dict(stat),
        'dropped': {k: list(v) for k, v in drop.items()},
        'routes': new,
    }

    if dry:
        print(u'')
        print(u'[dry] 不写盘；事实文件也未落')
        return 0

    rj = _json(ROUTES)
    old = [r for r in (rj.get('routes') or [])
           if not str((r or {}).get('when_scene') or '').startswith('ut.')]
    removed = len(rj.get('routes') or []) - len(old)
    rj['routes'] = old + new

    # meta 如实登记（不覆盖既有说明，只追加一段）
    meta = rj.setdefault('meta', {})
    note = meta.get('note') or u''
    tag = u'★ 第122轮：'
    if tag in note:
        note = note.split(tag)[0].rstrip(u'\n')
    meta['note'] = note + u'\n' + (
        u'★ 第122轮：新增 %d 条 `when_scene` 以 `ut.` 开头的规则 = ut 的门'
        u'（%d 条对象级 `when_src` + %d 条字母 A）。ut 的门对象**不带字母**，'
        u'目标写在 GML 的 `room_goto()` 里 ⇒ 只能按 (场景, 对象名) 定位，'
        u'为此新增 `when_src` 字段（见 `item_interact.route_for_door`）。'
        u'生成器 `code-quality-audit/第122轮-ut门与房间连接/_tools/gen_routes122.py`，'
        u'只取可信层，候选层（`room_goto_next` 之外的猜测）一条不用。'
        % (len(new), stat['src_ok'], stat['next_ok']))

    os.makedirs(EVID, exist_ok=True)
    _write_like_original(ROUTES, rj)
    _write_like_original(FACT, ev)
    print(u'')
    print(u'[ok] 删旧 ut 条目 %d，写入 %d；总计 %d 条' % (removed, len(new), len(rj['routes'])))
    print(u'[ok] 事实文件 %s' % os.path.relpath(FACT, REPO))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))
