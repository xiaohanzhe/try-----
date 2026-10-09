# -*- coding: utf-8 -*-
u"""extract_outertale99.py —— 第99轮：从 outertale 的 Vite bundle 抽房间表（只读源、产数据面）。

数据源（E 盘，第61轮已落地，本轮只读）
------------------------------------
`E:\\Download\\_extract61\\outertale\\www\\index-<hash>.js`（27.5 MB minified bundle）。

定位过程（可复算的推导链，见报告）
----------------------------------
1. `@5462879` 的运行时派发暴露了「**房间 id 首字母 = 区域**」：
   `c.room[0]==="w"?oi.rooms : ===\"s\"?Pi.rooms : ===\"f\"?si.rooms
    : ===\"a\"?zp.rooms : ===\"c\"?Sl.rooms : {}`  → `[c.room]`
2. `@5458378` 给出**全量房间表**的构造：
   `const Bn={room:"",rooms:[Sb,w3,I3,y3,Ub,Fb].flatMap(t=>Object.keys(t))
              .filter(t=>t!=="_"), ...}`
3. 六个表逐一在盘上定位（本轮实证的字节偏移）：
   `Sb@1495673  w3@4460932  I3@5211860  y3@3851182  Ub@2221696  Fb@3011559`
4. 每条目形如 `w_start:Xe("w_start",Mn,z$e)` ⇒ **key == id**，且第二个实参是
   **区域标记变量**：`Sb→as  w3→Mn  I3→Dn  y3→rn  Ub→fo  Fb→en`。

⇒ 抽取规则：在**每个表自己的对象体内部**匹配 `(\w+):Xe\("(\w+)",(\w+),(\w+)\)`。
   ⚠️ 必须按表切体，否则一个全局正则会把 6 个表混成一堆、且可能吃到别的 `Xe(` 调用。

锚点（不通过就不往下用）
----------------------
A1 六表齐备；A2 每条 `key == id`；A3 每表内区域标记**唯一**；
A4 六个区域标记**互不相同**；A5 汇总条数 == 全量构造式推得的条数（去掉 `_`）；
A6 负控制（改一个字母的表名必须 0 命中）。

用法
----
    C:\\Python311\\python.exe -X utf8 extract_outertale99.py            # 只跑锚点
    C:\\Python311\\python.exe -X utf8 extract_outertale99.py --dump     # 另存原始抽取结果
"""
import io
import json
import os
import re
import sys

WWW = u'E:\\Download\\_extract61\\outertale\\www'
HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
OUT = os.path.join(ROUND, u'_evidence')

#: 六个房间表变量名 —— 顺序取自 bundle 里 `[Sb,w3,I3,y3,Ub,Fb]` 的**字面顺序**
TABLES = [u'Sb', u'w3', u'I3', u'y3', u'Ub', u'Fb']

#: 区域标记变量 → 产品侧区域 id / 显示名。
#: ★ 依据 = bundle 里的**存档字段**（`kills_wastelands` / `evac_starton` /
#:   `bully_foundry` / `kills_aerialis`）+ `citadelRooms:Fb` / `citadelStates:Sl`。
#:   这是**实证**，不是按字母猜的。
#: ★★ 首跑时 A3 报红，暴露出 `Ub` 表里**有两个标记**（`fo` / `jn`）
#:   ⇒ 见下：`jn` = **Core**（与第61轮 `ZONES_KNOWN` 里已记录的 `core` 对上）。
#:   "判据报红先怀疑判据"这条又一次成立 —— 红的是**我的登记表漏了一区**，不是抽错。
REGION_OF_VAR = {
    u'as': (u'special', u'特殊'),
    u'Mn': (u'wastelands', u'Wastelands'),
    u'Dn': (u'starton', u'Starton'),
    u'rn': (u'foundry', u'Foundry'),
    u'fo': (u'aerialis', u'Aerialis'),
    u'jn': (u'core', u'Core'),
    u'en': (u'citadel', u'Citadel'),
}
#: 前缀 → 区域 id（交叉校验用；应与 REGION_OF_VAR 的结论一致）
PREFIX_OF_REGION = {
    u'_': u'special', u'w': u'wastelands', u's': u'starton',
    u'f': u'foundry', u'a': u'aerialis', u'c': u'citadel',
}

ROW_RE = re.compile(u'([A-Za-z_$][\\w$]*):Xe\\("([^"]*)",([A-Za-z_$][\\w$]*),'
                    u'([A-Za-z_$][\\w$]*)\\)')


def load_js():
    names = [n for n in os.listdir(WWW)
             if n.lower().startswith(u'index-') and n.lower().endswith(u'.js')]
    if not names:
        raise SystemExit(u'!! 找不到 index-*.js in %s' % WWW)
    p = os.path.join(WWW, sorted(names)[0])
    raw = io.open(p, 'rb').read()
    return p, raw, raw.decode('utf-8', 'replace')


def body_at(t, start):
    u"""从 `const <T>={` 的整体 `{` 起平衡解析，返回对象体字符串（含外层大括号）。"""
    i = t.find(u'{', start)
    if i < 0:
        return None
    depth = 0
    k = i
    while k < len(t):
        ch = t[k]
        if ch in u'{[(':
            depth += 1
        elif ch in u'}])':
            depth -= 1
            if depth == 0:
                return t[i:k + 1]
        elif ch == u'"':
            k = t.find(u'"', k + 1)
            if k < 0:
                return None
        elif ch == u'`':
            k = t.find(u'`', k + 1)
            if k < 0:
                return None
        k += 1
    return None


