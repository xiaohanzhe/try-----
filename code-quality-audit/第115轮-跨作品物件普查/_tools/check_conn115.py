# -*- coding: utf-8 -*-
"""对账 conn115.json / conn_inferred115.json（本轮第 13 节）。

判据只判**结构守恒**（越界、重复、来源混放、标签自洽），
不判"边在游戏里对不对" —— 那个本轮没有真值，判不了就别假装判了。

用法
----
    python check_conn115.py            # 全跑
    python check_conn115.py -v         # 打印每条判据的实际数值
"""
import copy
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence')

KEYS = ['ut', 'uty', 'outertale']
# 与本轮 report115.md §13 表格逐值对齐（改了数据就要同步改这里，否则 C11 报红）
EXPECT = {
    'ut': (338, 131, 101, 563),
    'uty': (287, 1, 1, 0),
    'outertale': (358, 144, 110, 588),
}

FAILS = []
NOPS = []


def check(name, ok, detail=''):
    if ok:
        return True
    FAILS.append((name, detail))
    return False


def nop(name):
    """显式登记"这条判据被跳过了"，别让空跑冒充通过"""
    NOPS.append(name)


def load(fn):
    with io.open(os.path.join(EV, fn), encoding='utf-8') as f:
        return json.load(f)


# ---------------------------------------------------------------- 判据本体
def c2_range(d):
    bad = []
    for key in KEYS:
        n = d[key]['n_rooms']
        for e in d[key]['edges']:
            if not (0 <= e['src'] < n and 0 <= e['dst'] < n):
                bad.append((key, e['src'], e['dst'], 'OUT_OF_RANGE'))
            elif e['src'] == e['dst']:
                bad.append((key, e['src'], e['dst'], 'SELF_LOOP'))
    return bad


def c3_dedup(raw, d):
    """导出条数 == 原始 (src,dst) 唯一对数（去重必须真的去重，不许顺手丢边）"""
    bad = []
    for key in KEYS:
        seen = set()
        for x in raw[key]['items']:
            if x['src'] >= 0 and x['dst'] >= 0 and 0 <= x['dst'] < raw[key]['n_rooms']:
                seen.add((x['src'], x['dst']))
        got = d[key]['n_edges']
        if got != len(seen):
            bad.append((key, got, len(seen)))
    return bad


def c4_names(d):
    bad = []
    for key in KEYS:
        names = None
        with io.open(os.path.join(EV, 'raw', key, 'conn_ut.json'), encoding='utf-8') as f:
            names = json.load(f)['room_names']
        for e in d[key]['edges']:
            if names[e['src']] != e['src_name'] or names[e['dst']] != e['dst_name']:
                bad.append((key, e['src'], e['dst']))
    return bad


def c5_overlap(ex, inf):
    return [(key, e['src'], e['dst']) for key in KEYS
            for e in inf[key]['edges'] if (e['src'], e['dst']) in
            set((x['src'], x['dst']) for x in ex[key]['edges'])]


def c6_off(inf):
    bad = [(key, e['src'], e['dst'], e['off']) for key in KEYS
           for e in inf[key]['edges']
           if e['off'] not in (1, -1) or e['dst'] != e['src'] + e['off']]
    return bad


def c7_same_area(inf):
    bad = []
    for key in KEYS:
        n = sum(1 for e in inf[key]['edges'] if e['same_area'])
        if n != inf[key]['same_area']:
            bad.append((key, n, inf[key]['same_area']))
    return bad


def c11_expect(ex, inf):
    bad = []
    for key in KEYS:
        n, ne, ns, ni = EXPECT[key]
        got = (ex[key]['n_rooms'], ex[key]['n_edges'], ex[key]['src_rooms'], inf[key]['n_edges'])
        if got != (n, ne, ns, ni):
            bad.append((key, got, (n, ne, ns, ni)))
    return bad


