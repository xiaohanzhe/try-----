# -*- coding: utf-8 -*-
u"""check118_rec.py —— 第118轮**录屏逐帧判据**（独立重读 avi + csv，不信录屏脚本的输出）。

用户口径（逐字，10-19）
----------------------
「**可以，你自己录屏，记住，以人类的视角评价，也就是，你只认图案而非字符，ok？
然后继续推进就好**」

⇒ 本文件里的判据**一律是图案/几何级的**：门在哪条边、门贴图有没有真的画上去、
红心在哪一行、框和对话框有没有叠。**不读任何日志字符串**、不看"代码里有没有写
`drawPixmap`"这种字面证据。

为什么要"独立重读"而不是直接信 `rec118.py` 打印的东西
------------------------------------------------------
第117轮的教训：判据要用**产品之外**的原始数据重算一遍。录屏脚本自己打印的
"我抓了默认态"只能证明它**调用了**抓图；证明"图上真有一颗红心、真的换行了"，
必须回到 avi 的像素上量。

★ 而且录屏脚本本身犯过两个错（都已在 `rec118.py` 里写清）：
  ① 在 tick 槽里直接调 `interact_scene_prop()` ⇒ 同一个 QTimer 不能重入自己
     ⇒ 模态期间 8.3 s 零帧；
  ② 存 PNG 时把 BGR 当 RGB ⇒ **红蓝颠倒**，红心看起来是蓝的。
  ⇒ 本文件对这两个坑各留一条**反向判据**（R6 / C7），它们必须**报红**才说明
     夹具没被坑 —— 如果哪天有人把这两处改回去，这里会立刻发现。

跑法
----
  C:\\Python311\\python.exe code-quality-audit\\第118轮-桌面门可达性\\_tools\\check118_rec.py
"""
import csv
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROUND = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
EV = os.path.join(ROUND, '_evidence', 'rec118')
# ★ 输入可覆盖：变异测试（`mutate118_rec.py`）要在**临时副本**上跑，
#   不能动仓库里那份真证据。默认仍指向真实证据。
AVI = os.environ.get('RALSEI_REC118_AVI') or os.path.join(EV, 'rec118.avi')
CSVP = os.environ.get('RALSEI_REC118_CSV') or os.path.join(EV, 'rec118_frames.csv')
SCN = os.path.join(ROOT, 'ralsei_pet', 'assets', 'scenes', 'objs')

L = []
FAILS = [0]
PASSES = [0]


def ck(cond, name, detail=''):
    cond = bool(cond)
    line = ('[PASS] %s' % name) if cond else ('[FAIL] %s' % name)
    # ★★★ 教训（第118轮 `check118.py` 踩过）：必须先把**这一行本身**打出来，
    #   detail 单独打。曾经写成 "append(FAIL 行) → append(detail) → print(L[-1])"
    #   ⇒ 打印的永远是 detail，`[FAIL]` 前缀一次都没出现过，变异测试全判 MISSED。
    L.append(line)
    print(line)
    if not cond:
        FAILS[0] += 1
        if detail:
            d = '       detail: %s' % (detail,)
            L.append(d)
            print(d)
    else:
        PASSES[0] += 1


def hdr(t):
    s = '--- %s ---' % t
    L.append(s)
    print(s)


if not (os.path.isfile(AVI) and os.path.isfile(CSVP)):
    print('[FAIL] 缺少证据：%s / %s' % (AVI, CSVP))
    sys.exit(1)

import cv2                                                       # noqa: E402
import numpy as np                                               # noqa: E402
from PIL import Image                                            # noqa: E402

ROWS = list(csv.DictReader(io.open(CSVP, encoding='utf-8', newline='')))
SPR = {'A': 'desk_door_oneshot_black.png', 'B': 'niko_door_portal.png',
       'C': 'desk_door_ut.png', 'D': 'desk_door_deltarune.png'}


def num(r, k, d=0.0):
    try:
        return float(r.get(k, '') or d)
    except (TypeError, ValueError):
        return d


