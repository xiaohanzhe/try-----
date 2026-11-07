# -*- coding: utf-8 -*-
u"""第170轮：把反编译出的 W 门 GML **源码**解析成「房间 → 分支」表。

为什么不用第169轮那套字节码反推
--------------------------------
字节码里 `Push VAR=x / PushI lo / Cmp / Bf ...` 只能猜出 x 区间，且
「分支无 x 条件」与「解析失败」长得一样（都退化成 None）。
源码里这三件事**字面可读**：

    if (room == room_town_mid)
    {
        if (x > 290 && x < 370)   { global.entrance = 20; room_goto(room_lw_icee_pizza); }
        if (x > 1730 && x < 1840) { global.entrance = 23; room_goto(room_alphysalley); }
    }

★ 三类分支（本文件的核心分类，`kind` 字段）
------------------------------------------------
  · `uncond` —— 块内直接 `room_goto`：**该房间该门只有一扇**，1:1，无需区分。
  · `x`      —— 块内按 `if (x > A && x < B)` 分流：**按门实例位置**，可精确对上实例。
  · `other`  —— 块内按 flag / random / 函数分流（例：`room_cc_elevator` 的
                `global.flag[239]`、`room_dw_city_traffic_3` 的 `random(50)`）：
                **不是「哪一扇门」的问题**，是运行时状态。产品侧不模仿，如实留档。

★ 开闭区间必须记账（`xlo_incl` / `xhi_incl`）
  GML 写的是 `x > 290 && x < 370`（**严格不等**）。若当成 `>=`/`<=`，
  将来一旦有门的 x 恰好等于边界，就会静默多匹配一扇 —— 这种错很难发现。
"""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
GMLROOT = os.path.join(ROUND, '_evidence', 'gml')
EV42 = os.path.join(REPO, 'code-quality-audit', '第42轮-原作拓扑取证', '_evidence')
OUT = os.path.join(ROUND, '_evidence', 'gml170.json')

#: 章 → 第42轮那份证据（要里面的 `room_names` 做 name→id）
CH_ROOMFILE = {
    'ch1': 'conn42b.json', 'ch2': 'ch2_conn42b.json', 'ch3': 'ch3_conn42b.json',
    'ch4': 'ch4_conn42b.json', 'ch5': 'ch5_conn42b.json',
}
#: 对象名 → GML code 名（两份控制器，第168轮同一份常量）
CODES = {
    'obj_doorW': 'gml_Object_obj_doorW_Alarm_2',
    'obj_doorw_musfade': 'gml_Object_obj_doorw_musfade_Alarm_2',
}

RE_GUARD = re.compile(r'^if\s*\(\s*room\s*==\s*([A-Za-z_]\w*)\s*\)$')
RE_GOTO = re.compile(r'room_goto\s*\(\s*([A-Za-z_]\w*|\d+)\s*\)')
RE_ENT = re.compile(r'global\.entrance\s*=\s*(-?\d+)')
RE_XCMP = re.compile(r'x\s*(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)')
RE_XIF = re.compile(r'^if\s*\(\s*(.+?)\s*\)$')


def load_room_names(ch):
    p = os.path.join(EV42, CH_ROOMFILE[ch])
    s = io.open(p, encoding='utf-8', errors='replace', newline='').read()
    s = s.replace(': True', ': true').replace(': False', ': false')
    d = json.loads(s)
    return list(d.get('room_names') or [])


def read_lines(p):
    s = io.open(p, encoding='utf-8', errors='replace', newline='').read()
    return [ln.rstrip('\r') for ln in s.replace('\r\n', '\n').split('\n')]


def block_after(lines, i):
    u"""`lines[i]` 是 `if (...)`, 返回 (块体行列表, 块后下一行下标)。"""
    j = i + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    if j >= len(lines) or lines[j].strip() != '{':
        return None, i + 1
    depth = 0
    start = j + 1
    while j < len(lines):
        t = lines[j]
        depth += t.count('{') - t.count('}')
        if depth == 0 and j >= start - 1:
            return lines[start:j], j + 1
        j += 1
    return None, len(lines)


def top_blocks(lines):
    u"""抽出所有**顶层** `if (room == X) { ... }`（跳过嵌套块里的同名形态）。"""
    out = []
    depth = 0
    i = 0
    while i < len(lines):
        t = lines[i].strip()
        if t == '}' or t.startswith('}'):
            depth = max(0, depth - t.count('}'))
        if depth == 0:
            m = RE_GUARD.match(t)
            if m:
                body, nxt = block_after(lines, i)
                if body is not None:
                    out.append((m.group(1), body, i))
                    i = nxt
                    continue
        depth += t.count('{') - t.count('}')
        i += 1
    return out


