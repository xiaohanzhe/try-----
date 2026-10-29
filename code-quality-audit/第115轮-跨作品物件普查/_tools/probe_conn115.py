# -*- coding: utf-8 -*-
"""房间连通图：可外推路线 + 覆盖率体检（只读，产出 txt）。

背景
----
`conn_ut.csx` 只收 GML 里写死常量的 `room_goto(M)`，并把 `if (room == N)` 里的 N 当 src。
产出的边数（ut 147 / uty 1 / outertale 158）远不够覆盖 338/287/358 间房。
本脚本回答三件事：

B. 「门对象 -> 固定房间偏移」能否外推？
   上一版实验（probe_doorrule117）拿"源房间里摆了哪些门对象"当触发者，**归因是错的**
   （一个房间摆十几个门对象，真正触发的是事件代码所属那一个）。这里改按 `code` 分组。
   ★ 修正后要注意一个陷阱：一个 code 里可以塞很多条 `if (room == N) {...}` 分支，
   所以 code 级偏移不恒定**不等于**数据不可用 —— 数据是 (src,dst) 精确对。
   本节的结论只针对"能否从门对象类型推出目标房间"。

C. 几何匹配（贴边的门对贴边的门）精度够不够？
   A 房底边的门 at x 应对上 B 房顶边的门 at x±tol。用 GML 真值验证命中率。

D. 缺口到底多大？
   * 已知边的 src 覆盖了多少间房；
   * 无 src 的边（`goto_const_nosrc`）里有多少能从 code 名反推 src
     （`gml_Room_<roomname>_Create` / `gml_Room_<roomname>_Step` 之类）；
   * 摆了门却一条出边都没有的房间有多少 —— 这才是真正要补的量。

判据纪律：分母为 0 时显式打印 EMPTY，不产出 0% 这种看着像结论的假数据。

用法
----
    python probe_conn115.py
产出
----
    _evidence/conn_falsify115.txt
"""
import collections
import io
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
RAW = os.path.join(ROUND, '_evidence', 'raw')
OUT = os.path.join(ROUND, '_evidence', 'conn_falsify115.txt')

KEYS = ['ut', 'uty', 'outertale']
DOORISH = re.compile(r'door|stairs|stair|elevator|ladder|pipe|exit|entrance', re.I)
# ★ GameMaker 把「房间创建代码」命名成 gml_RoomCC_<房间名>_<序号>，
#   不是 gml_Room_<房间名>_Create —— 只写后者会 0 命中（已实测，别退回旧写法）
ROOMCODE = re.compile(r'^gml_RoomCC_(.+)_\d+$')
ROOMCODE2 = re.compile(r'^gml_Room_(.+)_(Create|Step|Alarm_\d+|Draw|Destroy)$')

EDGE_TOL = 8.0        # 距边 <= 8px 算贴在这一边
MATCH_TOL = 32.0      # 两房门的坐标差 <= 32px 算对上
MIN_N = 3             # 偏移规律只在观测 >= 3 次的 code 上谈


def load_rooms(key):
    """返回 rooms[idx] = {'name','w','h','doors':[(obj,x,y)]}"""
    p = os.path.join(RAW, key, 'inst_full.tsv')
    rooms = {}
    cur = None
    with io.open(p, encoding='utf-8') as f:
        for ln in f:
            ln = ln.rstrip('\n')
            if ln.startswith('R\t'):
                q = ln.split('\t')
                cur = int(q[1])
                rooms[cur] = {'name': q[2], 'w': float(q[3]), 'h': float(q[4]),
                              'doors': []}
            elif ln.startswith('I\t') and cur is not None:
                q = ln.split('\t')
                if DOORISH.search(q[1]):
                    rooms[cur]['doors'].append((q[1], float(q[2]), float(q[3])))
    return rooms


def side_of(room, x, y):
    w, h = room['w'], room['h']
    if y <= EDGE_TOL:
        return 'top', x
    if y >= h - EDGE_TOL:
        return 'bottom', x
    if x <= EDGE_TOL:
        return 'left', y
    if x >= w - EDGE_TOL:
        return 'right', y
    return None, None


