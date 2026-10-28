# -*- coding: utf-8 -*-
u"""对 `objects_name114.py` 的产物做**独立对账**（判据也是被测物，所以不引用它的汇总行）。

被验对象：`_evidence/objects_lib.json` + `oneshot_objects_todo.csv` / `.txt` + `thumbs/index.json`
参照物  ：`_evidence/objects_l1l2.json`（普查产物，另一支工具算出来的）+ 渲染图实际像素尺寸

判据（每条都成对，带负控制）：
  V1  三类签名（todo / named / solid_only）两两不相交，并集 = 全部签名
  V2  Σn 守恒：三类的块数加起来 = 普查的 4380，且 = 全库签名块数
  V3  todo 里不许出现任何原作名字（这是“待填”的定义）
  V4  CSV 数据行数 = todo 类数；编号唯一、连续
  V5  每条 todo 的裁剪框都落在对应渲染图内（否则缩略图会是空白/红线）
  V6  thumbs/index.json 覆盖全部 todo 编号，行列在 [0,6) 内且不重复占位
  V7  负控制：故意塞一个带名字的块进 todo，V3 必须报红（判据不是恒真）

用法：python check_name114.py
"""
import collections
import csv
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EV = os.path.normpath(os.path.join(HERE, '..', '_evidence'))

res = []


def ck(name, ok, detail=''):
    res.append((name, bool(ok), detail))
    print(u'[%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                          (u'  ' + detail) if detail else ''))


def main():
    lib = json.load(io.open(os.path.join(EV, 'objects_lib.json'), encoding='utf-8'))
    cen = json.load(io.open(os.path.join(EV, 'objects_l1l2.json'), encoding='utf-8'))
    todo, named, solid = lib['todo'], lib['named'], lib['solid_only']

    # V1 三类互斥且穷尽
    st = set(e['sig'] for e in todo)
    sn = set(e['sig'] for e in named)
    ss = set(e['sig'] for e in solid)
    inter = (st & sn) | (st & ss) | (sn & ss)
    ck(u'V1 三类签名互不相交且并集=全部',
       not inter and len(st | sn | ss) == lib['totals']['sigs'],
       u'交集 %d，并集 %d / 总 %d' % (len(inter), len(st | sn | ss),
                                     lib['totals']['sigs']))

    # V2 Σn 守恒（参照普查的 4380，不是导出器自己的汇总）
    tot = sum(e['n'] for e in todo + named + solid)
    ck(u'V2 Σ块数 = 普查 4380', tot == cen['totals']['obj'] == 4380,
       u'三类合计 %d / 普查 %d' % (tot, cen['totals']['obj']))

    # V3 待填里不许有名字
    bad3 = [e['code'] for e in todo if e['named']]
    ck(u'V3 待填项不含原作名字', not bad3, u'违规 %d 条' % len(bad3))

    # V4 CSV 行数与编号
    rows = list(csv.reader(io.open(os.path.join(EV, 'oneshot_objects_todo.csv'),
                                   encoding='utf-8-sig')))
    body = rows[1:]
    codes = [r[0] for r in body]
    ck(u'V4 CSV 行数/编号一致',
       len(body) == len(todo) and len(set(codes)) == len(codes)
       and codes == [e['code'] for e in todo],
       u'CSV %d 行 / todo %d 类，唯一编号 %d' % (len(body), len(todo), len(set(codes))))

    # V5 裁剪框在渲染图内
    sizes = {}
    out5 = []
    for e in todo:
        f0 = e['first']
        n = f0['map']
        if n not in sizes:
            p = 'D:/_tmp/render_all/map%d.png' % n
            if os.path.isfile(p):
                sizes[n] = __import__('PIL.Image', fromlist=['Image']).open(p).size
            else:
                sizes[n] = None
        sz = sizes[n]
        if sz is None:
            out5.append(u'%s(map%d 无渲染图)' % (e['code'], n))
            continue
        px = f0['px']
        if not (0 <= px[0] < px[2] <= sz[0] and 0 <= px[1] < px[3] <= sz[1]):
            out5.append(u'%s(%s 越界 %s)' % (e['code'], n, px))
    ck(u'V5 裁剪框都在渲染图内', not out5, u'越界 %d 条 %s' % (len(out5), out5[:3]))

    # V6 缩略图索引
    idx = json.load(io.open(os.path.join(EV, 'thumbs', 'index.json'), encoding='utf-8'))
    cs = idx['cells']
    miss = [e['code'] for e in todo if e['code'] not in cs]
    cells = collections.Counter((v['file'], v['row'], v['col']) for v in cs.values())
    dup = [k for k, v in cells.items() if v > 1]
    rng = [(k, v['row'], v['col']) for k, v in cs.items()
           if not (0 <= v['row'] < idx['rows'] and 0 <= v['col'] < idx['cols'])]
    ck(u'V6 缩略图索引覆盖且不重叠',
       not miss and not dup and not rng,
       u'缺 %d / 重 %d / 越界 %d' % (len(miss), len(dup), len(rng)))

    # V7 负控制：往 todo 里塞一个带名字的副本，V3 的判据必须报红
    fake = dict(todo[0])
    fake['named'] = [u'__negative_control__']
    poisoned = [fake] + list(todo[1:])
    red = bool([e['code'] for e in poisoned if e['named']])
    ck(u'V7 负控制（V3 判据不是恒真）', red, u'注入带名块后判据%s' %
       (u'报红=有效' if red else u'仍全绿=判据失效'))

    ok = all(r[1] for r in res)
    print(u'\n%s  共 %d 条，PASS %d / FAIL %d'
          % (u'全绿' if ok else u'有红', len(res),
             sum(1 for r in res if r[1]), sum(1 for r in res if not r[1])))
    return 0 if ok else 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