cap = cv2.VideoCapture(AVI)
NFR = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
_CACHE = {}


def frame(i):
    if i in _CACHE:
        return _CACHE[i]
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
    ok, f = cap.read()
    _CACHE[i] = f if ok else None
    return _CACHE[i]


def first_frame():
    return frame(0)


f0 = first_frame()
if f0 is None:
    print('[FAIL] avi 打不开')
    sys.exit(1)
SCR_H, SCR_W = f0.shape[0], f0.shape[1]

# ============================================================ R 组：录像/门
hdr('R 组：录像完整性与四门几何（图案/几何级）')

ck(NFR > 0 and abs(NFR - len(ROWS)) <= 2,
   'R1 avi 帧数与 csv 行数一致',
   'avi=%d csv=%d（录屏必须"每帧都有账"）' % (NFR, len(ROWS)))

# ---- 门的矩形：每帧都在，且四扇都有 ----
RECT = {}
DRIFT = {}
for L2 in 'ABCD':
    xs = [(num(r, L2 + '_x'), num(r, L2 + '_y'),
           num(r, L2 + '_w'), num(r, L2 + '_h')) for r in ROWS
          if num(r, L2 + '_w') > 0]
    DRIFT[L2] = sorted(set(xs))
    if xs:
        RECT[L2] = xs[0]
ck(all(L2 in RECT for L2 in 'ABCD'), 'R2a 四门矩形全程都有记录',
   '拿到 %r' % sorted(RECT))
# ★ 每扇门的矩形**全程只能有一种**（第112轮续三的核心 bug 就是"门跟着动画一跳一跳"）
bad = {k: v for k, v in DRIFT.items() if len(v) > 1}
ck(not bad, 'R2b 每扇门的矩形**全程不漂移**（没有一帧换过位置/尺寸）',
   '漂移的门：%r' % {k: v[:4] for k, v in bad.items()})

# ---- 每条边：门贴着自己的那条边 ----
if all(L2 in RECT for L2 in 'ABCD'):
    ax, ay, aw, ah = RECT['A']
    bx, by, bw, bh = RECT['B']
    cx, cy, cw, chh = RECT['C']
    dx, dy, dw, dh = RECT['D']
    ck(ay <= 2, 'R3a 门 A 在**正上**边（top<=2）',
       'A=(%g,%g,%g,%g)' % (ax, ay, aw, ah))
    ck(cx <= 2, 'R3b 门 C 在**正左**边（left<=2）',
       'C=(%g,%g,%g,%g)' % (cx, cy, cw, chh))
    ck(dx + dw >= SCR_W - 2, 'R3c 门 D 在**正右**边（right>=屏宽-2）',
       'D=(%g,%g,%g,%g) 屏宽=%d' % (dx, dy, dw, dh, SCR_W))
    tb = SCR_H - (by + bh)
    ck(0 < tb < 140, 'R3d 门 B 在**正下**边且正好压在任务栏上沿',
       'B=(%g,%g,%g,%g) 距屏底 %g px（工作区底 = 屏高-任务栏）'
       % (bx, by, bw, bh, tb))
    ck(abs((by + bh) - max(ay + ah, by + bh, cy + chh, dy + dh)) < 1,
       'R3e 门 B 的底边就是四门里最靠下的那条（= 工作区底）',
       'B_bottom=%g' % (by + bh))

# ---- 站在门上时门必须全显（alpha>=0.99）----
hdr('R 组：门渐显在"站上去"时必须到 1.0')
for L2 in 'ABCD':
    idx = [i for i, r in enumerate(ROWS)
           if r['step'].endswith('_hold') and ('_%s_' % L2) in r['step']]
    if not idx:
        ck(False, 'R4%s 门 %s 有 hold 段帧' % (L2, L2), 'csv 里没有该段的帧')
        continue
    al = [num(ROWS[i], L2 + '_alpha', -1.0) for i in idx]
    ck(min(al) >= 0.99, 'R4%s 站到门 %s 上时 alpha 到 1.0' % (L2, L2),
       'alpha 序列最小值 %.3f（%d 帧）' % (min(al), len(al)))

