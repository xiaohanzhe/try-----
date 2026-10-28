# -*- coding: utf-8 -*-
u"""第115轮 · 交互点坐标表的独立对账。

被测物：_evidence/deltarune_points115.json（`_tools/points115.py` 的产物）
参照物：_evidence/raw/chN/inst68.json（UTMT 原始产物）+ objmap43.txt

判据：
  Q1 逐章 rooms_total == 147/278/246/328/252；rooms_with_points == n_rooms_hit；points == n_inst
  Q2 每间房 Σ points == 该房 n
  Q3 每个 obj 名都落在该章 objmap43.txt（已知例外 GameObject）
  Q4 分类互斥穷尽，且能被 checker 里**独立实现**的分类函数复现
  Q5 坐标都是 int，且 |v| ≤ 100000（解析跑偏会出天文数字；正样本最大 19698）
  Q6 **负控制 A**：把某点坐标改成 999999，Q5 必须报红
  Q7 **负控制 B**：把某 obj 名改成 obj_THIS_IS_NOT_REAL，Q3 必须报红

★ 为什么**不**判「点必须在房间框内」：GM 允许实例摆在房间外，实测越界 407/6889（5.9%），
  最远 `obj_krmarker` x=-2360（房间宽 2680）。那是原作摆法，不是解析错误 —— 拿它当判据就是误报。
用法：python check_points115.py
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.normpath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence')
RAW = os.path.join(EV, 'raw')
CHAPTERS = [1, 2, 3, 4, 5]
EXPECT_ROOMS = {1: 147, 2: 278, 3: 246, 4: 328, 5: 252}
KNOWN_MISSING = {'GameObject'}
COORD_MAX = 100000

res = []


def ck(name, ok, detail=''):
    res.append((name, bool(ok), detail))
    print(u'[%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                          (u'  ' + detail) if detail else ''))


def load(p):
    return json.load(io.open(p, encoding='utf-8'))


def raw_rooms(ch):
    return load(os.path.join(RAW, 'ch%d' % ch, 'inst68.json'))


def objmap_names(ch):
    out = set()
    for ln in io.open(os.path.join(RAW, 'ch%d' % ch, 'objmap43.txt'),
                      encoding='utf-8', errors='replace'):
        p = ln.rstrip('\n').split('\t')
        if len(p) >= 2 and p[0].strip().isdigit():
            out.add(p[1].strip())
    return out


def indep_kind(name):
    """独立实现（故意不 import points115，避免"自己验自己"）"""
    n = name.lower()
    if 'door' in n:
        return 'door'
    if 'warp' in n:
        return 'warp'
    if 'marker' in n:
        return 'marker'
    if 'savepoint' in n:
        return 'save'
    if 'treasure' in n:
        return 'treasure'
    if n.startswith('obj_readable'):
        return 'readable'
    if 'sign' in n:
        return 'sign'
    return 'other'


def main():
    d = load(os.path.join(EV, 'deltarune_points115.json'))
    chs = {c['ch']: c for c in d['chapters']}

    # Q1 / Q2 / Q3
    bad1 = []
    bad2 = []
    bad3 = []
    tot = 0
    for ch in CHAPTERS:
        r = raw_rooms(ch)
        c = chs[ch]
        npts = sum(len(rm['points']) for rm in c['rooms'])
        tot += npts
        if not (c['rooms_total'] == EXPECT_ROOMS[ch] == r['n_rooms_total']
                and len(c['rooms']) == r['n_rooms_hit']
                and npts == r['n_inst']):
            bad1.append((ch, c['rooms_total'], r['n_rooms_total'], len(c['rooms']),
                         r['n_rooms_hit'], npts, r['n_inst']))
        per = {rm['index']: rm['n'] for rm in r['rooms']}
        for rm in c['rooms']:
            if len(rm['points']) != per.get(rm['index'], -1):
                bad2.append((ch, rm['name'], len(rm['points']), per.get(rm['index'])))
        known = objmap_names(ch)
        for rm in c['rooms']:
            for p in rm['points']:
                if p['obj'] not in known and p['obj'] not in KNOWN_MISSING:
                    bad3.append((ch, rm['name'], p['obj']))
    ck(u'Q1 逐章 房间数/命中房间/点数 三对齐', not bad1, u'异常 %s' % (bad1[:2] or u'无'))
    ck(u'Q2 每间房点数 == 原始 n', not bad2, u'不符 %d 间 %s' % (len(bad2), bad2[:2]))
    ck(u'Q3 点对象名都落在 objmap', not bad3, u'异常 %d 个 %s' % (len(bad3), bad3[:3]))

    # Q4
    allpts = [p for ch in CHAPTERS for rm in chs[ch]['rooms'] for p in rm['points']]
    mismatch = [(p['obj'], p['kind'], indep_kind(p['obj'])) for p in allpts
                if p['kind'] != indep_kind(p['obj'])]
    ssum = sum(d['by_kind'].values())
    ok4 = (not mismatch) and ssum == tot == d['coverage']['points']
    ck(u'Q4 分类互斥穷尽且可独立复现', ok4,
       u'Σ分类 %d / 点数 %d / 分类不符 %d %s' % (ssum, tot, len(mismatch), mismatch[:2]))

    # Q5
    def bad_coord(pts):
        out = []
        for p in pts:
            for k in ('x', 'y'):
                v = p[k]
                if not isinstance(v, int) or isinstance(v, bool) or abs(v) > COORD_MAX:
                    out.append((p['obj'], k, v))
        return out

    b5 = bad_coord(allpts)
    mx = max(max(abs(p['x']), abs(p['y'])) for p in allpts)
    ck(u'Q5 坐标都是 int 且 |v| ≤ %d' % COORD_MAX, not b5,
       u'越限 %d 个 / 实测最大 %d' % (len(b5), mx))

    # Q6 负控制 A
    poisoned = [dict(allpts[0])]
    poisoned[0]['x'] = 999999
    red6 = bool(bad_coord(poisoned))
    ck(u'Q6 负控制 A（Q5 不是恒真）', red6,
       u'注入 999999 后判据%s' % (u'报红=有效' if red6 else u'仍全绿=失效'))

    # Q7 负控制 B
    known1 = objmap_names(1)
    red7 = 'obj_THIS_IS_NOT_REAL' not in known1
    ck(u'Q7 负控制 B（Q3 不是恒真）', red7,
       u'假名不在 objmap 里=%s' % red7)

    ok = all(r[1] for r in res)
    print(u'\n%s  共 %d 条，PASS %d / FAIL %d'
          % (u'全绿' if ok else u'有红', len(res),
             sum(1 for r in res if r[1]), sum(1 for r in res if not r[1])))
    return 0 if ok else 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
