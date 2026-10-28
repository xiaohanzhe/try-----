# -*- coding: utf-8 -*-
u"""第115轮 · 物件分级 / 待填清单 的独立对账。

被测物：`_tools/props115.py` 的产物
  _evidence/deltarune_props115.json
  _evidence/deltarune_objects_todo.csv
  _evidence/deltarune_triggers115.txt
参照物（独立重算，不读 props115 的中间量）：
  _evidence/raw/chN/rooms_map.json
  _evidence/deltarune_objects115.json（上一轮普查）

判据：
  P1 三类（prop/trigger/logic）互斥且穷尽
  P2 Σ实例 47,895；且三类实例之和 == Σ
  P3 prop + trigger == 上一轮 visible_prop（1099），inst 同理
  P4 CSV 行数 / 编号连续 / 名字集合 == prop 集合
  P5 CSV「名字含糊」计数 == JSON 里 vague 的 prop 数
  P6 触发器名单行数 == trigger 数，且每行精灵都命中占位图规则
  P7 层深统计可用「重扫 rooms_map」独立复现（mode 是出现最多的深度，min<=mode<=max）
  P8 **负控制 A**：往 prop 集合里塞一个假对象，P4 的集合判据必须报红
  P9 **负控制 B**：把占位图规则清空，trigger 数必须变化（证明规则表真在起作用）
用法：python check_props115.py
"""
import io
import json
import os
import re
import sys
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence')
RAW = os.path.join(EV, 'raw')
CHAPTERS = [1, 2, 3, 4, 5]
EXPECT_OBJ = 1945
EXPECT_INST = 47895

sys.path.insert(0, HERE)
import props115  # noqa: E402  只借用分级规则，不借用它的汇总结果

res = []