# ---- 门贴图**真的画在屏幕上**（像素比对，带配对负控制）----
hdr('R 组：门贴图是否真的落到了屏幕上（像素比对 + 配对负控制）')


def sprite_bgra(letter, w, h):
    p = os.path.join(SCN, SPR[letter])
    im = Image.open(p).convert('RGBA')
    if im.size != (int(w), int(h)):
        im = im.resize((int(w), int(h)), Image.NEAREST)   # 产品落笔 = 最近邻
    a = np.array(im)
    return a[:, :, :3][:, :, ::-1].astype(int), a[:, :, 3] >= 250   # RGB→BGR


def hit_rate(letter, rect, fi):
    x, y, w, h = [int(v) for v in rect]
    fr = frame(fi)
    if fr is None or w <= 0 or h <= 0:
        return None, 0
    sub = fr[y:y + h, x:x + w].astype(int)
    spr, m = sprite_bgra(letter, w, h)
    if sub.shape[:2] != spr.shape[:2] or not m.any():
        return None, 0
    d = np.abs(sub - spr).max(axis=2)
    return float(((d <= 12) & m).sum()) / float(m.sum()), int(m.sum())


THR = {'A': 0.60, 'B': 0.20, 'C': 0.50, 'D': 0.10}
for L2 in 'ABCD':
    idx = [i for i, r in enumerate(ROWS)
           if r['step'].endswith('_hold') and ('_%s_' % L2) in r['step']]
    if not idx or L2 not in RECT:
        ck(False, 'R5%s 门 %s 有可判帧' % (L2, L2), '缺 hold 帧或矩形')
        continue
    hr, npx = hit_rate(L2, RECT[L2], idx[-1])
    okk = hr is not None and hr >= THR[L2]
    ck(okk, 'R5%s 门 %s 的贴图真的画在该矩形里（命中>=%.0f%%）'
       % (L2, L2, THR[L2] * 100),
       '命中 %s / 不透明 %d px（阈值 %.0f%%；avi 是有损压缩，细线门天然偏低）'
       % ('None' if hr is None else '%.1f%%' % (hr * 100), npx, THR[L2] * 100))
    # ★ 配对负控制：同一个矩形换一张**别的门**的贴图 ⇒ 命中率必须显著更低
    if L2 in ('C', 'A'):
        other = 'D' if L2 == 'C' else 'B'
        hr2, _ = hit_rate(other, RECT[L2], idx[-1])
        ck(hr2 is not None and hr is not None and hr > hr2 + 0.10,
           'R5%s 负控制：门 %s 的矩形拿去比门 %s 的贴图，命中显著更低'
           % (L2, L2, other),
           '本门 %.1f%% vs 别门 %s' % ((hr or 0) * 100,
                                       'None' if hr2 is None else '%.1f%%' % (hr2 * 100)))

# ---- 四个世界真的进去过 ----
hdr('R 组：真的进了那四个世界（看场景列，不看日志）')
WANT = [('A', 'oneshot'), ('C', 'ut.rooms.room_start'), ('D', 'ch1.hometown.town_mid')]
for L2, pre in WANT:
    n = sum(1 for r in ROWS if str(r.get('scene', '')).startswith(pre))
    ck(n >= 5, 'R6%s 门 %s 真的切到了 %s（录像里 >=5 帧）' % (L2, L2, pre),
       '命中 %d 帧' % n)
nb = [r for r in ROWS if r['step'] == 'P4_B_ask']
ck(len(nb) >= 5 and all(str(r.get('scene', '')) == 'desktop' for r in nb),
   'R6B 门 B 是彩蛋门：全程留在 desktop（**不进任何世界**）',
   'P4_B_ask 共 %d 帧' % len(nb))
ck(str(ROWS[-1].get('scene', '')) == 'desktop', 'R7 录像结束时回到桌面')