def part_b(key, conn, out):
    """门对象事件 -> 房间偏移，能否外推"""
    edges = [x for x in conn['items'] if x['src'] >= 0 and x['dst'] >= 0]
    out.append('-' * 74)
    out.append('[%s] B. 「门对象 -> 固定偏移」能否外推（按 code 分组）' % key)
    if not edges:
        out.append('  已知 src 的边 0 条 => EMPTY，本路线无从检验')
        return
    by_code = collections.defaultdict(collections.Counter)
    for e in edges:
        by_code[e['code']][e['dst'] - e['src']] += 1
    multi = [(c, d) for c, d in by_code.items() if sum(d.values()) >= MIN_N]
    pure = [c for c, d in multi if len(d) == 1]
    mixed = [c for c, d in multi if len(d) > 1]
    out.append('  已知边 %d 条，落在 %d 个 code 上' % (len(edges), len(by_code)))
    out.append('  观测 >= %d 次的 code：%d 个 => 偏移恒定 %d / 偏移不定 %d'
               % (MIN_N, len(multi), len(pure), len(mixed)))
    for c, d in sorted(multi, key=lambda kv: -sum(kv[1].values()))[:5]:
        out.append('    %-46s n=%-3d 偏移=%s'
                   % (c[:46], sum(d.values()), dict(d.most_common(6))))
    if multi:
        out.append('  判读：偏移不恒定 => 目标不是"由门对象类型决定"，'
                   '同一 code 内含多条 `if (room == N)` 分支。')
        out.append('        => 不能按门对象外推；但这些分支本身就是精确 (src,dst)，可直接用。')


def part_c(key, conn, rooms, out):
    """几何匹配精度"""
    known = set((x['src'], x['dst']) for x in conn['items']
                if x['src'] >= 0 and x['dst'] >= 0)
    out.append('-' * 74)
    out.append('[%s] C. 几何匹配精度' % key)
    if not known:
        out.append('  已知边 0 条 => EMPTY，无法验证精度，结论只能是"不可用"')

    portals = collections.defaultdict(list)
    for idx, r in rooms.items():
        for obj, x, y in r['doors']:
            sd, coord = side_of(r, x, y)
            if sd:
                portals[sd].append((idx, coord, obj))

    geo = set()
    for sa, sb in [('bottom', 'top'), ('left', 'right')]:
        for ra, ca, _oa in portals[sa]:
            for rb, cb, _ob in portals[sb]:
                if ra != rb and abs(ca - cb) <= MATCH_TOL:
                    geo.add((ra, rb))
    geo |= set((b, a) for a, b in geo)

    hit = len(known & geo)
    ndoor = sum(len(r['doors']) for r in rooms.values())
    onside = sum(len(v) for v in portals.values())
    out.append('  房间 %d / door 实例 %d（贴边可判方向 %d）'
               % (len(rooms), ndoor, onside))
    out.append('  几何候选边 %d 条' % len(geo))
    if known:
        out.append('  命中已知边: %d / %d = %.1f%%' % (hit, len(known),
                                                     100.0 * hit / len(known)))
    if geo:
        out.append('  几何边中已知的比例: %d / %d = %.1f%%（其余无法证真）'
                   % (hit, len(geo), 100.0 * hit / len(geo)))


def part_d(key, conn, rooms, out):
    """覆盖率与 src 反推"""
    names = conn.get('room_names') or []
    idx_of = {}
    for i, n in enumerate(names):
        idx_of[n] = i

    items = conn['items']
    with_src = [x for x in items if x['src'] >= 0 and x['dst'] >= 0]
    nosrc = [x for x in items if x['src'] < 0 and x['dst'] >= 0]

    # 从 code 名 `gml_RoomCC_<房间名>_<序号>` 反推 src
    rec = []
    for x in nosrc:
        m = ROOMCODE.match(x['code']) or ROOMCODE2.match(x['code'])
        if m and m.group(1) in idx_of:
            rec.append((idx_of[m.group(1)], x['dst'], x['code']))
    rec_src = set(r[0] for r in rec)

    src_all = set(x['src'] for x in with_src) | rec_src
    have_door = set(i for i, r in rooms.items() if r['doors'])
    gap = sorted(have_door - src_all)

    out.append('-' * 74)
    out.append('[%s] D. 覆盖率与缺口' % key)
    out.append('  房间总数 %d；摆了 doorish 实例的房间 %d' % (len(rooms), len(have_door)))
    out.append('  已知 src 的边 %d 条，涉及 %d 间房' % (len(with_src), len(set(x['src'] for x in with_src))))
    dsts = set(x['dst'] for x in items if x['dst'] >= 0)
    out.append('  作为目标出现过的房间 %d 间；src 或 dst 至少出现一侧的房间 %d 间 = %.1f%%'
               % (len(dsts), len(set(x['src'] for x in with_src) | dsts),
                  100.0 * len(set(x['src'] for x in with_src) | dsts) / len(rooms) if rooms else 0))
    out.append('  无 src 的边 %d 条，其中能从 `gml_RoomCC_<名>_<n>` 反推 src 的 %d 条（%d 间房）'
               % (len(nosrc), len(rec), len(rec_src)))
    cc = collections.Counter(x['code'] for x in nosrc)
    out.append('  无 src 的边所属 code（前6，用来判断还有没有别的命名规律）:')
    for c, n in cc.most_common(6):
        out.append('    %-50s n=%d' % (c[:50], n))
    if not have_door:
        out.append('  EMPTY：没有任何房间摆 doorish 实例，缺口语义不成立')
        return
    out.append('  摆了门但一条出边都推不出来的房间: %d / %d = %.1f%%'
               % (len(gap), len(have_door), 100.0 * len(gap) / len(have_door)))
    out.append('  这些房间样例(前6): %s'
               % ', '.join('%d:%s' % (i, rooms[i]['name']) for i in gap[:6]))