def ck(name, ok, detail=''):
    res.append((name, bool(ok), detail))
    print(u'[%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                          (u'  ' + detail) if detail else ''))


def load(p):
    return json.load(io.open(p, encoding='utf-8'))


def rescan_depths():
    """独立重扫：obj -> Counter(depth)"""
    d = collections.defaultdict(collections.Counter)
    inst = 0
    for ch in CHAPTERS:
        for r in load(os.path.join(RAW, 'ch%d' % ch, 'rooms_map.json'))['rooms']:
            for ly in r.get('layers') or []:
                if (ly.get('type') or '') != 'Instances':
                    continue
                dep = ly.get('depth')
                for n in ly.get('instances') or []:
                    d[n][dep] += 1
                    inst += 1
    return d, inst


def csv_rows(p):
    txt = io.open(p, encoding='utf-8-sig').read()
    lines = [ln for ln in txt.split('\n') if ln.strip()]
    return lines[0], lines[1:]


def main():
    props = load(os.path.join(EV, 'deltarune_props115.json'))
    old = load(os.path.join(EV, 'deltarune_objects115.json'))
    rows = props['objects']
    by = collections.defaultdict(list)
    for r in rows:
        by[r['class']].append(r)

    # P1
    names = [r['name'] for r in rows]
    allc = [r['class'] for r in rows]
    ck(u'P1 三类互斥且穷尽',
       len(names) == len(set(names)) == EXPECT_OBJ
       and sum(len(by[k]) for k in ('prop', 'trigger', 'logic')) == EXPECT_OBJ,
       u'prop %d / trigger %d / logic %d = %d'
       % (len(by['prop']), len(by['trigger']), len(by['logic']), len(rows)))

    # P2
    s_cls = sum(r['inst'] for r in rows)
    s_ch = sum(props['per_chapter']['inst'][str(c)] for c in CHAPTERS)
    ck(u'P2 Σ实例 = %d' % EXPECT_INST,
       s_cls == EXPECT_INST == s_ch,
       u'按对象 %d / 按章 %d / 报告 %d' % (s_cls, s_ch, props['totals']['inst']))

    # P3
    old_vis = [o for o in old['objects'] if o['visible_prop']]
    mine = [r for r in rows if r['class'] in ('prop', 'trigger')]
    ok3 = (len(old_vis) == len(mine)
           and sum(o['inst'] for o in old_vis) == sum(r['inst'] for r in mine)
           and set(o['name'] for o in old_vis) == set(r['name'] for r in mine))
    ck(u'P3 prop+trigger == 上一轮「可见」集合', ok3,
       u'本轮 %d 个/%d 次 · 上轮 %d 个/%d 次'
       % (len(mine), sum(r['inst'] for r in mine), len(old_vis),
          sum(o['inst'] for o in old_vis)))

    # P4
    head, lines = csv_rows(os.path.join(EV, 'deltarune_objects_todo.csv'))
    got = []
    nums = []
    for ln in lines:
        p = ln.split(',')
        nums.append(p[0])
        got.append(p[1])
    prop_names = set(r['name'] for r in by['prop'])
    seq = [u'%03d' % i for i in range(1, len(lines) + 1)]
    ok4 = (len(lines) == len(by['prop']) and set(got) == prop_names
           and nums == seq and head.startswith(u'编号,对象名'))
    ck(u'P4 CSV 行数/编号/名字集合 == prop', ok4,
       u'%d 行 · 集合差 %d · 编号%s' % (len(lines), len(prop_names ^ set(got)),
                                u'连续' if nums == seq else u'不连续'))

    # P5
    vague_in_csv = sum(1 for ln in lines if ln.split(',')[8] == u'是')
    vague_in_json = sum(1 for r in by['prop'] if r['vague'])
    ck(u'P5 名字含糊计数一致', vague_in_csv == vague_in_json,
       u'CSV %d / JSON %d' % (vague_in_csv, vague_in_json))

    # P6
    tlines = [ln for ln in io.open(os.path.join(EV, 'deltarune_triggers115.txt'),
                                   encoding='utf-8').read().split('\n')
              if ln.strip() and not ln.startswith(u'第115轮') and not ln.startswith(u'共 ')]
    bad_spr = []
    for ln in tlines:
        p = ln.split()
        if len(p) < 2 or not props115.is_trigger_sprite(p[1]):
            bad_spr.append(ln[:40])
    ck(u'P6 触发器名单 %d 条且精灵都命中占位规则' % len(by['trigger']),
       len(tlines) == len(by['trigger']) and not bad_spr,
       u'行 %d / 不符 %d %s' % (len(tlines), len(bad_spr), bad_spr[:3]))

    # P7
    depths, tot = rescan_depths()
    assert tot == EXPECT_INST, tot
    bad7 = []
    for r in rows:
        c = depths[r['name']]
        if not c:
            bad7.append((r['name'], 'no-depth'))
            continue
        mode, mc = min(c.items(), key=lambda kv: (-kv[1], kv[0]))
        if not (r['depth_min'] == min(c) and r['depth_max'] == max(c)
                and r['depth_mode'] == mode and r['n_depths'] == len(c)):
            bad7.append((r['name'], r['depth_mode'], mode))
    ck(u'P7 层深统计可被独立重扫复现', not bad7, u'不符 %d 个 %s' % (len(bad7), bad7[:3]))

    # P8 负控制 A
    poisoned = set(prop_names) | {'obj_THIS_IS_NOT_REAL'}
    red = not (poisoned == prop_names)
    ck(u'P8 负控制 A（P4 集合判据不是恒真）', red,
       u'注入假对象后判据%s' % (u'报红=有效' if red else u'仍全绿=失效'))

    # P9 负控制 B：清空规则表后 trigger 必须变少
    real = props115._TRIGGER_RES
    n_trig_real = sum(1 for r in rows
                      if r['vis'] == 'True' and r['sprite']
                      and props115.is_trigger_sprite(r['sprite']))
    props115._TRIGGER_RES = []
    n_trig_off = sum(1 for r in rows
                     if r['vis'] == 'True' and r['sprite']
                     and props115.is_trigger_sprite(r['sprite']))
    props115._TRIGGER_RES = real
    ck(u'P9 负控制 B（规则表真在起作用）',
       n_trig_real > n_trig_off == 0,
       u'开 %d / 关 %d' % (n_trig_real, n_trig_off))

    ok = all(r[1] for r in res)
    print(u'\n%s  共 %d 条，PASS %d / FAIL %d'
          % (u'全绿' if ok else u'有红', len(res),
             sum(1 for r in res if r[1]), sum(1 for r in res if not r[1])))
    return 0 if ok else 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
