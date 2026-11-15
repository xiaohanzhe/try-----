# -*- coding: utf-8 -*-
u"""第190轮 · 「台词 → 表情」整链演示图（**不依赖 Qt**）。

## 这张图想证明什么

不是"函数返回了值"，而是**用户肉眼能看到的那个结果**：

    台词「（苦笑）算了，随你吧。」

      ① `strip_action_parentheticals(sink=acts)` ⇒ 屏幕上的字变成「算了，随你吧。」
      ② `acts = ['苦笑']` ⇒ `acts_to_emotion` ⇒ `'sad'`
      ③ 该角色候选链命中真实素材 ⇒ 头像变成**难过的脸**

中间任何一环断了，右边那张头像就不会变。所以每行都同时打印
"屏幕上的字 / 抓到的动作 / 映射出的情绪 / 最后用了哪张图"，一眼能看出断在哪。

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

sys.path.insert(0, os.path.join(REPO, 'ralsei_pet'))
from modules import event_speech as E          # noqa: E402
from modules import dialogue_ui as D           # noqa: E402

BOX, BORDER, PIX = 84, 2, 78
BG = (238, 236, 230)
INK = (25, 25, 25)
HDR = (95, 92, 86)
GREEN = (30, 110, 60)
RED = (160, 40, 40)

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
    """复现 face_label：84×84 黑底 + 2px 白边 + 居中 KeepAspectRatio。"""
    box = Image.new('RGB', (BOX, BOX), (255, 255, 255))
    box.paste(Image.new('RGB', (BOX - 2 * BORDER, BOX - 2 * BORDER), (0, 0, 0)),
              (BORDER, BORDER))
    w, h = img.size
    s = min(PIX / float(w), PIX / float(h))
    tw, th = max(1, int(round(w * s))), max(1, int(round(h * s)))
    sm = img.resize((tw, th), Image.LANCZOS)
    box.paste(sm.convert('RGB'),
              (BORDER + (BOX - 2 * BORDER - tw) // 2,
               BORDER + (BOX - 2 * BORDER - th) // 2))
    return box


CASES = [
    (u'（笑）你说什么呢。', u'hy_ceroba_ketsukane'),
    (u'（苦笑）算了，随你吧。', u'hy_starlo'),
    (u'（想了想）那倒也是。', u'hy_chujin_ketsukane'),
    (u'（叹气）今天真是累。', u'hy_mooch'),
    (u'嗯（笑）我在呢。', u'hy_ace'),
    (u'（轻轻敲了敲键盘）在吗', u'hy_axis'),
]


def main():
    mf = os.path.join(FACES, 'manifest.json')
    if not os.path.isfile(mf):
        print(u'[停手] 缺 manifest')
        return 2
    man = json.load(io.open(mf, encoding='utf-8'))
    have = {}
    for m in man:
        if m.get('kind') == 'expression':
            have.setdefault(m['id'], {})[m['emotion']] = m['file']
    os.makedirs(OUT, exist_ok=True)

    ROWH = 116
    W = 1180
    H = 78 + len(CASES) * ROWH + 16
    sheet = Image.new('RGB', (W, H), BG)
    dr = ImageDraw.Draw(sheet)
    F_T = font(19)
    F_L = font(14)
    F_S = font(13)
    F_BIG = font(17)

    dr.text((14, 12), u'括号 → 表情 整链演示（左边是屏幕上会显示的字，右边是头像框会变成的样子）',
            fill=INK, font=F_T)
    dr.text((14, 40), u'素材一个像素没改；黑底是 dialogue_ui 的 face_label 底色（#000000 + 2px 白边）',
            fill=HDR, font=F_L)

    y = 78
    for line, cid in CASES:
        acts = []
        shown = E.strip_action_parentheticals(line, sink=acts)
        emo = E.acts_to_emotion(acts)

        hit, path = None, None
        for nm in D._char_face_candidates(emo):
            if nm.lower() in have.get(cid, {}):
                hit = nm
                path = os.path.join(FACES, have[cid][nm].replace('/', os.sep))
                break
        ok = bool(path and os.path.isfile(path))

        # 行分隔
        dr.line([(14, y - 4), (W - 14, y - 4)], fill=(214, 211, 203))

        # 台词（原文用灰色划掉的感觉 → 用灰字，处理后用黑字）
        dr.text((16, y + 6), u'原文', fill=HDR, font=F_S)
        dr.text((66, y + 4), line, fill=(150, 147, 140), font=F_BIG)
        dr.text((16, y + 34), u'显示', fill=HDR, font=F_S)
        dr.text((66, y + 32), shown if shown else u'（空 ⇒ 判无效，重采样）',
                fill=INK, font=F_BIG)
        # 中间量
        dr.text((470, y + 6), u'抓到 %s' % (acts or [u'—']), fill=HDR, font=F_S)
        dr.text((470, y + 26), u'情绪 %s' % emo, fill=GREEN, font=F_S)
        dr.text((470, y + 46), u'命中 %s' % (hit or u'❌ 落空'), fill=GREEN if ok else RED,
                font=F_S)
        dr.text((470, y + 66), u'角色 %s' % cid.replace('hy_', ''), fill=HDR, font=F_S)
        # ★★ 如实标出**已知缺口**（§10.7）：台词里还有括号、但护栏没删它，
        #    所以不会触发表情。不做修饰 —— 藏着的话用户会以为是这一行写错了。
        if (u'（' in line or u'(' in line) and not acts:
            dr.text((470, y + 84), u'[!] 括号未被护栏处理 ⇒ 不换表情（已知缺口 §10.7）',
                    fill=RED, font=F_S)

        # 头像框
        if ok:
            try:
                im = Image.open(path)
                im.load()
                sheet.paste(render_box(im.convert('RGBA')), (860, y + 6))
            except Exception:  # noqa: BLE001
                pass
        y += ROWH

    p = os.path.join(OUT, 'chain_demo.png')
    sheet.save(p)
    print(u'[A] %s  %dx%d' % (p, W, H))
    for line, cid in CASES:
        acts = []
        shown = E.strip_action_parentheticals(line, sink=acts)
        print(u'   %-22s → %-20s acts=%-16r emo=%s'
              % (line, shown, acts, E.acts_to_emotion(acts)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
