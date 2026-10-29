# -*- coding: utf-8 -*-
u"""第115轮 · UT / UTY / Outertale 全量实例坐标的独立对账。

被测物：_evidence/raw/{ut,uty,outertale}/inst_full.tsv（UTMT csx 直接产物）
参照物：详版 §87.11 的历史登记（ut=338 间 `room_*` / uty=287 间 `rm_*`，来自第42轮拓扑取证）
        —— 这是**独立的**外部期望，不是本脚本自己算出来的，所以能真正证伪

判据：
  U1 三份 TSV 存在且非空（分母闸：房间数>0 且 实例数>0，防「空集恒真」）
  U2 H 行自述房间数 == 实际 R 行数
  U3 R 行 8 字段 / I 行 11 字段（全量逐行，不抽样）
  U4a 每房「层内实例数」== 实际 I 行数（导出自身的一致性，必须 0 例外）
  U4b 房间 GameObjects 数与层内实例数的差异集合 == 白名单（多一处就报红）
      ⇒ UTY 的 `rm_intro` 是老格式房间：3 个实例全在
        `Compatibility_Instances_Depth_0` 层，但引擎实例表有 4 个（有 1 个没挂层）。
        这是真实特征，不是导出缺陷，所以进白名单而不是放宽成 `>=`。
  U5 ut == 338 间、uty == 287 间（与历史登记逐值相等）
  U6 房间名前缀覆盖：ut 的 `room_` ≥ 90%、uty 的 `rm_` ≥ 80%
  U7 x/y/sx/sy/rot 全量可解析且 |v| ≤ 100000
  U8 raw 件与 D:\\_wb_tmp\\dw_ut 下的工作副本 sha256 一致（副本还在时才判）
  U9  **负控制 A**：把 ut 一间房的层内实例数 +1 ⇒ U4a 必须报红
  U10 **负控制 B**：把 uty 的期望房间数写成 288 ⇒ U5 必须报红
  U11 **负控制 C**：喂空房间列表 ⇒ U4a 的分母闸必须判红（不是恒真通过）
  U12 **负控制 D**：往差异集合里塞一个白名单外的新差异 ⇒ U4b 必须报红

用法：python check_ut115.py
"""
import hashlib
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
RAW = os.path.join(ROUND, '_evidence', 'raw')
WORK = os.environ.get('DUMP_WORK_UT', r'D:\_wb_tmp\dw_ut')

KEYS = ['ut', 'uty', 'outertale']
EXPECT_ROOMS = {'ut': 338, 'uty': 287, 'outertale': None}
EXPECT_PREFIX = {'ut': ('room_', 0.90), 'uty': ('rm_', 0.80), 'outertale': None}
COORD_MAX = 100000.0
R_FIELDS = 8
I_FIELDS = 11
# 已知且已解释的「引擎实例表 > 层内实例」房间（老格式房间，实例没挂层）
GO_WHITELIST = {('uty', 'rm_intro')}

res = []


