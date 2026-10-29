# -*- coding: utf-8 -*-
"""对账 cross_semantics115.json（本轮第 14 节）。

★ 每条"门通向哪"都要能回验：exact 门的 `via`（那段 GML 的 code 名）里必须真的出现
  这个门对象的名字，且 (room, to_room) 必须是真边。回验不了的不许算 resolved。

用法
----
    python check_semantics115.py
    python check_semantics115.py -v
"""
import ast
import copy
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence')

KEYS = ['ut', 'uty', 'outertale']
N_INST = 36136          # 三款实例总数（与 §11 独立相符）
EXPECT = {              # doors, resolved_exact, resolved_inferred, unknown
    'ut': (1299, 239, 309, 749),
    'uty': (523, 0, 0, 523),
    'outertale': (1367, 256, 324, 785),
}

FAILS = []


def check(name, ok, detail=''):
    if ok:
        return True
    FAILS.append((name, detail))
    return False


def load(fn):
    with io.open(os.path.join(EV, fn), encoding='utf-8') as f:
        return json.load(f)


def in_code(code, obj):
    """独立实现（不复用被测脚本）：对象名在 code 里按边界出现"""
    return re.search(r'(^|_)' + re.escape(obj) + r'(_|$)', code or '') is not None


def kinds_of(path):
    """从源码里用 AST 取 KINDS 的 key 列表（不执行文件，也不怕注释里的同名字符串）"""
    tree = ast.parse(io.open(path, encoding='utf-8').read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', '') == 'KINDS':
            return [e.elts[0].value for e in node.value.elts]
    return None


def m4_exact_doors(d, ex):
    """每条 provenance=exact 的门：真边存在 + code 回验通过"""
    bad = []
    for g in KEYS:
        edges = set((e['src'], e['dst']) for e in ex[g]['edges'])
        for dd in d['doors']:
            if dd['game'] != g or dd['provenance'] != 'exact':
                continue
            if (dd['room'], dd['to_room']) not in edges:
                bad.append(('NO_EDGE', g, dd['room'], dd['to_room']))
            elif not in_code(dd['via'], dd['obj']):
                bad.append(('CODE_MISMATCH', g, dd['obj'], dd['via']))
    return bad


def m5_inferred_doors(d, inf):
    bad = []
    for g in KEYS:
        edges = set((e['src'], e['dst']) for e in inf[g]['edges'])
        for dd in d['doors']:
            if dd['game'] != g or dd['provenance'] != 'inferred':
                continue
            if (dd['room'], dd['to_room']) not in edges:
                bad.append(('NO_INF_EDGE', g, dd['room'], dd['to_room']))
            elif dd.get('via') != dd['obj']:
                bad.append(('VIA_MISMATCH', g, dd['obj'], dd.get('via')))
    return bad


def m3_accounting(d):
    """resolved + ambiguous + unknown == 门实例数；且三个计数与实测一致"""
    bad = []
    for g in KEYS:
        st = d['door_stat'][g]
        tot = st.get('doors', 0)
        s = (st.get('resolved_exact', 0) + st.get('resolved_inferred', 0)
             + st.get('ambiguous', 0) + st.get('unknown', 0))
        if s != tot:
            bad.append((g, 'SUM', s, tot))
        got = (tot, st.get('resolved_exact', 0), st.get('resolved_inferred', 0),
               st.get('unknown', 0))
        if got != EXPECT[g]:
            bad.append((g, 'EXPECT', got, EXPECT[g]))
    return bad


def m2_conserve(d):
    """分类守恒：三款所有 kind 合计 == 实例总数（互斥穷尽）"""
    tot = sum(d['by_kind'].values())
    return [] if tot == N_INST else [('SUM', tot, N_INST)]


def m6_same_kinds():
    a = kinds_of(os.path.join(HERE, 'points115.py'))
    b = kinds_of(os.path.join(HERE, 'semantic115.py'))
    if a is None or b is None:
        return [('AST_FAIL', a, b)]
    return [] if a == b else [('KINDS_DIFF', a, b)]


def main(argv):
    d = load('cross_semantics115.json')
    ex = load('conn115.json')
    inf = load('conn_inferred115.json')
    verbose = '-v' in argv

    empty = [g for g in KEYS if d['door_stat'].get(g, {}).get('doors', 0) <= 0]
    if check('M1 分母闸', not empty, '门实例为 0 的作品: %s' % empty):
        print('[PASS] M1 分母闸：三款门实例都非零（1299 / 523 / 1367）')

    bad = m2_conserve(d)
    if check('M2 分类守恒', not bad, str(bad)):
        print('[PASS] M2 分类守恒：所有 kind 合计 == 36,136（互斥穷尽）')

    bad = m3_accounting(d)
    if check('M3 门的账对得上', not bad, str(bad)):
        print('[PASS] M3 resolved+ambiguous+unknown == 门实例数，且与实测逐值一致')

    bad = m4_exact_doors(d, ex)
    if check('M4 exact 门可回验', not bad, str(bad[:5])):
        print('[PASS] M4 每条 exact 门：真边存在，且 code 里真的出现该对象名')

    bad = m5_inferred_doors(d, inf)
    if check('M5 inferred 门可回验', not bad, str(bad[:5])):
        print('[PASS] M5 每条 inferred 门：候选边存在，且 via == 对象名')

    bad = m6_same_kinds()
    if check('M6 与 Deltarune 同口径', not bad, str(bad)):
        print('[PASS] M6 分类口径与 points115.py 的 KINDS 逐项相同（AST 比对，不执行源码）')

    # ---- 负控制
    dd = copy.deepcopy(d)
    t = next(x for x in dd['doors'] if x['provenance'] == 'exact')
    t['to_room'] = 9999
    if check('M7 负控制A：门目标改成 9999 => M4 报红', bool(m4_exact_doors(dd, ex))):
        print('[PASS] M7 负控制A：把一条 exact 门的 to_room 改成 9999 => M4 报红')

    dd = copy.deepcopy(d)
    t = next(x for x in dd['doors'] if x['provenance'] == 'exact')
    t['via'] = 'gml_Object_obj_完全没有_Alarm_2'
    if check('M8 负控制B：code 与对象不匹配 => M4 报红', bool(m4_exact_doors(dd, ex))):
        print('[PASS] M8 负控制B：把 via 换成不含该对象名的 code => M4 报红')

    dd = copy.deepcopy(d)
    dd['door_stat']['ut']['unknown'] += 5
    if check('M9 负控制C：unknown 虚报 => M3 报红', bool(m3_accounting(dd))):
        print('[PASS] M9 负控制C：把 ut 的 unknown +5 => M3 报红')

    dd = copy.deepcopy(d)
    dd['by_kind']['door'] += 1
    if check('M10 负控制D：分类总数溢出 => M2 报红', bool(m2_conserve(dd))):
        print('[PASS] M10 负控制D：把 door 计数 +1 => M2 报红')

    if verbose:
        for g in KEYS:
            st = d['door_stat'][g]
            print('  [%s] doors=%d exact=%d inferred=%d ambig=%d unknown=%d'
                  % (g, st['doors'], st.get('resolved_exact', 0),
                     st.get('resolved_inferred', 0), st.get('ambiguous', 0),
                     st.get('unknown', 0)))

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
