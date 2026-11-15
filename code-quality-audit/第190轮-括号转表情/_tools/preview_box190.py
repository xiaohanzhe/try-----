# -*- coding: utf-8 -*-
u"""第190轮 · 头像框离线渲染预览（**不依赖 Qt**，纯 PIL 复现 set_face 的贴图规则）。

## 这个脚本在模拟什么

`dialogue_ui._apply_face_pixmap` 做三件事：
  ① `face_label` 固定 84×84，样式 `background-color:#000000; border:2px solid #fff`
  ② 位图 `scaled(78*scale, 78*scale, KeepAspectRatio, Smooth)`（78 = 84 - 2*2 - 内缩）
  ③ `setAlignment(Qt.AlignCenter)` ⇒ **居中**

★ `scale` 默认 1.0，所以预览按 84 / 78 像素原样画，**不是估算**。

## 为什么要这张图

`assets/faces/` 的黄魂肖像原作**三套底色**（79 黑底白线 / 21 透明黑剪影 /
64 纯白线透明底）。只看素材文件（白底看图器）会误判"64 帧什么都看不到"，
而实际要贴的是**黑底框** —— 必须在黑底上才算数。这张图就是黑底上的样子。

产物落 `D:\\_tmp190\\preview\\`，**不进仓库**。
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
REPO = os.path.abspath(os.path.join(ROUND, '..', '..'))
FACES = os.path.join(REPO, 'ralsei_pet', 'assets', 'faces')
OUT = u'D:\\_tmp190\\preview'

# 与 dialogue_ui 保持一致的口径（改了这里必须同步改那边）
BOX = 84          # face_label 的 setFixedSize(84, 84)
BORDER = 2        # border: 2px solid #ffffff
PIX = 78          # 位图基准边长（78 * ui_scale）

BG = (238, 236, 230)
INK = (25, 25, 25)
HDR = (60, 60, 60)

_FONTS = [u'C:\\Windows\\Fonts\\msyh.ttc', u'C:\\Windows\\Fonts\\msyh.ttc',
          u'C:\\Windows\\Fonts\\simhei.ttf', u'C:\\Windows\\Fonts\\simsun.ttc']


def font(size):
    for p in _FONTS:
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:  # noqa: BLE001
                continue
    return ImageFont.load_default()


def render_box(img):
    """复现 face_label：84×84 黑底 + 2px 白边 + 居中 KeepAspectRatio 贴图。"""
    box = Image.new('RGB', (BOX, BOX), (255, 255, 255))     # 外圈白（= 边框）
    inner = Image.new('RGB', (BOX - 2 * BORDER, BOX - 2 * BORDER), (0, 0, 0))
    box.paste(inner, (BORDER, BORDER))
    w, h = img.size
    s = min(PIX / float(w), PIX / float(h))
    tw, th = max(1, int(round(w * s))), max(1, int(round(h * s)))
    small = img.resize((tw, th), Image.LANCZOS)
    x = BORDER + (BOX - 2 * BORDER - tw) // 2
    y = BORDER + (BOX - 2 * BORDER - th) // 2
    box.paste(small.convert('RGB'), (x, y))
    return box


def main():
    mf = os.path.join(FACES, 'manifest.json')
    if not os.path.isfile(mf):
        print(u'[停手] 缺 manifest：%s' % mf)
        return 2
    man = json.load(io.open(mf, encoding='utf-8'))
    os.makedirs(OUT, exist_ok=True)

    # 每个角色挑这几个情绪（有就画）。顺序贴近实际会用到的高频情绪。
    WANT = ['normal', 'neutral', 'default', 'smile', 'happy', 'angry', 'sad',
            'surprised', 'smirk', 'pensive']
    by_id = {}
    for m in man:
        if m.get('kind') != 'expression' or m.get('frame') != 0:
            continue
        by_id.setdefault(m['id'], {})[m['emotion']] = m['file']

    ids = sorted(by_id)
    cols = []
    for cid in ids:
        got = [e for e in WANT if e in by_id[cid]]
        cols.append((cid, got[:6]))

    PAD = 12
    CW = BOX + 8
    ROWH = BOX + 26
    W = PAD * 2 + max(len(g) for _c, g in cols) * CW + 190
    H = 74 + len(cols) * ROWH + PAD
    sheet = Image.new('RGB', (W, H), BG)
    dr = ImageDraw.Draw(sheet)
    F_T = font(19)
    F_L = font(14)

    dr.text((PAD, 12), u'头像框实际渲染（84×84 黑底 + 2px 白边 + 居中 KeepAspectRatio）',
            fill=INK, font=F_T)
    dr.text((PAD, 40), u'这就是 dialogue_ui 现在的样子：素材一个像素没改，靠黑底让三套底色都看得清',
            fill=HDR, font=F_L)

    y = 74
    for cid, emos in cols:
        dr.text((PAD, y + BOX // 2 - 9), cid.replace('hy_', ''), fill=INK, font=F_L)
        for k, emo in enumerate(emos):
            try:
                im = Image.open(os.path.join(FACES, by_id[cid][emo].replace('/', os.sep)))
                im.load()
            except Exception:  # noqa: BLE001
                continue
            box = render_box(im.convert('RGBA'))
            x = PAD + 190 + k * CW
            sheet.paste(box, (x, y))
            dr.text((x + 2, y + BOX + 5), emo[:12], fill=HDR, font=F_L)
        y += ROWH

    p = os.path.join(OUT, 'face_boxes.png')
    sheet.save(p)
    print(u'[A] %s  %dx%d  (%d 个角色)' % (p, W, H, len(cols)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
