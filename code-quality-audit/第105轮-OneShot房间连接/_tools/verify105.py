# -*- coding: utf-8 -*-
"""verify105.py —— 第105轮**真源复算**：回原作 gamedata 从头算一遍，与产品对账。

与 `check105` 的分工（**必须分开**，否则是自证）
----------------------------------------------
  · `check105`（进 G2）：只读**仓库内**文件（产品 + 蒸馏证据），
    **零外部盘依赖**（E 盘掉线也照跑）。它守的是"产品 == 蒸馏事实"。
  · `verify105`（本文件，**不进 G2**）：回**原作 gamedata** 现扫 263 张图，
    自己重建整条链，再同时对上**产品**与**证据**两类产物。
    ⇒ 它是"蒸馏事实本身有没有过期/失真"的独立第三方。

判据分四组：
  A 原作侧计数（826 / 749 / 77 / 19 / 420）—— 全部**现算**，不读证据；
  B 三方对账（原作现算 == 蒸馏证据 == 产品）；
  C 逐字段重推（when_door 词根 / priority 段 / 目标登记）；
  D 结构与拓扑（无自环路由 / 无孤儿 / 图的连通分量数一致）+ 抽样锚点 + 负控制。

跑法::

    python verify105.py            # 结果同时打到 stdout 与 _evidence/verify105.txt
    python verify105.py --quiet    # 只写文件

⚠️ 本脚本**依赖外部盘**（原作目录），故**不许**注册进 `run_all.py` 的 SUITES
   —— 那会让 G2 基线随"E 盘在不在线"漂移（本项目踩过：`routes_order44` C 段
   曾静默退化成 SKIP）。原作目录不在时**明确报 SKIP 并非 0 退出**，不伪装成绿。
"""
import collections
import importlib.util
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(ROUND, '..', '..'))
SC = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
ROUTES = os.path.join(SC, '_routes.json')
INDEX = os.path.join(SC, '_index.json')
EVID = os.path.join(ROUND, '_evidence', 'oneshot_transfers.json')
OUT = os.path.join(ROUND, '_evidence', 'verify105.txt')

PRIO_BASE = 3000
_COND_KEYS = ('switch1_valid', 'switch2_valid', 'variable_valid', 'self_switch_valid')

_LINES = []
_N = [0]
_FAIL = []


def out(s=''):
    _LINES.append(s)
    if '--quiet' not in sys.argv:
        print(s)


def ok(cond, msg):
    _N[0] += 1
    if cond:
        out('[PASS] %s' % msg)
    else:
        _FAIL.append(msg)
        out('[FAIL] %s' % msg)


def jload(p):
    with io.open(p, encoding='utf-8') as fh:
        return json.load(fh)


def load_t(p):
    s = io.open(p, encoding='utf-8', newline='').read()
    try:
        return json.loads(s)
    except ValueError:
        return json.loads(re.sub(r',(\s*[}\]])', r'\1', s))


def slug(name):
    """★ 与生成器分开写的第二份实现（本题的第三条独立路径）。"""
    s = re.sub(r'[^0-9a-z]+', '_', str(name or '').strip().lower()).strip('_')
    return s or 'unnamed'