#: ★★★ 否定式必须**先翻转再解析**（本轮第二个贵坑）
#:   `else` 分支的条件我记作 `!(x < 0)`，但 `axis_range_of` 原来只看
#:   `x < 0` 这段 ⇒ 解出 `hi=0`，语义却是 `x >= 0`，**方向整个反了**。
#:   实测被它污染 6 条：`!(y > 4700)`→`[4700,None]`（应为 `[None,4700]`）、
#:   `!(y < 200)`→`[None,200]`（应为 `[200,None]`）、`!(x > 1200)`→`[1200,None]`…
#:   而 `feasible170.in_range()` 正是拿这个 lo/hi 去算「命中哪扇门」，
#:   所以反的区间会**把房间判错**，连带我那 11 条坐标也可能跟着变。
_NEG = re.compile(r'!\s*\(\s*([xy])\s*(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)\s*\)')
_FLIP = {'>': '<=', '>=': '<', '<': '>=', '<=': '>'}


def _unnest(cond):
    u"""`!(x < 0)` → `x >= 0`；`!(global.plot < 120)` 不动（不是 x/y 轴）。"""
    return _NEG.sub(lambda m: '%s %s %s' % (m.group(1), _FLIP[m.group(2)], m.group(3)), cond)


def axis_range_of(cond):
    u"""把 `x > 290 && x < 370` / `y > 900` 解成 (axis, lo, lo_incl, hi, hi_incl)。

    ★ 轴有两种：`x`（左右门）与 `y`（上下门）。只认 `x` 会漏掉
      `room_dw_cyber_maze_rhythm` 这类「上出口 / 下出口」，把它们误判成 `other`。
    ★ 也认单边（`x < 10` 只有上界）。解不出 → None。
    ★ 否定式先归一（见 `_unnest`），否则区间方向会反。
    """
    cond = _unnest(cond)
    # ★ 复合否定式（`!(x < 10 && global.plot < 120)`）归一不了：
    #   里面那一半条件是**否定范围内**的一部分，拿它当区间＝把"不全是"当"是"。
    #   宁可解不出（None），也不许拿半个条件充数。
    if '!(' in cond.replace(' ', ''):
        return None
    axes = set(re.findall(r'\b([xy])\s*(?:>=|<=|>|<)', cond))
    if len(axes) != 1:
        return None                      # 没有、或同一条件里混了 x 和 y（不敢猜）
    axis = axes.pop()
    parts = re.findall(r'\b%s\s*(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)' % axis, cond)
    lo = hi = None
    lo_incl = hi_incl = None
    for op, num in parts:
        v = float(num)
        v = int(v) if v == int(v) else v
        if op in ('>', '>='):
            lo, lo_incl = v, (op == '>=')
        elif op in ('<', '<='):
            hi, hi_incl = v, (op == '<=')
    if lo is None and hi is None:
        return None
    return (axis, lo, lo_incl, hi, hi_incl)


def parse_block(lines, inherited=None):
    u"""递归解析一个块 → [(conds:list, goto:str, ent:int|None)]。

    ★★★ 为什么必须递归（本轮最贵的一条）
    ------------------------------------
    `RE_GOTO.search()` 只取**第一个** goto。原作里这种形态很常见：

        if (x > 600)
        {
            if (global.plot < 120) { room_goto(room_dw_mansion_darkbulb_2); }
            else                   { room_goto(room_dw_mansion_dining_a); }
        }

    只取第一个会把 **else 分支整条吞掉**。后果是：第169轮那 10 条「表里有、
    GML 没有」的路由**全是假问题** —— 它们本来就写在 else 里，是我这层解析
    看不见，不是它造错。**差点因此误删 10 条正确数据。**
    """
    out = []
    ent = inherited
    i = 0
    while i < len(lines):
        t = lines[i].strip()
        m_if = RE_XIF.match(t) if t.startswith('if') else None
        if m_if and 'room ==' not in t:
            cond = m_if.group(1)
            body, nxt = block_after(lines, i)
            if body is not None:
                for c2, g2, e2 in parse_block(body, ent):
                    out.append(([cond] + c2, g2, e2))
                j = nxt
                while j < len(lines) and not lines[j].strip():
                    j += 1
                if j < len(lines) and lines[j].strip().startswith('else'):
                    ebody, enxt = block_after(lines, j)
                    if ebody is not None:
                        for c2, g2, e2 in parse_block(ebody, ent):
                            out.append((['!(%s)' % cond] + c2, g2, e2))
                        i = enxt
                        continue
                i = nxt
                continue
        m_ent = RE_ENT.search(t)
        if m_ent:
            ent = int(m_ent.group(1))
        m_g = RE_GOTO.search(t)
        if m_g:
            out.append(([], m_g.group(1), ent))
        i += 1
    return out


