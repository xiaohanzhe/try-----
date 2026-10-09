# -*- coding: utf-8 -*-
u"""os_bg100.py —— 第100轮：从 OneShot WME 的**原作数据**合成房间背景图（只读原作，产物进 _evidence）。

口径（用户）：「一切根据原作」。所以背景**不是手画的**，是拿原作的
`gamedata/maps/map<N>.tmx`（Tiled，CSV 瓦片）+ tsx 图集 + `oneshot_map_colors.json`（底色）
**逐像素合成**出来的。

数据链路
--------
 map<N>.tmx  width/height/tilewidth/tileheight + <tileset firstgid source="../*.tsx"> + 每层 CSV gid
   -> *.tsx   name/tilecount/columns + <image source="../../Content/xxx.png" trans="00ff00">
   -> 实际图 = content/xxx.**xnb**（发行版只带 xnb，png 被剥掉）=> 用最小 XNB 解码取 RGBA
   -> oneshot_map_colors.json 里该 map 的底色（纯地板区域靠它）

锚点（不通过就不往下用）
----------------------
 A1 tmx 数 == 263（与场景索引里 oneshot 的房间数一致）
 A2 结构恒等式：输出尺寸 == map.width*tilewidth × map.height*tileheight
 A3 正控制：同一张图渲染两次必须**逐字节相同**
 A4 负控制：**丢掉第 1 层**后结果必须与原图不同（证明层真的被用上了，不是空转）
 A5 所有 firstgid 都能解析到图像文件（解不开的如实报数）

用法：
    python -X utf8 os_bg100.py --probe          # 只跑锚点 + 渲染 3 张样例
    python -X utf8 os_bg100.py --all            # 全部 263 张
"""
import hashlib
import io
import json
import os
import re
import struct
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image                                          # noqa: E402

OSD = (r'C:\Users\23002\Desktop\项目文件夹\niko的秘密'
       r'\OneShot.World.Machine.Edition.Build.16512634')
MAPS = os.path.join(OSD, 'gamedata', 'maps')
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), '_evidence', 'os_bg')

FAILS = []


def check(name, ok, detail=''):
    print('[%s] %s %s' % ('PASS' if ok else 'FAIL', name, detail))
    if not ok:
        FAILS.append(name)
    return ok


# ------------------------------------------------------------------ XNB
def rd7(b, i):
    r = s = 0
    while True:
        x = b[i]
        i += 1
        r |= (x & 0x7F) << s
        if not (x & 0x80):
            return r, i
        s += 7


_XNB_CACHE = {}


def xnb_rgba(path):
    if path in _XNB_CACHE:
        return _XNB_CACHE[path]
    b = open(path, 'rb').read()
    if b[:3] != b'XNB' or (b[5] & 0xC0):
        _XNB_CACHE[path] = None
        return None
    i = 10
    nr, i = rd7(b, i)
    for _ in range(nr):
        n, i = rd7(b, i)
        i += n + 4
    _s, i = rd7(b, i)
    _t, i = rd7(b, i)
    _fmt, w, h, mips = struct.unpack('<iIII', b[i:i + 16])
    i += 16
    d = None
    for m in range(mips):
        sz = struct.unpack('<I', b[i:i + 4])[0]
        i += 4
        if m == 0:
            d = b[i:i + sz]
        i += sz
    im = Image.frombytes('RGBA', (w, h), d[:w * h * 4]) if d else None
    _XNB_CACHE[path] = im
    return im


# ------------------------------------------------------------------ 解析
_TAG = re.compile(r'<(\w+)([^>]*?)/?>')
_ATTR = re.compile(r'(\w+)\s*=\s*"([^"]*)"')


def attrs(tail):
    return dict(_ATTR.findall(tail))


def parse_map(path):
    s = io.open(path, encoding='utf-8', newline='').read()
    a = attrs(re.search(r'<map\b([^>]*)>', s).group(1))
    m = {'w': int(a['width']), 'h': int(a['height']),
         'tw': int(a['tilewidth']), 'th': int(a['tileheight']),
         'props': {}, 'tilesets': [], 'layers': []}
    for name, tail in _TAG.findall(s):
        at = attrs(tail)
        if name == 'property':
            m['props'][at.get('name')] = at.get('value')
        elif name == 'tileset':
            m['tilesets'].append((int(at['firstgid']), at['source']))
    for lay in re.findall(r'<layer\b([^>]*)>\s*<data[^>]*>(.*?)</data>', s, re.S):
        at = attrs(lay[0])
        gids = [int(x) for x in re.findall(r'\d+', lay[1])]
        m['layers'].append((at.get('name'), gids))
    return m


def parse_tsx(path):
    s = io.open(path, encoding='utf-8', newline='').read()
    a = attrs(re.search(r'<tileset\b([^>]*)>', s).group(1))
    ia = attrs(re.search(r'<image\b([^>]*)>', s).group(1))
    return {'columns': int(a['columns']), 'tilecount': int(a['tilecount']),
            'tw': int(a['tilewidth']), 'th': int(a['tileheight']),
            'img': ia['source'], 'trans': ia.get('trans')}


