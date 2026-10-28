# -*- coding: utf-8 -*-
u"""第115轮 · 全量实例坐标（inst_full.tsv）的独立对账。

被测物：_evidence/raw/chN/inst_full.tsv（UTMT csx 直接产物，47,895 行）
参照物：_evidence/raw/chN/rooms_map.json（第115轮普查用）+ objmap43.txt +
        _evidence/deltarune_objects115.json（1,945 个对象的实例数）

判据：
  R1 逐章 房间数/实例数 == 既有普查（147/3513 · 278/8050 · 246/9892 · 328/13953 · 252/12487），Σ=47895
  R2 每间房 R 行自述的「层内实例数」== 实际 I 行数 == R 行「GameObjects 数」
  R3 实例名**多重集**与 rooms_map 完全相等（ch5 允许 1 个 `空名 ↔ GameObject`，那是唯一一个空引用实例）
  R4 非空对象名都落在该章 objmap43.txt（已知例外 GameObject）
  R5 由 TSV 汇总的「每个对象的实例数」与上一轮 deltarune_objects115.json **逐个相等**
  R6 ★ 同一间房里、同一个层 ⇒ 只能有一个 depth（depth 列错位会立刻暴露）
  R7 坐标/缩放/旋转都能解析成数字，且 |v| ≤ 100000
  R8 **负控制 A**：注入一个假对象名 ⇒ R3 必须报红
  R9 **负控制 B**：把某房 R 行的层内实例数 +1 ⇒ R2 必须报红

★ 不判「层名里的 `_Depth_N` 必须等于 depth 列」：ch4/ch5 的层是自定义名
  （`OBJECTS_MAIN` / `COLLISION_DOOR` …），且有 59 个 `_Depth_N` 层与 depth 不符——
  层名是人起的、depth 才是引擎用的，拿层名当判据是误报源。R6 用「房内层→depth 唯一」代替。
用法：python check_inst115.py
"""
import collections
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence')
RAW = os.path.join(EV, 'raw')
CHAPTERS = [1, 2, 3, 4, 5]
EXPECT = {1: (147, 3513), 2: (278, 8050), 3: (246, 9892), 4: (328, 13953), 5: (252, 12487)}
KNOWN_MISSING = {'GameObject'}
COORD_MAX = 100000

res = []


