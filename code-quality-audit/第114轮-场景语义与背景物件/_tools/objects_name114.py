# -*- coding: utf-8 -*-
u"""把「背景物件普查」变成**用户能直接填的清单** —— 第114轮交付物生成器。

用户口径（原话）：
  「如果有些背景图里拆下来的物品没有对应的功能简介，列出来，我后期自己填写」

问题在于**量**：263 间房共 4380 个物件块，其中 3456 块没有原作名字。
让人逐块填 = 3456 行，不现实。

★ 破局点：**同一个 sprite 在几十个房间里重用**。
  把每个块表示成「图案签名」= 主图集名 + 相对 bbox 原点的逐格 `(dx, dy, tsx, 局部id)`，
  签名相同的块在外观上是同一件东西（位置/房间不同而已）。
  实测：3456 个无名块 → **711 类**；4380 个块总数 → 1200 类。
  用户在 711 行上填一次名，1938 个无名块全部有名字。

★★ 签名忽略 gid 翻转位 —— 这是**故意**的，而且已经验证安全：
  `probe_flip114.py` 实测 263 间房**没有任何一格**使用 `0x80000000/0x40000000/0x20000000`。
  ⇒ 按局部 id 合并不会把镜像件错并，`render_room.py` 不做镜像也是对的。
  （若将来换版本后出现翻转，这个探针会报红，届时签名要带上翻转位。）

产物（都在 `_evidence/`，不入库大图）：
  objects_lib.json            全量图案库（含每类出现位置，11 MB 级，供后续工具用）
  oneshot_objects_todo.csv    711 行待填清单（UTF-8 **带 BOM**，Excel/WPS 直接开不乱码）
  oneshot_objects_todo.txt    同上，人读版，按覆盖面积降序
  oneshot_objects_named.txt   已带原作名字的对照表（924 块 / 489 类），供起名时沿用原作措辞

不做的事：**不猜名字**。留空列给人填，宁可空着也不编。
"""
import collections
import csv
import hashlib
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import oneshot_tmx as T

EV = os.path.normpath(os.path.join(HERE, '..', '_evidence'))
SRC = os.path.join(EV, 'objects_l1l2.json')
#: 本身就是地面的块（`kind == 'solid'`）没有“拆”这回事，不进待填清单，只计数。
KIND_ORDER = {'removable': 0, 'partial': 1, 'solid': 2}

# ★★ 「有名字」的**可信口径**（第一版直接用普查的 `o['named']`，实测有 190 块是假的）：
#   · `pixel 0,0`（495 个）、`Map Events`、`init`、`noloop`、`force meet` 这些是**元事件**，
#     等于没名字；普查把它们当名字数了 51 块「名字全是元事件」。
#   · 大块（>64 格）会把一屋子事件全吸进 bbox —— `map40 Alula` 整张图是**一个** 70×70
#     连通块，挂了 35 个名字。给它挂什么名字都是错的。
#   ⇒ 只有「非元事件名 + cells<=64」才算真有名。收紧后 924 → 734 块，190 块回到待填。
#   ★ 小件挂多名是**合法**的（`bed top left / bed bottom right` 就是一个床的四个角），不砍。
_META = re.compile(r'^(pixel \d+,\d+$|map events$|init$|noloop$|force meet$|'
                   r'you tried$|!.*)', re.I)
ITEM_MAX_CELLS = 64   # 同时用作「真有名」的块大小上限、A/B 组分界线


def sig_of(detail):
    u"""图案签名。detail 已相对 bbox 原点 ⇒ 同一图案在别处出现时签名相同。"""
    key = ';'.join('%d,%d,%s,%d' % t for t in detail)
    return hashlib.sha1(key.encode('utf-8')).hexdigest()[:10]


def kind_of(e):
    u"""一个图案里可能既有 removable 也有 solid 实例，取「最像物件」的那个定性。"""
    return min(e['kind'], key=lambda k: KIND_ORDER.get(k, 9))


def short_auto(e, n=4):
    u"""自动编号只列前几个 —— 一个 38 块的图案能带 40 多个 `EV###`，全列出来只是噪音。"""
    a = sorted(e['auto'])
    if not a:
        return u''
    tail = u' …共%d个' % len(a) if len(a) > n else u''
    return u' '.join(a[:n]) + tail