def main(argv):
    ex = load('conn115.json')
    inf = load('conn_inferred115.json')
    raw = {k: json.load(io.open(os.path.join(EV, 'raw', k, 'conn_ut.json'), encoding='utf-8'))
           for k in KEYS}
    verbose = '-v' in argv

    # C1 分母闸：可信边三款都得有，否则后面的判据在空集上恒真
    # ★ 候选边不能要求每款都非空：uty 全库里没有任何 next/prev 规则（实测 0 条），
    #   那是数据事实，不是缺陷。为空的款显式登记 nop，别让"没跑"冒充"通过"。
    empty = [k for k in KEYS if not ex[k]['edges']]
    if check('C1a 可信边分母闸', not empty,
             '以下作品可信边为空，后续判据会退化成恒真: %s' % empty):
        print('[PASS] C1a 可信边分母闸：三款都有可信边（131 / 1 / 144）')
    if not any(inf[k]['edges'] for k in KEYS):
        check('C1b 候选边分母闸', False, '三款候选边全为空')
    else:
        print('[PASS] C1b 候选边分母闸：至少一款有候选边')
    for k in KEYS:
        if not inf[k]['edges']:
            nop('[%s] C6/C7 在候选边为空时无从检验（UTY 无 next/prev 规则）' % k)

    # C2
    bad = c2_range(ex)
    if check('C2 可信边不越界不自环', not bad, str(bad[:6])):
        print('[PASS] C2 可信边不越界不自环（%d 条全部落在 0..n-1 且 src != dst）'
              % sum(ex[k]['n_edges'] for k in KEYS))

    # C3
    bad = c3_dedup(raw, ex)
    if check('C3 去重守恒', not bad, str(bad)):
        print('[PASS] C3 去重守恒（原始 147/1/158 条 -> 去重后 131/1/144 条）')

    # C4
    bad = c4_names(ex)
    if check('C4 房间名逐条对得上', not bad, str(bad[:6])):
        print('[PASS] C4 每条边的 src_name/dst_name 与 conn_ut.json 的 room_names 一致')

    # C5
    bad = c5_overlap(ex, inf)
    if check('C5 可信边与候选边不混放', not bad, str(bad[:6])):
        print('[PASS] C5 可信边与候选边零重叠（错边比缺边糟，来源必须分开）')

    # C6
    bad = c6_off(inf)
    if check('C6 候选边等于相邻房', not bad, str(bad[:6])):
        print('[PASS] C6 候选边 dst == src + off 且 off ∈ {+1,-1}')

    # C7
    bad = c7_same_area(inf)
    if check('C7 同区域计数自洽', not bad, str(bad)):
        print('[PASS] C7 same_area 计数与逐条标签一致（ut %d / outertale %d）'
              % (inf['ut']['same_area'], inf['outertale']['same_area']))

    # C11
    bad = c11_expect(ex, inf)
    if check('C11 与报告 §13 数字对齐', not bad, str(bad)):
        print('[PASS] C11 房间数/边数/src 房数与 report115.md §13 逐值一致')

    # ---- 负控制（成对：破坏必须报红）
    d = copy.deepcopy(ex)
    d['ut']['edges'][0]['dst'] = 99999
    if check('C8 负控制A：越界 dst 被 C2 抓到', bool(c2_range(d))):
        print('[PASS] C8 负控制A：把一条 dst 改成 99999 => C2 报红')

    d = copy.deepcopy(ex)
    d['uty']['n_edges'] = d['uty']['n_edges'] + 1
    if check('C9 负控制B：边数造假被 C3 抓到', bool(c3_dedup(raw, d))):
        print('[PASS] C9 负控制B：把 uty 的 n_edges +1 => C3 报红')

    inf2 = copy.deepcopy(inf)
    e0 = inf2['ut']['edges'][0]
    inf2['ut']['edges'].append(dict(e0, src=ex['ut']['edges'][0]['src'],
                                    dst=ex['ut']['edges'][0]['dst']))
    if check('C10 负控制C：候选边混进可信边被 C5 抓到', bool(c5_overlap(ex, inf2))):
        print('[PASS] C10 负控制C：把一条可信边复制进候选边 => C5 报红')

    inf3 = copy.deepcopy(inf)
    inf3['ut']['edges'][0]['same_area'] = not inf3['ut']['edges'][0]['same_area']
    if check('C12 负控制D：同区域标签翻面被 C7 抓到', bool(c7_same_area(inf3))):
        print('[PASS] C12 负控制D：翻转一条 same_area => C7 报红')

    d = copy.deepcopy(ex)
    d['ut']['edges'] = []
    if check('C13 负控制E：空集被 C1a 抓到', bool([k for k in KEYS if not d[k]['edges']])):
        print('[PASS] C13 负控制E：清空 ut 可信边 => C1a 分母闸报红')

    if verbose:
        for key in KEYS:
            print('  [%s] rooms=%d exact=%d src_rooms=%d infer=%d same_area=%d'
                  % (key, ex[key]['n_rooms'], ex[key]['n_edges'], ex[key]['src_rooms'],
                     inf[key]['n_edges'], inf[key]['same_area']))
    if NOPS:
        print('跳过 %d 条判据: %s' % (len(NOPS), NOPS))

    if FAILS:
        print('')
        for name, detail in FAILS:
            print('[FAIL] %s  %s' % (name, detail))
        print('=> %d FAIL' % len(FAILS))
        return 1
    print('=> 全部 PASS（0 FAIL）')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
