# -*- coding: utf-8 -*-
u"""第117轮：把「Niko 回家光门」做成**黑光**版本（OneShot 门专用）。

用户口径（逐字，10-18）
------------------------
  「oneshot 用最后 niko 回家走的那道门，但**颜色变成黑光**，
    然后 niko 的家还是用他那道，ut 的门就用你的那个就好，对了**大一点都**」

⇒ 三件事：
  ① **门 A（OneShot）**：贴图换成「Niko 回家光门」的**黑光**变体；
  ② **门 B（Niko 的家）**：仍是原版光门（**不动**）；
  ③ **门 C（UT）**：仍是 `desk_door_ut.png`（**不动**）；另加「四扇门统一放大」。

本脚本只做 ① 的**贴图生成**。为什么必须单独生成而不是"运行时调色"：
  产品里门是 `drawPixmap` 直接贴图（`scene_canvas._paint_screen_doors`），
  没有着色管线；把调色塞进渲染循环 = 每帧算 24576 像素 + 引入"素材不止一处"。
  生成一张**静态变体**既省，也让"门长什么样"仍可被回归逐像素校验。

★★★ 三条硬约束（都来自前几轮的实证教训）
  1. **绝不覆盖原件**：`niko_door_portal.png` 还被门 B（Niko 的家）用着。
  2. **alpha 一个像素都不动**：形状/摆放/尺寸全照原件 ⇒ 门不会因为换色而位移。
  3. **不许把门做成一块黑**：第116轮用户报的「黑底也没去干净」就是"整片黑"。
     所以亮度**保留层次**（40 档以上），只做「压暗 + 偏紫」的色相映射。

取色（可复算，不是"看着调"）
---------------------------
  以可见像素亮度 `l = 0.299r + 0.587g + 0.114b` 为参数 `t = l/255`：
      R = 4  + 96·t      （4 .. 100）
      G = 2  + 24·t      （2 ..  26）
      B = 6  + 84·t      （6 ..  90）
  ⇒ 最暗 = `rgb(4,2,6)`（近黑，保住原图的"暗部结构"）；
    最亮 = `rgb(100,26,90)`（**深品紫**，保住原门"品红"的色相记忆，只是压暗成"黑光"）。
  ★ 为什么不是纯灰：整张变灰会让门在深色壁纸上"糊掉"；偏紫既保留原门身份，
    又和门 B 的亮品红形成**同形不同色**的对照（用户要的正是"同一道门、换颜色"）。

产物
----
  · `ralsei_pet/assets/scenes/objs/desk_door_oneshot_black.png`（192×128，与原件同尺寸）
  · `_evidence/png117/` 三张对照：原件 / 黑光 / 棋盘合成（黑光贴在格子上看边界）
  · `_evidence/key117_black.txt` 统计
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
OBJS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'objs')
EV = os.path.join(ROUND, '_evidence')
PNG = os.path.join(EV, 'png117')

try:
    from PIL import Image, ImageDraw
except Exception as e:                                        # noqa: BLE001
    sys.stdout.write('PIL 不可用: %r\n' % (e,))
    sys.exit(2)

SRC_NAME = 'niko_door_portal.png'
DST_NAME = 'desk_door_oneshot_black.png'
SRC = os.path.join(OBJS, SRC_NAME)
DST = os.path.join(OBJS, DST_NAME)

BUF = []


def say(m=''):
    print(m)
    BUF.append(str(m))


def _lum(r, g, b):
    return 0.299 * r + 0.587 * g + 0.114 * b


def _map_px(r, g, b, a):
    u"""原像素 ⇒ 黑光像素（**alpha 原样**）。"""
    t = _lum(r, g, b) / 255.0
    return (int(round(4 + 96 * t)), int(round(2 + 24 * t)),
            int(round(6 + 84 * t)), a)


def build():
    if not os.path.isfile(SRC):
        say('原件不在盘：%s' % SRC)
        return None
    src = Image.open(SRC).convert('RGBA')
    w, h = src.size
    out = Image.new('RGBA', (w, h))
    s_px = list(src.getdata())
    o_px = [_map_px(r, g, b, a) for (r, g, b, a) in s_px]
    out.putdata(o_px)
    out.save(DST)
    return src, out, s_px, o_px


def stats(tag, px, size):
    vis = [t for t in px if t[3] > 0]
    if not vis:
        return '%s: 无可见像素' % tag
    ls = [_lum(r, g, b) for (r, g, b, _a) in vis]
    ls.sort()
    n = len(ls)

    def q(p):
        return ls[min(n - 1, int(n * p))]

    a0 = sum(1 for t in px if t[3] == 0)
    a255 = sum(1 for t in px if t[3] == 255)
    return (u'%s: 尺寸 %d×%d · alpha0=%d(%.1f%%) alpha255=%d(%.1f%%) · '
            u'可见亮度 min=%.1f p10=%.1f 中位=%.1f p90=%.1f max=%.1f · 可见档数=%d'
            % (tag, size[0], size[1], a0, 100.0 * a0 / len(px),
               a255, 100.0 * a255 / len(px), ls[0], q(0.10), q(0.50), q(0.90), ls[-1],
               len(set(int(v) for v in ls))))


def main():
    got = build()
    if not got:
        return 2
    src, out, s_px, o_px = got
    w, h = src.size
    os.makedirs(PNG, exist_ok=True)

    say(u'== 第117轮 · OneShot 门「黑光」变体 ==')
    say(u'源：%s  →  产物：%s' % (SRC_NAME, DST_NAME))
    say(u'尺寸 %d×%d（与原件一致：%s）' % (src.size[0], src.size[1],
                                          src.size == out.size))
    say(stats(u'原件', s_px, src.size))
    say(stats(u'黑光', o_px, out.size))
    # alpha 必须逐像素一致（形状不动）
    same_a = all(x[3] == y[3] for x, y in zip(s_px, o_px))
    say(u'alpha 逐像素一致 = %s' % same_a)
    # 亮部档数（防"糊成一块"）
    # ★★ 这里踩过一次「阈值用代理量」：首版写死 `>= 40 档`，而**原件本身只有 20 档**
    #    （1787 字节的索引色 PNG，就是几十种色块的平涂）⇒ 判据恒假、报"一块黑"，
    #    可实际上黑光有 16 档、和原件同构。⇒ 改成**相对口径**：
    #    ① 档数不少于原件的 60%；② 最亮值必须真"黑"（≤120）；③ 但不能全黑（≥30）。
    vis_l = [_lum(r, g, b) for (r, g, b, a) in o_px if a > 0]
    src_l = [_lum(r, g, b) for (r, g, b, a) in s_px if a > 0]
    levels = len(set(int(v) for v in vis_l))
    src_levels = len(set(int(v) for v in src_l))
    lv_need = max(6, int(src_levels * 0.6))
    mx = max(vis_l) if vis_l else 0
    say(u'黑光可见亮度档数 = %d（原件 %d 档；要求 ≥ %d）' % (levels, src_levels, lv_need))
    say(u'黑光最亮 = %.1f（要求 30 ≤ max ≤ 120：既真"黑"，又不至于整块看不见）' % mx)

    # 对照图：原件 | 黑光 | 棋盘上的黑光
    scale = 2
    pad = 8
    cw, ch = w * scale, h * scale
    canvas = Image.new('RGBA', (cw * 3 + pad * 4, ch + pad * 2), (24, 24, 28, 255))
    canvas.paste(src.resize((cw, ch), Image.NEAREST), (pad, pad), src.resize((cw, ch), Image.NEAREST))
    canvas.paste(out.resize((cw, ch), Image.NEAREST), (cw + pad * 2, pad),
                 out.resize((cw, ch), Image.NEAREST))
    # 棋盘背景（64px 格，模拟桌面壁纸明暗两档都要能看出边界）
    board = Image.new('RGBA', (cw, ch), (40, 44, 52, 255))
    d = ImageDraw.Draw(board)
    cell = 32
    for yy in range(0, ch, cell):
        for xx in range(0, cw, cell):
            if (xx // cell + yy // cell) % 2 == 0:
                d.rectangle([xx, yy, xx + cell - 1, yy + cell - 1], fill=(196, 200, 208, 255))
    big = out.resize((cw, ch), Image.NEAREST)
    board.paste(big, (0, 0), big)
    canvas.paste(board, (cw * 2 + pad * 3, pad))
    p_comp = os.path.join(PNG, 'oneshot_black_compare.png')
    canvas.save(p_comp)

    p_src = os.path.join(PNG, 'src_niko_door_portal.png')
    src.resize((cw, ch), Image.NEAREST).save(p_src)
    p_dst = os.path.join(PNG, 'dst_desk_door_oneshot_black.png')
    out.resize((cw, ch), Image.NEAREST).save(p_dst)

    say(u'对照图：%s' % p_comp)
    say(u'（左=原件 品红光门 · 中=黑光变体 · 右=黑光叠在深浅棋盘上）')

    with io.open(os.path.join(EV, 'key117_black.txt'), 'w',
                 encoding='utf-8', newline='\n') as f:
        f.write(u'\n'.join(BUF) + u'\n')

    ok = (same_a and levels >= lv_need and 30 <= mx <= 120
          and os.path.getsize(DST) > 0)
    say(u'\n结论 = %s' % ('OK' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
