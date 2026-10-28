# -*- coding: utf-8 -*-
u"""全量普查：263 间房里 **L1/L2 上的“物件”到底有多少、能不能拆、拆了会不会露洞**。

判据（本脚本唯一的结论口径）：
  · 一个**物件** = 同一层里 4-连通的一坨格子（家具、招牌、水面杂物、墙上的画…）。
  · `floor_below == cells` ⇒ **可拆**：拆掉只是少画那几格，底下 L0 地板天然露出来。
  · `0 < floor_below < cells` ⇒ **部分可拆**：这一坨压在“有地板”和“本来就是地面”的边界上，
    拆了会露洞的部分得单独处理（登记出来，不硬拆）。
  · `floor_below == 0` ⇒ **不可拆**：它就是地面本身（暗世界的草地/水面），拆了整片塌。

产出：`_evidence/objects_l1l2.json`（每间房一份清单 + 全局汇总），可复算、可对账。
零依赖（除 oneshot_tmx）。读游戏文件，只写这一个 JSON。
"""
import argparse
import json
import os
import sys

import oneshot_tmx as T

HERE = os.path.abspath(os.path.dirname(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))


def map_names():
    p = os.path.join(T.GD, 'oneshot_map_names.json')
    if not os.path.isfile(p):
        return {}
    with open(p, 'r', encoding='utf-8') as fh:
        d = json.load(fh)
    return dict((int(x['id']), x.get('name')) for x in (d.get('map_names') or []))


_AUTO_EV = __import__('re').compile(r'^EV\d+$')


def load_events(num):
    u"""读 `events_mapN.json`：原作给每个互动点起的名字 + 它踩在哪一格。

    ★ 为什么要它：物件块本身只有“格子”，没有语义；原作的事件表就是**唯一**的
      人话来源（`fridge left` / `chair` / `north door` / `fire action`）。
      `EV###` 开头的名字是自动编号（等于没名字），要单独标出来 —— 这正是用户要的
      “哪些物件还没有功能简介”的那一批。
    """
    p = os.path.join(T.MAPS, 'events_map%d.json' % num)
    if not os.path.isfile(p):
        return []
    try:
        with open(p, 'r', encoding='utf-8') as fh:
            d = json.load(fh)
    except ValueError:
        return []
    out = []
    for e in (d.get('events') or []):
        name = (e.get('name') or '').strip()
        try:
            x, y = int(e.get('x')), int(e.get('y'))
        except (TypeError, ValueError):
            continue
        out.append({'id': e.get('id'), 'name': name, 'x': x, 'y': y,
                    'named': bool(name) and not _AUTO_EV.match(name)})
    return out


def attach_events(objs, events, tol=1):
    u"""把事件挂到物件块上：事件坐标落在块内（**容差 1 格**，因为事件常踩在物件边上）。

    ★ 容差不能放大：相邻两个物件相距常常只有 2~3 格，放到 2 就会互相抢名字。
      抢错了比没有更糟 —— 模型会照着错名字说话。
    """
    for o in objs:
        hit = [e for e in events
               if o['x0'] - tol <= e['x'] <= o['x1'] + tol
               and o['y0'] - tol <= e['y'] <= o['y1'] + tol]
        o['events'] = [{'id': e['id'], 'name': e['name'], 'x': e['x'], 'y': e['y']}
                       for e in hit]
        o['named'] = [e['name'] for e in hit if e['named']]
        o['auto_named'] = [e['name'] for e in hit if not e['named'] and e['name']]
    return objs


