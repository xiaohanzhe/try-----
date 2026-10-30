# -*- coding: utf-8 -*-
u"""第120轮合成器：把 UT / Outertale 的房间**烘成一张背景 PNG**。

为什么是"烘"而不是"摆物件"：
    这两款的房间美术是 6.9 万块 legacy tile + 1.4 万个对象实例堆出来的，
    逐块搬进产品当物件会（a）撑爆场景 JSON，（b）每帧几万次 blit。
    产品侧只要一张图就能 1:1 看到原作，交互物（可读物/门）仍然走 `objects`。
    所以：**画面烘成图，交互留成物件**。

画法（严格按 GMS2 的 depth 语义：depth 大 = 更靠后，先画）：
    ① 底色（`room.BackgroundColor`）
    ② 背景层（`LBG`：精灵可平铺/拉伸/纯色填充）
    ③ 图块层（`TLE`：从 `t_<tpag>.png` 抠 (srcX,srcY,w,h) 贴到 (x,y)，可缩放）
    ④ 资源层精灵（`LSP`）
    ⑤ 对象实例（`inst_full.tsv` + `objmap_ut.txt` 的可见性/精灵）
    ⚠️ `vis=False` 的对象**不画**（UT 的碰撞体全是隐形的 obj_solid*）。

用法：
    python bake120.py --game ut --limit 5           # 先烘 5 间看看
    python bake120.py --game ut                     # 全量
"""
import argparse
import io
import os
import sys
from collections import defaultdict

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.dirname(HERE)
WORK = os.environ.get('DUMP_WORK_UT', r'D:\_wb_tmp\dw_ut')

# 第115轮已入库的实例表 / 对象表（ut、outertale 各一份）
RAW115 = os.path.join(os.path.dirname(ROUND), '第115轮-跨作品物件普查', '_evidence', 'raw')


def _rows(path):
    for ln in io.open(path, encoding='utf-8', newline='').read().split('\n'):
        if ln:
            yield ln.split('\t')


def load_viz(path):
    rooms = {}
    layers = defaultdict(list)          # room -> [(idx, name, type, depth, visible)]
    lbg = defaultdict(list)
    lsp = defaultdict(list)
    spr = {}
    for r in _rows(path):
        k = r[0]
        if k == 'ROOM':
            rooms[int(r[1])] = {'name': r[2], 'w': int(r[3]), 'h': int(r[4]),
                                'bgcolor': int(r[5]), 'drawbg': r[6] == 'True'}
        elif k == 'LAYER':
            layers[int(r[1])].append({'i': int(r[2]), 'name': r[3], 'type': r[4],
                                      'depth': int(r[5]), 'vis': r[6] == '1'})
        elif k == 'LBG':
            lbg[int(r[1])].append({'li': int(r[2]), 'spr': r[3],
                                   'x': float(r[4]), 'y': float(r[5]),
                                   'ht': r[6] == '1', 'vt': r[7] == '1',
                                   'stretch': r[8] == '1', 'fg': r[9] == '1',
                                   'vis': r[10] == '1', 'color': int(r[13])})
        elif k == 'LSP':
            lsp[int(r[1])].append({'li': int(r[2]), 'spr': r[4], 'frame': int(r[5]),
                                   'x': int(r[6]), 'y': int(r[7]),
                                   'sx': float(r[8]), 'sy': float(r[9]),
                                   'color': int(r[11])})
        elif k == 'SPR':
            spr[(r[1], int(r[2]))] = {'ox': int(r[4]), 'oy': int(r[5]),
                                      'w': int(r[6]), 'h': int(r[7]),
                                      'bw': int(r[8]), 'bh': int(r[9])}
    return rooms, layers, lbg, lsp, spr


def load_tiles(path):
    tiles = defaultdict(list)
    tps = {}
    for r in _rows(path):
        if r[0] == 'TLE':
            tiles[int(r[1])].append({'depth': int(r[2]), 'tp': int(r[3]),
                                     'x': int(r[4]), 'y': int(r[5]),
                                     'sx': int(r[6]), 'sy': int(r[7]),
                                     'w': int(r[8]), 'h': int(r[9]),
                                     'kx': float(r[10]), 'ky': float(r[11]),
                                     'color': int(r[12]), 'vis': r[13] == '1'})
        elif r[0] == 'TP':
            tps[int(r[1])] = {'bw': int(r[3]), 'bh': int(r[4])}
    return tiles, tps


