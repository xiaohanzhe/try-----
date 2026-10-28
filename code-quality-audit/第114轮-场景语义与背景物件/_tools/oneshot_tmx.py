# -*- coding: utf-8 -*-
u"""OneShot `.tmx` / `.tsx` 解析 —— 第114轮“场景语义”唯一数据入口。

链路（照 RPG Maker XP / Tiled 的存法，逐层拆到底）：

    mapN.tmx ──<tileset firstgid=.. source=../xxx.tsx/>──► xxx.tsx ──<image source=..>──► 图集 png
        │                                                     │
        │ <layer><data encoding="csv">gid,x,y…</data>          └─ tilecount / columns / tilewidth
        ▼
    每格 gid → (哪个 tsx, 它的局部 id) → 图集里第 (lid%cols, lid//cols) 块 16×16

★★★ 第114轮的核心发现（推翻了“拆走物件要补洞”这个前提）：
  262/263 间房都是 **3 个 tile layer**：
    L0 = 地面/墙体（整房铺满）
    L1 = 画在上面的**物件**（家具、招牌、水面上的东西…）
    L2 = 再上层（少量）
  ⇒ 拆一个 L1 物件 = “少画那几格”，底下 L0 的地板天然露出来，**不需要任何回填算法**。
  实测 map2/3/4 的 L1 物件格 **106/106 全部有 L0 垫底**（`census_objects114.py` 会全量复算）。

★ 之前为什么会“留洞”：拿 `assets/scenes/bg/oneshot_map*.png`（**合成后**的整张图）当底图
  去“整格复制地板”，于是砖缝接缝指标 9.31 → 81.49（恶化 9 倍）。
  ★★ 但「那批 PNG 不可信」是**我自己搞错了**（第114轮后段已撤回，见 `bg_base114.py`）：
  它们是第100/101轮从**同一份 tmx** 合成的，把底色层（`oneshot_map_colors.json`）补上之后，
  **222/263 间逐像素差异 ≤1%**（中位 0.0000、`map1` = 0.0000），剩 41 间 1%~12.5% 的差异
  几乎全在**半透明瓦片**（我给 alpha 109~115、PNG 给 192~193）。
  错位负控制（右移一格）差异涨到 0.11~0.40 ⇒ 判据看得见错位，说明**版面是对的**。
  **要换掉这些 PNG 的理由不成立。**

零依赖：只用标准库（`xml.etree` / `re` / `os`）。读游戏文件，不写任何东西。
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

#: 游戏数据目录。换机器／换版本时用环境变量 `ONESHOT_GD` 覆盖，别改代码。
#: ★★ 第114轮实测：这个目录**被挪过位置**（`桌面\珍贵的回忆\` → `桌面\项目文件夹\珍贵的回忆\`），
#:   写死一个路径就会静默失效（`FileNotFoundError` 或更糟：找到一张旧图继续跑）。
#:   所以这里**按候选探测**，全都不中就抛错并列出试过的路径 —— 报错比“猜一个”安全。
_GD_CANDIDATES = [
    os.environ.get('ONESHOT_GD') or '',
    os.path.join(os.path.expanduser('~'), 'Desktop', u'项目文件夹', u'珍贵的回忆',
                 'OneShot.World.Machine.Edition.Build.16512634', 'gamedata'),
    os.path.join(os.path.expanduser('~'), 'Desktop', u'珍贵的回忆',
                 'OneShot.World.Machine.Edition.Build.16512634', 'gamedata'),
    os.path.join(os.path.expanduser('~'), 'Desktop', 'OneShot.World.Machine.Edition.'
                 'Build.16512634', 'gamedata'),
]


def _find_gd():
    tried = []
    for p in _GD_CANDIDATES:
        if not p:
            continue
        tried.append(p)
        if os.path.isdir(os.path.join(p, 'maps')):
            return p
    # 再扫一层 Desktop：用户的目录名可能带版本号变化
    desk = os.path.join(os.path.expanduser('~'), 'Desktop')
    for root in (desk, os.path.join(desk, u'项目文件夹')):
        if not os.path.isdir(root):
            continue
        for n in sorted(os.listdir(root)):
            if 'OneShot' not in n:
                continue
            p = os.path.join(root, n, 'gamedata')
            tried.append(p)
            if os.path.isdir(os.path.join(p, 'maps')):
                return p
    raise RuntimeError(
        u'找不到 OneShot 的 gamedata（试过 %d 个路径）：\n  %s\n'
        u'⇒ 设环境变量 ONESHOT_GD 指向 gamedata 目录。'
        % (len(tried), u'\n  '.join(tried)))


GD = _find_gd()
MAPS = os.path.join(GD, 'maps')

_tsx_cache = {}


def parse_tsx(path):
    u"""读 `.tsx`。注意 `image source` 是**相对 tsx 自己的目录**（实测是 `../../Content/...`）。"""
    if path in _tsx_cache:
        return _tsx_cache[path]
    root = ET.parse(path).getroot()
    d = {'name': root.get('name') or os.path.basename(path),
         'dir': os.path.dirname(path),
         'tw': int(root.get('tilewidth') or 16),
         'th': int(root.get('tileheight') or 16),
         'count': int(root.get('tilecount') or 0),
         'cols': int(root.get('columns') or 1),
         'img': None, 'iw': 0, 'ih': 0,
         'tileprops': {}}
    im = root.find('image')
    if im is not None:
        d['img'] = im.get('source')
        d['iw'] = int(im.get('width') or 0)
        d['ih'] = int(im.get('height') or 0)
    for t in root.findall('tile'):
        props = dict((p.get('name'), p.get('value'))
                     for p in t.findall('properties/property'))
        if props:
            d['tileprops'][int(t.get('id'))] = props
    _tsx_cache[path] = d
    return d


def load_map(num):
    u"""读一张图。返回 dict：`W/H/TW/TH`（格数与格子像素）、`sets`、`layers`、`objgroups`。"""
    p = os.path.join(MAPS, 'map%d.tmx' % num)
    root = ET.parse(p).getroot()
    m = {'num': num, 'path': p,
         'W': int(root.get('width')), 'H': int(root.get('height')),
         'TW': int(root.get('tilewidth')), 'TH': int(root.get('tileheight')),
         'sets': [], 'layers': [], 'objgroups': [], 'groups': 0}
    m['groups'] = len(root.findall('group'))
    for ts in root.findall('tileset'):
        fg = int(ts.get('firstgid'))
        src = ts.get('source')
        if not src:
            continue
        tsx = os.path.normpath(os.path.join(MAPS, src))
        if not os.path.isfile(tsx):
            continue
        m['sets'].append((fg, tsx, parse_tsx(tsx)))
    m['sets'].sort(key=lambda r: r[0])
    for ly in root.findall('layer'):
        data = ly.find('data')
        if data is None or (data.get('encoding') or '') != 'csv':
            continue
        nums = [int(x) for x in re.findall(r'-?\d+', data.text or '')]
        m['layers'].append({'name': ly.get('name'),
                            'w': int(ly.get('width') or m['W']),
                            'h': int(ly.get('height') or m['H']),
                            'data': nums,
                            'opacity': float(ly.get('opacity') or 1.0)})
    for og in root.findall('objectgroup'):
        objs = []
        for o in og.findall('object'):
            objs.append({'name': o.get('name'), 'type': o.get('type'),
                         'x': o.get('x'), 'y': o.get('y'),
                         'w': o.get('width'), 'h': o.get('height'),
                         'gid': o.get('gid')})
        m['objgroups'].append({'name': og.get('name'), 'objs': objs})
    return m


def gid_to(m, gid):
    u"""gid → (tsx 路径, tsx 信息, 局部 id)。`gid<=0` 或超出 tilecount ⇒ None。"""
    gid = gid & 0x1FFFFFFF                 # 高位是翻转标志，不是编号
    if gid <= 0:
        return None
    best = None
    for fg, tsx, d in m['sets']:
        if gid >= fg:
            best = (fg, tsx, d)
        else:
            break
    if not best:
        return None
    fg, tsx, d = best
    lid = gid - fg
    if d['count'] and lid >= d['count']:
        return None
    return tsx, d, lid


def cell(m, layer, x, y):
    u"""取某层某格的 gid（越界返 0）。"""
    w = layer['w']
    i = y * w + x
    return layer['data'][i] if 0 <= i < len(layer['data']) else 0


def clusters(m, layer, tsx_path=None, only_with_floor_below=False,
             with_detail=False):
    u"""同一层内 4-连通聚类 ⇒ 一个“画在一起的东西”。

    参数
    ----
    tsx_path : 只聚某个 tsx 的格子（None = 本层所有非空格一起聚，跨图集也算连通）
    only_with_floor_below : 只保留“底下 L0 有东西”的格子（= 可拆物件，见模块说明）
    with_detail : 额外返回 `detail` = [(dx, dy, tsx 基名, 局部 id), …]（相对 bbox 原点）。
                  ★★ 「图案签名」靠它：同一张图在别的房间重用 ⇒ 签名一致 ⇒ **只需命名一次**。
                  默认关掉，因为普查有 4000 多块，多存一份明细会明显变慢／变大。

    ★ 为什么按 tsx 分开聚也可用：同一次连通里混不同图集是正常的（一个物件由多张图拼成），
      所以默认**不按 tsx 分**；要按图集看细节时再传 `tsx_path`。
    """
    w, h = layer['w'], layer['h']
    L0 = m['layers'][0] if m['layers'] else None
    cells = {}
    for i, g in enumerate(layer['data']):
        r = gid_to(m, g)
        if not r:
            continue
        if tsx_path is not None and r[0] != tsx_path:
            continue
        x, y = i % w, i // w
        if only_with_floor_below:
            if not L0 or not gid_to(m, (L0['data'][y * L0['w'] + x]
                                        if y * L0['w'] + x < len(L0['data']) else 0)):
                continue
        cells[(x, y)] = (r[2], os.path.basename(r[0]))
    seen, out = set(), []
    for c in list(cells.keys()):
        if c in seen:
            continue
        stack, comp = [c], []
        seen.add(c)
        while stack:
            cx, cy = stack.pop()
            comp.append((cx, cy, cells[(cx, cy)]))
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (cx + dx, cy + dy)
                if n in cells and n not in seen:
                    seen.add(n)
                    stack.append(n)
        xs = [a for a, _, _ in comp]
        ys = [b for _, b, _ in comp]
        x0, y0 = min(xs), min(ys)
        d = {'x0': x0, 'y0': y0, 'x1': max(xs), 'y1': max(ys),
             'cw': max(xs) - x0 + 1, 'ch': max(ys) - y0 + 1,
             'cells': len(comp),
             'lids': sorted(set(c[0] for _, _, c in comp))}
        if with_detail:
            d['detail'] = sorted((ax - x0, ay - y0, c[1], c[0]) for ax, ay, c in comp)
        out.append(d)
    out.sort(key=lambda r: (-r['cells'], r['y0'], r['x0']))
    return out


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    nums = [int(x) for x in sys.argv[1:]] or [2]
    for n in nums:
        m = load_map(n)
        print(u'map%d %dx%d 格  tile=%dx%d  → %dx%d px  层=%d  图集=%d'
              % (n, m['W'], m['H'], m['TW'], m['TH'], m['W'] * m['TW'],
                 m['H'] * m['TH'], len(m['layers']), len(m['sets'])))
        for i, ly in enumerate(m['layers']):
            used = sum(1 for g in ly['data'] if gid_to(m, g))
            print(u'  L%d %-14r 非空 %d 格' % (i, ly['name'], used))
