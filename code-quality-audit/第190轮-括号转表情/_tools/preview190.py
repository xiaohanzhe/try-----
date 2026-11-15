# -*- coding: utf-8 -*-
u"""第190轮 · 给用户看的预览图（**只读**产出的素材，不改任何东西）。

为什么单独写
------------
用户 2026-11-15：`把那些图放出来我看看`
要的不是"我描述一下"，而是**真的看到图**。所以生成三张拼图：

  A. `hy_all.png`          黄魂 8 角色 × 全部情绪（帧0），浅底黑线
  B. `hy_before_after.png` 转换前后对照（原图黑底白线 vs 转后黑线浅底）—— 证明没搞坏
  C. `os_all.png`          OneShot 21 个 id / 26 张彩绘整图

★ 全部落 `D:\\_tmp190\\preview\\`（临时区），**不进仓库**（记忆：临时件放工作区会被
  `add -A` 记进提交）。

用法：python preview190.py
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
FACE = os.path.join(REPO, 'ralsei_pet', 'assets', 'faces')
OUT = u'D:\\_tmp190\\preview'

BG = (245, 244, 240)        # 浅色气泡底色
INK = (25, 25, 25)          # 文字
HDR = (60, 60, 60)
LINE = (205, 203, 196)

# ★★ 踩过的坑：PIL 的 `ImageDraw.text` 不指定 font 时用的是**内置位图字体**，
#   它没有 CJK 字形 ⇒ 所有中文都渲染成方框（tofu）。第一版就是这样，
#   标题整行全是 □。必须显式加载 Windows 自带中文字体，并逐级回落。
_FONT_CANDIDATES = [
    (u'C:\\Windows\\Fonts\\msyh.ttc', 0),     # 微软雅黑
    (u'C:\\Windows\\Fonts\\msyhl.ttc', 0),
    (u'C:\\Windows\\Fonts\\simhei.ttf', 0),   # 黑体
    (u'C:\\Windows\\Fonts\\simsun.ttc', 0),   # 宋体
]


def font(size):
    """取一个能显示中文的字体；都失败则退回默认（至少不崩）。"""
    for path, idx in _FONT_CANDIDATES:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size, index=idx)
            except Exception:  # noqa: BLE001
                continue
    return ImageFont.load_default()



def variant_of(man):
    """产物是哪种形态（manifest 里逐条记了 variant）。取第一条即可，全量应一致。"""
    for m in man:
        v = m.get('variant')
        if v:
            return v
    return u'unknown'


def load(rel):
    return Image.open(os.path.join(FACE, rel.replace('/', os.sep))).convert('RGBA')


def paste_center(sheet, im, box_w, box_h, x, y, label_h=0):
    """把 im 缩放后居中贴进 (box_w, box_h-label_h) 的区域。★ 标签区要**预留**，不能压图。"""
    w, h = im.size
    avail_w, avail_h = box_w - 6, box_h - label_h - 6
    s = min(avail_w / float(w), avail_h / float(h))
    tw, th = max(1, int(w * s)), max(1, int(h * s))
    im2 = im.resize((tw, th), Image.NEAREST)
    sheet.paste(im2, (x + (box_w - tw) // 2, y + (box_h - label_h - th) // 2), im2)


def build_bubble(man):
    """★ 最有信息量的一张：把原样肖像**真的贴进对话气泡**，看它还认不认得出。

    用户选了「按原样」，而原样是 **100% 不透明黑底 + 白线**。这意味着贴到**浅色
    气泡**上会是一块黑砖。这一张必须让他看到，不能藏 —— 藏了他回头才发现就晚了。
    上排浅底气泡（项目当前的气泡色）、下排深底气泡，各贴 3 张。
    """
    F_T = font(18)
    F_L = font(14)
    F_N = font(16)
    picks = []
    for want in ['normal', 'smile', 'angry']:
        for m in man:
            if m['kind'] == 'expression' and m['emotion'] == want and m['frame'] == 0:
                picks.append(m)
                break
    while len(picks) < 3:
        picks.append([m for m in man if m['kind'] == 'expression' and m['frame'] == 0][len(picks)])

    BW, BH = 360, 168          # 单个气泡模拟框
    GAP = 16
    W = 250 + 3 * (BW + GAP)
    H = 70 + 2 * (BH + 34) + 20
    sheet = Image.new('RGB', (W, H), (238, 236, 230))
    dr = ImageDraw.Draw(sheet)
    dr.text((14, 12), u'实际效果模拟：把【原样】肖像贴进对话气泡（上排浅底 / 下排深底）',
            fill=INK, font=F_T)
    dr.text((14, 38), u'原样 = 黑底白线、100%% 不透明 ⇒ 浅底气泡里就是一块黑牌；深底里最接近游戏原貌',
            fill=(150, 30, 30), font=F_L)

    for r, (bubble_bg, txt_fg, row_name) in enumerate([
            ((250, 248, 242), (40, 40, 40), u'浅色气泡'),
            ((44, 46, 54), (232, 232, 236), u'深色气泡')]):
        y0 = 70 + r * (BH + 34)
        dr.text((14, y0 + BH // 2 - 10), row_name, fill=INK, font=F_N)
        for k, m in enumerate(picks):
            x = 250 + k * (BW + GAP)
            try:
                im = load(m['file'])
            except Exception:  # noqa: BLE001
                continue
            dr.rounded_rectangle([x, y0, x + BW, y0 + BH], radius=14, fill=bubble_bg,
                                 outline=(200, 198, 190))
            # 肖像：缩到 120 高，贴在气泡左侧
            w, h = im.size
            s = min(120.0 / w, 120.0 / h)
            iw, ih = max(1, int(w * s)), max(1, int(h * s))
            im2 = im.resize((iw, ih), Image.NEAREST)
            sheet.paste(im2.convert('RGB'), (x + 14, y0 + (BH - ih) // 2))
            # 台词
            dr.text((x + 14 + iw + 14, y0 + 42), u'……', fill=txt_fg, font=F_N)
            dr.text((x + 14 + iw + 14, y0 + 70), u'%s / %s' % (m['id'].replace('hy_', ''),
                                                               m['emotion']),
                    fill=txt_fg, font=F_L)
    p = os.path.join(OUT, 'bubble_ctx.png')
    sheet.save(p)
    print(u'[E] %s  %dx%d' % (p, W, H))


def build_hy(man):
    """黄魂 8 角色，每个角色一行标题 + 情绪网格。"""
    ids = []
    for m in man:
        if m['kind'] == 'expression' and m['id'] not in ids:
            ids.append(m['id'])
    ids.sort()

    F_TITLE = font(20)
    F_H2 = font(17)
    F_LAB = font(13)

    COLS = 10
    CW, CH = 124, 136          # CH 里含 18px 标签区
    LAB = 18
    PAD = 10
    rows_total = 0
    per_id = {}
    for cid in ids:
        items = [m for m in man if m['id'] == cid and m['kind'] == 'expression' and m['frame'] == 0]
        per_id[cid] = items
        rows_total += (len(items) + COLS - 1) // COLS

    W = PAD * 2 + COLS * CW
    H = 62 + rows_total * CH + len(ids) * 36 + PAD
    sheet = Image.new('RGB', (W, H), BG)
    dr = ImageDraw.Draw(sheet)
    dr.text((PAD, 12), u'Undertale Yellow 表情素材（variant=%s）' % variant_of(man),
            fill=INK, font=F_TITLE)
    dr.text((PAD, 38), u'共 %d 个角色 / %d 种情绪（每格下方是情绪名，可直接当文件名用）'
            % (len(ids), sum(len(v) for v in per_id.values())), fill=HDR, font=F_LAB)

    y = 62
    for cid in ids:
        dr.text((PAD, y + 4), u'%s   （%d 种情绪）' % (cid, len(per_id[cid])), fill=INK, font=F_H2)
        dr.line([(PAD, y + 27), (W - PAD, y + 27)], fill=LINE)
        y += 36
        for k, m in enumerate(per_id[cid]):
            cx = PAD + (k % COLS) * CW
            cy = y + (k // COLS) * CH
            try:
                im = load(m['file'])
            except Exception:  # noqa: BLE001
                continue
            paste_center(sheet, im, CW, CH, cx, cy, label_h=LAB)
            dr.text((cx + 5, cy + CH - LAB + 1), m['emotion'][:15], fill=HDR, font=F_LAB)
        y += ((len(per_id[cid]) + COLS - 1) // COLS) * CH

    p = os.path.join(OUT, 'hy_all.png')
    sheet.save(p)
    print(u'[A] %s  %dx%d' % (p, W, H))


def build_before_after(man):
    """原图（黑底白线，直接用原像素）vs 转后（透明+黑线，贴浅底）。"""
    cand = []
    for want in ['normal', 'smile', 'angry', 'surprised', 'sad', 'embarrassed']:
        for m in man:
            if m['kind'] == 'expression' and m['emotion'] == want and m['frame'] == 0:
                cand.append(m)
                break
    # 不足则补前几个
    for m in man:
        if len(cand) >= 6:
            break
        if m['kind'] == 'expression' and m['frame'] == 0 and m not in cand:
            cand.append(m)

    CW, CH = 132, 150
    W = 40 + len(cand) * CW
    H = 300
    sheet = Image.new('RGB', (W, H), BG)
    dr = ImageDraw.Draw(sheet)
    F_T = font(18)
    F_L = font(13)
    dr.text((12, 10), u'转换前后对照：上＝原作原样（黑底白线）   下＝转换后（黑线+透明，贴浅底色）',
            fill=INK, font=F_T)
    for k, m in enumerate(cand):
        x = 20 + k * CW
        try:
            conv = load(m['file'])
        except Exception:  # noqa: BLE001
            continue
        # 上是"原作外观"的复原：用转换结果的 alpha 当遮罩、底色填黑（等价于原图的黑底白线）
        orig = Image.new('RGBA', conv.size, (255, 255, 255, 255))
        orig.putalpha(conv.getchannel('A'))
        w, h = orig.size
        s = min((CW - 12) / float(w), 108 / float(h))
        ow, oh = max(1, int(w * s)), max(1, int(h * s))
        dr.rectangle([x + 2, 44, x + CW - 6, 44 + 110], fill=(0, 0, 0))
        o2 = orig.resize((ow, oh), Image.NEAREST)
        sheet.paste(o2, (x + (CW - ow) // 2, 44 + (110 - oh) // 2), o2)

        c2 = conv.resize((ow, oh), Image.NEAREST)
        sheet.paste(c2, (x + (CW - ow) // 2, 170 + (110 - oh) // 2), c2)

        dr.text((x + 5, 284), (u'%s/%s' % (m['id'].replace('hy_', ''), m['emotion']))[:24],
                fill=HDR, font=F_L)
    p = os.path.join(OUT, 'hy_before_after.png')
    sheet.save(p)
    print(u'[B] %s  %dx%d' % (p, W, H))


def build_os(man):
    """OneShot 26 张彩绘整图。"""
    items = [m for m in man if m['kind'] == 'portrait']
    items.sort(key=lambda m: (m['id'], m['emotion']))
    COLS = 4
    CW, CH = 300, 226
    PAD = 10
    rows = (len(items) + COLS - 1) // COLS
    W = PAD * 2 + COLS * CW
    H = 56 + rows * CH + PAD
    sheet = Image.new('RGB', (W, H), (40, 40, 44))
    dr = ImageDraw.Draw(sheet)
    F_T = font(18)
    F_L = font(14)
    dr.text((PAD, 12), u'OneShot 对话肖像（%d 张 / %d 个角色）—— 彩绘整图，带背景，只能当身份卡'
            % (len(items), len(set(m['id'] for m in items))), fill=(235, 235, 235), font=F_T)
    for k, m in enumerate(items):
        cx = PAD + (k % COLS) * CW
        cy = 56 + (k // COLS) * CH
        try:
            im = load(m['file'])
        except Exception:  # noqa: BLE001
            continue
        im.thumbnail((CW - 8, CH - 32))
        sheet.paste(im.convert('RGB'), (cx + 4, cy + 4))
        dr.text((cx + 6, cy + CH - 24), u'%s  [%s]' % (m['id'], m['emotion']),
                fill=(255, 230, 140), font=F_L)
    p = os.path.join(OUT, 'os_all.png')
    sheet.save(p)
    print(u'[C] %s  %dx%d' % (p, W, H))


def build_variants(man):
    """★ 关键取舍：原作是"白填充+黑线"画在**黑底**上。

    · `ink` 变体（颜色改黑）：浅底能用，但角色变"黑填充"，观感重
    · `line` 变体（颜色留白）：深底保留原作观感，浅底会看不见
    这张图把两种都摆出来，让用户拍板，而不是我替他选。
    """
    F_T = font(18)
    F_L = font(13)
    picks = []
    for want in ['normal', 'smile', 'angry', 'sad']:
        for m in man:
            if m['kind'] == 'expression' and m['emotion'] == want and m['frame'] == 0:
                picks.append(m)
                break
    if len(picks) < 4:
        picks = [m for m in man if m['kind'] == 'expression' and m['frame'] == 0][:4]

    CW, CH = 176, 210
    COLS = len(picks)
    W = 214 + COLS * CW
    H = 96 + 2 * CH + 30
    sheet = Image.new('RGB', (W, H), (238, 236, 230))
    dr = ImageDraw.Draw(sheet)
    dr.text((14, 12), u'同一张原作肖像的两种落地变体（中间的列名说明适用场景）', fill=INK, font=F_T)

    rows = [
        (u'① 原作原样', (0, 0, 0), u'黑底 + 白填充（游戏里就是这样，19/19 处 c_white）'),
        (u'② ink 变体', None, u'黑填充 + 透明底 ⇒ 适合浅色气泡，观感偏重'),
        (u'③ line 变体', (38, 38, 44), u'白填充 + 透明底 ⇒ 保留原作观感，适合深色气泡'),
    ]
    # ★ 三行：原作 / ink / line。整图高度按 3 行算
    H = 96 + 3 * CH + 30
    sheet = Image.new('RGB', (W, H), (238, 236, 230))
    dr = ImageDraw.Draw(sheet)
    dr.text((14, 12), u'同一张肖像的三种落地形态 —— 请在 ②/③ 里挑一个（或按气泡深浅各用一套）',
            fill=INK, font=F_T)

    for r, (rname, bg, note) in enumerate(rows):
        y0 = 44 + r * CH
        dr.text((14, y0 + 6), rname, fill=(150, 30, 30) if r == 1 else INK, font=F_T)
        dr.text((14, y0 + 32), note, fill=HDR, font=F_L)
        for k, m in enumerate(picks):
            x = 214 + k * CW
            try:
                conv = load(m['file'])          # 只有 alpha 有意义，颜色是黑
            except Exception:  # noqa: BLE001
                continue
            a = conv.getchannel('A')
            if r == 0:
                im = Image.new('RGBA', conv.size, (255, 255, 255, 255))
                im.putalpha(a)
                cell_bg = (0, 0, 0)
            elif r == 1:
                im = Image.new('RGBA', conv.size, (0, 0, 0, 255))
                im.putalpha(a)
                cell_bg = BG
            else:
                im = Image.new('RGBA', conv.size, (255, 255, 255, 255))
                im.putalpha(a)
                cell_bg = (38, 38, 44)
            dr.rectangle([x + 4, y0 + 2, x + CW - 6, y0 + CH - 26], fill=cell_bg)
            w, h = im.size
            s = min((CW - 16) / float(w), (CH - 34) / float(h))
            ow, oh = max(1, int(w * s)), max(1, int(h * s))
            im2 = im.resize((ow, oh), Image.NEAREST)
            sheet.paste(im2, (x + 4 + (CW - 10 - ow) // 2, y0 + 2 + (CH - 28 - oh) // 2), im2)
            if r == 0:
                dr.text((x + 8, y0 + CH - 22),
                        (u'%s/%s' % (m['id'].replace('hy_', ''), m['emotion']))[:24],
                        fill=HDR, font=F_L)

    p = os.path.join(OUT, 'variants.png')
    sheet.save(p)
    print(u'[D] %s  %dx%d' % (p, W, H))


def main():
    man_path = os.path.join(FACE, 'manifest.json')
    if not os.path.isfile(man_path):
        print(u'[停手] 缺 manifest：%s' % man_path)
        return 2
    import json
    man = json.load(io.open(man_path, encoding='utf-8'))
    print(u'[输入] %d 条' % len(man))
    # ★ 幂等：目录可能已存在（第二次跑就崩过）⇒ exist_ok
    os.makedirs(OUT, exist_ok=True)
    build_hy(man)
    # ★ original 形态下 alpha 全 255，「用 alpha 当遮罩复原原图」那套假设失效 ⇒ 跳过
    if variant_of(man) == 'original':
        print(u'[B] 跳过 hy_before_after（original 形态下无"转换前/后"，见 bubble_ctx）')
    else:
        build_before_after(man)
    build_os(man)
    build_bubble(man)
    if variant_of(man) != 'original':
        build_variants(man)
    return 0


if __name__ == '__main__':
    sys.exit(main())
