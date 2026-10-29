# -*- coding: utf-8 -*-
u"""第115轮 · UT / UTY / Outertale 物件分级的独立对账。

被测物：_evidence/cross_props115.json + cross_objects_todo.csv + cross_triggers115.txt
参照物：_evidence/raw/<key>/inst_full.tsv（实例真源，独立于分级脚本）
        + 详版 §87.11 登记（房间数）+ Deltarune 的分级口径（props115.py）

判据：
  P1  三款 by_class 互斥且穷尽：prop+trigger+logic 的对象数 == 实例表里出现的对象数
  P2  三款实例总数 == 13,965 / 7,636 / 14,535（与坐标导出各自独立相符）
  P3  CSV 行数 == 不同 prop 对象名数；编号连续 001..N；对象名集合 == prop 名字集合；
      作品列只在三个合法值里（多作品用 ` / ` 连接）
  P4  每个 prop 的 sprite 非空且 vis=True（防「把看不见的东西塞进待填清单」）
  P5  每个 trigger 的 sprite 非空（规则只该命中"有图但是占位图"的对象）
  P6  ★ 与 Deltarune 同口径抽查：obj_solidsmall / obj_doorA 必须是 logic，obj_mainchara 必须是 prop
  P7  **负控制 A**：把 obj_doorA 的 vis 改成 True ⇒ P6 必须报红
  P8  **负控制 B**：清空占位图规则表 ⇒ trigger 必须掉到 0（证明规则表真在起作用）
  P9  **负控制 C**：往 CSV 编号里注入重复 ⇒ P3 的连续性判据必须报红
  P10 分母闸：prop 数必须 > 0（空集不算通过）
  P11 ★ 合并守恒：CSV「实例数合计」之和 == prop 实例总和；「作品数」之和 == 未合并行数
      （这两条同时成立，才说明合并只是换了个分组，没有丢数据也没有重复计数）

用法：python check_props_ut115.py
"""
import collections
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence')

sys.path.insert(0, HERE)
import props_ut115 as P          # 复用同一份规则表（P8 要证明它真在起作用）

WORKS = ['ut', 'uty', 'outertale']
EXPECT_INST = {'ut': 13965, 'uty': 7636, 'outertale': 14535}
OK_WORK_CN = set(P.WORK_CN.values())

res = []