def main():
    census = json.load(io.open(SRC, encoding='utf-8'))
    rooms = census['rooms']
    meta = dict((r['map'], r) for r in rooms)

    # ---- 1. 用普查结果建 (map, layer, 完整 bbox) → 该块的原作命名/自动编号 ----
    # ★★ 键必须用**完整 bbox**，不能用 (x0, y0)：实测 map37 L1 (49,50) 和 map121 L1 (51,14)
    #    各有一对块共用左上角（一个 1×1 孤立格正好压在大块的左上格斜对角上，
    #    4-连通里它们不相连，但 bbox 起点相同）。拿 (x0,y0) 当键会**静默覆盖**掉一个块，
    #    而且总数照样对得上（4380 不会变）—— 只有 assert 能抓住。
    idx = {}
    for r in rooms:
        for o in r['objects']:
            k = (r['map'], o['layer'], o['x0'], o['y0'], o['x1'], o['y1'], o['cells'])
            assert k not in idx, u'普查里出现重复块键 %r' % (k,)
            idx[k] = o

    # ---- 2. 重算聚类（这次带逐格明细），按签名聚合 ----
    lib = collections.OrderedDict()
    seen_keys = set()
    n_blocks = 0
    for r in rooms:
        m = T.load_map(r['map'])
        for li in range(1, len(m['layers'])):
            for c in T.clusters(m, m['layers'][li], with_detail=True):
                n_blocks += 1
                k = (r['map'], li, c['x0'], c['y0'], c['x1'], c['y1'], c['cells'])
                o = idx.get(k)
                assert o is not None, u'聚类块 %r 在普查里找不到（两次聚类不一致）' % (k,)
                seen_keys.add(k)
                s = sig_of(c['detail'])
                e = lib.get(s)
                if e is None:
                    e = lib[s] = {
                        'sig': s, 'n': 0, 'cells': 0,
                        # ★★ `cells` 是**所有实例累计**（给“覆盖面积”用）；
                        #    `each` 才是**单块格数**。拿累计值去和 64 比分类是错的：
                        #    “3 格的东西出现 50 次” 会算成 150 格，被判进“大面积拼合”。
                        'each': c['cells'],
                        'cw': c['cw'], 'ch': c['ch'],
                        'tsx': sorted(set(d[2] for d in c['detail'])),
                        'kind': collections.Counter(),
                        'named': set(), 'auto': set(),
                        'rooms': set(), 'inst': [],
                    }
                assert e['each'] == c['cells'], (
                    u'同一签名的单块格数不一致 %s: %d vs %d' % (s, e['each'], c['cells']))
                e['n'] += 1
                e['cells'] += c['cells']
                e['kind'][o['kind']] += 1
                # ★ 名字只认「小块 + 非元事件」；大块吸进来的名字一律不收（理由见文件头）
                if c['cells'] <= ITEM_MAX_CELLS:
                    for nm in o['named']:
                        if not _META.match(nm):
                            e['named'].add(nm)
                for nm in o.get('auto_named') or []:
                    e['auto'].add(nm)
                e['rooms'].add(r['map'])
                e['inst'].append({'map': r['map'], 'room': r['name'], 'layer': li,
                                  'x0': c['x0'], 'y0': c['y0'],
                                  'px': [c['x0'] * m['TW'], c['y0'] * m['TH'],
                                         (c['x1'] + 1) * m['TW'],
                                         (c['y1'] + 1) * m['TH']],
                                  'kind': o['kind'], 'cells': c['cells']})
    assert len(seen_keys) == len(idx), (
        u'聚类总数 %d ≠ 普查总数 %d ⇒ 有一边漏块' % (len(seen_keys), len(idx)))
    print(u'复核：聚类块 %d 与普查块 %d 一一对上' % (n_blocks, len(idx)))

    # ---- 3. 分三类：有真名 / 只有自动编号 / 完全没名 ----
    named_sigs = [e for e in lib.values() if e['named']]
    todos = [e for e in lib.values() if not e['named'] and kind_of(e) != 'solid']
    solid_only = [e for e in lib.values() if not e['named'] and kind_of(e) == 'solid']

    # ★★ 排序口径（第一版按面积排，结果「79×15 的整面楼」排第一 —— 那种一坨是
    #   4-连通把贴在一起的墙/窗/门并起来的产物，不是“物品”，让人给它起名毫无意义）：
    #   按**单块格数** `each` 分线（不是累计格数，累计会把“3 格的东西出现 50 次”算成 150）。
    #   ⇒ A 组（典型物件，each<=64 = 8×8 格 = 128×128 px 以内）按**复用块数**降序：
    #      一次命名覆盖最多块；B 组（大面积拼合）按单块面积降序单列。
    items = [e for e in todos if e['each'] <= ITEM_MAX_CELLS]
    blobs = [e for e in todos if e['each'] > ITEM_MAX_CELLS]
    items.sort(key=lambda e: (-e['n'], -e['each'], e['sig']))
    blobs.sort(key=lambda e: (-e['each'], -e['n'], e['sig']))
    for i, e in enumerate(items, 1):
        e['code'] = 'A%03d' % i
        e['group'] = u'典型物件'
    for i, e in enumerate(blobs, 1):
        e['code'] = 'B%03d' % i
        e['group'] = u'大面积拼合'
    todos = items + blobs
    named_sigs.sort(key=lambda e: (-e['n'], -e['cells'], e['sig']))
    for i, e in enumerate(named_sigs, 1):
        e['code'] = 'N%03d' % i

    # ---- 4. 落盘：全量库 ----
    def dump(e):
        return {'code': e.get('code'), 'group': e.get('group'), 'sig': e['sig'],
                'n': e['n'],
                'cells': e['cells'], 'size': [e['cw'], e['ch']],
                'tsx': e['tsx'], 'kind': dict(e['kind']),
                'named': sorted(e['named']), 'auto': sorted(e['auto']),
                'rooms': sorted(e['rooms']),
                'first': e['inst'][0], 'inst': e['inst']}

    libout = {
        'note': u'图案签名库：同一签名=同一张图的样子，命名一次覆盖全部出现位置',
        'totals': {
            'blocks': n_blocks,
            'sigs': len(lib),
            'named_sigs': len(named_sigs),
            'item_sigs': len(items),
            'item_blocks': sum(e['n'] for e in items),
            'blob_sigs': len(blobs),
            'blob_blocks': sum(e['n'] for e in blobs),
            'todo_sigs': len(todos),
            'solid_only_sigs': len(solid_only),
            'todo_blocks': sum(e['n'] for e in todos),
            'todo_cells': sum(e['cells'] for e in todos),
        },
        'todo': [dump(e) for e in todos],
        'named': [dump(e) for e in named_sigs],
        'solid_only': [dump(e) for e in solid_only],
    }
    p_lib = os.path.join(EV, 'objects_lib.json')
    with io.open(p_lib, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(libout, ensure_ascii=False, indent=1))
    print(u'图案库 → %s (%.1f MB)' % (p_lib, os.path.getsize(p_lib) / 1048576.0))

    # 缩略图位置（由 thumbs114.py 生成；没生成就不打印那一行）
    p_thumbs = os.path.join(EV, 'thumbs', 'index.json')
    thumbs = {}
    if os.path.isfile(p_thumbs):
        thumbs = json.load(io.open(p_thumbs, encoding='utf-8')).get('cells') or {}
        print(u'缩略图索引 → 已载入 %d 条' % len(thumbs))

    # ---- 5. 待填 CSV（带 BOM，Excel 直开不乱码）----
    p_csv = os.path.join(EV, 'oneshot_objects_todo.csv')
    with io.open(p_csv, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow([u'编号', u'分组', u'图案编号', u'出现块数', u'覆盖格数', u'尺寸(格)',
                    u'主图集', u'类型', u'首次出现', u'出现房间数', u'缩略图',
                    u'原作给过的自动编号', u'★中文名（待填）', u'★功能说明（待填）'])
        for e in todos:
            f0 = e['inst'][0]
            th = thumbs.get(e['code'])
            w.writerow([
                e['code'], e['group'], e['sig'], e['n'], e['cells'],
                u'%dx%d' % (e['cw'], e['ch']),
                e['tsx'][0] if e['tsx'] else '', kind_of(e),
                u'map%d %s' % (f0['map'], f0['room']), len(e['rooms']),
                (u'%s 第%d行第%d列' % (th['file'], th['row'] + 1, th['col'] + 1)
                 if th else ''),
                short_auto(e), u'', u''])
    print(u'待填清单 → %s（%d 行）' % (p_csv, len(todos)))

    # ---- 6. 待填人读版 ----
    p_txt = os.path.join(EV, 'oneshot_objects_todo.txt')
    with io.open(p_txt, 'w', encoding='utf-8', newline='\n') as f:
        f.write(u'OneShot 背景物件 · 待命名清单\n')
        f.write(u'=' * 60 + u'\n')
        f.write(u'共 %d 类图案 / %d 个物件块 / %d 格。\n'
                % (len(todos), sum(e['n'] for e in todos),
                   sum(e['cells'] for e in todos)))
        f.write(u'每个图案只需填一次，所有出现位置共用。\n')
        f.write(u'「类型」= removable（可整块拆走，底下就是地板）/ '
                u'partial（部分格没地板垫底）。\n')
        f.write(u'填完把本文件发回即可，中文名和功能说明都只在 ★ 后面那两行。\n\n')
        f.write(u'A 组「典型物件」%d 类 / %d 块 —— 按复用块数降序，'
                u'先填前面的，一次命名覆盖最多地方。\n'
                % (len(items), sum(e['n'] for e in items)))
        f.write(u'B 组「大面积拼合」%d 类 / %d 块 —— 4-连通把贴在一起的墙/窗/门并成了'
                u'一坨（有的一张就 79×15 格），是场景结构不是物品，放在最后，\n'
                u'    不想填可以整组留空。\n\n'
                % (len(blobs), sum(e['n'] for e in blobs)))
        for grp, arr, head in ((u'典型物件', items, u'A'),
                               (u'大面积拼合', blobs, u'B')):
            f.write(u'\n')
            f.write(u'#' * 60 + u'\n')
            f.write(u'#  %s 组（%d 类 / %d 块）\n'
                    % (grp, len(arr), sum(e['n'] for e in arr)))
            f.write(u'#' * 60 + u'\n\n')
            for e in arr:
                f0 = e['inst'][0]
                f.write(u'[%s] %d 块 / %d 格 / %dx%d %s\n'
                        % (e['code'], e['n'], e['cells'], e['cw'], e['ch'],
                           kind_of(e)))
                f.write(u'  图集：%s\n' % u', '.join(e['tsx']))
                f.write(u'  首见：map%d %s  第 %d 层，格 (%d,%d)，px %s\n'
                        % (f0['map'], f0['room'], f0['layer'], f0['x0'], f0['y0'],
                           f0['px']))
                f.write(u'  出现于 %d 间房\n' % len(e['rooms']))
                th = thumbs.get(e['code'])
                if th:
                    f.write(u'  看样：_evidence/thumbs/%s  第 %d 行第 %d 列\n'
                            % (th['file'], th['row'] + 1, th['col'] + 1))
                if e['auto']:
                    f.write(u'  原作自动编号：%s\n' % short_auto(e))
                f.write(u'  ★中文名：\n')
                f.write(u'  ★功能说明：\n\n')
    print(u'待填人读版 → %s' % p_txt)

    # ---- 7. 已有名字的对照表 ----
    p_named = os.path.join(EV, 'oneshot_objects_named.txt')
    with io.open(p_named, 'w', encoding='utf-8', newline='\n') as f:
        f.write(u'OneShot 背景物件 · 原作已有名字（起名时沿用这些措辞）\n')
        f.write(u'=' * 60 + u'\n')
        f.write(u'%d 类图案 / %d 块。名字来自 `events_mapN.json` 的事件名。\n\n'
                % (len(named_sigs), sum(e['n'] for e in named_sigs)))
        for e in named_sigs:
            f0 = e['inst'][0]
            f.write(u'[%s] %s\n' % (e['code'], u' / '.join(sorted(e['named']))))
            f.write(u'  %d 块 / %d 格 / %dx%d  map%d %s 第%d层 (%d,%d)\n\n'
                    % (e['n'], e['cells'], e['cw'], e['ch'],
                       f0['map'], f0['room'], f0['layer'], f0['x0'], f0['y0']))
    print(u'已有名字对照 → %s（%d 类）' % (p_named, len(named_sigs)))

    t = libout['totals']
    print(u'\n汇总：块 %d / 图案 %d｜已有名字 %d 类｜待填 %d 类（%d 块）｜纯地面 %d 类'
          % (t['blocks'], t['sigs'], t['named_sigs'], t['todo_sigs'],
             t['todo_blocks'], t['solid_only_sigs']))


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    main()