def ck(name, ok, detail=''):
    res.append((name, bool(ok), detail))
    print(u'[%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                          (u'  ' + detail) if detail else ''))


def parse(key):
    """返回 (h_rooms, rooms[], insts[], bad_r, bad_i)"""
    p = os.path.join(RAW, key, 'inst_full.tsv')
    if not os.path.isfile(p):
        return None, [], [], 0, 0
    h_rooms = None
    rooms, insts = [], []
    cur = None
    bad_r = bad_i = 0
    with io.open(p, encoding='utf-8') as f:
        for ln in f:
            ln = ln.rstrip('\n')
            if not ln:
                continue
            if ln.startswith('H\t'):
                hp = ln.split('\t')
                if len(hp) >= 3:
                    h_rooms = int(hp[1])
                continue
            if ln.startswith('R\t'):
                p2 = ln.split('\t')
                if len(p2) != R_FIELDS:
                    bad_r += 1
                    continue
                cur = {'index': int(p2[1]), 'name': p2[2], 'w': int(p2[3]), 'h': int(p2[4]),
                       'layers': int(p2[5]), 'n': int(p2[6]), 'go': int(p2[7]), 'got': 0}
                rooms.append(cur)
            elif ln.startswith('I\t'):
                p2 = ln.split('\t')
                if len(p2) != I_FIELDS:
                    bad_i += 1
                    continue
                if cur is None:
                    bad_i += 1
                    continue
                cur['got'] += 1
                insts.append({'room': cur['name'], 'obj': p2[1],
                              'x': float(p2[2]), 'y': float(p2[3]),
                              'sx': float(p2[4]), 'sy': float(p2[5]),
                              'rot': float(p2[6]), 'depth': int(p2[9]),
                              'layer': p2[10]})
    return h_rooms, rooms, insts, bad_r, bad_i


def room_errors(rooms):
    """每房 n（层内实例数）== got（实际 I 行数）；空列表返回 ['EMPTY'] 而不是空集（防恒真）"""
    if not rooms:
        return [('EMPTY', '房间列表为空，判据无从成立')]
    return [(r['name'], r['n'], r['got'])
            for r in rooms if r['n'] != r['got']]


def go_diffs(key, rooms):
    """房间 GameObjects 数 与 层内实例数 不等的房间：[(key, name, n, go)]"""
    return [(key, r['name'], r['n'], r['go']) for r in rooms if r['n'] != r['go']]


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


def main():
    data = {}
    for k in KEYS:
        data[k] = parse(k)

    # U1 分母闸
    empty = [k for k in KEYS if not data[k][1] or not data[k][2]]
    ck(u'U1 三份 TSV 非空（分母闸）', not empty,
       u'%s' % (u'空：%s' % empty if empty else
                u' '.join(u'%s=%d房/%d实例' % (k, len(data[k][1]), len(data[k][2])) for k in KEYS)))

    # U2 H 行 == R 行数
    bad2 = [(k, data[k][0], len(data[k][1])) for k in KEYS
            if data[k][0] is not None and data[k][0] != len(data[k][1])]
    ck(u'U2 H 行自述房间数 == 实际 R 行数', not bad2,
       u'不符 %s' % (bad2 or u'无'))

    # U3 字段数
    bad3 = [(k, data[k][3], data[k][4]) for k in KEYS if data[k][3] or data[k][4]]
    ck(u'U3 R 行 %d 字段 / I 行 %d 字段（全量逐行）' % (R_FIELDS, I_FIELDS), not bad3,
       u'格式异常 %s' % (bad3 or u'无'))

    # U4a 房内一致性（层内实例数 == I 行数）
    bad4 = []
    for k in KEYS:
        for e in room_errors(data[k][1]):
            bad4.append((k,) + tuple(e))
    ck(u'U4a 每房 层内实例数 == 实际 I 行数', not bad4,
       u'不符 %d 处 %s' % (len(bad4), bad4[:2] or u''))

    # U4b GameObjects 差异集合 == 白名单（多一处即报红）
    diffs = []
    for k in KEYS:
        diffs += go_diffs(k, data[k][1])
    got_names = set((d[0], d[1]) for d in diffs)
    ck(u'U4b GameObjects 差异集合 == 白名单（%d 间）' % len(GO_WHITELIST),
       got_names == GO_WHITELIST,
       u'实测差异 %d 间 %s / 白名单外新增 %s / 白名单内消失 %s'
       % (len(got_names), sorted(got_names),
          sorted(got_names - GO_WHITELIST) or u'无',
          sorted(GO_WHITELIST - got_names) or u'无'))

    # U5 与历史登记逐值相等
    bad5 = [(k, len(data[k][1]), EXPECT_ROOMS[k]) for k in KEYS
            if EXPECT_ROOMS[k] is not None and len(data[k][1]) != EXPECT_ROOMS[k]]
    ck(u'U5 ut=338 间 / uty=287 间（历史登记逐值相等）', not bad5,
       u'%s' % (u'不符 %s' % bad5 if bad5 else
                u'ut=%d uty=%d' % (len(data['ut'][1]), len(data['uty'][1]))))

    # U6 前缀覆盖
    bad6 = []
    detail6 = []
    for k in KEYS:
        pre = EXPECT_PREFIX[k]
        if pre is None or not data[k][1]:
            continue
        name, ratio = pre
        hit = sum(1 for r in data[k][1] if r['name'].startswith(name))
        actual = hit / float(len(data[k][1]))
        detail6.append(u'%s %s %.1f%%' % (k, name, actual * 100))
        if actual < ratio:
            bad6.append((k, hit, len(data[k][1]), ratio))
    ck(u'U6 房间名前缀覆盖达标', not bad6,
       u'%s %s' % (u' '.join(detail6), (u'不达标 %s' % bad6) if bad6 else u''))

    # U7 数值可解析 + 上界
    bad7 = []
    for k in KEYS:
        for i in data[k][2]:
            for f in ('x', 'y', 'sx', 'sy', 'rot'):
                if abs(i[f]) > COORD_MAX:
                    bad7.append((k, i['obj'], f, i[f]))
                    break
    mx = 0.0
    for k in KEYS:
        for i in data[k][2]:
            mx = max(mx, abs(i['x']), abs(i['y']))
    ck(u'U7 坐标/缩放/旋转可解析且 |v| ≤ %d' % int(COORD_MAX), not bad7,
       u'越限 %d 个 / 实测最大 %d' % (len(bad7), mx))

    # U8 与工作副本一致
    cmp8 = []
    bad8 = False
    for k in KEYS:
        w = os.path.join(WORK, k, 'inst_full.tsv')
        r = os.path.join(RAW, k, 'inst_full.tsv')
        if not os.path.isfile(w):
            cmp8.append((k, u'work 副本已清，跳过'))
            continue
        same = sha(w) == sha(r)
        cmp8.append((k, u'一致' if same else u'不一致!!'))
        if not same:
            bad8 = True
    ck(u'U8 raw 件与工作副本 sha256 一致', not bad8,
       u'%s' % u' '.join(u'%s:%s' % (a, b) for a, b in cmp8))

    # U9 负控制 A
    if not data['ut'][1]:
        ck(u'U9 负控制 A（U4a 不是恒真）', False, u'ut 房间为空，无法构造负控制')
    else:
        fake = [dict(r) for r in data['ut'][1]]
        fake[0]['n'] += 1
        red9 = bool(room_errors(fake))
        ck(u'U9 负控制 A（U4a 不是恒真）', red9,
           u'改一间房的层内实例数后判据%s' % (u'报红=有效' if red9 else u'仍全绿=失效'))

    # U10 负控制 B
    shifted = dict(EXPECT_ROOMS)
    shifted['uty'] = EXPECT_ROOMS['uty'] + 1
    red10 = len(data['uty'][1]) != shifted['uty']
    ck(u'U10 负控制 B（U5 不是恒真）', red10,
       u'把 uty 期望改成 %d 后判据%s' % (shifted['uty'], u'报红=有效' if red10 else u'仍全绿=失效'))

    # U11 负控制 C：分母闸
    red11 = bool(room_errors([]))
    ck(u'U11 负控制 C（空输入不会恒真通过）', red11,
       u'喂空房间列表后判据%s' % (u'报红=有效' if red11 else u'仍全绿=失效'))

    # U12 负控制 D：白名单外新增差异必须被抓到
    poisoned = set(got_names)
    poisoned.add(('ut', 'room_THIS_IS_NOT_REAL'))
    red12 = (poisoned != GO_WHITELIST)
    ck(u'U12 负控制 D（U4b 不是恒真）', red12,
       u'注入白名单外差异后判据%s' % (u'报红=有效' if red12 else u'仍全绿=失效'))

    ok = all(r[1] for r in res)
    print(u'\n%s  共 %d 条，PASS %d / FAIL %d'
          % (u'全绿' if ok else u'有红', len(res),
             sum(1 for r in res if r[1]), sum(1 for r in res if not r[1])))
    return 0 if ok else 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