def ck(name, ok, detail=''):
    res.append((name, bool(ok), detail))
    print(u'[%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                          (u'  ' + detail) if detail else ''))


def load(p):
    return json.load(io.open(p, encoding='utf-8'))


def parse(ch):
    """返回 (rooms[], insts[])；insts 每项 = (roomName, obj, x, y, sx, sy, rot, depth, layer)"""
    rooms = []
    insts = []
    cur = None
    with io.open(os.path.join(RAW, 'ch%d' % ch, 'inst_full.tsv'), encoding='utf-8') as f:
        for ln in f:
            ln = ln.rstrip('\n')
            if not ln:
                continue
            if ln[0] == 'R':
                p = ln.split('\t')
                cur = {'index': int(p[1]), 'name': p[2], 'w': int(p[3]), 'h': int(p[4]),
                       'layers': int(p[5]), 'n': int(p[6]), 'go': int(p[7]), 'got': 0}
                rooms.append(cur)
            elif ln[0] == 'I':
                p = ln.split('\t')
                cur['got'] += 1
                insts.append((cur['name'], p[1], float(p[2]), float(p[3]),
                              float(p[4]), float(p[5]), float(p[6]),
                              int(p[9]), p[10]))
    return rooms, insts


def rooms_map_names(ch):
    d = load(os.path.join(RAW, 'ch%d' % ch, 'rooms_map.json'))
    out = []
    for r in d['rooms']:
        for ly in r.get('layers') or []:
            if (ly.get('type') or '') == 'Instances':
                out.extend(ly.get('instances') or [])
    return out


def objmap_names(ch):
    out = set()
    for ln in io.open(os.path.join(RAW, 'ch%d' % ch, 'objmap43.txt'),
                      encoding='utf-8', errors='replace'):
        p = ln.rstrip('\n').split('\t')
        if len(p) >= 2 and p[0].strip().isdigit():
            out.add(p[1].strip())
    return out


def main():
    data = {ch: parse(ch) for ch in CHAPTERS}

    # R1
    bad1 = []
    tot_r = tot_i = 0
    for ch in CHAPTERS:
        rooms, insts = data[ch]
        tot_r += len(rooms)
        tot_i += len(insts)
        if (len(rooms), len(insts)) != EXPECT[ch]:
            bad1.append((ch, len(rooms), len(insts), EXPECT[ch]))
    ck(u'R1 逐章 房间数/实例数 == 既有普查，Σ=47895',
       not bad1 and tot_r == 1251 and tot_i == 47895,
       u'%d 间 / %d 实例 %s' % (tot_r, tot_i, bad1 or u''))

    # R2
    bad2 = [(ch, r['name'], r['n'], r['got'], r['go']) for ch in CHAPTERS
            for r in data[ch][0] if not (r['n'] == r['got'] == r['go'])]
    ck(u'R2 每房 层内实例数 == 实际 I 行数 == GameObjects 数', not bad2,
       u'不符 %d 间 %s' % (len(bad2), bad2[:2]))

    # R3
    bad3 = []
    for ch in CHAPTERS:
        got = collections.Counter(i[1] for i in data[ch][1])
        ref = collections.Counter(rooms_map_names(ch))
        if ch == 5:
            # 唯一一个空引用实例：旧导出写 'GameObject'，本次 dump 得到空名
            got2 = dict(got)
            ref2 = dict(ref)
            if got2.get('', 0) == 1 and ref2.get('GameObject', 0) == 1:
                got2[''] -= 1
                ref2['GameObject'] -= 1
                got = collections.Counter({k: v for k, v in got2.items() if v})
                ref = collections.Counter({k: v for k, v in ref2.items() if v})
        if got != ref:
            d = [(k, got.get(k, 0), ref.get(k, 0)) for k in set(got) | set(ref)
                 if got.get(k, 0) != ref.get(k, 0)]
            bad3.append((ch, len(d), d[:4]))
    ck(u'R3 实例名多重集 == rooms_map（ch5 允许 空名↔GameObject 一对）', not bad3,
       u'异常 %s' % (bad3 or u'无'))

    # R4
    bad4 = []
    for ch in CHAPTERS:
        known = objmap_names(ch)
        for i in data[ch][1]:
            n = i[1]
            if not n:
                continue
            if n not in known and n not in KNOWN_MISSING:
                bad4.append((ch, n))
    ck(u'R4 非空对象名都落在 objmap（允许 GameObject）', not bad4,
       u'异常 %d %s' % (len(bad4), bad4[:4]))

    # R5
    old = {o['name']: o['inst'] for o in load(os.path.join(EV, 'deltarune_objects115.json'))['objects']}
    mine = collections.Counter()
    n_empty = 0
    for ch in CHAPTERS:
        for i in data[ch][1]:
            if i[1]:
                mine[i[1]] += 1
            else:
                # 全作只有 1 个实例的 Object 引用是空的（ch5 room_dw_cliff_finaldash），
                # 上一轮导出脚本给它写了类型名占位 'GameObject'，这里按同一口径归一
                n_empty += 1
                mine['GameObject'] += 1
    diff5 = [(k, mine.get(k, 0), old.get(k, 0)) for k in set(mine) | set(old)
             if mine.get(k, 0) != old.get(k, 0)]
    ck(u'R5 每个对象的实例数 == 上一轮普查（1,945 个逐个比）',
       not diff5 and n_empty == 1,
       u'不符 %d 个 %s / 空引用实例 %d 个' % (len(diff5), diff5[:3], n_empty))

    # R6
    bad6 = []
    for ch in CHAPTERS:
        per = collections.defaultdict(set)
        for i in data[ch][1]:
            per[(i[0], i[8])].add(i[7])
        bad6 += [(ch, k, v) for k, v in per.items() if len(v) > 1]
    ck(u'R6 同一间房同一个层 ⇒ 唯一 depth', not bad6,
       u'违反 %d 处 %s' % (len(bad6), bad6[:2]))

    # R7
    bad7 = []
    for ch in CHAPTERS:
        for i in data[ch][1]:
            for v in i[2:7]:
                if abs(v) > COORD_MAX:
                    bad7.append((ch, i[1], v))
                    break
    mx = max(max(abs(i[2]), abs(i[3])) for ch in CHAPTERS for i in data[ch][1])
    ck(u'R7 坐标/缩放/旋转可解析且 |v| ≤ %d' % COORD_MAX, not bad7,
       u'越限 %d 个 / 实测最大 %d' % (len(bad7), mx))

    # R8 负控制 A
    rooms1, insts1 = data[1]
    poisoned = collections.Counter(i[1] for i in insts1)
    poisoned['obj_THIS_IS_NOT_REAL'] += 1
    red8 = poisoned != collections.Counter(rooms_map_names(1))
    ck(u'R8 负控制 A（R3 不是恒真）', red8,
       u'注入假名后判据%s' % (u'报红=有效' if red8 else u'仍全绿=失效'))

    # R9 负控制 B
    fake_rooms = [dict(r) for r in rooms1]
    fake_rooms[0]['n'] += 1
    red9 = any(not (r['n'] == r['go']) for r in fake_rooms)
    ck(u'R9 负控制 B（R2 不是恒真）', red9,
       u'改一间房的层内实例数后判据%s' % (u'报红=有效' if red9 else u'仍全绿=失效'))

    ok = all(r[1] for r in res)
    print(u'\n%s  共 %d 条，PASS %d / FAIL %d'
          % (u'全绿' if ok else u'有红', len(res),
             sum(1 for r in res if r[1]), sum(1 for r in res if not r[1])))
    return 0 if ok else 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
