# -*- coding: utf-8 -*-
"""第44轮续 · 路由表「连接顺序」回归锁 —— 锁死 priority 不变量。

为什么单开一套
--------------
第44轮续复检时**抓到一个 G2 没覆盖的真缺陷**：
`gen_routes44.py` 用 `priority = 110 + (order % 240)`，order 是全局计数器；
跨过 240 回绕后，同一场景的出边 priority 不再随门字母单调 ⇒
`ch2.cyber_field.dw_cyber_maze_virokun` 的默认出口从 A 变 B。
443 条里只有 1 个场景中招 —— 但它**静默**破坏了「没指定门时走字母最靠前
的门」这条设计约定。既有套件（scene_routing / scene_route_original）
都没有锁这条不变量，所以它溜过了 37 套件。

本套件把这个"字母序 = priority 序"的不变量钉死，并同时守护：
  · 生成器不得再出现 `order % <n>` 这类全局取模写法（静态锚点）；
  · priority 值域安全（不与 _DEFAULT_PRIORITY 混叠、无回绕）；
  · 断链 = 原作侧真实死胡同（不是生成器漏编）。

★ 铁律：
  · 成功标记必须 `[PASS]` 字面量（run_all.py:425 按它计数）。
  · 正/负控制成对 —— **负控制必须证明本锁有鉴别力**（用旧写法复现缺陷）。
  · 锚点：产品边必须能由原作门表独立重算出来（解析器输出先过真值锚点）。
"""
import io
import json
import os
import re
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
SC = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes')
TOOLS = os.path.join(HERE, '_tools')

_N = [0]
_FAIL = []


def ok(cond, msg):
    _N[0] += 1
    if cond:
        print('[PASS] %s' % msg)
    else:
        _FAIL.append(msg)
        print('[FAIL] %s' % msg)


def jload(p):
    with io.open(p, encoding='utf-8') as fh:
        return json.load(fh)


def _read(p):
    with io.open(p, encoding='utf-8') as fh:
        return fh.read()


routes = jload(os.path.join(SC, '_routes.json'))
RL = routes.get('routes') or []

# ===========================================================================
# A 生成器静态锚点：不得再有全局取模写法
# ===========================================================================
print('--- A 生成器静态锚点 ---')
gen_src = _read(os.path.join(TOOLS, 'gen_routes44.py'))


def _strip_comments(src):
    """剥掉 # 行注释与三引号/单行字符串，避免"注释里提到旧写法"被误判成
    "代码里还在用旧写法"（A1 第一版就踩了这个 —— 判据自身的坑）。"""
    out = []
    in_tri = None
    for line in src.split('\n'):
        s = line
        if in_tri:
            if in_tri in s:
                s = s.split(in_tri, 1)[1]
                in_tri = None
            else:
                continue
        for q in ('"""', "'''"):
            if q in s:
                # 行内成对 → 只删其间；否则进入跨行态
                first = s.index(q)
                rest = s[first + 3:]
                if q in rest:
                    s = s[:first] + rest.split(q, 1)[1]
                else:
                    s = s[:first]
                    in_tri = q
                break
        if '#' in s:
            s = s.split('#', 1)[0]
        out.append(s)
    return '\n'.join(out)


gen_code = _strip_comments(gen_src)

# A1 旧写法必须从**代码**里消失（`order % 240` 之类）
ok(not re.search(r'order\s*%\s*\d+', gen_code),
   'A1 gen_routes44 代码中不再出现 `order % <n>` 全局取模写法')

# A2 新写法须在位（场景段 + 段内序）
ok('scene_ord' in gen_src and 'BAND' in gen_src,
   'A2 gen_routes44 用「场景段 + 段内序」赋 priority')

# A3 生成器里必须真的带「同场景字母序 = priority 序」的注释（意图可查）
ok('字母序' in gen_src and 'priority 回绕' in gen_src,
   'A3 gen_routes44 记录了回绕缺陷与修复意图（注释留痕）')

# ===========================================================================
# B priority 不变量（正控制）
# ===========================================================================
print('--- B priority 不变量 ---')
by_src = collections.defaultdict(list)
for r in RL:
    by_src[r.get('when_scene')].append(r)