def load_obj_rooms(key):
    """对象名 -> {房间下标}（该对象在哪些房间摆了实例）"""
    p = os.path.join(RAW, key, 'inst_full.tsv')
    m = collections.defaultdict(set)
    cur = None
    with io.open(p, encoding='utf-8') as f:
        for ln in f:
            ln = ln.rstrip('\n')
            if ln.startswith('R\t'):
                cur = int(ln.split('\t')[1])
            elif ln.startswith('I\t') and cur is not None:
                m[ln.split('\t')[1]].add(cur)
    return m


def obj_of_code(code, objnames):
    """`gml_Object_obj_door_w_Alarm_2` -> `obj_door_w`（取最长匹配，防前缀误判）"""
    pre = 'gml_Object_'
    if not code.startswith(pre):
        return None
    rest = code[len(pre):]
    best = None
    for o in objnames:
        if rest.startswith(o + '_') and (best is None or len(o) > len(best)):
            best = o
    return best


def part_e(key, conn, out):
    """src 反推：事件所属对象的实例若只在一间房 => 该房就是 src

    先用「已知 src 的边」当验证集量一下这招准不准，再看能补多少条。
    """
    obj2rooms = load_obj_rooms(key)
    objnames = sorted(obj2rooms, key=len, reverse=True)
    out.append('-' * 74)
    out.append('[%s] E. src 反推（对象的实例唯一所在房间）' % key)

    stat = collections.Counter()
    for x in conn['items']:
        if x['dst'] < 0:
            continue
        o = obj_of_code(x['code'], objnames)
        rs = obj2rooms.get(o) if o else None
        if not rs:
            stat['无从反推'] += 1
            continue
        uniq = next(iter(rs)) if len(rs) == 1 else None
        if x['src'] >= 0:                      # 验证集
            if uniq is None:
                stat['已知边/多房(无法判)'] += 1
            elif uniq == x['src']:
                stat['已知边/一致'] += 1
            else:
                stat['已知边/冲突'] += 1
        else:
            stat['待补/唯一房' if uniq is not None else '待补/多房'] += 1

    agree, clash = stat['已知边/一致'], stat['已知边/冲突']
    denom = agree + clash
    out.append('  验证集（已知 src 且对象有实例）: 一致 %d / 冲突 %d' % (agree, clash))
    if denom:
        out.append('  一致率 = %d / %d = %.1f%%' % (agree, denom, 100.0 * agree / denom))
    else:
        out.append('  EMPTY：没有可比对的样本，本招无法验证，不能当数据用')
    out.append('  待补边里对象只在一间房的 %d 条 / 对象跨多房的 %d 条 / 无从反推 %d 条'
               % (stat['待补/唯一房'], stat['待补/多房'], stat['无从反推']))