def comps(m, li):
    u"""第 li 层的 4-连通块（含每格坐标，便于算“底下有没有地板”）。"""
    ly = m['layers'][li]
    w = ly['w']
    cells = {}
    for i, g in enumerate(ly['data']):
        if T.gid_to(m, g):
            cells[(i % w, i // w)] = g
    seen, out = set(), []
    for c in list(cells.keys()):
        if c in seen:
            continue
        stack, comp = [c], []
        seen.add(c)
        while stack:
            cx, cy = stack.pop()
            comp.append((cx, cy))
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (cx + dx, cy + dy)
                if n in cells and n not in seen:
                    seen.add(n)
                    stack.append(n)
        out.append(comp)
    return out


def census(nums=None):
    names = map_names()
    if nums is None:
        nums = sorted(int(f[3:-4]) for f in os.listdir(T.MAPS)
                      if f.startswith('map') and f.endswith('.tmx'))
    rooms = []
    tot = {'l1': 0, 'l2': 0, 'obj': 0, 'removable': 0, 'removable_cells': 0,
           'partial': 0, 'solid': 0, 'solid_cells': 0,
           'named': 0, 'auto_only': 0, 'no_event': 0}
    for n in nums:
        try:
            m = T.load_map(n)
        except Exception as e:                          # noqa: BLE001
            print(u'!! map%d 解析失败：%r' % (n, e))
            continue
        L0 = m['layers'][0] if m['layers'] else None
        tw, th = m['TW'], m['TH']
        objs = []
        l1 = l2 = 0
        for li in range(1, len(m['layers'])):
            ly = m['layers'][li]
            ncell = sum(1 for g in ly['data'] if T.gid_to(m, g))
            if li == 1:
                l1 = ncell
            else:
                l2 += ncell
            for comp in comps(m, li):
                fb = 0
                for x, y in comp:
                    g = T.cell(m, L0, x, y) if L0 else 0
                    if T.gid_to(m, g):
                        fb += 1
                xs = [x for x, _ in comp]
                ys = [y for _, y in comp]
                x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
                tilesets = sorted({os.path.basename(T.gid_to(m, T.cell(m, ly, x, y))[0])
                                   for x, y in comp
                                   if T.gid_to(m, T.cell(m, ly, x, y))})
                kind = ('removable' if fb == len(comp)
                        else ('solid' if fb == 0 else 'partial'))
                objs.append({'layer': li, 'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1,
                             'cw': x1 - x0 + 1, 'ch': y1 - y0 + 1,
                             'cells': len(comp), 'floor_below': fb, 'kind': kind,
                             'px': [x0 * tw, y0 * th, (x1 + 1) * tw - 1, (y1 + 1) * th - 1],
                             'tilesets': tilesets})
        objs.sort(key=lambda o: (o['layer'], -o['cells'], o['y0'], o['x0']))
        attach_events(objs, load_events(n))
        for o in objs:
            tot['obj'] += 1
            if o['kind'] == 'removable':
                tot['removable'] += 1
                tot['removable_cells'] += o['cells']
            elif o['kind'] == 'solid':
                tot['solid'] += 1
                tot['solid_cells'] += o['cells']
            else:
                tot['partial'] += 1
            if o['named']:
                tot['named'] += 1
            elif o['auto_named']:
                tot['auto_only'] += 1
            else:
                tot['no_event'] += 1
        tot['l1'] += l1
        tot['l2'] += l2
        rooms.append({'map': n, 'name': names.get(n) or u'?',
                      'w': m['W'], 'h': m['H'], 'tw': tw, 'th': th,
                      'layers': len(m['layers']), 'l1_cells': l1, 'l2_cells': l2,
                      'objects': objs})
    return rooms, tot


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROUND, '_evidence', 'objects_l1l2.json'))
    ap.add_argument('--maps', default='')
    a = ap.parse_args(argv)
    nums = [int(x) for x in a.maps.split(',') if x.strip()] or None
    rooms, tot = census(nums)

    # 只看光世界那几间（Start / Bathroom / Livingroom / Basement）做逐条打印
    show = [r for r in rooms if r['map'] in (2, 3, 4, 5)]
    for r in show:
        print(u'map%-4d %-16s L1=%d 格  物件块=%d'
              % (r['map'], r['name'], r['l1_cells'], len(r['objects'])))
        for o in r['objects'][:8]:
            print(u'   L%d px(%4d,%4d)-(%4d,%4d) %d×%d 格  %2d 格  底下有地板 %2d  → %s'
                  % (o['layer'], o['px'][0], o['px'][1], o['px'][2], o['px'][3],
                     o['cw'], o['ch'], o['cells'], o['floor_below'], o['kind']))

    zero = [r['map'] for r in rooms if r['l1_cells'] == 0]
    empty_obj = [r['map'] for r in rooms if not r['objects']]
    print('')
    print(u'房间 %d 间（L1 全空 %d 间；一个物件块都没有 %d 间）'
          % (len(rooms), len(zero), len(empty_obj)))
    print(u'L1 格 %d / L2 格 %d' % (tot['l1'], tot['l2']))
    print(u'物件块 %d 个：可拆 %d（%d 格）· 部分可拆 %d · 不可拆(地面) %d（%d 格）'
          % (tot['obj'], tot['removable'], tot['removable_cells'],
             tot['partial'], tot['solid'], tot['solid_cells']))
    if tot['obj']:
        # ★ 分母必须是 L1+L2：物件块可能落在 L2（实测 map3 有 4 块在 L2），
        #   拿 L1 当分母会算出 >100% 这种一眼假的数（第一版就是这么写的）。
        base = tot['l1'] + tot['l2']
        print(u'可拆占物件块 %.1f%%；可拆格占 L1+L2 总格 %.1f%%'
              % (100.0 * tot['removable'] / tot['obj'],
                 100.0 * tot['removable_cells'] / max(1, base)))
        n = float(tot['obj'])
        print(u'有原作名字 %d (%.1f%%) · 只有自动编号 EV### %d (%.1f%%) · 一个事件都没有 %d (%.1f%%)'
              % (tot['named'], 100 * tot['named'] / n,
                 tot['auto_only'], 100 * tot['auto_only'] / n,
                 tot['no_event'], 100 * tot['no_event'] / n))

    if a.out:
        d = os.path.dirname(a.out)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        payload = {'note': u'第114轮：OneShot 263 间房的 L1/L2 物件清单。'
                           u'kind=removable 表示底下 L0 有地板 ⇒ 拆走不露洞。',
                   'totals': tot, 'rooms': rooms}
        with open(a.out, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1)
            fh.write('\n')
        print(u'清单 → %s' % a.out)
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))
