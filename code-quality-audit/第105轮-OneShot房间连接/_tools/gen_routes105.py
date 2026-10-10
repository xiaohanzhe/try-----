# -*- coding: utf-8 -*-
"""第105轮 · OneShot 房间连接（原作 code-201 传送门）生成器。

用户口径：「一切根据原作」「把原作的世界搬到桌面上（桌面也是一个场景）」。

为什么需要这一轮
----------------
第100~104轮已经把 OneShot 的 263 间房**画出来**了（`_zone.oneshot.*` 分片 +
背景 + 物件材质），`_index.json` 里 263 个场景全部登记、且每个都带
`original_room_id`（= 原作 map 序号）。但**房间之间走不通**：
`_routes.json` 452 条规则的 `when_scene` 前缀分布是
`{ch1:167, ch2:188, ch3:31, ch4:29, ch5:28, desktop:9}` —— **oneshot 0 条**。
⇒ 站在任何一间 OneShot 房里 `scene_routing.match()` 都只能落 `_fallback`（回桌面）。

原作侧的证据
------------
原作 OneShot 的房间连接**不是**"门 + 下标位移"（那是 Deltarune 的机制），
而是 **code 201 = Transfer Player** 事件指令：事件摆在地图某格上，玩家踩到
（trigger=1）或与它对话（trigger=0/2）就切到目标 map 的 (x, y)。
全 263 图实测 **826** 条 code-201，其中 **page0 且该页无任何触发条件** 的
**749** 条 = 「纯位置门」（不需要剧情开关就能通行）；**77** 条带条件 / 在非 0 页
= 剧情传送（**只登记不生成** —— 接入存档/开关状态之前没有翻页依据）。

口径（与第44轮同源：算得出才写，算不出不伪装）
--------------------------------------------
· 只取 page0 且无条件的 code-201（实测 749 条）；
· 目标必须在 1..263 且**两端都已登记为场景**（实测 749/749 都满足）；
· **自环（src == dst，19 条）只登记不生成** —— "切到自己"不是一条路由；
· 跨房 730 条按 `(src, dst)` **去重后 420 条唯一边**：同一对房间可由多个传送
  事件到达（不同入口 / 不同格子），合成一条路由，全部来源记进
  `_original.events`（**不丢事实**）；
· `when_door` = 该边的代表性事件名归一化 slug（小写 + 非字母数字→`_`），
  **同一场景内保证唯一**（重名按目标房升序加后缀）⇒ 满足
  `verify_routes_order44.B2`「同场景内 when_door 序 == priority 序」不变量；
· `priority` 走**独立段 3000+**，追加在声明序末尾
  （原作 Deltarune 边 110~2478 / 桌面门 200）⇒ B3「原作生成段无回绕」仍成立；
· `_original.kind = 'oneshot_transfer'`，与桌面门的 `'desktop_portal'` 并列，
  让第36轮 C3 能按 `kind` 分派（它原本只认 A+1 / B-1 / C+2 的门位移）。

产出
----
· `_evidence/oneshot_transfers.json` —— **原作事实**（边 + 事件 + 自环 + 剧情
  传送），**不含本生成器的任何决策字段**；`check105` 从它**独立重推**期望值。
· 就地更新 `ralsei_pet/assets/scenes/_routes.json`（保持 CRLF / 2 空格缩进 /
  无尾换行 —— 实测 `json.dumps(..., indent=2)` 与原文逐字节相同）。

用法::

    python gen_routes105.py            # 生成 + 写盘
    python gen_routes105.py --dry      # 只打印统计，不写
    python gen_routes105.py --check    # 只验证「既有产物与重算一致」，不写
"""
import collections
import importlib.util
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))          # .../第105轮-.../_tools
ROUND = os.path.dirname(HERE)                              # .../第105轮-...
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))    # 仓库根
SC = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
EV = os.path.join(ROUND, '_evidence')
ROUTES = os.path.join(SC, '_routes.json')

#: ★ 房间连接图的**第二个消费面**：逐门寻路（`scene_pathfind.load_room_graph`）。
#: 它由第42轮把原作反汇编成 `ch1..ch5`（782 边），但**没有 oneshot 章** ⇒
#: `plan_route_to` 在 OneShot 里 `edges_by_chapter.get('oneshot') → None` ⇒
#: `travel_to` 只能退化成"直达"（`route='direct'`），走不出逐门的步骤。
#: 本轮的 420 条边**同时**喂给它，才能让"走通"真的落地。
#: ⚠️ 该文件是**运行时数据**（`room_graph_path()` 硬编码了这个路径），
#:    本轮只**追加** `chapters.oneshot`，五章必须逐字段不变（脚本内自证）。
ROOM_GRAPH = os.path.join(ROOT, 'code-quality-audit', '第42轮-原作拓扑取证',
                          '_evidence', '_room_graph.json')