def resolve_img(tsx_dir, src):
    """tsx 里的 <image source> 指向 .png，但发行版只带 .xnb => 换成 xnb 再解。"""
    p = os.path.normpath(os.path.join(tsx_dir, src))
    cands = [p, os.path.splitext(p)[0] + '.xnb']
    for c in cands:
        if os.path.isfile(c):
            return c
    # 大小写不敏感兜底（Windows 通常无所谓，防 tar 解包变成小写）
    d, n = os.path.split(p)
    if os.path.isdir(d):
        low = {x.lower(): x for x in os.listdir(d)}
        for k in (n.lower(), os.path.splitext(n)[0].lower() + '.xnb'):
            if k in low:
                return os.path.join(d, low[k])
    return None


def load_map_colors():
    s = io.open(os.path.join(OSD, 'gamedata', 'oneshot_map_colors.json'),
                encoding='utf-8', newline='').read()
    s = re.sub(r',(\s*[}\]])', r'\1', s)                     # 原作 json 有尾逗号
    d = json.loads(s)
    out = {}
    for e in d['mapColors']:
        c = e['color']
        for n in e['maps']:
            out[int(n)] = (c['r'], c['g'], c['b'], c.get('a', 255))
    return out


def render(mpath, colors, drop_first_layer=False):
    m = parse_map(mpath)
    n = int(re.search(r'map(\d+)\.tmx$', mpath).group(1))
    imgs = []
    for fg, src in m['tilesets']:
        tsx = os.path.normpath(os.path.join(MAPS, src))
        t = parse_tsx(tsx)
        ip = resolve_img(os.path.dirname(tsx), t['img'])
        imgs.append((fg, t, ip, xnb_rgba(ip) if ip else None))
    W, H = m['w'] * m['tw'], m['h'] * m['th']
    base = colors.get(n, (0, 0, 0, 255))
    out = Image.new('RGBA', (W, H), base)
    used = 0
    layers = m['layers'][1:] if drop_first_layer else m['layers']
    for lname, gids in layers:
        for idx, g in enumerate(gids):
            if g <= 0:
                continue
            cur = None
            for fg, t, ip, im in imgs:
                if g >= fg:
                    cur = (fg, t, ip, im)
                else:
                    break
            if cur is None or cur[3] is None:
                continue
            fg, t, ip, im = cur
            lid = g - fg
            if lid >= t['tilecount']:
                continue
            col, row = lid % t['columns'], lid // t['columns']
            tile = im.crop((col * t['tw'], row * t['th'],
                            col * t['tw'] + t['tw'], row * t['th'] + t['th']))
            out.paste(tile, ((idx % m['w']) * m['tw'], (idx // m['w']) * m['th']), tile)
            used += 1
    return out, used, m


def main():
    all_ = '--all' in sys.argv
    tmx = sorted(f for f in os.listdir(MAPS) if f.endswith('.tmx'))
    check('A1 tmx 数 == 263（= 场景索引里 oneshot 房间数）', len(tmx) == 263, str(len(tmx)))
    colors = load_map_colors()
    print('    mapColors 覆盖 %d 张地图' % len(colors))

    # A5 解析率
    miss, tot = [], 0
    for f in tmx:
        m = parse_map(os.path.join(MAPS, f))
        for fg, src in m['tilesets']:
            tot += 1
            tsx = os.path.normpath(os.path.join(MAPS, src))
            if not os.path.isfile(tsx):
                miss.append((f, src, 'tsx 缺'))
                continue
            t = parse_tsx(tsx)
            if resolve_img(os.path.dirname(tsx), t['img']) is None:
                miss.append((f, src, 'image 缺：' + t['img']))
    check('A5 所有 tileset 引用都能解析到图像文件', not miss,
          '%d/%d 未解析 %s' % (len(miss), tot, miss[:3]))

    # A2/A3/A4 —— 用 map1 做结构 + 正/负控制
    p1 = os.path.join(MAPS, 'map1.tmx')
    im1, used1, m1 = render(p1, colors)
    check('A2 输出尺寸 == map.width*tilewidth × map.height*tileheight',
          im1.size == (m1['w'] * m1['tw'], m1['h'] * m1['th']),
          '%s vs %s' % (im1.size, (m1['w'] * m1['tw'], m1['h'] * m1['th'])))
    b1 = im1.tobytes()
    im1b, _u, _m = render(p1, colors)
    check('A3 正控制：同图渲染两次逐字节相同', b1 == im1b.tobytes())
    im_nb, _, _ = render(p1, colors, drop_first_layer=True)
    check('A4 负控制：丢第 1 层后必须不同', im_nb.tobytes() != b1,
          '非零像素差=%d' % sum(1 for a, b in zip(im_nb.tobytes(), b1) if a != b))

    os.makedirs(OUT, exist_ok=True)
    targets = tmx if all_ else ['map1.tmx', 'map2.tmx', 'map50.tmx']
    made = []
    for f in targets:
        im, used, m = render(os.path.join(MAPS, f), colors)
        n = re.search(r'map(\d+)', f).group(1)
        p = os.path.join(OUT, 'os_%s.png' % n)
        im.save(p)
        made.append((p, im.size, used))
    print('\n渲染 %d 张：' % len(made))
    for p, sz, u in made[:8]:
        print('   %-52s %s 贴了 %d 块' % (os.path.basename(p), sz, u))
    if len(made) > 8:
        print('   ... 另 %d 张' % (len(made) - 8))
    print('\n输出目录', OUT)
    print('FAIL =', len(FAILS), FAILS)
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
