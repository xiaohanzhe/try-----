# -*- coding: utf-8 -*-
u"""第118轮：把解析结果按 (房间, 对象) 分组，看清「第二层守卫」到底是哪几类、各多少。

要回答三个问题（不看清就动手＝拍脑袋）：
  1. 有多少 (房间, 对象) 组**存在多条候选**（第117轮因为"只取第一条"被丢掉的 14 条在这里）；
  2. 这些多条候选里，多少能用 `x`/`y` **位置**区分（产品有 pos，可静态绑定）；
  3. 多少只能靠剧情/实例状态区分（产品没有这套状态 ⇒ 只能取默认那条并如实标注）。
"""
import collections
import io
import os
import re
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.dirname(HERE)
CONDS = os.path.join(ROUND, '_evidence', 'readable_conds118.tsv')

RE_ROOM = re.compile(r'^room == (\w+)$')
RE_POS = re.compile(r'^([xy])\s*(<=|>=|<|>|==)\s*(-?[\d.]+)$')


def read_tsv(path):
    with io.open(path, encoding='utf-8', errors='replace', newline='') as f:
        lines = f.read().splitlines()
    return [ln.split('\t') for ln in lines[1:] if ln.strip()]


def obj_of(alarm):
    s = alarm
    if s.startswith('gml_Object_'):
        s = s[11:]
    i = s.find('_Alarm_')
    return s[:i] if i > 0 else s


def main():
    rows = read_tsv(CONDS)
    if not rows:
        print('[FAIL] 没有解析结果（先跑 conds118.py）')
        return 2

    groups = collections.defaultdict(list)
    for alarm, _depth, cond, target, key in rows:
        if key.startswith('MSC_'):
            continue
        atoms = [a for a in cond.split(' && ') if a]
        room = None
        pos, plot, other = [], [], []
        for a in atoms:
            m = RE_ROOM.match(a)
            if m:
                room = m.group(1)
                continue
            if RE_POS.match(a):
                pos.append(a)
            elif a.startswith(('ELSE_IF:', 'ELSE_OF:')):
                other.append(a)
            elif a.startswith(('global.', 'scr_', 'murdererlv', 'instance_exists',
                               'read', 'dognumber', 'obj_')):
                plot.append(a)
            else:
                other.append(a)
        if room is None:
            continue
        groups[(room, obj_of(alarm))].append({
            'key': key, 'target': target, 'pos': pos, 'plot': plot, 'other': other,
        })

    multi = {k: v for k, v in groups.items() if len(v) > 1}
    print('组合 %d 个，其中多条候选 %d 个' % (len(groups), len(multi)))
    print('')

    by_kind = collections.Counter()
    for k, vs in multi.items():
        has_pos = any(v['pos'] for v in vs)
        has_plot = any(v['plot'] for v in vs)
        has_other = any(v['other'] for v in vs)
        if has_pos and not has_plot and not has_other:
            by_kind['仅位置可分'] += 1
        elif has_pos:
            by_kind['位置+其它'] += 1
        elif has_plot and not has_other:
            by_kind['仅剧情可分'] += 1
        else:
            by_kind['其它'] += 1
    print('多条候选的分类：%s' % dict(by_kind))
    print('')

    print('== 逐组（只列前 20，按候选数降序）==')
    for k, vs in sorted(multi.items(), key=lambda kv: -len(kv[1]))[:20]:
        print('%s / %s  ×%d' % (k[0], k[1], len(vs)))
        for v in vs:
            print('    %-8s pos=%s plot=%s key=%s'
                  % (v['target'], '&'.join(v['pos']) or '-',
                     '&'.join(v['plot']) or '-', v['key']))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