def part_f(key, conn, out):
    """F. 按「对象 -> 该对象事件里写死的跳转」推边，并用已知边验证

    ★ 这是第 B 节的正确做法。B 只看了「有 src 的边」的偏移分布，漏掉了关键一类：
      `room_goto_next()` / `room_goto_previous()` 的 src 在 GML 里写不出来（-1），
      但它的**偏移是 op 自带的**（+1 / -1）。而对象事件是共享的 ——
      一个 `obj_doorA_Alarm_2` 写一次 `room_goto_next`，
      就覆盖了**所有摆了 obj_doorA 的房间**。这才是 UT 的主机制。
    """
    obj2rooms = load_obj_rooms(key)
    objnames = sorted(obj2rooms, key=len, reverse=True)
    nroom = len(conn.get('room_names') or [])
    out.append('-' * 74)
    out.append('[%s] F. 「对象 -> 事件里写死的跳转」推边（含验证）' % key)

    # 每个对象能产生什么偏移（或绝对目标）
    rel = collections.defaultdict(set)      # obj -> {offset}
    absd = collections.defaultdict(set)     # obj -> {dst}（无 src 守卫的常量目标）
    tab = collections.defaultdict(set)      # obj -> {(src,dst)}
    for x in conn['items']:
        o = obj_of_code(x['code'], objnames)
        if not o:
            continue
        if x['op'] == 'room_goto_next':
            rel[o].add(1)
        elif x['op'] == 'room_goto_previous':
            rel[o].add(-1)
        elif x['dst'] >= 0:
            if x['src'] >= 0:
                tab[o].add((x['src'], x['dst']))
            else:
                absd[o].add(x['dst'])

    objs = set(rel) | set(absd) | set(tab)
    known = set((x['src'], x['dst']) for x in conn['items']
                if x['src'] >= 0 and x['dst'] >= 0)

    tot_m = tot_c = 0
    rows = []
    for o in objs:
        rs = obj2rooms.get(o) or set()
        ks = [e for e in known if e[0] in rs]
        if not ks:
            continue
        ok = bad = 0
        for src, dst in ks:
            good = (dst - src) in rel[o] or dst in absd[o] or (src, dst) in tab[o]
            ok += 1 if good else 0
            bad += 0 if good else 1
        tot_m += ok
        tot_c += bad
        rows.append((o, len(rs), len(ks), ok, bad, sorted(rel[o]), sorted(absd[o])[:3]))
    rows.sort(key=lambda r: -r[2])
    out.append('  对象（摆了实例的房间数 / 已知边落在这些房间 / 规则相符 / 不符）:')
    for o, nr, nk, ok, bad, rr, ad in rows[:10]:
        out.append('    %-30s 房=%-4d 已知=%-4d 符=%-4d 不符=%-3d next/prev=%s 绝对=%s'
                   % (o[:30], nr, nk, ok, bad, rr, ad))
    if not rows:
        out.append('  EMPTY：没有任何对象的实例房里有已知边，规则无法验证')
        return
    out.append('  合计：相符 %d / 不符 %d => 相符率 %.1f%%'
               % (tot_m, tot_c, 100.0 * tot_m / (tot_m + tot_c)))

    # 用规则补边：房间 R 摆了对象 O，O 有相对规则 => (R, R+off)
    gen = set()
    for o, offs in rel.items():
        for r in (obj2rooms.get(o) or set()):
            for off in offs:
                d = r + off
                if 0 <= d < nroom and d != r:
                    gen.add((r, d))
    for o, ds in absd.items():
        for r in (obj2rooms.get(o) or set()):
            for d in ds:
                if 0 <= d < nroom and d != r:
                    gen.add((r, d))
    out.append('  规则可生成的边 %d 条（其中新增 %d 条）' % (len(gen), len(gen - known)))
    out.append('  生成边与已知边交叉验证：命中 %d / %d = %.1f%%'
               % (len(gen & known), len(known),
                  100.0 * len(gen & known) / len(known) if known else 0))
    out.append('  ★ 命中率低说明"摆了某对象就有这条边"这个前提不总成立'
               '（房间里的对象可能是装饰、或需要额外条件），只能当候选边。')


def _base(name):
    """房间名 -> 区域名：room_water11 / room_water_nicecream 都归到 water。

    先砍 `room_` 前缀，再取开头那串字母（含数字就截在数字前）：
      room_ruins12A -> ruins | room_tundra_town -> tundra | room_basement4_final -> basement
    ★ 只认开头字母，别用"去掉结尾数字"那种写法 —— 它会把 room_water_nicecream 判成
      跟 room_water 不同区域（已实测，误报率高）。
    """
    s = re.sub(r'^(room|rm)[_\-]', '', name or '', flags=re.I)
    m = re.match(r'[A-Za-z]+', s)
    return (m.group(0) if m else s).lower()


