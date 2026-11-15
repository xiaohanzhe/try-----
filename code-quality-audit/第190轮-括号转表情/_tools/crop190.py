# -*- coding: utf-8 -*-
u"""第190轮 · 从游戏包**原样切贴图页 + 按 UV 裁切**，拿到彩色 sprite。

为什么不用 `TextureWorker.ExportAsPNG`
--------------------------------------
实测（2026-11-15）：它对 hy/ut 两个包都只吐**黑白蒙版**（ceroba 的脸、undyne 的脸
都只有 2 种颜色）。而包里的贴图页本来就是 PNG（hy 34 块 / ut 42 块，IEND 全完整），
所以改成"自己按 PNG 签名把页切出来，再按 UV 裁"——颜色必然是原样。

★ 验证（每一步都验，用户要求）
   1. 切出的页数 **必须等于** UTMT 报的 `Data.EmbeddedTextures.Count`；
   2. 每张页的实际尺寸 **必须等于** `pages.tsv` 里 UTMT 报的宽高（对不上=顺序错，立即停）；
   3. 裁出的图 **颜色数 > 2**（只 2 色就是又退化成蒙版，立即报红）；
   4. 裁出的张数 **必须等于** `uv.tsv` 的数据行数。

用法
----
    python crop190.py --tag hy --prefix spr_portrait_          # UTY 肖像
    python crop190.py --tag ut --prefix spr_face_               # UT 脸部
    python crop190.py --tag hy --prefix spr_portrait_ --dry
"""
import io
import os
import re
import shutil
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
EV = os.path.join(ROUND, '_evidence')
TSV = os.path.join(EV, 'sprites')
EXE = u'E:\\Download\\UTMT_CLI_v0.9.2.0\\UndertaleModCli.exe'
CSX = os.path.join(HERE, 'dump_uv190.csx')
WORK = u'D:/_tmp190'
PKG = {
    'hy': u'D:/_wb_tmp/dw_ut/uty/game.droid',
    'ot': u'D:/_wb_tmp/dw_ut/outertale/game.droid',
    'ut': u'D:/_wb_tmp/dw_ut/ut/game.droid',
}
SIG = b'\x89PNG\r\n\x1a\n'
IEND = b'IEND\xaeB`\x82'


def names_of(tag, prefix):
    out = []
    for line in io.open(os.path.join(TSV, tag + '.tsv'), encoding='utf-8', errors='replace'):
        if line.startswith('#'):
            continue
        p = line.rstrip('\n').split('\t')
        if p and p[0].startswith(prefix):
            out.append(p[0])
    return out


def run_uv(tag, names):
    d = os.path.join(WORK, tag + '_uv')
    if os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    lst = os.path.join(WORK, tag + '_uv_list.txt')
    with io.open(lst, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(names) + '\n')
    csx_work = os.path.join(WORK, 'dump_uv190.csx')
    shutil.copyfile(CSX, csx_work)
    env = dict(os.environ)
    env['R190_LIST'] = lst
    env['R190_OUT'] = d.replace('/', '\\')
    log = os.path.join(WORK, tag + '_uv.log')
    with io.open(log, 'wb') as fh:
        p = subprocess.Popen([EXE, 'load', PKG[tag], '-s', csx_work], stdout=fh,
                             stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env)
        rc = p.wait()
    txt = io.open(log, 'r', encoding='utf-8', errors='replace').read()
    for l in txt.splitlines():
        if 'R190' in l:
            print('   [utmt] %s' % l)
    if rc != 0:
        print('[失败] UTMT rc=%s，日志：%s' % (rc, log))
        return None
    return d


def extract_pages(pkg, outdir):
    data = open(pkg, 'rb').read()
    starts = [m.start() for m in re.finditer(re.escape(SIG), data)]
    paths = []
    for s in starts:
        e = data.find(IEND, s)
        if e < 0:
            continue
        blob = data[s:e + 8]
        p = os.path.join(outdir, 'page_%03d.png' % len(paths))
        with io.open(p, 'wb') as fh:
            fh.write(blob)
        paths.append(p)
    return paths


def read_tsv(p):
    rows = []
    for line in io.open(p, encoding='utf-8', errors='replace'):
        if line.startswith('#'):
            continue
        f = line.rstrip('\n').split('\t')
        if f and f[0]:
            rows.append(f)
    return rows


def main():
    argv = sys.argv[1:]
    tag = argv[argv.index('--tag') + 1] if '--tag' in argv else 'hy'
    prefix = argv[argv.index('--prefix') + 1] if '--prefix' in argv else 'spr_portrait_'
    dry = '--dry' in argv
    names = names_of(tag, prefix)
    print('[清单] %s* 共 %d 条' % (prefix, len(names)))
    if not names:
        return 3
    if dry:
        return 0

    d = run_uv(tag, names)
    if not d:
        return 4

    from PIL import Image
    pages = extract_pages(PKG[tag], d)
    meta = read_tsv(os.path.join(d, 'pages.tsv'))
    want_pages = int(re.search(r'embedded=(\d+)',
                               io.open(os.path.join(d, 'pages.tsv'),
                                       encoding='utf-8').readline()).group(1))
    print('[页] 切出 %d 张 PNG；UTMT 报 embedded=%d' % (len(pages), want_pages))
    if len(pages) != want_pages:
        print('[停手] 页数对不上 ⇒ 切页方式不可信（差 %d）' % (want_pages - len(pages)))
        return 5

    # ② 尺寸对账：顺序错一定在这里暴露
    bad = []
    for r in meta:
        if len(r) != 3:
            continue
        idx, w, h = int(r[0]), int(r[1]), int(r[2])
        if w <= 0 or h <= 0:
            continue
        im = Image.open(pages[idx])
        if (im.width, im.height) != (w, h):
            bad.append((idx, (w, h), (im.width, im.height)))
    if bad:
        print('[停手] 页尺寸对不上（顺序错）：%r' % bad[:5])
        return 6
    print('[对账] %d 张页的尺寸与 UTMT 报的一致' % len(meta))

    uvs = read_tsv(os.path.join(d, 'uv.tsv'))
    outdir = os.path.join(WORK, tag + '_faces')
    if os.path.isdir(outdir):
        shutil.rmtree(outdir, ignore_errors=True)
    os.makedirs(outdir, exist_ok=True)
    made, thin = 0, []
    for r in uvs:
        if len(r) != 7:
            continue
        name, frame, pi, sx, sy, sw, sh = r[0], int(r[1]), int(r[2]), \
            int(r[3]), int(r[4]), int(r[5]), int(r[6])
        if sw <= 0 or sh <= 0:
            continue
        page = Image.open(pages[pi]).convert('RGBA')
        box = (sx, sy, min(sx + sw, page.width), min(sy + sh, page.height))
        img = page.crop(box)
        dst = os.path.join(outdir, '%s_%d.png' % (name, frame))
        img.save(dst)
        made += 1
        cols = img.getcolors(1 << 20)
        if cols is not None and len(cols) <= 2:
            thin.append((name, frame, len(cols)))

    print('[裁切] %d 张 → %s' % (made, outdir))
    print('[验证] uv 行数=%d，产出=%d %s' % (len(uvs), made,
                                        '一致' if made == len(uvs) else '不一致!!'))
    if thin:
        print('[报红] %d 张仍是 ≤2 色（蒙版）：%r' % (len(thin), thin[:5]))
        return 7
    print('[验证] 全部 >2 色 ⇒ 颜色已正确带出')
    return 0


if __name__ == '__main__':
    sys.exit(main())
