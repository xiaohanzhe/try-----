# -*- coding: utf-8 -*-
u"""第66轮 · 交付前复检。

判据分五组，**每组配负控制**：
  ① 可编译/JSON ② 编码 ③ 结构自洽（判非门的证据成立）④ 连通性（含"合成边真的在承重"）
  ⑤ 逐令牌回验（报告数字 ← 产物）
★ 只 ast.parse，不产 .pyc；不改变任何被测状态。
"""
from __future__ import print_function
import ast, collections, io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
AUD = os.path.join(HERE, '..')
EV = os.path.join(AUD, '_evidence')
R65 = os.path.join(HERE, '..', '..', u'第65轮-黄魂并入Undertale大地图', '_evidence')
# ★★ 修订（第66轮）：原先这里写的是 `E:\Download\_extract61\...`（外部盘 + 用后即删的
#    转储区）—— **违反铁律**（回归/复检不许依赖外部盘：盘一掉线，判据要么报红、
#    要么**静默变成假绿**）。已用 `_tools/distill_gml66.py` 把 ⑥ 段要读的 105 个 GML
#    蒸馏进 `_evidence/gml_evidence66/`，本脚本只读仓内那一份。
GML = {
    'ut': os.path.join(EV, 'gml_evidence66', 'ut'),
    'uty': os.path.join(EV, 'gml_evidence66', 'uty'),
    'ry': os.path.join(EV, 'gml_evidence66', 'ry'),
}
GML_MANIFEST = os.path.join(EV, 'gml_evidence66', '_manifest.json')
ROWS = []


def ck(n, ok, d=''):
    ROWS.append((n, bool(ok)))
    print('  [%s] %-58s %s' % ('PASS' if ok else 'FAIL', n, d))