FIVE_CH = ('ch1', 'ch2', 'ch3', 'ch4', 'ch5')
OS_FOLDER = 'OneShot'

#: 独立 priority 段 —— 必须 > 原作 Deltarune 段最大值（实测 2478），
#: 且不撞桌面门的 200。留着 2500..2999 的空档便于以后插别的东西。
PRIO_BASE = 3000

#: 只取 page0 且"该页无任何触发条件"的传送（四个条件位全为假）。
_COND_KEYS = ('switch1_valid', 'switch2_valid', 'variable_valid', 'self_switch_valid')

#: `_original.kind` 取值 —— 与桌面门的 'desktop_portal' 并列。
KIND = 'oneshot_transfer'


def _osd():
    """原作数据根目录 —— **唯一入口**是第100轮留下的 `os_bg100.OSD`。

    不在这里复制那个长路径字符串：复制 = 同一件事两处算（本项目头号教训）。
    """
    p = os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景',
                     '_tools', 'os_bg100.py')
    spec = importlib.util.spec_from_file_location('os_bg100', p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.OSD


def load_t(p):
    """容错 JSON 读取（原作导出的 JSON 里有尾逗号）。"""
    s = io.open(p, encoding='utf-8', newline='').read()
    try:
        return json.loads(s)
    except ValueError:
        return json.loads(re.sub(r',(\s*[}\]])', r'\1', s))


def read_src(p):
    return io.open(p, encoding='utf-8', newline='').read()


def slug(name):
    """事件名 → 稳定的 `when_door` 标识（小写 + 非字母数字折成 `_`）。"""
    s = re.sub(r'[^0-9a-z]+', '_', (name or '').strip().lower()).strip('_')
    return s or 'unnamed'


# ===========================================================================
#  1. 登记表：map_id → (scene_id, 房名, 区 id, 区中文名)
# ===========================================================================
def load_registry():
    idx = load_t(os.path.join(SC, '_index.json'))
    ch = (idx.get('chapters') or {}).get('oneshot') or {}
    reg = {}
    for aid, area in (ch.get('areas') or {}).items():
        aname = area.get('name') or aid
        for sid, rec in (area.get('scenes') or {}).items():
            rid = rec.get('original_room_id')
            if isinstance(rid, int):
                reg[rid] = {
                    'scene_id': sid,
                    'room_name': rec.get('name') or rid_str(rid),
                    'area_id': aid,
                    'area_name': aname,
                }
    return reg


def rid_str(rid):
    return 'map%d' % rid


# ===========================================================================
#  2. 原作扫描：826 条 code-201 → 门候选 / 剧情传送
# ===========================================================================
def scan(maps_dir):
    doors = []      # page0 且无条件
    deferred = []   # 有条件 / 非 page0
    total = 0
    for n in range(1, 264):
        p = os.path.join(maps_dir, 'events_map%d.json' % n)
        if not os.path.isfile(p):
            continue
        for e in (load_t(p).get('events') or []):
            pages = e.get('pages') or []
            for pi, pg in enumerate(pages):
                cond = pg.get('condition') or {}
                hascond = any(cond.get(k) for k in _COND_KEYS)
                g = pg.get('graphic') or {}
                for ins in (pg.get('list') or []):
                    if ins.get('code') != 201:
                        continue
                    total += 1
                    pr = ins.get('parameters') or []
                    dst = pr[1] if len(pr) > 1 else None
                    rec = {
                        'src_map': n,
                        'dst_map': (int(dst) if isinstance(dst, int) or
                                    (isinstance(dst, str) and dst.isdigit()) else None),
                        'event': e.get('name') or '',
                        'event_xy': [e.get('x'), e.get('y')],
                        'page': pi,
                        'n_pages': len(pages),
                        'trigger': pg.get('trigger'),
                        'has_condition': bool(hascond),
                        'graphic': (g.get('character_name') or ''),
                        'dst_xy': [pr[2] if len(pr) > 2 else None,
                                   pr[3] if len(pr) > 3 else None],
                        'dst_dir': pr[4] if len(pr) > 4 else None,
                        'fade': pr[5] if len(pr) > 5 else None,
                    }
                    if pi == 0 and not hascond:
                        doors.append(rec)
                    else:
                        deferred.append(rec)
    return doors, deferred, total


def build(maps_dir, reg):
    """→ (edges, self_loops, deferred, counts)。

    `edges` 每项 = 一条 (src, dst) 唯一边 + 它的全部来源事件。
    """
    doors, deferred, total = scan(maps_dir)
    edges = collections.OrderedDict()      # (src, dst) -> [rec, ...]
    self_loops = []
    unreg = []
    for rec in doors:
        s, d = rec['src_map'], rec['dst_map']
        if not (isinstance(d, int) and 1 <= d <= 263):
            unreg.append(rec)
            continue
        if s not in reg or d not in reg:
            unreg.append(rec)
            continue
        if s == d:
            self_loops.append(rec)
            continue
        edges.setdefault((s, d), []).append(rec)

    # 代表性事件：按 (事件名, x, y) 最小 —— 完全确定，不看扫描顺序。
    for (s, d), evs in edges.items():
        evs.sort(key=lambda r: (r['event'], r['event_xy'][0] if r['event_xy'][0] is not None else -1,
                                r['event_xy'][1] if r['event_xy'][1] is not None else -1))
    counts = {
        'code201_total': total,
        'doors_page0_uncond': len(doors),
        'deferred_conditional_or_nonpage0': len(deferred),
        'self_loops': len(self_loops),
        'unregistered_or_bad_dst': len(unreg),
        'unique_edges': len(edges),
        'cross_room_transfers': len(doors) - len(self_loops) - len(unreg),
    }
    return edges, self_loops, deferred, counts


# ===========================================================================
#  3. 由**原作事实**推导路由（when_door / priority / reason）
# ===========================================================================
def derive_routes(edges, reg):
    """→ [route, ...]（按 (when_scene, when_door) 升序，priority 单调递增）。"""
    # 先给每条边定 label（同一场景内唯一）
    per_src = collections.defaultdict(list)
    for (s, d), evs in edges.items():
        per_src[s].append({'src': s, 'dst': d, 'evs': evs,
                           'label': slug(evs[0]['event'])})
    for s, lst in per_src.items():
        used = set()
        for item in sorted(lst, key=lambda r: (r['label'], r['dst'])):
            base = item['label']
            lab, k = base, 1
            while lab in used:
                k += 1
                lab = '%s__%d' % (base, k)
            used.add(lab)
            item['label'] = lab

    flat = [it for lst in per_src.values() for it in lst]
    flat.sort(key=lambda r: (reg[r['src']]['scene_id'], r['label'], r['dst']))

    out = []
    for i, it in enumerate(flat):
        s, d = it['src'], it['dst']
        rs, rd = reg[s], reg[d]
        ev0 = it['evs'][0]
        disp = ev0['event'] or '（未命名事件）'
        out.append({
            'to': rd['scene_id'],
            'priority': PRIO_BASE + i,
            'reason': '原作连接：从 OneShot·%s·%s 的「%s」传送，落到 OneShot·%s·%s。'
                      % (rs['area_name'], rs['room_name'], disp,
                         rd['area_name'], rd['room_name']),
            'when_scene': rs['scene_id'],
            'when_door': it['label'],
            '_original': {
                'chapter': 'oneshot',
                'kind': KIND,
                'src_map': s,
                'dst_map': d,
                'src_room_name': rs['room_name'],
                'dst_room_name': rd['room_name'],
                'event': ev0['event'],
                'event_xy': ev0['event_xy'],
                'graphic': ev0['graphic'],
                # ⚠️ 逐事件明细**不放这里**：`_routes.json` 是运行时资产
                #   （`load_routes` 每次冷启都要读整份），把 420 条边的全部
                #   来源事件塞进来会让它从 245KB 涨到 614KB。明细在
                #   `_evidence/oneshot_transfers.json`（每条边一个 `events` 数组）。
                'n_events': len(it['evs']),
            },
        })
    return out


# ===========================================================================
#  4. 写盘
# ===========================================================================
def write_evidence(edges, self_loops, deferred, counts, reg):
    payload = {
        'round': 105,
        'schema': 1,
        'kind': KIND,
        'note': ('第105轮 · OneShot 房间连接的原作事实蒸馏。'
                 '本文件**只有原作数据**（code-201 事件 + 两端 map / 房名），'
                 '不含生成器的任何决策（when_door slug / priority / reason）——'
                 'check105 必须从它**独立重推**期望值，否则比对是自证。'),
        'counts': counts,
        'edges': [
            {'src_map': s, 'dst_map': d,
             'src_scene': reg[s]['scene_id'], 'dst_scene': reg[d]['scene_id'],
             'src_room_name': reg[s]['room_name'], 'dst_room_name': reg[d]['room_name'],
             'events': [{'event': e['event'], 'xy': e['event_xy'],
                         'graphic': e['graphic'], 'trigger': e['trigger']}
                        for e in evs]}
            for (s, d), evs in sorted(edges.items())
        ],
        'self_loops': self_loops,
        'deferred': deferred,
    }
    p = os.path.join(EV, 'oneshot_transfers.json')
    txt = json.dumps(payload, ensure_ascii=False, indent=2) + '\n'
    with io.open(p, 'w', encoding='utf-8', newline='') as fh:
        fh.write(txt)
    return p


def patch_routes(new_routes, dry=False):
    raw = read_src(ROUTES)
    d = json.loads(raw)
    assert isinstance(d.get('routes'), list)
    kept = [r for r in d['routes']
            if not str((r or {}).get('when_scene', '')).startswith('oneshot')]
    removed = len(d['routes']) - len(kept)
    d['routes'] = kept + list(new_routes)

    meta = d.setdefault('meta', {})
    # rule_fields 里的 `_original` 说明补一句（surgical，不动其它字段）
    rf = meta.get('rule_fields')
    if isinstance(rf, dict) and 'oneshot_transfer' not in str(rf.get('_original')):
        rf['_original'] = rf.get('_original', '') + \
            '；第105轮起也用于 OneShot 传送门（kind=\'oneshot_transfer\'）'
    # 新键：把 OneShot 这一段的机制写进 meta（后人不必翻脚本就知道边从哪来）
    meta['oneshot_note'] = (
        '★ 第105轮：OneShot 房间连接 = 原作 **code 201（Transfer Player）**事件指令，'
        '不是 Deltarune 的门位移。口径：只取 page0 且该页无条件的传送 → 749 条候选 → '
        '去自环 19 → 跨房 730 条按 (src_map, dst_map) 去重成 420 条唯一边；'
        '另有 77 条带条件/非 0 页的**剧情传送只登记不生成**（没有存档/开关状态可依）。'
        '本段的 `_original.kind` 一律 = \'oneshot_transfer\'，priority 走独立段 '
        '3000+ 并追加在声明序末尾（保 `verify_routes_order44.B3` 的"原作生成段无回绕"）。'
        '事实蒸馏在 code-quality-audit/第105轮-OneShot房间连接/_evidence/oneshot_transfers.json。')

    text = json.dumps(d, ensure_ascii=False, indent=2).replace('\n', '\r\n')
    if not dry:
        with io.open(ROUTES, 'w', encoding='utf-8', newline='') as fh:
            fh.write(text)
    return removed, len(d['routes']), len(text)


def _ch_fp(rec):
    import hashlib
    return hashlib.sha256(
        json.dumps(rec, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def patch_room_graph(edges, reg, dry=False):
    """★ 把同 420 条边**同时**写进逐门寻路图（`chapters.oneshot`）。

    :return: `(n_edges, bytes, five_ch_unchanged: bool)`

    只**追加**一章；五章（ch1..ch5）逐字段指纹必须不变 —— 那 782 条边是第42轮
    反汇编的取证事实，动它就是改动历史证据。脚本内自证，不靠"我记得没动"。
    """
    raw = read_src(ROOM_GRAPH)
    d = json.loads(raw)
    chs = d.get('chapters')
    if not isinstance(chs, dict):
        raise SystemExit('房间图缺 chapters')
    before = {k: _ch_fp(v) for k, v in chs.items() if k in FIVE_CH}

    rows = []
    for (s, dd), evs in sorted(edges.items()):
        rep = min(evs, key=lambda r: (
            r['event'],
            r['event_xy'][0] if isinstance(r['event_xy'][0], int) else -1,
            r['event_xy'][1] if isinstance(r['event_xy'][1], int) else -1))
        rows.append({
            'src': s, 'src_name': reg[s]['room_name'],
            'dst': dd, 'dst_name': reg[dd]['room_name'],
            'door': slug(rep['event']),
            'kind': KIND,
        })
    chs['oneshot'] = {'folder': OS_FOLDER, 'n_edges': len(rows), 'edges': rows}
    meta = d.setdefault('meta', {})
    meta['oneshot_note'] = (
        '★ 第105轮：本图新增 `oneshot` 章（%d 条边），来源 = 原作 OneShot 的 '
        'code-201（Transfer Player）事件指令（page0 且无条件；自环 19 条与 '
        '带条件的剧情传送 77 条**只登记不生成**）。'
        '`kind=oneshot_transfer` 与 Deltarune 的 `delta`/`table` 并列；'
        '`door` 是该边的代表性**事件名**归一化 slug（OneShot 没有门对象）。'
        '依据：code-quality-audit/第105轮-OneShot房间连接/_evidence/oneshot_transfers.json。'
        '⚠️ ch1~ch5 一个字段都没动（生成器内含指纹自证）。' % len(rows))
    after = {k: _ch_fp(v) for k, v in chs.items() if k in FIVE_CH}
    same = (before == after)
    if not same:
        raise SystemExit('五章被改动了！生成的边只许追加到 chapters.oneshot')

    text = json.dumps(d, ensure_ascii=False, indent=1).replace('\n', '\r\n')
    if not dry:
        with io.open(ROOM_GRAPH, 'w', encoding='utf-8', newline='') as fh:
            fh.write(text)
    return len(rows), len(text), same


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    dry = '--dry' in sys.argv
    check_only = '--check' in sys.argv
    osd = _osd()
    maps_dir = os.path.join(osd, 'gamedata', 'maps')
    reg = load_registry()
    print('登记表：%d 个 OneShot 场景（带 original_room_id）' % len(reg))
    edges, self_loops, deferred, counts = build(maps_dir, reg)
    print('原作扫描：%s' % json.dumps(counts, ensure_ascii=False))
    routes = derive_routes(edges, reg)
    print('推导出 %d 条路由；when_door 样本 %s'
          % (len(routes), [r['when_door'] for r in routes[:6]]))
    assert routes, '没有推出任何路由 —— 扫描口径坏了'
    assert all(r['priority'] >= 110 for r in routes)
    # 不变量自检（同一场景内 label 唯一 + priority 随 label 单调）
    by = collections.defaultdict(list)
    for r in routes:
        by[r['when_scene']].append(r)
    for sid, lst in by.items():
        labs = [r['when_door'] for r in sorted(lst, key=lambda x: x['priority'])]
        assert len(labs) == len(set(labs)), 'when_door 在 %s 内重复' % sid
        assert labs == sorted(labs), 'when_door 序 != priority 序 @ %s' % sid
    print('自检通过：%d 个源场景，when_door 场景内唯一且序 == priority 序' % len(by))

    if check_only:
        raw = read_src(ROUTES)
        cur = json.loads(raw)
        got = [r for r in cur['routes']
               if str(r.get('when_scene', '')).startswith('oneshot')]
        same = json.dumps(got, ensure_ascii=False, sort_keys=True) == \
            json.dumps(routes, ensure_ascii=False, sort_keys=True)
        print('--check：产品里 oneshot 路由 %d 条，与重算一致 = %s' % (len(got), same))
        return 0 if same else 1

    ep = os.path.join(EV, 'oneshot_transfers.json')
    if not dry:
        ep = write_evidence(edges, self_loops, deferred, counts, reg)
        print('证据写入 %s (%d bytes)' % (ep, os.path.getsize(ep)))
    else:
        print('（dry-run：证据未重写；现有 %s %s）'
              % (os.path.basename(ep),
                 ('%d bytes' % os.path.getsize(ep)) if os.path.isfile(ep) else '不存在'))
    removed, total, nbytes = patch_routes(routes, dry=dry)
    print('路由表：移除既有 oneshot %d 条，追加 %d 条，总 %d 条，%d bytes%s'
          % (removed, len(routes), total, nbytes, '（dry-run 未写盘）' if dry else ''))
    ne, gbytes, same = patch_room_graph(edges, reg, dry=dry)
    print('寻路图：chapters.oneshot %d 条边，%d bytes，五章未变=%s%s'
          % (ne, gbytes, same, '（dry-run 未写盘）' if dry else ''))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
