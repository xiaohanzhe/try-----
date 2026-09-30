# -*- coding: utf-8 -*-
u"""第66轮 · 把复检要读的 GML **蒸馏进仓**。

★★ 为什么必须做（本项目铁律，第44轮立的规矩）
------------------------------------------------
`recheck66.py` 的 ⑥ 段要"真实回查源码"来证明判非门的判别力（抽查 8 条
non-door-superseded + 2 个正控制 + 1 个反向控制）。而 GML 转储躺在
`E:\\Download\\_extract61\\...` —— **外部盘 + 用后即删的转储区**。
回归/复检依赖它 = 盘一掉线，判据要么报红、要么**静默变成假绿**。

⇒ 一次性把复检会读到的 GML 全部复制进 `_evidence/gml_evidence66/`，
  复检改成读仓内目录（与第65轮把 19 个 GML 蒸馏进 `gml_evidence65/` 同一套做法）。

蒸馏范围（**宁多勿少**）
------------------------
① `bigmap66.json` 的 `non_doors[].events` 引用的**全部**唯一文件（102 个）；
② 3 个控制文件（正控制 2 + 反向控制 1，可能与 ① 重叠）。

用法：python distill_gml66.py
"""
from __future__ import print_function

import io
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
EV = os.path.join(ROUND, '_evidence')
DESC = os.path.join(EV, 'gml_evidence66')

GML = {
    'ut': r'E:\Download\_extract61\_data\undertale\u65\gml65ut',
    'uty': r'E:\Download\_extract61\_data\undertale_yellow\uty65\gml65',
    'ry': r'E:\Download\_extract64\assets\redyellow65\gml65',
}

#: 复检 ⑥ 段直接按文件名读的 3 个控制文件（work, filename）。
CONTROLS = [
    ('uty', 'gml_Object_obj_hiddenentrance_Step_0.gml'),
    ('ut', 'gml_Object_obj_door_t_Alarm_2.gml'),
    ('uty', 'gml_Object_obj_doorway_Collision_obj_pl.gml'),
]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    b = json.load(io.open(os.path.join(EV, 'bigmap66.json'), encoding='utf-8'))
    want = set()
    for x in b['non_doors']:
        for fn in (x.get('events') or []):
            want.add((x['work'], fn))
    for w, fn in CONTROLS:
        want.add((w, fn))

    print(u'需蒸馏 %d 个 (work, file)' % len(want))
    copied, missing = [], []
    for w, fn in sorted(want):
        src = os.path.join(GML.get(w, ''), fn)
        if not os.path.isfile(src):
            missing.append((w, fn))
            continue
        dst_dir = os.path.join(DESC, w)
        if not os.path.isdir(dst_dir):
            os.makedirs(dst_dir)
        shutil.copyfile(src, os.path.join(dst_dir, fn))
        copied.append((w, fn))

    print(u'已复制 %d 个；缺 %d 个' % (len(copied), len(missing)))
    if missing:
        for w, fn in missing[:10]:
            print(u'  MISSING %s/%s' % (w, fn))

    # ---- manifest：把"蒸馏时的事实"钉下来，复检拿它做守恒判据 ----
    man = {
        'source': dict((k, v.replace('\\', '/')) for k, v in GML.items()),
        'note': (u'第66轮复检 ⑥ 段要回查的 GML（non_doors 引用的全部事件 + 3 个控制文件）。'
                 u'★ 蒸馏进仓的理由：转储在 E 盘、用后即删 ⇒ 回归/复检不许依赖它。'),
        'n_expected': len(want),
        'n_copied': len(copied),
        'missing': [{'work': w, 'file': fn} for w, fn in missing],
        'controls': [{'work': w, 'file': fn} for w, fn in CONTROLS],
        'files': [{'work': w, 'file': fn, 'bytes': os.path.getsize(
            os.path.join(DESC, w, fn))} for w, fn in sorted(copied)],
        'by_work': {},
    }
    for w, _ in copied:
        man['by_work'][w] = man['by_work'].get(w, 0) + 1
    with io.open(os.path.join(DESC, '_manifest.json'), 'w', encoding='utf-8',
                 newline='\n') as fh:
        fh.write(json.dumps(man, ensure_ascii=False, indent=1) + u'\n')

    print(u'by_work = %s' % json.dumps(man['by_work'], ensure_ascii=False))
    print(u'manifest → %s' % os.path.join(DESC, '_manifest.json'))
    return 0 if not missing else 1


if __name__ == '__main__':
    sys.exit(main())
