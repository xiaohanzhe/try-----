# -*- coding: utf-8 -*-
u"""cmp116_doors.py —— 四扇门贴图的**数字**对照（原件 vs 桌面变体）。

为什么要它
----------
`desktop.json` 的 `_comment.round116_desk_door_sprites` 里写了几个数
（纯黑 76.4% / 82.6% ⇒ 变体 0.000），那是**上一会话**的结果。按用户口径
「**以后再调整重要核心文件时一定要记得复检**」，这些数必须**现算一遍**
—— 不能拿旧结论当证据（本项目同类踩坑已多次）。

判据（每条都打印实测值，人可复核）
----------------------------------
  ① 变体与原件**像素尺寸一字不变**（否则门摆位会跟着变）；
  ② 变体的「纯黑比」（max(R,G,B)<=26 且 alpha>=250）**必须**降到 0.000；
  ③ 变体的「全透明比」（alpha<=8）**必须**显著上升；
  ④ 门 A / 门 B **不产变体**（用户第112轮逐字「oneshot 和 niko 的家不变」）
     —— 这条由「文件不存在」来体现，这里只报存在性。

跑法
----
  C:\\Python311\\python.exe "...\\_tools\\cmp116_doors.py"
输出落 `_evidence/rec116/cmp116_doors.txt`。
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
OBJS = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'objs')
OUT = os.path.join(ROUND, '_evidence', 'rec116')
os.makedirs(OUT, exist_ok=True)

BLACK_MAX = 26          # 与 `key116_doors.py --key` 同口径
ALPHA_SOLID = 250
ALPHA_CLEAR = 8

#: (字母, 原件, 桌面变体 or None)
PAIRS = [
    ('A', 'spr_darkdoor_0.png', None),          # OneShot —— 用户「不变」
    ('B', 'niko_door_portal.png', None),        # Niko 的家 —— 用户「不变」
    ('C', 'ut_castle_realdoor_0.png', 'desk_door_ut.png'),
    ('D', 'spr_giantdarkdoor_0.png', 'desk_door_deltarune.png'),
]


def _load(path):
    u"""⇒ `[(r,g,b,a), ...]`（宽*高 个）。取不到 ⇒ None。"""
    try:
        from PyQt5.QtGui import QImage
    except Exception as e:
        print('[cmp116] PyQt5 不可用: %r' % (e,))
        return None
    img = QImage(path)
    if img.isNull():
        return None
    img = img.convertToFormat(QImage.Format_ARGB32)
    px = []
    w, h = img.width(), img.height()
    for y in range(h):
        for x in range(w):
            c = img.pixel(x, y)
            px.append(((c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF,
                       (c >> 24) & 0xFF))
    return (w, h, px)


def _stats(t):
    w, h, px = t
    n = float(len(px))
    black = 0
    clear = 0
    for r, g, b, a in px:
        if a <= ALPHA_CLEAR:
            clear += 1
        elif a >= ALPHA_SOLID and max(r, g, b) <= BLACK_MAX:
            black += 1
    return {'w': w, 'h': h, 'n': len(px),
            'black': black / n, 'clear': clear / n}


def main():
    rep = [u'# cmp116_doors —— 四扇门贴图原件 / 桌面变体 数字对照']
    rep.append(u'# 纯黑口径：alpha >= %d 且 max(R,G,B) <= %d' % (ALPHA_SOLID,
                                                                BLACK_MAX))
    rep.append(u'# 全透明口径：alpha <= %d' % ALPHA_CLEAR)
    rep.append(u'')
    bad = 0
    for letter, orig, var in PAIRS:
        po = os.path.join(OBJS, orig)
        rep.append(u'== 门%s ==' % letter)
        if not os.path.isfile(po):
            rep.append(u'  [FAIL] 原件不在盘: %s' % orig)
            bad += 1
            continue
        so = _stats(_load(po))
        rep.append(u'  原件 %-26s %dx%d  纯黑=%.4f  全透明=%.4f'
                   % (orig, so['w'], so['h'], so['black'], so['clear']))
        if var is None:
            rep.append(u'  ⇒ 用户第112轮逐字「oneshot 和 niko 的家不变」'
                       u' ⇒ 按口径**不产变体**')
            rep.append(u'')
            continue
        pv = os.path.join(OBJS, var)
        if not os.path.isfile(pv):
            rep.append(u'  [FAIL] 变体不在盘: %s' % var)
            bad += 1
            continue
        sv = _stats(_load(pv))
        rep.append(u'  变体 %-26s %dx%d  纯黑=%.4f  全透明=%.4f'
                   % (var, sv['w'], sv['h'], sv['black'], sv['clear']))
        same_size = (so['w'] == sv['w']) and (so['h'] == sv['h'])
        rep.append(u'  ① 尺寸不变: %s' % (u'OK' if same_size else u'!! 变了'))
        if not same_size:
            bad += 1
        if sv['black'] > 0.0:
            rep.append(u'  ② 纯黑比降为 0: !! 仍为 %.4f' % sv['black'])
            bad += 1
        else:
            rep.append(u'  ② 纯黑比降为 0: OK（%.4f -> %.4f）'
                       % (so['black'], sv['black']))
        if sv['clear'] <= so['clear']:
            rep.append(u'  ③ 全透明比上升: !! %.4f -> %.4f'
                       % (so['clear'], sv['clear']))
            bad += 1
        else:
            rep.append(u'  ③ 全透明比上升: OK（%.4f -> %.4f）'
                       % (so['clear'], sv['clear']))
        rep.append(u'')
    # ---- 全局判据：桌面变体**只应有 2 个**（C/D）----
    #  ★ 这条是上面"门 A/B 不产变体"的**机器化**：不靠人肉记得，靠列目录。
    _found = sorted(f for f in os.listdir(OBJS)
                    if f.startswith('desk_door_') and f.endswith('.png'))
    _want = ['desk_door_deltarune.png', 'desk_door_ut.png']
    rep.append(u'== objs/desk_door_*.png 清单 ==')
    rep.append(u'  实到 %r' % (_found,))
    rep.append(u'  应为 %r' % (_want,))
    if _found != _want:
        rep.append(u'  [FAIL] 变体清单不符（多做了 A/B 的变体，或少了 C/D）')
        bad += 1
    else:
        rep.append(u'  OK')
    rep.append(u'')
    rep.append(u'合计不合规项 = %d' % bad)
    txt = u'\n'.join(rep) + u'\n'
    with io.open(os.path.join(OUT, 'cmp116_doors.txt'), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write(txt)
    sys.stdout.write(txt)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
