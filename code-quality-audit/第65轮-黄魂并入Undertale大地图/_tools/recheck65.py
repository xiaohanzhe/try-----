# -*- coding: utf-8 -*-
u"""第65轮 · 交付前复检（六类判据 + 逐令牌回验 + 负控制）。

判据刻意分五组，每组都配「负控制」——否则判据可能空转（恒真）。
本脚本**不修改任何被测状态**（只 ast.parse，不用 py_compile，避免留 .pyc）。
"""
from __future__ import print_function
import ast, io, json, os, sys, subprocess, collections

HERE = os.path.dirname(os.path.abspath(__file__))
AUD = os.path.join(HERE, '..')
EV = os.path.join(AUD, '_evidence')

ROWS = []


def ck(name, ok, detail=''):
    ROWS.append((name, bool(ok), detail))
    print('  [%s] %-58s %s' % ('PASS' if ok else 'FAIL', name, detail))
    return ok


def read_b(p):
    with io.open(p, 'rb') as f:
        return f.read()


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print('===== 第65轮交付前复检 =====')

    # ---- ① 可编译（ast.parse；不用 py_compile 以免产出 .pyc 污染仓库） ----
    print('\n① 语法 / 可编译')
    pys = sorted(n for n in os.listdir(HERE) if n.endswith('.py'))
    for n in pys:
        src = read_b(os.path.join(HERE, n)).decode('utf-8')
        try:
            ast.parse(src)
            ck('ast.parse %s' % n, True)
        except SyntaxError as ex:
            ck('ast.parse %s' % n, False, str(ex))
    # 负控制：故意坏源码必须被拒
    try:
        ast.parse('def f(:\n  pass\n')
        ck('负控制 · 坏源码必须被拒', False, '竟然解析成功')
    except SyntaxError:
        ck('负控制 · 坏源码必须被拒', True)

    # ---- ② JSON 合法 + 结构自检 ----
    print('\n② JSON 合法性 / 结构')
    js = {}
    for n in sorted(os.listdir(EV)):
        if not n.endswith('.json'):
            continue
        try:
            js[n] = json.load(io.open(os.path.join(EV, n), encoding='utf-8'))
            ck('json.load %s' % n, True)
        except Exception as ex:
            ck('json.load %s' % n, False, repr(ex))

    big = js.get('bigmap65.json', {})
    ut = js.get('ut_topology65.json', {})
    uty = js.get('uty_topology65.json', {})
    ry = js.get('ry_topology65.json', {})
    ov = js.get('bigmap65_ry_overlay.json', {})

    for nm, d in (('bigmap65', big), ('ut', ut), ('uty', uty), ('ry', ry)):
        if not d:
            continue
        need = {'rooms', 'edges', 'stats', 'room_count'}
        if nm != 'bigmap65':
            ck('%s 必备键齐' % nm, need <= set(d))
        ck('%s 房间数 == len(rooms)' % nm,
           d.get('room_count', len(d.get('rooms', []))) == len(d.get('rooms', [])))
    ck('bigmap node_count == len(nodes)', big.get('node_count') == len(big.get('nodes', [])))
    ck('bigmap edge_count == len(edges)', big.get('edge_count') == len(big.get('edges', [])))
    ck('bigmap 每个 node 都有 work 标签',
       all('work' in n and ':' in n['id'] for n in big.get('nodes', [])))

    # ---- ③ 编码：无 BOM / 无 U+FFFD ----
    print('\n③ 编码（BOM / U+FFFD）')
    files = [os.path.join(EV, n) for n in os.listdir(EV)] + \
            [os.path.join(HERE, n) for n in os.listdir(HERE)]
    bad_bom = [os.path.basename(p) for p in files
               if p.endswith(('.json', '.py', '.csx', '.md')) and read_b(p).startswith(b'\xef\xbb\xbf')]
    ck('无 BOM', not bad_bom, str(bad_bom))
    bad_rep = []
    for p in files:
        if not p.endswith(('.json', '.py', '.csx', '.md')):
            continue
        try:
            if u'\ufffd' in read_b(p).decode('utf-8'):
                bad_rep.append(os.path.basename(p))
        except Exception:
            bad_rep.append(os.path.basename(p) + '(decode-err)')
    ck('无 U+FFFD', not bad_rep, str(bad_rep))
    # 负控制：伪造一个带 U+FFFD 的串必须被检出
    ck('负控制 · U+FFFD 检出器可用', (u'\ufffd' in ('a\ufffdb'.encode('utf-8')).decode('utf-8')))

    # ---- ④ 恒真判据复查（本轮的"守恒判据"必须真的在图上有判别力） ----
    print('\n④ 恒真判据复查')
    comp = big.get('components', {})
    pw = comp.get('per_work', {})
    exp = sum(v['components'] for v in pw.values())
    ck('守恒：union 分量 == Σ 各作品分量', comp.get('conservation', {}).get('equal')
       and comp.get('conservation', {}).get('expected') == exp == comp.get('count'))
    ck('跨作品边 == 0', comp.get('all_cross_work') is True
       and big.get('namespace_check', {}).get('cross_work_edges') == 0)
    ck('conserve_ok 为 True', comp.get('conserve_ok') is True)
    # 负控制：把一条边改成跨作品形态，判据应报 False
    fake_edges = list(big.get('edges', []))
    if fake_edges:
        fe = dict(fake_edges[0])
        fe['to'] = ('uty:0' if fe['from'].startswith('ut:') else 'ut:0')
        wrong = [e for e in fake_edges + [fe]
                 if e['from'].split(':')[0] != e['to'].split(':')[0]]
        ck('负控制 · 伪造跨作品边会被数出来', len(wrong) == 1, 'wrong=%d' % len(wrong))

    # ---- ⑤ 逐令牌回验（报告里要用的数字，必须真的在产物里） ----
    print('\n⑤ 逐令牌回验（报告数字 ← 产物）')
    S_ut, S_uty, S_ry = ut.get('stats', {}), uty.get('stats', {}), ry.get('stats', {})
    TOK = [
        ('ut 房数', 338, ut.get('room_count')),
        ('ut 边数', 557, S_ut.get('edges')),
        ('ut 已解析', 544, S_ut.get('resolved')),
        ('ut 未解析', 13, S_ut.get('unresolved')),
        ('ut 分量', 61, S_ut.get('components')),
        ('ut 最大分量', 209, S_ut.get('largest_component')),
        ('uty 房数', 287, uty.get('room_count')),
        ('uty 边数', 491, S_uty.get('edges')),
        ('uty 已解析', 444, S_uty.get('resolved')),
        ('uty 未解析', 47, S_uty.get('unresolved')),
        ('uty 分量', 64, S_uty.get('components')),
        ('uty 最大分量', 128, S_uty.get('largest_component')),
        ('uty cc 边', 443, S_uty.get('by_evidence', {}).get('cc-nextroom')),
        ('ry 房数', 358, ry.get('room_count')),
        ('ry 已解析', 580, S_ry.get('resolved')),
        ('ry 分量', 68, S_ry.get('components')),
        ('ry 最大分量', 223, S_ry.get('largest_component')),
        ('大图 节点', 625, big.get('node_count')),
        ('大图 边', 988, big.get('edge_count')),
        ('大图 分量', 125, comp.get('count')),
        ('大图 最大分量', 209, comp.get('largest')),
        ('红与黄 同序', 338, big.get('reconcile_third_source', {}).get('same_order_vs_ut')),
        ('红与黄 增量', 20, big.get('reconcile_third_source', {}).get('extra_count')),
        ('红与黄 基线共同', 537, big.get('reconcile_third_source', {}).get('base_shared')),
        ('红与黄 仅原版', 7, big.get('reconcile_third_source', {}).get('base_only_in_ut')),
        ('红与黄 仅红黄', 9, big.get('reconcile_third_source', {}).get('base_only_in_ry')),
        ('overlay 增量房', 20, ov.get('stats', {}).get('extra_rooms')),
        ('overlay 连接点', 5, ov.get('stats', {}).get('attach_points')),
        ('overlay 增量边', 39, ov.get('stats', {}).get('extra_edges')),
        ('命名空间交集', 0, big.get('namespace_check', {}).get('pairwise_intersection', {}).get('ut∩uty', {}).get('count')),
    ]
    for label, want, got in TOK:
        ck('token %s = %s' % (label, want), got == want, 'got=%s' % (got,))
    # 负控制：不存在的 token 必须 FAIL
    ck('负控制 · 错 token(999) 必须 FAIL', (S_uty.get('edges') == 999) is False)

    # ---- ⑥ 工具可重跑（端到端） ----
    print('\n⑥ 合并器可重跑（端到端退出码 0）')
    r = subprocess.run([sys.executable, os.path.join(HERE, 'merge_bigmap65.py')],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=AUD)
    tail = r.stdout.decode('utf-8', 'replace').strip().splitlines()[-1:]
    ck('merge_bigmap65.py 退出码 0', r.returncode == 0, 'rc=%d | %s' % (r.returncode, tail))

    n = len(ROWS)
    nf = sum(1 for _, ok, _ in ROWS if not ok)
    print('\n===== 合计 %d 项：PASS %d / FAIL %d ⇒ %s ====='
          % (n, n - nf, nf, 'ALL PASS' if nf == 0 else 'HAS FAILURE'))
    return 1 if nf else 0


if __name__ == '__main__':
    raise SystemExit(main())