def comps(ids, edges):
    adj = collections.defaultdict(set)
    idset = set(ids)
    for e in edges:
        if e['from'] in idset and e['to'] in idset:
            adj[e['from']].add(e['to'])
            adj[e['to']].add(e['from'])
    seen, n = set(), 0
    for i in ids:
        if i in seen:
            continue
        n += 1
        st = [i]
        seen.add(i)
        while st:
            u = st.pop()
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    st.append(v)
    return n


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print('===== 第66轮交付前复检 =====')

    print('\n① 可编译 / JSON')
    for n in sorted(x for x in os.listdir(HERE) if x.endswith('.py')):
        try:
            ast.parse(io.open(os.path.join(HERE, n), encoding='utf-8').read())
            ck('ast.parse %s' % n, True)
        except SyntaxError as ex:
            ck('ast.parse %s' % n, False, str(ex))
    try:
        ast.parse('def f(:\n pass\n')
        ck('负控制 · 坏源码必被拒', False)
    except SyntaxError:
        ck('负控制 · 坏源码必被拒', True)
    js = {}
    for n in sorted(x for x in os.listdir(EV) if x.endswith('.json')):
        try:
            js[n] = json.load(io.open(os.path.join(EV, n), encoding='utf-8'))
            ck('json.load %s' % n, True)
        except Exception as ex:
            ck('json.load %s' % n, False, repr(ex))

    print('\n② 编码')
    files = [os.path.join(EV, x) for x in os.listdir(EV)] + \
            [os.path.join(HERE, x) for x in os.listdir(HERE)]
    bad = [os.path.basename(p) for p in files
           if p.endswith(('.json', '.py')) and io.open(p, 'rb').read().startswith(b'\xef\xbb\xbf')]
    ck('无 BOM', not bad, str(bad))
    bad2 = []
    for p in files:
        if not p.endswith(('.json', '.py')):
            continue
        try:
            if u'\ufffd' in io.open(p, 'rb').read().decode('utf-8'):
                bad2.append(os.path.basename(p))
        except Exception:
            bad2.append(os.path.basename(p) + '(decode-err)')
    ck('无 U+FFFD', not bad2, str(bad2))
    ck('负控制 · U+FFFD 检出器可用', u'\ufffd' in u'a\ufffdb')

    b = js.get('bigmap66.json')
    if not b:
        print('!! bigmap66.json 缺失')
        return 1

    print('\n③ 结构自洽')
    ck('nodes == 645', len(b['nodes']) == 645, 'got=%d' % len(b['nodes']))
    ck('edges == 1034', len(b['edges']) == 1034, 'got=%d' % len(b['edges']))
    ck('每节点有 work', all('work' in n and ':' in n['id'] for n in b['nodes']))
    ck('每条边两端都在节点里',
       set(e['from'] for e in b['edges']) <= set(n['id'] for n in b['nodes'])
       and set(e['to'] for e in b['edges']) <= set(n['id'] for n in b['nodes']))
    # 判非门：non-door-superseded 必须"同房确有已解析门"
    nd = b['non_doors']
    sup = [x for x in nd if x['reason'] == 'non-door-superseded']

    def viol(rows):
        return [x for x in rows if x['reason'] == 'non-door-superseded'
                and not x.get('same_room_has_resolved_door')]

    ck('non-door-superseded 全部"同房已有真门"', not viol(nd), 'violations=%d' % len(viol(nd)))
    # ★ 负控制：**判据本身**也要能抓假样本（否则判据可能空转）
    fake = dict(sup[0]) if sup else {'reason': 'non-door-superseded'}
    fake['same_room_has_resolved_door'] = False
    ck('负控制 · 判据能抓出伪造的 superseded', len(viol(list(nd) + [fake])) == 1,
       'planted=1 got=%d' % len(viol(list(nd) + [fake])))
    print('      （明细：%s）' % json.dumps(
        dict(('%s/%s' % k, v) for k, v in
             collections.Counter((x['work'], x['reason']) for x in nd).items()),
        ensure_ascii=False))
    # 载体 4 的目标必须是真实房号
    n_real = dict((w, len(b['works'][w]['rooms'])) for w in ('ut', 'uty'))
    bad_rt = [e for e in b['edges'] if e['evidence_kind'] == 'runtime-nextroom'
              and not (0 <= int(e['to'].split(':')[1]) < n_real[e['to'].split(':')[0]])]
    ck('runtime-nextroom 目标房号合法', not bad_rt, str(bad_rt))
    ck('runtime-nextroom 恰 3 条',
       len([e for e in b['edges'] if e['evidence_kind'] == 'runtime-nextroom']) == 3)

    print('\n④ 连通性（★ 合成边必须在承重）')
    # ★ 口径：真实分量只在**作品节点**上算（hub 节点无真实边，计入会白加 3）
    ids_work = [n['id'] for n in b['nodes']]
    ids = ids_work + [h['id'] for h in b['hub']['nodes']]
    real = comps(ids_work, b['edges'])
    full = comps(ids, b['edges'] + b['hub']['edges'] + b['synthetic_edges'])
    ck('真实分量 == 129（仅作品节点）', real == 129, 'got=%d' % real)
    ck('含合成边后 == 1（完全连通）', full == 1, 'got=%d' % full)
    ck('产物自报 real == 129', b['connectivity']['real']['components'] == 129)
    ck('产物自报 with_synthetic == 1', b['connectivity']['with_synthetic']['components'] == 1)
    ck('hub 节点本身与真实图无关（真实边上无 hub）',
       all(e['from'] in set(ids_work) and e['to'] in set(ids_work) for e in b['edges']))
    # 负控制 A：全部合成边（含 hub 边）抽掉 ⇒ 必须回落
    ck('负控制 · 抽掉 hub+合成边 ⇒ 回到 129',
       comps(ids_work, b['edges']) == 129
       and comps(ids, b['edges']) == 132)
    # 负控制 B：只抽掉一条 orphan ⇒ 必须 > 1
    if b['synthetic_edges']:
        one_less = b['synthetic_edges'][1:]
        ck('负控制 · 少一条 orphan ⇒ > 1',
           comps(ids, b['edges'] + b['hub']['edges'] + one_less) > 1)
    # 反向控制：加一条冗余同源边 ⇒ 仍是 1
    red = b['synthetic_edges'][:1] + b['synthetic_edges']
    ck('反向控制 · 加冗余合成边 ⇒ 仍是 1',
       comps(ids, b['edges'] + b['hub']['edges'] + red) == 1)

    print('\n⑤ 逐令牌回验（报告数字 ← 产物）')
    ew = b['counts']['by_work']
    ev = b['counts']['by_evidence']
    TOK = [
        ('ut 家族房数', 358, b['works']['ut']['room_count']),
        ('uty 房数', 287, b['works']['uty']['room_count']),
        ('ut 家族边数', 587, ew['ut']['edges']),
        ('uty 边数', 447, ew['uty']['edges']),
        ('总节点', 645, len(b['nodes'])),
        ('总边', 1034, len(b['edges'])),
        ('真实分量', 129, b['connectivity']['real']['components']),
        ('最大真实分量', 225, b['connectivity']['real']['largest']),
        ('合成后分量', 1, b['connectivity']['with_synthetic']['components']),
        ('hub 节点', 3, len(b['hub']['nodes'])),
        ('hub 边', 4, len(b['hub']['edges'])),
        ('orphan 合成边', 127, len(b['synthetic_edges'])),
        ('offset=+1', 187, ev.get('offset=+1')),
        ('offset=-1', 184, ev.get('offset=-1')),
        ('cond', 145, ev.get('cond')),
        ('cc-nextroom', 443, ev.get('cc-nextroom')),
        ('runtime-nextroom', 3, ev.get('runtime-nextroom')),
        ('ry 增量房', 20, b['works']['ut']['merged_from']['ry_extra_rooms']),
        ('ry 合并新增边', 43, b['works']['ut']['merged_from']['ry_extra_edges']),
        ('ry 前 338 同名同序', 338, b['works']['ut']['merged_from']['ry_base_same_order']),
        ('非门对象总数', 66, len(nd)),
        ('非门-superseded', 57, len(sup)),
        ('code-not-dumped', 6, len([x for x in nd if x['reason'] == 'code-not-dumped'])),
        ('仍无解边', 4, len(b.get('still_unresolved', []))),
    ]
    for lbl, want, got in TOK:
        ck('token %s = %s' % (lbl, want), got == want, 'got=%s' % (got,))
    ck('负控制 · 错 token(999) 必 FAIL', (b['counts']['nodes'] == 999) is False)

    print('\n⑥ 判非门判据的判别力（真实回查源码 —— ★只读仓内蒸馏副本）')
    _man = json.load(io.open(GML_MANIFEST, encoding='utf-8'))
    _disk = sum(1 for w in ('ut', 'uty', 'ry')
                for f in os.listdir(GML[w]) if f.endswith('.gml'))
    ck('GML 蒸馏守恒：仓内 %d 个 == manifest 记的 %d 个（missing=%d；★不碰外部盘）'
       % (_disk, _man['n_copied'], len(_man['missing'])),
       _disk == _man['n_copied'] and not _man['missing'])
    ck('负控制 · 蒸馏目录真的在仓内（不是指向 E 盘的软链/旧路径）',
       os.path.abspath(GML['ut']).startswith(os.path.abspath(EV)))
    # 抽查 3 个 non-door-superseded：其事件里确实没有任何转场指令
    import re
    pats = [re.compile(r'room_goto\s*\('), re.compile(r'room_goto_next\s*\('),
            re.compile(r'(?<![A-Za-z0-9_.])nextroom\s*=\s*-?\d+'),
            re.compile(r'(?<![A-Za-z0-9_.])room\s*=\s*[A-Za-z_]')]
    spot = [x for x in sup if x.get('files')][:8]
    okall = True
    for x in spot:
        w, obj = x['work'], x['obj']
        if w not in GML:
            continue
        d = GML[w]
        hit = 0
        for fn in os.listdir(d):
            if not fn.startswith('gml_Object_' + obj + '_'):
                continue
            t = io.open(os.path.join(d, fn), encoding='utf-8', errors='replace').read()
            t = re.sub(r'/\*.*?\*/', '', t, flags=re.S)
            t = re.sub(r'//[^\n]*', '', t)
            if any(p.search(t) for p in pats):
                hit += 1
        if hit:
            okall = False
            print('      !! %s/%s 竟然有转场指令 ×%d' % (w, obj, hit))
    ck('抽查 non-door-superseded 源码：确实无转场指令', okall, 'checked=%d' % len(spot))
    # ★ 正控制必须选**声明目标**的对象（`obj_doorway` 是**读取端**，把 nextroom 转交
    #   `obj_transition`，本来就不含转场指令 ⇒ 拿它当正控制是判据侧写错）
    pos = [('uty', 'gml_Object_obj_hiddenentrance_Step_0.gml',
            u'运行期 nextroom = 28'),
           ('ut', 'gml_Object_obj_door_t_Alarm_2.gml', u'room_goto 表')]
    for w, fn, why in pos:
        p = os.path.join(GML[w], fn)
        if not os.path.isfile(p):
            ck('正控制 · %s 可读' % fn, False, 'missing')
            continue
        t = io.open(p, encoding='utf-8', errors='replace').read()
        ck('正控制 · 同判据命中 %s（%s）' % (fn.replace('gml_Object_', ''), why),
           any(rx.search(t) for rx in pats))
    # 反向核对：obj_doorway 是读取端，判据**不该**命中（否则判据把读取端当声明端）
    tp = os.path.join(GML['uty'], 'gml_Object_obj_doorway_Collision_obj_pl.gml')
    t = io.open(tp, encoding='utf-8', errors='replace').read()
    ck('反向控制 · obj_doorway(读取端) 判据不命中（它靠 nextroom，不自己声明）',
       not any(rx.search(t) for rx in pats))

    nf = sum(1 for _, ok in ROWS if not ok)
    print('\n===== 合计 %d 项：PASS %d / FAIL %d ⇒ %s ====='
          % (len(ROWS), len(ROWS) - nf, nf, 'ALL PASS' if nf == 0 else 'HAS FAILURE'))
    return 1 if nf else 0


if __name__ == '__main__':
    raise SystemExit(main())