multi = {k: v for k, v in by_src.items() if len(v) > 1}
ok(len(multi) > 100,
   'B1 多出边场景数 > 100（实测 %d，确保判据有真实样本）' % len(multi))

# B2 ★ 核心不变量：同一场景内，按 priority 升序取出的门字母必须递增
bad = []
for k, v in multi.items():
    v2 = sorted(v, key=lambda r: r.get('priority'))
    letters = [r.get('when_door') for r in v2]
    if letters != sorted(letters):
        bad.append((k, letters))
ok(not bad,
   'B2 ★同场景内「字母序 == priority 序」（0 例外；实测 %d 个多出口场景）'
   % len(multi))

# B2b 负控制：用旧写法（全局取模）**必须能复现**至少一个违例
#      —— 证明 B2 有鉴别力，不是恒真。
def _old_priority_letters():
    """按旧写法 110 + (order % 240) 重算，看是否产生字母序错乱。"""
    order = 0
    out = {}
    for sa in sorted(by_src):
        exits = sorted(by_src[sa], key=lambda r: (r.get('when_door'), r.get('to')))
        lst = []
        for r in exits:
            lst.append((110 + (order % 240), r.get('when_door')))
            order += 1
        out[sa] = [L for (_p, L) in sorted(lst)]
    return out


old = _old_priority_letters()
old_bad = [k for k, L in old.items() if len(L) > 1 and L != sorted(L)]
ok(len(old_bad) >= 1,
   'B2b 负控制：旧写法确实复现字母序错乱（%d 个，证明 B2 有鉴别力）'
   % len(old_bad))

# B3 无回绕：全局 priority 声明序单调不减（新写法保证）
prios = [r.get('priority') for r in RL]
drops = [i for i in range(1, len(prios)) if prios[i] < prios[i - 1]]
ok(not drops, 'B3 priority 声明序无回绕（下降次数 = %d）' % len(drops))

# B4 值域安全：全部 >= 100 且不与未来手写低区间冲突（>=110）
ok(all(isinstance(p, int) and p >= 110 for p in prios),
   'B4 priority 全为 int 且 >= 110（实测值域 [%d, %d]）'
   % (min(prios), max(prios)))

# B5 每条规则都显式带 priority（不依赖 _DEFAULT_PRIORITY）
ok(all('priority' in r for r in RL),
   'B5 全部 %d 条规则显式带 priority（不落 _DEFAULT_PRIORITY）' % len(RL))

# B6 每条规则都带 when_door（共同卡口分流的依据）
ok(all(isinstance(r.get('when_door'), str) and r.get('when_door')
       for r in RL),
   'B6 全部规则带 when_door（解决共同卡口）')

# ===========================================================================
# C 锚点：产品边可由原作门表独立重算
# ===========================================================================
print('--- C 原作锚点 ---')
DRW = r'E:\Download\_tmp\drw'
CHS = ['chapter1_windows', 'chapter2_windows', 'chapter3_windows',
       'chapter4_windows', 'chapter5_windows']
TAG = {CHS[i]: 'ch%d' % (i + 1) for i in range(5)}
DELTA = {'A': 1, 'B': -1, 'C': 2}


def dletter(n):
    if not n or not n.startswith('obj_door'):
        return None
    t = n[len('obj_door'):]
    for s in ('_musfade', '_solid'):
        if t.endswith(s):
            t = t[:-len(s)]
    if len(t) == 1 and t.isalpha() and t.upper() in DELTA:
        return t.upper()
    return None


def mletter(n):
    if not n or not n.startswith('obj_marker'):
        return None
    t = n[len('obj_marker'):]
    if len(t) == 1 and t.isalpha() and t.isupper():
        return t
    return None


def pts(l):
    o = []
    for s in l or []:
        p = str(s).split(',')
        if len(p) >= 3:
            o.append((p[0], p[1], p[2]))
    return o


have_rooms = all(os.path.isfile(os.path.join(DRW, w, 'rooms44.json'))
                 for w in CHS)