def osd():
    p = os.path.join(ROOT, 'code-quality-audit', '第100轮-跨作品素材与背景',
                     '_tools', 'os_bg100.py')
    spec = importlib.util.spec_from_file_location('os_bg100', p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.OSD


# ===========================================================================
#  原作侧：从头扫一遍（**不读证据**）
# ===========================================================================
def scan_original(maps_dir):
    doors, deferred, total, defer_detail = [], [], 0, []
    for n in range(1, 264):
        p = os.path.join(maps_dir, 'events_map%d.json' % n)
        if not os.path.isfile(p):
            continue
        for e in (load_t(p).get('events') or []):
            pages = e.get('pages') or []
            for pi, pg in enumerate(pages):
                cond = pg.get('condition') or {}
                hascond = any(cond.get(k) for k in _COND_KEYS)
                for ins in (pg.get('list') or []):
                    if ins.get('code') != 201:
                        continue
                    total += 1
                    pr = ins.get('parameters') or []
                    d = pr[1]
                    rec = {'src': n,
                           'dst': int(d) if isinstance(d, int) or
                           (isinstance(d, str) and d.isdigit()) else None,
                           'event': e.get('name') or '',
                           'xy': [e.get('x'), e.get('y')],
                           'page': pi, 'has_condition': bool(hascond)}
                    if pi == 0 and not hascond:
                        doors.append(rec)
                    else:
                        deferred.append(rec)
                        defer_detail.append(rec)
    return doors, deferred, total


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    global OUT
    try:
        _osd = osd()
    except Exception as e:
        out('[SKIP] 原作数据入口不可用（%r）—— 本脚本依赖外部盘，不伪装成绿' % (e,))
        out('')
        out('合计 PASS=0 FAIL=0 SKIP=1')
        with io.open(OUT, 'w', encoding='utf-8', newline='') as fh:
            fh.write('\n'.join(_LINES) + '\n')
        return 3

    maps_dir = os.path.join(_osd, 'gamedata', 'maps')
    out('原作目录 = %s' % maps_dir)
    ok(os.path.isdir(maps_dir), 'A0 原作 maps 目录可达')

    doors, deferred, total = scan_original(maps_dir)
    ok(total == 826, 'A1 原作 code-201（Transfer Player）总数 == 826（实得 %d）' % total)
    ok(len(doors) == 749,
       'A2 page0 且该页无条件 的"纯位置门" == 749（实得 %d）' % len(doors))
    ok(len(deferred) == 77,
       'A3 带条件 / 非 page0 的"剧情传送" == 77（实得 %d）' % len(deferred))
    ok(total == len(doors) + len(deferred),
       'A4 计数自洽：%d == %d + %d' % (total, len(doors), len(deferred)))

    # 登记表
    idx = jload(INDEX)
    reg = {}
    for aid, area in (((idx.get('chapters') or {}).get('oneshot') or {})
                      .get('areas') or {}).items():
        for sid, rec in (area.get('scenes') or {}).items():
            if isinstance(rec.get('original_room_id'), int):
                reg[rec['original_room_id']] = (sid, rec.get('name'), area.get('name'))
    ok(len(reg) == 263, 'A5 OneShot 场景登记 263 间（带 original_room_id，实得 %d）'
       % len(reg))

    bad_dst = [d for d in doors if not (isinstance(d['dst'], int) and 1 <= d['dst'] <= 263)]
    unreg = [d for d in doors if d['dst'] not in reg or d['src'] not in reg]
    self_l = [d for d in doors if d['dst'] == d['src']]
    ok(not bad_dst and not unreg,
       'A6 门候选中无坏目标 / 无未登记房间（坏目标 %d，未登记 %d）'
       % (len(bad_dst), len(unreg)))
    ok(len(self_l) == 19, 'A7 自环（目标 == 自己）== 19（实得 %d）' % len(self_l))

    edges = collections.defaultdict(list)
    for d in doors:
        if d['dst'] != d['src'] and d['dst'] in reg and d['src'] in reg:
            edges[(d['src'], d['dst'])].append(d)
    ok(len(edges) == 420,
       'A8 ★跨房传送按 (src_map, dst_map) 去重 == 420 条唯一边（实得 %d）' % len(edges))
    ok(sum(len(v) for v in edges.values()) + len(self_l) == len(doors),
       'A9 计数守恒：去重前跨房 %d + 自环 %d == 门候选 %d'
       % (sum(len(v) for v in edges.values()), len(self_l), len(doors)))

    # ---------------------------------------------------------------- B 三方对账
    raw = json.loads(io.open(ROUTES, encoding='utf-8', newline='').read())
    osr = [r for r in raw['routes']
           if str((r or {}).get('when_scene') or '').startswith('oneshot')]
    prod_set = set((r.get('when_scene'), r.get('to')) for r in osr)
    orig_set = set((reg[s][0], reg[d][0]) for (s, d) in edges)
    ev = jload(EVID)
    ev_set = set((e['src_scene'], e['dst_scene']) for e in (ev.get('edges') or []))

    ok(orig_set == ev_set,
       'B1 ★蒸馏证据 == 现扫原作（原作 %d / 证据 %d / 对称差 %d）'
       % (len(orig_set), len(ev_set), len(orig_set ^ ev_set)))
    ok(prod_set == orig_set,
       'B2 ★★产品 == 现扫原作（产品 %d / 原作 %d / 对称差 %d）'
       % (len(prod_set), len(orig_set), len(prod_set ^ orig_set)))
    ok(len(osr) == len(orig_set),
       'B3 产品 oneshot 规则条数 %d == 唯一边数 %d' % (len(osr), len(orig_set)))

    # ---------------------------------------------------------------- C 逐字段重推
    rep = {}
    for (s, d), evs in edges.items():
        def key(e):
            x, y = e['xy'][0], e['xy'][1]
            return (e['event'], x if isinstance(x, int) else -1,
                    y if isinstance(y, int) else -1)
        rep[(s, d)] = slug(min(evs, key=key)['event'])

    root_bad = []
    for r in osr:
        o = r.get('_original') or {}
        k = (o.get('src_map'), o.get('dst_map'))
        want = rep.get(k)
        got = r.get('when_door')
        if want is None:
            root_bad.append('%s(不属于现扫边集)' % r.get('to'))
        elif got != want and not (isinstance(got, str) and got.startswith(want + '__')):
            root_bad.append('%r≠%r' % (got, want))
    ok(not root_bad,
       'C1 ★每条 oneshot 规则的 when_door 词根 == 由**原作事件**重推的 slug'
       '（不符 %d: %s）' % (len(root_bad), root_bad[:3]))

    prios = sorted(r['priority'] for r in osr)
    ok(prios == list(range(PRIO_BASE, PRIO_BASE + len(osr))),
       'C2 oneshot priority 恰为连续段 [%d, %d]（实得 [%r, %r]）'
       % (PRIO_BASE, PRIO_BASE + len(osr) - 1, prios[0], prios[-1]))

    ok(all(isinstance(r.get('reason'), str) and r['reason'].startswith('原作连接：从 OneShot·')
           for r in osr),
       'C3 每条规则的 reason 是"原作连接：从 OneShot·…"自然语言（喂给 AI 的理由）')
    ok(all((r.get('_original') or {}).get('chapter') == 'oneshot'
           and (r.get('_original') or {}).get('kind') == 'oneshot_transfer'
           for r in osr),
       'C4 每条规则的 _original 都标了 chapter=oneshot / kind=oneshot_transfer')

    # ---------------------------------------------------------------- D 结构与拓扑
    orphan = sorted(t for (_s, t) in prod_set if t not in set(reg[k][0] for k in reg))
    ok(not orphan, 'D1 无孤儿目标（%s）' % (orphan[:3] or '无'))
    ok(not any(r['when_scene'] == r['to'] for r in osr),
       'D2 产品里没有自环路由（19 条自环只登记）')

    def comps(pairs):
        adj = collections.defaultdict(set)
        nodes = set()
        for a, b in pairs:
            adj[a].add(b)
            adj[b].add(a)
            nodes.add(a)
            nodes.add(b)
        seen, n = set(), 0
        for x in nodes:
            if x in seen:
                continue
            n += 1
            stack = [x]
            seen.add(x)
            while stack:
                cur = stack.pop()
                for y in adj[cur]:
                    if y not in seen:
                        seen.add(y)
                        stack.append(y)
        return n, len(nodes)

    c_orig, n_orig = comps(orig_set)
    c_prod, n_prod = comps(prod_set)
    ok((c_orig, n_orig) == (c_prod, n_prod),
       'D3 ★拓扑保真：产品边图的连通分量数 / 节点数 == 原作现算（%d/%d vs %d/%d）'
       % (c_prod, n_prod, c_orig, n_orig))

    # 抽样锚点：map2「Start」的 "west door" → map3「Bathroom」
    anchor = (reg[2][0], reg[3][0])
    ok(anchor in prod_set,
       'D4 锚点：原作 map2「Start」的 west door → map3「Bathroom」在产品里（%r）'
       % (anchor,))
    r_anchor = [r for r in osr if (r['when_scene'], r['to']) == anchor]
    ok(r_anchor and r_anchor[0].get('when_door') == 'west_door',
       'D5 锚点：这条边的 when_door == "west_door"（实得 %r）'
       % (r_anchor[0].get('when_door') if r_anchor else None))

    # 剧情传送不该混进来：只由剧情传送支撑的对
    door_pairs = set((d['src'], d['dst']) for d in doors if d['dst'] != d['src'])
    self_pairs = set((d['src'], d['dst']) for d in self_l)
    def_only = set((d['src'], d['dst']) for d in deferred) - door_pairs - self_pairs
    leak = []
    for (s, d) in sorted(def_only):
        if (reg[s][0], reg[d][0]) in prod_set:
            leak.append((s, d))
    ok(not leak,
       'D6 只由剧情传送支撑的 %d 对房间没有混进产品（泄漏 %d: %s）'
       % (len(def_only), len(leak), leak[:3]))

    # 负控制：伪造的来源场景必须**不在**边集合里（证明 D4 的成员判定有区分度）。
    # ⚠️ 第一版这里写成 `... or True` —— 那是**恒真判据**，比不写还危险
    #    （看着像在守，其实什么都没守）。现在改成"必须为假"的真断言。
    ok(('oneshot.__no_such_scene__', reg[3][0]) not in prod_set
       and (reg[2][0], 'oneshot.__no_such_scene__') not in prod_set,
       'D7 负控制：伪造的场景名不在边集合里（成员判定有区分度）')
    # —— 真正的负控制：错的 slug 必须与重推值不等
    ok(slug('west door') != slug('east door'),
       'D8 负控制：slug 对不同事件名给出不同值（%r vs %r）'
       % (slug('west door'), slug('east door')))

    out('')
    out('合计 PASS=%d FAIL=%d' % (_N[0] - len(_FAIL), len(_FAIL)))
    with io.open(OUT, 'w', encoding='utf-8', newline='') as fh:
        fh.write('\n'.join(_LINES) + '\n')
    return 1 if _FAIL else 0


if __name__ == '__main__':
    raise SystemExit(main())