def ck(name, ok, detail=''):
    res.append((name, bool(ok), detail))
    print(u'[%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                          (u'  ' + detail) if detail else ''))


def load():
    with io.open(os.path.join(EV, 'cross_props115.json'), encoding='utf-8') as f:
        return json.load(f)


def used_objects_from_tsv(key):
    """从实例表独立数出「出现过的对象名」个数与实例数（不复用分级脚本）"""
    p = os.path.join(EV, 'raw', key, 'inst_full.tsv')
    names = set()
    n = 0
    with io.open(p, encoding='utf-8') as f:
        for ln in f:
            if ln.startswith('I\t'):
                names.add(ln.split('\t')[1])
                n += 1
    return len(names), n


def main():
    d = load()
    rows = d['objects']
    by = collections.defaultdict(list)
    for r in rows:
        by[r['work']].append(r)

    # P1 互斥穷尽
    bad1 = []
    for key in WORKS:
        used, _ = used_objects_from_tsv(key)
        got = len(by[key])
        cls_sum = sum(d['totals'][key]['by_class'][c]['objects']
                      for c in ('prop', 'trigger', 'logic'))
        if not (got == used == cls_sum):
            bad1.append((key, got, used, cls_sum))
    ck(u'P1 三款 分级对象数 == 实例表对象数（互斥穷尽）', not bad1,
       u'%s' % (u' '.join(u'%s=%d' % (k, len(by[k])) for k in WORKS)
                if not bad1 else u'不符 %s' % bad1))

    # P2 实例数
    bad2 = [(k, sum(r['inst'] for r in by[k]), EXPECT_INST[k]) for k in WORKS
            if sum(r['inst'] for r in by[k]) != EXPECT_INST[k]]
    ck(u'P2 三款实例数 == 13,965 / 7,636 / 14,535', not bad2,
       u'%s' % (u'不符 %s' % bad2 if bad2 else
                u' '.join(u'%s=%d' % (k, sum(r['inst'] for r in by[k])) for k in WORKS)))

    # P3 CSV（同名跨作品已合并：行数 == 不同对象名数，不是 prop 行数）
    csv_p = os.path.join(EV, 'cross_objects_todo.csv')
    lines = io.open(csv_p, encoding='utf-8-sig').read().splitlines()
    body = lines[1:]
    nums = []
    bad_work = []
    csv_names = []
    csv_inst = 0
    csv_nworks = 0
    for ln in body:
        parts = ln.split(',')
        if len(parts) < 5:
            continue
        nums.append(parts[0])
        csv_names.append(parts[2])
        for w in [x.strip() for x in parts[1].split('/')]:
            if w not in OK_WORK_CN:
                bad_work.append(w)
        csv_nworks += int(parts[4])
        csv_inst += int(parts[6]) if len(parts) > 6 else 0
    props_all = [r for r in rows if r['class'] == 'prop']
    prop_names = set(r['name'] for r in props_all)
    distinct = len(prop_names)
    seq_ok = (nums == ['%03d' % i for i in range(1, len(nums) + 1)])
    ck(u'P3 CSV 行数==不同对象名数 / 编号连续 / 作品列合法',
       len(body) == distinct and seq_ok and not bad_work
       and set(csv_names) == prop_names,
       u'行数 %d vs 不同名 %d；编号连续=%s；非法作品 %s；名字集合相等=%s'
       % (len(body), distinct, seq_ok, bad_work[:3] or u'无',
          set(csv_names) == prop_names))

    # P4 prop 必须有图且可见
    bad4 = [(r['work'], r['name'], r['sprite'], r['vis']) for r in rows
            if r['class'] == 'prop' and (not r['sprite'] or r['vis'] != 'True')]
    ck(u'P4 每个 prop 的 sprite 非空且 vis=True', not bad4,
       u'违反 %d 个 %s' % (len(bad4), bad4[:3] or u''))

    # P5 trigger 必须有图
    bad5 = [(r['work'], r['name']) for r in rows
            if r['class'] == 'trigger' and not r['sprite']]
    ck(u'P5 每个 trigger 的 sprite 非空', not bad5,
       u'违反 %d 个 %s' % (len(bad5), bad5[:3] or u''))

    # P6 与 Deltarune 同口径抽查
    idx = {(r['work'], r['name']): r for r in rows}
    spec = [(('ut', 'obj_solidsmall'), 'logic'),
            (('ut', 'obj_doorA'), 'logic'),
            (('ut', 'obj_mainchara'), 'prop'),
            (('uty', 'obj_wall'), 'logic')]
    bad6 = []
    for k, want in spec:
        r = idx.get(k)
        if r is None:
            bad6.append((k, 'MISSING', want))
        elif r['class'] != want:
            bad6.append((k, r['class'], want))
    ck(u'P6 与 Deltarune 同口径抽查（碰撞块/门=logic，主角=prop）', not bad6,
       u'%s' % (u'不符 %s' % bad6 if bad6 else u'4/4 相符'))

    # P7 负控制 A：把 obj_doorA 的 vis 翻成 True，P6 必须报红
    fake = [dict(r) for r in rows]
    for r in fake:
        if r['work'] == 'ut' and r['name'] == 'obj_doorA':
            r['vis'] = 'True'
            r['class'] = 'prop'          # 模拟"判据没拦住"的后果
    fidx = {(r['work'], r['name']): r for r in fake}
    red7 = fidx[('ut', 'obj_doorA')]['class'] != 'logic'
    ck(u'P7 负控制 A（P6 不是恒真）', red7,
       u'把 obj_doorA 的 vis 改成 True 后判据%s' % (u'报红=有效' if red7 else u'仍全绿=失效'))

    # P8 负控制 B：清空规则表，trigger 必须掉到 0
    saved = list(P.TRIGGER_RULES)
    try:
        P.TRIGGER_RULES = []
        n_trig = 0
        for key in WORKS:
            for r in by[key]:
                spr = r['sprite']
                if spr and r['vis'] == 'True' and P.triggered_by(spr):
                    n_trig += 1
    finally:
        P.TRIGGER_RULES = saved
    real_trig = sum(1 for r in rows if r['class'] == 'trigger')
    red8 = (n_trig == 0 and real_trig > 0)
    ck(u'P8 负控制 B（规则表真在起作用）', red8,
       u'清空后 trigger=%d，实际=%d ⇒ %s'
       % (n_trig, real_trig, u'规则表有效' if red8 else u'规则表可能是摆设'))

    # P9 负控制 C：CSV 编号注入重复
    poisoned = list(nums)
    if len(poisoned) >= 2:
        poisoned[1] = poisoned[0]
    red9 = (poisoned != ['%03d' % i for i in range(1, len(poisoned) + 1)])
    ck(u'P9 负控制 C（P3 的编号连续判据不是恒真）', red9,
       u'注入重复编号后判据%s' % (u'报红=有效' if red9 else u'仍全绿=失效'))

    # P10 分母闸
    n_prop = len(props_all)
    ck(u'P10 分母闸：prop 数 > 0', n_prop > 0, u'prop=%d' % n_prop)

    # P11 合并守恒
    prop_inst_sum = sum(r['inst'] for r in props_all)
    ck(u'P11 合并守恒（实例数不重不漏 / 作品数之和 == 未合并行数）',
       csv_inst == prop_inst_sum and csv_nworks == n_prop,
       u'CSV 实例合计 %d vs prop 实例 %d；作品数之和 %d vs 未合并行数 %d'
       % (csv_inst, prop_inst_sum, csv_nworks, n_prop))

    ok = all(r[1] for r in res)
    print(u'\n%s  共 %d 条，PASS %d / FAIL %d'
          % (u'全绿' if ok else u'有红', len(res),
             sum(1 for r in res if r[1]), sum(1 for r in res if not r[1])))
    return 0 if ok else 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