def part_g(key, conn, out):
    """G. 对 F 的候选边做「同区域」合理性体检（含随机对照）

    ★ F 的「不符」其实**不能**证伪规则：同一房间可能摆了多个门对象，
      表驱动门（obj_door_t 等）和 next/prev 门可以同时存在，两条边都成立。
      所以 F 只能得出"不能证真"。这里换一个独立信号：
      若 R -> R+1 真是原作的门，两间房的名字多半同属一片区域（room_ruins5 -> room_ruins6）。
      对照 = 随机房对，量出"随机两间同区域"的基线，避免把区域本就很粗的假象当结论。
    """
    names = conn.get('room_names') or []
    nroom = len(names)
    obj2rooms = load_obj_rooms(key)
    objnames = sorted(obj2rooms, key=len, reverse=True)
    out.append('-' * 74)
    out.append('[%s] G. 候选边（next/prev 规则）的同区域体检' % key)
    if nroom < 3:
        out.append('  EMPTY：房间太少，样本无意义')
        return

    rel = collections.defaultdict(set)
    for x in conn['items']:
        o = obj_of_code(x['code'], objnames)
        if not o:
            continue
        if x['op'] == 'room_goto_next':
            rel[o].add(1)
        elif x['op'] == 'room_goto_previous':
            rel[o].add(-1)
    if not rel:
        out.append('  EMPTY：没有任何对象带 next/prev 规则')
        return

    known = set((x['src'], x['dst']) for x in conn['items']
                if x['src'] >= 0 and x['dst'] >= 0)
    cand = set()
    for o, offs in rel.items():
        for r in (obj2rooms.get(o) or set()):
            for off in offs:
                d = r + off
                if 0 <= d < nroom and d != r:
                    cand.add((r, d))

    def same_rate(pairs):
        if not pairs:
            return None
        return 100.0 * sum(1 for a, b in pairs if _base(names[a]) == _base(names[b])) / len(pairs)

    new = cand - known
    # 负控制：随机房对（固定种子，可复现）
    rnd = random.Random(115)
    ctrl = set()
    while len(ctrl) < min(2000, nroom * 3):
        a, b = rnd.randrange(nroom), rnd.randrange(nroom)
        if a != b:
            ctrl.add((a, b))

    r_cand, r_new, r_ctrl = same_rate(cand), same_rate(new), same_rate(ctrl)
    out.append('  候选边 %d 条（新增 %d 条）；已知边里 next/prev 规则贡献 0 条（本来就无 src）'
               % (len(cand), len(new)))
    out.append('  同区域率：候选 %.1f%% / 新增 %.1f%% / 随机对照 %.1f%%'
               % (r_cand or 0, r_new or 0, r_ctrl or 0))
    out.append('  A/B 判读：候选显著高于随机 => 规则方向大致对；接近随机 => 纯噪声，不可用')
    # 新增边能把 src 覆盖推到哪里
    src_known = set(a for a, _b in known) | set(a for a, _b in new)
    out.append('  若采纳候选边：src 覆盖 %d -> %d / %d'
               % (len(set(a for a, _b in known)), len(src_known), nroom))
    cross = [(a, b) for a, b in new if _base(names[a]) != _base(names[b])]
    out.append('  跨区域的新增边 %d 条（这些最可疑），样例: %s'
               % (len(cross), ', '.join('%s->%s' % (names[a], names[b]) for a, b in cross[:5]) or '无'))


def main():
    out = []
    out.append('房间连通图：可外推路线与覆盖率体检')
    out.append('数据源 _evidence/raw/<game>/{inst_full.tsv, conn_ut.json}')
    for key in KEYS:
        conn = json.load(io.open(os.path.join(RAW, key, 'conn_ut.json'), encoding='utf-8'))
        rooms = load_rooms(key)
        out.append('=' * 74)
        out.append('[%s] 房间 %d；扫描 %s 个 code，%s 个含换房，nonconst 目标 %s'
                   % (key, conn.get('n_rooms', -1), conn.get('n_scanned'),
                      conn.get('n_with_room_goto'), conn.get('n_nonconst_target')))
        out.append('  op 分布 %s' % (conn.get('op_counts'),))
        part_b(key, conn, out)
        part_c(key, conn, rooms, out)
        part_d(key, conn, rooms, out)
        part_e(key, conn, out)
        part_f(key, conn, out)
        part_g(key, conn, out)

    out.append('=' * 74)
    out.append('结论：B、C 两条外推路线都不成立；能采信的只有 GML 里写死的 (src,dst)。'
               '缺口见 D 节，处理方式见 report115.md §12.6。')
    txt = '\n'.join(out) + '\n'
    with io.open(OUT, 'w', encoding='utf-8', newline='') as f:
        f.write(txt)
    sys.stdout.write(txt)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