def load_inst(game):
    path = os.path.join(RAW115, game, 'inst_full.tsv')
    out = defaultdict(list)
    cur = None
    for r in _rows(path):
        if r[0] == 'R':
            cur = int(r[1])
        elif r[0] == 'I' and cur is not None:
            out[cur].append({'obj': r[1], 'x': int(r[2]), 'y': int(r[3]),
                             'sx': float(r[4]), 'sy': float(r[5]),
                             'rot': float(r[6]), 'frame': int(r[7]),
                             'depth': int(r[9]), 'layer': r[10]})
    return out


def load_objmap(game):
    path = os.path.join(RAW115, game, 'objmap_ut.txt')
    objs = {}
    for ln in io.open(path, encoding='utf-8', newline='').read().split('\n'):
        if not ln or ln.startswith('==') or ln.startswith('GameObjects'):
            continue
        parts = ln.split('\t')
        if len(parts) < 5:
            continue
        name = parts[1]
        spr = parts[2][4:] if parts[2].startswith('spr=') else ''
        vis = parts[3] == 'vis=True'
        objs[name] = {'spr': spr, 'vis': vis}
    return objs


def load_draw(game):
    u"""对象的 Draw 事件分类：none=没有 Draw（走 GM 默认 draw_self）/ self=Draw 里调 draw_self / custom=自绘。

    ★ 为什么要它：`obj_overworldcontroller` 的精灵是 `spr_heartgtfo`，但它的 Draw 只在战斗里画，
      直接按资产精灵贴上去，每间房左上角就多一颗红心（第一版烘图就是这个症状）。
    """
    p = os.path.join(WORK, game, '_out', 'draw120.%s.tsv' % game)
    out = {}
    if not os.path.isfile(p):
        return out
    for r in _rows(p):
        if r[0] != 'D' or len(r) < 5:
            continue
        name, dn, has_self = r[1], r[2], r[3]
        if dn == '-':
            out[name] = 'none'
        else:
            out[name] = 'self' if has_self == '1' else 'custom'
    return out


def load_hidden(game):
    u"""Create 里把自己设成不可见的对象（`pushi.e 0` + `pop.v.i self.visible`，最后一条为准）。"""
    p = os.path.join(WORK, game, '_out', 'visasm120.%s.tsv' % game)
    last = {}
    if not os.path.isfile(p):
        return set()
    for r in _rows(p):
        if r[0] != 'L' or len(r) < 5:
            continue
        prev, cur = r[3], r[4]
        if 'visible' not in cur:
            continue
        if 'pushi.e 1' in prev:
            last[r[1]] = False
        elif 'pushi.e 0' in prev:
            last[r[1]] = True
    return set(k for k, v in last.items() if v)


def gm_color(c):
    u"""GM 的颜色是 **ABGR** 打包：A=(c>>24), B=(c>>16), G=(c>>8), R=c&0xFF。"""
    return ((c >> 24) & 255, (c >> 16) & 255, (c >> 8) & 255, c & 255)  # r,g,b,a 反着取


def rgba_of(c):
    a = (c >> 24) & 255
    b = (c >> 16) & 255
    g = (c >> 8) & 255
    r = c & 255
    return (r, g, b, a)


class Tex(object):
    u"""贴图缓存 + 抠图 + 染色。"""

    def __init__(self, texdir):
        self.dir = texdir
        self.cache = {}
        self.miss = defaultdict(int)

    def get(self, name):
        if name in self.cache:
            return self.cache[name]
        p = os.path.join(self.dir, name)
        img = None
        if os.path.isfile(p):
            try:
                img = Image.open(p).convert('RGBA')
            except Exception:
                img = None
        else:
            self.miss[name] += 1
        self.cache[name] = img
        return img

    def tile_png(self, idx):
        return self.get('t_%d.png' % idx)

    def spr_png(self, name, frame):
        img = self.get('spr_%s_%d.png' % (name, frame))
        if img is None and frame != 0:
            img = self.get('spr_%s_0.png' % name)
        if img is None:
            img = self.get('spr_%s_0.png' % name)
        return img


