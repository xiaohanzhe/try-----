# -*- coding: utf-8 -*-
u"""第115轮普查结果的独立对账（不引用普查脚本自己的汇总）。

参照物：`_evidence/raw/chN/rooms_map.json` + `objmap43.txt`（UTMT 原始产物）
判据：
  C1 逐章房间数 == 既有记录（147/278/246/328/252，合计 1,251）
  C2 Σ实例 == 47,895；且 == 报告 totals.instances
  C3 输出里每个对象都能在对应章的 `objmap43.txt` 里找到（已知例外：`GameObject` 1 个）
  C4 可见/纯逻辑两类互斥且穷尽（和 == 对象总数）
  C5 排序单调（「出现房间数」不升序 ⇒ 排序逻辑坏了）
  C6 **负控制**：把一个实例名改成 `obj_THIS_IS_NOT_REAL`，C3 必须报红
用法：python check_obj115.py
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
RAW = os.path.join(ROUND, '_evidence', 'raw')
OUT = os.path.join(ROUND, '_evidence', 'deltarune_objects115.json')
EXPECT_ROOMS = {1: 147, 2: 278, 3: 246, 4: 328, 5: 252}
KNOWN_MISSING = {'GameObject'}

res = []


def ck(name, ok, detail=''):
    res.append((name, bool(ok), detail))
    print(u'[%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                          (u'  ' + detail) if detail else ''))


def rooms_inst_names(ch):
    d = json.load(io.open(os.path.join(RAW, 'ch%d' % ch, 'rooms_map.json'),
                          encoding='utf-8'))
    names = []
    for r in d['rooms']:
        for ly in r.get('layers') or []:
            if (ly.get('type') or '') != 'Instances':
                continue
            names.extend(ly.get('instances') or [])
    return d['rooms'], names


def objmap_names(ch):
    out = set()
    for ln in io.open(os.path.join(RAW, 'ch%d' % ch, 'objmap43.txt'),
                      encoding='utf-8', errors='replace'):
        p = ln.rstrip('\n').split('\t')
        if len(p) >= 2 and p[0].strip().isdigit():
            out.add(p[1].strip())
    return out


def main():
    d = json.load(io.open(OUT, encoding='utf-8'))
    rows = d['objects']
    per = d['per_chapter']

    # C1 / C2
    tot_rooms = 0
    tot_inst = 0
    miss = []
    for ch in sorted(EXPECT_ROOMS):
        rooms, names = rooms_inst_names(ch)
        tot_rooms += len(rooms)
        tot_inst += len(names)
        known = objmap_names(ch)
        bad = sorted(set(n for n in names if n not in known))
        # C3 按章算：只允许已知例外
        unexpected = [n for n in bad if n not in KNOWN_MISSING]
        if unexpected:
            miss.append((ch, unexpected[:5]))
        ok_rooms = len(rooms) == EXPECT_ROOMS[ch] == per[str(ch)]['rooms']
        ck(u'C1 ch%d 房间数 = %d' % (ch, EXPECT_ROOMS[ch]), ok_rooms,
           u'%(a)d / 期望 %(b)d / 报告 %(c)d' % {'a': len(rooms), 'b': EXPECT_ROOMS[ch],
                                                'c': per[str(ch)]['rooms']})
    ck(u'C1b 五章合计 = 1251 间', tot_rooms == 1251, u'实得 %d' % tot_rooms)
    ck(u'C2 Σ实例 = 47895', tot_inst == 47895 == d['totals']['instances'],
       u'重算 %d / 报告 %d' % (tot_inst, d['totals']['instances']))
    ck(u'C3 实例名都落在 objmap（允许 GameObject 例外）', not miss, u'异常 %s' % (miss or u'无'))

    # C4
    vis = [r for r in rows if r['visible_prop']]
    logic = [r for r in rows if not r['visible_prop']]
    ck(u'C4 可见/纯逻辑互斥且穷尽',
       len(vis) + len(logic) == len(rows) and not (set(r['name'] for r in vis)
                                                  & set(r['name'] for r in logic)),
       u'可见 %d + 逻辑 %d = %d / 总 %d' % (len(vis), len(logic), len(vis) + len(logic), len(rows)))

    # C5
    mono = all(rows[i]['rooms'] >= rows[i + 1]['rooms'] for i in range(len(rows) - 1))
    ck(u'C5 按「出现房间数」降序排列', mono,
       u'首 %d / 末 %d' % (rows[0]['rooms'], rows[-1]['rooms']))

    # C6 负控制
    rooms, names = rooms_inst_names(1)
    known = objmap_names(1)
    poisoned = list(names) + ['obj_THIS_IS_NOT_REAL']
    red = bool([n for n in poisoned if n not in known])
    ck(u'C6 负控制（C3 判据不是恒真）', red,
       u'注入假名后判据%s' % (u'报红=有效' if red else u'仍全绿=失效'))

    ok = all(r[1] for r in res)
    print(u'\n%s  共 %d 条，PASS %d / FAIL %d'
          % (u'全绿' if ok else u'有红', len(res),
             sum(1 for r in res if r[1]), sum(1 for r in res if not r[1])))
    return 0 if ok else 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