def classify_block(body, default_ent):
    u"""→ (kind, branches[], digest)。

    `kind` 的语义（决定「这条能不能按门实例精确定位」）：
      · `uncond`    —— 无条件、唯一一条：一房一门，1:1
      · `pos`       —— 只受 x/y 位置约束：**可以**按门实例坐标精确还原
      · `pos_state` —— 位置 + 运行状态（`plot` / `flag` / `extflag`）混合：
                       同一扇门可能去多个地方，只能取位置那层约束
      · `state`     —— 只受运行状态约束：**不是「哪一扇门」的问题**，不猜
    """
    text = '\n'.join(body)
    raw = parse_block(body, default_ent)
    brs = []
    for conds, goto, ent in raw:
        pos = [c for c in conds if axis_range_of(c)]
        state = [c for c in conds if not axis_range_of(c)]
        rng = axis_range_of(pos[0]) if len(pos) == 1 else None
        if not pos:
            kind = 'state'
        elif len(pos) == 1 and not state:
            kind = 'pos'
        else:
            kind = 'pos_state'
        brs.append({
            'kind': kind,
            'axis': rng[0] if rng else None,
            'cond': ' && '.join(conds) if conds else None,
            'lo': rng[1] if rng else None, 'lo_incl': rng[2] if rng else None,
            'hi': rng[3] if rng else None, 'hi_incl': rng[4] if rng else None,
            'ent': ent, 'to': goto,
            'pos_conds': pos, 'state_conds': state,
        })
    if not brs:
        return 'empty', [], text.strip()[:120]
    kinds = set(b['kind'] for b in brs)
    if kinds == {'state'} and len(brs) == 1 and not brs[0]['cond']:
        kind = 'uncond'
        brs[0]['kind'] = 'uncond'
    elif kinds == {'pos'}:
        kind = 'pos'
    elif kinds == {'state'}:
        kind = 'state'
    else:
        kind = 'mixed'
    return kind, brs, text.strip()[:120]


def _side_effects(stext):
    u"""分支体里除 goto / entrance 之外的副作用（flag 赋值等）—— 只记录，不实现。"""
    out = []
    for ln in stext.replace('\r', '').split('\n'):
        t = ln.strip()
        if not t or t in ('{', '}') or '{' in t or '}' in t:
            continue
        if 'room_goto' in t or 'global.entrance' in t or t.startswith('var '):
            continue
        if t.startswith('if ') or t.startswith('if('):
            continue          # 条件行本身不算副作用
        out.append(t)
    return out


def main():
    ev = {'note': u'第170轮 · W 门 GML 源码解析（房间 → 分支）', 'chapters': {}}
    bad = 0
    for ch in ('ch1', 'ch2', 'ch3', 'ch4', 'ch5'):
        names = load_room_names(ch)
        chd = {}
        for obj, code in sorted(CODES.items()):
            p = os.path.join(GMLROOT, ch, 'CodeEntries', code + '.gml')
            if not os.path.exists(p):
                print(u'[FAIL] 缺 %s' % p)
                bad += 1
                continue
            lines = read_lines(p)
            default_ent = RE_ENT.search('\n'.join(lines))
            default_ent = int(default_ent.group(1)) if default_ent else None
            rooms = {}
            for room, body, _ln in top_blocks(lines):
                kind, brs, digest = classify_block(body, default_ent)
                rid = names.index(room) if room in names else None
                for b in brs:
                    t = b['to']
                    b['to_id'] = names.index(t) if t in names else (
                        int(t) if t.isdigit() else None)
                rooms[room] = {'room_id': rid, 'kind': kind,
                               'default_entrance': default_ent,
                               'branches': brs, 'body_digest': digest}
            chd[obj] = {'gml': code, 'rooms': rooms}
        ev['chapters'][ch] = chd

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    text = json.dumps(ev, ensure_ascii=False, indent=1)
    io.open(OUT, 'wb').write(text.replace('\n', '\r\n').encode('utf-8'))

    print(u'== 各章各对象：房间数 / 分支类型分布 ==')
    for ch, chd in ev['chapters'].items():
        for obj, d in sorted(chd.items()):
            rs = d['rooms']
            import collections
            c = collections.Counter(v['kind'] for v in rs.values())
            nb = sum(len(v['branches']) for v in rs.values())
            print(u'  %-4s %-20s 房间 %-4d 分支 %-4d %r'
                  % (ch, obj, len(rs), nb, dict(c)))
    # 只报「一房多分支」的（这才是本轮要处理的）
    print()
    print(u'== 一房多分支（原作确实分流的）==')
    n = 0
    for ch, chd in ev['chapters'].items():
        for obj, d in sorted(chd.items()):
            for room, v in sorted(d['rooms'].items()):
                if len(v['branches']) < 2:
                    continue
                n += 1
                print(u'  %-4s %-20s %-34s %-8s' % (ch, obj, room, v['kind']))
                for b in v['branches']:
                    if b['kind'] == 'pos':
                        print(u'        %s%s%-6s, %-6s%s%s ent=%-3s -> %-40s'
                              % (b['axis'], '[' if b['lo_incl'] else '(',
                                 b['lo'] if b['lo'] is not None else '-inf',
                                 b['hi'] if b['hi'] is not None else '+inf',
                                 ']' if b['hi_incl'] else ')',
                                 '', b['ent'], b['to']))
                    else:
                        print(u'        %-9s cond=%-46s -> %s'
                              % (b['kind'], (b['cond'] or '')[:46], b['to']))
    print()
    print(u'一房多分支共 %d 处' % n)
    print(u'落盘 %s (%d B)' % (OUT, os.path.getsize(OUT)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