# ============================================================ C 组：选择框
hdr('C 组：原作式选择框（**只看图案**：红心在哪一行、框在哪）')


def heart_in(fr, box):
    u"""框内"纯红"像素的 (y 质心, x 质心, 个数)。**不看任何文字**。"""
    x, y, w, h = [int(v) for v in box]
    if fr is None or w <= 0 or h <= 0:
        return None
    sub = fr[y:y + h, x:x + w].astype(int)              # BGR
    b, g, r = sub[:, :, 0], sub[:, :, 1], sub[:, :, 2]
    m = (r > 180) & (g < 70) & (b < 70)
    n = int(m.sum())
    if n < 20:
        return None
    ys, xs = np.nonzero(m)
    return (float(ys.mean()) + y, float(xs.mean()) + x, n)


MODAL = [i for i, r in enumerate(ROWS) if str(r.get('modal', '')) == '1']
ck(len(MODAL) >= 8, 'C1 选择框在录像里出现了足够多帧（>=8）',
   '模态帧 %d 个（第一版夹具只有 0 个 —— 那时模态期间零帧）' % len(MODAL))

if MODAL:
    hb = []
    for i in MODAL:
        r = ROWS[i]
        box = (num(r, 'dlg_x'), num(r, 'dlg_y'), num(r, 'dlg_w'), num(r, 'dlg_h'))
        hy = heart_in(frame(i), box)
        hb.append((i, box, hy))
    got = [t for t in hb if t[2] is not None]
    ck(len(got) == len(hb), 'C2 每个模态帧的框内都能找到红心',
       '找到 %d / %d 帧' % (len(got), len(hb)))
    # ★★★ 教训（本文件第一版自己踩的）：C3~C10 原来整段写在 `if got:` 里
    #   ⇒ 一旦 C2 失败（找不到红心），后面 8 条判据**静默跳过**，
    #   既不 PASS 也不 FAIL。变异测试 M10 就是这么漏掉的（它只让 C2 红了，
    #   C10 根本没机会跑）。⇒ 规矩：**不能评估就如实 FAIL**，绝不静默消失。
    if got:
        ys = [t[2][0] for t in got]
        xs = [t[2][1] for t in got]
        ns = [t[2][2] for t in got]
        ck(max(xs) - min(xs) <= 2.0, 'C3 红心**横向不漂移**（x 抖动 <=2 px）',
           'x ∈ [%.1f, %.1f]' % (min(xs), max(xs)))
        lv = sorted(set(round(y, 1) for y in ys))
        ck(len(lv) == 2, 'C4 红心只停过**两档 y**（两行选项）',
           '出现的 y 档位 = %r' % (lv,))
        if len(lv) == 2:
            dy = lv[1] - lv[0]
            ck(30.0 <= dy <= 38.0, 'C5 两档之间正好**一行**（30~38 px，行高 34×scale）',
               '实测 %.1f px' % dy)
        else:
            ck(False, 'C5 两档之间正好**一行**（30~38 px，行高 34×scale）',
               '只有 %d 档 y，量不了行距：%r' % (len(lv), lv))
        ck(max(ns) - min(ns) <= 0.15 * max(ns), 'C6 两档里红心像素数一致（没换素材/没变形）',
           'n ∈ [%d, %d]' % (min(ns), max(ns)))
    else:
        for _n in ('C3 红心**横向不漂移**（x 抖动 <=2 px）',
                   'C4 红心只停过**两档 y**（两行选项）',
                   'C5 两档之间正好**一行**（30~38 px，行高 34×scale）',
                   'C6 两档里红心像素数一致（没换素材/没变形）'):
            ck(False, _n, '无法评估：框内没找到红心 ⇒ 如实 FAIL（不许静默跳过）')

    r0 = ROWS[MODAL[0]]
    bx = (num(r0, 'dlg_x'), num(r0, 'dlg_y'), num(r0, 'dlg_w'), num(r0, 'dlg_h'))
    fr0 = frame(MODAL[0])
    # ★ 反向判据：红蓝**没有**颠倒。素材是纯红 (255,0,0)。
    if fr0 is not None:
        sub = fr0[int(bx[1]):int(bx[1] + bx[3]),
                  int(bx[0]):int(bx[0] + bx[2])].astype(int)
        b, g, r_ = sub[:, :, 0], sub[:, :, 1], sub[:, :, 2]
        nred = int(((r_ > 180) & (g < 70) & (b < 70)).sum())
        nblue = int(((b > 180) & (g < 70) & (r_ < 70)).sum())
        ck(nred > 50 and nred > 5 * max(1, nblue),
           'C7 红心是**红的**（红蓝没颠倒 —— 第一版裁图把 BGR 当 RGB 用，红心成了纯蓝）',
           '框内 纯红=%d px / 纯蓝=%d px' % (nred, nblue))
    else:
        ck(False, 'C7 红心是**红的**（红蓝没颠倒…）', '取不到模态帧')
    # ★ 负控制：同一块框区域，在**非模态帧**里不应有这颗心
    nonm = [i for i in range(len(ROWS)) if str(ROWS[i].get('modal', '')) != '1']
    hits = 0
    tried = 0
    for i in nonm[:120]:
        tried += 1
        if heart_in(frame(i), bx) is not None:
            hits += 1
    ck(tried >= 20 and hits <= max(1, int(0.15 * tried)),
       'C8 负控制：同一块矩形在**非模态帧**里基本找不到这颗心',
       '试了 %d 帧，命中 %d 帧（若恒命中 ⇒ 判据被壁纸喂饱了）' % (tried, hits))

    # ---- 几何判据：**无条件跑**（不依赖像素）----
    geos = set((num(r, 'dlg_x'), num(r, 'dlg_y'),
                num(r, 'dlg_w'), num(r, 'dlg_h')) for r in (ROWS[i] for i in MODAL))
    ck(len(geos) == 1, 'C9 框的几何全程不漂移（x/y/w/h 恒定）',
       '出现 %d 种几何：%r' % (len(geos), sorted(geos)[:3]))
    # ---- 框必须**在对话框上方、不与之重叠** ----
    #   第118轮真机录屏发现：原来固定贴底 ⇒ 和对话气泡叠了 61 px，
    #   裁图里能看到对话气泡的左上角从选择框左边戳出来。
    #   ★ 对话气泡的矩形没进 csv（那是我录屏脚本的疏漏），所以这条退一步判：
    #     框底边必须**明显高于**旧摆法的底边（旧 = 1261+146 = 1407）。
    gy = max(geos, key=lambda t: t[1])[1] if geos else 0
    gh = max(geos, key=lambda t: t[3])[3] if geos else 0
    ck(gy + gh < 1250, 'C10 框不再压在最底下（旧的贴底摆法底边=1407 ⇒ 会与对话气泡重叠）',
       '框底边 = %g（旧摆法 = 1407）' % (gy + gh))

# ============================================================ F 组：判据自身
hdr('F 组：判据自身（恒真 / 输入为空）')
ck(PASSES[0] + FAILS[0] == len([x for x in L if x.startswith('[PASS]') or x.startswith('[FAIL]')]),
   'F1 判据条数记账一致',
   'PASS=%d FAIL=%d' % (PASSES[0], FAILS[0]))
ck(len(ROWS) > 100 and SCR_W > 1000, 'F2 输入不是空的（帧数/画面尺寸都合理）',
   'rows=%d 屏=%dx%d' % (len(ROWS), SCR_W, SCR_H))
# ★ 恒真检查：`heart_in` 对一张全黑图必须返回 None
ck(heart_in(np.zeros((60, 60, 3), np.uint8), (0, 0, 60, 60)) is None,
   'F3 `heart_in` 对全黑图返回 None（判据不是恒真）')

cap.release()
print('')
print('==== check118_rec: PASS=%d FAIL=%d ====' % (PASSES[0], FAILS[0]))
sys.exit(1 if FAILS[0] else 0)