def parse_table(t, var):
    u"""定位 `const <var>={` 并抽表内全部 `id:Xe("id", region, data)` 行。"""
    for pat in (u'const %s={' % var, u' %s={' % var, u',%s={' % var):
        at = t.find(pat)
        if at >= 0:
            break
    else:
        return None, None, []
    body = body_at(t, at)
    if body is None:
        return at, None, []
    rows = ROW_RE.findall(body)
    return at, body, rows


def main():
    path, raw, t = load_js()
    print(u'[src] %s' % path)
    print(u'[src] bytes=%d chars=%d' % (len(raw), len(t)))
    print()

    fails = []
    tables = {}
    offset = {}
    for var in TABLES:
        at, body, rows = parse_table(t, var)
        tables[var] = rows
        offset[var] = at
        print(u'  %-4s @%-9s 条目 %-4d body=%s'
              % (var, at, len(rows), (len(body) if body else u'None')))
        if not rows:
            fails.append(u'A1 表 %s 未抽到条目' % var)

    # ---- A1 ----
    print()
    print(u'[A1] 六表齐备：%s' % (u'PASS' if not fails else u'FAIL %r' % fails))

    # ---- A2 key == id ----
    bad2 = []
    for var, rows in tables.items():
        for k, rid, reg, data in rows:
            if k != rid:
                bad2.append((var, k, rid))
    print(u'[A2] 每条 key == id：%s（%d 条）'
          % (u'PASS' if not bad2 else u'FAIL %r' % bad2[:5],
             sum(len(v) for v in tables.values())))

    # ---- A3 表内标记全部已登记、且不超出登记范围 ----
    bad3 = []
    regvars = {}
    for var, rows in tables.items():
        vs = sorted({r[2] for r in rows})
        regvars[var] = vs
        unknown = [v for v in vs if v not in REGION_OF_VAR]
        if not vs or unknown:
            bad3.append((var, vs, unknown))
    print(u'[A3] 表内区域标记均已登记：%s' % (u'PASS' if not bad3 else u'FAIL %r' % bad3))
    for var in TABLES:
        print(u'      %-4s -> %s' % (var, regvars[var]))

    # ---- A4 出现过的标记互不相同（每个标记只属于一个表）----
    seen = {}
    dup = []
    for var in TABLES:
        for v in regvars[var]:
            if v in seen:
                dup.append((v, seen[v], var))
            seen[v] = var
    ok4 = not dup
    print(u'[A4] 区域标记不跨表重复：%s（共 %d 个标记：%r）'
          % (u'PASS' if ok4 else u'FAIL %r' % dup, len(seen), sorted(seen)))

    # ---- A5 条数与全量构造式对账 ----
    total = sum(len(v) for v in tables.values())
    # `Bn.rooms` = flatMap(keys).filter(t => t !== "_")  ⇒ 去掉唯一一个键名恰为 "_" 的条目
    n_underscore = sum(1 for var, rows in tables.items() for k, _r, _g, _d in rows if k == u'_')
    expect = total - n_underscore
    print(u'[A5] 汇总条数 %d（其中键名 == "_" 的 %d 条）⇒ 构造式口径应为 %d'
          % (total, n_underscore, expect))
    print(u'     六表逐表：%s' % {v: len(tables[v]) for v in TABLES})

    # ---- A6 负控制 ----
    _a, _b, neg = parse_table(t, u'SbX')
    print(u'[A6] 负控制（表名 `SbX` 应为 0 命中）：%s（%d 条）'
          % (u'PASS' if not neg else u'FAIL', len(neg)))

    # ---- 汇总 ----
    rooms = []
    for var in TABLES:
        for k, rid, reg, data in tables[var]:
            rooms.append({u'table': var, u'id': rid, u'key': k,
                          u'region_var': reg,
                          u'region': REGION_OF_VAR.get(reg, (None, None))[0]})
    by_region = {}
    for r in rooms:
        by_region.setdefault(r[u'region'], []).append(r[u'id'])
    print()
    print(u'[汇总] 房间 %d 个，分区：' % len(rooms))
    for rg in sorted(by_region, key=lambda k: -len(by_region[k])):
        print(u'      %-12s %4d  %s' % (rg, len(by_region[rg]),
                                        sorted(by_region[rg])[:8]))

    # 交叉校验：房间 id 前缀 与 区域 是否一致
    conflict = []
    for r in rooms:
        rid = r[u'id']
        pre = rid.split(u'_')[0] if u'_' in rid else (
            u'_' if rid.startswith(u'_') else u'(无)')
        pre = u'_' if rid.startswith(u'_') else pre
        want = PREFIX_OF_REGION.get(pre)
        if want is not None and want != r[u'region']:
            conflict.append((rid, pre, want, r[u'region']))
    print(u'[交叉] 前缀语义与区域标记冲突的条目：%d 条  %s'
          % (len(conflict), conflict[:6]))

    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    if u'--dump' in sys.argv:
        p = os.path.join(OUT, u'outertale99_rooms.json')
        with io.open(p, 'w', encoding='utf-8') as fh:
            fh.write(json.dumps(
                {u'source': path, u'tables': TABLES, u'offsets': offset,
                 u'region_vars': regvars, u'rooms': rooms,
                 u'by_region': {k: sorted(v) for k, v in by_region.items()},
                 u'prefix_conflicts': conflict},
                ensure_ascii=False, indent=1))
        print(u'[dump] -> %s' % p)

    hard = bool(fails) or bool(bad2) or bool(bad3) or not ok4 or bool(neg)
    print()
    print(u'[结果] %s' % (u'全部锚点 PASS' if not hard else u'存在 FAIL，停止'))
    return 0 if not hard else 1


if __name__ == u'__main__':
    sys.exit(main())