if have_rooms:
    rooms = {}
    for w in CHS:
        d = jload(os.path.join(DRW, w, 'rooms44.json'))
        for r in d['rooms']:
            rooms[(TAG[w], r['id'])] = r

    idx = jload(os.path.join(SC, '_index.json'))
    by_room = {}
    for chid, c in (idx.get('chapters') or {}).items():
        for aid, a in (c.get('areas') or {}).items():
            for sid, e in (a.get('scenes') or {}).items():
                if isinstance(e.get('original_room_id'), int):
                    by_room[(chid, e['original_room_id'])] = sid

    orig_edges = set()
    for (ch, rid), r in rooms.items():
        sa = by_room.get((ch, rid))
        if not sa:
            continue
        for (_x, _y, dn) in pts(r.get('doors')):
            L = dletter(dn)
            if not L:
                continue
            tr = rooms.get((ch, rid + DELTA[L]))
            if tr is None:
                continue
            if not any(mletter(m) == L for (_a, _b, m) in pts(tr.get('markers'))):
                continue
            sb = by_room.get((ch, tr['id']))
            if sb:
                orig_edges.add((sa, sb))

    prod_edges = set((r.get('when_scene'), r.get('to')) for r in RL)
    ok(prod_edges == orig_edges,
       'C1 ★产品边集合 == 原作门表独立重算集合（各 %d 条，差值 %d）'
       % (len(prod_edges), len(prod_edges ^ orig_edges)))

    # C2 断链归因：'to 无出边的场景' 里，凡原作**能编出边**的都算真缺口。
    #   ⚠️ 判据必须是"原作侧按同一机制能编出边"，而不是"该房有没有字母门" ——
    #   第一版就误用了后者：`schooldoor` 的房间有 C 门，但 C 门的目标房
    #   `room_school_unusedroom` **未登记为场景** ⇒ 生成器本就编不出边，
    #   属"覆盖策略如实报告"，不是漏编。判据不完整 = 报假问题。
    tos = set(r.get('to') for r in RL)
    froms = set(r.get('when_scene') for r in RL)
    dead = sorted(tos - froms)
    real_gap = [sid for sid in dead if sid in {sa for (sa, _sb) in orig_edges}]
    ok(not real_gap,
       'C2 断链 %d 个全为原作死胡同（能编出边却漏编的真缺口 = %d：%s）'
       % (len(dead), len(real_gap), real_gap[:3]))

    # C2b 断链里必须**确实存在**"有字母门但目标未登记"的样本
    #     （证明 C2 的口径不是"把所有断链都算成正常"）
    lettered_dead = 0
    for sid in dead:
        e = {}
        for chid, c in (idx.get('chapters') or {}).items():
            for aid, a in (c.get('areas') or {}).items():
                if sid in (a.get('scenes') or {}):
                    e = dict(a['scenes'][sid])
                    e['chapter_id'] = chid
        ch, orid = e.get('chapter_id'), e.get('original_room_id')
        rec = rooms.get((ch, orid)) if isinstance(orid, int) else None
        if rec and any(dletter(dn) for (_x, _y, dn) in pts(rec.get('doors'))):
            lettered_dead += 1
    ok(lettered_dead >= 1,
       'C2b 断链中有 %d 个房带字母门却编不出边（目标未登记/无落点）——'
       '证明 C2 未把真缺口一并放过' % lettered_dead)
else:
    print('[SKIP] C 段：原作 rooms44.json 不在（临时区，可能已清）——'
          '跳过锚点，但 B 段不变量仍生效')

# ===========================================================================
# D 兜底与结构
# ===========================================================================
print('--- D 兜底与结构 ---')
fb = routes.get('_fallback') or {}
ok(isinstance(fb.get('to'), str) and fb.get('to'),
   'D1 _fallback 有合法 to（= %r）' % fb.get('to'))
ok(routes.get('schema_version') == 1, 'D2 schema_version == 1')
meta = routes.get('meta') or {}
ok('critical_warning_priority_beats_score' in meta,
   'D3 meta 保留「priority 压过 score」警告')

# D4 恒真自查：多出边场景里确实存在字母不同的（否则 B2 无意义）
diff_letter = [k for k, v in multi.items()
               if len(set(r.get('when_door') for r in v)) > 1]
ok(len(diff_letter) >= 20,
   'D4 有 %d 个场景的出边字母互不相同（B2 才有鉴别力）' % len(diff_letter))

print()
print('合计 PASS=%d FAIL=%d' % (_N[0] - len(_FAIL), len(_FAIL)))
if _FAIL:
    raise SystemExit(1)
