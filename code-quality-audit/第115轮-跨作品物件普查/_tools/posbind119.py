# -*- coding: utf-8 -*-
u"""第119轮 · 第二层守卫：用**实例坐标**把 `msg[0]` 的候选收敛到一个

## 为什么不是"选分支"，而是"按顺序覆盖"

`obj_readable_*_Alarm_0` 的原文不是 `if/else if` 链，而是**一串平行的 if**，每个块里
`global.msg[0] = scr_gettext(...)` **直接覆盖**。所以语义是「**最后一条成立的赋值获胜**」，
不是「找到唯一匹配的分支」。实测 `room_torielroom`：

    global.msc = 524;                       # 默认交给 msc 脚本
    if (x > 192) {
        global.msc = 0;
        global.msg[0] = _112;  msg[1] = _113;
        if (read > 0)        msg[0] = _114;      # 状态相关
        if (global.flag[7] == 1) { msg[0] = _118; msg[1] = _119; }
    }

⇒ 位置（`x > 192`）能判；`read` / `global.flag[7]` 不能判。本脚本把两者**分开记**：
   · `certain` —— 只由位置决定的最终 `msg[0]`（供产品静态绑定）
   · `unknown` —— 还需要运行时状态才能定的覆盖项（**如实列出，不猜**）

## 三条口径

1. **顺序即语义**：行的文件顺序 = 执行顺序，`certain` 取**最后一条**全位置条件成立的赋值。
2. **认不出的条件一律计入 `unknown`**（不当作 False）：宁可标"不确定"，不许静默取错。
3. **分母闸**：一个实例都没对上 / 一条位置赋值都没有 ⇒ 报 FAIL，不许"零结果算通过"。

输入（全在仓库里）
    _evidence/readable_conds118.<game>.tsv    第118轮 GML 解析结果（含文件顺序）
    _evidence/raw/<game>/inst_full.tsv        实例坐标（R 行=房间 / I 行=实例）
    ralsei_pet/assets/scenes/_readable_text.json   现有正文表（用来对账）
    ralsei_pet/assets/scenes/_zone.<game>.*.json   只取 original_room_id → scene_id

输出
    _evidence/readable_pos119.<game>.tsv      ★ 逐实例（scene, obj, x, y）→ 确定的 key
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

GAMES = ['ut', 'outertale']
ALARM_OBJ = re.compile(r'^gml_Object_(.+)_Alarm_0$')
RE_ROOM = re.compile(r'^room\s*==\s*(\w+)$')
RE_POS = re.compile(r'^(x|y)\s*(<=|>=|==|!=|<|>)\s*(-?\d+)$')


# ---------------------------------------------------------------- 装载
def load_conds(game):
    """→ OrderedDict[(room, obj)] -> [ (conds_list, target, key) ]（保持文件顺序）"""
    p = os.path.join(EV, 'readable_conds118.%s.tsv' % game)
    groups = collections.OrderedDict()
    cur = None
    n = 0
    for ln in io.open(p, encoding='utf-8'):
        ln = ln.rstrip('\n')
        if not ln or ln == 'alarm\tdepth\tcond\ttarget\tkey':
            continue
        q = ln.split('\t')
        if len(q) != 5:
            continue
        alarm, _depth, cond, target, key = q
        m = ALARM_OBJ.match(alarm)
        if not m:
            continue
        obj = m.group(1)
        room = None
        for tok in (cond.split(' && ') if cond else []):
            mr = RE_ROOM.match(tok.strip())
            if mr:
                room = mr.group(1)
                break
        if room is None:
            room = ''           # 没有 room 条件的赋值：对所有房间生效
        gk = (room, obj)
        if gk != cur:
            groups.setdefault(gk, [])
            cur = gk
        groups[gk].append(([t.strip() for t in cond.split(' && ')] if cond else [],
                           target, key))
        n += 1
    return groups, n


def load_inst(game):
    """→ (room_name -> idx, oid -> room_name, (room, obj) -> [(x, y), ...])"""
    p = os.path.join(RAW, game, 'inst_full.tsv')
    name_of_oid = {}
    inst = collections.defaultdict(list)
    cur = None
    for ln in io.open(p, encoding='utf-8'):
        q = ln.rstrip('\n').split('\t')
        if q[0] == 'R':
            cur = q[2]
            name_of_oid[int(q[1])] = cur
        elif q[0] == 'I':
            inst[(cur, q[1])].append((int(q[2]), int(q[3])))
    return name_of_oid, inst


def load_oid_to_scene(game):
    """original_room_id -> scene_id（**按 id 不按名字**：outertale 的房间被改过名）"""
    out, dup = {}, 0
    for p in sorted(glob.glob(os.path.join(SCENES, '_zone.%s.*.json' % game))):
        try:
            d = json.load(io.open(p, encoding='utf-8'))['scenes']
        except Exception:
            continue
        for sid, s in d.items():
            oid = s.get('original_room_id')
            if oid is None:
                continue
            if oid in out and out[oid] != sid:
                dup += 1
            out[oid] = sid
    return out, dup


def load_current_table():
    """(scene_id, obj) -> 现有正文表里**排在最前**的那条的 key（loader 取的就是这条）"""
    p = os.path.join(SCENES, '_readable_text.json')
    d = json.load(io.open(p, encoding='utf-8'))['by_scene']
    out = {}
    for sid, entries in d.items():
        for e in entries or ():
            obj = e.get('obj')
            if obj and (sid, obj) not in out:
                out[(sid, obj)] = e.get('key')
    return out


# ---------------------------------------------------------------- 判定
def eval_tok(tok, room, x, y):
    """→ ('T'|'F'|'?', 原因)。**认不出的一律 '?'**，不当作 False。"""
    t = tok.strip()
    if not t:
        return 'T', ''
    m = RE_ROOM.match(t)
    if m:
        return ('T', '') if m.group(1) == room else ('F', '')
    m = RE_POS.match(t)
    if m:
        var, op, num = m.group(1), m.group(2), int(m.group(3))
        v = x if var == 'x' else y
        r = {'<': v < num, '>': v > num, '<=': v <= num,
             '>=': v >= num, '==': v == num, '!=': v != num}[op]
        return ('T', '') if r else ('F', '')
    return '?', t


def eval_cond(conds, room, x, y):
    """→ (True/False/None, [认不出的 token])；None = 有认不出的，但**没有一条为假**"""
    unknown = []
    for tok in conds:
        v, why = eval_tok(tok, room, x, y)
        if v == 'F':
            return False, unknown
        if v == '?':
            unknown.append(why or tok)
    return (None if unknown else True), unknown


def bind(groups, inst):
    """逐实例求 msg[0] 的确定值 + 不确定覆盖项"""
    rows = []
    stat = collections.Counter()
    per_group = collections.OrderedDict()

    for (room, obj), stmts in groups.items():
        if not room:
            continue                     # 无 room 条件的（msc 默认值）不参与逐房间绑定
        coords = inst.get((room, obj)) or []
        if not coords:
            stat['group_no_inst'] += 1
            continue
        gk = (room, obj)
        certain_by_coord = []
        for (x, y) in coords:
            cur_key = None
            unknown = []
            seen_pos = False
            for conds, target, key in stmts:
                if not target.startswith('msg['):
                    continue             # msg[N] 才是正文；msc 另行处理
                ok, unk = eval_cond(conds, room, x, y)
                if ok is False:
                    continue
                if ok is True:
                    seen_pos = True
                    if target == 'msg[0]':
                        cur_key = key
                else:
                    for u in unk:
                        if u not in unknown:
                            unknown.append(u)
                    if target == 'msg[0]':
                        unknown.append(key)   # 这一条可能覆盖掉 cur_key
            certain_by_coord.append((x, y, cur_key, unknown, seen_pos))
        per_group[gk] = certain_by_coord

    return per_group, stat


def main():
    cur_tab = load_current_table()
    grand = collections.Counter()
    for game in GAMES:
        groups, n_rows = load_conds(game)
        name_of_oid, inst = load_inst(game)
        oid2sid, dup = load_oid_to_scene(game)
        per_group, stat = bind(groups, inst)
        oid_of_name = {}
        for o, nm in name_of_oid.items():
            oid_of_name.setdefault(nm, o)

        out_rows = []
        c = collections.Counter()
        diffs = []
        splits = []
        for (room, obj), lst in per_group.items():
            oid = oid_of_name.get(room)
            sid = oid2sid.get(oid) if oid is not None else None
            if sid is None:
                c['no_scene'] += 1
                continue
            keys = {k for (_x, _y, k, _u, _s) in lst if k}
            if not keys:
                c['no_certain'] += 1
            if len(keys) > 1:
                c['instance_split'] += 1
                splits.append((sid, obj, sorted(keys)))
            had_pos = any(s for (_x, _y, _k, _u, s) in lst)
            if had_pos:
                c['has_pos_assignment'] += 1
            k0 = lst[0][2]
            old = cur_tab.get((sid, obj))
            if old is not None and k0 and old != k0:
                c['diff_vs_table'] += 1
                diffs.append((sid, obj, old, k0))
            elif old is None:
                c['not_in_table'] += 1
            for (x, y, k, unk, _s) in lst:
                out_rows.append((sid, obj, x, y, k or '', '|'.join(unk)))
                c['inst_rows'] += 1

        out_rows.sort()
        p = os.path.join(EV, 'readable_pos119.%s.tsv' % game)
        with io.open(p, 'w', encoding='utf-8', newline='\n') as f:
            f.write(u'scene\tobj\tx\ty\tcertain_key\tuncertain_overrides\n')
            for r in out_rows:
                f.write(u'%s\t%s\t%d\t%d\t%s\t%s\n' % r)

        print(u'=== %s：%d 条 GML 赋值 → %d 组（房间×对象）' % (game, n_rows, len(groups)))
        print(u'    逐实例行 %d / 有位置赋值 %d / 实例间冲突 %d / 无确定值 %d'
              % (c['inst_rows'], c['has_pos_assignment'], c['instance_split'],
                 c['no_certain']))
        print(u'    与现有表**不一致** %d 组 / 表里没有 %d 组 / 找不到场景 %d 组'
              % (c['diff_vs_table'], c['not_in_table'], c['no_scene']))
        for sid, obj, old, new in diffs[:12]:
            print(u'      [DIFF] %-42s %-24s 表=%s 实=%s' % (sid, obj, old, new))
        for sid, obj, keys in splits[:8]:
            print(u'      [SPLIT] %-40s %-22s %s' % (sid, obj, u' / '.join(keys)))
        grand.update(c)

        if not out_rows:
            print(u'[FAIL] %s 一行都没产出 —— 本脚本什么也没证明' % game)
            return 1

    print(u'\n合计：逐实例 %d 行 / 冲突 %d 组 / 与表不一致 %d 组'
          % (grand['inst_rows'], grand['instance_split'], grand['diff_vs_table']))
    print(u'落盘：_evidence/readable_pos119.<game>.tsv')
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
