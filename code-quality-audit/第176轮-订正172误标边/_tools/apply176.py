# -*- coding: utf-8 -*-
u"""第176轮 · 订正第172轮的 42 条误标边（**删除**，不是改标签）。

三条独立证据（都能复算，见 check176）
------------------------------------
① **标错**：这 42 条的 `when_src` / `_original.via` 都写 `obj_doorAny`，
   而它们的 `precreate`（`gml_RoomCC_<房>_<n>_PreCreate`）在第174轮的 51 条
   变体取证里 —— 真身是 `obj_doorAnyHorz`（36 条）/ `obj_doorAnyVert`（6 条）。
② **是死边**：`route_for_door` 的对象级匹配是 `r.get('when_src') == src`
   **精确字符串相等**；产品里这 42 扇门的 `src` 已经是变体名（第174轮物化的），
   所以 `when_src='obj_doorAny'` **一条都匹配不上** ⇒ 从未被消费。
③ **纯冗余**：这 42 条与第174轮落的 51 条在 `(场景, 目标, door_x, door_y)`
   上**完全重合**（42/42 覆盖，未覆盖 0）。

⇒ 处置：**删掉**。留档可恢复。

为什么不是"改标签"
------------------
改标签会让它们变成"活的重复边"：与 174 的 51 条在 `(场景,目标,门坐标,src)`
上完全重复 ⇒ 每组两条候选 ⇒ `_pick_by_pos` 挑不出唯一 ⇒ 退回 priority 最小
⇒ 生效的是 172 这批（priority 7831~8057 < 8100~8150），**结果一样但"哪条在干活"变了**，
而且直接违反第170轮立的「重复边不加」。

★ 删前/删后各跑一次**全表路由快照**（所有门物件的 `route_for_door` 结果），
  逐值必须相同，**不同就拒写** —— 这是本轮的硬闸，也是"纯冗余"这个判断的验证。

用法
----
    python apply176.py            # 演练（不写盘，但会打印快照差异）
    python apply176.py --apply    # 真删
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
EV = os.path.join(ROUND, '_evidence')
SCENES = os.path.join(REPO, 'ralsei_pet', 'assets', 'scenes')
ROUTES = os.path.join(SCENES, '_routes.json')
EV174 = os.path.join(REPO, 'code-quality-audit', u'第174轮-Any门变体', '_evidence')

PKG = os.path.join(REPO, 'ralsei_pet')
for _p in (PKG, os.path.join(PKG, 'modules')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from modules.item_interact import door_letter_of, route_for_door   # noqa: E402

VAR_SRC = ('obj_doorAnyHorz', 'obj_doorAnyVert')
EXPECT_DEL = 42
APPLY = '--apply' in sys.argv


def jl(p):
    return json.loads(io.open(p, encoding='utf-8', newline='').read())


def load_objs():
    """scene_id -> objects（独立文件 + 区域分片两条来源都读）。"""
    out = {}
    for f in os.listdir(SCENES):
        if f.endswith('.json') and not f.startswith('_'):
            d = jl(os.path.join(SCENES, f))
            out[d.get('scene_id')] = d.get('objects') or []
    for f in os.listdir(SCENES):
        if not f.startswith('_zone.'):
            continue
        d = jl(os.path.join(SCENES, f))
        for sid, sc in ((d or {}).get('scenes') or {}).items():
            out[sid] = (sc or {}).get('objects') or []
    return out


def snapshot(RL, OBJS):
    """全表路由快照：每个**门类**物件的 `route_for_door` 结果。"""
    out = {}
    for sid in sorted(OBJS):
        for i, o in enumerate(OBJS[sid] or []):
            if not isinstance(o, dict):
                continue
            src = o.get('src')
            if not isinstance(src, str) or not src.lower().startswith('obj_door'):
                continue
            pos = o.get('pos')
            letter = door_letter_of(src)
            r = route_for_door(RL, sid, letter, src, pos)
            out['%s#%d|%s|%s' % (sid, i, src, pos)] = r
    return out


def main():
    data = jl(ROUTES)
    RL = data['routes'] if isinstance(data, dict) else data
    OBJS = load_objs()
    ev = {r['code']: r for r in jl(os.path.join(EV174, 'analyze174.json'))['rows']}

    # 174 那 51 条的 (场景,目标,门坐标) 集合
    cov = set()
    for r in RL:
        o = r.get('_original') or {}
        if o.get('via') in VAR_SRC and o.get('precreate') in ev:
            cov.add((r.get('when_scene'), r.get('to'), o.get('door_x'), o.get('door_y')))

    todo, skip = [], []
    for idx, r in enumerate(RL):
        o = r.get('_original') or {}
        if o.get('via') != 'obj_doorAny' or r.get('when_src') != 'obj_doorAny':
            continue
        pc = o.get('precreate')
        if pc not in ev:
            continue
        want = ev[pc]['obj']
        k = (r.get('when_scene'), r.get('to'), o.get('door_x'), o.get('door_y'))
        # 多重校验：真身是变体 + 已被 174 覆盖 + 产品里那处物件 src 就是变体
        oks = []
        oks.append(('真身', want in VAR_SRC))
        oks.append(('被174覆盖', k in cov))
        here = [x.get('src') for x in (OBJS.get(r.get('when_scene')) or [])
                if len(x.get('pos') or []) >= 2
                and (x['pos'][0], x['pos'][1]) == (o.get('door_x'), o.get('door_y'))]
        oks.append(('产品里src=变体', want in here))
        if all(v for _n, v in oks):
            todo.append((idx, r, want))
        else:
            skip.append((idx, [n for n, v in oks if not v]))

    print(u'误标边（命中断言的全集） = %d' % (len(todo) + len(skip)))
    print(u'可删 = %d   跳过 = %d %r' % (len(todo), len(skip), skip[:5]))
    if not todo and not skip:
        print(u'\n[幂等] 已经是清理后的状态（0 条误标边），未改动任何文件。')
        return 0
    if len(todo) != EXPECT_DEL:
        print(u'!! 可删条数 %d != 期望 %d —— 拒写' % (len(todo), EXPECT_DEL))
        return 1

    print(u'\n[1/3] 跑改前全表路由快照 ...')
    snap0 = snapshot(RL, OBJS)
    print(u'      门类物件 %d 个，其中解出目标 %d 个'
          % (len(snap0), sum(1 for v in snap0.values() if v)))

    del_idx = set(i for i, _r, _w in todo)
    new_rl = [r for i, r in enumerate(RL) if i not in del_idx]
    print(u'\n[2/3] 删后条数 %d -> %d' % (len(RL), len(new_rl)))

    print(u'\n[3/3] 跑改后快照并逐值比对 ...')
    snap1 = snapshot(new_rl, OBJS)
    diff = [(k, snap0.get(k), snap1.get(k)) for k in set(snap0) | set(snap1)
            if snap0.get(k) != snap1.get(k)]
    print(u'      差异 = %d' % len(diff))
    if diff:
        print(u'!! 删除改变了路由行为 —— 说明"纯冗余"判断错了，拒写。前 6 条：')
        for d in diff[:6]:
            print(u'   %r  %r -> %r' % d)
        return 2
    print(u'      ★ 全表路由逐值不变（%d 个门物件）' % len(snap0))

    if not APPLY:
        print(u'\n[dry] 通过全部校验，未写盘。加 --apply 才真删。')
        return 0

    os.makedirs(EV, exist_ok=True)
    with io.open(os.path.join(EV, 'removed176.json'), 'w',
                 encoding='utf-8', newline='\n') as f:
        json.dump({'note': u'第176轮删掉的 42 条误标边（原样留档，可整段加回 _routes.json）',
                   'count': len(todo),
                   'items': [r for _i, r, _w in todo]},
                  f, ensure_ascii=False, indent=1)
    with io.open(os.path.join(EV, 'snapshot176.json'), 'w',
                 encoding='utf-8', newline='\n') as f:
        json.dump({'note': u'改前全表路由快照（删后必须逐值相同）',
                   'n': len(snap0), 'snap': snap0},
                  f, ensure_ascii=False, indent=1)
    print(u'\n[留档] removed176.json / snapshot176.json -> %s' % EV)

    txt = io.open(ROUTES, encoding='utf-8', newline='').read()
    rt = json.dumps(data, ensure_ascii=False, indent=2).replace('\n', '\r\n')
    if rt != txt:
        print(u'!! 无损往返自检失败：不写盘（先查 indent/EOL 口径）')
        return 3

    data['routes'] = new_rl
    out = json.dumps(data, ensure_ascii=False, indent=2).replace('\n', '\r\n')
    tmp = ROUTES + '.new'
    with io.open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    back = io.open(tmp, 'rb').read()
    if back.startswith(b'\xef\xbb\xbf'):
        print(u'!! 带 BOM，拒写')
        os.remove(tmp)
        return 4
    d2 = json.loads(back.decode('utf-8'))
    if len(d2['routes']) != len(new_rl):
        print(u'!! 复读条数不符')
        os.remove(tmp)
        return 5
    b0 = os.path.getsize(ROUTES)
    os.replace(tmp, ROUTES)
    print(u'\n[落盘] %d -> %d 条；%d -> %d B'
          % (len(RL), len(new_rl), b0, os.path.getsize(ROUTES)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