def tint(img, color):
    r, g, b, a = rgba_of(color)
    if (r, g, b, a) == (255, 255, 255, 255):
        return img
    if a == 0:
        return None
    px = img.split()
    r_ch, g_ch, b_ch, a_ch = px
    # 乘算：GM 的 image_blend 就等价于逐通道相乘
    r_ch = r_ch.point(lambda v: v * r // 255)
    g_ch = g_ch.point(lambda v: v * g // 255)
    b_ch = b_ch.point(lambda v: v * b // 255)
    a_ch = a_ch.point(lambda v: v * a // 255) if a != 255 else a_ch
    return Image.merge('RGBA', (r_ch, g_ch, b_ch, a_ch))


def paste(canvas, img, x, y):
    u"""贴图：完全落在画布内走 alpha_composite（快），越界走 paste（自动裁边）。"""
    if img is None:
        return
    x, y = int(x), int(y)
    if _inside(canvas, img, x, y):
        canvas.alpha_composite(img, (x, y))
    else:
        canvas.paste(img, (x, y), img)


def _inside(canvas, img, x, y):
    return x >= 0 and y >= 0 and x + img.width <= canvas.width and y + img.height <= canvas.height


def bake_room(room, layers, bgs, lsps, tiles, tex, insts, objs, room_dir,
              draw_kind=None, hidden_objs=None, ignore_vis=False):
    W, H = room['w'], room['h']
    base = rgba_of(room['bgcolor']) if room['drawbg'] else (0, 0, 0, 255)
    canvas = Image.new('RGBA', (W, H), base)

    layer_depth = {L['i']: L['depth'] for L in layers}

    items = []   # (depth, seq, kind, payload)
    seq = 0
    for b in bgs:
        items.append((layer_depth.get(b['li'], 0), seq, 'bg', b))
        seq += 1
    for s in lsps:
        items.append((layer_depth.get(s['li'], 0), seq, 'sp', s))
        seq += 1
    for t in tiles:
        if not t['vis']:
            continue
        items.append((t['depth'], seq, 'tl', t))
        seq += 1
    for i in insts:
        o = objs.get(i['obj'])
        # ★ 第121轮：`ignore_vis=True` 时**不按资产 `vis` 过滤**（默认 False，默认行为一字不变）。
        #   为什么需要它：GM 的 `visible` 只约束**自动绘制**（无 Draw 事件时）；
        #   自定义 Draw 事件照跑。所以「资产 vis=False」不等于「屏幕上没有」。
        #   这是用来做对照实验的开关，不是产品口径 —— 正式烘图仍走 vis 门。
        if not o or (not o['vis'] and not ignore_vis) or not o['spr']:
            continue
        # ★ 自绘对象不画（画了就一定是假的：它们的 Draw 里有条件/战斗专用逻辑）
        if draw_kind.get(i['obj']) == 'custom':
            continue
        if i['obj'] in hidden_objs:
            continue
        items.append((i['depth'], seq, 'ob', i))
        seq += 1

    # depth 大 = 靠后 = 先画；同 depth 保持原序
    items.sort(key=lambda z: (-z[0], z[1]))

    stat = defaultdict(int)
    for depth, _s, kind, p in items:
        if kind == 'bg':
            if not p['vis']:
                continue
            img = tex.spr_png(p['spr'], 0) if p['spr'] else None
            if img is None:
                # 无精灵的"Compatibility_Colour"层 = 纯色填充
                r, g, b, a = rgba_of(p['color'])
                if p['spr'] or a == 0:
                    continue
                canvas.alpha_composite(Image.new('RGBA', (W, H), (r, g, b, a)))
                stat['fill'] += 1
                continue
            img = tint(img, p['color'])
            if img is None:
                continue
            if p['stretch'] and img.width and img.height:
                img = img.resize((W, H), Image.NEAREST)
                canvas.alpha_composite(img, (0, 0))
            elif p['ht'] or p['vt']:
                step_x = img.width if p['ht'] else W
                step_y = img.height if p['vt'] else H
                ox, oy = int(p['x']), int(p['y'])
                y = oy % step_y - step_y
                while y < H:
                    x = ox % step_x - step_x
                    while x < W:
                        paste(canvas, img, x, y)
                        x += step_x
                    y += step_y
            else:
                paste(canvas, img, p['x'], p['y'])
            stat['bg'] += 1
        elif kind == 'tl':
            src = tex.tile_png(p['tp'])
            if src is None:
                stat['tile_miss'] += 1
                continue
            box = (p['sx'], p['sy'], p['sx'] + p['w'], p['sy'] + p['h'])
            if box[2] > src.width or box[3] > src.height or p['w'] <= 0 or p['h'] <= 0:
                stat['tile_oob'] += 1
                continue
            piece = src.crop(box)
            if p['kx'] != 1.0 or p['ky'] != 1.0:
                nw = max(1, int(round(p['w'] * p['kx'])))
                nh = max(1, int(round(p['h'] * p['ky'])))
                piece = piece.resize((nw, nh), Image.NEAREST)
            piece = tint(piece, p['color'])
            if piece is None:
                continue
            paste(canvas, piece, p['x'], p['y'])
            stat['tile'] += 1
        elif kind == 'sp':
            img = tex.spr_png(p['spr'], p['frame'])
            if img is None:
                stat['sp_miss'] += 1
                continue
            if p['sx'] != 1.0 or p['sy'] != 1.0:
                img = img.resize((max(1, int(round(img.width * p['sx']))),
                                  max(1, int(round(img.height * p['sy'])))), Image.NEAREST)
            img = tint(img, p['color'])
            if img is None:
                continue
            paste(canvas, img, p['x'], p['y'])
            stat['sp'] += 1
        else:  # 'ob'
            o = objs[p['obj']]
            img = tex.spr_png(o['spr'], p['frame'])
            if img is None:
                stat['ob_miss'] += 1
                continue
            ox = o.get('ox', 0)
            oy = o.get('oy', 0)
            if p['sx'] != 1.0 or p['sy'] != 1.0:
                img = img.resize((max(1, int(round(img.width * p['sx']))),
                                  max(1, int(round(img.height * p['sy'])))), Image.NEAREST)
                ox = int(round(ox * p['sx']))
                oy = int(round(oy * p['sy']))
            paste(canvas, img, p['x'] - ox, p['y'] - oy)
            stat['ob'] += 1

    return canvas, stat


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--game', required=True)
    ap.add_argument('--viz', default=None)
    ap.add_argument('--tiles', default=None)
    ap.add_argument('--tex', default=None)
    ap.add_argument('--out', default=None)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--rooms', default='', help='逗号分隔的房间名，只烘这些')
    # ★ 第121轮对照实验用：默认关，默认行为一字不变
    ap.add_argument('--include-invisible', action='store_true',
                    help='不按资产 vis 过滤对象（对照实验用，不是产品口径）')
    a = ap.parse_args(argv)

    d = os.path.join(WORK, a.game, '_out')
    viz = a.viz or os.path.join(d, 'viz120.%s.tsv' % a.game)
    tiles_p = a.tiles or os.path.join(d, 'tiles120.%s.tsv' % a.game)
    texdir = a.tex or os.path.join(d, 'tex')
    outdir = a.out or os.path.join(d, 'baked')
    os.makedirs(outdir, exist_ok=True)

    rooms, layers, lbg, lsp, spr = load_viz(viz)
    tiles, tps = load_tiles(tiles_p)
    insts = load_inst(a.game)
    objs = load_objmap(a.game)
    # 把精灵原点并进 objs（objmap 里没有原点，SPR 段有）
    spr_origin = {}
    for (nm, fr), v in spr.items():
        spr_origin.setdefault(nm, (v['ox'], v['oy']))
    for o in objs.values():
        o['ox'], o['oy'] = spr_origin.get(o['spr'], (0, 0))

    draw_kind = load_draw(a.game)
    hidden_objs = load_hidden(a.game)
    print('绘制分类：none %d / self %d / custom %d ；Create 里隐藏 %d'
          % (sum(1 for v in draw_kind.values() if v == 'none'),
             sum(1 for v in draw_kind.values() if v == 'self'),
             sum(1 for v in draw_kind.values() if v == 'custom'),
             len(hidden_objs)))

    tex = Tex(texdir)
    want = set(a.rooms.split(',')) if a.rooms.strip() else None

    order = sorted(rooms)
    if a.limit:
        order = order[:a.limit]

    print('%-4s %-26s %5s %5s  %s' % ('idx', 'room', 'w', 'h', 'items'))
    total = defaultdict(int)
    for ri in order:
        room = rooms[ri]
        if want and room['name'] not in want:
            continue
        canvas, stat = bake_room(room, layers.get(ri, []), lbg.get(ri, []),
                                 lsp.get(ri, []), tiles.get(ri, []), tex,
                                 insts.get(ri, []), objs, outdir,
                                 draw_kind, hidden_objs,
                                 ignore_vis=a.include_invisible)
        fn = os.path.join(outdir, '%s_%s.png' % (a.game, room['name']))
        canvas.save(fn)
        n = stat['tile'] + stat['ob'] + stat['bg'] + stat['sp'] + stat['fill']
        print('%-4d %-26s %5d %5d  %d  (tile %d / ob %d / bg %d / fill %d; miss t%d o%d)'
              % (ri, room['name'], room['w'], room['h'], n, stat['tile'], stat['ob'],
                 stat['bg'], stat['fill'], stat['tile_miss'], stat['ob_miss']))
        for k, v in stat.items():
            total[k] += v

    print('---- 合计', dict(total))
    if tex.miss:
        top = sorted(tex.miss.items(), key=lambda kv: -kv[1])[:15]
        print('---- 缺图 %d 种，前 15：%s' % (len(tex.miss), top))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))
