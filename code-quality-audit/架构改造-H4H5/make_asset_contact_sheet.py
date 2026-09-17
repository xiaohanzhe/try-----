# -*- coding: utf-8 -*-
"""素材对照图渲染器（只读）—— 把磁盘上的命名分组按行放大铺开，供人眼核对朝向/形态。

用法：
    python make_asset_contact_sheet.py <子串> [放大倍数] [每行最多帧数]

例：
    python make_asset_contact_sheet.py climb 6 6
    python make_asset_contact_sheet.py nuzzle 5 5

输出：<脚本目录>/_evidence/<子串>_sheet.png + 同名 .txt 图例（离屏/无字体环境下文字可能画不出来，
所以组名同时写进 txt，PNG 里另画一条彩色定位带）。
"""
import os
import sys
import re
import collections

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ASSET_DIR = os.path.join(ROOT, "deltarune_ralsei")
OUT_DIR = os.path.join(HERE, "_evidence")

SEQ_RE = re.compile(r"^(?P<base>.+)_(?P<seq>\d+)$")


def parse_stem(filename):
    stem = filename
    if stem.lower().endswith(".png"):
        stem = stem[:-4]
    if stem.startswith("spr_"):
        stem = stem[4:]
    m = SEQ_RE.match(stem)
    if m:
        return m.group("base"), int(m.group("seq"))
    return stem, None


def main():
    if len(sys.argv) < 2:
        print("usage: make_asset_contact_sheet.py <substring> [scale] [maxcols]")
        return 2
    needle = sys.argv[1].lower()
    scale = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    maxcols = int(sys.argv[3]) if len(sys.argv) > 3 else 6

    files = sorted(n for n in os.listdir(ASSET_DIR)
                   if n.lower().endswith(".png") and needle in n.lower())
    if not files:
        print("no file matches %r" % needle)
        return 1

    groups = collections.OrderedDict()
    for fn in files:
        base, seq = parse_stem(fn)
        groups.setdefault(base, []).append((seq, fn))
    for v in groups.values():
        v.sort(key=lambda x: (x[0] is None, x[0]))

    # 载入 JSON 引用情况，便于在图例里标注
    import json
    jpath = os.path.join(ROOT, "ralsei_pet", "assets", "animations.json")
    used = set()
    if os.path.isfile(jpath):
        with open(jpath, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        for g in (data.get("groups") or {}).values():
            used.update(g.get("frames") or [])

    imgs = {}
    for base, items in groups.items():
        for _, fn in items:
            try:
                imgs[fn] = Image.open(os.path.join(ASSET_DIR, fn)).convert("RGBA")
            except Exception:
                pass

    # 布局
    cell_w = max((im.width for im in imgs.values()), default=32) + 2
    cell_h = max((im.height for im in imgs.values()), default=48) + 2
    label_w = 300
    rows = []
    for base, items in groups.items():
        rows.append((base, items))

    # 字体：PIL 直接读 .ttf（沙箱里 Qt 拿不到字体，但 PIL 读文件可以）
    fpath = None
    for cand in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyh.ttf",
                 r"C:\Windows\Fonts\simsun.ttc", r"C:\Windows\Fonts\arial.ttf"):
        if os.path.isfile(cand):
            fpath = cand
            break
    try:
        fbig = ImageFont.truetype(fpath, 26) if fpath else ImageFont.load_default()
    except Exception:
        fbig = ImageFont.load_default()
    try:
        fsmall = ImageFont.truetype(fpath, 17) if fpath else ImageFont.load_default()
    except Exception:
        fsmall = ImageFont.load_default()

    bands = [(150, 195, 235), (170, 215, 180), (240, 220, 160), (240, 185, 190),
             (195, 190, 230), (215, 215, 215)]
    W = label_w + maxcols * cell_w * scale + 8
    H = sum(cell_h * scale + 16 for _ in rows) + 8
    canvas = Image.new("RGB", (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    y = 4
    legend_lines = []
    for i, (base, items) in enumerate(rows):
        color = bands[i % len(bands)]
        rowh = cell_h * scale + 16
        draw.rectangle([0, y, W - 1, y + rowh - 1], outline=color, width=2)
        draw.rectangle([0, y, label_w - 1, y + rowh - 1], fill=color)
        n_used = sum(1 for _, f in items if f in used)
        tag = "已登记" if n_used == len(items) else ("部分引用" if n_used else "未引用")
        draw.text((6, y + 8), "%d. %s" % (i + 1, base), fill=(15, 15, 15), font=fbig)
        draw.text((6, y + 44), "%d 帧   [%s]" % (len(items), tag), fill=(60, 60, 60), font=fsmall)
        legend_lines.append("row%-2d %-46s %d 帧" % (i + 1, base, len(items)))
        x = label_w + 4
        for idx, (seq, fn) in enumerate(items):
            if idx >= maxcols:
                break
            im = imgs.get(fn)
            if im is None:
                continue
            big = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
            canvas.paste(big, (x, y + 8), big)
            draw.text((x, y + rowh - 22), str(seq), fill=(80, 80, 80), font=fsmall)
            x += cell_w * scale
        y += rowh

    os.makedirs(OUT_DIR, exist_ok=True)
    png = os.path.join(OUT_DIR, "%s_sheet.png" % needle)
    canvas.save(png)
    with open(os.path.join(OUT_DIR, "%s_sheet.txt" % needle), "w", encoding="utf-8") as fh:
        fh.write("对照图：%s  放大 %dx  每行至多 %d 帧\n" % (png, scale, maxcols))
        fh.write("磁盘文件数 %d，命名分组 %d\n" % (len(files), len(groups)))
        fh.write("列 = 序号（帧），行 = 命名分组；行首色带里的名字即组名\n")
        fh.write("组名后用 [已登记]/[未引用] 标注是否被 animations.json 引用\n\n")
        for line, (base, items) in zip(legend_lines, rows):
            n_used = sum(1 for _, f in items if f in used)
            tag = "已登记" if n_used == len(items) else ("部分引用" if n_used else "未引用")
            fh.write("%s   [%s %d/%d]\n" % (line, tag, n_used, len(items)))
            fh.write("      " + ", ".join(f for _, f in items) + "\n")
    print("wrote %s" % png)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
